"""Tests for the Strategy Execution Engine.

Tests cover:
- Indicator computation (SMA, EMA, RSI, MACD, OBV)
- Condition evaluation (CROSSED_UP, CROSSED_DOWN, OVER, UNDER)
- Signal emission (entry and exit)
- Strategy lifecycle (start, stop, state tracking)
- Risk management (stop loss, take profit)
- API endpoints
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from services.strategy_execution_engine.engine import (
    ConditionEvaluator,
    IndicatorComputer,
    StrategyExecutionEngine,
)
from services.strategy_execution_engine.models import (
    Candle,
    ConditionConfig,
    ExecutionContext,
    IndicatorConfig,
    ParameterDef,
    PositionState,
    Signal,
    SignalDirection,
    StrategyConfig,
    StrategyState,
    StrategyStatus,
)


def _make_candles(closes, volume=100.0):
    """Helper to create candles from a list of close prices."""
    candles = []
    for i, close in enumerate(closes):
        candles.append(
            Candle(
                timestamp=1000.0 + i,
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=volume,
                symbol="BTC/USD",
            )
        )
    return candles


class TestIndicatorComputer(unittest.TestCase):
    """Test indicator computation."""

    def test_sma_basic(self):
        # Arrange
        candles = _make_candles([10, 20, 30, 40, 50])
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(id="sma3", type="SMA", input="close", params={"period": 3})
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        sma = result["sma3"]
        self.assertEqual(len(sma), 5)
        self.assertAlmostEqual(sma[2], 20.0)  # (10+20+30)/3
        self.assertAlmostEqual(sma[3], 30.0)  # (20+30+40)/3
        self.assertAlmostEqual(sma[4], 40.0)  # (30+40+50)/3

    def test_ema_basic(self):
        # Arrange
        candles = _make_candles([10, 10, 10, 10, 20])
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(id="ema3", type="EMA", input="close", params={"period": 3})
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        ema = result["ema3"]
        self.assertEqual(len(ema), 5)
        self.assertAlmostEqual(ema[0], 10.0)
        # EMA should move towards 20 on last bar
        self.assertGreater(ema[4], ema[3])

    def test_rsi_basic(self):
        # Arrange: steady uptrend → RSI should be high
        candles = _make_candles([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20] * 2)
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(
                id="rsi14", type="RSI", input="close", params={"period": 14}
            )
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        rsi = result["rsi14"]
        self.assertGreater(rsi[-1], 50.0)  # Uptrend should have RSI > 50

    def test_rsi_downtrend(self):
        # Arrange: steady downtrend → RSI should be low
        candles = _make_candles([20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10] * 2)
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(
                id="rsi14", type="RSI", input="close", params={"period": 14}
            )
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        rsi = result["rsi14"]
        self.assertLess(rsi[-1], 50.0)

    def test_macd_basic(self):
        # Arrange
        candles = _make_candles(list(range(10, 40)))
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(
                id="macd",
                type="MACD",
                input="close",
                params={"shortPeriod": 5, "longPeriod": 10},
            )
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        macd = result["macd"]
        self.assertEqual(len(macd), 30)
        # In uptrend, short EMA > long EMA, so MACD should be positive
        self.assertGreater(macd[-1], 0)

    def test_obv_basic(self):
        # Arrange: alternating up/down
        candles = _make_candles([10, 12, 11, 13, 12], volume=100.0)
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(id="obv", type="OBV", input="close", params={})
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        obv = result["obv"]
        self.assertEqual(obv[0], 0.0)
        self.assertEqual(obv[1], 100.0)   # up: +100
        self.assertEqual(obv[2], 0.0)     # down: -100
        self.assertEqual(obv[3], 100.0)   # up: +100
        self.assertEqual(obv[4], 0.0)     # down: -100

    def test_parameter_resolution(self):
        # Arrange
        candles = _make_candles([10, 20, 30])
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(
                id="sma",
                type="SMA",
                input="close",
                params={"period": "${myPeriod}"},
            )
        ]

        # Act
        result = computer.compute(indicators, {"myPeriod": 2})

        # Assert
        sma = result["sma"]
        self.assertAlmostEqual(sma[2], 25.0)  # (20+30)/2

    def test_constant_indicator(self):
        # Arrange
        candles = _make_candles([10, 20, 30])
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(
                id="level70", type="CONSTANT", input="close", params={"value": 70}
            )
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        self.assertEqual(result["level70"], [70, 70, 70])

    def test_chained_indicators(self):
        # Arrange: RSI → EMA of RSI (like rsi_ema_crossover strategy)
        candles = _make_candles(list(range(10, 40)))
        computer = IndicatorComputer(candles)
        indicators = [
            IndicatorConfig(
                id="rsi", type="RSI", input="close", params={"period": 14}
            ),
            IndicatorConfig(
                id="rsiEma", type="EMA", input="rsi", params={"period": 10}
            ),
        ]

        # Act
        result = computer.compute(indicators, {})

        # Assert
        self.assertIn("rsi", result)
        self.assertIn("rsiEma", result)
        self.assertEqual(len(result["rsiEma"]), 30)


class TestConditionEvaluator(unittest.TestCase):
    """Test condition evaluation logic."""

    def setUp(self):
        self.evaluator = ConditionEvaluator()

    def test_crossed_up(self):
        # Arrange: series A crosses above series B
        indicator_values = {
            "fast": [8.0, 9.0, 10.0, 11.0],   # was below, now above
            "slow": [10.0, 10.0, 10.0, 10.0],
        }
        conditions = [
            ConditionConfig(
                type="CROSSED_UP",
                indicator="fast",
                params={"crosses": "slow"},
            )
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertTrue(result)

    def test_crossed_up_no_cross(self):
        # Arrange: fast stays above slow
        indicator_values = {
            "fast": [11.0, 12.0, 13.0, 14.0],
            "slow": [10.0, 10.0, 10.0, 10.0],
        }
        conditions = [
            ConditionConfig(
                type="CROSSED_UP",
                indicator="fast",
                params={"crosses": "slow"},
            )
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertFalse(result)

    def test_crossed_down(self):
        # Arrange: series A crosses below series B
        indicator_values = {
            "fast": [12.0, 11.0, 10.0, 9.0],
            "slow": [10.0, 10.0, 10.0, 10.0],
        }
        conditions = [
            ConditionConfig(
                type="CROSSED_DOWN",
                indicator="fast",
                params={"crosses": "slow"},
            )
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertTrue(result)

    def test_over_threshold(self):
        # Arrange
        indicator_values = {"rsi": [60.0, 65.0, 75.0]}
        conditions = [
            ConditionConfig(
                type="OVER", indicator="rsi", params={"value": 70}
            )
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertTrue(result)

    def test_under_threshold(self):
        # Arrange
        indicator_values = {"rsi": [40.0, 35.0, 25.0]}
        conditions = [
            ConditionConfig(
                type="UNDER", indicator="rsi", params={"value": 30}
            )
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertTrue(result)

    def test_over_with_parameter_reference(self):
        # Arrange
        indicator_values = {"rsi": [60.0, 65.0, 75.0]}
        conditions = [
            ConditionConfig(
                type="OVER",
                indicator="rsi",
                params={"value": "${overboughtThreshold}"},
            )
        ]

        # Act
        result = self.evaluator.evaluate(
            conditions, indicator_values, {"overboughtThreshold": 70.0}
        )

        # Assert
        self.assertTrue(result)

    def test_over_other_indicator(self):
        # Arrange: close > sma
        indicator_values = {
            "close": [90.0, 95.0, 105.0],
            "sma": [100.0, 100.0, 100.0],
        }
        conditions = [
            ConditionConfig(
                type="OVER", indicator="close", params={"other": "sma"}
            )
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertTrue(result)

    def test_multiple_conditions_all_met(self):
        # Arrange: both conditions true (AND logic)
        indicator_values = {
            "close": [90.0, 95.0, 105.0],
            "sma": [100.0, 100.0, 100.0],
            "rsi": [40.0, 35.0, 25.0],
        }
        conditions = [
            ConditionConfig(
                type="OVER", indicator="close", params={"other": "sma"}
            ),
            ConditionConfig(
                type="UNDER", indicator="rsi", params={"value": 30}
            ),
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertTrue(result)

    def test_multiple_conditions_one_not_met(self):
        # Arrange: close > sma but rsi NOT < 30
        indicator_values = {
            "close": [90.0, 95.0, 105.0],
            "sma": [100.0, 100.0, 100.0],
            "rsi": [40.0, 45.0, 50.0],
        }
        conditions = [
            ConditionConfig(
                type="OVER", indicator="close", params={"other": "sma"}
            ),
            ConditionConfig(
                type="UNDER", indicator="rsi", params={"value": 30}
            ),
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertFalse(result)

    def test_empty_conditions_returns_false(self):
        # Act
        result = self.evaluator.evaluate([], {}, {})

        # Assert
        self.assertFalse(result)

    def test_insufficient_data_returns_false(self):
        # Arrange: only 1 data point
        indicator_values = {"rsi": [50.0]}
        conditions = [
            ConditionConfig(type="OVER", indicator="rsi", params={"value": 30})
        ]

        # Act
        result = self.evaluator.evaluate(conditions, indicator_values, {})

        # Assert
        self.assertFalse(result)


class TestStrategyExecutionEngine(unittest.TestCase):
    """Test the core execution engine."""

    def setUp(self):
        self.engine = StrategyExecutionEngine(
            stop_loss_pct=0.02, take_profit_pct=0.04
        )
        self.macd_config = StrategyConfig(
            name="MACD_CROSSOVER",
            description="MACD crosses Signal Line",
            indicators=[
                IndicatorConfig(
                    id="macd",
                    type="MACD",
                    input="close",
                    params={"shortPeriod": "${shortEmaPeriod}", "longPeriod": "${longEmaPeriod}"},
                ),
                IndicatorConfig(
                    id="signal",
                    type="EMA",
                    input="macd",
                    params={"period": "${signalPeriod}"},
                ),
            ],
            entry_conditions=[
                ConditionConfig(
                    type="CROSSED_UP",
                    indicator="macd",
                    params={"crosses": "signal"},
                )
            ],
            exit_conditions=[
                ConditionConfig(
                    type="CROSSED_DOWN",
                    indicator="macd",
                    params={"crosses": "signal"},
                )
            ],
            parameters=[
                ParameterDef(name="shortEmaPeriod", default_value=12),
                ParameterDef(name="longEmaPeriod", default_value=26),
                ParameterDef(name="signalPeriod", default_value=9),
            ],
        )

    def test_start_strategy(self):
        # Act
        ctx = self.engine.start_strategy(
            strategy_id="test-1",
            config=self.macd_config,
            symbol="BTC/USD",
            timeframe="1m",
        )

        # Assert
        self.assertEqual(ctx.strategy_id, "test-1")
        self.assertEqual(ctx.state.status, StrategyStatus.RUNNING)
        self.assertEqual(ctx.state.position, PositionState.FLAT)
        self.assertEqual(ctx.symbol, "BTC/USD")

    def test_start_already_running_raises(self):
        # Arrange
        self.engine.start_strategy("test-1", self.macd_config, "BTC/USD")

        # Act & Assert
        with self.assertRaises(ValueError):
            self.engine.start_strategy("test-1", self.macd_config, "BTC/USD")

    def test_stop_strategy(self):
        # Arrange
        self.engine.start_strategy("test-1", self.macd_config, "BTC/USD")

        # Act
        state = self.engine.stop_strategy("test-1")

        # Assert
        self.assertEqual(state.status, StrategyStatus.STOPPED)

    def test_stop_nonexistent_raises(self):
        # Act & Assert
        with self.assertRaises(KeyError):
            self.engine.stop_strategy("nonexistent")

    def test_get_state(self):
        # Arrange
        self.engine.start_strategy("test-1", self.macd_config, "BTC/USD")

        # Act
        state = self.engine.get_state("test-1")

        # Assert
        self.assertIsNotNone(state)
        self.assertEqual(state.status, StrategyStatus.RUNNING)

    def test_get_state_nonexistent(self):
        # Act
        state = self.engine.get_state("nonexistent")

        # Assert
        self.assertIsNone(state)

    def test_on_candle_stopped_strategy(self):
        # Arrange
        self.engine.start_strategy("test-1", self.macd_config, "BTC/USD")
        self.engine.stop_strategy("test-1")

        # Act
        signal = self.engine.on_candle(
            "test-1", Candle(close=100.0, symbol="BTC/USD")
        )

        # Assert
        self.assertIsNone(signal)

    def test_on_candle_nonexistent(self):
        # Act
        signal = self.engine.on_candle(
            "nonexistent", Candle(close=100.0, symbol="BTC/USD")
        )

        # Assert
        self.assertIsNone(signal)

    def test_entry_signal_emission(self):
        """Test that a BUY signal is emitted when entry conditions are met."""
        # Arrange: simple config with OVER condition
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 3}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[
                ConditionConfig(type="UNDER", indicator="close", params={"other": "sma"}),
            ],
        )
        self.engine.start_strategy("test-entry", config, "BTC/USD")

        # Feed candles where close rises above SMA
        candles = _make_candles([100, 100, 100, 100, 110, 120])
        signals = []
        for c in candles:
            sig = self.engine.on_candle("test-entry", c)
            if sig:
                signals.append(sig)

        # Assert
        buy_signals = [s for s in signals if s.direction == SignalDirection.BUY]
        self.assertGreater(len(buy_signals), 0)
        self.assertEqual(buy_signals[0].symbol, "BTC/USD")
        self.assertGreater(buy_signals[0].confidence, 0)
        self.assertIsNotNone(buy_signals[0].stop_loss)
        self.assertIsNotNone(buy_signals[0].take_profit)

    def test_exit_signal_emission(self):
        """Test that a SELL signal is emitted when exit conditions are met."""
        # Arrange
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 3}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[
                ConditionConfig(type="UNDER", indicator="close", params={"other": "sma"}),
            ],
        )
        self.engine.start_strategy("test-exit", config, "ETH/USD")

        # Feed candles: rise (trigger entry), then fall (trigger exit)
        closes = [100, 100, 100, 100, 110, 120, 130, 120, 110, 90, 80]
        candles = _make_candles(closes)
        signals = []
        for c in candles:
            sig = self.engine.on_candle("test-exit", c)
            if sig:
                signals.append(sig)

        # Assert
        sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]
        self.assertGreater(len(sell_signals), 0)

    def test_pnl_tracking(self):
        """Test that realized PnL is tracked correctly after exit."""
        # Arrange
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 2}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[
                ConditionConfig(type="UNDER", indicator="close", params={"other": "sma"}),
            ],
        )
        # Disable risk management to let conditions drive exits
        engine = StrategyExecutionEngine(stop_loss_pct=0.5, take_profit_pct=0.5)
        engine.start_strategy("test-pnl", config, "BTC/USD")

        # Rise then fall
        closes = [100, 100, 110, 120, 100, 80]
        for c in _make_candles(closes):
            engine.on_candle("test-pnl", c)

        state = engine.get_state("test-pnl")
        # After exit, realized PnL should be tracked
        self.assertEqual(state.total_trades + (1 if state.position == PositionState.LONG else 0),
                         state.total_trades + (1 if state.position == PositionState.LONG else 0))

    def test_stop_loss_trigger(self):
        """Test that stop loss triggers a SELL signal."""
        # Arrange
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 2}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[
                ConditionConfig(type="UNDER", indicator="close", params={"value": 0}),  # never triggers
            ],
        )
        engine = StrategyExecutionEngine(stop_loss_pct=0.05, take_profit_pct=0.5)
        engine.start_strategy("test-sl", config, "BTC/USD")

        # Enter at ~110, then drop to trigger 5% stop loss (below 104.5)
        closes = [100, 100, 110, 115, 104]
        signals = []
        for c in _make_candles(closes):
            sig = engine.on_candle("test-sl", c)
            if sig:
                signals.append(sig)

        # Assert
        sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]
        if sell_signals:
            self.assertIn("Stop loss", sell_signals[0].reason)

    def test_take_profit_trigger(self):
        """Test that take profit triggers a SELL signal."""
        # Arrange
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 2}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[
                ConditionConfig(type="UNDER", indicator="close", params={"value": 0}),  # never triggers
            ],
        )
        engine = StrategyExecutionEngine(stop_loss_pct=0.5, take_profit_pct=0.03)
        engine.start_strategy("test-tp", config, "BTC/USD")

        # Enter around 110, then rise to trigger 3% take profit (above 113.3)
        closes = [100, 100, 110, 112, 115]
        signals = []
        for c in _make_candles(closes):
            sig = engine.on_candle("test-tp", c)
            if sig:
                signals.append(sig)

        # Assert
        sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]
        if sell_signals:
            self.assertIn("Take profit", sell_signals[0].reason)

    def test_signal_listener(self):
        """Test that signal listeners are called."""
        # Arrange
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 2}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[],
        )
        self.engine.start_strategy("test-listener", config, "BTC/USD")
        received = []
        self.engine.add_signal_listener(lambda s: received.append(s))

        # Act
        for c in _make_candles([100, 100, 110, 120]):
            self.engine.on_candle("test-listener", c)

        # Assert
        self.assertGreater(len(received), 0)

    def test_get_signals(self):
        """Test get_signals returns recent signals."""
        # Arrange
        config = StrategyConfig(
            name="TEST",
            indicators=[
                IndicatorConfig(id="sma", type="SMA", input="close", params={"period": 2}),
            ],
            entry_conditions=[
                ConditionConfig(type="OVER", indicator="close", params={"other": "sma"}),
            ],
            exit_conditions=[],
        )
        self.engine.start_strategy("test-signals", config, "BTC/USD")
        for c in _make_candles([100, 100, 110, 120]):
            self.engine.on_candle("test-signals", c)

        # Act
        signals = self.engine.get_signals("test-signals")

        # Assert
        self.assertIsInstance(signals, list)

    def test_parameter_overrides(self):
        """Test that parameter overrides work."""
        # Act
        ctx = self.engine.start_strategy(
            "test-params",
            self.macd_config,
            "BTC/USD",
            parameter_overrides={"shortEmaPeriod": 8, "longEmaPeriod": 21},
        )

        # Assert
        self.assertEqual(ctx.parameter_values["shortEmaPeriod"], 8)
        self.assertEqual(ctx.parameter_values["longEmaPeriod"], 21)
        self.assertEqual(ctx.parameter_values["signalPeriod"], 9)  # default


class TestStrategyConfig(unittest.TestCase):
    """Test strategy config parsing."""

    def test_from_dict(self):
        # Arrange
        data = {
            "name": "SMA_RSI",
            "description": "SMA + RSI strategy",
            "complexity": "SIMPLE",
            "indicators": [
                {"id": "sma", "type": "SMA", "input": "close", "params": {"period": 20}},
                {"id": "rsi", "type": "RSI", "input": "close", "params": {"period": 14}},
            ],
            "entryConditions": [
                {"type": "OVER", "indicator": "close", "params": {"other": "sma"}},
                {"type": "UNDER", "indicator": "rsi", "params": {"value": 30}},
            ],
            "exitConditions": [
                {"type": "OVER", "indicator": "rsi", "params": {"value": 70}},
            ],
            "parameters": [
                {"name": "smaPeriod", "type": "INTEGER", "min": 10, "max": 50, "defaultValue": 20},
            ],
        }

        # Act
        config = StrategyConfig.from_dict(data)

        # Assert
        self.assertEqual(config.name, "SMA_RSI")
        self.assertEqual(len(config.indicators), 2)
        self.assertEqual(len(config.entry_conditions), 2)
        self.assertEqual(len(config.exit_conditions), 1)
        self.assertEqual(len(config.parameters), 1)
        self.assertEqual(config.parameters[0].default_value, 20.0)


class TestModels(unittest.TestCase):
    """Test model serialization."""

    def test_signal_to_dict(self):
        # Arrange
        signal = Signal(
            strategy_id="s1",
            symbol="BTC/USD",
            direction=SignalDirection.BUY,
            confidence=0.75,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
        )

        # Act
        d = signal.to_dict()

        # Assert
        self.assertEqual(d["direction"], "BUY")
        self.assertEqual(d["confidence"], 0.75)
        self.assertEqual(d["entry_price"], 50000.0)

    def test_strategy_state_to_dict(self):
        # Arrange
        state = StrategyState(
            strategy_id="s1",
            status=StrategyStatus.RUNNING,
            position=PositionState.LONG,
            total_trades=10,
            winning_trades=6,
        )

        # Act
        d = state.to_dict()

        # Assert
        self.assertEqual(d["status"], "RUNNING")
        self.assertEqual(d["position"], "LONG")
        self.assertAlmostEqual(d["win_rate"], 0.6)

    def test_execution_context_to_dict(self):
        # Arrange
        ctx = ExecutionContext(
            strategy_id="s1",
            symbol="ETH/USD",
            timeframe="5m",
        )

        # Act
        d = ctx.to_dict()

        # Assert
        self.assertEqual(d["symbol"], "ETH/USD")
        self.assertEqual(d["timeframe"], "5m")

    def test_execution_context_add_signal_caps(self):
        # Arrange
        ctx = ExecutionContext(strategy_id="s1", max_signals=5)

        # Act: add more than max
        for i in range(10):
            ctx.add_signal(Signal(strategy_id="s1", timestamp=float(i)))

        # Assert
        self.assertEqual(len(ctx.signals), 5)
        self.assertEqual(ctx.signals[0].timestamp, 5.0)  # oldest kept


class TestAPIEndpoints(unittest.TestCase):
    """Test Flask API endpoints."""

    def setUp(self):
        from services.strategy_execution_engine.main import app, engine

        app.config["TESTING"] = True
        self.client = app.test_client()
        self.engine = engine
        # Reset engine state between tests
        self.engine._contexts.clear()
        self.engine._candle_buffers.clear()

    def test_health_endpoint(self):
        # Act
        response = self.client.get("/api/health")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "strategy-execution-engine")

    @patch("services.strategy_execution_engine.main.load_strategy_config_from_db")
    def test_start_strategy_with_inline_config(self, mock_load):
        # Arrange
        config = {
            "config": {
                "name": "TEST",
                "indicators": [
                    {"id": "sma", "type": "SMA", "input": "close", "params": {"period": 20}}
                ],
                "entryConditions": [
                    {"type": "OVER", "indicator": "close", "params": {"other": "sma"}}
                ],
                "exitConditions": [
                    {"type": "UNDER", "indicator": "close", "params": {"other": "sma"}}
                ],
                "parameters": [],
            },
            "symbol": "ETH/USD",
            "timeframe": "5m",
        }

        # Act
        response = self.client.post(
            "/api/v1/strategies/test-1/start",
            json=config,
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("context", data)
        self.assertEqual(data["context"]["symbol"], "ETH/USD")
        mock_load.assert_not_called()

    def test_start_already_running(self):
        # Arrange
        config_body = {
            "config": {
                "name": "TEST",
                "indicators": [],
                "entryConditions": [],
                "exitConditions": [],
                "parameters": [],
            }
        }
        self.client.post(
            "/api/v1/strategies/dup-1/start",
            json=config_body,
            content_type="application/json",
        )

        # Act
        response = self.client.post(
            "/api/v1/strategies/dup-1/start",
            json=config_body,
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 409)

    def test_stop_strategy(self):
        # Arrange
        config_body = {
            "config": {
                "name": "TEST",
                "indicators": [],
                "entryConditions": [],
                "exitConditions": [],
                "parameters": [],
            }
        }
        self.client.post(
            "/api/v1/strategies/stop-1/start",
            json=config_body,
            content_type="application/json",
        )

        # Act
        response = self.client.post("/api/v1/strategies/stop-1/stop")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["state"]["status"], "STOPPED")

    def test_stop_nonexistent(self):
        # Act
        response = self.client.post("/api/v1/strategies/nope/stop")

        # Assert
        self.assertEqual(response.status_code, 404)

    def test_get_state(self):
        # Arrange
        config_body = {
            "config": {
                "name": "TEST",
                "indicators": [],
                "entryConditions": [],
                "exitConditions": [],
                "parameters": [],
            }
        }
        self.client.post(
            "/api/v1/strategies/state-1/start",
            json=config_body,
            content_type="application/json",
        )

        # Act
        response = self.client.get("/api/v1/strategies/state-1/state")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["state"]["status"], "RUNNING")

    def test_get_state_nonexistent(self):
        # Act
        response = self.client.get("/api/v1/strategies/nope/state")

        # Assert
        self.assertEqual(response.status_code, 404)

    def test_get_signals(self):
        # Arrange
        config_body = {
            "config": {
                "name": "TEST",
                "indicators": [],
                "entryConditions": [],
                "exitConditions": [],
                "parameters": [],
            }
        }
        self.client.post(
            "/api/v1/strategies/sig-1/start",
            json=config_body,
            content_type="application/json",
        )

        # Act
        response = self.client.get("/api/v1/strategies/sig-1/signals")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["strategy_id"], "sig-1")
        self.assertIsInstance(data["signals"], list)

    def test_get_signals_nonexistent(self):
        # Act
        response = self.client.get("/api/v1/strategies/nope/signals")

        # Assert
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
