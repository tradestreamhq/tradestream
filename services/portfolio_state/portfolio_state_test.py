"""Tests for portfolio state computation and risk metrics."""

import pytest

from services.portfolio_state.portfolio_state import (
    AccountBalance,
    Position,
    PortfolioState,
    RiskMetrics,
    compute_balance,
    compute_positions,
    compute_risk_metrics,
    format_portfolio_context,
    validate_decision,
    _classify_sector,
)


class TestComputePositions:
    def test_long_position_with_profit(self):
        portfolio = [
            {
                "symbol": "BTC-USD",
                "quantity": 0.1,
                "avg_entry_price": 40000.0,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-10T00:00:00",
            }
        ]
        trades = [
            {
                "trade_id": "t-1",
                "symbol": "BTC-USD",
                "side": "BUY",
                "entry_price": 40000.0,
                "quantity": 0.1,
                "opened_at": "2026-03-10T00:00:00",
            }
        ]
        prices = {"BTC-USD": 42000.0}

        positions = compute_positions(portfolio, trades, prices)
        assert len(positions) == 1

        p = positions[0]
        assert p.symbol == "BTC-USD"
        assert p.side == "LONG"
        assert p.current_price == 42000.0
        assert p.unrealized_pnl == 200.0  # 0.1 * (42000 - 40000)
        assert p.unrealized_pnl_percent == 5.0

    def test_short_position_with_profit(self):
        portfolio = [
            {
                "symbol": "SOL-USD",
                "quantity": 5.0,
                "avg_entry_price": 100.0,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-10T00:00:00",
            }
        ]
        trades = [
            {
                "trade_id": "t-2",
                "symbol": "SOL-USD",
                "side": "SELL",
                "entry_price": 100.0,
                "quantity": 5.0,
                "opened_at": "2026-03-10T00:00:00",
            }
        ]
        prices = {"SOL-USD": 95.0}

        positions = compute_positions(portfolio, trades, prices)
        p = positions[0]
        assert p.side == "SHORT"
        assert p.unrealized_pnl == 25.0  # 5.0 * (100 - 95)

    def test_position_uses_entry_price_when_no_market_price(self):
        portfolio = [
            {
                "symbol": "XYZ-USD",
                "quantity": 1.0,
                "avg_entry_price": 50.0,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-10T00:00:00",
            }
        ]
        positions = compute_positions(portfolio, [], {})
        assert positions[0].current_price == 50.0
        assert positions[0].unrealized_pnl == 0.0

    def test_empty_portfolio(self):
        assert compute_positions([], [], {}) == []


class TestComputeBalance:
    def test_balance_with_positions(self):
        positions = [
            Position(
                symbol="BTC-USD",
                side="LONG",
                quantity=0.1,
                entry_price=40000.0,
                current_price=42000.0,
                unrealized_pnl=200.0,
                unrealized_pnl_percent=5.0,
                opened_at="2026-03-10T00:00:00",
            )
        ]
        balance = compute_balance(
            positions,
            realized_pnl_today=50.0,
            total_realized_pnl=150.0,
            initial_capital=10000.0,
        )
        assert balance.total_equity == 10350.0  # 10000 + 150 + 200
        assert balance.margin_used == 4000.0  # 0.1 * 40000
        assert balance.available_cash == 6350.0  # 10350 - 4000
        assert balance.buying_power == 6350.0
        assert balance.unrealized_pnl == 200.0
        assert balance.realized_pnl_today == 50.0

    def test_balance_no_positions(self):
        balance = compute_balance([], 0.0, 0.0, 10000.0)
        assert balance.total_equity == 10000.0
        assert balance.available_cash == 10000.0
        assert balance.margin_used == 0.0


class TestComputeRiskMetrics:
    def test_risk_with_positions(self):
        positions = [
            Position(
                symbol="BTC-USD",
                side="LONG",
                quantity=0.1,
                entry_price=40000.0,
                current_price=42000.0,
                unrealized_pnl=200.0,
                unrealized_pnl_percent=5.0,
                opened_at="2026-03-10T00:00:00",
            ),
            Position(
                symbol="ETH-USD",
                side="LONG",
                quantity=1.0,
                entry_price=2000.0,
                current_price=2100.0,
                unrealized_pnl=100.0,
                unrealized_pnl_percent=5.0,
                opened_at="2026-03-10T01:00:00",
            ),
        ]
        risk = compute_risk_metrics(positions, total_equity=10000.0)
        assert risk.num_open_positions == 2
        # BTC: 0.1 * 42000 = 4200 -> 42%; ETH: 1.0 * 2100 = 2100 -> 21%
        assert risk.portfolio_heat == 63.0
        assert risk.max_position_symbol == "BTC-USD"
        assert risk.max_position_pct == 42.0
        assert "Crypto" in risk.sector_exposure

    def test_risk_empty(self):
        risk = compute_risk_metrics([], total_equity=10000.0)
        assert risk.num_open_positions == 0
        assert risk.portfolio_heat == 0.0

    def test_risk_zero_equity(self):
        risk = compute_risk_metrics([], total_equity=0.0)
        assert risk.portfolio_heat == 0.0


class TestClassifySector:
    def test_crypto_symbols(self):
        assert _classify_sector("BTC-USD") == "Crypto"
        assert _classify_sector("ETH-USD") == "Crypto"
        assert _classify_sector("SOL/USD") == "Crypto"

    def test_non_crypto(self):
        assert _classify_sector("AAPL-USD") == "Other"
        assert _classify_sector("UNKNOWN") == "Other"


class TestFormatPortfolioContext:
    def test_format_with_positions(self):
        state = PortfolioState(
            balance=AccountBalance(
                total_equity=10500.0,
                available_cash=8000.0,
                buying_power=8000.0,
                margin_used=2500.0,
                margin_available=8000.0,
                unrealized_pnl=150.0,
                realized_pnl_today=50.0,
            ),
            positions=[
                Position(
                    symbol="BTC-USD",
                    side="LONG",
                    quantity=0.05,
                    entry_price=42000.0,
                    current_price=45000.0,
                    unrealized_pnl=150.0,
                    unrealized_pnl_percent=7.14,
                    opened_at="2026-03-10T00:00:00",
                ),
            ],
            risk_metrics=RiskMetrics(
                portfolio_heat=21.43,
                max_position_pct=21.43,
                max_position_symbol="BTC-USD",
                num_open_positions=1,
                sector_exposure={"Crypto": 21.43},
            ),
            recent_trades=[
                {
                    "symbol": "SOL-USD",
                    "side": "BUY",
                    "quantity": 5.0,
                    "entry_price": 95.0,
                    "exit_price": 98.5,
                    "pnl": 17.5,
                },
            ],
            as_of="2026-03-10T12:00:00+00:00",
        )

        context = format_portfolio_context(state)
        assert "CURRENT PORTFOLIO STATE" in context
        assert "Balance: $10,500.00" in context
        assert "BTC-USD: LONG" in context
        assert "Portfolio heat: 21.4%" in context
        assert "SOL-USD" in context

    def test_format_empty_portfolio(self):
        state = PortfolioState(
            balance=AccountBalance(
                total_equity=10000.0,
                available_cash=10000.0,
                buying_power=10000.0,
                margin_used=0.0,
                margin_available=10000.0,
                unrealized_pnl=0.0,
                realized_pnl_today=0.0,
            ),
            positions=[],
            risk_metrics=RiskMetrics(
                portfolio_heat=0.0,
                max_position_pct=0.0,
                max_position_symbol="",
                num_open_positions=0,
            ),
            recent_trades=[],
            as_of="2026-03-10T12:00:00+00:00",
        )

        context = format_portfolio_context(state)
        assert "No open positions" in context
        assert "No recent trades" in context


class TestValidateDecision:
    def _make_state(self, equity=10000.0, buying_power=10000.0, heat=0.0):
        return PortfolioState(
            balance=AccountBalance(
                total_equity=equity,
                available_cash=buying_power,
                buying_power=buying_power,
                margin_used=0.0,
                margin_available=buying_power,
                unrealized_pnl=0.0,
                realized_pnl_today=0.0,
            ),
            positions=[],
            risk_metrics=RiskMetrics(
                portfolio_heat=heat,
                max_position_pct=0.0,
                max_position_symbol="",
                num_open_positions=0,
            ),
            recent_trades=[],
            as_of="2026-03-10T12:00:00+00:00",
        )

    def test_valid_small_trade(self):
        state = self._make_state()
        result = validate_decision("BUY", "BTC-USD", 0.001, 50000.0, state)
        assert result["valid"] is True

    def test_insufficient_buying_power(self):
        state = self._make_state(buying_power=100.0)
        result = validate_decision("BUY", "BTC-USD", 1.0, 50000.0, state)
        assert result["valid"] is False
        assert any("buying power" in e.lower() for e in result["errors"])

    def test_position_too_large(self):
        state = self._make_state()
        # 0.1 * 50000 = 5000 = 50% of 10000, exceeds 2%
        result = validate_decision("BUY", "BTC-USD", 0.1, 50000.0, state, max_position_pct=0.02)
        assert result["valid"] is False
        assert any("too large" in e.lower() for e in result["errors"])

    def test_exceeds_portfolio_heat(self):
        state = self._make_state(heat=45.0)
        # 0.01 * 50000 = 500 = 5% + 45% = 50% heat, right at limit
        result = validate_decision("BUY", "BTC-USD", 0.01, 50000.0, state, max_position_pct=1.0, max_portfolio_heat=0.49)
        assert result["valid"] is False
        assert any("heat" in e.lower() for e in result["errors"])

    def test_sell_skips_buying_power_check(self):
        state = self._make_state(buying_power=0.0)
        result = validate_decision("SELL", "BTC-USD", 0.1, 50000.0, state, max_position_pct=1.0)
        assert result["valid"] is True
