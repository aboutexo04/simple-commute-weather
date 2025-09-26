"""Configuration helpers for commute-weather project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class KMAAPIConfig:
    """Configuration bundle for the KMA typ01 surface observation API."""

    base_url: str
    auth_key: str
    station_id: str
    help_flag: int = 0
    timeout_seconds: float = 10.0
    timezone: str = "Asia/Seoul"


@dataclass(frozen=True)
class WeatherAPIConfig:
    """Encapsulates API access details for the upstream weather service."""

    base_url: str
    api_key: Optional[str] = None
    location: Optional[str] = None
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class ProjectPaths:
    """Centralizes the canonical project directories."""

    root: Path
    data_raw: Path
    data_interim: Path
    data_processed: Path

    @classmethod
    def from_root(cls, root: Path) -> "ProjectPaths":
        return cls(
            root=root,
            data_raw=root / "data" / "raw",
            data_interim=root / "data" / "interim",
            data_processed=root / "data" / "processed",
        )
