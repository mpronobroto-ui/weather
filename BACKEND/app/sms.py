"""
Early-warning dissemination — SMS today, Cell-Broadcast-ready architecture.

The brief calls for "extreme weather alerts and early warning dissemination"
reaching people beyond the chat window — critical for rural users without a
smartphone open at the right moment. This module sends real SMS via
Twilio's REST API (no SDK dependency, just httpx) to everyone subscribed
near a hazardous location.

True Cell Broadcast (the SMS-like blast IMD/NDMA use for cyclone warnings,
via India's SACHET / Common Alerting Protocol gateway) requires a signed
agreement with a telecom's Cell Broadcast Centre — not something any app can
call directly. `dispatch_alerts()` is exactly the seam where that would
plug in: replace `_send_sms()` with a CAP-formatted POST to a CBC/SACHET
gateway and every subscriber in this file starts receiving Cell Broadcast
warnings instead of / in addition to SMS, with no other code changes.

Degrades gracefully: with no Twilio credentials set, `dispatch_alerts()`
still evaluates every subscriber's alert level (useful for testing / for the
`/api/alerts/dispatch` endpoint's dry-run response) but skips the actual
send and reports it was skipped.
"""
from __future__ import annotations

import logging
import math
import os
from typing import Any

import httpx

from . import alerts as alerts_mod
from . import i18n, satellite, subscriptions, weather

logger = logging.getLogger("sms")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

DISPATCH_MIN_LEVEL = os.getenv("ALERT_DISPATCH_MIN_LEVEL", "orange")  # orange or red
_LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}

# A subscriber gets a cyclone SMS once an active storm's centre comes within
# this radius of their saved location. Default 100km — a tight, closer-to-
# landfall warning radius (raise it via CYCLONE_ALERT_RADIUS_KM if you want
# earlier/wider warnings).
CYCLONE_ALERT_RADIUS_KM = float(os.getenv("CYCLONE_ALERT_RADIUS_KM", "100"))

# In-memory set of (phone, storm_name) pairs already texted for the storm's
# CURRENT time in range. Without this, dispatch_cyclone_alerts() (called on
# a timer — see main.py's _dispatch_loop, default hourly) would re-send the
# same cyclone SMS to the same person every single run for as long as the
# storm stays within range — the docstring below already promised "only
# fires... the first time... goes into range", this is what actually makes
# that true. Cleared for a (phone, storm) pair once the storm is no longer
# nearby, so a *later* re-entry (e.g. storm loops back, or a new storm with
# the same generic name next season) still alerts again.
_already_notified: set[tuple[str, str]] = set()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def sms_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER)


async def _send_sms(to_phone: str, body: str) -> bool:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {"From": TWILIO_FROM_NUMBER, "To": to_phone, "Body": body}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            return resp.status_code < 300
        except Exception as exc:
            logger.warning("SMS send failed to %s: %s", to_phone, exc)
            return False


async def dispatch_alerts() -> dict:
    """Check every subscriber's location; send an SMS warning to anyone
    whose area is at/above DISPATCH_MIN_LEVEL today. Returns a summary dict
    (used by the /api/alerts/dispatch endpoint and the background task).
    """
    subs = subscriptions.list_subscriptions()
    results: dict[str, Any] = {"checked": 0, "warned": 0, "sent": 0, "skipped_no_credentials": not sms_configured(), "details": []}

    for sub in subs:
        results["checked"] += 1
        try:
            forecast = await weather.get_forecast(sub["lat"], sub["lon"], days=1)
            timeline = alerts_mod.build_alert_timeline(forecast.get("daily", {}))
            today = timeline[0] if timeline else {"level": "green", "hazards": []}
        except Exception as exc:
            results["details"].append({"phone": sub["phone"], "error": str(exc)})
            continue

        today_level = str(today.get("level", "green"))
        today_hazards = list(today.get("hazards", []))

        if _LEVEL_RANK.get(today_level, 0) >= _LEVEL_RANK.get(DISPATCH_MIN_LEVEL, 2):
            results["warned"] += 1
            lang = str(sub.get("lang", "en"))
            label = i18n.alert_label(today_level, lang)
            hazards = ", ".join(today_hazards) or "severe weather"
            body = f"WeatherGPT alert [{label}]: {hazards} expected near your location today. Stay safe."
            sent = await _send_sms(sub["phone"], body)
            if sent:
                results["sent"] += 1
            results["details"].append({"phone": sub["phone"], "level": today_level, "hazards": today_hazards, "sms_sent": sent})

    return results


async def dispatch_cyclone_alerts() -> dict:
    """Check every subscriber who opted into cyclone_alerts against the
    live IMD + NHC + RAMMB/CIRA storm list; SMS anyone within
    CYCLONE_ALERT_RADIUS_KM of an active storm's current centre. Only fires
    an SMS the first time a given (phone, storm name) pair goes into range
    this run — call this on a timer (see main.py startup loop).
    """
    subs = [s for s in subscriptions.list_subscriptions() if s.get("cyclone_alerts", True)]
    results: dict[str, Any] = {"checked": 0, "warned": 0, "sent": 0, "skipped_no_credentials": not sms_configured(), "details": []}
    if not subs:
        return results

    try:
        storms = await satellite.get_active_cyclones()
    except Exception as exc:
        results["error"] = str(exc)
        return results

    tracked = [s for s in storms if s.get("latest_lat") is not None and s.get("latest_lon") is not None]

    seen_this_run: set[tuple[str, str]] = set()

    for sub in subs:
        results["checked"] += 1
        nearby = []
        for storm in tracked:
            dist = _haversine_km(sub["lat"], sub["lon"], storm["latest_lat"], storm["latest_lon"])
            if dist <= CYCLONE_ALERT_RADIUS_KM:
                nearby.append((storm, round(dist)))
        if not nearby:
            continue

        for storm, _dist in nearby:
            seen_this_run.add((sub["phone"], storm["name"]))

        # Only text about storms this phone hasn't already been warned about
        # while still in range — repeat runs while the storm lingers nearby
        # should stay silent instead of re-texting every dispatch interval.
        new_nearby = [(s, d) for s, d in nearby if (sub["phone"], s["name"]) not in _already_notified]
        for storm, _dist in nearby:
            _already_notified.add((sub["phone"], storm["name"]))
        if not new_nearby:
            continue

        results["warned"] += 1
        lang = sub.get("lang", "en")
        names = ", ".join(f"{s['name']} (~{d}km away)" for s, d in new_nearby[:3])
        body = f"WeatherGPT cyclone alert: active storm(s) near your saved location — {names}. Follow official IMD/PAGASA/NHC advisories."
        sent = await _send_sms(sub["phone"], body)
        if sent:
            results["sent"] += 1
        results["details"].append({
            "phone": sub["phone"],
            "storms": [{"name": s["name"], "distance_km": d} for s, d in new_nearby],
            "sms_sent": sent,
        })

    # A (phone, storm) pair that was in range before but isn't anymore is no
    # longer "current" — drop it so a future re-entry (or a same-named storm
    # next season) alerts again instead of staying suppressed forever.
    _already_notified.intersection_update(seen_this_run)

    return results
