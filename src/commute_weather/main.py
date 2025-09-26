"""Main CLI application for commute weather comfort predictions."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import KMAAPIConfig
from .scheduler import CommuteScheduler
from .pipelines.commute_predictor import CommutePredictor, format_prediction_report


def create_kma_config() -> KMAAPIConfig:
    """Create KMA API configuration from environment variables."""

    auth_key = os.getenv("KMA_AUTH_KEY")
    if not auth_key:
        print("❌ KMA_AUTH_KEY 환경변수가 필요합니다.")
        print("사용법: export KMA_AUTH_KEY='your-api-key'")
        sys.exit(1)

    station_id = os.getenv("KMA_STATION_ID", "108")  # Default to Seoul

    return KMAAPIConfig(
        base_url="https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php",
        auth_key=auth_key,
        station_id=station_id,
    )


def cmd_predict_now(args: argparse.Namespace) -> None:
    """Run immediate prediction based on current time."""

    config = create_kma_config()
    predictor = CommutePredictor(config)

    try:
        prediction = predictor.get_current_prediction()
        report = format_prediction_report(prediction)
        print(report)

    except Exception as e:
        print(f"❌ 예측 실패: {str(e)}")
        sys.exit(1)


def cmd_predict_morning(args: argparse.Namespace) -> None:
    """Run morning commute prediction."""

    config = create_kma_config()
    predictor = CommutePredictor(config)

    try:
        prediction = predictor.predict_morning_commute()
        report = format_prediction_report(prediction)
        print(f"🌅 출근길 예측:\n{report}")

    except Exception as e:
        print(f"❌ 출근길 예측 실패: {str(e)}")
        sys.exit(1)


def cmd_predict_evening(args: argparse.Namespace) -> None:
    """Run evening commute prediction."""

    config = create_kma_config()
    predictor = CommutePredictor(config)

    try:
        prediction = predictor.predict_evening_commute()
        report = format_prediction_report(prediction)
        print(f"🌆 퇴근길 예측:\n{report}")

    except Exception as e:
        print(f"❌ 퇴근길 예측 실패: {str(e)}")
        sys.exit(1)


def cmd_schedule(args: argparse.Namespace) -> None:
    """Start scheduled predictions."""

    config = create_kma_config()
    scheduler = CommuteScheduler(config)

    print("🚀 출퇴근 예측 스케줄러를 시작합니다...")
    print("- 매일 오전 7시: 출근길 예측")
    print("- 오후 2-6시: 매시간 퇴근길 예측")
    print("Ctrl+C로 중단할 수 있습니다.")

    try:
        scheduler.start_scheduled_predictions()
    except KeyboardInterrupt:
        print("\n⏹️ 스케줄러를 중단합니다.")


def cmd_test_api(args: argparse.Namespace) -> None:
    """Test KMA API connection."""

    config = create_kma_config()

    try:
        from .data_sources.weather_api import fetch_kma_weather

        print("🔍 KMA API 연결 테스트 중...")
        observations = fetch_kma_weather(config, lookback_hours=1)

        if observations:
            print(f"✅ API 연결 성공! {len(observations)}개 관측 데이터 수신")
            latest = observations[-1]
            print(f"📊 최신 데이터: {latest.timestamp} - 온도 {latest.temperature_c}°C")
        else:
            print("⚠️ API 연결됨, 그러나 데이터가 없습니다.")

    except Exception as e:
        print(f"❌ API 연결 실패: {str(e)}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""

    parser = argparse.ArgumentParser(
        description="출퇴근길 쾌적지수 예측 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m commute_weather now      # 현재 시점 예측
  python -m commute_weather morning  # 출근길 예측
  python -m commute_weather evening  # 퇴근길 예측
  python -m commute_weather schedule # 스케줄 실행
  python -m commute_weather test     # API 연결 테스트

환경변수:
  KMA_AUTH_KEY     기상청 API 인증키 (필수)
  KMA_STATION_ID   기상 관측소 ID (기본값: 108 - 서울)
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # Immediate prediction
    subparsers.add_parser("now", help="현재 시점 예측")

    # Morning prediction
    subparsers.add_parser("morning", help="출근길 예측 (최근 3시간 데이터)")

    # Evening prediction
    subparsers.add_parser("evening", help="퇴근길 예측 (오후 2-5시 데이터)")

    # Scheduled mode
    subparsers.add_parser("schedule", help="스케줄 모드 (7시 출근, 2-6시 퇴근)")

    # Test API
    subparsers.add_parser("test", help="API 연결 테스트")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to appropriate command handler
    command_handlers = {
        "now": cmd_predict_now,
        "morning": cmd_predict_morning,
        "evening": cmd_predict_evening,
        "schedule": cmd_schedule,
        "test": cmd_test_api,
    }

    handler = command_handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"❌ 알 수 없는 명령어: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()