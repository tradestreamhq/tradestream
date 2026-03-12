"""Tests for the Position Management service endpoints."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.position_management.postgres_client import PostgresClient
from services.position_management.service import create_app


@pytest.fixture
def pg_client():
    client = MagicMock(spec=PostgresClient)
    client.get_positions = AsyncMock(return_value=[])
    client.get_position = AsyncMock(return_value=None)
    client.open_position = AsyncMock()
    client.close_position = AsyncMock()
    client.update_market_price = AsyncMock()
    client.get_position_summary = AsyncMock(return_value=[])
    return client


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    loop.close()


@pytest.fixture
def app(pg_client, event_loop):
    flask_app = create_app(
        pg_client=pg_client,
        market_mcp_url="http://market-mcp:8080",
        event_loop=event_loop,
    )
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


SAMPLE_POSITION = {
    "id": "pos-1",
    "symbol": "BTC-USD",
    "side": "LONG",
    "quantity": 0.1,
    "filled_quantity": 0.1,
    "entry_price": 40000.0,
    "current_price": 42000.0,
    "unrealized_pnl": 200.0,
    "realized_pnl": 0.0,
    "status": "FILLED",
    "strategy_name": "MACD_CROSSOVER",
    "asset_class": "Crypto",
    "signal_id": None,
    "stop_loss": 38000.0,
    "take_profit": 45000.0,
    "opened_at": "2026-03-10T00:00:00",
    "updated_at": "2026-03-10T01:00:00",
    "closed_at": None,
    "exit_price": None,
}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "position-management"


class TestListPositions:
    def test_list_empty(self, client, pg_client):
        resp = client.get("/positions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["positions"] == []
        assert data["count"] == 0

    def test_list_with_positions(self, client, pg_client):
        pg_client.get_positions.return_value = [SAMPLE_POSITION]

        resp = client.get("/positions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["positions"][0]["symbol"] == "BTC-USD"

    def test_list_with_filters(self, client, pg_client):
        pg_client.get_positions.return_value = [SAMPLE_POSITION]

        resp = client.get("/positions?symbol=BTC-USD&strategy=MACD_CROSSOVER&status=FILLED")
        assert resp.status_code == 200
        pg_client.get_positions.assert_called_with(
            symbol="BTC-USD",
            strategy_name="MACD_CROSSOVER",
            status="FILLED",
            asset_class=None,
            limit=100,
        )

    def test_list_with_limit(self, client, pg_client):
        resp = client.get("/positions?limit=5")
        assert resp.status_code == 200
        pg_client.get_positions.assert_called_with(
            symbol=None,
            strategy_name=None,
            status=None,
            asset_class=None,
            limit=5,
        )


class TestGetPosition:
    def test_get_existing(self, client, pg_client):
        pg_client.get_position.return_value = SAMPLE_POSITION

        resp = client.get("/positions/pos-1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "pos-1"
        assert data["symbol"] == "BTC-USD"

    def test_get_not_found(self, client, pg_client):
        resp = client.get("/positions/nonexistent")
        assert resp.status_code == 404


class TestOpenPosition:
    def test_open_valid(self, client, pg_client):
        pg_client.open_position.return_value = {
            "id": "pos-new",
            "symbol": "ETH-USD",
            "side": "LONG",
            "quantity": 1.0,
            "filled_quantity": 1.0,
            "entry_price": 2000.0,
            "current_price": 2000.0,
            "status": "FILLED",
            "strategy_name": "SMA_RSI",
            "asset_class": "Crypto",
            "opened_at": "2026-03-10T00:00:00",
            "updated_at": "2026-03-10T00:00:00",
        }

        resp = client.post(
            "/positions",
            json={
                "symbol": "ETH-USD",
                "side": "LONG",
                "quantity": 1.0,
                "entry_price": 2000.0,
                "strategy_name": "SMA_RSI",
                "stop_loss": 1800.0,
                "take_profit": 2500.0,
            },
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == "pos-new"
        assert data["asset_class"] == "Crypto"

    def test_open_missing_fields(self, client):
        resp = client.post(
            "/positions",
            json={"symbol": "BTC-USD"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_open_invalid_side(self, client):
        resp = client.post(
            "/positions",
            json={
                "symbol": "BTC-USD",
                "side": "INVALID",
                "quantity": 1.0,
                "entry_price": 40000.0,
            },
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "LONG or SHORT" in resp.get_json()["error"]

    def test_open_no_body(self, client):
        resp = client.post("/positions")
        assert resp.status_code == 400


class TestClosePosition:
    def test_close_full(self, client, pg_client):
        pg_client.close_position.return_value = {
            "id": "pos-1",
            "symbol": "BTC-USD",
            "side": "LONG",
            "entry_price": 40000.0,
            "exit_price": 42000.0,
            "closed_quantity": 0.1,
            "remaining_quantity": 0.0,
            "realized_pnl": 200.0,
            "total_realized_pnl": 200.0,
            "status": "CLOSED",
        }

        resp = client.post(
            "/positions/pos-1/close",
            json={"exit_price": 42000.0},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "CLOSED"
        assert data["realized_pnl"] == 200.0

    def test_close_partial(self, client, pg_client):
        pg_client.close_position.return_value = {
            "id": "pos-1",
            "status": "PARTIALLY_CLOSED",
            "remaining_quantity": 0.05,
            "realized_pnl": 100.0,
        }

        resp = client.post(
            "/positions/pos-1/close",
            json={"exit_price": 42000.0, "quantity": 0.05},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "PARTIALLY_CLOSED"

    def test_close_not_found(self, client, pg_client):
        pg_client.close_position.return_value = None

        resp = client.post(
            "/positions/nonexistent/close",
            json={"exit_price": 42000.0},
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_close_missing_price(self, client):
        resp = client.post(
            "/positions/pos-1/close",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_close_no_body(self, client):
        resp = client.post("/positions/pos-1/close")
        assert resp.status_code == 400


class TestMarkPosition:
    def test_mark_success(self, client, pg_client):
        pg_client.get_position.return_value = {
            **SAMPLE_POSITION,
            "current_price": 43000.0,
            "unrealized_pnl": 300.0,
        }

        resp = client.post(
            "/positions/pos-1/mark",
            json={"current_price": 43000.0},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current_price"] == 43000.0

    def test_mark_not_found(self, client, pg_client):
        pg_client.get_position.return_value = None

        resp = client.post(
            "/positions/pos-1/mark",
            json={"current_price": 43000.0},
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_mark_missing_price(self, client):
        resp = client.post(
            "/positions/pos-1/mark",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestPositionSummary:
    def test_summary_by_strategy(self, client, pg_client):
        pg_client.get_position_summary.return_value = [
            {
                "group_key": "MACD_CROSSOVER",
                "num_open": 2,
                "num_closed": 1,
                "total_unrealized_pnl": 300.0,
                "total_realized_pnl": 100.0,
                "total_exposure": 5000.0,
            }
        ]

        resp = client.get("/positions/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["group_by"] == "strategy"
        assert len(data["summary"]) == 1
        assert data["summary"][0]["group_key"] == "MACD_CROSSOVER"

    def test_summary_by_asset_class(self, client, pg_client):
        pg_client.get_position_summary.return_value = [
            {
                "group_key": "Crypto",
                "num_open": 3,
                "num_closed": 0,
                "total_unrealized_pnl": 500.0,
                "total_realized_pnl": 0.0,
                "total_exposure": 10000.0,
            }
        ]

        resp = client.get("/positions/summary?group_by=asset_class")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["group_by"] == "asset_class"

    def test_summary_invalid_group(self, client):
        resp = client.get("/positions/summary?group_by=invalid")
        assert resp.status_code == 400
