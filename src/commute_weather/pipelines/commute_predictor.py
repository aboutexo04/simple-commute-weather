"""Commute comfort prediction for morning and evening schedules."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional
import pytz

from ..config import KMAAPIConfig
from ..data_sources.weather_api import fetch_kma_weather, WeatherObservation
from .baseline import compute_commute_comfort_score, ComfortScoreBreakdown


@dataclass(frozen=True)
class CommutePrediction:
    """Prediction result with timestamp and score details."""

    prediction_time: dt.datetime
    target_period: str  # "morning_commute" or "evening_commute"
    comfort_score: ComfortScoreBreakdown
    observations_count: int
    data_period: str  # Time range of data used


class CommutePredictor:
    """Predicts commute comfort based on recent weather data."""

    def __init__(self, kma_config: KMAAPIConfig):
        self.kma_config = kma_config

    def predict_morning_commute(self) -> CommutePrediction:
        """Predict morning commute comfort using last 3 hours of weather data."""

        kst = pytz.timezone('Asia/Seoul')
        current_time = dt.datetime.now(kst)

        # Get weather data from last 3 hours for morning prediction
        observations = fetch_kma_weather(
            self.kma_config,
            lookback_hours=3
        )

        if not observations:
            raise ValueError("No weather observations available for morning prediction")

        comfort_score = compute_commute_comfort_score(observations)

        # Create data period description
        start_time = current_time - dt.timedelta(hours=3)
        data_period = f"{start_time.strftime('%H:%M')}-{current_time.strftime('%H:%M')}"

        return CommutePrediction(
            prediction_time=current_time,
            target_period="morning_commute",
            comfort_score=comfort_score,
            observations_count=len(observations),
            data_period=data_period
        )

    def predict_evening_commute(self) -> CommutePrediction:
        """Predict evening commute comfort using weather data from 2-5 PM."""

        kst = pytz.timezone('Asia/Seoul')
        current_time = dt.datetime.now(kst)
        today = current_time.date()

        # Define afternoon period (2-5 PM) in KST
        start_time = kst.localize(dt.datetime.combine(today, dt.time(14, 0)))  # 2 PM KST
        end_time = kst.localize(dt.datetime.combine(today, dt.time(17, 0)))    # 5 PM KST

        # Calculate hours from start_time to current time
        if current_time < start_time:
            # If current time is before 2 PM, we can't make evening prediction yet
            raise ValueError("Cannot predict evening commute before 2 PM")

        # Get hours between start_time and current time (or end_time if past 5 PM)
        actual_end_time = min(current_time, end_time)
        lookback_hours = int((actual_end_time - start_time).total_seconds() / 3600)

        if lookback_hours < 1:
            lookback_hours = 1  # Minimum 1 hour

        observations = fetch_kma_weather(
            self.kma_config,
            lookback_hours=lookback_hours
        )

        if not observations:
            raise ValueError("No weather observations available for evening prediction")

        # Filter observations to only include afternoon period
        afternoon_observations = [
            obs for obs in observations
            if start_time <= obs.timestamp <= actual_end_time
        ]

        if not afternoon_observations:
            # If no afternoon data, use all available recent data
            afternoon_observations = observations

        comfort_score = compute_commute_comfort_score(afternoon_observations)

        # Create data period description
        data_period = f"{start_time.strftime('%H:%M')}-{actual_end_time.strftime('%H:%M')}"

        return CommutePrediction(
            prediction_time=current_time,
            target_period="evening_commute",
            comfort_score=comfort_score,
            observations_count=len(afternoon_observations),
            data_period=data_period
        )

    def get_current_prediction(self) -> CommutePrediction:
        """Get appropriate prediction based on current time."""

        kst = pytz.timezone('Asia/Seoul')
        current_hour = dt.datetime.now(kst).hour

        if 6 <= current_hour < 10:
            # Morning hours: predict morning commute
            return self.predict_morning_commute()
        elif 14 <= current_hour < 19:
            # Afternoon hours: predict evening commute
            return self.predict_evening_commute()
        else:
            # Outside commute prediction hours, default to morning prediction logic
            return self.predict_morning_commute()


def format_prediction_report(prediction: CommutePrediction) -> str:
    """Format prediction result as a readable report."""

    comfort = prediction.comfort_score

    report = f"""
=== 출퇴근길 쾌적지수 예측 ===
예측 시간: {prediction.prediction_time.strftime('%Y-%m-%d %H:%M')}
대상: {'출근길' if prediction.target_period == 'morning_commute' else '퇴근길'}
데이터 기간: {prediction.data_period}
관측 데이터 수: {prediction.observations_count}개

🌟 쾌적지수: {comfort.score:.1f}/100 ({comfort.label})

📊 세부 점수:
- 온도: -{comfort.penalties['temperature']:.1f}점
- 강수: -{comfort.penalties['precipitation']:.1f}점
- 바람: -{comfort.penalties['wind']:.1f}점
- 습도: -{comfort.penalties['humidity']:.1f}점

💡 한줄 평가: """

    if comfort.score >= 80:
        report += "완벽한 출퇴근 날씨입니다! ☀️"
    elif comfort.score >= 60:
        report += "쾌적한 출퇴근길이 예상됩니다. 😊"
    elif comfort.score >= 40:
        report += "보통 수준의 날씨입니다. 🌤️"
    else:
        report += "불편한 날씨가 예상됩니다. 준비하세요! 🌧️"

    return report