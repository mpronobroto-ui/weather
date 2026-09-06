"""
PostgreSQL/PostGIS-backed GIS layer.

Real spatial lookups (point-in-polygon against district boundaries) rather
than just carrying a bare lat/lon around — this is the seam the brief calls
for under "GIS tools" and "urban planning" use cases: once real Survey-of-
India / OSM district polygons are loaded into the `districts` table (see
`SQL/districts.sql`), advisories can be scoped to an actual administrative
unit ("Purba Bardhaman district, West Bengal") instead of a raw coordinate,
and could later be used to draw hazard polygons on a map.

Runs on PostgreSQL 13+ with the PostGIS extension enabled — PostGIS is the
de-facto standard spatial engine (a proper geography type, GiST spatial
indexes, and a much larger function library than MySQL's spatial
extensions), which reads as the more credible "GIS tools" choice for a
smart-city / urban-planning pitch than plain MySQL spatial columns.
Coordinates use the standard EPSG:4326 (lon, lat) ordering throughout,
matching GeoJSON and the rest of this app.

Degrades gracefully: if Postgres isn't reachable or `asyncpg` isn't
installed, `lookup_district` simply returns None and the rest of the app
carries on using plain coordinates — nothing else depends on this being
available.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("gis")

# DATABASE_URL takes priority (the usual convention on Render/Heroku/etc,
# e.g. "postgresql://user:pass@host:5432/weathergpt"); individual
# PG*-style vars are supported too for local/manual setups.
DATABASE_URL = os.getenv("DATABASE_URL")
PG_HOST = os.getenv("PG_HOST", os.getenv("POSTGRES_HOST", "localhost"))
PG_PORT = int(os.getenv("PG_PORT", os.getenv("POSTGRES_PORT", "5432")))
PG_USER = os.getenv("PG_USER", os.getenv("POSTGRES_USER", "postgres"))
PG_PASSWORD = os.getenv("PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", ""))
PG_DB = os.getenv("PG_DB", os.getenv("POSTGRES_DB", "weathergpt"))

_pool = None
_unavailable = False


async def _get_pool():
    global _pool, _unavailable
    if _unavailable:
        return None
    if _pool is not None:
        return _pool
    try:
        import asyncpg
    except ImportError:
        logger.info("GIS: asyncpg not installed, district lookup disabled")
        _unavailable = True
        return None
    try:
        if DATABASE_URL:
            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL, min_size=1, max_size=5, command_timeout=5,
            )
        else:
            _pool = await asyncpg.create_pool(
                host=PG_HOST,
                port=PG_PORT,
                user=PG_USER,
                password=PG_PASSWORD,
                database=PG_DB,
                min_size=1,
                max_size=5,
                command_timeout=5,
            )
        return _pool
    except Exception as exc:
        logger.info("GIS: could not connect to PostgreSQL (%s) — district lookup disabled", exc)
        _unavailable = True
        return None


async def lookup_district(lat: float, lon: float) -> dict | None:
    """Return {"state": ..., "district": ...} for the district polygon
    containing (lat, lon), or None if unavailable / no match.
    """
    pool = await _get_pool()
    if pool is None:
        return None
    # ST_SetSRID(..., 4326) matches the districts table's declared SRID;
    # ST_Contains does an exact point-in-polygon test against the geometry.
    query = """
        SELECT state, district
        FROM districts
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
        LIMIT 1;
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, lon, lat)
        if row:
            return {"state": row["state"], "district": row["district"]}
        return None
    except Exception as exc:
        logger.info("GIS: lookup failed (%s)", exc)
        return None


async def gis_available() -> bool:
    return await _get_pool() is not None
