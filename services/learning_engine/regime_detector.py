"""Market Regime Detector — classifies market conditions into regimes.

Detects four primary market regimes based on volatility, trend strength,
and volume analysis:
  - trending_up: Strong upward price movement with directional momentum
  - trending_down: Strong downward price movement with directional momentum
  - ranging: Low directional movement, price oscillating in a band
  - volatile: High volatility without clear direction
  - quiet: Low volatility, low volume, minimal price movement
"""

import json
import math
import uuid
from datetime import datetime, timezone

from absl import logging


# Regime detection thresholds (tunable).
REGIME_THRESHOLDS = {
    "volatility_high": 0.03,     # annualized vol > 3% per period = high
    "volatility_low": 0.01,      # annualized vol < 1% per period = low
    "trend_strong": 0.6,         # ADX-like trend strength > 0.6 = trending
    "trend_weak": 0.3,           # trend strength < 0.3 = no trend
    "volume_surge": 1.5,         # volume > 1.5x average = elevated
    "volume_quiet": 0.5,         # volume < 0.5x average = quiet
}


class RegimeDetector:
    """Classifies the current market regime from price/volume data.

    Works with raw candle data (OHLCV) passed as lists of dicts or
    queried from the database.
    """

    def __init__(self, db_connection=None, thresholds=None):
        self._conn = db_connection
        self._thresholds = thresholds or REGIME_THRESHOLDS

    # ── Core Detection ──────────────────────────────────────────────────

    def detect(self, candles, instrument="UNKNOWN"):
        """Detect the current market regime from OHLCV candle data.

        Args:
            candles: List of dicts with keys: open, high, low, close, volume.
                     Must be sorted chronologically (oldest first).
            instrument: Instrument identifier for logging/storage.

        Returns:
            dict with regime_type, confidence, and indicator values.
        """
        if len(candles) < 20:
            return {
                "regime_type": "unknown",
                "confidence": 0.0,
                "indicators": {},
                "reason": "Insufficient data (need >= 20 candles)",
            }

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c.get("volume", 0)) for c in candles]

        volatility = self._calculate_volatility(closes)
        trend_strength = self._calculate_trend_strength(closes)
        trend_direction = self._calculate_trend_direction(closes)
        volume_ratio = self._calculate_volume_ratio(volumes)
        atr_ratio = self._calculate_atr_ratio(highs, lows, closes)

        indicators = {
            "volatility": round(volatility, 6),
            "trend_strength": round(trend_strength, 4),
            "trend_direction": round(trend_direction, 4),
            "volume_ratio": round(volume_ratio, 4),
            "atr_ratio": round(atr_ratio, 6),
        }

        regime_type, confidence = self._classify(
            volatility, trend_strength, trend_direction, volume_ratio
        )

        result = {
            "regime_type": regime_type,
            "confidence": round(confidence, 4),
            "indicators": indicators,
            "instrument": instrument,
        }

        logging.info(
            "Regime detected: %s (confidence=%.2f) for %s",
            regime_type, confidence, instrument,
        )
        return result

    def _classify(self, volatility, trend_strength, trend_direction, volume_ratio):
        """Classify regime based on indicator values. Returns (type, confidence)."""
        t = self._thresholds

        # High volatility without trend → volatile
        if volatility > t["volatility_high"] and trend_strength < t["trend_weak"]:
            confidence = min(1.0, (volatility / t["volatility_high"]) * 0.5 +
                           (1 - trend_strength) * 0.5)
            return "volatile", confidence

        # Strong trend → trending_up or trending_down
        if trend_strength > t["trend_strong"]:
            confidence = min(1.0, trend_strength)
            if trend_direction > 0:
                return "trending_up", confidence
            else:
                return "trending_down", confidence

        # Low volatility and low volume → quiet
        if volatility < t["volatility_low"] and volume_ratio < t["volume_quiet"]:
            confidence = min(1.0, (1 - volatility / t["volatility_low"]) * 0.5 +
                           (1 - volume_ratio) * 0.5)
            return "quiet", confidence

        # Low volatility alone → quiet
        if volatility < t["volatility_low"]:
            confidence = min(1.0, 1 - volatility / t["volatility_low"])
            return "quiet", confidence * 0.7

        # Default: ranging
        confidence = min(1.0, (1 - trend_strength / t["trend_strong"]) * 0.7 +
                       (1 - abs(volatility - t["volatility_low"]) /
                        (t["volatility_high"] - t["volatility_low"])) * 0.3)
        return "ranging", max(0.3, confidence)

    # ── Indicators ──────────────────────────────────────────────────────

    def _calculate_volatility(self, closes):
        """Calculate rolling volatility as standard deviation of returns."""
        if len(closes) < 2:
            return 0.0
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1]
                   for i in range(1, len(closes)) if closes[i - 1] != 0]
        if not returns:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance)

    def _calculate_trend_strength(self, closes):
        """Calculate trend strength using a simplified ADX-like metric.

        Measures the ratio of directional movement to total movement.
        Returns a value between 0 (no trend) and 1 (perfect trend).
        """
        if len(closes) < 10:
            return 0.0
        n = len(closes)
        # Linear regression R-squared as trend strength proxy
        x_mean = (n - 1) / 2.0
        y_mean = sum(closes) / n
        ss_xy = sum((i - x_mean) * (closes[i] - y_mean) for i in range(n))
        ss_xx = sum((i - x_mean) ** 2 for i in range(n))
        ss_yy = sum((closes[i] - y_mean) ** 2 for i in range(n))
        if ss_xx == 0 or ss_yy == 0:
            return 0.0
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)
        return min(1.0, r_squared)

    def _calculate_trend_direction(self, closes):
        """Calculate trend direction: positive = up, negative = down."""
        if len(closes) < 10:
            return 0.0
        # Simple: compare recent mean to older mean
        mid = len(closes) // 2
        old_mean = sum(closes[:mid]) / mid
        new_mean = sum(closes[mid:]) / (len(closes) - mid)
        if old_mean == 0:
            return 0.0
        return (new_mean - old_mean) / old_mean

    def _calculate_volume_ratio(self, volumes):
        """Calculate recent volume relative to average volume."""
        if not volumes or all(v == 0 for v in volumes):
            return 1.0
        avg_volume = sum(volumes) / len(volumes)
        if avg_volume == 0:
            return 1.0
        recent_n = max(1, len(volumes) // 4)
        recent_avg = sum(volumes[-recent_n:]) / recent_n
        return recent_avg / avg_volume

    def _calculate_atr_ratio(self, highs, lows, closes):
        """Calculate Average True Range ratio (ATR / close price)."""
        if len(highs) < 2:
            return 0.0
        true_ranges = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)
        if not true_ranges:
            return 0.0
        atr = sum(true_ranges) / len(true_ranges)
        last_close = closes[-1]
        if last_close == 0:
            return 0.0
        return atr / last_close

    # ── Database Operations ─────────────────────────────────────────────

    def store_regime(self, regime_result):
        """Store a detected regime in the database."""
        if not self._conn:
            return None
        regime_id = str(uuid.uuid4())
        with self._conn.cursor() as cur:
            # Close any open regime for this instrument
            cur.execute(
                """
                UPDATE market_regimes
                SET ended_at = NOW()
                WHERE instrument = %s AND ended_at IS NULL
                """,
                (regime_result["instrument"],),
            )
            cur.execute(
                """
                INSERT INTO market_regimes (id, instrument, regime_type, confidence, indicators)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    regime_id,
                    regime_result["instrument"],
                    regime_result["regime_type"],
                    regime_result["confidence"],
                    json.dumps(regime_result["indicators"]),
                ),
            )
        self._conn.commit()
        return regime_id

    def get_current_regime(self, instrument):
        """Get the current (open) regime for an instrument."""
        if not self._conn:
            return None
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, instrument, regime_type, confidence, indicators, started_at
                FROM market_regimes
                WHERE instrument = %s AND ended_at IS NULL
                ORDER BY started_at DESC LIMIT 1
                """,
                (instrument,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "instrument": row[1],
                "regime_type": row[2],
                "confidence": float(row[3]),
                "indicators": row[4],
                "started_at": row[5],
            }

    def get_regime_history(self, instrument, limit=50):
        """Get recent regime history for an instrument."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, instrument, regime_type, confidence, indicators,
                       started_at, ended_at
                FROM market_regimes
                WHERE instrument = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (instrument, limit),
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
