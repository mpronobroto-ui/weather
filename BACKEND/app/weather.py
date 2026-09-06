"""
WeatherGPT Backend — Weather Core Module

Single seam to the NWP model provider. Uses Open-Meteo's free forecast +
archive APIs (no API key required) so the whole app runs out of the box.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Dict, List
import httpx

logger = logging.getLogger("weathergpt")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

# ---------------------------------------------------------------------------
# NWP model integration (GFS / WRF-class regional models / ICON / ECMWF / …)
#
# Open-Meteo is a broker in front of the real numerical weather prediction
# models run by national met agencies — it does not run its own physics.
# Passing an explicit `models` slug pins the request to one (or several)
# named NWP models instead of Open-Meteo's auto-blended "best_match".
# WRF itself isn't distributed as a public global feed, so the closest
# operational equivalents are the convection-permitting regional models
# below (AROME / HRRR), which are also WRF-family or WRF-like high-resolution
# mesoscale models.
# ---------------------------------------------------------------------------
NWP_MODELS: Dict[str, str] = {
    "gfs": "gfs_seamless",                 # NOAA GFS (global)
    "gfs_hrrr": "gfs_hrrr",                 # NOAA HRRR — WRF-ARW based, convection-permitting (CONUS)
    "icon": "icon_seamless",                # DWD ICON (global)
    "ecmwf": "ecmwf_ifs04",                 # ECMWF IFS (global)
    "ukmo": "ukmo_seamless",                # UK Met Office
    "gem": "gem_seamless",                  # Environment Canada
    "jma": "jma_seamless",                  # Japan Meteorological Agency
    "meteofrance_arome": "meteofrance_arome_france", # Meteo-France AROME — WRF-class mesoscale regional model
    "best_match": "best_match",             # Open-Meteo's own auto-blend (default when no model given)
}

DEFAULT_MULTI_MODEL_SET = ["gfs", "icon", "ecmwf"]


def resolve_model_slug(model: str) -> str:
    """Map a friendly NWP model key (e.g. 'gfs', 'meteofrance_arome') to the
    slug Open-Meteo's `models` query param expects. Unknown keys are passed
    through unchanged so any Open-Meteo-supported slug still works directly."""
    return NWP_MODELS.get(model.lower().strip(), model)

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "windspeed_10m_max",
    "windgusts_10m_max",
    "winddirection_10m_dominant",
    "uv_index_max",
    "relative_humidity_2m_max",
    "weathercode",
]

# WMO weather codes -> short human label (used by composer.py for replies)
_WEATHER_CODE_LABELS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def weather_code_label(code: Any) -> str:
    """Map a WMO weather code to a short human-readable label."""
    try:
        return _WEATHER_CODE_LABELS.get(int(code), "changeable conditions")
    except (TypeError, ValueError):
        return "changeable conditions"


async def _get(url: str, params: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    last_err = "Network execution timeout."
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    logger.warning("Weather API rate-limited (429) on attempt %d", attempt + 1)
                    if attempt < max_retries:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return {"error": True, "reason": "Weather models are temporarily rate-limited. Please retry shortly.", "daily": {}}
                logger.warning("Weather API responded with status: %d", response.status_code)
                last_err = f"Upstream status {response.status_code}"
        except Exception as exc:
            logger.warning("Weather API request failed (attempt %d/%d): %s", attempt + 1, max_retries + 1, exc)
            last_err = str(exc) or "Network timeout connecting to weather provider."
            if attempt < max_retries:
                await asyncio.sleep(0.8)

    return {"error": True, "reason": last_err, "daily": {}}


async def get_forecast(lat: float, lon: float, days: int = 7, model: str | None = None) -> Dict[str, Any]:
    """Fetches real-time NWP forecast + current conditions for a location.

    By default Open-Meteo's "best_match" blend is used. Pass `model` (e.g.
    "gfs", "icon", "ecmwf", "gfs_hrrr", "meteofrance_arome") to pin the
    request to one specific NWP model provider instead — see NWP_MODELS.
    """
    params: Dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "hourly": "precipitation_probability,visibility,windspeed_10m,uv_index",
        "current_weather": "true",
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
            "weather_code,wind_speed_10m,surface_pressure,cloud_cover"
        ),
        "timezone": "auto",
        "forecast_days": max(1, min(days, 16)),
    }
    if model:
        params["models"] = resolve_model_slug(model)

    data = await _get(FORECAST_URL, params)
    if data.get("error"):
        # Attempt fallback with simplified params if full request failed
        simple_params: Dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max,weathercode",
            "current_weather": "true",
            "timezone": "auto",
            "forecast_days": max(1, min(days, 7)),
        }
        if model:
            simple_params["models"] = resolve_model_slug(model)
        fallback_data = await _get(FORECAST_URL, simple_params, max_retries=1)
        if not fallback_data.get("error") and fallback_data.get("daily"):
            data = fallback_data
        else:
            return data

    daily = data.get("daily") or {}
    current_raw = data.get("current") or {}
    current_w = data.get("current_weather") or {}

    # Extract best available current temperature, wind, and weathercode
    temp = current_raw.get("temperature_2m") if "temperature_2m" in current_raw else current_w.get("temperature")
    if temp is None and daily.get("temperature_2m_max"):
        temp = daily["temperature_2m_max"][0]

    wind = current_raw.get("wind_speed_10m") if "wind_speed_10m" in current_raw else current_w.get("windspeed")
    if wind is None and daily.get("windspeed_10m_max"):
        wind = daily["windspeed_10m_max"][0]

    code = current_raw.get("weather_code") if "weather_code" in current_raw else current_w.get("weathercode")
    if code is None and daily.get("weathercode"):
        code = daily["weathercode"][0]

    # Visibility and UV index aren't available in Open-Meteo's "current"
    # block (only "hourly"), so pull the value for whichever hourly slot
    # matches the current reported time — the same trick apps like Google
    # Weather use to present an hourly-resolution field as "right now".
    hourly = data.get("hourly") or {}
    now_time = current_raw.get("time") or current_w.get("time")
    visibility_now = None
    uv_index_now = None
    hourly_times = hourly.get("time") or []
    if now_time and now_time in hourly_times:
        h_idx = hourly_times.index(now_time)
        vis_series = hourly.get("visibility") or []
        uv_series = hourly.get("uv_index") or []
        if h_idx < len(vis_series):
            visibility_now = vis_series[h_idx]
        if h_idx < len(uv_series):
            uv_index_now = uv_series[h_idx]
    elif hourly_times:
        # No exact match (e.g. simplified fallback request) — use the first
        # available hourly slot as a same-day approximation.
        vis_series = hourly.get("visibility") or []
        uv_series = hourly.get("uv_index") or []
        visibility_now = vis_series[0] if vis_series else None
        uv_index_now = uv_series[0] if uv_series else None

    normalized_current = {
        "temperature": temp,
        "temperature_2m": temp,
        "windspeed": wind,
        "wind_speed_10m": wind,
        "weathercode": code,
        "weather_code": code,
        "relative_humidity": current_raw.get("relative_humidity_2m"),
        "pressure_msl": current_raw.get("surface_pressure"),
        "surface_pressure": current_raw.get("surface_pressure"),
        "cloud_cover": current_raw.get("cloud_cover"),
        "visibility_m": visibility_now,
        "visibility_km": round(visibility_now / 1000, 1) if visibility_now is not None else None,
        "uv_index": uv_index_now,
        "uv_index_max_today": (daily.get("uv_index_max") or [None])[0],
        "time": now_time,
    }

    return {
        "daily": daily,
        "hourly": data.get("hourly", {}),
        "current_weather": normalized_current,
        "model_used": resolve_model_slug(model) if model else "best_match",
    }



async def get_historical_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """Fetch observed/reanalysis weather for a concrete past date range.

    Open-Meteo's archive endpoint provides historical/reanalysis values rather
    than a forecast. The returned daily series is intentionally shaped like
    the forecast payload so the same frontend can render both.
    """
    params: Dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_hours",
            "windspeed_10m_max",
            "windgusts_10m_max",
            "winddirection_10m_dominant",
            "relative_humidity_2m_max",
            "relative_humidity_2m_min",
            "weathercode",
        ]),
        "hourly": ",".join([
            "temperature_2m",
            "precipitation",
            "relative_humidity_2m",
            "windspeed_10m",
            "windgusts_10m",
            "weathercode",
            "visibility",
        ]),
        "timezone": "auto",
    }

    data = await _get(ARCHIVE_URL, params)

    # The archive/reanalysis feed can lag by a few days. For very recent
    # requests (especially "yesterday"), use Open-Meteo's forecast endpoint's
    # past_days window as a fallback instead of incorrectly showing a forecast.
    daily = data.get("daily") if not data.get("error") else None
    if not daily or not daily.get("time"):
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            today = date.today()
            age_days = (today - start).days
            if 1 <= age_days <= 7:
                recent_params = {
                    "latitude": lat,
                    "longitude": lon,
                    "daily": ",".join([
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "precipitation_hours",
                        "windspeed_10m_max",
                        "windgusts_10m_max",
                        "winddirection_10m_dominant",
                        "relative_humidity_2m_max",
                        "relative_humidity_2m_min",
                        "weathercode",
                    ]),
                    "hourly": ",".join([
                        "temperature_2m",
                        "precipitation",
                        "relative_humidity_2m",
                        "windspeed_10m",
                        "windgusts_10m",
                        "weathercode",
                        "visibility",
                    ]),
                    "timezone": "auto",
                    "past_days": min(age_days, 7),
                    "forecast_days": 1,
                }
                recent = await _get(FORECAST_URL, recent_params, max_retries=1)
                recent_daily = recent.get("daily") if not recent.get("error") else None
                if recent_daily and recent_daily.get("time"):
                    keep = [
                        idx for idx, value in enumerate(recent_daily.get("time", []))
                        if start_date <= value <= end_date
                    ]
                    if keep:
                        def select_series(block: Dict[str, Any]) -> Dict[str, Any]:
                            out = {}
                            for key, values in block.items():
                                if isinstance(values, list):
                                    out[key] = [values[i] for i in keep if i < len(values)]
                                else:
                                    out[key] = values
                            return out

                        recent_hourly = recent.get("hourly") or {}
                        # Hourly timestamps can be filtered directly by date.
                        hourly_keep = [
                            idx for idx, value in enumerate(recent_hourly.get("time", []))
                            if start_date <= value[:10] <= end_date
                        ]
                        def select_hourly(block: Dict[str, Any]) -> Dict[str, Any]:
                            out = {}
                            for key, values in block.items():
                                if isinstance(values, list):
                                    out[key] = [values[i] for i in hourly_keep if i < len(values)]
                                else:
                                    out[key] = values
                            return out

                        return {
                            "daily": select_series(recent_daily),
                            "hourly": select_hourly(recent_hourly),
                            "timezone": recent.get("timezone"),
                            "latitude": recent.get("latitude", lat),
                            "longitude": recent.get("longitude", lon),
                            "data_source": "Open-Meteo recent past-days data (model/observational blend)",
                        }
        except Exception as exc:
            logger.info("Recent past-days fallback failed: %s", exc)

    if not daily or not daily.get("time"):
        return {
            "error": True,
            "reason": "No historical weather data is available for the requested dates.",
            "daily": {},
        }

    return {
        "daily": daily,
        "hourly": data.get("hourly", {}),
        "timezone": data.get("timezone"),
        "latitude": data.get("latitude", lat),
        "longitude": data.get("longitude", lon),
        "data_source": "Open-Meteo Historical Weather API (archive/reanalysis)",
    }


async def get_multi_model_forecast(
    lat: float,
    lon: float,
    days: int = 5,
    models: List[str] | None = None,
) -> Dict[str, Any]:
    """Queries several named NWP models (e.g. GFS, ICON, ECMWF, WRF-class
    AROME/HRRR) side by side for the same location so callers can compare
    forecasts across providers instead of relying on a single blended model.

    Open-Meteo returns one daily/hourly series per requested model, with
    each variable name suffixed by the model slug (e.g.
    "temperature_2m_max_gfs_seamless"). This unpacks those into a
    per-model dict plus a simple max vs min spread per day, which is a
    cheap proxy for forecast uncertainty/model agreement.
    """
    model_keys = models or DEFAULT_MULTI_MODEL_SET
    slugs = [resolve_model_slug(m) for m in model_keys]

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max,weathercode",
        "models": ",".join(slugs),
        "timezone": "auto",
        "forecast_days": max(1, min(days, 16)),
    }
    data = await _get(params=params, url=FORECAST_URL)
    if data.get("error"):
        return {"error": True, "reason": data.get("reason"), "models": {}}

    daily = data.get("daily") or {}
    dates = daily.get("time", [])

    per_model: Dict[str, Dict[str, Any]] = {}
    for key, slug in zip(model_keys, slugs):
        per_model[key] = {
            "model_slug": slug,
            "time": dates,
            "temperature_2m_max": daily.get(f"temperature_2m_max_{slug}"),
            "temperature_2m_min": daily.get(f"temperature_2m_min_{slug}"),
            "precipitation_sum": daily.get(f"precipitation_sum_{slug}"),
            "precipitation_probability_max": daily.get(f"precipitation_probability_max_{slug}"),
            "windspeed_10m_max": daily.get(f"windspeed_10m_max_{slug}"),
            "weathercode": daily.get(f"weathercode_{slug}"),
        }

    # Per-day agreement: spread between the highest and lowest max-temp
    # forecast across all requested models — larger spread = less agreement.
    spread_per_day: List[Dict[str, Any]] = []
    for i, day in enumerate(dates):
        values = [
            per_model[k]["temperature_2m_max"][i]
            for k in model_keys
            if per_model[k]["temperature_2m_max"] and i < len(per_model[k]["temperature_2m_max"])
            and per_model[k]["temperature_2m_max"][i] is not None
        ]
        spread_per_day.append({
            "date": day,
            "min_forecast_max_temp": round(min(values), 1) if values else None,
            "max_forecast_max_temp": round(max(values), 1) if values else None,
            "spread_c": round(max(values) - min(values), 1) if len(values) > 1 else 0.0,
        })

    return {
        "models": per_model,
        "model_agreement": spread_per_day,
    }


async def get_historical_summary(lat: float, lon: float, years_back: int = 10) -> List[Dict[str, Any]]:
    """Retrieves historical weather metrics to chart multi-year climatological trends.

    Fetches all requested years CONCURRENTLY (asyncio.gather) instead of one
    HTTP round-trip after another — with `_get`'s own 12s timeout x up to 3
    attempts per year, a sequential fetch of 10 years could previously take
    well over a minute in the worst case, which made the climate chart feel
    like it was "not showing" when it was really just still loading (or the
    caller/browser had already given up waiting). Concurrent fetches turn
    that into roughly one request's worth of wall-clock time.
    """
    today = date.today()

    async def _fetch_year(target_year: int) -> Dict[str, Any] | None:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": f"{target_year}-01-01",
            "end_date": f"{target_year}-12-31",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        }
        data = await _get(ARCHIVE_URL, params)
        daily = data.get("daily") if not data.get("error") else None
        if daily:
            return {"year": target_year, "data": daily}
        return None

    target_years = [today.year - i for i in range(1, years_back + 1)]
    results = await asyncio.gather(*(_fetch_year(y) for y in target_years), return_exceptions=True)

    historical_datasets: List[Dict[str, Any]] = []
    for year, result in zip(target_years, results):
        if isinstance(result, Exception):
            logger.info("Historical fetch for %s failed: %s", year, result)
            continue
        if result:
            historical_datasets.append(result)

    return historical_datasets


async def get_marine_forecast(lat: float, lon: float, days: int = 3) -> Dict[str, Any]:
    """Real ocean swell/wave data from Open-Meteo's free Marine Weather API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "wave_height_max,wind_wave_height_max,swell_wave_height_max",
        "timezone": "auto",
        "forecast_days": max(1, min(days, 8)),
    }
    return await _get(MARINE_URL, params)


async def get_energy_forecast(lat: float, lon: float, days: int = 2) -> Dict[str, Any]:
    """Real hourly solar-irradiance and 80m wind-speed series for a simple renewable-energy outlook."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "shortwave_radiation,direct_radiation,windspeed_80m,precipitation,precipitation_probability",
        "timezone": "auto",
        "forecast_days": max(1, min(days, 3)),
    }
    return await _get(FORECAST_URL, params)


def _linear_slope(xs: List[float], ys: List[float]) -> float | None:
    """Ordinary least-squares slope of ys against xs (simple linear
    regression, no external stats library needed for a per-decade trend
    line)."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return None
    return num / den


def explain_climate_trend(trend: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turns the per-year summary rows into a plain-language explanation:
    warming/cooling rate per decade and rainfall change, using a simple
    linear regression over the available years — enough to say something
    concrete ("warming at ~0.3°C/decade") without pretending to be a full
    climate-attribution study.
    """
    years = [r["year"] for r in trend if r.get("avg_max_temp_c") is not None]
    temps = [r["avg_max_temp_c"] for r in trend if r.get("avg_max_temp_c") is not None]
    rain_years = [r["year"] for r in trend if r.get("total_rainfall_mm") is not None]
    rains = [r["total_rainfall_mm"] for r in trend if r.get("total_rainfall_mm") is not None]

    temp_slope = _linear_slope(years, temps)
    rain_slope = _linear_slope(rain_years, rains)

    lines = []
    if temp_slope is not None:
        per_decade = round(temp_slope * 10, 2)
        direction = "warming" if per_decade > 0 else ("cooling" if per_decade < 0 else "flat")
        lines.append(
            f"Average daily-high temperature trend: {direction} at roughly "
            f"{abs(per_decade)}°C per decade over the available years."
        )
    if rain_slope is not None:
        per_decade_mm = round(rain_slope * 10, 1)
        direction = "increasing" if per_decade_mm > 0 else ("decreasing" if per_decade_mm < 0 else "flat")
        lines.append(
            f"Total annual rainfall trend: {direction} at roughly "
            f"{abs(per_decade_mm)} mm per decade over the available years."
        )
    lines.append(
        "This is a simple linear trend over the fetched years, not a full "
        "climate-attribution model — useful to see direction and rough "
        "magnitude, not a certified climatology figure."
    )

    return {
        "temp_trend_c_per_decade": round(temp_slope * 10, 2) if temp_slope is not None else None,
        "rainfall_trend_mm_per_decade": round(rain_slope * 10, 1) if rain_slope is not None else None,
        "explanation": " ".join(lines),
        "chart": {
            "years": [r["year"] for r in trend],
            "avg_max_temp_c": [r.get("avg_max_temp_c") for r in trend],
            "total_rainfall_mm": [r.get("total_rainfall_mm") for r in trend],
        },
    }


def summarize_yearly_trend(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reduces each year's raw daily archive into one summary row per year."""
    trend: List[Dict[str, Any]] = []
    for entry in sorted(datasets, key=lambda e: e["year"]):
        temps = entry["data"].get("temperature_2m_max", []) or []
        precip = entry["data"].get("precipitation_sum", []) or []
        temps = [t for t in temps if t is not None]
        precip = [p for p in precip if p is not None]
        trend.append({
            "year": entry["year"],
            "avg_max_temp_c": round(sum(temps) / len(temps), 2) if temps else None,
            "total_rainfall_mm": round(sum(precip), 2) if precip else None,
        })
    return trend
