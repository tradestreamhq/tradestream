"""Portfolio rebalancing engine.

Calculates and generates trades needed to move the current portfolio
allocation toward a target allocation, subject to constraints like
minimum trade size, max slippage, and risk limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class AllocationTarget:
    """Target allocation for a single asset."""

    symbol: str
    target_pct: float  # 0.0 to 1.0


@dataclass
class CurrentHolding:
    """Current holding for a single asset."""

    symbol: str
    quantity: float
    current_price: float
    market_value: float  # quantity * current_price


@dataclass
class RebalanceTrade:
    """A trade that the rebalancer wants to execute."""

    symbol: str
    side: TradeSide
    quantity: float
    estimated_price: float
    estimated_value: float  # quantity * estimated_price
    reason: str


@dataclass
class RebalanceConstraints:
    """Constraints applied when computing rebalance trades."""

    min_trade_value: float = 10.0  # ignore trades smaller than this
    max_trade_pct: float = 0.25  # max single trade as fraction of portfolio
    max_slippage_pct: float = 0.005  # 0.5% max expected slippage
    max_portfolio_heat: float = 0.50  # max fraction of capital in positions
    drift_threshold_pct: float = 0.02  # only rebalance if drift > 2%


@dataclass
class RebalanceReport:
    """Summary of a rebalancing run."""

    timestamp: str
    total_equity: float
    target_allocation: Dict[str, float]
    current_allocation: Dict[str, float]
    drift: Dict[str, float]  # target - current per asset
    trades: List[RebalanceTrade]
    skipped: List[Dict[str, Any]]  # trades skipped due to constraints
    cash_before: float
    cash_after_estimate: float


def compute_current_allocation(
    holdings: List[CurrentHolding],
    cash: float,
) -> tuple[float, Dict[str, float]]:
    """Compute current allocation percentages.

    Returns (total_equity, allocation_dict) where allocation_dict maps
    symbol -> fraction of total equity.
    """
    total_market_value = sum(h.market_value for h in holdings)
    total_equity = total_market_value + cash

    if total_equity <= 0:
        return 0.0, {}

    allocation = {}
    for h in holdings:
        allocation[h.symbol] = h.market_value / total_equity

    return total_equity, allocation


def compute_drift(
    targets: List[AllocationTarget],
    current_allocation: Dict[str, float],
) -> Dict[str, float]:
    """Compute drift between target and current allocation.

    Returns dict mapping symbol -> (target_pct - current_pct).
    Positive drift means we need to buy, negative means sell.
    """
    drift = {}
    for target in targets:
        current = current_allocation.get(target.symbol, 0.0)
        drift[target.symbol] = target.target_pct - current

    # Assets held but not in targets should be sold entirely
    target_symbols = {t.symbol for t in targets}
    for symbol, pct in current_allocation.items():
        if symbol not in target_symbols:
            drift[symbol] = -pct

    return drift


def compute_rebalance_trades(
    targets: List[AllocationTarget],
    holdings: List[CurrentHolding],
    cash: float,
    current_prices: Dict[str, float],
    constraints: Optional[RebalanceConstraints] = None,
) -> RebalanceReport:
    """Compute trades needed to rebalance toward target allocation.

    Args:
        targets: Desired allocation targets (should sum to <= 1.0).
        holdings: Current portfolio holdings.
        cash: Available cash balance.
        current_prices: Current market prices keyed by symbol.
        constraints: Trading constraints to apply.

    Returns:
        RebalanceReport with computed trades and metadata.
    """
    if constraints is None:
        constraints = RebalanceConstraints()

    total_equity, current_alloc = compute_current_allocation(holdings, cash)
    target_alloc = {t.symbol: t.target_pct for t in targets}
    drift = compute_drift(targets, current_alloc)

    trades: List[RebalanceTrade] = []
    skipped: List[Dict[str, Any]] = []

    if total_equity <= 0:
        return RebalanceReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_equity=0.0,
            target_allocation=target_alloc,
            current_allocation=current_alloc,
            drift=drift,
            trades=[],
            skipped=[],
            cash_before=cash,
            cash_after_estimate=cash,
        )

    # Sort by drift: sell first (negative drift), then buy (positive drift).
    # This frees up cash before we try to buy.
    sorted_symbols = sorted(drift.keys(), key=lambda s: drift[s])

    estimated_cash = cash
    holdings_by_symbol = {h.symbol: h for h in holdings}

    for symbol in sorted_symbols:
        symbol_drift = drift[symbol]

        # Skip if drift is below threshold
        if abs(symbol_drift) < constraints.drift_threshold_pct:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "drift below threshold",
                    "drift": round(symbol_drift, 6),
                }
            )
            continue

        price = current_prices.get(symbol)
        if price is None or price <= 0:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "no valid price available",
                }
            )
            continue

        # Desired dollar change
        desired_value_change = symbol_drift * total_equity

        # Apply max trade size constraint
        max_trade_value = constraints.max_trade_pct * total_equity
        clamped_value = max(
            -max_trade_value, min(max_trade_value, desired_value_change)
        )

        # Convert to quantity
        quantity = abs(clamped_value) / price

        if quantity <= 0:
            continue

        trade_value = quantity * price

        # Skip trades below minimum size
        if trade_value < constraints.min_trade_value:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "below minimum trade size",
                    "trade_value": round(trade_value, 2),
                }
            )
            continue

        if clamped_value > 0:
            # BUY: check we have enough cash
            slippage_cost = trade_value * constraints.max_slippage_pct
            total_cost = trade_value + slippage_cost

            if total_cost > estimated_cash:
                # Reduce to what we can afford
                affordable_value = estimated_cash / (1 + constraints.max_slippage_pct)
                if affordable_value < constraints.min_trade_value:
                    skipped.append(
                        {
                            "symbol": symbol,
                            "reason": "insufficient cash",
                            "needed": round(total_cost, 2),
                            "available": round(estimated_cash, 2),
                        }
                    )
                    continue
                quantity = affordable_value / price
                trade_value = quantity * price
                slippage_cost = trade_value * constraints.max_slippage_pct
                total_cost = trade_value + slippage_cost

            trades.append(
                RebalanceTrade(
                    symbol=symbol,
                    side=TradeSide.BUY,
                    quantity=round(quantity, 8),
                    estimated_price=price,
                    estimated_value=round(trade_value, 2),
                    reason=f"under-allocated by {abs(symbol_drift)*100:.1f}%",
                )
            )
            estimated_cash -= total_cost

        else:
            # SELL: check we hold enough
            holding = holdings_by_symbol.get(symbol)
            available_qty = holding.quantity if holding else 0.0

            sell_qty = min(quantity, available_qty)
            if sell_qty <= 0:
                skipped.append(
                    {
                        "symbol": symbol,
                        "reason": "no position to sell",
                    }
                )
                continue

            sell_value = sell_qty * price
            if sell_value < constraints.min_trade_value and sell_qty < available_qty:
                skipped.append(
                    {
                        "symbol": symbol,
                        "reason": "below minimum trade size",
                        "trade_value": round(sell_value, 2),
                    }
                )
                continue

            trades.append(
                RebalanceTrade(
                    symbol=symbol,
                    side=TradeSide.SELL,
                    quantity=round(sell_qty, 8),
                    estimated_price=price,
                    estimated_value=round(sell_value, 2),
                    reason=f"over-allocated by {abs(symbol_drift)*100:.1f}%",
                )
            )
            net_proceeds = sell_value * (1 - constraints.max_slippage_pct)
            estimated_cash += net_proceeds

    return RebalanceReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_equity=round(total_equity, 2),
        target_allocation={k: round(v, 6) for k, v in target_alloc.items()},
        current_allocation={k: round(v, 6) for k, v in current_alloc.items()},
        drift={k: round(v, 6) for k, v in drift.items()},
        trades=trades,
        skipped=skipped,
        cash_before=round(cash, 2),
        cash_after_estimate=round(estimated_cash, 2),
    )


def format_rebalance_report(report: RebalanceReport) -> str:
    """Format a rebalance report as human-readable text."""
    lines = [
        "PORTFOLIO REBALANCE REPORT",
        f"Timestamp: {report.timestamp}",
        f"Total Equity: ${report.total_equity:,.2f}",
        "",
        "Target vs Current Allocation:",
    ]

    all_symbols = sorted(
        set(
            list(report.target_allocation.keys())
            + list(report.current_allocation.keys())
        )
    )
    for symbol in all_symbols:
        target = report.target_allocation.get(symbol, 0.0) * 100
        current = report.current_allocation.get(symbol, 0.0) * 100
        drift_val = report.drift.get(symbol, 0.0) * 100
        sign = "+" if drift_val >= 0 else ""
        lines.append(
            f"  {symbol}: target={target:.1f}% current={current:.1f}%"
            f" drift={sign}{drift_val:.1f}%"
        )

    lines.append("")
    lines.append(f"Trades ({len(report.trades)}):")
    if not report.trades:
        lines.append("  No trades needed")
    else:
        for t in report.trades:
            lines.append(
                f"  {t.side.value} {t.quantity:.8f} {t.symbol} "
                f"@ ~${t.estimated_price:,.2f} (${t.estimated_value:,.2f})"
                f" — {t.reason}"
            )

    if report.skipped:
        lines.append("")
        lines.append(f"Skipped ({len(report.skipped)}):")
        for s in report.skipped:
            lines.append(f"  {s['symbol']}: {s['reason']}")

    lines.append("")
    lines.append(
        f"Cash: ${report.cash_before:,.2f} -> ~${report.cash_after_estimate:,.2f}"
    )

    return "\n".join(lines)
