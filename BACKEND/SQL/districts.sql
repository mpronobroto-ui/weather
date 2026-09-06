-- WeatherGPT district GIS layer (PostgreSQL 13+ with the PostGIS extension).
--
-- First create the database (skip if it already exists):
--   createdb weathergpt
--
-- Then run this file:
--   psql -U postgres -d weathergpt -f districts.sql
-- or, with the bundled docker-compose Postgres service:
--   docker compose exec -T postgres psql -U postgres -d weathergpt -f /docker-entrypoint-initdb.d/districts.sql
--
-- NOTE ON THE SAMPLE DATA: the polygons below are simplified rectangular
-- bounding boxes for a handful of Indian districts, good enough to prove out
-- real point-in-polygon lookups end to end. For production, replace this
-- table's contents with actual Survey of India / OSM administrative
-- boundaries — e.g. loaded straight into PostGIS with `ogr2ogr` from a
-- shapefile/GeoJSON, or via QGIS's "Export to PostGIS" tool.
--
-- NOTE ON COORDINATES: the geometry column is declared with SRID 4326
-- (standard WGS84 lat/lon), and PostGIS's GEOMETRY type — unlike MySQL 8 —
-- does NOT silently swap axis order on you. Points are constructed with
-- ST_MakePoint(lon, lat), the same (longitude, latitude) convention used
-- everywhere else in this app (GeoJSON, app/gis.py, etc.), so there's no
-- axis-order footgun to work around.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS districts (
    id SERIAL PRIMARY KEY,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    geom GEOMETRY(POLYGON, 4326) NOT NULL
);

-- GiST index is what makes ST_Contains lookups fast at scale — the spatial
-- equivalent of a B-tree index, essential once real district boundaries
-- (thousands of vertices each) replace these sample bounding boxes.
CREATE INDEX IF NOT EXISTS districts_geom_idx ON districts USING GIST (geom);

TRUNCATE TABLE districts RESTART IDENTITY;

INSERT INTO districts (state, district, geom) VALUES
('West Bengal', 'North 24 Parganas',
 ST_SetSRID(ST_GeomFromText('POLYGON((88.30 22.40, 89.05 22.40, 89.05 23.00, 88.30 23.00, 88.30 22.40))'), 4326)),
('West Bengal', 'Kolkata',
 ST_SetSRID(ST_GeomFromText('POLYGON((88.25 22.45, 88.45 22.45, 88.45 22.63, 88.25 22.63, 88.25 22.45))'), 4326)),
('West Bengal', 'Purba Bardhaman',
 ST_SetSRID(ST_GeomFromText('POLYGON((87.60 23.00, 88.30 23.00, 88.30 23.60, 87.60 23.60, 87.60 23.00))'), 4326)),
('Maharashtra', 'Mumbai City',
 ST_SetSRID(ST_GeomFromText('POLYGON((72.78 18.89, 72.98 18.89, 72.98 19.08, 72.78 19.08, 72.78 18.89))'), 4326)),
('Tamil Nadu', 'Chennai',
 ST_SetSRID(ST_GeomFromText('POLYGON((80.15 12.90, 80.35 12.90, 80.35 13.25, 80.15 13.25, 80.15 12.90))'), 4326)),
('Karnataka', 'Bengaluru Urban',
 ST_SetSRID(ST_GeomFromText('POLYGON((77.35 12.75, 77.75 12.75, 77.75 13.15, 77.35 13.15, 77.35 12.75))'), 4326)),
('Delhi', 'New Delhi',
 ST_SetSRID(ST_GeomFromText('POLYGON((77.05 28.45, 77.35 28.45, 77.35 28.75, 77.05 28.75, 77.05 28.45))'), 4326));
