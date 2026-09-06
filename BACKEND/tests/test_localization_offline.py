import pytest
from app import composer, geocode, gis, llm, satellite, weather


@pytest.mark.asyncio
async def test_selected_bengali_language_localizes_forecast_without_llm(monkeypatch):
    async def fake_geo(query, language="en"):
        return {"name": "Dhaka", "admin1": "Dhaka", "country": "Bangladesh", "latitude": 23.81, "longitude": 90.41}

    async def fake_forecast(lat, lon, days=7, model=None):
        dates = ["2026-09-04", "2026-09-05", "2026-09-06"][:days]
        n = len(dates)
        return {
            "daily": {
                "time": dates,
                "temperature_2m_max": [30.0] * n,
                "temperature_2m_min": [25.0] * n,
                "precipitation_sum": [5.0] * n,
                "precipitation_probability_max": [80] * n,
                "windspeed_10m_max": [12.0] * n,
                "windgusts_10m_max": [20.0] * n,
                "winddirection_10m_dominant": [90] * n,
                "uv_index_max": [3.0] * n,
                "relative_humidity_2m_max": [90] * n,
                "weathercode": [61] * n,
            },
            "hourly": {},
            "current_weather": {"temperature": 27.0, "windspeed": 8.0, "weathercode": 61},
        }

    async def fake_district(*args, **kwargs):
        return None

    async def fake_cyclones(*args, **kwargs):
        return []

    monkeypatch.setattr(geocode, "resolve_location", fake_geo)
    monkeypatch.setattr(weather, "get_forecast", fake_forecast)
    monkeypatch.setattr(gis, "lookup_district", fake_district)
    monkeypatch.setattr(satellite, "get_active_cyclones", fake_cyclones)
    monkeypatch.setattr(llm, "llm_available", lambda: False)

    result = await composer.handle_message("2 day forecast for Dhaka", lang="bn")
    assert result["lang"] == "bn"
    assert "দিনের আবহাওয়ার পূর্বাভাস" in result["reply"]
    assert result["data"]["forecast_days"] == 2
    assert [row["condition"] for row in result["data"]["forecast"]] == ["বৃষ্টি", "বৃষ্টি"]
