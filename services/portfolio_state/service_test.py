"""Tests for the Portfolio State Awareness service."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.portfolio_state.postgres_client import PostgresClient
from services.portfolio_state.service import create_app


@pytest.fixture
def pg_client():
    client = MagicMock(spec=PostgresClient)
    client.get_positions = AsyncMock()
    client.get_open_trades = AsyncMock()
    client.get_recent_closed_trades = AsyncMock()
    client.get_realized_pnl_today = AsyncMock()
    client.get_total_realized_pnl = AsyncMock()
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
        initial_capital=10000.0,
        event_loop=event_loop,
    )
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _setup_mock_data(pg_client, positions=None, trades=None, closed=None):
    """Helper to set up common mock return values."""
    pg_client.get_positions.return_value = positions or []
    pg_client.get_open_trades.return_value = trades or []
    pg_client.get_recent_closed_trades.return_value = closed or []
    pg_client.get_realized_pnl_today.return_value = 0.0
    pg_client.get_total_realized_pnl.return_value = 0.0


SAMPLE_POSITIONS = [
    {
        "symbol": "BTC-USD",
        "quantity": 0.05,
        "avg_entry_price": 42150.0,
        "unrealized_pnl": 0.0,
        "updated_at": "2026-03-10T00:00:00",
    },
    {
        "symbol": "ETH-USD",
        "quantity": 0.8,
        "avg_entry_price": 2280.0,
        "unrealized_pnl": 0.0,
        "updated_at": "2026-03-10T01:00:00",
    },
]

SAMPLE_TRADES = [
    {
        "trade_id": "t-1",
        "signal_id": "s-1",
        "symbol": "BTC-USD",
        "side": "BUY",
        "entry_price": 42150.0,
        "quantity": 0.05,
        "opened_at": "2026-03-10T00:00:00",
    },
    {
        "trade_id": "t-2",
        "signal_id": "s-2",
        "symbol": "ETH-USD",
        "side": "BUY",
        "entry_price": 2280.0,
        "quantity": 0.8,
        "opened_at": "2026-03-10T01:00:00",
    },
]

SAMPLE_CLOSED = [
    {
        "trade_id": "t-0",
        "symbol": "SOL-USD",
        "side": "BUY",
        "entry_price": 95.0,
        "exit_price": 98.5,
        "quantity": 5.0,
        "pnl": 17.5,
        "opened_at": "2026-03-09T00:00:00",
        "closed_at": "2026-03-10T05:00:00",
    },
]


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "portfolio-state"


class TestStateEndpoint:
    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_full_state(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client,
            positions=SAMPLE_POSITIONS,
            trades=SAMPLE_TRADES,
            closed=SAMPLE_CLOSED,
        )
        pg_client.get_realized_pnl_today.return_value = 17.5
        pg_client.get_total_realized_pnl.return_value = 17.5
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        resp = client.get("/portfolio/state")
        assert resp.status_code == 200
        data = resp.get_json()

        assert "balance" in data
        assert "positions" in data
        assert "risk_metrics" in data
        assert "recent_trades" in data
        assert "as_of" in data

        assert data["balance"]["total_equity"] > 0
        assert len(data["positions"]) == 2
        assert data["positions"][0]["symbol"] == "BTC-USD"
        assert data["positions"][0]["side"] == "LONG"
        assert data["risk_metrics"]["num_open_positions"] == 2

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_empty_portfolio(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["positions"] == []
        assert data["balance"]["total_equity"] == 10000.0
        assert data["risk_metrics"]["num_open_positions"] == 0


class TestContextEndpoint:
    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_context_string(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client,
            positions=SAMPLE_POSITIONS,
            trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        resp = client.get("/portfolio/context")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "context" in data
        context = data["context"]
        assert "CURRENT PORTFOLIO STATE" in context
        assert "BTC-USD" in context
        assert "Account:" in context
        assert "Risk Status:" in context


class TestPositionsEndpoint:
    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_positions(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client,
            positions=SAMPLE_POSITIONS,
            trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        resp = client.get("/portfolio/positions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2
        assert data["positions"][0]["symbol"] == "BTC-USD"
        assert data["positions"][0]["current_price"] == 43800.0

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_positions_empty(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/positions")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0


class TestRiskEndpoint:
    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_risk_metrics(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client,
            positions=SAMPLE_POSITIONS,
            trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        resp = client.get("/portfolio/risk")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "portfolio_heat" in data
        assert "max_position_pct" in data
        assert data["num_open_positions"] == 2
        assert "Crypto" in data["sector_exposure"]


class TestValidateEndpoint:
    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_valid_trade(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.post(
            "/portfolio/validate",
            json={
                "action": "BUY",
                "symbol": "BTC-USD",
                "quantity": 0.001,
                "price": 50000.0,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["errors"] == []

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_insufficient_buying_power(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.post(
            "/portfolio/validate",
            json={
                "action": "BUY",
                "symbol": "BTC-USD",
                "quantity": 1.0,
                "price": 50000.0,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False
        assert any("buying power" in e.lower() for e in data["errors"])

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_position_too_large(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.post(
            "/portfolio/validate",
            json={
                "action": "BUY",
                "symbol": "BTC-USD",
                "quantity": 0.1,
                "price": 50000.0,
                "max_position_pct": 0.02,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False
        assert any("too large" in e.lower() for e in data["errors"])

    def test_validate_missing_fields(self, client):
        resp = client.post(
            "/portfolio/validate",
            json={"action": "BUY"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_validate_no_body(self, client):
        resp = client.post("/portfolio/validate")
        assert resp.status_code == 400
