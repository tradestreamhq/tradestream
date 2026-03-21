"""
Multi-Timeframe Analysis Engine.

Evaluates strategy conditions across multiple timeframes simultaneously,
computes confluence scores, and produces aligned snapshots.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

# How far back each timeframe should look to get enough candles for analysis.
_TIMEFRAME_LOOKBACK = {
    "1m": "-2h",
    "5m": "-10h",
    "15m": "-30h",
    "1h": "-5d",
    "4h": "-20d",
    "1d": "-120d",
}

# Minimum candles required per timeframe for meaningful analysis.
_MIN_CANDLES = 20


class Signal(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class TimeframeAnalysis:
    timeframe: str
    signal: Signal
    strength: float  # 0.0 to 1.0
    indicators: Dict[str, Any] = field(default_factory=dict)
    candle_count: int = 0


@dataclass
class ConfluenceResult:
    pair: str
    score: float  # -1.0 (strong bearish) to 1.0 (strong bullish)
    signal: Signal
    agreeing_timeframes: List[str]
    total_timeframes: int
    analyses: Dict[str, TimeframeAnalysis] = field(default_factory=dict)


# Timeframe weights — higher timeframes carry more weight.
_TIMEFRAME_WEIGHTS = {
    "1m": 0.05,
    "5m": 0.10,
    "15m": 0.15,
    "1h": 0.20,
    "4h": 0.25,
    "1d": 0.25,
}


class MultiTimeframeAnalyzer:
    """Analyze a trading pair across multiple timeframes using candle data."""

    def __init__(self, influxdb_client):
        self._influx = influxdb_client

    def _compute_sma(self, closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period

    def _compute_ema(self, closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period:
            return None
        multiplier = 2.0 / (period + 1)
        ema = sum(closes[:period]) / period
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _compute_rsi(self, closes: List[float], period: int = 14) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _analyze_candles(
        self, candles: List[Dict[str, Any]], timeframe: str
    ) -> TimeframeAnalysis:
        """Derive a signal from candle data for a single timeframe."""
        closes = [c["close"] for c in candles if c.get("close") is not None]

        if len(closes) < _MIN_CANDLES:
            return TimeframeAnalysis(
                timeframe=timeframe,
                signal=Signal.NEUTRAL,
                strength=0.0,
                candle_count=len(closes),
            )

        sma_short = self._compute_sma(closes, 10)
        sma_long = self._compute_sma(closes, 20)
        ema_short = self._compute_ema(closes, 10)
        ema_long = self._compute_ema(closes, 20)
        rsi = self._compute_rsi(closes)
        current_price = closes[-1]

        indicators = {
            "sma_10": round(sma_short, 8) if sma_short else None,
            "sma_20": round(sma_long, 8) if sma_long else None,
            "ema_10": round(ema_short, 8) if ema_short else None,
            "ema_20": round(ema_long, 8) if ema_long else None,
            "rsi_14": round(rsi, 2) if rsi else None,
            "price": current_price,
        }

        # Score individual signals and combine.
        bullish_points = 0.0
        bearish_points = 0.0
        total_checks = 0

        # SMA crossover
        if sma_short is not None and sma_long is not None:
            total_checks += 1
            if sma_short > sma_long:
                bullish_points += 1
            else:
                bearish_points += 1

        # EMA crossover
        if ema_short is not None and ema_long is not None:
            total_checks += 1
            if ema_short > ema_long:
                bullish_points += 1
            else:
                bearish_points += 1

        # Price vs SMA
        if sma_long is not None:
            total_checks += 1
            if current_price > sma_long:
                bullish_points += 1
            else:
                bearish_points += 1

        # RSI
        if rsi is not None:
            total_checks += 1
            if rsi > 60:
                bullish_points += 1
            elif rsi < 40:
                bearish_points += 1
            else:
                bullish_points += 0.5
                bearish_points += 0.5

        if total_checks == 0:
            signal = Signal.NEUTRAL
            strength = 0.0
        else:
            net = (bullish_points - bearish_points) / total_checks
            if net > 0.15:
                signal = Signal.BULLISH
            elif net < -0.15:
                signal = Signal.BEARISH
            else:
                signal = Signal.NEUTRAL
            strength = min(abs(net), 1.0)

        return TimeframeAnalysis(
            timeframe=timeframe,
            signal=signal,
            strength=round(strength, 4),
            indicators=indicators,
            candle_count=len(closes),
        )

    def get_snapshot(
        self, pair: str, timeframes: Optional[List[str]] = None
    ) -> Dict[str, TimeframeAnalysis]:
        """Return per-timeframe analysis for the given pair."""
        tfs = timeframes or TIMEFRAMES
        results: Dict[str, TimeframeAnalysis] = {}
        for tf in tfs:
            lookback = _TIMEFRAME_LOOKBACK.get(tf, "-1h")
            candles = self._influx.get_candles(
                symbol=pair, timeframe=tf, start=lookback, limit=200
            )
            results[tf] = self._analyze_candles(candles, tf)
        return results

    def get_confluence(
        self, pair: str, timeframes: Optional[List[str]] = None
    ) -> ConfluenceResult:
        """Compute a weighted confluence score across timeframes."""
        analyses = self.get_snapshot(pair, timeframes)

        weighted_sum = 0.0
        total_weight = 0.0
        agreeing: List[str] = []
        dominant_signal = Signal.NEUTRAL

        for tf, analysis in analyses.items():
            weight = _TIMEFRAME_WEIGHTS.get(tf, 0.1)
            total_weight += weight
            if analysis.signal == Signal.BULLISH:
                weighted_sum += weight * analysis.strength
            elif analysis.signal == Signal.BEARISH:
                weighted_sum -= weight * analysis.strength

        if total_weight == 0:
            score = 0.0
        else:
            score = weighted_sum / total_weight

        if score > 0.15:
            dominant_signal = Signal.BULLISH
        elif score < -0.15:
            dominant_signal = Signal.BEARISH
        else:
            dominant_signal = Signal.NEUTRAL

        for tf, analysis in analyses.items():
            if analysis.signal == dominant_signal and dominant_signal != Signal.NEUTRAL:
                agreeing.append(tf)

        return ConfluenceResult(
            pair=pair,
            score=round(score, 4),
            signal=dominant_signal,
            agreeing_timeframes=agreeing,
            total_timeframes=len(analyses),
            analyses=analyses,
        )
