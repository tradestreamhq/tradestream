"""Tests for the Order Management REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.order_api.app import create_app


class FakeRecord(dict):
    """Dict subclass that mimics asyncpg.Record access patterns."""

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


ORDER_ID = str(uuid.uuid4())
NOW = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)


def _sample_order(**overrides):
    base = FakeRecord(
        id=uuid.UUID(ORDER_ID),
        symbol="BTC/USD",
        side="BUY",
        order_type="LIMIT",
        quantity=1.5,
        price=50000.0,
        stop_price=None,
        filled_quantity=0.0,
        avg_fill_price=None,
        status="PENDING",
        created_at=NOW,
        updated_at=NOW,
    )
    base.update(overrides)
    return base


def _sample_fill(**overrides):
    base = FakeRecord(
        id=uuid.uuid4(),
        order_id=uuid.UUID(ORDER_ID),
        quantity=0.5,
        price=50100.0,
        filled_at=NOW,
    )
    base.update(overrides)
    return base


# --- Health ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200

    def test_ready(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"


# --- Place Order ---


class TestPlaceOrder:
    def test_place_limit_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_order()

        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 1.5,
                "price": 50000.0,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "order"
        assert body["data"]["id"] == ORDER_ID
        assert body["data"]["attributes"]["symbol"] == "BTC/USD"
        assert body["data"]["attributes"]["status"] == "PENDING"

    def test_place_market_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_order(order_type="MARKET", price=None)

        resp = tc.post(
            "",
            json={
                "symbol": "ETH/USD",
                "side": "SELL",
                "order_type": "MARKET",
                "quantity": 10.0,
            },
        )
        assert resp.status_code == 201

    def test_place_stop_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_order(order_type="STOP", stop_price=48000.0)

        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "SELL",
                "order_type": "STOP",
                "quantity": 1.0,
                "stop_price": 48000.0,
            },
        )
        assert resp.status_code == 201

    def test_limit_order_without_price(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 1.0,
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_stop_order_without_stop_price(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "order_type": "STOP",
                "quantity": 1.0,
            },
        )
        assert resp.status_code == 422

    def test_place_order_invalid_quantity(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": -1.0,
            },
        )
        assert resp.status_code == 422

    def test_place_order_missing_symbol(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 1.0,
            },
        )
        assert resp.status_code == 422

    def test_place_order_invalid_side(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "INVALID",
                "order_type": "MARKET",
                "quantity": 1.0,
            },
        )
        assert resp.status_code == 422

    def test_place_order_db_error(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = Exception("DB connection lost")

        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 1.0,
            },
        )
        assert resp.status_code == 500


# --- List Orders ---


class TestListOrders:
    def test_list_orders_empty(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_list_orders_with_results(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_sample_order()]

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 1

    def test_list_orders_filter_by_status(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_sample_order()]

        resp = tc.get("", params={"status": "PENDING"})
        assert resp.status_code == 200

    def test_list_orders_filter_by_symbol(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_sample_order()]

        resp = tc.get("", params={"symbol": "BTC/USD"})
        assert resp.status_code == 200

    def test_list_orders_filter_by_side(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_sample_order(side="SELL")]

        resp = tc.get("", params={"side": "SELL"})
        assert resp.status_code == 200

    def test_list_orders_filter_by_date_range(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_sample_order()]

        resp = tc.get(
            "",
            params={
                "start_date": "2026-03-01T00:00:00Z",
                "end_date": "2026-03-31T23:59:59Z",
            },
        )
        assert resp.status_code == 200

    def test_list_orders_with_pagination(self, client):
        tc, conn = client
        conn.fetchval.return_value = 100
        conn.fetch.return_value = [_sample_order()]

        resp = tc.get("", params={"limit": 10, "offset": 20})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20
        assert body["meta"]["total"] == 100

    def test_list_orders_combined_filters(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_sample_order()]

        resp = tc.get(
            "",
            params={"status": "PENDING", "symbol": "BTC/USD", "side": "BUY"},
        )
        assert resp.status_code == 200

    def test_list_orders_db_error(self, client):
        tc, conn = client
        conn.fetchval.side_effect = Exception("DB error")

        resp = tc.get("")
        assert resp.status_code == 500


# --- Get Order Detail ---


class TestGetOrder:
    def test_get_order_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_order()
        conn.fetch.return_value = [_sample_fill()]

        resp = tc.get(f"/{ORDER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == ORDER_ID
        assert body["data"]["type"] == "order"
        assert "fills" in body["data"]["attributes"]
        assert len(body["data"]["attributes"]["fills"]) == 1

    def test_get_order_no_fills(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_order()
        conn.fetch.return_value = []

        resp = tc.get(f"/{ORDER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["fills"] == []

    def test_get_order_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{ORDER_ID}")
        assert resp.status_code == 404

    def test_get_order_with_partial_fill(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_order(
            status="PARTIAL_FILL", filled_quantity=0.5, avg_fill_price=50100.0
        )
        conn.fetch.return_value = [_sample_fill()]

        resp = tc.get(f"/{ORDER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "PARTIAL_FILL"
        assert attrs["filled_quantity"] == 0.5

    def test_get_order_db_error(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = Exception("DB error")

        resp = tc.get(f"/{ORDER_ID}")
        assert resp.status_code == 500


# --- Cancel Order ---


class TestCancelOrder:
    def test_cancel_pending_order(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.UUID(ORDER_ID), status="PENDING"),
            _sample_order(status="CANCELLED"),
        ]

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "CANCELLED"

    def test_cancel_open_order(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.UUID(ORDER_ID), status="OPEN"),
            _sample_order(status="CANCELLED"),
        ]

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 200

    def test_cancel_partial_fill_order(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.UUID(ORDER_ID), status="PARTIAL_FILL"),
            _sample_order(status="CANCELLED", filled_quantity=0.5),
        ]

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 200

    def test_cancel_filled_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.UUID(ORDER_ID), status="FILLED"
        )

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "ORDER_NOT_CANCELLABLE"

    def test_cancel_already_cancelled(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.UUID(ORDER_ID), status="CANCELLED"
        )

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 409

    def test_cancel_expired_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.UUID(ORDER_ID), status="EXPIRED"
        )

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 409

    def test_cancel_order_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 404

    def test_cancel_order_db_error(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = Exception("DB error")

        resp = tc.delete(f"/{ORDER_ID}")
        assert resp.status_code == 500


# --- Modify Order ---


class TestModifyOrder:
    def test_modify_price(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.UUID(ORDER_ID), status="PENDING", order_type="LIMIT"),
            _sample_order(price=51000.0),
        ]

        resp = tc.put(f"/{ORDER_ID}", json={"price": 51000.0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["price"] == 51000.0

    def test_modify_quantity(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.UUID(ORDER_ID), status="OPEN", order_type="LIMIT"),
            _sample_order(quantity=2.0),
        ]

        resp = tc.put(f"/{ORDER_ID}", json={"quantity": 2.0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["quantity"] == 2.0

    def test_modify_both_price_and_quantity(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.UUID(ORDER_ID), status="PENDING", order_type="LIMIT"),
            _sample_order(price=52000.0, quantity=3.0),
        ]

        resp = tc.put(f"/{ORDER_ID}", json={"price": 52000.0, "quantity": 3.0})
        assert resp.status_code == 200

    def test_modify_no_fields(self, client):
        tc, conn = client
        resp = tc.put(f"/{ORDER_ID}", json={})
        assert resp.status_code == 422

    def test_modify_filled_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.UUID(ORDER_ID), status="FILLED", order_type="LIMIT"
        )

        resp = tc.put(f"/{ORDER_ID}", json={"price": 51000.0})
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "ORDER_NOT_MODIFIABLE"

    def test_modify_cancelled_order(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.UUID(ORDER_ID), status="CANCELLED", order_type="LIMIT"
        )

        resp = tc.put(f"/{ORDER_ID}", json={"price": 51000.0})
        assert resp.status_code == 409

    def test_modify_order_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.put(f"/{ORDER_ID}", json={"price": 51000.0})
        assert resp.status_code == 404

    def test_modify_order_db_error(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = Exception("DB error")

        resp = tc.put(f"/{ORDER_ID}", json={"price": 51000.0})
        assert resp.status_code == 500

    def test_modify_invalid_price(self, client):
        tc, conn = client
        resp = tc.put(f"/{ORDER_ID}", json={"price": -100.0})
        assert resp.status_code == 422

    def test_modify_invalid_quantity(self, client):
        tc, conn = client
        resp = tc.put(f"/{ORDER_ID}", json={"quantity": 0})
        assert resp.status_code == 422
