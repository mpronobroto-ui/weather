"""Air-quality data — Indian National AQI (CPCB) computed from Open-Meteo pollutant data.

Open-Meteo's Air Quality API only ships pre-computed US and European AQI —
there is no "indian_aqi" field. So instead we pull the raw pollutant
concentrations (PM2.5, PM10, NO2, SO2, CO, O3) and run them through the
Central Pollution Control Board's official "National Air Quality Index"
breakpoint tables ourselves, exactly as CPCB / SAFAR / most Indian AQI apps
do:

  1. Convert each pollutant's concentration into a 0-500 sub-index by
     linear interpolation within its CPCB breakpoint bucket.
  2. The overall AQI is the WORST (maximum) of the available sub-indices —
     CPCB's "One Number, One Colour, One Description" rule.
  3. The pollutant that produced that maximum is reported as the
     "dominant pollutant", same as apps like SAFAR-India / AQI.in do.

Reference: CPCB National Air Quality Index (2014), https://cpcb.nic.in
"""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger("weathergpt")

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# ---------------------------------------------------------------------------
# CPCB breakpoint tables: (conc_lo, conc_hi, aqi_lo, aqi_hi)
# Concentration units: PM2.5/PM10/NO2/SO2/O3 in µg/m³, CO in mg/m³.
# Averaging periods (CPCB spec): PM2.5/PM10/NO2/SO2 = 24-hr, O3/CO = 8-hr.
# Open-Meteo gives current-hour model values, so these are a live/indicative
# approximation of the official 24-hr / 8-hr rolling-average AQI, not a
# certified CPCB reading — the same caveat that applies to any live AQI app.
# ---------------------------------------------------------------------------
_BREAKPOINTS: dict[str, list[tuple[float, float, float, float]]] = {
    "pm2_5": [
        (0, 30, 0, 50),
        (30, 60, 50, 100),
        (60, 90, 100, 200),
        (90, 120, 200, 300),
        (120, 250, 300, 400),
        (250, 380, 400, 500),
    ],
    "pm10": [
        (0, 50, 0, 50),
        (50, 100, 50, 100),
        (100, 250, 100, 200),
        (250, 350, 200, 300),
        (350, 430, 300, 400),
        (430, 510, 400, 500),
    ],
    "nitrogen_dioxide": [
        (0, 40, 0, 50),
        (40, 80, 50, 100),
        (80, 180, 100, 200),
        (180, 280, 200, 300),
        (280, 400, 300, 400),
        (400, 500, 400, 500),
    ],
    "sulphur_dioxide": [
        (0, 40, 0, 50),
        (40, 80, 50, 100),
        (80, 380, 100, 200),
        (380, 800, 200, 300),
        (800, 1600, 300, 400),
        (1600, 2100, 400, 500),
    ],
    "ozone": [
        (0, 50, 0, 50),
        (50, 100, 50, 100),
        (100, 168, 100, 200),
        (168, 208, 200, 300),
        (208, 748, 300, 400),
        (748, 938, 400, 500),
    ],
    # CO breakpoints are defined in mg/m³ by CPCB; Open-Meteo reports CO in
    # µg/m³, so the raw value is divided by 1000 before lookup (see below).
    "carbon_monoxide": [
        (0, 1.0, 0, 50),
        (1.0, 2.0, 50, 100),
        (2.0, 10.0, 100, 200),
        (10.0, 17.0, 200, 300),
        (17.0, 34.0, 300, 400),
        (34.0, 50.0, 400, 500),
    ],
}

_POLLUTANT_LABEL = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide": "SO2",
    "ozone": "O3",
    "carbon_monoxide": "CO",
}


def _sub_index(pollutant: str, conc: float | None) -> float | None:
    """Linear-interpolate one pollutant's concentration into a 0-500 CPCB sub-index."""
    if conc is None or conc < 0:
        return None

    table = _BREAKPOINTS[pollutant]
    conc_for_lookup = conc / 1000.0 if pollutant == "carbon_monoxide" else conc

    for lo, hi, aqi_lo, aqi_hi in table:
        if lo <= conc_for_lookup <= hi:
            if hi == lo:
                return aqi_lo
            return round(((aqi_hi - aqi_lo) / (hi - lo)) * (conc_for_lookup - lo) + aqi_lo, 1)

    # Above the top bucket: extrapolate using the last segment's slope so an
    # extreme pollution spike still returns a (>500) number instead of None.
    lo, hi, aqi_lo, aqi_hi = table[-1]
    if conc_for_lookup > hi:
        return round(((aqi_hi - aqi_lo) / (hi - lo)) * (conc_for_lookup - lo) + aqi_lo, 1)
    return None


def _category(aqi: float | None) -> str:
    """CPCB's official six-band category names."""
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def _health_note(category: str) -> str:
    return {
        "Good": "Minimal impact.",
        "Satisfactory": "Minor breathing discomfort to sensitive people.",
        "Moderate": "Breathing discomfort to people with lung, asthma and heart disease, children and older adults.",
        "Poor": "Breathing discomfort to most people on prolonged exposure.",
        "Very Poor": "Respiratory illness on prolonged exposure; discomfort even on light activity.",
        "Severe": "Serious risk for everyone — affects even healthy people; avoid outdoor activity.",
        "Unknown": "",
    }.get(category, "")


def compute_cpcb_aqi(pollutants: dict[str, float | None]) -> dict:
    """Given raw concentrations, return the CPCB overall AQI + dominant pollutant."""
    sub_indices: dict[str, float] = {}
    for pollutant in _BREAKPOINTS:
        idx = _sub_index(pollutant, pollutants.get(pollutant))
        if idx is not None:
            sub_indices[pollutant] = idx

    if not sub_indices:
        return {"aqi": None, "category": "Unknown", "dominant_pollutant": None, "sub_indices": {}}

    dominant = max(sub_indices, key=sub_indices.get)
    overall = sub_indices[dominant]
    return {
        "aqi": round(overall),
        "category": _category(overall),
        "dominant_pollutant": _POLLUTANT_LABEL.get(dominant, dominant),
        "sub_indices": {
            _POLLUTANT_LABEL.get(k, k): round(v) for k, v in sub_indices.items()
        },
        "sufficient_data": len(sub_indices) >= 3,
    }


# CPCB's official averaging window per pollutant — this is the #1 reason a
# live "instant" AQI reading disagrees with apps (Google, SAFAR, AQI.in)
# that report a rolling average instead of the current-hour concentration:
# a single dusty/calm hour can spike the instant PM2.5 reading well above
# what a 24-hour average would show, and vice versa.
_AVERAGING_HOURS = {
    "pm2_5": 24,
    "pm10": 24,
    "nitrogen_dioxide": 24,
    "sulphur_dioxide": 24,
    "ozone": 8,
    "carbon_monoxide": 8,
}

_HOURLY_VARS = ",".join(_AVERAGING_HOURS.keys())


def _rolling_mean(series: list[float | None], hours: int) -> float | None:
    """Mean of the most recent `hours` non-null hourly values."""
    recent = [v for v in series[-hours:] if v is not None]
    if not recent:
        return None
    return sum(recent) / len(recent)


async def _get(url: str, params: dict, max_retries: int = 2) -> dict:
    """GET with retries/backoff + explicit 429 handling and logging.

    Mirrors weather.py's `_get` helper. Without this, a single transient
    timeout or rate-limit response from Open-Meteo (very common on shared
    hosting IPs like Render's free tier) permanently fails the request with
    no server-side trace of why — which is exactly what was happening here
    before this fix.
    """
    last_err = "Network execution timeout."
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    logger.warning("Air Quality API rate-limited (429) on attempt %d", attempt + 1)
                    if attempt < max_retries:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return {"error": True, "reason": "Air quality provider is temporarily rate-limited. Please retry shortly."}
                logger.warning("Air Quality API responded with status: %d", response.status_code)
                last_err = f"Upstream status {response.status_code}"
        except Exception as exc:
            logger.warning("Air Quality API request failed (attempt %d/%d): %s", attempt + 1, max_retries + 1, exc)
            last_err = str(exc) or "Network timeout connecting to air quality provider."
            if attempt < max_retries:
                await asyncio.sleep(0.8)

    return {"error": True, "reason": last_err}


async def get_air_quality(lat: float, lon: float) -> dict:
    """Computes the CPCB National AQI using the official rolling-average
    window per pollutant (24-hr for PM/NO2/SO2, 8-hr for O3/CO) instead of
    a single instantaneous reading — this is what brings the number in
    line with how Google/SAFAR/AQI.in report AQI, since they all average
    over the same CPCB-defined windows rather than showing one raw sample.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
        "hourly": _HOURLY_VARS,
        "past_hours": 24,
        "forecast_hours": 1,
        "timezone": "auto",
    }
    try:
        raw = await _get(AIR_QUALITY_URL, params)
        if raw.get("error"):
            logger.warning("Air quality lookup failed for (%s, %s): %s", lat, lon, raw.get("reason"))
            return {"error": True, "reason": raw.get("reason"), "data_source": "Open-Meteo Air Quality", "standard": "India CPCB National AQI"}
        cur = raw.get("current") or {}
        hourly = raw.get("hourly") or {}

        # Prefer the CPCB-correct rolling average; fall back to the
        # instantaneous "current" value for any pollutant where hourly
        # history isn't available (e.g. a very new/edge-of-coverage point).
        pollutants: dict[str, float | None] = {}
        instant: dict[str, float | None] = {}
        for pollutant, hours in _AVERAGING_HOURS.items():
            instant_val = cur.get(pollutant)
            instant[pollutant] = instant_val
            series = hourly.get(pollutant) or []
            avg = _rolling_mean(series, hours)
            pollutants[pollutant] = avg if avg is not None else instant_val

        cpcb = compute_cpcb_aqi(pollutants)
        # Same computation on the instantaneous values, purely so the
        # response can show how much the averaging changed the number —
        # transparency instead of silently picking one and hoping it matches.
        cpcb_instant = compute_cpcb_aqi(instant)

        return {
            "aqi": cpcb["aqi"],
            "category": cpcb["category"],
            "dominant_pollutant": cpcb["dominant_pollutant"],
            "sub_indices": cpcb["sub_indices"],
            "sufficient_data": cpcb.get("sufficient_data", False),
            "health_note": _health_note(cpcb["category"]),
            "pm2_5": pollutants.get("pm2_5"),
            "pm10": pollutants.get("pm10"),
            "carbon_monoxide": pollutants.get("carbon_monoxide"),
            "nitrogen_dioxide": pollutants.get("nitrogen_dioxide"),
            "sulphur_dioxide": pollutants.get("sulphur_dioxide"),
            "ozone": pollutants.get("ozone"),
            "instant_aqi": cpcb_instant["aqi"],
            "averaging_note": (
                "PM2.5/PM10/NO2/SO2 use a 24-hour rolling average and O3/CO an "
                "8-hour rolling average, per CPCB's official method — the same "
                "windows used by Google, SAFAR-India, and AQI.in. The single-hour "
                "instant reading is included separately for comparison."
            ),
            "time": cur.get("time"),
            "standard": "India CPCB National AQI",
            "data_source": (
                "Open-Meteo Air Quality (CAMS-based model data), 24h/8h rolling "
                "averages scored to CPCB National AQI breakpoints"
            ),
        }
    except Exception as exc:
        logger.exception("Unexpected error computing AQI for (%s, %s)", lat, lon)
        return {"error": True, "reason": str(exc), "data_source": "Open-Meteo Air Quality", "standard": "India CPCB National AQI"}
