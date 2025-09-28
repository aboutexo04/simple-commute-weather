
"""Data access helpers for the KMA typ01 surface observation API."""

from __future__ import annotations

import datetime as dt
from typing import List, Mapping, Optional, Sequence

import requests
from zoneinfo import ZoneInfo

from ..config import KMAAPIConfig
from .weather_api import WeatherObservation

_TEMPERATURE_KEYS: Sequence[str] = ("ta", "temp", "temperature")
_WIND_SPEED_KEYS: Sequence[str] = ("ws", "wind", "wind_speed")
_PRECIP_KEYS: Sequence[str] = ("rn", "rn_1", "rn_2", "pr1", "precip", "precipitation")
_HUMIDITY_KEYS: Sequence[str] = ("hm", "rh", "reh", "humidity")
_SENTINEL_THRESHOLD = -900.0


def fetch_recent_weather_kma(
    cfg: KMAAPIConfig,
    *,
    lookback_hours: int = 3,
    session: Optional[requests.Session] = None,
) -> List[WeatherObservation]:
    """Fetch recent observations from KMA and normalize them."""

    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")

    if not cfg.auth_key:
        raise ValueError("KMAAPIConfig.auth_key must be provided")

    tz = ZoneInfo(cfg.timezone)
    now = dt.datetime.now(tz=tz)
    end_time = now.replace(minute=0, second=0, microsecond=0)
    if end_time > now:
        end_time -= dt.timedelta(hours=1)

    span_hours = max(1, lookback_hours)
    start_time = end_time - dt.timedelta(hours=span_hours - 1)

    params = {
        "tm1": _format_timestamp(start_time),
        "tm2": _format_timestamp(end_time),
        "stn": cfg.station_id,
        "help": cfg.help_flag,
        "authKey": cfg.auth_key,
    }

    client = session or requests.Session()
    response = client.get(cfg.base_url, params=params, timeout=cfg.timeout_seconds)
    response.raise_for_status()

    observations = _parse_typ01_response(
        response.text,
        start_time=start_time.replace(tzinfo=None),
        end_time=end_time.replace(tzinfo=None),
    )
    if not observations:
        raise ValueError("KMA API returned no parsable weather observations")

    return observations


def _format_timestamp(value: dt.datetime) -> str:
    return value.strftime("%Y%m%d%H%M")


def _parse_typ01_response(
    payload: str,
    *,
    start_time: dt.datetime,
    end_time: dt.datetime,
) -> List[WeatherObservation]:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    header = _extract_header(lines)

    data_lines = [line for line in lines if not line.startswith("#")]
    if not data_lines:
        return []

    first_tokens = data_lines[0].split()
    if header is None:
        has_header = _looks_like_header(first_tokens)
        if has_header:
            header = [token.lower() for token in first_tokens]
            row_iter = (line.split() for line in data_lines[1:])
        else:
            header = _fallback_header(len(first_tokens))
            row_iter = (line.split() for line in data_lines)
    else:
        row_iter = (line.split() for line in data_lines)

    observations: List[WeatherObservation] = []
    for tokens in row_iter:
        row = _zip_fields(header, tokens)
        timestamp = _parse_timestamp(row.get("tm"))
        if timestamp is None:
            continue
        if timestamp < start_time or timestamp > end_time:
            continue

        temperature = _coerce_float_from_row(row, _TEMPERATURE_KEYS)
        wind_speed = _coerce_float_from_row(row, _WIND_SPEED_KEYS) or 0.0
        precipitation = _coerce_float_from_row(row, _PRECIP_KEYS)
        if precipitation is None or precipitation < 0:
            precipitation = 0.0
        humidity = _coerce_float_from_row(row, _HUMIDITY_KEYS)
        if humidity is not None and humidity < 0:
            humidity = None

        # Determine precipitation type based on temperature
        precipitation_type = "none"
        if precipitation > 0:
            if temperature is not None and temperature <= 2.0:
                precipitation_type = "snow"
            else:
                precipitation_type = "rain"

        observations.append(
            WeatherObservation(
                timestamp=timestamp,
                temperature_c=temperature if temperature is not None else 0.0,
                wind_speed_ms=wind_speed,
                precipitation_mm=precipitation,
                relative_humidity=humidity,
                precipitation_type=precipitation_type,
            )
        )

    observations.sort(key=lambda obs: obs.timestamp)
    return observations


def _looks_like_header(tokens: Sequence[str]) -> bool:
    lowered = {token.lower() for token in tokens}
    return any(name in lowered for name in ("tm", "ta", "ws", "rn", "hm", "reh"))


def _extract_header(lines: Sequence[str]) -> Optional[list[str]]:
    """Pull header tokens from the comment block if present."""

    for line in lines:
        if not line.startswith("#"):
            continue
        stripped = line.lstrip("#").strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if "YYMMDD" not in upper or "STN" not in upper:
            continue

        raw_tokens = stripped.split()
        return _normalize_header_tokens(raw_tokens)
    return None


_HEADER_ALIASES: Mapping[str, str] = {
    "yymmddhhmi": "tm",
    "tm": "tm",
    "stn": "stn",
    "ta": "ta",
    "hm": "hm",
    "rh": "hm",
    "reh": "hm",
    "ws": "ws",
    "rn": "rn",
}


def _normalize_header_tokens(raw_tokens: Sequence[str]) -> list[str]:
    counts: dict[str, int] = {}
    normalized: list[str] = []

    for token in raw_tokens:
        key = _HEADER_ALIASES.get(token.lower(), token.lower())
        if key in counts:
            suffix = counts[key]
            normalized.append(f"{key}_{suffix}")
            counts[key] = suffix + 1
        else:
            normalized.append(key)
            counts[key] = 1

    return normalized


def _fallback_header(width: int) -> List[str]:
    base = [
        "stn",
        "stnnm",
        "tm",
        "ta",
        "hm",
        "ws",
        "wd",
        "rn",
    ]
    if width <= len(base):
        return base[:width]
    base.extend(f"col{i}" for i in range(len(base), width))
    return base


def _zip_fields(header: Sequence[str], tokens: Sequence[str]) -> dict[str, str]:
    count = min(len(header), len(tokens))
    return {header[i]: tokens[i] for i in range(count)}


def _parse_timestamp(raw: Optional[str]) -> Optional[dt.datetime]:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y%m%d%H%M", "%Y%m%d%H"):
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _coerce_float_from_row(row: Mapping[str, str], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        result = _coerce_float(value)
        if result is not None:
            return result
    return None


def _coerce_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value or value in {"-", "."}:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed <= _SENTINEL_THRESHOLD:
        return None
    return parsed
