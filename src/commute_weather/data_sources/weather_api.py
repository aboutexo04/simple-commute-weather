"""Light wrapper for fetching recent weather observations."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional

import requests

from ..config import WeatherAPIConfig, KMAAPIConfig


@dataclass(frozen=True)
class WeatherObservation:
    """Normalized snapshot of weather conditions for a single timestamp."""

    timestamp: dt.datetime
    temperature_c: float
    wind_speed_ms: float
    precipitation_mm: float
    relative_humidity: Optional[float] = None
    condition_code: Optional[str] = None
    precipitation_type: Optional[str] = None  # "rain", "snow", "none"


def _default_headers(api_key: Optional[str]) -> Mapping[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def fetch_recent_weather(
    cfg: WeatherAPIConfig,
    *,
    lookback_hours: int = 3,
    session: Optional[requests.Session] = None,
) -> List[WeatherObservation]:
    """Pulls the latest hourly observations for the configured location.

    This thin wrapper intentionally leaves response parsing flexible so it can
    adapt to any provider. Tweak the endpoint and parsing to match your API.
    """

    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")

    if not cfg.location:
        raise ValueError("WeatherAPIConfig.location must be provided")

    client = session or requests.Session()

    params = {
        "location": cfg.location,
        "hours": lookback_hours,
    }
    response = client.get(
        cfg.base_url.rstrip("/") + "/observations",  # provider-specific path
        params=params,
        headers=_default_headers(cfg.api_key),
        timeout=cfg.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    return normalize_observations(payload)


def fetch_kma_weather(
    cfg: KMAAPIConfig,
    *,
    lookback_hours: int = 3,
    session: Optional[requests.Session] = None,
) -> List[WeatherObservation]:
    """Fetch weather data from KMA API for the specified time range."""

    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")

    client = session or requests.Session()

    # Calculate time range for KMA API
    end_time = dt.datetime.now()
    start_time = end_time - dt.timedelta(hours=lookback_hours)

    # Format times for KMA API (YYYYMMDDHHMM)
    tm1 = start_time.strftime("%Y%m%d%H%M")
    tm2 = end_time.strftime("%Y%m%d%H%M")

    params = {
        "tm1": tm1,
        "tm2": tm2,
        "stn": cfg.station_id,
        "help": cfg.help_flag,
        "authKey": cfg.auth_key,
    }

    response = client.get(
        cfg.base_url,
        params=params,
        timeout=cfg.timeout_seconds,
    )
    response.raise_for_status()

    # KMA API returns text data, not JSON
    return normalize_kma_observations(response.text)


def normalize_kma_observations(response_text: str) -> List[WeatherObservation]:
    """Convert KMA API response to normalized observations."""

    observations: List[WeatherObservation] = []
    lines = response_text.strip().split('\n')

    # Debug: print first few lines to understand structure
    print("=== KMA API Response Debug ===")
    for i, line in enumerate(lines[:5]):
        if not line.startswith('#') and line.strip():
            parts = line.split()
            print(f"Line {i}: {len(parts)} fields")
            print(f"Fields: {parts}")
            break

    for line in lines:
        # Skip comment lines and empty lines
        if line.startswith('#') or not line.strip():
            continue

        parts = line.split()
        if len(parts) < 14:  # Need at least 14 fields based on format
            continue

        try:
            # KMA API format: YYYYMMDDHHMM STN WD WS ... TA TD HM ...
            # Parse date/time from YYYYMMDDHHMM format (12 chars)
            datetime_str = parts[0]  # YYYYMMDDHHMM

            if len(datetime_str) != 12:
                continue

            year = int(datetime_str[0:4])
            month = int(datetime_str[4:6])
            day = int(datetime_str[6:8])
            hour = int(datetime_str[8:10])
            minute = int(datetime_str[10:12])

            timestamp = dt.datetime(year, month, day, hour, minute)

            # Extract weather data based on KMA format
            # TA (Temperature) is around field 11, TD around 12, HM around 13
            temperature_c = float(parts[11]) if parts[11] not in ['-9.0', '-9', '-'] else None
            wind_speed_ms = float(parts[3]) if parts[3] not in ['-9.0', '-9', '-'] else 0.0
            relative_humidity = float(parts[13]) if parts[13] not in ['-9.0', '-9', '-'] else None

            # For precipitation, we might need to check multiple fields
            # RN fields are around positions 15-18, but let's check more broadly
            precipitation_mm = 0.0
            print(f"Checking precipitation in {len(parts)} fields:")

            # Check broader range for precipitation fields
            for rn_idx in range(10, min(len(parts), 25)):
                if parts[rn_idx] not in ['-9.0', '-9', '-', '']:
                    try:
                        precip_val = float(parts[rn_idx])
                        print(f"  Field {rn_idx}: {parts[rn_idx]} = {precip_val}")
                        if precip_val > 0:
                            precipitation_mm = precip_val
                            print(f"  → Found precipitation: {precip_val}mm at field {rn_idx}")
                            break
                    except ValueError:
                        pass

            print(f"Final precipitation: {precipitation_mm}mm")

            # Determine precipitation type based on temperature and amount
            precipitation_type = "none"
            if precipitation_mm > 0:
                if temperature_c and temperature_c <= 2.0:
                    precipitation_type = "snow"  # Snow when temp <= 2°C
                else:
                    precipitation_type = "rain"  # Rain when temp > 2°C

            # Add observation (temperature_c can be None, we'll handle it in scoring)
            observations.append(
                WeatherObservation(
                    timestamp=timestamp,
                    temperature_c=temperature_c or 0.0,  # Default to 0 if None
                    wind_speed_ms=wind_speed_ms,
                    precipitation_mm=precipitation_mm,
                    relative_humidity=relative_humidity,
                    condition_code=None,
                    precipitation_type=precipitation_type,
                )
            )

        except (ValueError, IndexError) as exc:
            continue  # Skip malformed lines

    return observations


def normalize_observations(payload: Mapping[str, object]) -> List[WeatherObservation]:
    """Convert provider payload into normalized observations.

    Replace the keys in this function so they match the upstream API shape.
    """

    observations: List[WeatherObservation] = []
    raw_entries: Iterable[Mapping[str, object]] = payload.get("observations", [])  # type: ignore[arg-type]

    for entry in raw_entries:
        try:
            observations.append(
                WeatherObservation(
                    timestamp=dt.datetime.fromisoformat(str(entry["timestamp"])),
                    temperature_c=float(entry["temperature_c"]),
                    wind_speed_ms=float(entry["wind_speed_ms"]),
                    precipitation_mm=float(entry.get("precipitation_mm", 0.0) or 0.0),
                    relative_humidity=float(entry.get("relative_humidity")) if entry.get("relative_humidity") is not None else None,
                    condition_code=str(entry.get("condition_code")) if entry.get("condition_code") is not None else None,
                    precipitation_type=str(entry.get("precipitation_type", "none")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed weather observation: {entry}") from exc

    return observations
