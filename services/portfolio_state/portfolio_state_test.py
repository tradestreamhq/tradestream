"""Tests for portfolio state computation and risk metrics."""

import pytest

from services.portfolio_state.portfolio_state import (
    AccountBalance,
    Position,
    PortfolioState,
    RiskMetrics,
    build_portfolio_state,
    compute_balance,
    compute_positions,
    compute_risk_metrics,
    format_portfolio_context,
    validate_decision,
    _classify_sector,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MAX_PORTFOLIO_HEAT,
    DEFAULT_MAX_POSITION_PCT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_portfolio_row(
    symbol, quantity, avg_entry_price, updated_at="2026-03-10T00:00:00"
):
    return {
        "symbol": symbol,
        "quantity": quantity,
        "avg_entry_price": avg_entry_price,
        "unrealized_pnl": 0.0,
        "updated_at": updated_at,
    }


def _make_trade(
    symbol,
    side,
    entry_price,
    quantity,
    trade_id="t-1",
    opened_at="2026-03-10T00:00:00",
):
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "quantity": quantity,
        "opened_at": opened_at,
    }


def _make_position(
    symbol="BTC-USD",
    side="LONG",
    quantity=0.1,
    entry_price=40000.0,
    current_price=42000.0,
    unrealized_pnl=200.0,
    unrealized_pnl_percent=5.0,
    opened_at="2026-03-10T00:00:00",
    trade_id=None,
):
    return Position(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_pnl_percent,
        opened_at=opened_at,
        trade_id=trade_id,
    )


def _make_state(
    equity=10000.0,
    buying_power=10000.0,
    heat=0.0,
    positions=None,
    recent_trades=None,
    margin_used=0.0,
    unrealized_pnl=0.0,
    realized_pnl_today=0.0,
):
    return PortfolioState(
        balance=AccountBalance(
            total_equity=equity,
            available_cash=buying_power,
            buying_power=buying_power,
            margin_used=margin_used,
            margin_available=max(0.0, equity - margin_used),
            unrealized_pnl=unrealized_pnl,
            realized_pnl_today=realized_pnl_today,
        ),
        positions=positions or [],
        risk_metrics=RiskMetrics(
            portfolio_heat=heat,
            max_position_pct=0.0,
            max_position_symbol="",
            num_open_positions=len(positions) if positions else 0,
        ),
        recent_trades=recent_trades or [],
        as_of="2026-03-10T12:00:00+00:00",
    )


# ===========================================================================
# compute_positions
# ===========================================================================


class TestComputePositions:
    def test_long_position_with_profit(self):
        portfolio = [_make_portfolio_row("BTC-USD", 0.1, 40000.0)]
        trades = [_make_trade("BTC-USD", "BUY", 40000.0, 0.1)]
        prices = {"BTC-USD": 42000.0}

        positions = compute_positions(portfolio, trades, prices)
        assert len(positions) == 1
        p = positions[0]
        assert p.symbol == "BTC-USD"
        assert p.side == "LONG"
        assert p.current_price == 42000.0
        assert p.unrealized_pnl == 200.0  # 0.1 * (42000 - 40000)
        assert p.unrealized_pnl_percent == 5.0

    def test_long_position_with_loss(self):
        portfolio = [_make_portfolio_row("BTC-USD", 0.1, 40000.0)]
        trades = [_make_trade("BTC-USD", "BUY", 40000.0, 0.1)]
        prices = {"BTC-USD": 38000.0}

        positions = compute_positions(portfolio, trades, prices)
        p = positions[0]
        assert p.side == "LONG"
        assert p.unrealized_pnl == -200.0  # 0.1 * (38000 - 40000)
        assert p.unrealized_pnl_percent == -5.0

    def test_short_position_with_profit(self):
        portfolio = [_make_portfolio_row("SOL-USD", 5.0, 100.0)]
        trades = [_make_trade("SOL-USD", "SELL", 100.0, 5.0)]
        prices = {"SOL-USD": 95.0}

        positions = compute_positions(portfolio, trades, prices)
        p = positions[0]
        assert p.side == "SHORT"
        assert p.unrealized_pnl == 25.0  # 5 * (100 - 95)
        assert p.unrealized_pnl_percent == 5.0

    def test_short_position_with_loss(self):
        portfolio = [_make_portfolio_row("SOL-USD", 5.0, 100.0)]
        trades = [_make_trade("SOL-USD", "SELL", 100.0, 5.0)]
        prices = {"SOL-USD": 110.0}

        positions = compute_positions(portfolio, trades, prices)
        p = positions[0]
        assert p.side == "SHORT"
        assert p.unrealized_pnl == -50.0  # 5 * (100 - 110)
        assert p.unrealized_pnl_percent == -10.0

    def test_position_uses_entry_price_when_no_market_price(self):
        portfolio = [_make_portfolio_row("XYZ-USD", 1.0, 50.0)]
        positions = compute_positions(portfolio, [], {})
        assert positions[0].current_price == 50.0
        assert positions[0].unrealized_pnl == 0.0
        assert positions[0].unrealized_pnl_percent == 0.0

    def test_empty_portfolio(self):
        assert compute_positions([], [], {}) == []

    def test_multiple_positions(self):
        portfolio = [
            _make_portfolio_row("BTC-USD", 0.1, 40000.0),
            _make_portfolio_row("ETH-USD", 1.0, 2000.0),
            _make_portfolio_row("SOL-USD", 10.0, 100.0),
        ]
        trades = [
            _make_trade("BTC-USD", "BUY", 40000.0, 0.1, trade_id="t-1"),
            _make_trade("ETH-USD", "BUY", 2000.0, 1.0, trade_id="t-2"),
            _make_trade("SOL-USD", "SELL", 100.0, 10.0, trade_id="t-3"),
        ]
        prices = {"BTC-USD": 42000.0, "ETH-USD": 2100.0, "SOL-USD": 90.0}

        positions = compute_positions(portfolio, trades, prices)
        assert len(positions) == 3
        assert positions[0].side == "LONG"
        assert positions[1].side == "LONG"
        assert positions[2].side == "SHORT"  # SOL is SELL
        assert positions[2].unrealized_pnl == 100.0  # 10 * (100 - 90)

    def test_trade_id_and_opened_at_from_trade(self):
        portfolio = [_make_portfolio_row("BTC-USD", 0.1, 40000.0)]
        trades = [
            _make_trade(
                "BTC-USD",
                "BUY",
                40000.0,
                0.1,
                trade_id="trade-123",
                opened_at="2026-03-10T14:30:00",
            )
        ]
        positions = compute_positions(portfolio, trades, {"BTC-USD": 40000.0})
        assert positions[0].trade_id == "trade-123"
        assert positions[0].opened_at == "2026-03-10T14:30:00"

    def test_defaults_side_to_buy_when_no_trade(self):
        """Positions without matching trade default to BUY/LONG."""
        portfolio = [_make_portfolio_row("BTC-USD", 0.1, 40000.0)]
        positions = compute_positions(portfolio, [], {"BTC-USD": 41000.0})
        assert positions[0].side == "LONG"

    def test_uses_updated_at_when_no_trade_opened_at(self):
        portfolio = [
            _make_portfolio_row(
                "BTC-USD", 0.1, 40000.0, updated_at="2026-03-09T08:00:00"
            )
        ]
        positions = compute_positions(portfolio, [], {"BTC-USD": 40000.0})
        assert positions[0].opened_at == "2026-03-09T08:00:00"

    def test_zero_entry_price_prevents_division_error(self):
        """Entry price of zero should not cause ZeroDivisionError."""
        portfolio = [_make_portfolio_row("FREE-TOKEN", 100.0, 0.0)]
        positions = compute_positions(portfolio, [], {"FREE-TOKEN": 0.5})
        assert positions[0].unrealized_pnl_percent == 0.0

    def test_only_first_trade_per_symbol_is_used(self):
        """If multiple trades exist for a symbol, only the first one seen is used."""
        portfolio = [_make_portfolio_row("BTC-USD", 0.2, 40000.0)]
        trades = [
            _make_trade("BTC-USD", "BUY", 40000.0, 0.1, trade_id="t-1"),
            _make_trade("BTC-USD", "BUY", 41000.0, 0.1, trade_id="t-2"),
        ]
        positions = compute_positions(portfolio, trades, {"BTC-USD": 42000.0})
        assert positions[0].trade_id == "t-1"

    def test_pnl_rounding(self):
        """P&L values are rounded to 8 decimal places."""
        portfolio = [_make_portfolio_row("XRP-USD", 3.0, 0.333333)]
        positions = compute_positions(portfolio, [], {"XRP-USD": 0.444444})
        # 3.0 * (0.444444 - 0.333333) = 0.333333
        assert positions[0].unrealized_pnl == round(3.0 * (0.444444 - 0.333333), 8)


# ===========================================================================
# compute_balance
# ===========================================================================


class TestComputeBalance:
    def test_balance_with_positions(self):
        positions = [_make_position()]
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
        assert balance.buying_power == 10000.0

    def test_balance_buying_power_floors_at_zero(self):
        """When margin exceeds equity, buying power should be 0."""
        positions = [
            _make_position(
                quantity=1.0,
                entry_price=8000.0,
                current_price=5000.0,
                unrealized_pnl=-3000.0,
            ),
            _make_position(
                symbol="ETH-USD",
                quantity=1.0,
                entry_price=4000.0,
                current_price=3000.0,
                unrealized_pnl=-1000.0,
            ),
        ]
        balance = compute_balance(positions, 0.0, 0.0, 10000.0)
        # total_equity = 10000 + 0 + (-4000) = 6000
        # margin_used = 8000 + 4000 = 12000
        # available_cash = 6000 - 12000 = -6000
        assert balance.buying_power == 0.0
        assert balance.available_cash == -6000.0

    def test_balance_with_negative_realized_pnl(self):
        balance = compute_balance(
            [],
            realized_pnl_today=-100.0,
            total_realized_pnl=-500.0,
            initial_capital=10000.0,
        )
        assert balance.total_equity == 9500.0
        assert balance.realized_pnl_today == -100.0

    def test_balance_with_multiple_positions(self):
        positions = [
            _make_position(quantity=0.1, entry_price=40000.0, unrealized_pnl=200.0),
            _make_position(
                symbol="ETH-USD",
                quantity=1.0,
                entry_price=2000.0,
                unrealized_pnl=100.0,
            ),
        ]
        balance = compute_balance(positions, 0.0, 0.0, 10000.0)
        assert balance.unrealized_pnl == 300.0
        assert balance.margin_used == 6000.0  # 4000 + 2000
        assert balance.total_equity == 10300.0

    def test_balance_uses_default_initial_capital(self):
        balance = compute_balance([], 0.0, 0.0)
        assert balance.total_equity == DEFAULT_INITIAL_CAPITAL

    def test_balance_values_are_rounded(self):
        positions = [
            _make_position(quantity=0.333, entry_price=100.333, unrealized_pnl=1.11111),
        ]
        balance = compute_balance(positions, 0.111, 0.222, 10000.0)
        assert balance.total_equity == round(10000.0 + 0.222 + 1.11111, 2)
        assert balance.margin_used == round(0.333 * 100.333, 2)


# ===========================================================================
# compute_risk_metrics
# ===========================================================================


class TestComputeRiskMetrics:
    def test_risk_with_positions(self):
        positions = [
            _make_position(symbol="BTC-USD", quantity=0.1, current_price=42000.0),
            _make_position(symbol="ETH-USD", quantity=1.0, current_price=2100.0),
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
        assert risk.max_position_symbol == ""

    def test_risk_zero_equity(self):
        risk = compute_risk_metrics([], total_equity=0.0)
        assert risk.portfolio_heat == 0.0

    def test_risk_negative_equity(self):
        risk = compute_risk_metrics([_make_position()], total_equity=-100.0)
        # Negative equity triggers early return
        assert risk.portfolio_heat == 0.0
        assert risk.num_open_positions == 0

    def test_risk_single_position(self):
        positions = [
            _make_position(symbol="BTC-USD", quantity=0.1, current_price=50000.0)
        ]
        risk = compute_risk_metrics(positions, total_equity=10000.0)
        assert risk.num_open_positions == 1
        assert risk.portfolio_heat == 50.0  # 5000/10000 * 100
        assert risk.max_position_pct == 50.0
        assert risk.max_position_symbol == "BTC-USD"

    def test_risk_mixed_sectors(self):
        positions = [
            _make_position(symbol="BTC-USD", quantity=0.1, current_price=10000.0),
            _make_position(symbol="AAPL-USD", quantity=10.0, current_price=100.0),
        ]
        risk = compute_risk_metrics(positions, total_equity=10000.0)
        assert "Crypto" in risk.sector_exposure
        assert "Other" in risk.sector_exposure
        assert risk.sector_exposure["Crypto"] == 10.0  # 1000/10000 * 100
        assert risk.sector_exposure["Other"] == 10.0

    def test_risk_sector_exposure_aggregates(self):
        """Multiple crypto positions should aggregate under 'Crypto'."""
        positions = [
            _make_position(symbol="BTC-USD", quantity=0.01, current_price=50000.0),
            _make_position(symbol="ETH-USD", quantity=1.0, current_price=2000.0),
        ]
        risk = compute_risk_metrics(positions, total_equity=10000.0)
        # BTC: 500/10000*100=5%, ETH: 2000/10000*100=20%
        assert risk.sector_exposure["Crypto"] == 25.0

    def test_risk_values_are_rounded(self):
        positions = [
            _make_position(symbol="BTC-USD", quantity=0.03, current_price=33333.33),
        ]
        risk = compute_risk_metrics(positions, total_equity=10000.0)
        # 0.03 * 33333.33 / 10000 * 100 = 9.999999
        assert risk.portfolio_heat == round(0.03 * 33333.33 / 10000.0 * 100, 2)

    def test_risk_daily_drawdown_defaults_to_zero(self):
        risk = compute_risk_metrics([], total_equity=10000.0)
        assert risk.daily_drawdown == 0.0


# ===========================================================================
# _classify_sector
# ===========================================================================


class TestClassifySector:
    def test_crypto_symbols(self):
        assert _classify_sector("BTC-USD") == "Crypto"
        assert _classify_sector("ETH-USD") == "Crypto"
        assert _classify_sector("SOL/USD") == "Crypto"
        assert _classify_sector("ADA-USD") == "Crypto"
        assert _classify_sector("DOT-USDT") == "Crypto"
        assert _classify_sector("AVAX/EUR") == "Crypto"
        assert _classify_sector("MATIC-USD") == "Crypto"
        assert _classify_sector("LINK-USD") == "Crypto"
        assert _classify_sector("UNI-USD") == "Crypto"
        assert _classify_sector("DOGE-USD") == "Crypto"
        assert _classify_sector("XRP-USD") == "Crypto"
        assert _classify_sector("BNB-USD") == "Crypto"

    def test_non_crypto(self):
        assert _classify_sector("AAPL-USD") == "Other"
        assert _classify_sector("UNKNOWN") == "Other"
        assert _classify_sector("TSLA/USD") == "Other"

    def test_case_insensitive_via_upper(self):
        """Symbol base is uppercased before comparison."""
        assert _classify_sector("btc-usd") == "Crypto"
        assert _classify_sector("Eth-USD") == "Crypto"

    def test_no_separator(self):
        """Symbol without - or / gets classified correctly."""
        assert _classify_sector("BTC") == "Crypto"
        assert _classify_sector("AAPL") == "Other"


# ===========================================================================
# build_portfolio_state
# ===========================================================================


class TestBuildPortfolioState:
    def test_assembles_state_with_timestamp(self):
        positions = [_make_position()]
        balance = AccountBalance(
            total_equity=10200.0,
            available_cash=6200.0,
            buying_power=6200.0,
            margin_used=4000.0,
            margin_available=6200.0,
            unrealized_pnl=200.0,
            realized_pnl_today=0.0,
        )
        risk = RiskMetrics(
            portfolio_heat=42.0,
            max_position_pct=42.0,
            max_position_symbol="BTC-USD",
            num_open_positions=1,
        )
        trades = [{"symbol": "SOL-USD", "side": "BUY", "pnl": 10.0}]

        state = build_portfolio_state(positions, balance, risk, trades)
        assert state.balance is balance
        assert state.positions is positions
        assert state.risk_metrics is risk
        assert state.recent_trades is trades
        # as_of should be an ISO timestamp string
        assert "T" in state.as_of

    def test_empty_state(self):
        balance = AccountBalance(
            total_equity=10000.0,
            available_cash=10000.0,
            buying_power=10000.0,
            margin_used=0.0,
            margin_available=10000.0,
            unrealized_pnl=0.0,
            realized_pnl_today=0.0,
        )
        risk = RiskMetrics(
            portfolio_heat=0.0,
            max_position_pct=0.0,
            max_position_symbol="",
            num_open_positions=0,
        )
        state = build_portfolio_state([], balance, risk, [])
        assert state.positions == []
        assert state.recent_trades == []


# ===========================================================================
# format_portfolio_context
# ===========================================================================


class TestFormatPortfolioContext:
    def test_format_with_positions(self):
        state = _make_state(
            equity=10500.0,
            buying_power=8000.0,
            margin_used=2500.0,
            unrealized_pnl=150.0,
            realized_pnl_today=50.0,
            positions=[
                _make_position(
                    symbol="BTC-USD",
                    quantity=0.05,
                    entry_price=42000.0,
                    current_price=45000.0,
                    unrealized_pnl=150.0,
                    unrealized_pnl_percent=7.14,
                ),
            ],
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
        )
        # Manually set risk metrics with sector exposure
        state.risk_metrics = RiskMetrics(
            portfolio_heat=21.43,
            max_position_pct=21.43,
            max_position_symbol="BTC-USD",
            num_open_positions=1,
            sector_exposure={"Crypto": 21.43},
        )

        context = format_portfolio_context(state)
        assert "CURRENT PORTFOLIO STATE" in context
        assert "Balance: $10,500.00" in context
        assert "Available to trade: $8,000.00" in context
        assert "BTC-USD: LONG" in context
        assert "+7.1%" in context
        assert "Portfolio heat: 21.4%" in context
        assert "Largest position: BTC-USD" in context
        assert "Crypto: 21.4%" in context
        assert "Bought 5.0 SOL-USD" in context
        assert "+$17.50" in context

    def test_format_empty_portfolio(self):
        state = _make_state()
        context = format_portfolio_context(state)
        assert "No open positions" in context
        assert "No recent trades" in context

    def test_format_with_negative_pnl(self):
        state = _make_state(
            equity=9500.0,
            realized_pnl_today=-50.0,
            positions=[
                _make_position(unrealized_pnl=-100.0, unrealized_pnl_percent=-2.5),
            ],
        )
        context = format_portfolio_context(state)
        assert "-$50.00" in context
        assert "-2.5%" in context

    def test_format_sell_in_recent_trades(self):
        state = _make_state(
            recent_trades=[
                {
                    "symbol": "BTC-USD",
                    "side": "SELL",
                    "quantity": 0.1,
                    "entry_price": 40000.0,
                    "exit_price": 42000.0,
                    "pnl": 200.0,
                },
            ],
        )
        context = format_portfolio_context(state)
        assert "Sold 0.1 BTC-USD" in context

    def test_format_trade_with_zero_pnl(self):
        state = _make_state(
            recent_trades=[
                {
                    "symbol": "ETH-USD",
                    "side": "BUY",
                    "quantity": 1.0,
                    "entry_price": 2000.0,
                    "exit_price": 2000.0,
                    "pnl": 0,
                },
            ],
        )
        context = format_portfolio_context(state)
        # Zero pnl should not include a pnl suffix
        assert "Bought 1.0 ETH-USD" in context
        lines = [l for l in context.split("\n") if "ETH-USD" in l]
        for line in lines:
            assert "(+" not in line
            assert "(-" not in line

    def test_format_trade_with_no_exit_price_uses_entry(self):
        state = _make_state(
            recent_trades=[
                {
                    "symbol": "ETH-USD",
                    "side": "BUY",
                    "quantity": 1.0,
                    "entry_price": 2000.0,
                    "exit_price": None,
                    "pnl": None,
                },
            ],
        )
        context = format_portfolio_context(state)
        assert "@ $2,000.00" in context

    def test_format_limits_recent_trades_to_five(self):
        trades = [
            {
                "symbol": f"SYM{i}-USD",
                "side": "BUY",
                "quantity": 1.0,
                "entry_price": 100.0,
                "exit_price": 110.0,
                "pnl": 10.0,
            }
            for i in range(10)
        ]
        state = _make_state(recent_trades=trades)
        context = format_portfolio_context(state)
        # Only 5 trades should appear
        assert context.count("Bought") == 5

    def test_format_no_sector_exposure_when_empty(self):
        state = _make_state()
        state.risk_metrics = RiskMetrics(
            portfolio_heat=0.0,
            max_position_pct=0.0,
            max_position_symbol="",
            num_open_positions=0,
            sector_exposure={},
        )
        context = format_portfolio_context(state)
        assert "Sector exposure" not in context

    def test_format_no_largest_position_when_empty(self):
        state = _make_state()
        state.risk_metrics = RiskMetrics(
            portfolio_heat=0.0,
            max_position_pct=0.0,
            max_position_symbol="",
            num_open_positions=0,
        )
        context = format_portfolio_context(state)
        assert "Largest position" not in context


# ===========================================================================
# validate_decision
# ===========================================================================


class TestValidateDecision:
    def test_valid_small_trade(self):
        state = _make_state()
        result = validate_decision("BUY", "BTC-USD", 0.001, 50000.0, state)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_insufficient_buying_power(self):
        state = _make_state(buying_power=100.0)
        result = validate_decision("BUY", "BTC-USD", 1.0, 50000.0, state)
        assert result["valid"] is False
        assert any("buying power" in e.lower() for e in result["errors"])

    def test_position_too_large(self):
        state = _make_state()
        result = validate_decision(
            "BUY", "BTC-USD", 0.1, 50000.0, state, max_position_pct=0.02
        )
        assert result["valid"] is False
        assert any("too large" in e.lower() for e in result["errors"])

    def test_exceeds_portfolio_heat(self):
        state = _make_state(heat=45.0)
        result = validate_decision(
            "BUY",
            "BTC-USD",
            0.01,
            50000.0,
            state,
            max_position_pct=1.0,
            max_portfolio_heat=0.49,
        )
        assert result["valid"] is False
        assert any("heat" in e.lower() for e in result["errors"])

    def test_sell_skips_buying_power_check(self):
        state = _make_state(buying_power=0.0)
        result = validate_decision(
            "SELL", "BTC-USD", 0.1, 50000.0, state, max_position_pct=1.0
        )
        assert result["valid"] is True

    def test_sell_skips_heat_check(self):
        """SELL orders should not trigger the portfolio heat check."""
        state = _make_state(heat=49.0)
        result = validate_decision(
            "SELL",
            "BTC-USD",
            1.0,
            50000.0,
            state,
            max_position_pct=1.0,
            max_portfolio_heat=0.50,
        )
        assert result["valid"] is True

    def test_multiple_errors(self):
        """A trade can trigger both buying power and position size errors."""
        state = _make_state(equity=10000.0, buying_power=100.0)
        result = validate_decision(
            "BUY", "BTC-USD", 1.0, 50000.0, state, max_position_pct=0.02
        )
        assert result["valid"] is False
        assert len(result["errors"]) >= 2

    def test_zero_equity_skips_position_and_heat_checks(self):
        state = _make_state(equity=0.0, buying_power=0.0)
        result = validate_decision("SELL", "BTC-USD", 1.0, 100.0, state)
        # With zero equity, the equity > 0 guard skips position size and heat
        assert result["valid"] is True

    def test_trade_exactly_at_buying_power_limit(self):
        """A BUY that exactly equals buying power should pass."""
        state = _make_state(equity=10000.0, buying_power=5000.0)
        result = validate_decision(
            "BUY",
            "BTC-USD",
            0.1,
            50000.0,
            state,
            max_position_pct=1.0,
            max_portfolio_heat=1.0,
        )
        assert result["valid"] is True

    def test_trade_just_over_buying_power(self):
        state = _make_state(equity=10000.0, buying_power=4999.99)
        result = validate_decision(
            "BUY",
            "BTC-USD",
            0.1,
            50000.0,
            state,
            max_position_pct=1.0,
            max_portfolio_heat=1.0,
        )
        assert result["valid"] is False

    def test_trade_exactly_at_position_limit(self):
        """Position exactly at the limit should pass."""
        state = _make_state(equity=10000.0, buying_power=10000.0)
        # 0.002 * 50000 = 100 / 10000 = 0.01 = 1%, which is at the 1% limit
        result = validate_decision(
            "BUY",
            "BTC-USD",
            0.002,
            50000.0,
            state,
            max_position_pct=0.01,
            max_portfolio_heat=1.0,
        )
        assert result["valid"] is True

    def test_trade_exactly_at_heat_limit(self):
        """Heat exactly at limit should pass (not strictly greater than)."""
        state = _make_state(equity=10000.0, buying_power=10000.0, heat=0.0)
        # qty*price/equity = 500/10000 = 0.05 => heat becomes 0.0 + 0.05 = 0.05
        result = validate_decision(
            "BUY",
            "BTC-USD",
            0.01,
            50000.0,
            state,
            max_position_pct=1.0,
            max_portfolio_heat=0.05,
        )
        assert result["valid"] is True

    def test_uses_default_limits(self):
        """Validate uses DEFAULT_MAX_POSITION_PCT and DEFAULT_MAX_PORTFOLIO_HEAT."""
        state = _make_state(equity=10000.0, buying_power=10000.0)
        # Default max_position_pct = 0.02, so 500/10000 = 5% > 2% should fail
        result = validate_decision("BUY", "BTC-USD", 0.01, 50000.0, state)
        assert result["valid"] is False
        assert any("too large" in e.lower() for e in result["errors"])


# ===========================================================================
# Integration-style tests: full pipeline
# ===========================================================================


class TestPortfolioStatePipeline:
    """End-to-end tests composing multiple compute functions."""

    def test_full_pipeline_with_mixed_positions(self):
        """Build a complete portfolio state from raw data."""
        portfolio = [
            _make_portfolio_row("BTC-USD", 0.05, 42000.0),
            _make_portfolio_row("ETH-USD", 1.0, 2200.0),
            _make_portfolio_row("AAPL-USD", 10.0, 150.0),
        ]
        trades = [
            _make_trade("BTC-USD", "BUY", 42000.0, 0.05, "t-1"),
            _make_trade("ETH-USD", "SELL", 2200.0, 1.0, "t-2"),
            _make_trade("AAPL-USD", "BUY", 150.0, 10.0, "t-3"),
        ]
        prices = {"BTC-USD": 44000.0, "ETH-USD": 2100.0, "AAPL-USD": 160.0}

        positions = compute_positions(portfolio, trades, prices)
        assert len(positions) == 3

        # BTC LONG profit: 0.05 * (44000-42000) = 100
        assert positions[0].unrealized_pnl == 100.0
        # ETH SHORT profit: 1.0 * (2200-2100) = 100
        assert positions[1].unrealized_pnl == 100.0
        # AAPL LONG profit: 10 * (160-150) = 100
        assert positions[2].unrealized_pnl == 100.0

        balance = compute_balance(
            positions,
            realized_pnl_today=50.0,
            total_realized_pnl=200.0,
            initial_capital=10000.0,
        )
        # equity = 10000 + 200 + 300 = 10500
        assert balance.total_equity == 10500.0
        assert balance.unrealized_pnl == 300.0

        risk = compute_risk_metrics(positions, balance.total_equity)
        assert risk.num_open_positions == 3
        assert "Crypto" in risk.sector_exposure
        assert "Other" in risk.sector_exposure
        assert risk.portfolio_heat > 0

        state = build_portfolio_state(positions, balance, risk, [])
        context = format_portfolio_context(state)
        assert "BTC-USD" in context
        assert "ETH-USD" in context
        assert "AAPL-USD" in context

    def test_validate_against_built_state(self):
        """Validate a trade against a portfolio built from compute functions."""
        positions = [
            _make_position(
                symbol="BTC-USD",
                quantity=0.1,
                entry_price=40000.0,
                current_price=42000.0,
                unrealized_pnl=200.0,
            ),
        ]
        balance = compute_balance(positions, 0.0, 0.0, 10000.0)
        risk = compute_risk_metrics(positions, balance.total_equity)
        state = build_portfolio_state(positions, balance, risk, [])

        # Small trade should pass
        result = validate_decision(
            "BUY",
            "ETH-USD",
            0.01,
            2000.0,
            state,
            max_position_pct=0.10,
            max_portfolio_heat=0.80,
        )
        assert result["valid"] is True

        # Large trade should fail
        result = validate_decision(
            "BUY", "ETH-USD", 5.0, 2000.0, state, max_position_pct=0.10
        )
        assert result["valid"] is False

    def test_portfolio_recovery_after_losses(self):
        """Simulate a portfolio that has realized losses but no open positions."""
        balance = compute_balance(
            [],
            realized_pnl_today=-500.0,
            total_realized_pnl=-2000.0,
            initial_capital=10000.0,
        )
        assert balance.total_equity == 8000.0
        assert balance.buying_power == 8000.0

        risk = compute_risk_metrics([], balance.total_equity)
        assert risk.portfolio_heat == 0.0
        assert risk.num_open_positions == 0

        state = build_portfolio_state([], balance, risk, [])

        # Should still be able to open new small positions
        result = validate_decision(
            "BUY",
            "BTC-USD",
            0.001,
            50000.0,
            state,
            max_position_pct=0.01,
            max_portfolio_heat=0.50,
        )
        assert result["valid"] is True
