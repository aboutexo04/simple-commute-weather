"""Tests for FastAPI endpoints exposed in app.py."""

from __future__ import annotations

import datetime as dt
from typing import Optional

import pytest
from fastapi.testclient import TestClient

import app as web_app
from commute_weather.pipelines.commute_predictor import CommutePrediction
from commute_weather.pipelines.baseline import ComfortScoreBreakdown
from commute_weather.data_sources.weather_api import WeatherObservation


def _make_prediction(latest: Optional[WeatherObservation]) -> CommutePrediction:
    return CommutePrediction(
        prediction_time=dt.datetime(2024, 1, 1, 8, 0),
        target_period="morning_commute",
        comfort_score=ComfortScoreBreakdown(
            score=72.5,
            penalties={
                "temperature": 5.0,
                "precipitation": 0.0,
                "wind": 12.5,
                "humidity": 10.0,
            },
        ),
        observations_count=3,
        data_period="05:00-08:00",
        latest_observation=latest,
    )


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required environment variables exist for the API config."""

    monkeypatch.setenv("KMA_AUTH_KEY", "test-key")
    monkeypatch.setenv("KMA_STATION_ID", "108")


def test_predict_now_uses_latest_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/predict/now` should surface metrics from the predictor's latest observation."""

    latest = WeatherObservation(
        timestamp=dt.datetime(2024, 1, 1, 7, 0),
        temperature_c=3.5,
        wind_speed_ms=2.0,
        precipitation_mm=0.0,
        relative_humidity=45.0,
        precipitation_type="none",
    )

    class DummyPredictor:
        def __init__(self, *_: object, **__: object) -> None:  # pragma: no cover - simple stub
            pass

        def get_current_prediction(self) -> CommutePrediction:
            return _make_prediction(latest)

    def _unexpected_fetch(*_: object, **__: object) -> None:  # pragma: no cover - guard
        raise AssertionError("fetch_recent_weather_kma should not be called when latest observation exists")

    monkeypatch.setattr(web_app, "CommutePredictor", DummyPredictor)
    monkeypatch.setattr(web_app, "fetch_recent_weather_kma", _unexpected_fetch)

    client = TestClient(web_app.app)
    response = client.get("/predict/now")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_temp"] == pytest.approx(3.5)
    assert payload["current_humidity"] == pytest.approx(45.0)
    assert payload["current_precipitation"] == pytest.approx(0.0)
    assert payload["current_precipitation_type"] == "none"


def test_predict_now_handles_missing_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint should respond with nulls when the predictor lacks a latest observation."""

    class DummyPredictor:
        def __init__(self, *_: object, **__: object) -> None:  # pragma: no cover - simple stub
            pass

        def get_current_prediction(self) -> CommutePrediction:
            return _make_prediction(None)

    fallback_observation = WeatherObservation(
        timestamp=dt.datetime(2024, 1, 1, 7, 0),
        temperature_c=1.0,
        wind_speed_ms=1.5,
        precipitation_mm=0.2,
        relative_humidity=70.0,
        precipitation_type="snow",
    )

    monkeypatch.setattr(web_app, "CommutePredictor", DummyPredictor)
    monkeypatch.setattr(web_app, "fetch_recent_weather_kma", lambda *_, **__: [fallback_observation])

    client = TestClient(web_app.app)
    response = client.get("/predict/now")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_temp"] == pytest.approx(1.0)
    assert payload["current_humidity"] == pytest.approx(70.0)
    assert payload["current_precipitation"] == pytest.approx(0.2)
    assert payload["current_precipitation_type"] == "snow"
