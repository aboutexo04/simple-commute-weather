#!/usr/bin/env python3
"""Entry-point for running the baseline comfort score pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SRC = PROJECT_ROOT / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from commute_weather.config import KMAAPIConfig, ProjectPaths, WeatherAPIConfig
from commute_weather.data_sources.weather_api import (
    WeatherObservation,
    normalize_observations,
    fetch_recent_weather,
)
from commute_weather.data_sources.kma_api import fetch_recent_weather_kma
from commute_weather.pipelines.baseline import (
    ComfortScoreBreakdown,
    compute_commute_comfort_score,
)


def _observations_from_file(path: Path) -> Iterable[WeatherObservation]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return normalize_observations(payload)


def _run_from_sample(paths: ProjectPaths) -> ComfortScoreBreakdown:
    sample_file = paths.data_raw / "example_recent_weather.json"
    observations = _observations_from_file(sample_file)
    return compute_commute_comfort_score(observations)



def _run_from_api(args: argparse.Namespace) -> ComfortScoreBreakdown:
    cfg = WeatherAPIConfig(
        base_url=args.base_url,
        api_key=args.api_key or os.getenv("WEATHER_API_KEY"),
        location=args.location,
        timeout_seconds=args.timeout,
    )
    observations = fetch_recent_weather(cfg, lookback_hours=args.lookback_hours)
    return compute_commute_comfort_score(observations)


def _run_from_kma(args: argparse.Namespace) -> ComfortScoreBreakdown:
    auth_key = args.kma_auth_key or os.getenv("KMA_AUTH_KEY")
    if not auth_key:
        raise SystemExit("Provide a KMA auth key via --kma-auth-key or KMA_AUTH_KEY env var")

    cfg = KMAAPIConfig(
        base_url=args.kma_base_url,
        auth_key=auth_key,
        station_id=str(args.kma_station),
        help_flag=args.kma_help_flag,
        timeout_seconds=args.timeout,
        timezone=args.kma_timezone,
    )
    observations = fetch_recent_weather_kma(cfg, lookback_hours=args.lookback_hours)
    return compute_commute_comfort_score(observations)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["sample", "api", "kma"], help="Choose data source")
    parser.add_argument(
        "--project-root",
        default=PROJECT_ROOT,
        type=Path,
        help="Project root for locating data files",
    )
    parser.add_argument("--base-url", default="https://api.example.com/weather", help="Weather API base URL")
    parser.add_argument("--location", default=os.getenv("COMMUTE_LOCATION"), help="Location identifier for API calls")
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key override (falls back to WEATHER_API_KEY env var)",
    )
    parser.add_argument("--lookback-hours", type=int, default=3, help="Hours of recent data to retrieve")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--kma-base-url",
        default="https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php",
        help="KMA typ01 endpoint base URL",
    )
    parser.add_argument(
        "--kma-station",
        default=os.getenv("KMA_STATION_ID", "108"),
        help="KMA station identifier (e.g. 108 for Seoul)",
    )
    parser.add_argument(
        "--kma-auth-key",
        default=None,
        help="KMA authKey override (falls back to KMA_AUTH_KEY env var)",
    )
    parser.add_argument(
        "--kma-timezone",
        default=os.getenv("KMA_TIMEZONE", "Asia/Seoul"),
        help="Timezone used to round timestamps for KMA queries",
    )
    parser.add_argument(
        "--kma-help-flag",
        type=int,
        default=0,
        help="Forwarded help flag for KMA responses (0 disables extra metadata)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = ProjectPaths.from_root(args.project_root)

    if args.mode == "sample":
        breakdown = _run_from_sample(paths)
    elif args.mode == "api":
        breakdown = _run_from_api(args)
    else:
        breakdown = _run_from_kma(args)

    _print_breakdown(breakdown)


def _print_breakdown(breakdown: ComfortScoreBreakdown) -> None:
    print(f"Comfort score: {breakdown.score:.1f} ({breakdown.label})")
    for name, value in breakdown.penalties.items():
        print(f"  penalty:{name} = {value:.1f}")


if __name__ == "__main__":
    main()
