"""
Indicator Registry for VectorBT Backtesting Service.

Maps indicator type names to VectorBT/pandas indicator implementations.
Mirrors the Java IndicatorRegistry for compatibility.
"""

from typing import Callable, Dict, Any, Optional
import pandas as pd
import numpy as np
import vectorbt as vbt


class IndicatorParams:
    """Container for indicator parameters with defaults."""

    def __init__(self, params: Dict[str, Any]):
        self._params = params or {}

    def get_int(self, key: str, default: int = 0) -> int:
        return int(self._params.get(key, default))

    def get_float(self, key: str, default: float = 0.0) -> float:
        return float(self._params.get(key, default))

    def get(self, key: str, default: Any = None) -> Any:
        return self._params.get(key, default)


# Type alias for indicator factory function
IndicatorFactory = Callable[[pd.Series, pd.DataFrame, IndicatorParams], pd.Series]


class IndicatorRegistry:
    """Registry of indicator factories mapping type names to implementations."""

    def __init__(self):
        self._factories: Dict[str, IndicatorFactory] = {}
        self._register_defaults()

    def register(self, name: str, factory: IndicatorFactory) -> None:
        """Register an indicator factory."""
        self._factories[name.upper()] = factory

    def create(
        self, name: str, close: pd.Series, ohlcv: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.Series:
        """Create an indicator by name."""
        factory = self._factories.get(name.upper())
        if factory is None:
            raise ValueError(f"Unknown indicator type: {name}")
        return factory(close, ohlcv, IndicatorParams(params))

    def has_indicator(self, name: str) -> bool:
        """Check if an indicator is registered."""
        return name.upper() in self._factories

    def list_indicators(self) -> list:
        """List all registered indicator names."""
        return sorted(self._factories.keys())

    def _register_defaults(self) -> None:
        """Register all default indicators."""
        # Moving Averages
        self.register(
            "SMA", lambda c, df, p: vbt.MA.run(c, window=p.get_int("period", 14)).ma
        )
        self.register(
            "EMA",
            lambda c, df, p: vbt.MA.run(c, window=p.get_int("period", 14), ewm=True).ma,
        )

        # For DEMA and TEMA, we compute manually
        self.register("DEMA", self._dema)
        self.register("TEMA", self._tema)
        self.register("WMA", self._wma)

        # Oscillators
        self.register(
            "RSI", lambda c, df, p: vbt.RSI.run(c, window=p.get_int("period", 14)).rsi
        )
        self.register("MACD", self._macd)
        self.register("MACD_SIGNAL", self._macd_signal)
        self.register("MACD_HIST", self._macd_hist)
        self.register("STOCHASTIC_K", self._stoch_k)
        self.register("STOCHASTIC_D", self._stoch_d)
        self.register("CCI", self._cci)
        self.register("CMO", self._cmo)
        self.register("WILLIAMS_R", self._williams_r)
        self.register("ROC", self._roc)
        self.register("DPO", self._dpo)

        # Trend Indicators
        self.register("ADX", self._adx)
        self.register("PLUS_DI", self._plus_di)
        self.register("MINUS_DI", self._minus_di)
        self.register("AROON_UP", self._aroon_up)
        self.register("AROON_DOWN", self._aroon_down)
        self.register("PARABOLIC_SAR", self._parabolic_sar)

        # Volatility Indicators
        self.register(
            "ATR",
            lambda c, df, p: vbt.ATR.run(
                df["high"], df["low"], df["close"], window=p.get_int("period", 14)
            ).atr,
        )
        self.register("BOLLINGER_UPPER", self._bbands_upper)
        self.register("BOLLINGER_MIDDLE", self._bbands_middle)
        self.register("BOLLINGER_LOWER", self._bbands_lower)
        self.register("DONCHIAN_UPPER", self._donchian_upper)
        self.register("DONCHIAN_LOWER", self._donchian_lower)

        # Volume Indicators
        self.register(
            "OBV", lambda c, df, p: vbt.OBV.run(df["close"], df["volume"]).obv
        )
        self.register("VWAP", self._vwap)

        # Price Helpers
        self.register("CLOSE", lambda c, df, p: df["close"])
        self.register("HIGH", lambda c, df, p: df["high"])
        self.register("LOW", lambda c, df, p: df["low"])
        self.register("OPEN", lambda c, df, p: df["open"])
        self.register("VOLUME", lambda c, df, p: df["volume"])
        self.register(
            "TYPICAL_PRICE", lambda c, df, p: (df["high"] + df["low"] + df["close"]) / 3
        )
        self.register("MEDIAN_PRICE", lambda c, df, p: (df["high"] + df["low"]) / 2)

        # Constant
        self.register(
            "CONSTANT",
            lambda c, df, p: pd.Series(p.get_float("value", 0), index=c.index),
        )

    # Indicator implementations
    def _dema(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        ema1 = close.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        return 2 * ema1 - ema2

    def _tema(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        ema1 = close.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        return 3 * ema1 - 3 * ema2 + ema3

    def _wma(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        weights = np.arange(1, period + 1)
        return close.rolling(period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

    def _macd(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        fast = params.get_int("shortPeriod", 12)
        slow = params.get_int("longPeriod", 26)
        macd = vbt.MACD.run(close, fast_window=fast, slow_window=slow, signal_window=9)
        return macd.macd

    def _macd_signal(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        fast = params.get_int("shortPeriod", 12)
        slow = params.get_int("longPeriod", 26)
        signal = params.get_int("signalPeriod", 9)
        macd = vbt.MACD.run(
            close, fast_window=fast, slow_window=slow, signal_window=signal
        )
        return macd.signal

    def _macd_hist(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        fast = params.get_int("shortPeriod", 12)
        slow = params.get_int("longPeriod", 26)
        signal = params.get_int("signalPeriod", 9)
        macd = vbt.MACD.run(
            close, fast_window=fast, slow_window=slow, signal_window=signal
        )
        return macd.hist

    def _stoch_k(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        stoch = vbt.STOCH.run(
            ohlcv["high"], ohlcv["low"], ohlcv["close"], k_window=period
        )
        return stoch.percent_k

    def _stoch_d(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        k_period = params.get_int("kPeriod", 14)
        d_period = params.get_int("dPeriod", 3)
        stoch = vbt.STOCH.run(
            ohlcv["high"],
            ohlcv["low"],
            ohlcv["close"],
            k_window=k_period,
            d_window=d_period,
        )
        return stoch.percent_d

    def _cci(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        tp = (ohlcv["high"] + ohlcv["low"] + ohlcv["close"]) / 3
        sma = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        return (tp - sma) / (0.015 * mad)

    def _cmo(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).sum()
        loss = (-delta.where(delta < 0, 0)).rolling(period).sum()
        return 100 * (gain - loss) / (gain + loss)

    def _williams_r(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        highest = ohlcv["high"].rolling(period).max()
        lowest = ohlcv["low"].rolling(period).min()
        return -100 * (highest - close) / (highest - lowest)

    def _roc(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 12)
        return 100 * (close - close.shift(period)) / close.shift(period)

    def _dpo(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        shift = period // 2 + 1
        sma = close.rolling(period).mean()
        return close.shift(shift) - sma

    def _adx(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        # Simplified ADX calculation
        high, low = ohlcv["high"], ohlcv["low"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr = pd.concat(
            [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
            axis=1,
        ).max(axis=1)

        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        return dx.ewm(span=period, adjust=False).mean()

    def _plus_di(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        high, low = ohlcv["high"], ohlcv["low"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)

        tr = pd.concat(
            [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
            axis=1,
        ).max(axis=1)

        atr = tr.ewm(span=period, adjust=False).mean()
        return 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr

    def _minus_di(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        high, low = ohlcv["high"], ohlcv["low"]
        minus_dm = -low.diff()
        plus_dm = high.diff()
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr = pd.concat(
            [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
            axis=1,
        ).max(axis=1)

        atr = tr.ewm(span=period, adjust=False).mean()
        return 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr

    def _aroon_up(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 25)

        def aroon_up_calc(x):
            return 100 * (period - (period - 1 - x.argmax())) / period

        return ohlcv["high"].rolling(period + 1).apply(aroon_up_calc, raw=True)

    def _aroon_down(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 25)

        def aroon_down_calc(x):
            return 100 * (period - (period - 1 - x.argmin())) / period

        return ohlcv["low"].rolling(period + 1).apply(aroon_down_calc, raw=True)

    def _parabolic_sar(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        # Simplified Parabolic SAR
        af_start = params.get_float("accelerationFactorStart", 0.02)
        af_inc = params.get_float("accelerationFactorIncrement", 0.02)
        af_max = params.get_float("accelerationFactorMax", 0.2)

        high, low = ohlcv["high"].values, ohlcv["low"].values
        n = len(close)
        sar = np.zeros(n)
        sar[0] = low[0]

        trend = 1  # 1 = uptrend, -1 = downtrend
        ep = high[0]  # extreme point
        af = af_start

        for i in range(1, n):
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if trend == 1:
                if low[i] < sar[i]:
                    trend = -1
                    sar[i] = ep
                    ep = low[i]
                    af = af_start
                else:
                    if high[i] > ep:
                        ep = high[i]
                        af = min(af + af_inc, af_max)
            else:
                if high[i] > sar[i]:
                    trend = 1
                    sar[i] = ep
                    ep = high[i]
                    af = af_start
                else:
                    if low[i] < ep:
                        ep = low[i]
                        af = min(af + af_inc, af_max)

        return pd.Series(sar, index=close.index)

    def _bbands_upper(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        mult = params.get_float("multiplier", 2.0)
        bb = vbt.BBANDS.run(close, window=period, alpha=mult)
        return bb.upper

    def _bbands_middle(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        bb = vbt.BBANDS.run(close, window=period)
        return bb.middle

    def _bbands_lower(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        mult = params.get_float("multiplier", 2.0)
        bb = vbt.BBANDS.run(close, window=period, alpha=mult)
        return bb.lower

    def _donchian_upper(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        return ohlcv["high"].rolling(period).max()

    def _donchian_lower(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 20)
        return ohlcv["low"].rolling(period).min()

    def _vwap(
        self, close: pd.Series, ohlcv: pd.DataFrame, params: IndicatorParams
    ) -> pd.Series:
        period = params.get_int("period", 14)
        tp = (ohlcv["high"] + ohlcv["low"] + ohlcv["close"]) / 3
        return (tp * ohlcv["volume"]).rolling(period).sum() / ohlcv["volume"].rolling(
            period
        ).sum()


# Singleton default registry
_default_registry: Optional[IndicatorRegistry] = None


def get_default_registry() -> IndicatorRegistry:
    """Get the default indicator registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = IndicatorRegistry()
    return _default_registry
