"""
WeatherGPT Backend — FastAPI entry point.

This is what `uvicorn main:app` actually boots. It wires together every
module under app/ (nlu, composer, weather, alerts, geocode, gis, i18n, llm,
satellite, sms, subscriptions, wis2) behind a small set of REST endpoints
that FRONTEND/index.html already calls:

    GET  /api/health         -> liveness check
    GET  /api/languages      -> supported languages for the language picker
    GET  /api/status         -> integration status strip (WIS2 / LLM / SMS)
    POST /api/chat           -> the main conversational endpoint
    WS   /ws/chat            -> same conversation, over a websocket

Plus the subscription + alert-dispatch endpoints described in DEMO.md /
ARCHITECTURE.md for the SMS early-warning feature.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import logging
import os
from datetime import date, datetime

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import auth, composer, gis, i18n, llm, sms, subscriptions, weather, wis2, geocode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weathergpt")

_dispatch_task: asyncio.Task | None = None
DISPATCH_INTERVAL_SECONDS = max(60, int(os.getenv("ALERT_DISPATCH_INTERVAL_SECONDS", "3600")))
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}
_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in _allowed_origins_raw.split(",") if o.strip()]
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["*"] if not IS_PRODUCTION else []

# Optional shared secret protecting the manual /api/alerts/dispatch trigger.
# Without this, that endpoint is a public, unauthenticated way to force the
# app to send a real SMS (cost) to every subscriber — anyone who finds the
# URL could hammer it. If ALERT_DISPATCH_SECRET is unset we leave the route
# open (so local/dev/demo use keeps working with zero setup) but log a
# warning once at startup so this doesn't silently ship insecure.
ALERT_DISPATCH_SECRET = os.getenv("ALERT_DISPATCH_SECRET")

if auth.SESSION_SECRET == "dev-insecure-secret-change-me":
    logger.warning(
        "SESSION_SECRET is unset — using the insecure default. Anyone can forge "
        "login session tokens. Set SESSION_SECRET (a long random string) before "
        "deploying this anywhere real."
    )
if not ALERT_DISPATCH_SECRET:
    logger.warning(
        "ALERT_DISPATCH_SECRET is unset — POST /api/alerts/dispatch is open to "
        "anyone and can be used to trigger real SMS sends. Set ALERT_DISPATCH_SECRET "
        "to require an X-Dispatch-Secret header before deploying this anywhere real."
    )
if IS_PRODUCTION and auth.SESSION_SECRET == "dev-insecure-secret-change-me":
    raise RuntimeError("SESSION_SECRET must be set in production.")
if IS_PRODUCTION and not ALLOWED_ORIGINS:
    raise RuntimeError("ALLOWED_ORIGINS must be set in production (comma-separated frontend origins).")
if IS_PRODUCTION and sms.sms_configured() and not ALERT_DISPATCH_SECRET:
    raise RuntimeError("ALERT_DISPATCH_SECRET must be set in production when SMS is enabled.")


async def _dispatch_loop() -> None:
    """Periodically re-checks every subscriber against the live weather-alert
    level AND the live cyclone list, texting anyone newly in range. Runs
    only while at least one Twilio credential is set; otherwise it's a
    harmless no-op loop (dispatch_* already degrade gracefully with
    skipped_no_credentials=True)."""
    while True:
        try:
            await sms.dispatch_alerts()
            await sms.dispatch_cyclone_alerts()
        except Exception as exc:
            logger.warning("Scheduled alert dispatch failed: %s", exc)
        await asyncio.sleep(DISPATCH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dispatch_task
    try:
        wis2.start_listener()
    except Exception as exc:
        logger.warning("WIS2 listener failed to start: %s", exc)
    if sms.sms_configured():
        _dispatch_task = asyncio.create_task(_dispatch_loop())
    yield
    try:
        wis2.stop_listener()
    except Exception:
        pass
    if _dispatch_task:
        _dispatch_task.cancel()


app = FastAPI(title="WeatherGPT API", version="1.0.0", lifespan=lifespan)

# The frontend is served separately (nginx on :8080 in docker-compose, or a
# plain `python -m http.server` while developing) so CORS must be open.
#
# allow_credentials=True + allow_origins=["*"] used to be set together here,
# but that combination is both insecure and non-functional: browsers refuse
# to expose a credentialed response (cookies, or fetch(..., {credentials:
# "include"})) when the server echoes back a wildcard "*" origin, so it
# bought nothing except a wider attack surface. This app authenticates with
# a bearer token in the Authorization header (see app/auth.py), which is not
# a "credential" in the fetch/XHR sense and is unaffected by this flag, so
# allow_credentials is safely False here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    lang: str = Field(default="en", max_length=20)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class SubscribeRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    lang: str = Field(default="en", max_length=20)
    label: str | None = Field(default=None, max_length=120)
    cyclone_alerts: bool = True


class RequestOtpRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=24)


class VerifyOtpRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=24)
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


# ---------------------------------------------------------------------------
# Health / meta endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/languages")
async def languages() -> dict:
    return i18n.SUPPORTED


@app.get("/api/status")
async def status() -> dict:
    return {
        "integrations": {
            "wis2_mqtt": wis2.get_status(),
            "llm": {"status": "enabled" if llm.llm_available() else "disabled"},
            "sms_twilio": {"status": "configured" if sms.sms_configured() else "not_configured"},
            "gis": {"status": "available" if await gis.gis_available() else "unavailable"},
        }
    }


# ---------------------------------------------------------------------------
# Core conversational endpoint
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    if (req.lat is None) != (req.lon is None):
        raise HTTPException(status_code=400, detail="lat and lon must be provided together.")
    return await composer.handle_message(
        req.message.strip(),
        lang=req.lang,
        client_lat=req.lat,
        client_lon=req.lon,
    )




@app.get("/api/location/reverse")
async def reverse_location(lat: float, lon: float) -> dict:
    """Return a human-readable locality for a fresh browser GPS coordinate.

    GPS coordinates remain the source of truth. Reverse geocoding only supplies
    a user-friendly locality label (locality/suburb/city/district/state/country).
    """
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates.")

    result = await geocode.reverse_geocode(lat, lon)
    result["accuracy_note"] = "Label is reverse-geocoded from the supplied GPS coordinate."
    return result


@app.get("/api/weather/forecast")
async def forecast(lat: float, lon: float, days: int = 7, model: str | None = None) -> dict:
    """Single-model NWP forecast. `model` selects a specific provider
    (gfs, icon, ecmwf, gfs_hrrr, meteofrance_arome, ukmo, gem, jma) instead
    of Open-Meteo's auto-blended best_match — see app/weather.py:NWP_MODELS."""
    return await weather.get_forecast(lat, lon, days=days, model=model)


@app.get("/api/weather/history")
async def history(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str | None = None,
) -> dict:
    """Historical weather report for a concrete past date/range.

    Dates must be in YYYY-MM-DD format and the requested range must be in the
    past. This endpoint is backed by Open-Meteo's archive/reanalysis service.
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else start
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD format.")

    if end < start:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date.")
    if end >= date.today():
        raise HTTPException(status_code=400, detail="Historical reports must end before today.")
    if (end - start).days > 31:
        raise HTTPException(status_code=400, detail="Historical report range is limited to 32 days per request.")

    result = await weather.get_historical_weather(lat, lon, start.isoformat(), end.isoformat())
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result.get("reason", "Historical weather provider unavailable."))
    return result


@app.get("/api/weather/models/compare")
async def compare_models(lat: float, lon: float, days: int = 5, models: str | None = None) -> dict:
    """Runs several named NWP models (GFS, ICON, ECMWF, WRF-class regional
    models like Meteo-France AROME / NOAA HRRR, …) side by side for the same
    spot and returns each model's daily series plus a simple per-day
    forecast-spread figure, so users/clients can see model agreement rather
    than trusting a single blended forecast."""
    model_list = [m.strip() for m in models.split(",")] if models else None
    return await weather.get_multi_model_forecast(lat, lon, days=days, models=model_list)


@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            payload = await ws.receive_json()
            message = str(payload.get("message", "")).strip()[:2000]
            if not message:
                await ws.send_json({"error": "Message is required."})
                continue
            result = await composer.handle_message(
                message,
                lang=str(payload.get("lang", "en"))[:20],
                client_lat=payload.get("lat"),
                client_lon=payload.get("lon"),
            )
            await ws.send_json(result)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Login — phone number + OTP (no password to store; verifying the phone IS
# the login, since the whole point is "so alerts can reach you").
# ---------------------------------------------------------------------------
@app.post("/api/auth/request-otp")
async def request_otp(req: RequestOtpRequest) -> dict:
    if not req.phone or len(req.phone.strip()) < 6:
        raise HTTPException(status_code=400, detail="Enter a valid phone number.")
    allowed, retry_after = auth.otp_request_allowed(req.phone)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many OTP requests. Retry in {retry_after} seconds.")
    otp = auth.generate_otp(req.phone)
    if sms.sms_configured():
        sent = await sms._send_sms(auth._normalize_phone(req.phone), f"Your WeatherGPT login code is {otp}. It expires in 5 minutes.")
        return {"sent": sent, "channel": "sms"}
    # No Twilio configured (e.g. local dev) — return the code directly so
    # the flow is still testable instead of dead-ending.
    if IS_PRODUCTION:
        raise HTTPException(status_code=503, detail="SMS login is not configured on this deployment.")
    logger.info("SMS not configured — dev OTP generated for local development")
    return {"sent": False, "channel": "dev", "dev_otp": otp}


@app.post("/api/auth/verify-otp")
async def verify_otp(req: VerifyOtpRequest) -> dict:
    if not auth.verify_otp(req.phone, req.otp):
        raise HTTPException(status_code=401, detail="Incorrect or expired code.")
    phone = auth._normalize_phone(req.phone)
    token = auth.issue_token(phone)
    return {"token": token, "phone": phone}


@app.get("/api/auth/me")
async def me(phone: str = Depends(auth.require_session)) -> dict:
    return {"phone": phone, "subscription": subscriptions.get_subscription(phone)}


# ---------------------------------------------------------------------------
# SMS early-warning subscriptions (requires login — Authorization: Bearer)
# ---------------------------------------------------------------------------
@app.post("/api/subscribe")
async def subscribe(req: SubscribeRequest, phone: str = Depends(auth.require_session)) -> dict:
    lang = req.lang if req.lang in i18n.SUPPORTED else "en"
    return subscriptions.add_subscription(
        phone, req.lat, req.lon, lang=lang, label=req.label, cyclone_alerts=req.cyclone_alerts
    )


@app.delete("/api/subscribe")
async def unsubscribe(phone: str = Depends(auth.require_session)) -> dict:
    removed = subscriptions.remove_subscription(phone)
    return {"removed": removed}


@app.get("/api/subscriptions")
async def get_subscriptions(phone: str = Depends(auth.require_session)) -> dict:
    # Only the logged-in user's own subscription — not everyone's.
    return subscriptions.get_subscription(phone) or {}


@app.post("/api/alerts/dispatch")
async def dispatch_alerts(x_dispatch_secret: str | None = Header(default=None)) -> dict:
    if (ALERT_DISPATCH_SECRET and x_dispatch_secret != ALERT_DISPATCH_SECRET) or (IS_PRODUCTION and not ALERT_DISPATCH_SECRET):
        raise HTTPException(status_code=401, detail="Missing or incorrect X-Dispatch-Secret header.")
    weather_result = await sms.dispatch_alerts()
    cyclone_result = await sms.dispatch_cyclone_alerts()
    return {"weather_alerts": weather_result, "cyclone_alerts": cyclone_result}
