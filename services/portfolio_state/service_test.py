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


def _setup_mock_data(pg_client, positions=None, trades=None, closed=None,
                     realized_today=0.0, total_realized=0.0):
    """Helper to set up common mock return values."""
    pg_client.get_positions.return_value = positions or []
    pg_client.get_open_trades.return_value = trades or []
    pg_client.get_recent_closed_trades.return_value = closed or []
    pg_client.get_realized_pnl_today.return_value = realized_today
    pg_client.get_total_realized_pnl.return_value = total_realized


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
            realized_today=17.5,
            total_realized=17.5,
        )
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

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_includes_all_balance_fields(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        balance = data["balance"]
        for field in [
            "total_equity", "available_cash", "buying_power",
            "margin_used", "margin_available", "unrealized_pnl",
            "realized_pnl_today",
        ]:
            assert field in balance, f"Missing balance field: {field}"

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_includes_all_risk_fields(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        risk = data["risk_metrics"]
        for field in [
            "portfolio_heat", "max_position_pct", "max_position_symbol",
            "num_open_positions", "sector_exposure", "daily_drawdown",
        ]:
            assert field in risk, f"Missing risk field: {field}"

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_position_fields(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client, positions=SAMPLE_POSITIONS, trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        resp = client.get("/portfolio/state")
        pos = resp.get_json()["positions"][0]
        for field in [
            "symbol", "side", "quantity", "entry_price",
            "current_price", "unrealized_pnl", "unrealized_pnl_percent",
            "opened_at",
        ]:
            assert field in pos, f"Missing position field: {field}"

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_returns_recent_trades(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client, closed=SAMPLE_CLOSED,
        )
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        assert len(data["recent_trades"]) == 1
        assert data["recent_trades"][0]["symbol"] == "SOL-USD"

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_with_realized_pnl(self, mock_prices, client, pg_client):
        _setup_mock_data(
            pg_client, realized_today=100.0, total_realized=500.0,
        )
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        assert data["balance"]["total_equity"] == 10500.0  # 10000 + 500
        assert data["balance"]["realized_pnl_today"] == 100.0

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_state_db_error_returns_500(self, mock_prices, client, pg_client):
        pg_client.get_positions = AsyncMock(side_effect=RuntimeError("DB down"))
        _setup_mock_data(pg_client)
        # Override after _setup_mock_data
        pg_client.get_positions = AsyncMock(side_effect=RuntimeError("DB down"))

        resp = client.get("/portfolio/state")
        assert resp.status_code == 500
        assert "error" in resp.get_json()


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
        assert "as_of" in data
        context = data["context"]
        assert "CURRENT PORTFOLIO STATE" in context
        assert "BTC-USD" in context
        assert "Account:" in context
        assert "Risk Status:" in context

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_context_empty_portfolio(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/context")
        assert resp.status_code == 200
        context = resp.get_json()["context"]
        assert "No open positions" in context
        assert "No recent trades" in context

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_context_db_error_returns_500(self, mock_prices, client, pg_client):
        pg_client.get_positions = AsyncMock(side_effect=RuntimeError("DB down"))

        resp = client.get("/portfolio/context")
        assert resp.status_code == 500
        assert "error" in resp.get_json()


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
        data = resp.get_json()
        assert data["count"] == 0
        assert data["positions"] == []

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_positions_with_short(self, mock_prices, client, pg_client):
        short_positions = [
            {
                "symbol": "SOL-USD",
                "quantity": 5.0,
                "avg_entry_price": 100.0,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-10T00:00:00",
            }
        ]
        short_trades = [
            {
                "trade_id": "t-s1",
                "symbol": "SOL-USD",
                "side": "SELL",
                "entry_price": 100.0,
                "quantity": 5.0,
                "opened_at": "2026-03-10T00:00:00",
            }
        ]
        _setup_mock_data(pg_client, positions=short_positions, trades=short_trades)
        mock_prices.return_value = {"SOL-USD": 95.0}

        resp = client.get("/portfolio/positions")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["positions"][0]["side"] == "SHORT"
        assert data["positions"][0]["unrealized_pnl"] == 25.0

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_positions_db_error_returns_500(self, mock_prices, client, pg_client):
        pg_client.get_positions = AsyncMock(side_effect=RuntimeError("DB down"))

        resp = client.get("/portfolio/positions")
        assert resp.status_code == 500
        assert "error" in resp.get_json()


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
        assert "total_equity" in data
        assert "margin_used" in data
        assert data["num_open_positions"] == 2
        assert "Crypto" in data["sector_exposure"]

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_risk_empty_portfolio(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/risk")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["portfolio_heat"] == 0.0
        assert data["num_open_positions"] == 0
        assert data["total_equity"] == 10000.0

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_get_risk_db_error_returns_500(self, mock_prices, client, pg_client):
        pg_client.get_positions = AsyncMock(side_effect=RuntimeError("DB down"))

        resp = client.get("/portfolio/risk")
        assert resp.status_code == 500
        assert "error" in resp.get_json()


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

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_with_custom_heat_limit(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.post(
            "/portfolio/validate",
            json={
                "action": "BUY",
                "symbol": "BTC-USD",
                "quantity": 0.1,
                "price": 50000.0,
                "max_position_pct": 1.0,
                "max_portfolio_heat": 0.01,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False
        assert any("heat" in e.lower() for e in data["errors"])

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_sell_order(self, mock_prices, client, pg_client):
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.post(
            "/portfolio/validate",
            json={
                "action": "SELL",
                "symbol": "BTC-USD",
                "quantity": 1.0,
                "price": 50000.0,
                "max_position_pct": 1.0,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True

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

    def test_validate_missing_symbol(self, client):
        resp = client.post(
            "/portfolio/validate",
            json={"action": "BUY", "quantity": 1.0, "price": 100.0},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_validate_missing_quantity(self, client):
        resp = client.post(
            "/portfolio/validate",
            json={"action": "BUY", "symbol": "BTC-USD", "price": 100.0},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_validate_missing_price(self, client):
        resp = client.post(
            "/portfolio/validate",
            json={"action": "BUY", "symbol": "BTC-USD", "quantity": 1.0},
            content_type="application/json",
        )
        assert resp.status_code == 400

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_db_error_returns_500(self, mock_prices, client, pg_client):
        pg_client.get_positions = AsyncMock(side_effect=RuntimeError("DB down"))

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
        assert resp.status_code == 500
        assert "error" in resp.get_json()


class TestStateTransitions:
    """Integration tests for state transitions through the HTTP API."""

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_state_reflects_position_addition(self, mock_prices, client, pg_client):
        """State should reflect newly added positions."""
        # Start empty
        _setup_mock_data(pg_client)
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        assert len(data["positions"]) == 0
        assert data["balance"]["total_equity"] == 10000.0

        # Add a position
        _setup_mock_data(
            pg_client, positions=SAMPLE_POSITIONS[:1], trades=SAMPLE_TRADES[:1],
        )
        mock_prices.return_value = {"BTC-USD": 43800.0}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "BTC-USD"
        assert data["risk_metrics"]["num_open_positions"] == 1

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_state_reflects_position_removal(self, mock_prices, client, pg_client):
        """State should reflect positions being closed (removed)."""
        # Start with positions
        _setup_mock_data(
            pg_client, positions=SAMPLE_POSITIONS, trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        resp = client.get("/portfolio/state")
        assert len(resp.get_json()["positions"]) == 2

        # Close all positions (empty portfolio, realized PnL from closed trades)
        _setup_mock_data(
            pg_client, closed=SAMPLE_CLOSED, realized_today=17.5, total_realized=17.5,
        )
        mock_prices.return_value = {}

        resp = client.get("/portfolio/state")
        data = resp.get_json()
        assert len(data["positions"]) == 0
        assert data["balance"]["total_equity"] == 10017.5
        assert data["balance"]["realized_pnl_today"] == 17.5

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_state_reflects_price_changes(self, mock_prices, client, pg_client):
        """Same positions with different prices should produce different state."""
        _setup_mock_data(
            pg_client, positions=SAMPLE_POSITIONS[:1], trades=SAMPLE_TRADES[:1],
        )

        # Price up
        mock_prices.return_value = {"BTC-USD": 50000.0}
        resp = client.get("/portfolio/state")
        data_up = resp.get_json()

        # Price down
        mock_prices.return_value = {"BTC-USD": 30000.0}
        resp = client.get("/portfolio/state")
        data_down = resp.get_json()

        assert data_up["positions"][0]["unrealized_pnl"] > 0
        assert data_down["positions"][0]["unrealized_pnl"] < 0
        assert data_up["balance"]["total_equity"] > data_down["balance"]["total_equity"]

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_context_and_state_are_consistent(self, mock_prices, client, pg_client):
        """Context string should reflect the same data as the state endpoint."""
        _setup_mock_data(
            pg_client, positions=SAMPLE_POSITIONS, trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        state_resp = client.get("/portfolio/state")
        context_resp = client.get("/portfolio/context")

        state_data = state_resp.get_json()
        context = context_resp.get_json()["context"]

        # Context should mention the same symbols
        for pos in state_data["positions"]:
            assert pos["symbol"] in context

        # Context should contain portfolio heat
        heat = state_data["risk_metrics"]["portfolio_heat"]
        assert f"{heat:.1f}%" in context

    @patch("services.portfolio_state.service._fetch_current_prices")
    def test_validate_against_current_state(self, mock_prices, client, pg_client):
        """Validation should use the current portfolio state for checks."""
        # With positions using up margin, buying power is reduced
        _setup_mock_data(
            pg_client, positions=SAMPLE_POSITIONS, trades=SAMPLE_TRADES,
        )
        mock_prices.return_value = {"BTC-USD": 43800.0, "ETH-USD": 2250.0}

        # Get current state to know buying power
        state = client.get("/portfolio/state").get_json()
        buying_power = state["balance"]["buying_power"]

        # Try to buy more than available
        resp = client.post(
            "/portfolio/validate",
            json={
                "action": "BUY",
                "symbol": "SOL-USD",
                "quantity": 1000.0,
                "price": buying_power + 1,
                "max_position_pct": 1.0,
                "max_portfolio_heat": 1.0,
            },
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["valid"] is False
        assert any("buying power" in e.lower() for e in data["errors"])
