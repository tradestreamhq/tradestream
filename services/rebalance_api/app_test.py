"""Tests for the Rebalance REST API."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.rebalance_api.app import (
    compute_drift,
    create_app,
    generate_orders,
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


# --- Unit tests for pure functions ---


class TestComputeDrift:
    def test_no_drift_when_on_target(self):
        positions = [
            {"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 60000.0},
            {"symbol": "ETH/USD", "quantity": 10.0, "avg_entry_price": 4000.0},
        ]
        allocations = [
            {"symbol": "BTC/USD", "target_weight": 0.6, "rebalance_threshold": 0.05},
            {"symbol": "ETH/USD", "target_weight": 0.4, "rebalance_threshold": 0.05},
        ]
        total_equity = 100000.0

        result = compute_drift(positions, allocations, total_equity)

        assert len(result) == 2
        btc = next(d for d in result if d["symbol"] == "BTC/USD")
        assert btc["current_weight"] == 0.6
        assert btc["drift"] == 0.0
        assert btc["needs_rebalance"] is False

    def test_drift_exceeds_threshold(self):
        positions = [
            {"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 70000.0},
            {"symbol": "ETH/USD", "quantity": 10.0, "avg_entry_price": 3000.0},
        ]
        allocations = [
            {"symbol": "BTC/USD", "target_weight": 0.5, "rebalance_threshold": 0.05},
            {"symbol": "ETH/USD", "target_weight": 0.5, "rebalance_threshold": 0.05},
        ]
        total_equity = 100000.0

        result = compute_drift(positions, allocations, total_equity)

        btc = next(d for d in result if d["symbol"] == "BTC/USD")
        assert btc["current_weight"] == 0.7
        assert btc["drift"] == 0.2
        assert btc["needs_rebalance"] is True

        eth = next(d for d in result if d["symbol"] == "ETH/USD")
        assert eth["current_weight"] == 0.3
        assert eth["drift"] == -0.2
        assert eth["needs_rebalance"] is True

    def test_zero_equity(self):
        allocations = [
            {"symbol": "BTC/USD", "target_weight": 0.5, "rebalance_threshold": 0.05},
        ]
        result = compute_drift([], allocations, 0.0)
        assert len(result) == 1
        assert result[0]["current_weight"] == 0.0
        assert result[0]["needs_rebalance"] is True

    def test_missing_position(self):
        """Asset in allocations but not in portfolio."""
        positions = [
            {"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 50000.0},
        ]
        allocations = [
            {"symbol": "BTC/USD", "target_weight": 0.5, "rebalance_threshold": 0.05},
            {"symbol": "ETH/USD", "target_weight": 0.5, "rebalance_threshold": 0.05},
        ]
        total_equity = 50000.0

        result = compute_drift(positions, allocations, total_equity)

        eth = next(d for d in result if d["symbol"] == "ETH/USD")
        assert eth["current_weight"] == 0.0
        assert eth["current_value"] == 0.0
        assert eth["needs_rebalance"] is True


class TestGenerateOrders:
    def test_threshold_generates_orders_for_drifted(self):
        drift_items = [
            {
                "symbol": "BTC/USD",
                "target_weight": 0.5,
                "current_weight": 0.7,
                "drift": 0.2,
                "drift_pct": 0.2,
                "needs_rebalance": True,
                "current_value": 70000.0,
                "target_value": 50000.0,
            },
            {
                "symbol": "ETH/USD",
                "target_weight": 0.5,
                "current_weight": 0.3,
                "drift": -0.2,
                "drift_pct": 0.2,
                "needs_rebalance": True,
                "current_value": 30000.0,
                "target_value": 50000.0,
            },
        ]
        prices = {"BTC/USD": 70000.0, "ETH/USD": 3000.0}

        orders = generate_orders(drift_items, 100000.0, "THRESHOLD", prices)

        assert len(orders) == 2
        btc_order = next(o for o in orders if o["symbol"] == "BTC/USD")
        assert btc_order["side"] == "SELL"
        assert btc_order["quantity"] > 0
        assert btc_order["estimated_cost"] > 0

        eth_order = next(o for o in orders if o["symbol"] == "ETH/USD")
        assert eth_order["side"] == "BUY"

    def test_threshold_skips_under_threshold(self):
        drift_items = [
            {
                "symbol": "BTC/USD",
                "target_weight": 0.5,
                "current_weight": 0.51,
                "drift": 0.01,
                "drift_pct": 0.01,
                "needs_rebalance": False,
                "current_value": 51000.0,
                "target_value": 50000.0,
            },
        ]
        prices = {"BTC/USD": 50000.0}
        orders = generate_orders(drift_items, 100000.0, "THRESHOLD", prices)
        assert len(orders) == 0

    def test_calendar_generates_for_all_drifted(self):
        drift_items = [
            {
                "symbol": "BTC/USD",
                "target_weight": 0.5,
                "current_weight": 0.52,
                "drift": 0.02,
                "drift_pct": 0.02,
                "needs_rebalance": False,
                "current_value": 52000.0,
                "target_value": 50000.0,
            },
        ]
        prices = {"BTC/USD": 52000.0}
        orders = generate_orders(drift_items, 100000.0, "CALENDAR", prices)
        assert len(orders) == 1
        assert orders[0]["side"] == "SELL"

    def test_no_orders_when_no_price(self):
        drift_items = [
            {
                "symbol": "NEW/USD",
                "target_weight": 0.5,
                "current_weight": 0.0,
                "drift": -0.5,
                "drift_pct": 0.5,
                "needs_rebalance": True,
                "current_value": 0.0,
                "target_value": 50000.0,
            },
        ]
        orders = generate_orders(drift_items, 100000.0, "THRESHOLD", {})
        assert len(orders) == 0

    def test_estimated_cost_calculation(self):
        drift_items = [
            {
                "symbol": "BTC/USD",
                "target_weight": 0.5,
                "current_weight": 0.7,
                "drift": 0.2,
                "drift_pct": 0.2,
                "needs_rebalance": True,
                "current_value": 70000.0,
                "target_value": 50000.0,
            },
        ]
        prices = {"BTC/USD": 70000.0}
        orders = generate_orders(drift_items, 100000.0, "THRESHOLD", prices)
        # Trade value = 20000, cost = 20000 * 10/10000 = 20.0
        assert orders[0]["estimated_cost"] == 20.0


# --- API endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestAllocations:
    def test_list_allocations(self, client):
        tc, conn = client
        alloc_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=alloc_id,
                symbol="BTC/USD",
                strategy=None,
                target_weight=Decimal("0.5"),
                min_weight=Decimal("0.3"),
                max_weight=Decimal("0.7"),
                rebalance_threshold=Decimal("0.05"),
                is_active=True,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        resp = tc.get("/allocations")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["symbol"] == "BTC/USD"

    def test_create_allocation(self, client):
        tc, conn = client
        alloc_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=alloc_id)

        resp = tc.post(
            "/allocations",
            json={
                "symbol": "BTC/USD",
                "target_weight": 0.5,
                "min_weight": 0.3,
                "max_weight": 0.7,
                "rebalance_threshold": 0.05,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["symbol"] == "BTC/USD"

    def test_create_allocation_invalid_weights(self, client):
        tc, conn = client
        resp = tc.post(
            "/allocations",
            json={
                "symbol": "BTC/USD",
                "target_weight": 0.9,
                "min_weight": 0.8,
                "max_weight": 0.5,
            },
        )
        assert resp.status_code == 422

    def test_delete_allocation(self, client):
        tc, conn = client
        alloc_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=alloc_id)

        resp = tc.delete(f"/allocations/{alloc_id}")
        assert resp.status_code == 200

    def test_delete_allocation_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/allocations/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestDrift:
    def test_get_drift(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # allocations
            [
                FakeRecord(
                    symbol="BTC/USD",
                    strategy=None,
                    target_weight=Decimal("0.6"),
                    min_weight=Decimal("0.4"),
                    max_weight=Decimal("0.8"),
                    rebalance_threshold=Decimal("0.05"),
                )
            ],
            # positions
            [
                FakeRecord(
                    symbol="BTC/USD",
                    quantity=Decimal("1.0"),
                    avg_entry_price=Decimal("60000.0"),
                )
            ],
        ]
        conn.fetchrow.return_value = FakeRecord(total_equity=Decimal("100000.0"))

        resp = tc.get("/drift")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "assets" in attrs
        assert attrs["total_equity"] == 100000.0


class TestCalculate:
    def test_calculate_threshold(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # allocations
            [
                FakeRecord(
                    symbol="BTC/USD",
                    strategy=None,
                    target_weight=Decimal("0.5"),
                    min_weight=Decimal("0.3"),
                    max_weight=Decimal("0.7"),
                    rebalance_threshold=Decimal("0.05"),
                ),
            ],
            # positions
            [
                FakeRecord(
                    symbol="BTC/USD",
                    quantity=Decimal("1.0"),
                    avg_entry_price=Decimal("70000.0"),
                ),
            ],
        ]
        conn.fetchrow.return_value = FakeRecord(total_equity=Decimal("100000.0"))
        conn.execute.return_value = None

        resp = tc.post(
            "/calculate",
            json={"method": "THRESHOLD", "total_equity": 100000.0},
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "orders" in attrs
        assert "event_id" in attrs
        assert attrs["total_estimated_cost"] >= 0

    def test_calculate_zero_equity(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], []]
        conn.fetchrow.return_value = FakeRecord(total_equity=Decimal("0"))

        resp = tc.post("/calculate", json={"method": "THRESHOLD"})
        assert resp.status_code == 422


class TestHistory:
    def test_get_history(self, client):
        tc, conn = client
        event_id = uuid.uuid4()
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            FakeRecord(
                id=event_id,
                method="THRESHOLD",
                status="PROPOSED",
                weights_before={"BTC/USD": 0.7},
                weights_after=None,
                proposed_orders=[
                    {"symbol": "BTC/USD", "side": "SELL", "quantity": 0.3}
                ],
                estimated_cost=Decimal("20.0"),
                triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                executed_at=None,
            )
        ]

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1

    def test_get_history_empty(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
