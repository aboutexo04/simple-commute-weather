"""Scheduled commute comfort predictions."""

from __future__ import annotations

import datetime as dt
import time
from typing import Callable, Optional

from .config import KMAAPIConfig
from .pipelines.commute_predictor import CommutePredictor, format_prediction_report


class CommuteScheduler:
    """Scheduler for automated commute comfort predictions."""

    def __init__(
        self,
        kma_config: KMAAPIConfig,
        output_callback: Optional[Callable[[str], None]] = None
    ):
        self.predictor = CommutePredictor(kma_config)
        self.output_callback = output_callback or print
        self._running = False

    def run_morning_prediction(self) -> None:
        """Run morning commute prediction at 7 AM."""

        try:
            prediction = self.predictor.predict_morning_commute()
            report = format_prediction_report(prediction)
            self.output_callback(f"🌅 아침 7시 출근길 예측:\n{report}")

        except Exception as e:
            self.output_callback(f"❌ 아침 예측 실패: {str(e)}")

    def run_evening_prediction(self) -> None:
        """Run evening commute prediction using 2-5 PM data."""

        try:
            prediction = self.predictor.predict_evening_commute()
            report = format_prediction_report(prediction)
            self.output_callback(f"🌆 퇴근길 예측 (오후 2-5시 데이터 기반):\n{report}")

        except Exception as e:
            self.output_callback(f"❌ 저녁 예측 실패: {str(e)}")

    def run_immediate_prediction(self) -> None:
        """Run immediate prediction based on current time."""

        try:
            prediction = self.predictor.get_current_prediction()
            report = format_prediction_report(prediction)
            self.output_callback(f"📱 현재 시점 예측:\n{report}")

        except Exception as e:
            self.output_callback(f"❌ 즉시 예측 실패: {str(e)}")

    def start_scheduled_predictions(self) -> None:
        """Start scheduled predictions (7 AM for morning, throughout afternoon for evening)."""

        self._running = True
        self.output_callback("🚀 출퇴근 예측 스케줄러 시작")

        while self._running:
            current_time = dt.datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute

            try:
                # Morning prediction at exactly 7:00 AM
                if current_hour == 7 and current_minute == 0:
                    self.run_morning_prediction()
                    time.sleep(60)  # Sleep for 1 minute to avoid duplicate runs

                # Evening predictions every hour from 2 PM to 6 PM
                elif 14 <= current_hour <= 18 and current_minute == 0:
                    self.run_evening_prediction()
                    time.sleep(60)  # Sleep for 1 minute to avoid duplicate runs

                else:
                    # Check every minute
                    time.sleep(60)

            except KeyboardInterrupt:
                self.output_callback("⏹️ 스케줄러 중단됨")
                break
            except Exception as e:
                self.output_callback(f"⚠️ 스케줄러 오류: {str(e)}")
                time.sleep(60)  # Continue after error

        self._running = False

    def stop_scheduled_predictions(self) -> None:
        """Stop the scheduled predictions."""

        self._running = False
        self.output_callback("⏹️ 스케줄러 중단 요청")


def create_scheduler_from_env() -> CommuteScheduler:
    """Create scheduler with KMA config from environment variables."""

    import os

    auth_key = os.getenv("KMA_AUTH_KEY")
    if not auth_key:
        raise ValueError("KMA_AUTH_KEY environment variable is required")

    station_id = os.getenv("KMA_STATION_ID", "108")  # Default to Seoul station

    kma_config = KMAAPIConfig(
        base_url="https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php",
        auth_key=auth_key,
        station_id=station_id,
    )

    return CommuteScheduler(kma_config)