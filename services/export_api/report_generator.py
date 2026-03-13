"""Report generator for strategy performance, trade recaps, and risk exposure.

Produces PDF-ready JSON structures that can be rendered by a frontend or
converted to PDF via a separate rendering service.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def strategy_performance_summary(
    implementation_id: str,
    performance_rows: List[Dict[str, Any]],
    signal_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a strategy performance summary report.

    Returns a structured JSON object suitable for PDF rendering.
    """
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    total_pnl = 0.0
    sharpe_values = []
    max_drawdown_values = []

    for row in performance_rows:
        total_trades += row.get("total_trades", 0)
        winning_trades += row.get("winning_trades", 0)
        losing_trades += row.get("losing_trades", 0)
        if row.get("sharpe_ratio") is not None:
            sharpe_values.append(float(row["sharpe_ratio"]))
        if row.get("max_drawdown") is not None:
            max_drawdown_values.append(float(row["max_drawdown"]))

    for signal in signal_rows:
        if signal.get("pnl") is not None:
            total_pnl += float(signal["pnl"])

    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
    avg_sharpe = sum(sharpe_values) / len(sharpe_values) if sharpe_values else None
    worst_drawdown = min(max_drawdown_values) if max_drawdown_values else None

    return {
        "report_type": "strategy_performance_summary",
        "implementation_id": implementation_id,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 4),
            "total_pnl": round(total_pnl, 8),
            "avg_sharpe_ratio": (
                round(avg_sharpe, 4) if avg_sharpe is not None else None
            ),
            "worst_max_drawdown": (
                round(worst_drawdown, 4) if worst_drawdown is not None else None
            ),
        },
        "periods": [
            {
                "period_start": str(r.get("period_start", "")),
                "period_end": str(r.get("period_end", "")),
                "sharpe_ratio": _to_float(r.get("sharpe_ratio")),
                "sortino_ratio": _to_float(r.get("sortino_ratio")),
                "win_rate": _to_float(r.get("win_rate")),
                "profit_factor": _to_float(r.get("profit_factor")),
                "max_drawdown": _to_float(r.get("max_drawdown")),
                "total_trades": r.get("total_trades", 0),
                "total_return": _to_float(r.get("total_return")),
            }
            for r in performance_rows
        ],
    }


def trade_recap(
    signal_rows: List[Dict[str, Any]],
    period_label: str,
) -> Dict[str, Any]:
    """Generate a periodic trade recap report (weekly/monthly).

    Args:
        signal_rows: Signals with outcome data for the period.
        period_label: Human-readable period label (e.g., "2026-W10", "2026-02").
    """
    total = len(signal_rows)
    wins = sum(1 for s in signal_rows if s.get("outcome") == "PROFIT")
    losses = sum(1 for s in signal_rows if s.get("outcome") == "LOSS")
    breakeven = sum(1 for s in signal_rows if s.get("outcome") == "BREAKEVEN")
    pending = total - wins - losses - breakeven

    total_pnl = sum(float(s["pnl"]) for s in signal_rows if s.get("pnl") is not None)
    pnl_values = [float(s["pnl"]) for s in signal_rows if s.get("pnl") is not None]
    best_trade = max(pnl_values) if pnl_values else None
    worst_trade = min(pnl_values) if pnl_values else None

    instruments = {}
    for s in signal_rows:
        inst = s.get("instrument", "unknown")
        if inst not in instruments:
            instruments[inst] = {"count": 0, "pnl": 0.0}
        instruments[inst]["count"] += 1
        if s.get("pnl") is not None:
            instruments[inst]["pnl"] += float(s["pnl"])

    # Round instrument pnl values
    for inst_data in instruments.values():
        inst_data["pnl"] = round(inst_data["pnl"], 8)

    return {
        "report_type": "trade_recap",
        "period": period_label,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "pending": pending,
            "win_rate": round(wins / total, 4) if total > 0 else 0.0,
            "total_pnl": round(total_pnl, 8),
            "best_trade_pnl": round(best_trade, 8) if best_trade is not None else None,
            "worst_trade_pnl": (
                round(worst_trade, 8) if worst_trade is not None else None
            ),
        },
        "by_instrument": instruments,
        "trades": [
            {
                "id": str(s.get("id", "")),
                "instrument": s.get("instrument"),
                "signal_type": s.get("signal_type"),
                "price": _to_float(s.get("price")),
                "exit_price": _to_float(s.get("exit_price")),
                "pnl": _to_float(s.get("pnl")),
                "outcome": s.get("outcome"),
                "created_at": str(s.get("created_at", "")),
            }
            for s in signal_rows
        ],
    }


def risk_exposure_report(
    performance_rows: List[Dict[str, Any]],
    open_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a risk exposure report.

    Args:
        performance_rows: Recent strategy_performance records.
        open_trades: Currently open paper trades.
    """
    # Aggregate risk metrics from performance data
    drawdowns = [
        float(r["max_drawdown"])
        for r in performance_rows
        if r.get("max_drawdown") is not None
    ]
    volatilities = [
        float(r["volatility"])
        for r in performance_rows
        if r.get("volatility") is not None
    ]
    var_values = [
        float(r["var_95"]) for r in performance_rows if r.get("var_95") is not None
    ]

    # Open position exposure
    position_exposure = {}
    total_exposure = 0.0
    for trade in open_trades:
        symbol = trade.get("symbol", "unknown")
        qty = float(trade.get("quantity", 0))
        entry = float(trade.get("entry_price", 0))
        notional = qty * entry
        total_exposure += notional
        if symbol not in position_exposure:
            position_exposure[symbol] = {"notional": 0.0, "positions": 0}
        position_exposure[symbol]["notional"] += notional
        position_exposure[symbol]["positions"] += 1

    # Round notional values
    for sym_data in position_exposure.values():
        sym_data["notional"] = round(sym_data["notional"], 8)

    return {
        "report_type": "risk_exposure",
        "generated_at": datetime.utcnow().isoformat(),
        "risk_metrics": {
            "worst_max_drawdown": round(min(drawdowns), 4) if drawdowns else None,
            "avg_max_drawdown": (
                round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else None
            ),
            "avg_volatility": (
                round(sum(volatilities) / len(volatilities), 4)
                if volatilities
                else None
            ),
            "worst_var_95": round(min(var_values), 4) if var_values else None,
        },
        "open_positions": {
            "total_notional_exposure": round(total_exposure, 8),
            "position_count": len(open_trades),
            "by_symbol": position_exposure,
        },
    }


def _to_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
