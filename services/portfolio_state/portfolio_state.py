"""Portfolio state computation and risk metrics.

Aggregates positions, balance, and risk data into a unified portfolio state
that can be injected into decision agent prompts.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    opened_at: str
    trade_id: Optional[str] = None


@dataclass
class AccountBalance:
    total_equity: float
    available_cash: float
    buying_power: float
    margin_used: float
    margin_available: float
    unrealized_pnl: float
    realized_pnl_today: float


@dataclass
class RiskMetrics:
    portfolio_heat: float  # % of capital at risk (in open positions)
    max_position_pct: float  # largest position as % of portfolio
    max_position_symbol: str
    num_open_positions: int
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    daily_drawdown: float = 0.0


@dataclass
class PortfolioState:
    balance: AccountBalance
    positions: List[Position]
    risk_metrics: RiskMetrics
    recent_trades: List[Dict[str, Any]]
    as_of: str


# Default account config for paper trading
DEFAULT_INITIAL_CAPITAL = 10000.0
DEFAULT_MAX_POSITION_PCT = 0.02
DEFAULT_MAX_PORTFOLIO_HEAT = 0.50


def compute_positions(
    portfolio_rows: List[Dict[str, Any]],
    open_trades: List[Dict[str, Any]],
    current_prices: Dict[str, float],
) -> List[Position]:
    """Build position objects from portfolio rows and current prices."""
    positions = []
    # Map trades by symbol for side/opened_at info
    trades_by_symbol: Dict[str, Dict[str, Any]] = {}
    for trade in open_trades:
        sym = trade["symbol"]
        if sym not in trades_by_symbol:
            trades_by_symbol[sym] = trade

    for row in portfolio_rows:
        symbol = row["symbol"]
        qty = row["quantity"]
        entry_price = row["avg_entry_price"]
        current_price = current_prices.get(symbol, entry_price)

        unrealized_pnl = qty * (current_price - entry_price)
        pnl_pct = (
            ((current_price - entry_price) / entry_price * 100)
            if entry_price > 0
            else 0.0
        )

        trade_info = trades_by_symbol.get(symbol, {})
        side = trade_info.get("side", "BUY")
        opened_at = trade_info.get("opened_at", row.get("updated_at", ""))
        trade_id = trade_info.get("trade_id")

        # For SHORT positions, P&L is inverted
        if side == "SELL":
            unrealized_pnl = qty * (entry_price - current_price)
            pnl_pct = (
                ((entry_price - current_price) / entry_price * 100)
                if entry_price > 0
                else 0.0
            )

        positions.append(
            Position(
                symbol=symbol,
                side="LONG" if side == "BUY" else "SHORT",
                quantity=qty,
                entry_price=entry_price,
                current_price=current_price,
                unrealized_pnl=round(unrealized_pnl, 8),
                unrealized_pnl_percent=round(pnl_pct, 2),
                opened_at=opened_at,
                trade_id=trade_id,
            )
        )

    return positions


def compute_balance(
    positions: List[Position],
    realized_pnl_today: float,
    total_realized_pnl: float,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> AccountBalance:
    """Compute account balance from positions and trade history."""
    total_unrealized = sum(p.unrealized_pnl for p in positions)
    margin_used = sum(p.quantity * p.entry_price for p in positions)

    total_equity = initial_capital + total_realized_pnl + total_unrealized
    available_cash = total_equity - margin_used
    buying_power = max(0.0, available_cash)
    margin_available = max(0.0, total_equity - margin_used)

    return AccountBalance(
        total_equity=round(total_equity, 2),
        available_cash=round(available_cash, 2),
        buying_power=round(buying_power, 2),
        margin_used=round(margin_used, 2),
        margin_available=round(margin_available, 2),
        unrealized_pnl=round(total_unrealized, 2),
        realized_pnl_today=round(realized_pnl_today, 2),
    )


def compute_risk_metrics(
    positions: List[Position],
    total_equity: float,
) -> RiskMetrics:
    """Calculate risk metrics from current positions."""
    if not positions or total_equity <= 0:
        return RiskMetrics(
            portfolio_heat=0.0,
            max_position_pct=0.0,
            max_position_symbol="",
            num_open_positions=0,
        )

    position_values = []
    sector_exposure: Dict[str, float] = {}

    for p in positions:
        value = p.quantity * p.current_price
        pct = (value / total_equity) * 100 if total_equity > 0 else 0.0
        position_values.append((p.symbol, pct))

        # Simple sector classification based on symbol suffix
        sector = _classify_sector(p.symbol)
        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + pct

    # Portfolio heat = total capital allocated to open positions
    total_heat = sum(pct for _, pct in position_values)

    # Max position
    max_sym, max_pct = max(position_values, key=lambda x: x[1])

    return RiskMetrics(
        portfolio_heat=round(total_heat, 2),
        max_position_pct=round(max_pct, 2),
        max_position_symbol=max_sym,
        num_open_positions=len(positions),
        sector_exposure={k: round(v, 2) for k, v in sector_exposure.items()},
    )


def _classify_sector(symbol: str) -> str:
    """Classify a symbol into a broad sector."""
    crypto_symbols = {
        "BTC",
        "ETH",
        "SOL",
        "ADA",
        "DOT",
        "AVAX",
        "MATIC",
        "LINK",
        "UNI",
        "DOGE",
        "XRP",
        "BNB",
    }
    base = symbol.split("-")[0].split("/")[0].upper()
    if base in crypto_symbols:
        return "Crypto"
    return "Other"


def build_portfolio_state(
    positions: List[Position],
    balance: AccountBalance,
    risk_metrics: RiskMetrics,
    recent_trades: List[Dict[str, Any]],
) -> PortfolioState:
    """Assemble the full portfolio state."""
    return PortfolioState(
        balance=balance,
        positions=positions,
        risk_metrics=risk_metrics,
        recent_trades=recent_trades,
        as_of=datetime.now(timezone.utc).isoformat(),
    )


def format_portfolio_context(state: PortfolioState) -> str:
    """Format portfolio state as a text context block for decision prompts."""
    lines = ["CURRENT PORTFOLIO STATE:", ""]

    # Account section
    b = state.balance
    pnl_sign = "+" if b.realized_pnl_today >= 0 else ""
    pnl_pct = (
        (b.realized_pnl_today / b.total_equity * 100) if b.total_equity > 0 else 0.0
    )
    lines.append("Account:")
    lines.append(f"- Balance: ${b.total_equity:,.2f}")
    lines.append(f"- Available to trade: ${b.buying_power:,.2f}")
    lines.append(f"- Margin used: ${b.margin_used:,.2f}")
    lines.append(
        f"- Today's P&L: {pnl_sign}${b.realized_pnl_today:,.2f} ({pnl_sign}{pnl_pct:.1f}%)"
    )
    lines.append(f"- Unrealized P&L: ${b.unrealized_pnl:,.2f}")
    lines.append("")

    # Positions section
    n = len(state.positions)
    lines.append(f"Open Positions ({n}):")
    if n == 0:
        lines.append("- No open positions")
    else:
        for i, p in enumerate(state.positions, 1):
            pnl_sign = "+" if p.unrealized_pnl >= 0 else ""
            pct_sign = "+" if p.unrealized_pnl_percent >= 0 else ""
            lines.append(
                f"{i}. {p.symbol}: {p.side} {p.quantity} @ ${p.entry_price:,.2f} "
                f"-> Currently {pct_sign}{p.unrealized_pnl_percent:.1f}% "
                f"({pnl_sign}${p.unrealized_pnl:,.2f})"
            )
    lines.append("")

    # Risk section
    r = state.risk_metrics
    lines.append("Risk Status:")
    lines.append(f"- Portfolio heat: {r.portfolio_heat:.1f}%")
    if r.max_position_symbol:
        lines.append(
            f"- Largest position: {r.max_position_symbol} at {r.max_position_pct:.1f}% of portfolio"
        )
    if r.sector_exposure:
        exposure_parts = [f"{k}: {v:.1f}%" for k, v in r.sector_exposure.items()]
        lines.append(f"- Sector exposure: {', '.join(exposure_parts)}")
    lines.append("")

    # Recent activity
    lines.append("Recent Activity:")
    if not state.recent_trades:
        lines.append("- No recent trades")
    else:
        for trade in state.recent_trades[:5]:
            action = "Bought" if trade.get("side") == "BUY" else "Sold"
            pnl_str = ""
            if trade.get("pnl") is not None and trade.get("pnl") != 0:
                pnl_val = trade["pnl"]
                pnl_sign = "+" if pnl_val >= 0 else ""
                pnl_str = f" ({pnl_sign}${pnl_val:,.2f})"
            lines.append(
                f"- {action} {trade.get('quantity', '?')} {trade.get('symbol', '?')} "
                f"@ ${trade.get('exit_price') or trade.get('entry_price', 0):,.2f}{pnl_str}"
            )

    return "\n".join(lines)


def validate_decision(
    action: str,
    symbol: str,
    quantity: float,
    price: float,
    state: PortfolioState,
    max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
    max_portfolio_heat: float = DEFAULT_MAX_PORTFOLIO_HEAT,
) -> Dict[str, Any]:
    """Validate a proposed trade against portfolio constraints.

    Returns:
        Dict with "valid" bool and "errors" list.
    """
    errors = []
    required_capital = quantity * price

    # Check buying power
    if action == "BUY" and required_capital > state.balance.buying_power:
        errors.append(
            f"Insufficient buying power: need ${required_capital:,.2f}, "
            f"have ${state.balance.buying_power:,.2f}"
        )

    # Check position size limit
    if state.balance.total_equity > 0:
        position_pct = required_capital / state.balance.total_equity
        if position_pct > max_position_pct:
            errors.append(
                f"Position too large: {position_pct:.1%} exceeds "
                f"{max_position_pct:.1%} limit"
            )

        # Check portfolio heat
        if action == "BUY":
            new_heat = (state.risk_metrics.portfolio_heat / 100) + position_pct
            if new_heat > max_portfolio_heat:
                errors.append(
                    f"Would exceed portfolio heat limit: "
                    f"{new_heat:.1%} > {max_portfolio_heat:.1%}"
                )

    return {"valid": len(errors) == 0, "errors": errors}
