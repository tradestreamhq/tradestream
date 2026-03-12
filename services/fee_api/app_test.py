"""Tests for the Fee Calculator REST API."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.fee_api.app import (
    calculate_fee,
    calculate_flat_fee,
    calculate_maker_taker_fee,
    calculate_tiered_fee,
    create_app,
)


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# --- Pure fee calculation tests ---


class TestMakerTakerFee:
    def test_maker_fee(self):
        schedule = {"maker_rate": 0.001, "taker_rate": 0.002}
        amount, rate = calculate_maker_taker_fee(
            Decimal("1.0"), Decimal("50000"), True, schedule
        )
        assert amount == Decimal("50")
        assert rate == Decimal("0.001")

    def test_taker_fee(self):
        schedule = {"maker_rate": 0.001, "taker_rate": 0.002}
        amount, rate = calculate_maker_taker_fee(
            Decimal("1.0"), Decimal("50000"), False, schedule
        )
        assert amount == Decimal("100")
        assert rate == Decimal("0.002")

    def test_small_trade(self):
        schedule = {"maker_rate": 0.001, "taker_rate": 0.002}
        amount, rate = calculate_maker_taker_fee(
            Decimal("0.001"), Decimal("100"), False, schedule
        )
        assert amount == Decimal("0.0002")

    def test_zero_rate(self):
        schedule = {"maker_rate": 0, "taker_rate": 0.001}
        amount, rate = calculate_maker_taker_fee(
            Decimal("10"), Decimal("1000"), True, schedule
        )
        assert amount == Decimal("0")
        assert rate == Decimal("0")


class TestFlatFee:
    def test_flat_fee(self):
        schedule = {"flat_fee": 5.0}
        amount, rate = calculate_flat_fee(schedule)
        assert amount == Decimal("5.0")
        assert rate == Decimal("0")

    def test_flat_fee_small(self):
        schedule = {"flat_fee": 0.01}
        amount, rate = calculate_flat_fee(schedule)
        assert amount == Decimal("0.01")

    def test_flat_fee_zero(self):
        schedule = {"flat_fee": 0}
        amount, rate = calculate_flat_fee(schedule)
        assert amount == Decimal("0")


class TestTieredFee:
    def test_lowest_tier(self):
        schedule = {
            "tiers": [
                {"min_volume": 0, "max_volume": 100000, "rate": "0.002"},
                {"min_volume": 100000, "max_volume": 1000000, "rate": "0.001"},
                {"min_volume": 1000000, "max_volume": None, "rate": "0.0005"},
            ]
        }
        amount, rate = calculate_tiered_fee(
            Decimal("1"), Decimal("50000"), Decimal("0"), schedule
        )
        assert rate == Decimal("0.002")
        assert amount == Decimal("100")

    def test_middle_tier(self):
        schedule = {
            "tiers": [
                {"min_volume": 0, "max_volume": 100000, "rate": "0.002"},
                {"min_volume": 100000, "max_volume": 1000000, "rate": "0.001"},
                {"min_volume": 1000000, "max_volume": None, "rate": "0.0005"},
            ]
        }
        amount, rate = calculate_tiered_fee(
            Decimal("1"), Decimal("50000"), Decimal("500000"), schedule
        )
        assert rate == Decimal("0.001")
        assert amount == Decimal("50")

    def test_highest_tier(self):
        schedule = {
            "tiers": [
                {"min_volume": 0, "max_volume": 100000, "rate": "0.002"},
                {"min_volume": 100000, "max_volume": 1000000, "rate": "0.001"},
                {"min_volume": 1000000, "max_volume": None, "rate": "0.0005"},
            ]
        }
        amount, rate = calculate_tiered_fee(
            Decimal("1"), Decimal("50000"), Decimal("2000000"), schedule
        )
        assert rate == Decimal("0.0005")
        assert amount == Decimal("25")

    def test_tiers_as_json_string(self):
        schedule = {
            "tiers": json.dumps(
                [{"min_volume": 0, "max_volume": None, "rate": "0.001"}]
            )
        }
        amount, rate = calculate_tiered_fee(
            Decimal("10"), Decimal("100"), Decimal("0"), schedule
        )
        assert rate == Decimal("0.001")
        assert amount == Decimal("1")

    def test_exact_tier_boundary(self):
        schedule = {
            "tiers": [
                {"min_volume": 0, "max_volume": 100000, "rate": "0.002"},
                {"min_volume": 100000, "max_volume": None, "rate": "0.001"},
            ]
        }
        # Exactly at boundary (100000) should fall into second tier
        amount, rate = calculate_tiered_fee(
            Decimal("1"), Decimal("50000"), Decimal("100000"), schedule
        )
        assert rate == Decimal("0.001")


class TestCalculateFeeRouter:
    def test_routes_to_maker_taker(self):
        schedule = {
            "fee_model": "MAKER_TAKER",
            "maker_rate": 0.001,
            "taker_rate": 0.002,
        }
        amount, rate = calculate_fee(
            Decimal("1"), Decimal("50000"), True, schedule
        )
        assert amount == Decimal("50")

    def test_routes_to_flat(self):
        schedule = {"fee_model": "FLAT", "flat_fee": 10.0}
        amount, rate = calculate_fee(
            Decimal("1"), Decimal("50000"), True, schedule
        )
        assert amount == Decimal("10.0")

    def test_routes_to_tiered(self):
        schedule = {
            "fee_model": "TIERED",
            "tiers": [{"min_volume": 0, "max_volume": None, "rate": "0.001"}],
        }
        amount, rate = calculate_fee(
            Decimal("1"), Decimal("50000"), True, schedule, Decimal("0")
        )
        assert amount == Decimal("50")

    def test_unknown_model_raises(self):
        schedule = {"fee_model": "UNKNOWN"}
        with pytest.raises(ValueError, match="Unknown fee model"):
            calculate_fee(Decimal("1"), Decimal("100"), True, schedule)


# --- API endpoint tests ---


class TestHealthEndpoint:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestListFeeSchedules:
    def test_list_schedules(self, client):
        tc, conn = client
        schedule_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=schedule_id,
                exchange="binance",
                fee_model="MAKER_TAKER",
                maker_rate=Decimal("0.001"),
                taker_rate=Decimal("0.002"),
                flat_fee=None,
                tiers=None,
                fee_currency="USD",
                is_active=True,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/schedule")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["exchange"] == "binance"
        assert attrs["fee_model"] == "MAKER_TAKER"
        assert attrs["maker_rate"] == 0.001

    def test_list_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/schedule")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0


class TestCalculateEndpoint:
    def test_calculate_maker_taker(self, client):
        tc, conn = client
        fee_id = uuid.uuid4()
        # First call: fetchrow for schedule lookup
        # Second call: fetchrow for INSERT RETURNING
        conn.fetchrow.side_effect = [
            FakeRecord(
                id=uuid.uuid4(),
                exchange="binance",
                fee_model="MAKER_TAKER",
                maker_rate=Decimal("0.001"),
                taker_rate=Decimal("0.002"),
                flat_fee=None,
                tiers=None,
                fee_currency="USDT",
                is_active=True,
            ),
            FakeRecord(id=fee_id),
        ]

        resp = tc.post(
            "/calculate",
            json={
                "exchange": "binance",
                "side": "BUY",
                "size": 1.0,
                "price": 50000.0,
                "is_maker": False,
                "symbol": "BTC/USDT",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["fee_amount"] == 100.0
        assert attrs["fee_rate"] == 0.002
        assert attrs["fee_currency"] == "USDT"

    def test_calculate_flat_fee(self, client):
        tc, conn = client
        fee_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(
                id=uuid.uuid4(),
                exchange="kraken",
                fee_model="FLAT",
                maker_rate=None,
                taker_rate=None,
                flat_fee=Decimal("5.0"),
                tiers=None,
                fee_currency="USD",
                is_active=True,
            ),
            FakeRecord(id=fee_id),
        ]

        resp = tc.post(
            "/calculate",
            json={
                "exchange": "kraken",
                "side": "SELL",
                "size": 10.0,
                "price": 3000.0,
                "is_maker": True,
                "symbol": "ETH/USD",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["fee_amount"] == 5.0
        assert attrs["fee_model"] == "FLAT"

    def test_calculate_tiered(self, client):
        tc, conn = client
        fee_id = uuid.uuid4()
        tiers = [
            {"min_volume": 0, "max_volume": 100000, "rate": "0.002"},
            {"min_volume": 100000, "max_volume": None, "rate": "0.001"},
        ]
        conn.fetchrow.side_effect = [
            FakeRecord(
                id=uuid.uuid4(),
                exchange="coinbase",
                fee_model="TIERED",
                maker_rate=None,
                taker_rate=None,
                flat_fee=None,
                tiers=tiers,
                fee_currency="USD",
                is_active=True,
            ),
            # monthly volume query
            FakeRecord(volume=Decimal("50000")),
            # insert returning
            FakeRecord(id=fee_id),
        ]

        resp = tc.post(
            "/calculate",
            json={
                "exchange": "coinbase",
                "side": "BUY",
                "size": 1.0,
                "price": 50000.0,
                "is_maker": False,
                "symbol": "BTC/USD",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["fee_amount"] == 100.0
        assert attrs["fee_rate"] == 0.002

    def test_calculate_exchange_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            "/calculate",
            json={
                "exchange": "unknown_exchange",
                "side": "BUY",
                "size": 1.0,
                "price": 100.0,
                "is_maker": False,
                "symbol": "BTC/USD",
            },
        )
        assert resp.status_code == 404

    def test_calculate_invalid_side(self, client):
        tc, _ = client
        resp = tc.post(
            "/calculate",
            json={
                "exchange": "binance",
                "side": "INVALID",
                "size": 1.0,
                "price": 100.0,
                "is_maker": False,
            },
        )
        assert resp.status_code == 422

    def test_calculate_negative_size(self, client):
        tc, _ = client
        resp = tc.post(
            "/calculate",
            json={
                "exchange": "binance",
                "side": "BUY",
                "size": -1.0,
                "price": 100.0,
                "is_maker": False,
            },
        )
        assert resp.status_code == 422


class TestFeeSummary:
    def test_summary_current_month(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                exchange="binance",
                strategy_id=uuid.uuid4(),
                fee_model="MAKER_TAKER",
                fee_currency="USDT",
                trade_count=50,
                total_fees=Decimal("250.50"),
                avg_fee_rate=Decimal("0.0015"),
                total_volume=Decimal("500000"),
            )
        ]

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["breakdowns"]) == 1
        assert attrs["grand_total_fees"] == 250.50
        assert attrs["breakdowns"][0]["trade_count"] == 50

    def test_summary_with_strategy_filter(self, client):
        tc, conn = client
        sid = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                exchange="binance",
                strategy_id=sid,
                fee_model="MAKER_TAKER",
                fee_currency="USDT",
                trade_count=10,
                total_fees=Decimal("50.0"),
                avg_fee_rate=Decimal("0.001"),
                total_volume=Decimal("100000"),
            )
        ]

        resp = tc.get(f"/summary?strategy_id={sid}&month=2026-03")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["month"] == "2026-03"
        assert len(attrs["breakdowns"]) == 1

    def test_summary_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["breakdowns"]) == 0
        assert attrs["grand_total_fees"] == 0.0

    def test_summary_invalid_month_format(self, client):
        tc, _ = client
        resp = tc.get("/summary?month=invalid")
        assert resp.status_code == 422
