# Past Weather Reports — Added

WeatherGPT now supports historical/past weather queries separately from forecasts.

## Examples

- `Yesterday weather in Kolkata`
- `Show past weather for Kolkata`
- `Last 7 days weather in Kolkata`
- `Past 5 days weather in Delhi`
- `Weather on 25 August 2026 in Kolkata`
- `Weather 25/08/2026 Kolkata`
- Bengali: `গতকাল কলকাতার আবহাওয়া`
- Hindi: `कल का मौसम कोलकाता`

## Backend

- `GET /api/weather/history` was added.
- Historical data uses Open-Meteo's archive/reanalysis API.
- For very recent dates, the backend can fall back to Open-Meteo's `past_days` data so "yesterday" is less likely to fail because the archive is still catching up.
- Historical requests never call the live forecast endpoint as their primary source.

## UI

Past reports are shown in a dedicated **PAST REPORT** section with:
- date
- minimum/maximum temperature
- rainfall
- rain hours
- maximum wind
- humidity
- weather condition
- location/map and data source

The existing forecast and climate-trend behavior remains unchanged.
