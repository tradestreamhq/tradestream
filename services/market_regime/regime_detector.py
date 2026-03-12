"""
Market regime detection engine.

Classifies market conditions into regimes using rolling technical indicators:
- SMA crossovers (20/50/200)
- ATR percentile for volatility
- Drawdown depth for crisis detection
- Realized volatility as VIX-equivalent
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Regime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CRISIS = "crisis"


@dataclass
class RegimeClassification:
    regime: Regime
    confidence: float
    symbol: str
    timestamp: datetime
    indicators: Dict[str, float] = field(default_factory=dict)


@dataclass
class RegimeTransition:
    symbol: str
    previous_regime: Regime
    new_regime: Regime
    timestamp: datetime
    confidence: float


class RegimeDetector:
    """Detects market regimes from OHLCV candle data."""

    # Lookback windows
    SMA_SHORT = 20
    SMA_MED = 50
    SMA_LONG = 200
    ATR_PERIOD = 14
    ATR_PERCENTILE_WINDOW = 100
    VOLATILITY_WINDOW = 20
    DRAWDOWN_WINDOW = 60

    # Thresholds
    CRISIS_DRAWDOWN = -0.20
    HIGH_VOL_ATR_PERCENTILE = 80.0
    LOW_VOL_ATR_PERCENTILE = 20.0
    TREND_SMA_SEPARATION = 0.005  # 0.5% minimum separation for trend
    RANGE_BOUND_BAND = 0.02  # 2% band for range-bound

    def __init__(self):
        self._history: Dict[str, List[RegimeClassification]] = {}
        self._transitions: List[RegimeTransition] = []

    def classify(
        self,
        symbol: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        timestamps: Optional[List[datetime]] = None,
    ) -> Optional[RegimeClassification]:
        """Classify the current market regime for a symbol.

        Requires at least 200 data points (for 200 SMA).
        """
        min_required = self.SMA_LONG
        if len(closes) < min_required:
            logger.warning(
                "Insufficient data for %s: %d candles (need %d)",
                symbol,
                len(closes),
                min_required,
            )
            return None

        sma_20 = _sma(closes, self.SMA_SHORT)
        sma_50 = _sma(closes, self.SMA_MED)
        sma_200 = _sma(closes, self.SMA_LONG)
        atr = _atr(highs, lows, closes, self.ATR_PERIOD)
        atr_pct = _atr_percentile(
            highs, lows, closes, self.ATR_PERIOD, self.ATR_PERCENTILE_WINDOW
        )
        drawdown = _max_drawdown(closes, self.DRAWDOWN_WINDOW)
        realized_vol = _realized_volatility(closes, self.VOLATILITY_WINDOW)

        current_price = closes[-1]
        indicators = {
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "atr": atr,
            "atr_percentile": atr_pct,
            "drawdown": drawdown,
            "realized_volatility": realized_vol,
            "price": current_price,
        }

        regime, confidence = self._determine_regime(
            current_price, sma_20, sma_50, sma_200, atr_pct, drawdown, realized_vol
        )

        ts = (
            timestamps[-1]
            if timestamps
            else datetime.now(timezone.utc)
        )
        classification = RegimeClassification(
            regime=regime,
            confidence=confidence,
            symbol=symbol,
            timestamp=ts,
            indicators=indicators,
        )

        self._record(symbol, classification)
        return classification

    def get_history(
        self, symbol: str, days: int = 90
    ) -> List[RegimeClassification]:
        return list(self._history.get(symbol, []))[-days:]

    def get_transitions(self, symbol: Optional[str] = None) -> List[RegimeTransition]:
        if symbol:
            return [t for t in self._transitions if t.symbol == symbol]
        return list(self._transitions)

    def _record(self, symbol: str, classification: RegimeClassification) -> None:
        history = self._history.setdefault(symbol, [])
        if history and history[-1].regime != classification.regime:
            transition = RegimeTransition(
                symbol=symbol,
                previous_regime=history[-1].regime,
                new_regime=classification.regime,
                timestamp=classification.timestamp,
                confidence=classification.confidence,
            )
            self._transitions.append(transition)
            logger.info(
                "Regime transition for %s: %s -> %s (confidence=%.2f)",
                symbol,
                transition.previous_regime.value,
                transition.new_regime.value,
                transition.confidence,
            )
        history.append(classification)

    def _determine_regime(
        self,
        price: float,
        sma_20: float,
        sma_50: float,
        sma_200: float,
        atr_percentile: float,
        drawdown: float,
        realized_vol: float,
    ) -> tuple:
        """Determine regime and confidence from indicators.

        Priority order: crisis > high_volatility > trending > range_bound > low_volatility.
        """
        # Crisis: deep drawdown
        if drawdown <= self.CRISIS_DRAWDOWN:
            severity = min(abs(drawdown) / abs(self.CRISIS_DRAWDOWN), 2.0)
            confidence = min(0.5 + severity * 0.25, 1.0)
            return Regime.CRISIS, round(confidence, 3)

        # High volatility: ATR in top percentile
        if atr_percentile >= self.HIGH_VOL_ATR_PERCENTILE:
            confidence = min(
                0.5 + (atr_percentile - self.HIGH_VOL_ATR_PERCENTILE) / 40.0, 1.0
            )
            return Regime.HIGH_VOLATILITY, round(confidence, 3)

        # Trending up: price > SMA20 > SMA50 > SMA200
        sma_ref = sma_200 if sma_200 > 0 else 1.0
        if (
            price > sma_20
            and sma_20 > sma_50
            and sma_50 > sma_200
            and (sma_20 - sma_200) / sma_ref > self.TREND_SMA_SEPARATION
        ):
            spread = (sma_20 - sma_200) / sma_ref
            confidence = min(0.5 + spread * 10.0, 1.0)
            return Regime.TRENDING_UP, round(confidence, 3)

        # Trending down: price < SMA20 < SMA50 < SMA200
        if (
            price < sma_20
            and sma_20 < sma_50
            and sma_50 < sma_200
            and (sma_200 - sma_20) / sma_ref > self.TREND_SMA_SEPARATION
        ):
            spread = (sma_200 - sma_20) / sma_ref
            confidence = min(0.5 + spread * 10.0, 1.0)
            return Regime.TRENDING_DOWN, round(confidence, 3)

        # Low volatility: ATR in bottom percentile
        if atr_percentile <= self.LOW_VOL_ATR_PERCENTILE:
            confidence = min(
                0.5 + (self.LOW_VOL_ATR_PERCENTILE - atr_percentile) / 40.0, 1.0
            )
            return Regime.LOW_VOLATILITY, round(confidence, 3)

        # Default: range-bound
        return Regime.RANGE_BOUND, 0.5


def _sma(values: List[float], period: int) -> float:
    """Simple moving average of the last `period` values."""
    if len(values) < period:
        return 0.0
    return sum(values[-period:]) / period


def _true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _atr(
    highs: List[float], lows: List[float], closes: List[float], period: int
) -> float:
    """Average True Range over the last `period` candles."""
    n = len(closes)
    if n < period + 1:
        return 0.0
    trs = []
    for i in range(n - period, n):
        trs.append(_true_range(highs[i], lows[i], closes[i - 1]))
    return sum(trs) / len(trs)


def _atr_percentile(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    atr_period: int,
    window: int,
) -> float:
    """Percentile rank of current ATR within a rolling window."""
    n = len(closes)
    needed = atr_period + window
    if n < needed:
        window = max(n - atr_period, 1)

    atrs = []
    for end in range(n - window, n + 1):
        if end < atr_period + 1:
            continue
        segment_h = highs[end - atr_period - 1 : end]
        segment_l = lows[end - atr_period - 1 : end]
        segment_c = closes[end - atr_period - 1 : end]
        atrs.append(_atr(segment_h, segment_l, segment_c, atr_period))

    if not atrs:
        return 50.0
    current = atrs[-1]
    count_below = sum(1 for a in atrs if a < current)
    return (count_below / len(atrs)) * 100.0


def _max_drawdown(closes: List[float], window: int) -> float:
    """Maximum drawdown over the last `window` candles."""
    segment = closes[-window:] if len(closes) >= window else closes
    if not segment:
        return 0.0
    peak = segment[0]
    max_dd = 0.0
    for price in segment:
        if price > peak:
            peak = price
        dd = (price - peak) / peak if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _realized_volatility(closes: List[float], window: int) -> float:
    """Annualized realized volatility from log returns."""
    segment = closes[-window - 1 :] if len(closes) >= window + 1 else closes
    if len(segment) < 2:
        return 0.0
    log_returns = []
    for i in range(1, len(segment)):
        if segment[i - 1] > 0 and segment[i] > 0:
            log_returns.append(math.log(segment[i] / segment[i - 1]))
    if not log_returns:
        return 0.0
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
    return math.sqrt(variance * 252)
