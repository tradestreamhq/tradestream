"""
Technical indicator computation library for TradeStream.

Provides implementations of common technical indicators that operate on
OHLCV candle data. Each indicator supports both batch computation (full
series) and streaming mode (incremental updates).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Candle:
    """OHLCV candle data."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ---------------------------------------------------------------------------
# SMA — Simple Moving Average
# ---------------------------------------------------------------------------


class SMA:
    """Simple Moving Average with streaming support."""

    def __init__(self, period: int):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._window: List[float] = []
        self._sum: float = 0.0

    def update(self, value: float) -> Optional[float]:
        self._window.append(value)
        self._sum += value
        if len(self._window) > self.period:
            self._sum -= self._window.pop(0)
        if len(self._window) == self.period:
            return self._sum / self.period
        return None

    @staticmethod
    def compute(closes: List[float], period: int) -> List[Optional[float]]:
        sma = SMA(period)
        return [sma.update(c) for c in closes]


# ---------------------------------------------------------------------------
# EMA — Exponential Moving Average
# ---------------------------------------------------------------------------


class EMA:
    """Exponential Moving Average with streaming support."""

    def __init__(self, period: int):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._k = 2.0 / (period + 1)
        self._ema: Optional[float] = None
        self._count = 0
        self._sum = 0.0

    def update(self, value: float) -> Optional[float]:
        self._count += 1
        if self._ema is None:
            self._sum += value
            if self._count == self.period:
                self._ema = self._sum / self.period
                return self._ema
            return None
        self._ema = value * self._k + self._ema * (1 - self._k)
        return self._ema

    @staticmethod
    def compute(closes: List[float], period: int) -> List[Optional[float]]:
        ema = EMA(period)
        return [ema.update(c) for c in closes]


# ---------------------------------------------------------------------------
# RSI — Relative Strength Index
# ---------------------------------------------------------------------------


class RSI:
    """RSI using Wilder's smoothing method with streaming support."""

    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._prev_close: Optional[float] = None
        self._gains: List[float] = []
        self._losses: List[float] = []
        self._avg_gain: Optional[float] = None
        self._avg_loss: Optional[float] = None
        self._count = 0

    def update(self, close: float) -> Optional[float]:
        if self._prev_close is None:
            self._prev_close = close
            return None

        change = close - self._prev_close
        self._prev_close = close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._count += 1

        if self._avg_gain is None:
            self._gains.append(gain)
            self._losses.append(loss)
            if self._count == self.period:
                self._avg_gain = sum(self._gains) / self.period
                self._avg_loss = sum(self._losses) / self.period
                if self._avg_loss == 0:
                    return 100.0
                rs = self._avg_gain / self._avg_loss
                return 100.0 - (100.0 / (1.0 + rs))
            return None

        self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
        self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period
        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def compute(closes: List[float], period: int = 14) -> List[Optional[float]]:
        rsi = RSI(period)
        return [rsi.update(c) for c in closes]


# ---------------------------------------------------------------------------
# MACD — Moving Average Convergence Divergence
# ---------------------------------------------------------------------------


@dataclass
class MACDResult:
    macd: Optional[float] = None
    signal: Optional[float] = None
    histogram: Optional[float] = None


class MACD:
    """MACD with streaming support."""

    def __init__(
        self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ):
        self._fast_ema = EMA(fast_period)
        self._slow_ema = EMA(slow_period)
        self._signal_ema = EMA(signal_period)

    def update(self, close: float) -> MACDResult:
        fast = self._fast_ema.update(close)
        slow = self._slow_ema.update(close)
        if fast is None or slow is None:
            return MACDResult()
        macd_val = fast - slow
        signal = self._signal_ema.update(macd_val)
        histogram = (macd_val - signal) if signal is not None else None
        return MACDResult(macd=macd_val, signal=signal, histogram=histogram)

    @staticmethod
    def compute(
        closes: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> List[MACDResult]:
        macd = MACD(fast_period, slow_period, signal_period)
        return [macd.update(c) for c in closes]


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


@dataclass
class BollingerBandsResult:
    upper: Optional[float] = None
    middle: Optional[float] = None
    lower: Optional[float] = None


class BollingerBands:
    """Bollinger Bands with streaming support."""

    def __init__(self, period: int = 20, num_std: float = 2.0):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self.num_std = num_std
        self._window: List[float] = []

    def update(self, close: float) -> BollingerBandsResult:
        self._window.append(close)
        if len(self._window) > self.period:
            self._window.pop(0)
        if len(self._window) < self.period:
            return BollingerBandsResult()
        mean = sum(self._window) / self.period
        variance = sum((x - mean) ** 2 for x in self._window) / self.period
        std = variance**0.5
        return BollingerBandsResult(
            upper=mean + self.num_std * std,
            middle=mean,
            lower=mean - self.num_std * std,
        )

    @staticmethod
    def compute(
        closes: List[float], period: int = 20, num_std: float = 2.0
    ) -> List[BollingerBandsResult]:
        bb = BollingerBands(period, num_std)
        return [bb.update(c) for c in closes]


# ---------------------------------------------------------------------------
# ATR — Average True Range
# ---------------------------------------------------------------------------


class ATR:
    """Average True Range with streaming support."""

    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._prev_close: Optional[float] = None
        self._tr_values: List[float] = []
        self._atr: Optional[float] = None

    def update(self, candle: Candle) -> Optional[float]:
        if self._prev_close is None:
            self._prev_close = candle.close
            tr = candle.high - candle.low
        else:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - self._prev_close),
                abs(candle.low - self._prev_close),
            )
            self._prev_close = candle.close

        if self._atr is None:
            self._tr_values.append(tr)
            if len(self._tr_values) == self.period:
                self._atr = sum(self._tr_values) / self.period
                return self._atr
            return None

        self._atr = (self._atr * (self.period - 1) + tr) / self.period
        return self._atr

    @staticmethod
    def compute(candles: List[Candle], period: int = 14) -> List[Optional[float]]:
        atr = ATR(period)
        return [atr.update(c) for c in candles]


# ---------------------------------------------------------------------------
# VWAP — Volume Weighted Average Price
# ---------------------------------------------------------------------------


class VWAP:
    """VWAP with streaming support. Resets are manual via reset()."""

    def __init__(self):
        self._cum_volume = 0.0
        self._cum_tp_volume = 0.0

    def reset(self):
        self._cum_volume = 0.0
        self._cum_tp_volume = 0.0

    def update(self, candle: Candle) -> Optional[float]:
        typical_price = (candle.high + candle.low + candle.close) / 3.0
        self._cum_tp_volume += typical_price * candle.volume
        self._cum_volume += candle.volume
        if self._cum_volume == 0:
            return None
        return self._cum_tp_volume / self._cum_volume

    @staticmethod
    def compute(candles: List[Candle]) -> List[Optional[float]]:
        vwap = VWAP()
        return [vwap.update(c) for c in candles]


# ---------------------------------------------------------------------------
# Stochastic Oscillator
# ---------------------------------------------------------------------------


@dataclass
class StochasticResult:
    k: Optional[float] = None
    d: Optional[float] = None


class StochasticOscillator:
    """Stochastic Oscillator (%K and %D) with streaming support."""

    def __init__(self, k_period: int = 14, d_period: int = 3):
        if k_period < 1 or d_period < 1:
            raise ValueError("periods must be >= 1")
        self.k_period = k_period
        self.d_period = d_period
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._k_values: List[float] = []

    def update(self, candle: Candle) -> StochasticResult:
        self._highs.append(candle.high)
        self._lows.append(candle.low)
        if len(self._highs) > self.k_period:
            self._highs.pop(0)
            self._lows.pop(0)

        if len(self._highs) < self.k_period:
            return StochasticResult()

        highest = max(self._highs)
        lowest = min(self._lows)
        if highest == lowest:
            k = 100.0
        else:
            k = 100.0 * (candle.close - lowest) / (highest - lowest)

        self._k_values.append(k)
        if len(self._k_values) > self.d_period:
            self._k_values.pop(0)

        d = None
        if len(self._k_values) == self.d_period:
            d = sum(self._k_values) / self.d_period

        return StochasticResult(k=k, d=d)

    @staticmethod
    def compute(
        candles: List[Candle], k_period: int = 14, d_period: int = 3
    ) -> List[StochasticResult]:
        stoch = StochasticOscillator(k_period, d_period)
        return [stoch.update(c) for c in candles]


# ---------------------------------------------------------------------------
# Convenience: compute all indicators for a candle series
# ---------------------------------------------------------------------------


def compute_indicators(
    candles: List[Candle], config: Dict
) -> Dict[str, List]:
    """Compute multiple indicators based on a config dict.

    Config format:
        {
            "sma": {"period": 20},
            "ema": {"period": 12},
            "rsi": {"period": 14},
            "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "bollinger_bands": {"period": 20, "num_std": 2.0},
            "atr": {"period": 14},
            "vwap": {},
            "stochastic": {"k_period": 14, "d_period": 3},
        }
    """
    closes = [c.close for c in candles]
    results: Dict[str, List] = {}

    if "sma" in config:
        results["sma"] = SMA.compute(closes, **config["sma"])
    if "ema" in config:
        results["ema"] = EMA.compute(closes, **config["ema"])
    if "rsi" in config:
        results["rsi"] = RSI.compute(closes, **config["rsi"])
    if "macd" in config:
        results["macd"] = MACD.compute(closes, **config["macd"])
    if "bollinger_bands" in config:
        results["bollinger_bands"] = BollingerBands.compute(
            closes, **config["bollinger_bands"]
        )
    if "atr" in config:
        results["atr"] = ATR.compute(candles, **config["atr"])
    if "vwap" in config:
        results["vwap"] = VWAP.compute(candles)
    if "stochastic" in config:
        results["stochastic"] = StochasticOscillator.compute(
            candles, **config["stochastic"]
        )

    return results
