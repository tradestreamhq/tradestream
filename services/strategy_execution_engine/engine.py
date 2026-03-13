"""Strategy Execution Engine — evaluates conditions and emits signals."""

import logging
import math
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

import yaml

from services.strategy_execution_engine.models import (
    Candle,
    ConditionConfig,
    ExecutionContext,
    IndicatorConfig,
    PositionState,
    Signal,
    SignalDirection,
    StrategyConfig,
    StrategyState,
    StrategyStatus,
)

logger = logging.getLogger(__name__)


class IndicatorComputer:
    """Computes indicator values from candle history."""

    def __init__(self, candle_history: List[Candle]):
        self._candles = candle_history

    def _closes(self) -> List[float]:
        return [c.close for c in self._candles]

    def _highs(self) -> List[float]:
        return [c.high for c in self._candles]

    def _lows(self) -> List[float]:
        return [c.low for c in self._candles]

    def _volumes(self) -> List[float]:
        return [c.volume for c in self._candles]

    def compute(
        self,
        indicators: List[IndicatorConfig],
        parameter_values: Dict[str, float],
    ) -> Dict[str, List[float]]:
        """Compute all indicator series, returning {indicator_id: [values]}."""
        results: Dict[str, List[float]] = {}

        # Base series
        results["close"] = self._closes()
        results["high"] = self._highs()
        results["low"] = self._lows()
        results["volume"] = self._volumes()
        results["open"] = [c.open for c in self._candles]

        for ind in indicators:
            input_series = results.get(ind.input, results.get("close", []))
            params = self._resolve_params(ind.params, parameter_values)
            series = self._compute_indicator(ind.type, input_series, params)
            results[ind.id] = series

        return results

    def _resolve_params(
        self,
        params: Dict[str, Any],
        parameter_values: Dict[str, float],
    ) -> Dict[str, Any]:
        """Resolve ${paramName} references in indicator params."""
        resolved = {}
        for key, val in params.items():
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                param_name = val[2:-1]
                resolved[key] = parameter_values.get(param_name, 0)
            else:
                resolved[key] = val
        return resolved

    def _compute_indicator(
        self,
        indicator_type: str,
        input_series: List[float],
        params: Dict[str, Any],
    ) -> List[float]:
        """Compute a single indicator type over an input series."""
        compute_fn = _INDICATOR_REGISTRY.get(indicator_type.upper())
        if compute_fn is None:
            logger.warning("Unknown indicator type: %s", indicator_type)
            return input_series[:]  # pass-through
        return compute_fn(input_series, params, self)


def _compute_sma(
    series: List[float], params: Dict[str, Any], _computer: IndicatorComputer
) -> List[float]:
    period = int(params.get("period", 20))
    result = [0.0] * len(series)
    for i in range(len(series)):
        if i < period - 1:
            result[i] = sum(series[: i + 1]) / (i + 1)
        else:
            result[i] = sum(series[i - period + 1 : i + 1]) / period
    return result


def _compute_ema(
    series: List[float], params: Dict[str, Any], _computer: IndicatorComputer
) -> List[float]:
    period = int(params.get("period", 20))
    if not series:
        return []
    multiplier = 2.0 / (period + 1)
    result = [series[0]]
    for i in range(1, len(series)):
        result.append(series[i] * multiplier + result[-1] * (1.0 - multiplier))
    return result


def _compute_rsi(
    series: List[float], params: Dict[str, Any], _computer: IndicatorComputer
) -> List[float]:
    period = int(params.get("period", 14))
    if len(series) < 2:
        return [50.0] * len(series)

    result = [50.0]
    gains = 0.0
    losses = 0.0

    for i in range(1, min(period + 1, len(series))):
        delta = series[i] - series[i - 1]
        if delta > 0:
            gains += delta
        else:
            losses -= delta
        avg_gain = gains / i
        avg_loss = losses / i
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    if period < len(series):
        avg_gain = gains / period
        avg_loss = losses / period

        for i in range(period + 1, len(series)):
            delta = series[i] - series[i - 1]
            if delta > 0:
                avg_gain = (avg_gain * (period - 1) + delta) / period
                avg_loss = (avg_loss * (period - 1)) / period
            else:
                avg_gain = (avg_gain * (period - 1)) / period
                avg_loss = (avg_loss * (period - 1) - delta) / period

            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100.0 - 100.0 / (1.0 + rs))

    return result


def _compute_macd(
    series: List[float], params: Dict[str, Any], _computer: IndicatorComputer
) -> List[float]:
    short_period = int(params.get("shortPeriod", 12))
    long_period = int(params.get("longPeriod", 26))
    short_ema = _compute_ema(series, {"period": short_period}, _computer)
    long_ema = _compute_ema(series, {"period": long_period}, _computer)
    return [s - l for s, l in zip(short_ema, long_ema)]


def _compute_obv(
    series: List[float], params: Dict[str, Any], computer: IndicatorComputer
) -> List[float]:
    volumes = computer._volumes()
    if not series or not volumes:
        return []
    result = [0.0]
    for i in range(1, len(series)):
        if series[i] > series[i - 1]:
            result.append(result[-1] + volumes[i])
        elif series[i] < series[i - 1]:
            result.append(result[-1] - volumes[i])
        else:
            result.append(result[-1])
    return result


def _compute_close(
    series: List[float], params: Dict[str, Any], computer: IndicatorComputer
) -> List[float]:
    return computer._closes()


def _compute_constant(
    series: List[float], params: Dict[str, Any], _computer: IndicatorComputer
) -> List[float]:
    value = float(params.get("value", 0))
    return [value] * len(series)


_INDICATOR_REGISTRY: Dict[str, Callable] = {
    "SMA": _compute_sma,
    "EMA": _compute_ema,
    "RSI": _compute_rsi,
    "MACD": _compute_macd,
    "OBV": _compute_obv,
    "CLOSE": _compute_close,
    "CONSTANT": _compute_constant,
}


class ConditionEvaluator:
    """Evaluates entry/exit conditions against indicator values."""

    def evaluate(
        self,
        conditions: List[ConditionConfig],
        indicator_values: Dict[str, List[float]],
        parameter_values: Dict[str, float],
    ) -> bool:
        """Return True if ALL conditions are met (AND logic) at the latest bar."""
        if not conditions:
            return False
        return all(
            self._evaluate_one(cond, indicator_values, parameter_values)
            for cond in conditions
        )

    def _evaluate_one(
        self,
        cond: ConditionConfig,
        indicator_values: Dict[str, List[float]],
        parameter_values: Dict[str, float],
    ) -> bool:
        series = indicator_values.get(cond.indicator, [])
        if len(series) < 2:
            return False

        cond_type = cond.type.upper()

        if cond_type == "CROSSED_UP":
            return self._crossed_up(series, cond.params, indicator_values)
        elif cond_type == "CROSSED_DOWN":
            return self._crossed_down(series, cond.params, indicator_values)
        elif cond_type == "OVER":
            return self._over(series, cond.params, indicator_values, parameter_values)
        elif cond_type == "UNDER":
            return self._under(series, cond.params, indicator_values, parameter_values)
        else:
            logger.warning("Unknown condition type: %s", cond_type)
            return False

    def _get_other_series(
        self,
        params: Dict[str, Any],
        indicator_values: Dict[str, List[float]],
    ) -> Optional[List[float]]:
        crosses_id = params.get("crosses")
        if crosses_id:
            return indicator_values.get(crosses_id)
        return None

    def _get_threshold(
        self,
        params: Dict[str, Any],
        parameter_values: Dict[str, float],
    ) -> Optional[float]:
        value = params.get("value")
        if value is None:
            other = params.get("other")
            if other:
                return None  # use other indicator
            return None
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            param_name = value[2:-1]
            return parameter_values.get(param_name)
        return float(value)

    def _crossed_up(
        self,
        series: List[float],
        params: Dict[str, Any],
        indicator_values: Dict[str, List[float]],
    ) -> bool:
        other = self._get_other_series(params, indicator_values)
        if other is None or len(other) < 2:
            return False
        prev_a, curr_a = series[-2], series[-1]
        prev_b, curr_b = other[-2], other[-1]
        return prev_a <= prev_b and curr_a > curr_b

    def _crossed_down(
        self,
        series: List[float],
        params: Dict[str, Any],
        indicator_values: Dict[str, List[float]],
    ) -> bool:
        other = self._get_other_series(params, indicator_values)
        if other is None or len(other) < 2:
            return False
        prev_a, curr_a = series[-2], series[-1]
        prev_b, curr_b = other[-2], other[-1]
        return prev_a >= prev_b and curr_a < curr_b

    def _over(
        self,
        series: List[float],
        params: Dict[str, Any],
        indicator_values: Dict[str, List[float]],
        parameter_values: Dict[str, float],
    ) -> bool:
        threshold = self._get_threshold(params, parameter_values)
        if threshold is not None:
            return series[-1] > threshold

        other_id = params.get("other")
        if other_id:
            other = indicator_values.get(other_id, [])
            if other:
                return series[-1] > other[-1]
        return False

    def _under(
        self,
        series: List[float],
        params: Dict[str, Any],
        indicator_values: Dict[str, List[float]],
        parameter_values: Dict[str, float],
    ) -> bool:
        threshold = self._get_threshold(params, parameter_values)
        if threshold is not None:
            return series[-1] < threshold

        other_id = params.get("other")
        if other_id:
            other = indicator_values.get(other_id, [])
            if other:
                return series[-1] < other[-1]
        return False


class StrategyExecutionEngine:
    """Core engine that evaluates strategy conditions against candle data."""

    def __init__(
        self,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.04,
    ):
        self._contexts: Dict[str, ExecutionContext] = {}
        self._candle_buffers: Dict[str, List[Candle]] = {}
        self._condition_evaluator = ConditionEvaluator()
        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct
        self._max_candles = 200
        self._signal_listeners: List[Callable[[Signal], None]] = []

    def add_signal_listener(self, listener: Callable[[Signal], None]) -> None:
        self._signal_listeners.append(listener)

    def load_config_from_yaml(self, yaml_path: str) -> StrategyConfig:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return StrategyConfig.from_dict(data)

    def load_config_from_dict(self, data: Dict[str, Any]) -> StrategyConfig:
        return StrategyConfig.from_dict(data)

    def start_strategy(
        self,
        strategy_id: str,
        config: StrategyConfig,
        symbol: str,
        timeframe: str = "1m",
        parameter_overrides: Optional[Dict[str, float]] = None,
    ) -> ExecutionContext:
        if strategy_id in self._contexts:
            existing = self._contexts[strategy_id]
            if existing.state.status == StrategyStatus.RUNNING:
                raise ValueError(
                    f"Strategy {strategy_id} is already running"
                )

        # Resolve parameter values
        param_values = {}
        for p in config.parameters:
            param_values[p.name] = p.default_value
        if parameter_overrides:
            param_values.update(parameter_overrides)

        state = StrategyState(
            strategy_id=strategy_id,
            status=StrategyStatus.RUNNING,
        )
        ctx = ExecutionContext(
            strategy_id=strategy_id,
            config=config,
            symbol=symbol,
            timeframe=timeframe,
            parameter_values=param_values,
            state=state,
        )
        self._contexts[strategy_id] = ctx
        self._candle_buffers[strategy_id] = []
        logger.info(
            "Started strategy %s (%s) on %s/%s",
            strategy_id, config.name, symbol, timeframe,
        )
        return ctx

    def stop_strategy(self, strategy_id: str) -> StrategyState:
        ctx = self._contexts.get(strategy_id)
        if ctx is None:
            raise KeyError(f"Strategy {strategy_id} not found")
        ctx.state.status = StrategyStatus.STOPPED
        logger.info("Stopped strategy %s", strategy_id)
        return ctx.state

    def get_context(self, strategy_id: str) -> Optional[ExecutionContext]:
        return self._contexts.get(strategy_id)

    def get_state(self, strategy_id: str) -> Optional[StrategyState]:
        ctx = self._contexts.get(strategy_id)
        return ctx.state if ctx else None

    def get_signals(
        self, strategy_id: str, limit: int = 50
    ) -> List[Signal]:
        ctx = self._contexts.get(strategy_id)
        if ctx is None:
            return []
        return ctx.signals[-limit:]

    def on_candle(self, strategy_id: str, candle: Candle) -> Optional[Signal]:
        """Process a new candle for a strategy. Returns a signal if emitted."""
        ctx = self._contexts.get(strategy_id)
        if ctx is None:
            return None
        if ctx.state.status != StrategyStatus.RUNNING:
            return None

        # Buffer candle
        buf = self._candle_buffers.setdefault(strategy_id, [])
        buf.append(candle)
        if len(buf) > self._max_candles:
            buf[:] = buf[-self._max_candles :]

        # Update current price
        ctx.state.current_price = candle.close

        # Update unrealized PnL
        if ctx.state.position == PositionState.LONG and ctx.state.entry_price:
            ctx.state.unrealized_pnl = candle.close - ctx.state.entry_price

        # Check stop loss / take profit
        signal = self._check_risk_management(ctx, candle)
        if signal:
            return signal

        # Need at least 2 candles to evaluate crossovers
        if len(buf) < 2:
            return None

        try:
            signal = self._evaluate(ctx, buf)
        except Exception as e:
            logger.error("Error evaluating strategy %s: %s", strategy_id, e)
            ctx.state.status = StrategyStatus.ERROR
            ctx.state.error_message = str(e)
            return None

        return signal

    def _check_risk_management(
        self, ctx: ExecutionContext, candle: Candle
    ) -> Optional[Signal]:
        if ctx.state.position != PositionState.LONG or ctx.state.entry_price is None:
            return None

        entry = ctx.state.entry_price
        stop_loss = entry * (1 - self._stop_loss_pct)
        take_profit = entry * (1 + self._take_profit_pct)

        if candle.close <= stop_loss:
            return self._emit_exit_signal(
                ctx, candle, "Stop loss triggered", stop_loss, take_profit
            )
        if candle.close >= take_profit:
            return self._emit_exit_signal(
                ctx, candle, "Take profit triggered", stop_loss, take_profit
            )
        return None

    def _evaluate(
        self, ctx: ExecutionContext, candles: List[Candle]
    ) -> Optional[Signal]:
        config = ctx.config
        if config is None:
            return None

        computer = IndicatorComputer(candles)
        indicator_values = computer.compute(config.indicators, ctx.parameter_values)

        if ctx.state.position == PositionState.FLAT:
            # Check entry conditions
            if self._condition_evaluator.evaluate(
                config.entry_conditions, indicator_values, ctx.parameter_values
            ):
                return self._emit_entry_signal(ctx, candles[-1], indicator_values)
        else:
            # Check exit conditions
            if self._condition_evaluator.evaluate(
                config.exit_conditions, indicator_values, ctx.parameter_values
            ):
                entry = ctx.state.entry_price or candles[-1].close
                stop_loss = entry * (1 - self._stop_loss_pct)
                take_profit = entry * (1 + self._take_profit_pct)
                return self._emit_exit_signal(
                    ctx, candles[-1], "Exit conditions met", stop_loss, take_profit
                )

        return None

    def _emit_entry_signal(
        self,
        ctx: ExecutionContext,
        candle: Candle,
        indicator_values: Dict[str, List[float]],
    ) -> Signal:
        entry_price = candle.close
        stop_loss = entry_price * (1 - self._stop_loss_pct)
        take_profit = entry_price * (1 + self._take_profit_pct)

        # Simple confidence based on how many indicators agree
        confidence = min(1.0, 0.5 + 0.1 * len(ctx.config.entry_conditions))

        signal = Signal(
            strategy_id=ctx.strategy_id,
            symbol=ctx.symbol,
            direction=SignalDirection.BUY,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"Entry conditions met for {ctx.config.name}",
            timestamp=candle.timestamp or time.time(),
        )

        # Update state
        ctx.state.position = PositionState.LONG
        ctx.state.entry_price = entry_price
        ctx.state.entry_time = candle.timestamp or time.time()
        ctx.state.unrealized_pnl = 0.0
        ctx.add_signal(signal)

        for listener in self._signal_listeners:
            listener(signal)

        logger.info(
            "BUY signal for %s at %.2f (SL=%.2f, TP=%.2f)",
            ctx.symbol, entry_price, stop_loss, take_profit,
        )
        return signal

    def _emit_exit_signal(
        self,
        ctx: ExecutionContext,
        candle: Candle,
        reason: str,
        stop_loss: float,
        take_profit: float,
    ) -> Signal:
        exit_price = candle.close
        entry_price = ctx.state.entry_price or exit_price

        signal = Signal(
            strategy_id=ctx.strategy_id,
            symbol=ctx.symbol,
            direction=SignalDirection.SELL,
            confidence=0.8,
            entry_price=exit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            timestamp=candle.timestamp or time.time(),
        )

        # Update PnL tracking
        pnl = exit_price - entry_price
        ctx.state.realized_pnl += pnl
        ctx.state.total_trades += 1
        if pnl > 0:
            ctx.state.winning_trades += 1
        else:
            ctx.state.losing_trades += 1

        # Reset position
        ctx.state.position = PositionState.FLAT
        ctx.state.entry_price = None
        ctx.state.entry_time = None
        ctx.state.unrealized_pnl = 0.0
        ctx.add_signal(signal)

        for listener in self._signal_listeners:
            listener(signal)

        logger.info(
            "SELL signal for %s at %.2f (PnL=%.2f, reason=%s)",
            ctx.symbol, exit_price, pnl, reason,
        )
        return signal
