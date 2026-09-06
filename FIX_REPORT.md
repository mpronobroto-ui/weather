# WeatherGPT refactor / audit report

This build was reviewed for runtime reliability, multilingual behavior, deployment configuration, and obvious security weaknesses.

## Fixed

- Selected reply language now controls the actual core answer even with no LLM API key. Added deterministic multilingual fallbacks for current weather, 1–7 day forecasts, rain/umbrella answers, AQI, alerts, climate summaries, greeting/help, and sector summaries.
- Forecast-row weather conditions are localized instead of always being English.
- Fixed the frontend backend-URL logic for `file://`, localhost, and the provided Render service names. Added optional `?api=https://...` override.
- Fixed the separate login/subscription script using a different hardcoded backend URL.
- Alert subscriptions now save the currently selected language instead of always saving English.
- Fixed the LLM intent schema: it now includes AQI, umbrella, energy, retail, construction, help, and the other supported intents, preventing LLM refinement from changing valid intents incorrectly.
- Fixed 0°C / zero-value handling where Python `or` could accidentally discard valid numeric zero values.
- Fixed map creation for valid coordinates on latitude/longitude zero.
- Added input validation for message length, coordinates, OTP format, labels, and paired lat/lon.
- OTP generation now uses `secrets` instead of the non-cryptographic `random` generator.
- Added OTP request throttling to reduce SMS-spam abuse.
- Production deployments no longer expose development OTP codes when SMS is missing.
- Production mode requires a real session secret and explicit CORS configuration. Render generates session and dispatch secrets.
- Render blueprint now sets production mode and the expected frontend origin.
- International Open-Meteo exact matches are no longer unnecessarily replaced by an India-biased fallback merely for having a score below 85.
- Added an offline localization regression test.

## Verification completed

- `python -m compileall -q BACKEND` passes.
- Frontend JavaScript extracted from `index.html` passes `node --check`.
- Render and Docker Compose YAML parse successfully.
- 12 offline/unit tests pass, including multilingual forecast localization.
- FastAPI application imports successfully in development mode.

## Live-integration note

Some existing repository tests directly call Open-Meteo / external geocoders. This execution sandbox could not reliably complete those external network calls, so those specific live-integration tests could not be fully re-run here. The production app still uses those real providers at runtime and already contains fallback/error handling for provider failures.

## Render deployment setting

The blueprint assumes the frontend URL is `https://weather-nova-frontend.onrender.com`. If Render gives your frontend a different URL, set backend `ALLOWED_ORIGINS` to that exact origin (no trailing slash). Secrets such as Gemini/Twilio/Google API keys must be entered in the Render dashboard and must not be committed to GitHub.

## 2026-09-04 Multilingual Number-Word Forecast Fix
Fixed a remaining NLU bug where numeric digits (5/৫) worked but written number words (Bengali `পাঁচ`, Hindi `पाँच`, English `five`, etc.) could return the default 7-day horizon. Number words are now normalized to numeric horizons 1–7, removed from location extraction, and explicit horizons detected by the rule engine cannot be overwritten by LLM refinement. See `NUMBER_WORD_FIX.md`.
