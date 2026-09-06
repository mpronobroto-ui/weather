# WeatherGPT — Conversational Weather Intelligence

A working weather-intelligence platform: natural-language weather Q&A in 12 Indian
languages, IMD-style colour alerts, live cyclone tracking, sector advisories, and
phone-verified SMS early-warning for cyclones — built for a hackathon, presentable
to judges as a real running prototype (not a mockup).

---

## 1. What it does

| Capability | How |
|---|---|
| Real-time weather | Live Open-Meteo NWP ensemble forecasts (GFS/ICON/DWD) — no canned data |
| Natural-language chat | Offline rule-based NLU (`app/nlu.py`) + optional Gemini/OpenAI/Ollama refinement (`app/llm.py`) |
| Cyclone tracking | Merged live feed from IMD, NHC `CurrentStorms.json`, and RAMMB/CIRA — filtered to the region actually asked about |
| IMD-style alerts | Green/Yellow/Orange/Red thresholds from rainfall, wind, heat/cold indices (`app/alerts.py`) |
| Sector advisories | Farming, aviation, marine, urban, energy, retail, construction (`app/advisory.py`) |
| Multilingual | 12 languages pre-translated (`app/i18n.py`): Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Punjabi, Kannada, Malayalam, Odia, Urdu, English |
| Voice | Browser Web Speech API — speech-to-text input, text-to-speech replies |
| Login + SMS alerts | Phone + OTP login (`app/auth.py`); logged-in users get a real Twilio SMS when an active cyclone comes within 100km of their saved location (`app/sms.py`) |
| Climate trend | 10-year historical rainfall/temperature aggregation |
| District GIS | Point-in-polygon lookup against Indian districts (PostgreSQL/PostGIS, `app/gis.py`) |
| Live bulletins | WIS2.0 Global Broker MQTT feed (`app/wis2.py`) |
| General-question fallback | Google Custom Search grounding for the LLM, plus a sourced no-LLM-needed fallback answer (`app/google_search.py`) |

No mocked weather anywhere — every number on screen traces back to a real upstream
API (Open-Meteo, IMD, NHC, RAMMB/CIRA, WIS2.0).

---

## 2. Architecture

```
FRONTEND/index.html  →  single-file chat PWA (no build step)
        │  REST (/api/chat) or WebSocket (/ws/chat)
        ▼
BACKEND/main.py       →  FastAPI entry point, wires every module below
        │
        ├─ nlu.py        offline intent + location extraction (12 languages)
        ├─ llm.py         optional LLM refine/phrase step (Gemini/OpenAI/Ollama)
        ├─ composer.py    orchestrates one chat turn end-to-end
        ├─ geocode.py     place name → lat/lon
        ├─ weather.py     Open-Meteo forecast/marine/energy calls
        ├─ satellite.py   cyclone merge (IMD+NHC+RAMMB) + region filter + rain advice
        ├─ alerts.py      IMD-style colour thresholds
        ├─ advisory.py    sector-specific tip generation
        ├─ gis.py         PostgreSQL/PostGIS district lookup
        ├─ google_search.py  Google Custom Search fallback + LLM grounding
        ├─ wis2.py        WIS2.0 MQTT listener
        ├─ auth.py        phone+OTP login, signed session tokens
        ├─ subscriptions.py  who gets alerted, where
        └─ sms.py         Twilio dispatch (weather-alert level + cyclone-proximity)
```

All heavy computation runs server-side; the frontend stays a thin, fast chat client.

---

## 3. Run it locally

```bash
cd BACKEND
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env        # then edit .env with your own keys (see below)
uvicorn main:app --reload --port 8000
```

Open `FRONTEND/index.html` directly in a browser (or serve it: `python -m http.server 8080`
from inside `FRONTEND/`). The chat's ⚙ / API-base prompt lets you point it at
`http://localhost:8000`.

**Everything works with an empty `.env`** — no keys required for a demo. Add keys only
to unlock extra integrations:

| Key | Unlocks |
|---|---|
| `GEMINI_API_KEY` | Natural-language phrasing + general-question fallback via Gemini |
| `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` | Google Custom Search grounding for general questions, and a sourced fallback answer even with no LLM key configured |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | Real SMS delivery for OTP login + cyclone alerts |
| `DATABASE_URL` (or `PG_*`) | District GIS point-in-polygon lookups (PostgreSQL + PostGIS) |

## 4. Run with Docker

```bash
docker compose up
```
Starts PostgreSQL/PostGIS, the backend (`:8000`), and the frontend (`:8080`) together — `BACKEND/SQL/districts.sql` is auto-loaded into Postgres on first start.

## 5. Deploy on Render

This repo includes `render.yaml` — from the Render dashboard, "New → Blueprint",
point it at this repo, and it creates two services:
- `weather-nova-backend` (Python web service, FastAPI)
- `weather-nova-frontend` (static site)

After deploy, add your real secrets (`GEMINI_API_KEY`, `TWILIO_*`) in the backend
service's **Environment** tab on Render — never commit them to `.env` in the repo.
Then open the frontend URL, tap the API-base setting, and paste the backend's
Render URL once (saved in the browser after that).

---

## 6. API endpoints (what's actually implemented)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/languages` | Supported languages |
| GET | `/api/status` | Integration status (WIS2 / LLM / SMS / GIS) — good first thing to show judges |
| POST | `/api/chat` | Main conversational endpoint |
| WS | `/ws/chat` | Same, over a websocket |
| POST | `/api/auth/request-otp` | Send login OTP by SMS |
| POST | `/api/auth/verify-otp` | Verify OTP, returns session token |
| GET | `/api/auth/me` | Current logged-in phone + subscription (requires `Authorization: Bearer <token>`) |
| POST | `/api/subscribe` | Save location for cyclone SMS alerts (requires login) |
| DELETE | `/api/subscribe` | Remove your subscription (requires login) |
| GET | `/api/subscriptions` | Your own subscription (requires login) |
| POST | `/api/alerts/dispatch` | Manually trigger one alert-check pass (also runs automatically on a timer) |

---

## 7. Demo script for judges (~4 minutes)

1. **"Is there a cyclone near the Philippines?"** — shows the live merged IMD/NHC/RAMMB
   feed, filtered to only that region's basin (not the whole world's active storms).
2. Tap **Use my location** → ask **"Should I take an umbrella tomorrow?"** — exact %
   chance of rain from ensemble NWP, not a guess.
3. Ask a farming/aviation/marine question — sector advisory tied to the live alert level.
4. Switch language to Hindi/Bengali/Tamil, ask the same kind of question.
5. Log in (phone + OTP) and enable cyclone alerts for your location — explain that a
   real SMS goes out automatically if a storm comes within 100km.
6. Ask something entirely unrelated to weather — show the Gemini fallback still gives
   a real, on-topic answer instead of a dead end.
7. Point at `/api/status` to show every live integration at a glance.

**If something fails live:** Open-Meteo occasionally rate-limits (a few seconds' wait
fixes it); with no cyclone active near the asked region, the honest "no active system"
answer is itself proof the pipeline is live, not scripted.

---

## 8. Honesty notes (say this to judges — it scores points)

- Cell Broadcast / SACHET integration is a documented **seam**, not a live connection —
  `sms.py` sends real Twilio SMS today; swapping in a CAP-formatted POST to a real
  CBC/SACHET gateway needs a signed telecom agreement, not code.
- IMD colour thresholds are **derived** from public rainfall/wind bands, not pulled
  directly from an IMD alerts API (IMD doesn't publish one).
- LLM phrasing is optional and additive — the whole app runs correctly with zero LLM
  key configured, using the deterministic rule-based templates instead.

---

## 9. Smart city weather monitoring — vision & use cases

WeatherGPT is built as an intelligent weather **decision-support system**, not
just a forecast lookup — the architecture (async FastAPI, pooled PostGIS,
real-time MQTT ingestion, sector-specific advisory templates) is the same
shape a city or regional deployment would need, just pointed at one user's
question at a time today.

**Possible use cases:**

- **Farmers** — crop-stage-aware sowing/irrigation/spraying advisories
  (`app/advisory.py::agriculture_advisory`) tied to live rainfall probability
  and pest-risk index, in the farmer's own language.
- **Aviation** — crosswind, visibility, and thunderstorm-risk advisories for
  pre-flight planning (`app/advisory.py::aviation_advisory`).
- **Marine / fisheries** — wave height, swell, and port-delay risk from live
  ocean-model data (`app/weather.py::get_marine_forecast`).
- **Urban planning & municipal ops** — district-scoped alerts via the PostGIS
  GIS layer, so a hazard can be reported against an actual administrative
  boundary instead of a raw coordinate — the seam for drawing hazard
  polygons on a city dashboard.
- **Energy** — solar-irradiance and wind-speed outlooks for renewable
  generation planning (`app/weather.py::get_energy_forecast`).
- **General public** — a mobile-friendly conversational front end (PWA,
  installable, voice input/output) for anyone who just wants a plain-language
  answer instead of reading a raw forecast chart.

**GIS tools:** `app/gis.py` runs real PostGIS point-in-polygon queries
(`ST_Contains`) against a `districts` table (`BACKEND/SQL/districts.sql`),
so any advisory can be scoped to an actual district/state instead of a bare
lat/lon — swap in real Survey of India / OSM boundary polygons (via
`ogr2ogr` or QGIS's PostGIS export) to go from the bundled sample bounding
boxes to production-accurate boundaries.

**Scalable architecture:** the backend is a stateless async FastAPI service
(safe to run as multiple replicas behind a load balancer), talks to
PostgreSQL through a connection pool, and ingests live cyclone-track
bulletins continuously over an MQTT subscription (`app/wis2.py`) rather than
polling — the same real-time-ingestion pattern a city-scale sensor network
(traffic, air-quality stations, river-gauge telemetry) would plug into.

**NWP model integration:** `app/weather.py` already queries named upstream
numerical weather prediction models through Open-Meteo's model-routing API —
NOAA GFS, DWD ICON, ECMWF IFS, and WRF-class convection-permitting regional
models (NOAA HRRR, Météo-France AROME) — either individually or blended, and
`get_multi_model_forecast` reports the spread between models as a simple
forecast-uncertainty signal. Open-Meteo is a broker in front of these
national met agencies' own model output, not a from-scratch reimplementation
of GFS/WRF physics; running a raw WRF domain yourself would mean provisioning
your own HPC/GPU compute for the mesoscale simulation, which is out of scope
for a hackathon prototype but is a documented next step if the project moves
toward a self-hosted regional model.

## Reliability/security fixes in this build

- Reply language is now deterministic for the core chat flow even when no LLM key is configured: current weather, 1–7 day forecasts, AQI, rain/umbrella answers, alerts, climate summaries, and sector-module summaries follow the selected language. Weather-condition text in forecast rows is localized too.
- `file://` and localhost frontend launches now automatically use `http://localhost:8000`; the Render frontend automatically targets the matching Render backend, and `?api=https://...` can override this without editing code.
- Production mode requires a non-default session secret and an explicit CORS allow-list. The Render blueprint generates both session/dispatch secrets and sets the expected frontend origin.
- Development OTP codes are never returned by a production deployment. OTP generation uses Python's `secrets` module rather than the non-cryptographic PRNG.
- Chat/subscription coordinates, message lengths, OTP format, and labels are validated at the API boundary.

For a differently named Render frontend service, change `ALLOWED_ORIGINS` in the Render dashboard to that exact `https://...onrender.com` origin. Do not include a trailing slash.
