from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from commute_weather.config import KMAAPIConfig
from commute_weather.data_sources import kma_api


SAMPLE_PAYLOAD = (
    '# Sample KMA typ01 data\n'
    'stn stnNm tm ta hm ws wd rn\n'
    '108 서울 202301010800 18.2 55 3.2 200 0.0\n'
    '108 서울 202301010900 19.1 53 3.5 210 0.0\n'
    '108 서울 202301011000 20.0 51 3.8 220 0.5\n'
)


def test_parse_typ01_response_with_header() -> None:
    start = dt.datetime(2023, 1, 1, 8, 0)
    end = dt.datetime(2023, 1, 1, 10, 0)
    observations = kma_api._parse_typ01_response(  # type: ignore[attr-defined]
        SAMPLE_PAYLOAD,
        start_time=start,
        end_time=end,
    )

    assert len(observations) == 3
    assert observations[0].temperature_c == pytest.approx(18.2)
    assert observations[-1].precipitation_mm == pytest.approx(0.5)


class _DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _DummySession:
    def __init__(self, text: str) -> None:
        self._text = text
        self.request_args: dict[str, object] | None = None

    def get(self, url: str, params: dict[str, str], timeout: float) -> _DummyResponse:
        self.request_args = {"url": url, "params": params, "timeout": timeout}
        return _DummyResponse(self._text)


def test_fetch_recent_weather_kma(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = dt.datetime(2023, 1, 1, 10, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    class _FixedDateTime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(kma_api.dt, "datetime", _FixedDateTime)

    session = _DummySession(SAMPLE_PAYLOAD)
    cfg = KMAAPIConfig(
        base_url="https://example.com/kma",
        auth_key="secret",
        station_id="108",
        help_flag=0,
        timeout_seconds=5.0,
        timezone="Asia/Seoul",
    )

    observations = kma_api.fetch_recent_weather_kma(
        cfg,
        lookback_hours=3,
        session=session,
    )

    assert session.request_args is not None
    params = session.request_args["params"]
    assert params["tm1"] == "202301010800"
    assert params["tm2"] == "202301011000"
    assert len(observations) == 3
    assert observations[0].temperature_c == pytest.approx(18.2)
    assert observations[-1].precipitation_mm == pytest.approx(0.5)
