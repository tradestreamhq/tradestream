"""Tests for market hours service."""

from datetime import date, datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from services.market_hours.app import create_app
from services.market_hours.calendar import get_holiday, get_holidays, is_half_day
from services.market_hours.models import MarketPhase
from services.market_hours.schedule import get_current_phase, is_market_open


# --- Calendar tests ---


class TestCalendar:
    def test_get_holiday_exists(self):
        h = get_holiday(date(2026, 12, 25))
        assert h is not None
        assert h.name == "Christmas Day"
        assert not h.half_day

    def test_get_holiday_half_day(self):
        h = get_holiday(date(2026, 11, 27))
        assert h is not None
        assert h.half_day

    def test_get_holiday_none(self):
        assert get_holiday(date(2026, 3, 15)) is None

    def test_is_half_day(self):
        assert is_half_day(date(2026, 7, 3))
        assert not is_half_day(date(2026, 7, 4))
        assert not is_half_day(date(2026, 3, 15))

    def test_get_holidays_2026(self):
        holidays = get_holidays(2026)
        assert len(holidays) >= 10
        assert holidays[0].date.year == 2026

    def test_get_holidays_2027(self):
        holidays = get_holidays(2027)
        assert len(holidays) >= 8

    def test_get_holidays_no_data(self):
        assert get_holidays(2020) == []


# --- Schedule / phase detection tests ---


def _utc(year, month, day, hour, minute=0):
    """Create a UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("UTC"))


class TestSchedule:
    def test_nyse_regular_hours(self):
        # 2026-03-12 is a Thursday. 10:30 ET = 14:30 UTC (EST+5 in March before DST)
        # March 8 2026 is DST, so EDT (UTC-4). 10:30 ET = 14:30 UTC
        now = _utc(2026, 3, 12, 14, 30)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.REGULAR
        assert status.is_open

    def test_nyse_pre_market(self):
        # 5:00 ET = 9:00 UTC (EDT)
        now = _utc(2026, 3, 12, 9, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.PRE_MARKET
        assert not status.is_open

    def test_nyse_post_market(self):
        # 17:00 ET = 21:00 UTC (EDT)
        now = _utc(2026, 3, 12, 21, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.POST_MARKET
        assert not status.is_open

    def test_nyse_closed_night(self):
        # 22:00 ET = 02:00 UTC next day (EDT)
        now = _utc(2026, 3, 13, 2, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.CLOSED

    def test_nyse_weekend(self):
        # 2026-03-14 is Saturday
        now = _utc(2026, 3, 14, 14, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.CLOSED
        assert not status.is_open

    def test_nyse_holiday(self):
        # Christmas 2026
        now = _utc(2026, 12, 25, 14, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.CLOSED
        assert status.is_holiday
        assert status.holiday_name == "Christmas Day"

    def test_nyse_half_day_open(self):
        # Day after Thanksgiving 2026-11-27, 10:30 ET = 15:30 UTC (EST, UTC-5)
        now = _utc(2026, 11, 27, 15, 30)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.REGULAR
        assert status.is_open
        assert status.is_holiday

    def test_nyse_half_day_closed_afternoon(self):
        # 2026-11-27, 14:00 ET = 19:00 UTC (EST). Half day closes at 13:00 ET.
        now = _utc(2026, 11, 27, 19, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.CLOSED
        assert not status.is_open

    def test_nasdaq_same_as_nyse(self):
        now = _utc(2026, 3, 12, 14, 30)
        status = get_current_phase("NASDAQ", now)
        assert status.phase == MarketPhase.REGULAR

    def test_crypto_always_open(self):
        now = _utc(2026, 12, 25, 3, 0)
        status = get_current_phase("CRYPTO", now)
        assert status.phase == MarketPhase.REGULAR
        assert status.is_open

    def test_crypto_weekend_open(self):
        now = _utc(2026, 3, 14, 12, 0)  # Saturday
        status = get_current_phase("CRYPTO", now)
        assert status.is_open

    def test_cme_saturday_closed(self):
        # Saturday
        now = _utc(2026, 3, 14, 12, 0)
        status = get_current_phase("CME", now)
        assert status.phase == MarketPhase.CLOSED

    def test_cme_sunday_evening_open(self):
        # Sunday 18:00 CT = Monday 00:00 UTC. CT is UTC-6 (CST) in March before DST.
        # March 8 is DST in 2026, so CDT (UTC-5). Sunday 18:00 CDT = 23:00 UTC.
        now = _utc(2026, 3, 15, 23, 0)  # Sunday 18:00 CDT
        status = get_current_phase("CME", now)
        assert status.phase == MarketPhase.REGULAR

    def test_unknown_exchange(self):
        with pytest.raises(ValueError, match="Unknown exchange"):
            get_current_phase("FAKE")

    def test_case_insensitive(self):
        status = get_current_phase("nyse", _utc(2026, 3, 12, 14, 30))
        assert status.exchange == "NYSE"

    def test_is_market_open_helper(self):
        assert is_market_open("CRYPTO")
        # Weekend
        assert not is_market_open("NYSE", _utc(2026, 3, 14, 14, 0))

    def test_timezone_boundary_edt(self):
        # Exactly at market open: 9:30 ET (EDT, UTC-4) = 13:30 UTC
        now = _utc(2026, 3, 12, 13, 30)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.REGULAR

    def test_timezone_boundary_close(self):
        # Exactly at market close: 16:00 ET (EDT, UTC-4) = 20:00 UTC
        now = _utc(2026, 3, 12, 20, 0)
        status = get_current_phase("NYSE", now)
        assert status.phase == MarketPhase.POST_MARKET


# --- API endpoint tests ---


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestAPI:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_list_exchanges(self, client):
        resp = client.get("/exchanges")
        assert resp.status_code == 200
        data = resp.json()["data"]
        codes = [e["exchange"] for e in data]
        assert "NYSE" in codes
        assert "CRYPTO" in codes

    def test_get_market_hours(self, client):
        resp = client.get("/CRYPTO")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["is_open"] is True
        assert body["data"]["attributes"]["phase"] == "regular"

    def test_get_market_hours_not_found(self, client):
        resp = client.get("/FAKE")
        assert resp.status_code == 404

    def test_get_market_hours_case_insensitive(self, client):
        resp = client.get("/crypto")
        assert resp.status_code == 200

    def test_holidays_endpoint(self, client):
        resp = client.get("/NYSE/holidays?year=2026")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] >= 10

    def test_holidays_crypto_empty(self, client):
        resp = client.get("/CRYPTO/holidays")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_holidays_unknown_exchange(self, client):
        resp = client.get("/FAKE/holidays")
        assert resp.status_code == 404
