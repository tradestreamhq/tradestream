"""
Strategy Template Library — built-in, code-defined strategy templates.

Each template defines a name, description, parameter schema (with types, ranges,
and defaults), and signal logic.  Templates are stored in a registry and exposed
via REST endpoints so that users can browse them and instantiate custom strategies.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Parameter schema
# ---------------------------------------------------------------------------


class ParamType(str, enum.Enum):
    INT = "int"
    FLOAT = "float"


@dataclass
class ParamDef:
    """Definition of a single template parameter."""

    name: str
    type: ParamType
    default: float
    min_value: float
    max_value: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "default": self.default,
            "min": self.min_value,
            "max": self.max_value,
            "description": self.description,
        }

    def validate(self, value: Any) -> Optional[str]:
        """Return an error string if *value* is invalid, else ``None``."""
        if self.type == ParamType.INT:
            if not isinstance(value, int) and not (
                isinstance(value, float) and value == int(value)
            ):
                return f"{self.name}: expected int, got {type(value).__name__}"
            value = int(value)
        elif self.type == ParamType.FLOAT:
            if not isinstance(value, (int, float)):
                return f"{self.name}: expected number, got {type(value).__name__}"
        if value < self.min_value or value > self.max_value:
            return f"{self.name}: {value} outside [{self.min_value}, {self.max_value}]"
        return None


# ---------------------------------------------------------------------------
# Signal enum returned by template logic
# ---------------------------------------------------------------------------


class Signal(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# ---------------------------------------------------------------------------
# Template dataclass
# ---------------------------------------------------------------------------

# Signal function signature: (params: dict, market_data: dict) -> Signal
SignalFn = Callable[[Dict[str, Any], Dict[str, Any]], Signal]


@dataclass
class StrategyTemplate:
    id: str
    name: str
    description: str
    category: str
    parameters: List[ParamDef]
    signal_fn: SignalFn

    def defaults(self) -> Dict[str, Any]:
        return {p.name: p.default for p in self.parameters}

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        for pdef in self.parameters:
            val = params.get(pdef.name, pdef.default)
            err = pdef.validate(val)
            if err:
                errors.append(err)
        return errors

    def merge_params(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        merged = self.defaults()
        merged.update(overrides)
        return merged

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
        }

    def to_detail(self) -> Dict[str, Any]:
        return {
            **self.to_summary(),
            "parameters": [p.to_dict() for p in self.parameters],
            "defaults": self.defaults(),
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TemplateRegistry:
    """In-memory registry of strategy templates."""

    def __init__(self) -> None:
        self._templates: Dict[str, StrategyTemplate] = {}

    def register(self, template: StrategyTemplate) -> None:
        self._templates[template.id] = template

    def get(self, template_id: str) -> Optional[StrategyTemplate]:
        return self._templates.get(template_id)

    def list_all(self) -> List[StrategyTemplate]:
        return list(self._templates.values())


# ---------------------------------------------------------------------------
# Signal logic helpers
# ---------------------------------------------------------------------------


def _sma(values: List[float], period: int) -> Optional[float]:
    """Simple moving average over the last *period* values."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(closes: List[float], period: int) -> Optional[float]:
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = [c for c in changes if c > 0]
    losses = [-c for c in changes if c < 0]
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ema(values: List[float], period: int) -> Optional[float]:
    """Exponential moving average over *values*."""
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------


def _sma_crossover_signal(params: Dict[str, Any], data: Dict[str, Any]) -> Signal:
    closes: List[float] = data.get("closes", [])
    fast = int(params["fast_period"])
    slow = int(params["slow_period"])
    sma_fast = _sma(closes, fast)
    sma_slow = _sma(closes, slow)
    if sma_fast is None or sma_slow is None:
        return Signal.HOLD
    if sma_fast > sma_slow:
        return Signal.BUY
    if sma_fast < sma_slow:
        return Signal.SELL
    return Signal.HOLD


def _rsi_mean_reversion_signal(params: Dict[str, Any], data: Dict[str, Any]) -> Signal:
    closes: List[float] = data.get("closes", [])
    period = int(params["rsi_period"])
    overbought = float(params["overbought"])
    oversold = float(params["oversold"])
    rsi_val = _rsi(closes, period)
    if rsi_val is None:
        return Signal.HOLD
    if rsi_val <= oversold:
        return Signal.BUY
    if rsi_val >= overbought:
        return Signal.SELL
    return Signal.HOLD


def _breakout_signal(params: Dict[str, Any], data: Dict[str, Any]) -> Signal:
    closes: List[float] = data.get("closes", [])
    volumes: List[float] = data.get("volumes", [])
    lookback = int(params["lookback_period"])
    vol_mult = float(params["volume_multiplier"])
    if len(closes) < lookback + 1 or len(volumes) < lookback + 1:
        return Signal.HOLD
    window = closes[-(lookback + 1) : -1]
    high = max(window)
    low = min(window)
    avg_vol = sum(volumes[-(lookback + 1) : -1]) / lookback
    current_price = closes[-1]
    current_vol = volumes[-1]
    vol_confirmed = current_vol >= avg_vol * vol_mult
    if current_price > high and vol_confirmed:
        return Signal.BUY
    if current_price < low and vol_confirmed:
        return Signal.SELL
    return Signal.HOLD


def _momentum_signal(params: Dict[str, Any], data: Dict[str, Any]) -> Signal:
    closes: List[float] = data.get("closes", [])
    period = int(params["momentum_period"])
    ema_period = int(params["ema_period"])
    threshold = float(params["threshold"])
    if len(closes) < max(period, ema_period) + 1:
        return Signal.HOLD
    momentum = (closes[-1] - closes[-period]) / closes[-period] * 100
    ema_val = _ema(closes, ema_period)
    if ema_val is None:
        return Signal.HOLD
    if momentum > threshold and closes[-1] > ema_val:
        return Signal.BUY
    if momentum < -threshold and closes[-1] < ema_val:
        return Signal.SELL
    return Signal.HOLD


def _vwap_signal(params: Dict[str, Any], data: Dict[str, Any]) -> Signal:
    closes: List[float] = data.get("closes", [])
    volumes: List[float] = data.get("volumes", [])
    highs: List[float] = data.get("highs", [])
    lows: List[float] = data.get("lows", [])
    period = int(params["period"])
    dev_threshold = float(params["deviation_threshold"])
    n = min(len(closes), len(volumes), len(highs), len(lows))
    if n < period:
        return Signal.HOLD
    # Compute VWAP over the lookback period
    typical_prices = [
        (highs[i] + lows[i] + closes[i]) / 3 for i in range(n - period, n)
    ]
    vols = volumes[n - period : n]
    cum_tp_vol = sum(tp * v for tp, v in zip(typical_prices, vols))
    cum_vol = sum(vols)
    if cum_vol == 0:
        return Signal.HOLD
    vwap = cum_tp_vol / cum_vol
    deviation = (closes[-1] - vwap) / vwap
    if deviation < -dev_threshold:
        return Signal.BUY
    if deviation > dev_threshold:
        return Signal.SELL
    return Signal.HOLD


# ---------------------------------------------------------------------------
# Build the default registry
# ---------------------------------------------------------------------------


def build_default_registry() -> TemplateRegistry:
    """Create the registry pre-loaded with all built-in templates."""
    registry = TemplateRegistry()

    registry.register(
        StrategyTemplate(
            id="sma_crossover",
            name="SMA Crossover",
            description="Generates signals when a fast simple moving average crosses above or below a slow simple moving average.",
            category="trend_following",
            parameters=[
                ParamDef("fast_period", ParamType.INT, 10, 2, 200, "Fast SMA period"),
                ParamDef("slow_period", ParamType.INT, 30, 5, 500, "Slow SMA period"),
            ],
            signal_fn=_sma_crossover_signal,
        )
    )

    registry.register(
        StrategyTemplate(
            id="rsi_mean_reversion",
            name="RSI Mean Reversion",
            description="Uses the Relative Strength Index to identify overbought and oversold conditions for mean-reversion entries.",
            category="mean_reversion",
            parameters=[
                ParamDef("rsi_period", ParamType.INT, 14, 2, 100, "RSI calculation period"),
                ParamDef("overbought", ParamType.FLOAT, 70, 50, 100, "Overbought threshold"),
                ParamDef("oversold", ParamType.FLOAT, 30, 0, 50, "Oversold threshold"),
            ],
            signal_fn=_rsi_mean_reversion_signal,
        )
    )

    registry.register(
        StrategyTemplate(
            id="breakout",
            name="Breakout",
            description="Detects price breakouts above recent highs or below recent lows, confirmed by volume expansion.",
            category="breakout",
            parameters=[
                ParamDef("lookback_period", ParamType.INT, 20, 5, 200, "Lookback window for high/low"),
                ParamDef("volume_multiplier", ParamType.FLOAT, 1.5, 1.0, 5.0, "Volume confirmation multiplier"),
            ],
            signal_fn=_breakout_signal,
        )
    )

    registry.register(
        StrategyTemplate(
            id="momentum",
            name="Momentum",
            description="Combines price momentum with an EMA trend filter to capture strong directional moves.",
            category="trend_following",
            parameters=[
                ParamDef("momentum_period", ParamType.INT, 14, 2, 200, "Momentum lookback period"),
                ParamDef("ema_period", ParamType.INT, 20, 5, 200, "EMA trend filter period"),
                ParamDef("threshold", ParamType.FLOAT, 2.0, 0.1, 20.0, "Momentum threshold (%)"),
            ],
            signal_fn=_momentum_signal,
        )
    )

    registry.register(
        StrategyTemplate(
            id="vwap",
            name="VWAP",
            description="Trades deviations from the Volume Weighted Average Price, buying below and selling above VWAP.",
            category="mean_reversion",
            parameters=[
                ParamDef("period", ParamType.INT, 20, 5, 200, "VWAP calculation period"),
                ParamDef("deviation_threshold", ParamType.FLOAT, 0.02, 0.001, 0.1, "Deviation threshold from VWAP (ratio)"),
            ],
            signal_fn=_vwap_signal,
        )
    )

    return registry


# Module-level singleton
default_registry = build_default_registry()
