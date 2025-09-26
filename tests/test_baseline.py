from __future__ import annotations

import datetime as dt
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SRC = PROJECT_ROOT / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from commute_weather.data_sources.weather_api import WeatherObservation, normalize_observations
from commute_weather.pipelines.baseline import compute_commute_comfort_score


def test_compute_commute_comfort_score_sample_payload() -> None:
    payload = {
        "observations": [
            {
                "timestamp": "2024-05-05T07:00:00",
                "temperature_c": 18.0,
                "wind_speed_ms": 3.2,
                "precipitation_mm": 0.0,
                "relative_humidity": 55.0,
            },
            {
                "timestamp": "2024-05-05T08:00:00",
                "temperature_c": 19.5,
                "wind_speed_ms": 3.8,
                "precipitation_mm": 0.0,
                "relative_humidity": 53.0,
            },
            {
                "timestamp": "2024-05-05T09:00:00",
                "temperature_c": 21.0,
                "wind_speed_ms": 4.2,
                "precipitation_mm": 0.0,
                "relative_humidity": 50.0,
            },
        ]
    }

    observations = normalize_observations(payload)
    breakdown = compute_commute_comfort_score(observations)

    assert breakdown.score == 100.0
    assert breakdown.label == "excellent"


def test_temperature_penalty_extreme_cold() -> None:
    observations = [
        WeatherObservation(
            timestamp=dt.datetime(2024, 5, 5, 7, 0),
            temperature_c=-5,
            wind_speed_ms=2.0,
            precipitation_mm=0.0,
            relative_humidity=40.0,
        )
        for _ in range(3)
    ]
    breakdown = compute_commute_comfort_score(observations)
    assert breakdown.score < 100
    assert breakdown.penalties["temperature"] > 0
