import pytest
from app import weather


@pytest.mark.asyncio
async def test_get_forecast_valid():
    # Test Kolkata coords
    data = await weather.get_forecast(22.57, 88.36, days=5)
    assert not data.get("error")
    assert "daily" in data
    assert "current_weather" in data
    assert "hourly" in data

    daily = data["daily"]
    assert "temperature_2m_max" in daily
    assert "temperature_2m_min" in daily
    assert "precipitation_probability_max" in daily
    assert len(daily.get("time", [])) >= 5

    current = data["current_weather"]
    assert current.get("temperature") is not None
    assert current.get("windspeed") is not None


@pytest.mark.asyncio
async def test_get_forecast_specific_nwp_model():
    # Pinning to a single named NWP model (GFS) instead of the auto-blend.
    data = await weather.get_forecast(22.57, 88.36, days=3, model="gfs")
    assert not data.get("error")
    assert data.get("model_used") == "gfs_seamless"
    assert "daily" in data


def test_resolve_model_slug():
    assert weather.resolve_model_slug("gfs") == "gfs_seamless"
    assert weather.resolve_model_slug("ICON") == "icon_seamless"
    assert weather.resolve_model_slug("meteofrance_arome") == "meteofrance_arome_france"
    # Unknown keys pass through unchanged so any Open-Meteo slug still works.
    assert weather.resolve_model_slug("some_future_model") == "some_future_model"


@pytest.mark.asyncio
async def test_get_multi_model_forecast():
    result = await weather.get_multi_model_forecast(22.57, 88.36, days=3, models=["gfs", "icon"])
    assert not result.get("error")
    assert set(result["models"].keys()) == {"gfs", "icon"}
    for model_data in result["models"].values():
        assert model_data["temperature_2m_max"] is not None
        assert len(model_data["time"]) >= 3
    assert len(result["model_agreement"]) >= 3
    assert "spread_c" in result["model_agreement"][0]


@pytest.mark.asyncio
async def test_weather_code_label():
    assert weather.weather_code_label(0) == "clear sky"
    assert weather.weather_code_label(95) == "thunderstorm"
    assert weather.weather_code_label(999) == "changeable conditions"
    assert weather.weather_code_label(None) == "changeable conditions"


def test_summarize_yearly_trend():
    mock_hist = [
        {
            "year": 2024,
            "data": {
                "temperature_2m_max": [30.0, 32.0, 34.0],
                "precipitation_sum": [10.0, 20.0, 30.0],
            },
        },
        {
            "year": 2023,
            "data": {
                "temperature_2m_max": [28.0, 30.0],
                "precipitation_sum": [5.0, 15.0],
            },
        },
    ]
    summary = weather.summarize_yearly_trend(mock_hist)
    assert len(summary) == 2
    assert summary[0]["year"] == 2023
    assert summary[0]["avg_max_temp_c"] == 29.0
    assert summary[0]["total_rainfall_mm"] == 20.0
    assert summary[1]["year"] == 2024
    assert summary[1]["avg_max_temp_c"] == 32.0
    assert summary[1]["total_rainfall_mm"] == 60.0
