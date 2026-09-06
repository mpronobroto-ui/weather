"""
Chat orchestration layer — the actual "conversational engine" of WeatherGPT.

Pipeline for every message:
  1. Rule-based NLU parse (instant, offline).
  2. Optional LLM refinement of intent/location (if a key is configured).
  3. Resolve location -> lat/lon (geocoding, or client-supplied GPS coords).
  4. Pull forecast / alerts / historical data for that location.
  5. Build a factual summary + structured payload for the frontend.
  6. Optionally ask the LLM to phrase it naturally in the target language;
     otherwise use the pre-translated template.
"""
from __future__ import annotations

import asyncio
from typing import Any

from . import (
    advisory,
    air_quality,
    alerts as alerts_mod,
    geocode,
    gis,
    google_search,
    i18n,
    llm,
    nlu,
    satellite,
    weather,
    wis2,
)


async def _general_fallback(text: str, lang_name: str) -> dict[str, Any] | None:
    """Try the LLM first (with Google Custom Search grounding baked in inside
    llm.general_weather_answer); if no LLM key is configured at all, fall
    back to answering straight from Google Custom Search snippets so the
    app still gives a real, sourced answer instead of a dead end.
    Returns {"reply": str, "sources": list | None} or None.
    """
    general = await llm.general_weather_answer(text, lang_name)
    if general:
        return {"reply": general, "sources": None}
    if google_search.search_available():
        found = await google_search.answer_from_search(text, lang_name)
        if found:
            return {"reply": found["text"], "sources": found["sources"]}
    return None


def _uv_category(uv: float | None) -> str | None:
    """WHO UV Index exposure categories."""
    if uv is None:
        return None
    if uv < 3:
        return "Low"
    if uv < 6:
        return "Moderate"
    if uv < 8:
        return "High"
    if uv < 11:
        return "Very High"
    return "Extreme"


async def _fast_reply(fallback_text: str, lang: str, user_question: str = "") -> str:
    """Prefer instant template replies for English; only call LLM for other languages or when needed."""
    if lang == "en" or not llm.llm_available():
        return fallback_text
    return await llm.phrase_reply(
        fallback_text,
        i18n.SUPPORTED.get(lang, {}).get("name", lang),
        fallback_text,
        user_question=user_question,
    )


# Human-readable basin names, used to group a mixed-basin answer (e.g.
# "Pacific" legitimately spans Western/Eastern/Central Pacific — thousands
# of miles apart) into clearly-labelled sub-sections instead of one flat,
# confusing list.
_BASIN_NAMES = {
    "wp": "Western Pacific (Philippine Sea / South China Sea)",
    "ep": "Eastern Pacific (Mexico / Central America)",
    "cp": "Central Pacific (Hawaii)",
    "al": "Atlantic / Caribbean / Gulf",
    "io": "North Indian Ocean",
    "ni": "North Indian Ocean",
    "bb": "Bay of Bengal",
    "as": "Arabian Sea",
    "sh": "Southern Hemisphere",
    "au": "Australian region",
}


def _basin_label(basin: str | None) -> str:
    return _BASIN_NAMES.get((basin or "").lower(), (basin or "Unclassified").upper())


# Severity ranking used to turn a list of active storms into one overall
# alert level for the reply, instead of always showing "green" regardless
# of whether a super typhoon is active.
def _cyclone_rank(category: str | None) -> int:
    c = (category or "").lower()
    if "super" in c or "extremely severe" in c:
        return 4
    if "very severe" in c or "major" in c:
        return 3
    if "severe" in c or "hurricane" in c or "typhoon" in c:
        return 2
    if "storm" in c:
        return 1
    return 0


_RANK_LEVEL = {0: "green", 1: "yellow", 2: "orange", 3: "red", 4: "red"}
_RANK_LABEL = {
    0: "TRACKING",
    1: "WATCH",
    2: "WARNING",
    3: "SEVERE WARNING",
    4: "SEVERE WARNING",
}


def _cyclone_alert(cyclones: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    """Return (alert dict for the UI pill, alert_label text) from a storm list."""
    if not cyclones:
        return {"level": "green", "hazards": []}, "NO ACTIVE CYCLONE"
    max_rank = max(_cyclone_rank(c.get("category")) for c in cyclones)
    hazards = [f"{c.get('name') or 'Unnamed'} — {c.get('category') or 'tropical system'}" for c in cyclones[:5]]
    label = f"{_RANK_LABEL[max_rank]} · {len(cyclones)} ACTIVE"
    return {"level": _RANK_LEVEL[max_rank], "hazards": hazards}, label


def _cyclone_map_payload(
    cyclones: list[dict[str, Any]] | None, region: str | None = None
) -> dict[str, Any] | None:
    for c in cyclones or []:
        if c.get("latest_lat") is not None and c.get("latest_lon") is not None:
            return {
                "lat": c["latest_lat"],
                "lon": c["latest_lon"],
                "label": c.get("name") or region or "storm",
                "zoom": 5,
            }
    return None


async def handle_message(
    text: str,
    lang: str = "en",
    client_lat: float | None = None,
    client_lon: float | None = None,
) -> dict[str, Any]:
    lang = lang if lang in i18n.SUPPORTED else "en"
    parsed = nlu.parse_query(text)

    # If the user explicitly asked for "my location" / "near me" / etc., the
    # rule-based parser has already (correctly) left location_text empty so
    # the GPS fallback below is used. Remember that here so the LLM refine
    # step (which doesn't know this rule) can never overwrite it with an
    # invented place name.
    wants_device_location = nlu.mentions_device_location(text)

    # Fast path: trust rule NLU when it found a clear intent + location (skip slow LLM refine)
    use_llm_refine = llm.llm_available() and parsed.intent != "historical" and (
        parsed.intent in ("current", "greeting") or not parsed.location_text
    )
    if use_llm_refine:
        refined = await llm.refine_query_understanding(
            text,
            {
                "intent": parsed.intent,
                "location": parsed.location_text,
                "day_offset": parsed.day_offset,
                "horizon_days": parsed.horizon_days,
            },
        )
        intent = str(refined.get("intent", parsed.intent))
        location_text = refined.get("location") or parsed.location_text
        day_offset = int(refined.get("day_offset", parsed.day_offset) or 0)
        horizon_days = int(refined.get("horizon_days", parsed.horizon_days) or 7)
    else:
        intent = parsed.intent
        location_text = parsed.location_text
        day_offset = parsed.day_offset
        horizon_days = parsed.horizon_days

    # Rule-based NLU is authoritative for an explicit forecast horizon.
    # LLMs frequently understand "5" but may normalize Bengali/Hindi number
    # words such as "পাঁচ" / "पाँच" back to the default 7.  If the parser
    # detected a concrete horizon below the default, never let refinement
    # overwrite it.  This keeps digit and word forms behaviorally identical.
    if parsed.intent == "forecast" and parsed.horizon_days < 7:
        intent = "forecast"
        horizon_days = parsed.horizon_days
        day_offset = parsed.day_offset

    # Forecasts exposed by the product are limited to seven days. Keep this
    # guard after optional LLM refinement as well, so an LLM can never expand
    # a user request beyond the supported horizon.
    horizon_days = max(1, min(int(horizon_days or 7), 7))
    day_offset = max(0, min(int(day_offset or 0), horizon_days - 1))

    # An explicit "my location" / "near me" phrase means the user wants their
    # own GPS position used — full stop. Never try to geocode whatever text
    # is left over in the sentence (e.g. "...for my location with ETA, rain,
    # fog and road risk" can otherwise leak a stray word like "optimisation"
    # or "with" as a fake place name and silently answer for a random town).
    # This overrides both the rule-based parse and any LLM refine guess.
    if wants_device_location:
        location_text = None

    if intent == "greeting":
        greet_text = i18n.t(i18n.GREETING, lang)
        # Was previously always returned in English regardless of `lang` (the
        # `greet` dict only ever had an "en" key) — every other intent below
        # runs its fallback text through `_fast_reply`/`llm.phrase_reply` to
        # translate; greeting was the one exception. Match that behavior.
        reply = await _fast_reply(greet_text, lang, user_question=text)
        return {
            "reply": reply,
            "lang": lang,
            "intent": intent,
            "data": None,
        }

    if intent == "help":
        help_text = i18n.t(i18n.HELP, lang)
        reply = await _fast_reply(help_text, lang, user_question=text)
        return {
            "reply": reply,
            "lang": lang,
            "intent": intent,
            "data": None,
        }

    # Cyclone questions are answered from IMD/WIS2 feeds and do NOT require
    # a city. Detect early so we never fall through to "Which place…?".
    is_cyclone_query = intent == "alert" and any(
        w in text.lower()
        for w in (
            "cyclone",
            "cyclones",
            "चक्रवात",
            "ঘূর্ণিঝড়",
            "புயல்",
            "తుఫాను",
            "तूफान",
            "typhoon",
            "hurricane",
            "depression",
        )
    )

    if is_cyclone_query:
        # Support "cyclone near Chennai and Kolkata" -> one cyclone report per
        # named place, so two places asked in one message get two separate
        # yes/no answers instead of being merged into a single lookup.
        locs: list[str] = nlu.split_multi_location(location_text)
        requested_locations: list[str | None] = [loc for loc in locs] if locs else [None]

        async def _cyclone_section(loc: str | None) -> tuple[str, dict[str, Any]]:
            region_label = loc or "the requested region"
            try:
                cyclones = await satellite.get_active_cyclones(region=loc)
            except Exception:
                cyclones = []
            mono = satellite.monsoon_status(region=loc)
            # Tag each storm with a human-readable basin label so a broad
            # region ("Pacific") that legitimately spans several distinct
            # basins doesn't get flattened into one confusing mixed list.
            for c in cyclones:
                c["basin_label"] = _basin_label(c.get("basin"))
            alert, alert_label = _cyclone_alert(cyclones)
            if cyclones:
                # Group by basin/sub-region so e.g. Western Pacific storms
                # and Eastern/Central Pacific storms (thousands of miles
                # apart, but both technically "Pacific") are shown under
                # clearly separate headings, never merged into one list.
                groups: dict[str, list[dict[str, Any]]] = {}
                for c in cyclones:
                    groups.setdefault(c["basin_label"], []).append(c)

                block_lines = []
                for basin_label, storms in groups.items():
                    header = basin_label if len(groups) > 1 else None
                    if header:
                        block_lines.append(f"\n{header}:")
                    for c in storms[:5]:
                        name = c.get("name") or "Unnamed"
                        cat = c.get("category") or "tropical system"
                        msw = c.get("mean_msw_kmph")
                        kt = c.get("intensity_kt")
                        pos = ""
                        if c.get("latest_lat") is not None and c.get("latest_lon") is not None:
                            pos = f" | Position: {c['latest_lat']:.1f}°, {c['latest_lon']:.1f}°"
                        wind = ""
                        if msw:
                            wind = f" | Max winds ~{msw:.0f} km/h"
                            if kt:
                                wind += f" ({kt:.0f} kt)"
                        elif kt:
                            wind = f" | Intensity ~{kt:.0f} kt"
                        src = c.get("source") or ""
                        basin = c.get("basin") or ""
                        block_lines.append(f"• {name} — {cat}{wind}{pos} [{src}/{basin}]".replace("/]", "]"))
                section = (
                    f"Yes. Active tropical system(s) near {region_label} ({len(cyclones)} total, "
                    f"{alert_label}):\n"
                    + "\n".join(block_lines).lstrip("\n")
                    + f"\n\nSeasonal context: {mono['phase']}. {mono['tip']} "
                    + "Follow official advisories (IMD / PAGASA / JMA / NHC / JTWC)."
                )
            else:
                section = (
                    f"No active tropical cyclone is currently listed near {region_label} "
                    f"in the combined IMD + NHC + RAMMB/CIRA feeds. "
                    f"Seasonal context: {mono['phase']}. {mono['tip']}"
                )
            info = {
                "active_cyclones": cyclones,
                "region": region_label,
                "monsoon": mono,
                "map": _cyclone_map_payload(cyclones, region_label),
                "alert": alert,
                "alert_label": alert_label,
            }
            return section, info

        sections = []
        by_location: dict[str, Any] = {}
        first_map = None
        multi = len(requested_locations) > 1
        for loc in requested_locations:
            section, info = await _cyclone_section(loc)
            key = loc or "region"
            sections.append(f"— {key.title()} —\n{section}" if multi else section)
            by_location[key] = info
            if first_map is None and info.get("map"):
                first_map = info["map"]

        reply = "\n\n".join(sections)
        data: dict[str, Any] = {
            "data_source": "IMD + NHC CurrentStorms + RAMMB/CIRA TC realtime (+ WIS2 fallback)",
            "map": first_map,
        }
        if multi:
            data["by_location"] = by_location
        else:
            data.update(next(iter(by_location.values())))

        return {"reply": reply, "lang": lang, "intent": "alert", "data": data}

    # --- resolve location -------------------------------------------------
    place: dict[str, Any] | None = None
    lat: float | None = None
    lon: float | None = None
    if location_text:
        place = await geocode.resolve_location(location_text, language=lang)
        if place:
            lat, lon = place["latitude"], place["longitude"]
    # GPS fallback: use device location when the user did not name a place
    if (lat is None or lon is None) and client_lat is not None and client_lon is not None:
        lat, lon = client_lat, client_lon
        place = {"name": await geocode.reverse_label(lat, lon)}

    if lat is None or lon is None:
        # No usable location. Before giving up, try answering as a general
        # weather/meteorology question (LLM, then Google Search fallback).
        found = await _general_fallback(text, i18n.SUPPORTED[lang]["name"])
        if found:
            data = {"sources": found["sources"]} if found["sources"] else None
            return {"reply": found["reply"], "lang": lang, "intent": intent, "data": data}
        if location_text and place is None:
            return {
                "reply": i18n.t(i18n.LOCATION_NOT_FOUND, lang),
                "lang": lang,
                "intent": intent,
                "data": None,
            }
        return {
            "reply": i18n.t(i18n.NO_LOCATION_PROMPT, lang),
            "lang": lang,
            "intent": intent,
            "data": None,
            "needs_location": True,
        }

    location_label = (place.get("name") if place else None) or location_text or "your location"
    if place and place.get("admin1") and place["admin1"].lower() not in location_label.lower():
        location_label = f"{location_label}, {place['admin1']}"

    # --- historical/past weather -----------------------------------------
    # Historical requests use the archive/reanalysis endpoint, never the live
    # forecast endpoint. This is the key distinction that prevents a query
    # like "yesterday's weather" from accidentally showing today's forecast.
    if intent == "historical":
        hist_start = parsed.historical_start_date
        hist_end = parsed.historical_end_date
        if not hist_start or not hist_end:
            # Defensive fallback for an older/custom NLU result.
            from datetime import date, timedelta
            hist_start = (date.today() - timedelta(days=7)).isoformat()
            hist_end = (date.today() - timedelta(days=1)).isoformat()

        district, historical = await asyncio.gather(
            gis.lookup_district(lat, lon),
            weather.get_historical_weather(lat, lon, hist_start, hist_end),
        )

        if historical.get("error") or not historical.get("daily", {}).get("time"):
            reason = historical.get(
                "reason",
                "Historical weather data is temporarily unavailable for those dates."
            )
            error_msg = f"Past weather for {location_label} could not be retrieved ({reason})"
            error_msg = await _fast_reply(error_msg, lang, user_question=text)
            return {
                "reply": error_msg,
                "lang": lang,
                "intent": "historical",
                "data": {
                    "error": True,
                    "historical": True,
                    "reason": reason,
                    "location": location_label,
                    "coordinates": {"lat": lat, "lon": lon},
                    "requested_start": hist_start,
                    "requested_end": hist_end,
                    "data_source": "Open-Meteo Historical Weather API (archive/reanalysis)",
                    "map": {"lat": lat, "lon": lon, "label": location_label, "zoom": 8},
                },
            }

        hd = historical["daily"]
        dates = hd.get("time", [])
        rows = []
        for j, hist_date in enumerate(dates):
            def hv(key):
                arr = hd.get(key) or []
                return arr[j] if j < len(arr) else None

            code = hv("weathercode")
            rows.append({
                "date": hist_date,
                "temperature_min": hv("temperature_2m_min"),
                "temperature_max": hv("temperature_2m_max"),
                "rainfall_mm": hv("precipitation_sum"),
                "rain_hours": hv("precipitation_hours"),
                "wind_kmh": hv("windspeed_10m_max"),
                "windgust_kmh": hv("windgusts_10m_max"),
                "humidity_max": hv("relative_humidity_2m_max"),
                "humidity_min": hv("relative_humidity_2m_min"),
                "weathercode": code,
                "condition": i18n.weather_condition(code, lang) if code is not None else "—",
            })

        rain_values = [r["rainfall_mm"] for r in rows if r["rainfall_mm"] is not None]
        high_values = [r["temperature_max"] for r in rows if r["temperature_max"] is not None]
        low_values = [r["temperature_min"] for r in rows if r["temperature_min"] is not None]
        wind_values = [r["wind_kmh"] for r in rows if r["wind_kmh"] is not None]

        payload = {
            "location": location_label,
            "coordinates": {"lat": lat, "lon": lon},
            "district": district,
            "historical": True,
            "historical_start": hist_start,
            "historical_end": hist_end,
            "historical_days": len(rows),
            "historical_reports": rows,
            "data_source": historical.get(
                "data_source",
                "Open-Meteo Historical Weather API (archive/reanalysis)"
            ),
            "map": {"lat": lat, "lon": lon, "label": location_label, "zoom": 8},
        }

        summary_parts = [
            f"Past weather report for {location_label}: {hist_start} to {hist_end}.",
            f"{len(rows)} day(s) of historical data are shown below."
        ]
        if high_values and low_values:
            summary_parts.append(
                f"Observed/reanalysis temperature range across the period: "
                f"{min(low_values):.1f}°C to {max(high_values):.1f}°C."
            )
        if rain_values:
            summary_parts.append(f"Total rainfall across the period: {sum(rain_values):.1f} mm.")
        if wind_values:
            summary_parts.append(f"Peak daily maximum wind: {max(wind_values):.1f} km/h.")

        fallback_text = " ".join(summary_parts)
        reply = await _fast_reply(fallback_text, lang, user_question=text)
        return {
            "reply": reply,
            "lang": lang,
            "intent": "historical",
            "data": payload,
        }

    # Parallel: district GIS + forecast (faster response)
    district, forecast = await asyncio.gather(
        gis.lookup_district(lat, lon),
        weather.get_forecast(lat, lon, days=max(horizon_days, day_offset + 1)),
    )
    if forecast.get("error") or not forecast.get("daily") or not forecast.get("daily", {}).get("time"):
        reason = forecast.get("reason", "Weather models temporarily unreachable. Please retry.")
        error_msg = f"Sorry, live weather data for {location_label} could not be retrieved at this moment ({reason})."
        if lang != "en":
            error_msg = await _fast_reply(error_msg, lang, user_question=text)
        return {
            "reply": error_msg,
            "lang": lang,
            "intent": intent,
            "data": {
                "error": True,
                "reason": reason,
                "location": location_label,
                "coordinates": {"lat": lat, "lon": lon},
                "map": {"lat": lat, "lon": lon, "label": location_label, "zoom": 8} if lat is not None and lon is not None else None,
            },
        }

    daily = forecast.get("daily", {})
    timeline = alerts_mod.build_alert_timeline(daily)
    idx = min(day_offset, len(timeline) - 1) if timeline else 0

    day_data = {k: (v[idx] if idx < len(v) else None) for k, v in daily.items() if k != "time"}
    today_alert = timeline[idx] if timeline else {"level": "green", "hazards": []}
    current = forecast.get("current_weather", {})

    today_level = str(today_alert.get("level", "green"))
    payload: dict[str, Any] = {
        "location": location_label,
        "coordinates": {"lat": lat, "lon": lon},
        "district": district,
        "current": current,
        "day": day_data,
        "date": daily.get("time", [None])[idx] if daily.get("time") else None,
        "alert": today_alert,
        "alert_label": i18n.alert_label(today_level, lang),
        "timeline": timeline,
    }
    payload["map"] = {"lat": lat, "lon": lon, "label": location_label, "zoom": 8}

    # For an explicit multi-day forecast request, return only the number of
    # daily records requested (1–7). This is separate from `day`, which remains
    # the selected/current day for the existing bulletin UI.
    if intent == "forecast":
        forecast_rows = []
        requested_rows = daily.get("time", [])[:horizon_days]
        for i, forecast_date in enumerate(requested_rows):
            row = {
                "date": forecast_date,
                "temperature_min": daily.get("temperature_2m_min", [None] * len(requested_rows))[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                "temperature_max": daily.get("temperature_2m_max", [None] * len(requested_rows))[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                "rain_probability": daily.get("precipitation_probability_max", [None] * len(requested_rows))[i] if i < len(daily.get("precipitation_probability_max", [])) else None,
                "rainfall_mm": daily.get("precipitation_sum", [None] * len(requested_rows))[i] if i < len(daily.get("precipitation_sum", [])) else None,
                "wind_kmh": daily.get("windspeed_10m_max", [None] * len(requested_rows))[i] if i < len(daily.get("windspeed_10m_max", [])) else None,
                "weathercode": daily.get("weathercode", [None] * len(requested_rows))[i] if i < len(daily.get("weathercode", [])) else None,
            }
            row["condition"] = i18n.weather_condition(row["weathercode"], lang) if row["weathercode"] is not None else "—"
            row["alert"] = timeline[i] if i < len(timeline) else {"level": "green", "hazards": []}
            forecast_rows.append(row)
        payload["forecast_days"] = horizon_days
        payload["forecast"] = forecast_rows

    # Attach satellite-informed cyclone status (IMD + WIS2 fallback)
    try:
        cyclones = await satellite.get_active_cyclones()
        if cyclones:
            payload["active_cyclones"] = cyclones
    except Exception:
        cyclones = []

    # --- build reply per intent --------------------------------------------
    if intent == "umbrella":
        # Precise rain / umbrella answer driven by ensemble precip probability
        # (satellite-assimilated NWP). Example:
        # "No. There is a 0% chance of rain tomorrow in Mumbai."
        rain_prob = day_data.get("precipitation_probability_max")
        precip_mm = day_data.get("precipitation_sum")
        advice = satellite.rain_advice(rain_prob, precip_mm)
        day_label = "today" if day_offset == 0 else ("tomorrow" if day_offset == 1 else f"in {day_offset} days")

        when_key = "today" if day_offset == 0 else ("tomorrow" if day_offset == 1 else "today")
        when_text = i18n.WHEN[when_key].get(lang, i18n.WHEN[when_key]["en"]) if day_offset < 2 else f"+{day_offset}d"
        rain_value = rain_prob if rain_prob is not None else 0
        advice_table = i18n.RAIN_ADVICE_YES if rain_value >= 40 else i18n.RAIN_ADVICE_NO
        fallback_text = i18n.t(i18n.RAIN_TEMPLATE, lang).format(
            location=location_label, when=when_text, rain=rain_value, advice=i18n.t(advice_table, lang)
        )
        # Strong deterministic reply so the user always gets a clear yes/no + %
        # even when the optional LLM is offline or rephrases poorly.
        reply = fallback_text
        if lang != "en":
            # still try natural phrasing in the requested language
            reply = await llm.phrase_reply(
                fallback_text,
                i18n.SUPPORTED[lang]["name"],
                fallback_text,
                user_question=text,
            )
        payload["umbrella_advice"] = advice
        payload["data_source"] = (
            "Open-Meteo ensemble (GFS/ICON/…) — precipitation probability "
            "derived from models that assimilate satellite observations"
        )

    elif intent in ("current", "forecast"):
        condition = i18n.weather_condition(day_data.get("weathercode") if day_data.get("weathercode") is not None else current.get("weathercode"), lang)
        temp = current.get("temperature")
        if temp is None:
            temp = current.get("temperature_2m")
        if temp is None:
            temp = day_data.get("temperature_2m_max")
        tmin = day_data.get("temperature_2m_min") if day_data.get("temperature_2m_min") is not None else temp
        tmax = day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else temp
        rain_prob = (
            day_data.get("precipitation_probability_max")
            if day_data.get("precipitation_probability_max") is not None
            else 0
        )
        wind = (
            current.get("windspeed")
            if current.get("windspeed") is not None
            else (
                current.get("wind_speed_10m")
                if current.get("wind_speed_10m") is not None
                else (day_data.get("windspeed_10m_max") or 0)
            )
        )

        if intent == "forecast":
            fallback_text = i18n.t(i18n.FORECAST_TEMPLATE, lang).format(days=horizon_days, location=location_label)
        else:
            fallback_text = i18n.t(i18n.CURRENT_TEMPLATE, lang).format(
                location=location_label,
                condition=condition,
                temp=round(temp, 1) if temp is not None else "—",
                tmin=round(tmin, 1) if tmin is not None else "—",
                tmax=round(tmax, 1) if tmax is not None else "—",
                rain_prob=rain_prob,
                wind=round(wind, 1),
            )
        humidity = current.get("relative_humidity")
        pressure = current.get("surface_pressure")
        visibility_km = current.get("visibility_km")
        uv_index = current.get("uv_index")

        summary_for_llm = (
            f"Location: {location_label}. Condition: {condition}. "
            f"Current temp: {temp}C. Today's range: {tmin}-{tmax}C. Rain chance: {rain_prob}%. "
            f"Wind: {wind} km/h. Humidity: {humidity}%. Pressure: {pressure} hPa. "
            f"Visibility: {visibility_km} km. UV index: {uv_index}. "
            f"Alert level: {today_alert['level']} ({', '.join(today_alert['hazards']) or 'no hazards'})."
        )
        if intent == "forecast":
            week_bits = []
            for day in timeline[: min(horizon_days, len(timeline))]:
                week_bits.append(f"{day['date']}: {day['level']} ({', '.join(day['hazards']) or 'normal'})")
            summary_for_llm += " Outlook: " + "; ".join(week_bits)
            payload["outlook"] = timeline[: horizon_days]

        # Structured fields for the frontend's condition chips — kept out of
        # the translated template string (numbers/units don't need
        # translation) and shown directly in the UI instead.
        payload["conditions"] = {
            "humidity_pct": humidity,
            "pressure_hpa": pressure,
            "visibility_km": visibility_km,
            "uv_index": uv_index,
            "uv_category": _uv_category(uv_index),
        }

        reply = await llm.phrase_reply(
            summary_for_llm,
            i18n.SUPPORTED[lang]["name"],
            fallback_text,
            user_question=text,
        )

    elif intent == "alert":
        fallback_text = i18n.t(i18n.ALERT_TEMPLATE, lang).format(
            location=location_label, alert=i18n.alert_label(today_level, lang)
        )
        # Enrich with any active cyclones from satellite / IMD feed
        if cyclones and lang == "en":
            names = ", ".join(c["name"] for c in cyclones[:3])
            fallback_text += f" Active cyclone(s) being monitored: {names}."
        summary_for_llm = fallback_text
        reply = await llm.phrase_reply(
            summary_for_llm,
            i18n.SUPPORTED[lang]["name"],
            fallback_text,
            user_question=text,
        )
        payload["outlook"] = timeline
        live_bulletins = wis2.get_recent_bulletins(limit=3)
        if live_bulletins:
            payload["live_wis2_bulletins"] = live_bulletins

    elif intent == "climate":
        hist = await weather.get_historical_summary(lat, lon, years_back=10)
        trend = weather.summarize_yearly_trend(hist)
        explained = weather.explain_climate_trend(trend)
        payload["climate_trend"] = trend
        # Chart-ready arrays (years / temps / rainfall) so the frontend can
        # render a real line chart instead of just a table of numbers.
        payload["climate_chart"] = explained["chart"]
        payload["climate_trend_stats"] = {
            "temp_trend_c_per_decade": explained["temp_trend_c_per_decade"],
            "rainfall_trend_mm_per_decade": explained["rainfall_trend_mm_per_decade"],
        }
        recent = trend[-5:] if len(trend) >= 5 else trend
        trend_str = "; ".join(
            f"{r['year']} avg max {r['avg_max_temp_c']}°C, rain {r['total_rainfall_mm']}mm"
            for r in recent
        )
        fallback_text = i18n.t(i18n.CLIMATE_TEMPLATE, lang).format(location=location_label)
        summary_for_llm = fallback_text
        reply = await llm.phrase_reply(
            summary_for_llm,
            i18n.SUPPORTED[lang]["name"],
            fallback_text,
            user_question=text,
        )

    elif intent == "aqi":
        aq = await air_quality.get_air_quality(lat, lon)
        if aq.get("error") or aq.get("aqi") is None:
            fallback_text = f"AQI data for {location_label} is temporarily unavailable."
        else:
            dominant = aq.get("dominant_pollutant")
            # Show the reading that actually drove the AQI so the number is never
            # a black box — PM2.5/PM10 are always shown below; if a different
            # pollutant (O3/NO2/SO2/CO) is dominant, surface its own value too.
            dominant_value_map = {
                "O3": ("ozone", "µg/m³"),
                "NO2": ("nitrogen_dioxide", "µg/m³"),
                "SO2": ("sulphur_dioxide", "µg/m³"),
                "CO": ("carbon_monoxide", "µg/m³"),
            }
            dominant_note = ""
            if dominant:
                dominant_note = f" Dominant pollutant: {dominant}"
                if dominant in dominant_value_map:
                    field, unit = dominant_value_map[dominant]
                    val = aq.get(field)
                    if val is not None:
                        dominant_note += f" ({val} {unit})"
                dominant_note += "."
            health_note = aq.get("health_note") or ""
            low_confidence_note = (
                " Note: this reading is based on only 1-2 pollutants, so treat it as indicative."
                if aq.get("sufficient_data") is False else ""
            )
            fallback_text = i18n.t(i18n.AQI_TEMPLATE, lang).format(
                location=location_label, aqi=aq.get("aqi"), category=aq.get("category"),
                pm25=aq.get("pm2_5"), pm10=aq.get("pm10")
            )
        payload["air_quality"] = aq
        payload["data_source"] = aq.get("data_source", "Open-Meteo Air Quality")
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "agriculture":
        tips = advisory.agriculture_advisory(day_data, today_alert)
        fallback_text = i18n.generic_weather_summary("agriculture", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["advisory"] = tips
        payload["pest_risk"] = advisory.pest_risk_index(day_data)
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "aviation":
        hourly = forecast.get("hourly", {})
        tips = advisory.aviation_briefing(day_data, hourly, today_alert)
        fallback_text = i18n.generic_weather_summary("aviation", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["advisory"] = tips
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "marine":
        # Real ocean-swell data from Open-Meteo's Marine API (returns nothing
        # useful for inland points, which port_delay_risk() reports as
        # "unknown" rather than inventing a number).
        marine_day = None
        try:
            marine_data = await weather.get_marine_forecast(lat, lon)
            marine_daily = marine_data.get("daily", {}) if not marine_data.get("error") else {}
            if marine_daily:
                marine_day = {
                    k: (v[idx] if idx < len(v) else None)
                    for k, v in marine_daily.items()
                    if k != "time"
                }
        except Exception:
            marine_day = None
        tips = advisory.marine_advisory(day_data, today_alert, marine_day=marine_day)
        fallback_text = i18n.generic_weather_summary("marine", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["advisory"] = tips
        payload["port_delay_risk"] = advisory.port_delay_risk(marine_day)
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "urban":
        tips = advisory.urban_advisory(day_data, today_alert)
        tips = tips + advisory.safety_tips(day_data, today_alert)
        fallback_text = i18n.generic_weather_summary("urban", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["advisory"] = tips
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "energy":
        # Real Open-Meteo shortwave radiation + 80m wind speed — a genuine
        # NWP-derived outlook, not a GraphCast/Prithvi-WxC generation model
        # (running those requires GPU infrastructure this environment doesn't have).
        try:
            energy_data = await weather.get_energy_forecast(lat, lon)
            hourly_energy = energy_data.get("hourly", {}) if not energy_data.get("error") else {}
        except Exception:
            hourly_energy = {}
        summary = advisory.energy_forecast_summary(hourly_energy)
        fallback_text = i18n.generic_weather_summary("energy", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["energy_forecast"] = summary
        payload["data_source"] = (
            "Open-Meteo hourly shortwave radiation + 80m wind speed (real NWP data)"
        )
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "retail":
        tips = advisory.retail_advisory(today_alert, timeline)
        fallback_text = i18n.generic_weather_summary("retail", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["advisory"] = tips
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    elif intent == "construction":
        tips = advisory.construction_advisory(day_data, today_alert)
        fallback_text = i18n.generic_weather_summary("construction", lang, location=location_label,
            temp=day_data.get("temperature_2m_max") if day_data.get("temperature_2m_max") is not None else current.get("temperature"),
            rain=day_data.get("precipitation_probability_max") or 0, wind=day_data.get("windspeed_10m_max") or current.get("windspeed") or 0,
            alert=i18n.alert_label(today_level, lang))
        payload["advisory"] = tips
        reply = await _fast_reply(fallback_text, lang, user_question=text)

    else:
        # Rule-based NLU has no dedicated handler for this intent (or the
        # message doesn't look like a structured weather query at all) —
        # last resort before giving up is to let Gemini (or whichever LLM
        # is configured) take a direct shot at it, falling back to Google
        # Search snippets if no LLM key is configured, so "any other
        # statement" still gets a real answer instead of a canned prompt.
        found = await _general_fallback(text, i18n.SUPPORTED[lang]["name"])
        reply = found["reply"] if found else i18n.t(i18n.NO_LOCATION_PROMPT, lang)
        if found and found["sources"]:
            payload = {"sources": found["sources"]}

    if payload is not None and "data_source" not in payload:
        payload["data_source"] = (
            "Open-Meteo ensemble NWP (satellite-assimilated) · IMD colour alerts · WIS2.0"
        )
    return {"reply": reply, "lang": lang, "intent": intent, "data": payload}
