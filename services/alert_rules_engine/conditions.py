"""Condition evaluators for alert rules.

Each evaluator takes market/portfolio state and returns (triggered, message, context).
"""

from services.alert_rules_engine.models import AlertCondition, ConditionType


def evaluate_condition(
    condition: AlertCondition,
    market_data: dict,
    portfolio_data: dict,
    signal_data: dict | None = None,
    regime_data: dict | None = None,
) -> tuple[bool, str, dict]:
    """Evaluate an alert condition against current state.

    Args:
        condition: The condition to evaluate.
        market_data: Current market prices keyed by symbol.
            Example: {"BTC/USD": {"price": 50000.0, ...}}
        portfolio_data: Current portfolio metrics.
            Example: {"daily_drawdown": 0.03, "portfolio_heat": 0.15, ...}
        signal_data: Most recent signal event (if any).
        regime_data: Current market regime info (if any).

    Returns:
        Tuple of (triggered, human_message, context_dict).
    """
    evaluator = _EVALUATORS.get(condition.condition_type)
    if evaluator is None:
        return False, f"Unknown condition type: {condition.condition_type}", {}
    return evaluator(condition.params, market_data, portfolio_data, signal_data, regime_data)


def _eval_price_above(params, market_data, portfolio_data, signal_data, regime_data):
    symbol = params.get("symbol", "")
    threshold = float(params.get("threshold", 0))
    price_info = market_data.get(symbol, {})
    price = float(price_info.get("price", 0))
    if price > 0 and price > threshold:
        msg = f"{symbol} price ${price:,.2f} crossed above ${threshold:,.2f}"
        return True, msg, {"symbol": symbol, "price": price, "threshold": threshold}
    return False, "", {}


def _eval_price_below(params, market_data, portfolio_data, signal_data, regime_data):
    symbol = params.get("symbol", "")
    threshold = float(params.get("threshold", 0))
    price_info = market_data.get(symbol, {})
    price = float(price_info.get("price", 0))
    if price > 0 and price < threshold:
        msg = f"{symbol} price ${price:,.2f} dropped below ${threshold:,.2f}"
        return True, msg, {"symbol": symbol, "price": price, "threshold": threshold}
    return False, "", {}


def _eval_drawdown_exceeds(params, market_data, portfolio_data, signal_data, regime_data):
    threshold = float(params.get("threshold", 0))
    drawdown = float(portfolio_data.get("daily_drawdown", 0))
    if drawdown > threshold:
        pct = drawdown * 100
        thresh_pct = threshold * 100
        msg = f"Portfolio drawdown {pct:.1f}% exceeds {thresh_pct:.1f}% threshold"
        return True, msg, {"drawdown": drawdown, "threshold": threshold}
    return False, "", {}


def _eval_portfolio_heat_exceeds(params, market_data, portfolio_data, signal_data, regime_data):
    threshold = float(params.get("threshold", 0))
    heat = float(portfolio_data.get("portfolio_heat", 0))
    if heat > threshold:
        pct = heat * 100
        thresh_pct = threshold * 100
        msg = f"Portfolio heat {pct:.1f}% exceeds {thresh_pct:.1f}% threshold"
        return True, msg, {"portfolio_heat": heat, "threshold": threshold}
    return False, "", {}


def _eval_signal_match(params, market_data, portfolio_data, signal_data, regime_data):
    if not signal_data:
        return False, "", {}
    symbol_filter = params.get("symbol", "")
    action_filter = params.get("action", "")
    min_confidence = float(params.get("min_confidence", 0))

    signal_symbol = signal_data.get("symbol", "")
    signal_action = signal_data.get("action", "")
    signal_confidence = float(signal_data.get("confidence", 0))

    if symbol_filter and signal_symbol != symbol_filter:
        return False, "", {}
    if action_filter and signal_action != action_filter:
        return False, "", {}
    if signal_confidence < min_confidence:
        return False, "", {}

    msg = f"Signal matched: {signal_action} {signal_symbol} (confidence {signal_confidence:.0%})"
    return True, msg, {
        "signal_symbol": signal_symbol,
        "signal_action": signal_action,
        "signal_confidence": signal_confidence,
    }


def _eval_regime_change(params, market_data, portfolio_data, signal_data, regime_data):
    if not regime_data:
        return False, "", {}
    current = regime_data.get("current_regime", "")
    previous = regime_data.get("previous_regime", "")
    from_regime = params.get("from_regime", "")
    to_regime = params.get("to_regime", "")

    if not current or current == previous:
        return False, "", {}
    if from_regime and previous != from_regime:
        return False, "", {}
    if to_regime and current != to_regime:
        return False, "", {}

    msg = f"Market regime changed from '{previous}' to '{current}'"
    return True, msg, {
        "previous_regime": previous,
        "current_regime": current,
    }


_EVALUATORS = {
    ConditionType.PRICE_ABOVE: _eval_price_above,
    ConditionType.PRICE_BELOW: _eval_price_below,
    ConditionType.DRAWDOWN_EXCEEDS: _eval_drawdown_exceeds,
    ConditionType.PORTFOLIO_HEAT_EXCEEDS: _eval_portfolio_heat_exceeds,
    ConditionType.SIGNAL_MATCH: _eval_signal_match,
    ConditionType.REGIME_CHANGE: _eval_regime_change,
}
