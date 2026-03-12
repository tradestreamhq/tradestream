"""End-to-end test for the full trading pipeline.

Verifies the complete flow:
  market data → signal generation → risk check → order execution
  → position tracking → P&L calculation

All external services (LLM, MCP servers, databases) are mocked so the test
exercises the real business logic across pipeline stages without requiring
live infrastructure.
"""

import asyncio
import json
import threading
from decimal import Decimal
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.paper_trading.postgres_client import (
    PostgresClient as PaperTradingPgClient,
)
from services.paper_trading.service import create_app as create_paper_trading_app
from services.portfolio_state.portfolio_state import (
    Position,
    build_portfolio_state,
    compute_balance,
    compute_positions,
    compute_risk_metrics,
    validate_decision,
)
from services.risk_adjusted_sizing.main import (
    PositionSize,
    RiskAdjustedSizer,
    RiskMetrics as SizingRiskMetrics,
)
from services.signal_generator_agent import agent


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SYMBOL = "BTC-USD"
ENTRY_PRICE = 50000.0
CURRENT_PRICE = 52000.0
QUANTITY = 0.1
SIGNAL_ID = "sig-e2e-001"


def _strategies():
    return [
        {
            "impl_id": "impl_1",
            "strategy_type": "momentum",
            "signal": "BUY",
            "confidence": 0.85,
            "score": 92,
        },
        {
            "impl_id": "impl_2",
            "strategy_type": "mean_reversion",
            "signal": "BUY",
            "confidence": 0.75,
            "score": 88,
        },
        {
            "impl_id": "impl_3",
            "strategy_type": "breakout",
            "signal": "BUY",
            "confidence": 0.70,
            "score": 85,
        },
    ]


def _market_summary():
    return {
        "symbol": SYMBOL,
        "price": ENTRY_PRICE,
        "volume_24h": 1_200_000,
        "change_24h": 3.2,
    }


def _candles(count=50):
    return [
        {
            "timestamp": f"2026-03-12T00:{i:02d}:00Z",
            "open": 49800 + i * 10,
            "high": 49850 + i * 10,
            "low": 49750 + i * 10,
            "close": 49820 + i * 10,
            "volume": 200 + i,
        }
        for i in range(count)
    ]


def _recent_signals_empty():
    return []


def _emit_result():
    return {"signal_id": SIGNAL_ID, "status": "emitted"}


# ---------------------------------------------------------------------------
# LLM mock helpers (same pattern as agent_integration_test.py)
# ---------------------------------------------------------------------------


def _make_mcp_response(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _mock_tool_call(call_id, name, arguments):
    tc = mock.Mock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _mock_assistant_with_tools(tool_calls):
    msg = mock.Mock()
    msg.tool_calls = tool_calls
    msg.content = None
    msg.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": tc.id,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
                "type": "function",
            }
            for tc in tool_calls
        ],
    }
    choice = mock.Mock()
    choice.finish_reason = "tool_calls"
    choice.message = msg
    resp = mock.Mock()
    resp.choices = [choice]
    return resp


def _mock_assistant_stop(content):
    msg = mock.Mock()
    msg.tool_calls = None
    msg.content = content if isinstance(content, str) else json.dumps(content)
    msg.model_dump.return_value = {"role": "assistant", "content": msg.content}
    choice = mock.Mock()
    choice.finish_reason = "stop"
    choice.message = msg
    resp = mock.Mock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def paper_pg_client():
    """Mock PostgresClient for paper trading."""
    client = MagicMock(spec=PaperTradingPgClient)
    client.execute_trade = AsyncMock()
    client.close_trade = AsyncMock()
    client.get_portfolio = AsyncMock()
    client.update_unrealized_pnl = AsyncMock()
    client.get_trades = AsyncMock()
    client.get_pnl_summary = AsyncMock()
    client.log_decision = AsyncMock()
    return client


@pytest.fixture
def event_loop_fixture():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    loop.close()


@pytest.fixture
def paper_app(paper_pg_client, event_loop_fixture):
    flask_app = create_paper_trading_app(
        pg_client=paper_pg_client,
        market_mcp_url="http://market-mcp:8080",
        signal_mcp_url="http://signal-mcp:8080",
        event_loop=event_loop_fixture,
    )
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def paper_client(paper_app):
    return paper_app.test_client()


# ---------------------------------------------------------------------------
# Stage 1: Signal Generation (market data → strategy analysis → signal)
# ---------------------------------------------------------------------------


class TestStage1SignalGeneration:
    """Market data flows through the signal generator agent to produce a BUY signal."""

    @patch("requests.post")
    @patch("services.signal_generator_agent.agent.OpenAI")
    def test_market_data_produces_buy_signal(self, mock_openai_cls, mock_http):
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Step 1: get_top_strategies
        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc1", "get_top_strategies", {"symbol": SYMBOL, "limit": 10}
                )
            ]
        )
        # Step 2: get_market_summary + get_candles
        resp2 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc2a", "get_market_summary", {"symbol": SYMBOL}),
                _mock_tool_call("tc2b", "get_candles", {"symbol": SYMBOL, "limit": 50}),
            ]
        )
        # Step 3: get_recent_signals
        resp3 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc3", "get_recent_signals", {"symbol": SYMBOL, "limit": 5}
                )
            ]
        )
        # Step 4: emit_signal
        signal_payload = {
            "symbol": SYMBOL,
            "action": "BUY",
            "confidence": 0.82,
            "reasoning": "Strong bullish consensus across momentum and mean_reversion strategies",
            "strategy_breakdown": [
                {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.85},
                {
                    "strategy_type": "mean_reversion",
                    "signal": "BUY",
                    "confidence": 0.75,
                },
                {"strategy_type": "breakout", "signal": "BUY", "confidence": 0.70},
            ],
        }
        resp4 = _mock_assistant_with_tools(
            [_mock_tool_call("tc4", "emit_signal", signal_payload)]
        )
        # Step 5: final
        resp5 = _mock_assistant_stop(signal_payload)

        mock_client.chat.completions.create.side_effect = [
            resp1,
            resp2,
            resp3,
            resp4,
            resp5,
        ]

        mcp_data = {
            "get_top_strategies": _strategies(),
            "get_market_summary": _market_summary(),
            "get_candles": _candles(),
            "get_recent_signals": _recent_signals_empty(),
            "emit_signal": _emit_result(),
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = _make_mcp_response(mcp_data[tool_name])
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol(SYMBOL, "test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "BUY"
        assert parsed["confidence"] >= 0.7
        assert len(parsed["strategy_breakdown"]) == 3

        # Return parsed signal for downstream stages
        return parsed


# ---------------------------------------------------------------------------
# Stage 2: Risk Check (signal → risk-adjusted sizing → approval/rejection)
# ---------------------------------------------------------------------------


class TestStage2RiskCheck:
    """Risk-adjusted sizing evaluates whether the signal should be traded."""

    def _make_sizer(self):
        sizer = RiskAdjustedSizer.__new__(RiskAdjustedSizer)
        sizer.db_config = {}
        sizer.pool = None
        return sizer

    def test_risk_sizing_approves_good_strategy(self):
        """A high-confidence strategy with reasonable metrics gets a positive position size."""
        sizer = self._make_sizer()
        metrics = [
            SizingRiskMetrics(
                strategy_id="strat-1",
                symbol=SYMBOL,
                strategy_type="momentum",
                current_score=0.82,
                volatility=0.15,
                sharpe_ratio=1.5,
                max_drawdown=0.05,
                win_rate=0.65,
                profit_factor=1.8,
            )
        ]
        positions = sizer.calculate_position_sizes(metrics)

        assert len(positions) == 1
        pos = positions[0]
        assert pos.final_size > 0, "Good strategy should get positive position size"
        assert pos.kelly_size > 0
        assert pos.risk_parity_size > 0
        assert pos.volatility_adjusted_size > 0
        assert pos.risk_contribution > 0

    def test_risk_sizing_rejects_bad_strategy(self):
        """A low win-rate strategy with poor profit factor gets minimal/zero sizing."""
        sizer = self._make_sizer()
        metrics = [
            SizingRiskMetrics(
                strategy_id="strat-bad",
                symbol=SYMBOL,
                strategy_type="breakout",
                current_score=0.3,
                volatility=0.50,
                sharpe_ratio=-0.5,
                max_drawdown=0.30,
                win_rate=0.25,
                profit_factor=0.4,
            )
        ]
        positions = sizer.calculate_position_sizes(metrics)

        assert len(positions) == 1
        pos = positions[0]
        # Kelly should be 0 for a bad strategy (b*p - q < 0)
        assert pos.kelly_size == 0.0
        # Final size should be very small
        assert pos.final_size < 0.05

    def test_portfolio_validation_approves_within_limits(self):
        """Validate that a trade within risk limits is approved."""
        positions = [
            Position(
                symbol="ETH-USD",
                side="LONG",
                quantity=0.5,
                entry_price=3000.0,
                current_price=3100.0,
                unrealized_pnl=50.0,
                unrealized_pnl_percent=3.33,
                opened_at="2026-03-12T00:00:00Z",
            )
        ]
        balance = compute_balance(
            positions, realized_pnl_today=0.0, total_realized_pnl=0.0
        )
        risk = compute_risk_metrics(positions, balance.total_equity)
        state = build_portfolio_state(positions, balance, risk, [])

        result = validate_decision(
            action="BUY",
            symbol=SYMBOL,
            quantity=QUANTITY,
            price=ENTRY_PRICE,
            state=state,
        )

        assert result["valid"] is True
        assert result["errors"] == []

    def test_portfolio_validation_rejects_oversized_position(self):
        """A position exceeding max_position_pct is rejected."""
        positions = []
        balance = compute_balance(
            positions, realized_pnl_today=0.0, total_realized_pnl=0.0
        )
        risk = compute_risk_metrics(positions, balance.total_equity)
        state = build_portfolio_state(positions, balance, risk, [])

        # Try to buy 1 BTC at 50k = $50,000 which is 500% of $10,000 equity
        result = validate_decision(
            action="BUY",
            symbol=SYMBOL,
            quantity=1.0,
            price=ENTRY_PRICE,
            state=state,
            max_position_pct=0.02,
        )

        assert result["valid"] is False
        assert any(
            "too large" in e.lower() or "exceeds" in e.lower() for e in result["errors"]
        )

    def test_portfolio_validation_rejects_insufficient_buying_power(self):
        """Insufficient buying power rejects the trade."""
        # Create a portfolio where almost all capital is allocated
        positions = [
            Position(
                symbol="ETH-USD",
                side="LONG",
                quantity=3.0,
                entry_price=3000.0,
                current_price=3000.0,
                unrealized_pnl=0.0,
                unrealized_pnl_percent=0.0,
                opened_at="2026-03-12T00:00:00Z",
            )
        ]
        balance = compute_balance(
            positions, realized_pnl_today=0.0, total_realized_pnl=0.0
        )
        risk = compute_risk_metrics(positions, balance.total_equity)
        state = build_portfolio_state(positions, balance, risk, [])

        result = validate_decision(
            action="BUY",
            symbol=SYMBOL,
            quantity=0.5,
            price=ENTRY_PRICE,
            state=state,
        )

        assert result["valid"] is False
        assert any("buying power" in e.lower() for e in result["errors"])


# ---------------------------------------------------------------------------
# Stage 3: Order Execution (approved signal → paper trade)
# ---------------------------------------------------------------------------


class TestStage3OrderExecution:
    """Paper trading simulator executes approved signals."""

    @patch("services.paper_trading.service._get_current_price")
    @patch("services.paper_trading.service.call_mcp_tool")
    def test_execute_buy_from_signal(
        self, mock_mcp, mock_price, paper_client, paper_pg_client
    ):
        """Execute a BUY paper trade from a signal."""
        mock_mcp.return_value = [
            {
                "signal_id": SIGNAL_ID,
                "symbol": SYMBOL,
                "action": "BUY",
                "confidence": 0.82,
            }
        ]
        mock_price.return_value = ENTRY_PRICE
        paper_pg_client.execute_trade.return_value = {
            "trade_id": "trade-e2e-1",
            "signal_id": SIGNAL_ID,
            "symbol": SYMBOL,
            "side": "BUY",
            "entry_price": ENTRY_PRICE,
            "quantity": QUANTITY,
            "status": "OPEN",
            "opened_at": "2026-03-12T10:00:00",
        }
        paper_pg_client.log_decision.return_value = "dec-1"

        resp = paper_client.post(
            "/paper/execute",
            json={
                "signal_id": SIGNAL_ID,
                "quantity": QUANTITY,
                "reasoning": "E2E test: bullish consensus",
            },
            content_type="application/json",
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["trade_id"] == "trade-e2e-1"
        assert data["side"] == "BUY"
        assert data["entry_price"] == ENTRY_PRICE
        assert data["quantity"] == QUANTITY
        assert data["status"] == "OPEN"

        paper_pg_client.execute_trade.assert_called_once_with(
            signal_id=SIGNAL_ID,
            symbol=SYMBOL,
            side="BUY",
            entry_price=ENTRY_PRICE,
            quantity=QUANTITY,
        )

    @patch("services.paper_trading.service.call_mcp_tool")
    def test_hold_signal_not_executed(self, mock_mcp, paper_client):
        """A HOLD signal cannot be executed as a trade."""
        mock_mcp.return_value = [
            {
                "signal_id": "sig-hold",
                "symbol": SYMBOL,
                "action": "HOLD",
                "confidence": 0.5,
            }
        ]

        resp = paper_client.post(
            "/paper/execute",
            json={"signal_id": "sig-hold", "quantity": QUANTITY},
            content_type="application/json",
        )

        assert resp.status_code == 400
        assert "HOLD" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Stage 4: Position Tracking (open trade → portfolio state)
# ---------------------------------------------------------------------------


class TestStage4PositionTracking:
    """Portfolio state correctly tracks positions from executed trades."""

    @patch("services.paper_trading.service._get_current_price")
    def test_portfolio_reflects_open_position(
        self, mock_price, paper_client, paper_pg_client
    ):
        """After a trade, the portfolio endpoint shows the open position."""
        paper_pg_client.get_portfolio.return_value = [
            {
                "symbol": SYMBOL,
                "quantity": QUANTITY,
                "avg_entry_price": ENTRY_PRICE,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-12T10:00:00",
            }
        ]
        mock_price.return_value = CURRENT_PRICE

        resp = paper_client.get("/paper/portfolio")

        assert resp.status_code == 200
        data = resp.get_json()
        positions = data["positions"]
        assert len(positions) == 1

        pos = positions[0]
        assert pos["symbol"] == SYMBOL
        assert pos["quantity"] == QUANTITY
        assert pos["avg_entry_price"] == ENTRY_PRICE
        assert pos["current_price"] == CURRENT_PRICE
        # Unrealized P&L: 0.1 * (52000 - 50000) = 200
        assert pos["unrealized_pnl"] == 200.0

    def test_compute_positions_long_profit(self):
        """Compute positions correctly for a profitable LONG trade."""
        portfolio_rows = [
            {
                "symbol": SYMBOL,
                "quantity": QUANTITY,
                "avg_entry_price": ENTRY_PRICE,
                "updated_at": "2026-03-12T10:00:00",
            }
        ]
        open_trades = [
            {
                "symbol": SYMBOL,
                "side": "BUY",
                "opened_at": "2026-03-12T10:00:00",
                "trade_id": "t-1",
            }
        ]
        current_prices = {SYMBOL: CURRENT_PRICE}

        positions = compute_positions(portfolio_rows, open_trades, current_prices)

        assert len(positions) == 1
        pos = positions[0]
        assert pos.side == "LONG"
        assert pos.unrealized_pnl == round(QUANTITY * (CURRENT_PRICE - ENTRY_PRICE), 8)
        assert pos.unrealized_pnl_percent == round(
            (CURRENT_PRICE - ENTRY_PRICE) / ENTRY_PRICE * 100, 2
        )

    def test_compute_positions_short_profit(self):
        """Compute positions correctly for a profitable SHORT trade."""
        short_entry = 52000.0
        short_current = 50000.0

        portfolio_rows = [
            {
                "symbol": SYMBOL,
                "quantity": QUANTITY,
                "avg_entry_price": short_entry,
                "updated_at": "2026-03-12T10:00:00",
            }
        ]
        open_trades = [
            {
                "symbol": SYMBOL,
                "side": "SELL",
                "opened_at": "2026-03-12T10:00:00",
                "trade_id": "t-2",
            }
        ]
        current_prices = {SYMBOL: short_current}

        positions = compute_positions(portfolio_rows, open_trades, current_prices)

        pos = positions[0]
        assert pos.side == "SHORT"
        # SHORT P&L: qty * (entry - current) = 0.1 * (52000 - 50000) = 200
        assert pos.unrealized_pnl == round(QUANTITY * (short_entry - short_current), 8)

    def test_risk_metrics_computation(self):
        """Risk metrics correctly reflect portfolio state."""
        positions = [
            Position(
                symbol=SYMBOL,
                side="LONG",
                quantity=QUANTITY,
                entry_price=ENTRY_PRICE,
                current_price=CURRENT_PRICE,
                unrealized_pnl=200.0,
                unrealized_pnl_percent=4.0,
                opened_at="2026-03-12T10:00:00Z",
            ),
            Position(
                symbol="ETH-USD",
                side="LONG",
                quantity=1.0,
                entry_price=3000.0,
                current_price=3100.0,
                unrealized_pnl=100.0,
                unrealized_pnl_percent=3.33,
                opened_at="2026-03-12T10:00:00Z",
            ),
        ]
        balance = compute_balance(
            positions, realized_pnl_today=50.0, total_realized_pnl=500.0
        )
        risk = compute_risk_metrics(positions, balance.total_equity)

        assert risk.num_open_positions == 2
        assert risk.portfolio_heat > 0
        assert risk.max_position_pct > 0
        assert risk.max_position_symbol in (SYMBOL, "ETH-USD")


# ---------------------------------------------------------------------------
# Stage 5: P&L Calculation (close trade → realized P&L)
# ---------------------------------------------------------------------------


class TestStage5PnLCalculation:
    """P&L is correctly calculated when trades are closed."""

    def test_pnl_summary_after_trades(self, paper_client, paper_pg_client):
        """P&L summary correctly aggregates closed trades."""
        paper_pg_client.get_pnl_summary.return_value = {
            "total_pnl": 350.0,
            "total_trades": 5,
            "winning_trades": 3,
            "losing_trades": 1,
            "breakeven_trades": 1,
            "win_rate": 60.0,
            "avg_pnl": 70.0,
            "best_trade": 200.0,
            "worst_trade": -50.0,
            "open_positions": 1,
            "total_unrealized_pnl": 200.0,
        }

        resp = paper_client.get("/paper/pnl-summary")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_pnl"] == 350.0
        assert data["winning_trades"] == 3
        assert data["losing_trades"] == 1
        assert data["win_rate"] == 60.0
        assert data["open_positions"] == 1
        assert data["total_unrealized_pnl"] == 200.0

    def test_balance_reflects_realized_pnl(self):
        """Account balance correctly incorporates realized P&L."""
        positions = [
            Position(
                symbol=SYMBOL,
                side="LONG",
                quantity=QUANTITY,
                entry_price=ENTRY_PRICE,
                current_price=CURRENT_PRICE,
                unrealized_pnl=200.0,
                unrealized_pnl_percent=4.0,
                opened_at="2026-03-12T10:00:00Z",
            )
        ]

        total_realized = 500.0
        balance = compute_balance(
            positions,
            realized_pnl_today=100.0,
            total_realized_pnl=total_realized,
            initial_capital=10000.0,
        )

        # Equity = initial + realized + unrealized = 10000 + 500 + 200
        assert balance.total_equity == 10700.0
        assert balance.unrealized_pnl == 200.0
        assert balance.realized_pnl_today == 100.0
        # Margin used = qty * entry = 0.1 * 50000 = 5000
        assert balance.margin_used == 5000.0
        # Available = equity - margin = 10700 - 5000 = 5700
        assert balance.available_cash == 5700.0

    def test_pnl_buy_trade_profit(self):
        """BUY trade P&L: (exit - entry) * qty."""
        entry = 50000.0
        exit_price = 52000.0
        qty = 0.1
        # P&L = (52000 - 50000) * 0.1 = 200
        pnl = (exit_price - entry) * qty
        assert pnl == 200.0

    def test_pnl_buy_trade_loss(self):
        """BUY trade loss: (exit - entry) * qty when exit < entry."""
        entry = 50000.0
        exit_price = 48000.0
        qty = 0.1
        # P&L = (48000 - 50000) * 0.1 = -200
        pnl = (exit_price - entry) * qty
        assert pnl == -200.0

    def test_pnl_sell_trade_profit(self):
        """SELL (short) trade P&L: (entry - exit) * qty."""
        entry = 50000.0
        exit_price = 48000.0
        qty = 0.1
        # P&L = (50000 - 48000) * 0.1 = 200
        pnl = (entry - exit_price) * qty
        assert pnl == 200.0


# ---------------------------------------------------------------------------
# Full Pipeline Integration
# ---------------------------------------------------------------------------


class TestFullPipelineIntegration:
    """End-to-end: signal generation → risk check → execution → tracking → P&L."""

    @patch("requests.post")
    @patch("services.signal_generator_agent.agent.OpenAI")
    @patch("services.paper_trading.service._get_current_price")
    @patch("services.paper_trading.service.call_mcp_tool")
    def test_successful_trade_full_pipeline(
        self,
        mock_paper_mcp,
        mock_price,
        mock_openai_cls,
        mock_http,
        paper_client,
        paper_pg_client,
    ):
        """Complete successful pipeline: market data → signal → risk → execute → track → P&L."""

        # --- Stage 1: Signal Generation ---
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        signal_payload = {
            "symbol": SYMBOL,
            "action": "BUY",
            "confidence": 0.82,
            "reasoning": "Strong bullish consensus",
            "strategy_breakdown": [
                {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.85},
                {
                    "strategy_type": "mean_reversion",
                    "signal": "BUY",
                    "confidence": 0.75,
                },
            ],
        }

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc1", "get_top_strategies", {"symbol": SYMBOL, "limit": 10}
                )
            ]
        )
        resp2 = _mock_assistant_with_tools(
            [_mock_tool_call("tc2", "emit_signal", signal_payload)]
        )
        resp3 = _mock_assistant_stop(signal_payload)
        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3]

        mcp_data = {
            "get_top_strategies": _strategies(),
            "emit_signal": _emit_result(),
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = _make_mcp_response(mcp_data[tool_name])
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        signal_result = agent.run_agent_for_symbol(SYMBOL, "test-key", mcp_urls)
        parsed_signal = json.loads(signal_result)
        assert parsed_signal["action"] == "BUY"

        # --- Stage 2: Risk Check ---
        sizer = RiskAdjustedSizer.__new__(RiskAdjustedSizer)
        sizer.db_config = {}
        sizer.pool = None
        risk_metrics = [
            SizingRiskMetrics(
                strategy_id="strat-1",
                symbol=SYMBOL,
                strategy_type="momentum",
                current_score=parsed_signal["confidence"],
                volatility=0.15,
                sharpe_ratio=1.5,
                max_drawdown=0.05,
                win_rate=0.65,
                profit_factor=1.8,
            )
        ]
        position_sizes = sizer.calculate_position_sizes(risk_metrics)
        assert position_sizes[0].final_size > 0, "Risk check should approve"

        # Portfolio validation
        portfolio_state = build_portfolio_state(
            positions=[],
            balance=compute_balance([], 0.0, 0.0),
            risk_metrics=compute_risk_metrics([], 10000.0),
            recent_trades=[],
        )
        validation = validate_decision(
            action=parsed_signal["action"],
            symbol=SYMBOL,
            quantity=QUANTITY,
            price=ENTRY_PRICE,
            state=portfolio_state,
        )
        assert validation["valid"] is True

        # --- Stage 3: Order Execution ---
        mock_paper_mcp.return_value = [
            {
                "signal_id": SIGNAL_ID,
                "symbol": SYMBOL,
                "action": "BUY",
                "confidence": 0.82,
            }
        ]
        mock_price.return_value = ENTRY_PRICE
        paper_pg_client.execute_trade.return_value = {
            "trade_id": "trade-e2e-full",
            "signal_id": SIGNAL_ID,
            "symbol": SYMBOL,
            "side": "BUY",
            "entry_price": ENTRY_PRICE,
            "quantity": QUANTITY,
            "status": "OPEN",
            "opened_at": "2026-03-12T10:00:00",
        }
        paper_pg_client.log_decision.return_value = "dec-e2e"

        resp = paper_client.post(
            "/paper/execute",
            json={
                "signal_id": SIGNAL_ID,
                "quantity": QUANTITY,
                "reasoning": parsed_signal["reasoning"],
            },
            content_type="application/json",
        )
        assert resp.status_code == 201
        trade = resp.get_json()
        assert trade["status"] == "OPEN"

        # --- Stage 4: Position Tracking ---
        paper_pg_client.get_portfolio.return_value = [
            {
                "symbol": SYMBOL,
                "quantity": QUANTITY,
                "avg_entry_price": ENTRY_PRICE,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-12T10:00:00",
            }
        ]
        mock_price.return_value = CURRENT_PRICE

        portfolio_resp = paper_client.get("/paper/portfolio")
        assert portfolio_resp.status_code == 200
        portfolio_data = portfolio_resp.get_json()
        assert len(portfolio_data["positions"]) == 1
        assert portfolio_data["positions"][0]["current_price"] == CURRENT_PRICE
        expected_unrealized = QUANTITY * (CURRENT_PRICE - ENTRY_PRICE)
        assert portfolio_data["positions"][0]["unrealized_pnl"] == expected_unrealized

        # --- Stage 5: P&L Calculation ---
        paper_pg_client.get_pnl_summary.return_value = {
            "total_pnl": expected_unrealized,
            "total_trades": 1,
            "winning_trades": 1,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 100.0,
            "avg_pnl": expected_unrealized,
            "best_trade": expected_unrealized,
            "worst_trade": 0.0,
            "open_positions": 1,
            "total_unrealized_pnl": expected_unrealized,
        }

        pnl_resp = paper_client.get("/paper/pnl-summary")
        assert pnl_resp.status_code == 200
        pnl_data = pnl_resp.get_json()
        assert pnl_data["total_pnl"] == expected_unrealized
        assert pnl_data["winning_trades"] == 1
        assert pnl_data["win_rate"] == 100.0

    @patch("requests.post")
    @patch("services.signal_generator_agent.agent.OpenAI")
    def test_rejected_trade_pipeline(self, mock_openai_cls, mock_http):
        """Pipeline where risk limits prevent trade execution."""

        # --- Stage 1: Signal Generation (produces BUY) ---
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        signal_payload = {
            "symbol": SYMBOL,
            "action": "BUY",
            "confidence": 0.78,
            "reasoning": "Momentum consensus",
            "strategy_breakdown": [
                {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.78},
            ],
        }
        resp1 = _mock_assistant_stop(signal_payload)
        mock_client.chat.completions.create.return_value = resp1

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        signal_result = agent.run_agent_for_symbol(SYMBOL, "test-key", mcp_urls)
        parsed_signal = json.loads(signal_result)
        assert parsed_signal["action"] == "BUY"

        # --- Stage 2: Risk Check REJECTS ---
        # Portfolio is already heavily allocated
        existing_positions = [
            Position(
                symbol="ETH-USD",
                side="LONG",
                quantity=3.0,
                entry_price=3000.0,
                current_price=3000.0,
                unrealized_pnl=0.0,
                unrealized_pnl_percent=0.0,
                opened_at="2026-03-12T00:00:00Z",
            ),
        ]
        balance = compute_balance(
            existing_positions,
            realized_pnl_today=0.0,
            total_realized_pnl=0.0,
        )
        risk = compute_risk_metrics(existing_positions, balance.total_equity)
        state = build_portfolio_state(existing_positions, balance, risk, [])

        # Try to buy 0.5 BTC at 50k = $25,000 but equity is only $10,000
        validation = validate_decision(
            action="BUY",
            symbol=SYMBOL,
            quantity=0.5,
            price=ENTRY_PRICE,
            state=state,
        )

        assert validation["valid"] is False
        assert len(validation["errors"]) > 0
        # Trade should NOT proceed to execution

    def test_multiple_positions_portfolio_tracking(self):
        """Track multiple concurrent positions with correct risk metrics."""
        portfolio_rows = [
            {
                "symbol": "BTC-USD",
                "quantity": 0.1,
                "avg_entry_price": 50000.0,
                "updated_at": "2026-03-12T10:00:00",
            },
            {
                "symbol": "ETH-USD",
                "quantity": 1.0,
                "avg_entry_price": 3000.0,
                "updated_at": "2026-03-12T10:00:00",
            },
            {
                "symbol": "SOL-USD",
                "quantity": 10.0,
                "avg_entry_price": 150.0,
                "updated_at": "2026-03-12T10:00:00",
            },
        ]
        open_trades = [
            {
                "symbol": "BTC-USD",
                "side": "BUY",
                "opened_at": "2026-03-12T10:00:00",
                "trade_id": "t-1",
            },
            {
                "symbol": "ETH-USD",
                "side": "BUY",
                "opened_at": "2026-03-12T10:00:00",
                "trade_id": "t-2",
            },
            {
                "symbol": "SOL-USD",
                "side": "BUY",
                "opened_at": "2026-03-12T10:00:00",
                "trade_id": "t-3",
            },
        ]
        current_prices = {
            "BTC-USD": 52000.0,
            "ETH-USD": 3200.0,
            "SOL-USD": 145.0,
        }

        positions = compute_positions(portfolio_rows, open_trades, current_prices)
        assert len(positions) == 3

        # Verify individual P&L
        btc_pos = next(p for p in positions if p.symbol == "BTC-USD")
        assert btc_pos.unrealized_pnl == round(0.1 * (52000 - 50000), 8)  # +200

        eth_pos = next(p for p in positions if p.symbol == "ETH-USD")
        assert eth_pos.unrealized_pnl == round(1.0 * (3200 - 3000), 8)  # +200

        sol_pos = next(p for p in positions if p.symbol == "SOL-USD")
        assert sol_pos.unrealized_pnl == round(10.0 * (145 - 150), 8)  # -50

        # Compute aggregate balance
        total_realized = 100.0
        balance = compute_balance(
            positions, realized_pnl_today=50.0, total_realized_pnl=total_realized
        )
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        assert balance.total_equity == round(
            10000.0 + total_realized + total_unrealized, 2
        )

        # Risk metrics
        risk = compute_risk_metrics(positions, balance.total_equity)
        assert risk.num_open_positions == 3
        assert risk.portfolio_heat > 0
