"""Heuristic commute comfort score using the last few hours of weather."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable, Mapping

from ..data_sources.weather_api import WeatherObservation


@dataclass(frozen=True)
class ComfortScoreBreakdown:
    """Carries the final score alongside the individual penalties."""

    score: float
    penalties: Mapping[str, float]

    @property
    def label(self) -> str:
        if self.score >= 80:
            return "excellent"
        if self.score >= 60:
            return "good"
        if self.score >= 40:
            return "fair"
        return "poor"


def compute_commute_comfort_score(observations: Iterable[WeatherObservation]) -> ComfortScoreBreakdown:
    """Compute a simple comfort score from weather observations.

    The score starts at 100 and subtracts penalties for uncomfortable
    conditions. This baseline acts as a quick benchmark before trying ML.
    """

    obs_list = list(observations)
    if not obs_list:
        raise ValueError("At least one observation is required")

    base_score = 100.0
    penalties = {
        "temperature": _temperature_penalty(obs_list),
        "precipitation": _precipitation_penalty(obs_list),
        "wind": _wind_penalty(obs_list),
        "humidity": _humidity_penalty(obs_list),
    }

    final_score = max(0.0, base_score - sum(penalties.values()))
    return ComfortScoreBreakdown(score=final_score, penalties=penalties)


def _temperature_penalty(observations: list[WeatherObservation]) -> float:
    temps = [obs.temperature_c for obs in observations]
    median_temp = statistics.median(temps)
    if 10 <= median_temp <= 25:
        return 0.0
    if median_temp < 10:
        return min(40.0, (10 - median_temp) * 2.5)
    return min(40.0, (median_temp - 25) * 1.8)


def _precipitation_penalty(observations: list[WeatherObservation]) -> float:
    """Calculate precipitation penalty with different weights for rain vs snow."""
    rain_total = 0.0
    snow_total = 0.0

    for obs in observations:
        if obs.precipitation_mm > 0:
            if obs.precipitation_type == "snow":
                snow_total += obs.precipitation_mm
            else:  # rain or unspecified precipitation
                rain_total += obs.precipitation_mm

    if rain_total == 0 and snow_total == 0:
        return 0.0

    # Snow is more inconvenient than rain for commuting
    rain_penalty = min(30.0, rain_total * 5.0)      # Rain: up to 30 points
    snow_penalty = min(40.0, snow_total * 8.0)      # Snow: up to 40 points (worse)

    return rain_penalty + snow_penalty


def _wind_penalty(observations: list[WeatherObservation]) -> float:
    peak_wind = max(obs.wind_speed_ms for obs in observations)
    if peak_wind <= 4:
        return 0.0
    return min(25.0, (peak_wind - 4) * 3.0)


def _humidity_penalty(observations: list[WeatherObservation]) -> float:
    humidities = [obs.relative_humidity for obs in observations if obs.relative_humidity is not None]
    if not humidities:
        return 0.0
    avg_humidity = statistics.mean(humidities)
    if 30 <= avg_humidity <= 70:
        return 0.0
    return min(15.0, abs(avg_humidity - 50) * 0.4)
