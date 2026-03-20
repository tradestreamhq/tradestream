"""
Market Scanner — core scanning logic.

Evaluates configured scan conditions against market data:
price breakout, volume spike, RSI extremes, moving average crossover.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScanCondition(str, Enum):
    PRICE_BREAKOUT = "price_breakout"
    VOLUME_SPIKE = "volume_spike"
    RSI_EXTREME = "rsi_extreme"
    MA_CROSSOVER = "ma_crossover"


class ScanDefinition(BaseModel):
    """User-defined scan configuration."""

    pairs: List[str] = Field(..., min_length=1, description="Trading pairs to scan")
    conditions: List[ScanCondition] = Field(
        ..., min_length=1, description="Conditions to check"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Condition-specific parameters"
    )


class ScanResult(BaseModel):
    """Result of a scan evaluation."""

    pair: str
    condition_met: str
    timestamp: str
    details: Dict[str, Any]


class StoredScan(BaseModel):
    """A persisted scan definition."""

    id: str
    pairs: List[str]
    conditions: List[ScanCondition]
    params: Dict[str, Any]
    created_at: str


class MarketScanner:
    """Scans configured pairs for market conditions."""

    def __init__(self, market_data_client):
        self._market_data = market_data_client
        self._scans: Dict[str, StoredScan] = {}
        self._results: List[ScanResult] = []

    def create_scan(self, definition: ScanDefinition) -> StoredScan:
        scan_id = str(uuid.uuid4())
        scan = StoredScan(
            id=scan_id,
            pairs=definition.pairs,
            conditions=definition.conditions,
            params=definition.params,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._scans[scan_id] = scan
        return scan

    def delete_scan(self, scan_id: str) -> bool:
        if scan_id in self._scans:
            del self._scans[scan_id]
            return True
        return False

    def get_scan(self, scan_id: str) -> Optional[StoredScan]:
        return self._scans.get(scan_id)

    def get_results(
        self, pair: Optional[str] = None, condition: Optional[str] = None
    ) -> List[ScanResult]:
        results = self._results
        if pair:
            results = [r for r in results if r.pair == pair]
        if condition:
            results = [r for r in results if r.condition_met == condition]
        return results

    def run_scans(self) -> List[ScanResult]:
        """Execute all configured scans and return new results."""
        new_results = []
        for scan in self._scans.values():
            for pair in scan.pairs:
                for condition in scan.conditions:
                    result = self._evaluate(pair, condition, scan.params)
                    if result:
                        new_results.append(result)
        self._results.extend(new_results)
        return new_results

    def _evaluate(
        self, pair: str, condition: ScanCondition, params: Dict[str, Any]
    ) -> Optional[ScanResult]:
        now = datetime.now(timezone.utc).isoformat()
        try:
            if condition == ScanCondition.PRICE_BREAKOUT:
                return self._check_price_breakout(pair, params, now)
            elif condition == ScanCondition.VOLUME_SPIKE:
                return self._check_volume_spike(pair, params, now)
            elif condition == ScanCondition.RSI_EXTREME:
                return self._check_rsi_extreme(pair, params, now)
            elif condition == ScanCondition.MA_CROSSOVER:
                return self._check_ma_crossover(pair, params, now)
        except Exception as e:
            logger.warning("Scan evaluation failed for %s/%s: %s", pair, condition, e)
        return None

    def _check_price_breakout(
        self, pair: str, params: Dict[str, Any], now: str
    ) -> Optional[ScanResult]:
        candles = self._market_data.get_candles(pair, timeframe="1h", limit=24)
        if not candles or len(candles) < 2:
            return None
        highs = [c["high"] for c in candles[:-1]]
        lows = [c["low"] for c in candles[:-1]]
        current = candles[-1]
        resistance = max(highs)
        support = min(lows)
        if current["close"] > resistance:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.PRICE_BREAKOUT,
                timestamp=now,
                details={
                    "direction": "bullish",
                    "price": current["close"],
                    "resistance": resistance,
                },
            )
        if current["close"] < support:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.PRICE_BREAKOUT,
                timestamp=now,
                details={
                    "direction": "bearish",
                    "price": current["close"],
                    "support": support,
                },
            )
        return None

    def _check_volume_spike(
        self, pair: str, params: Dict[str, Any], now: str
    ) -> Optional[ScanResult]:
        threshold = params.get("volume_spike_threshold", 2.0)
        candles = self._market_data.get_candles(pair, timeframe="1h", limit=24)
        if not candles or len(candles) < 2:
            return None
        volumes = [c["volume"] for c in candles[:-1]]
        avg_volume = sum(volumes) / len(volumes)
        current_volume = candles[-1]["volume"]
        if avg_volume > 0 and current_volume > avg_volume * threshold:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.VOLUME_SPIKE,
                timestamp=now,
                details={
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "ratio": round(current_volume / avg_volume, 2),
                },
            )
        return None

    def _check_rsi_extreme(
        self, pair: str, params: Dict[str, Any], now: str
    ) -> Optional[ScanResult]:
        overbought = params.get("rsi_overbought", 70)
        oversold = params.get("rsi_oversold", 30)
        period = params.get("rsi_period", 14)
        candles = self._market_data.get_candles(pair, timeframe="1h", limit=period + 1)
        if not candles or len(candles) < period + 1:
            return None
        closes = [c["close"] for c in candles]
        rsi = self._compute_rsi(closes, period)
        if rsi is None:
            return None
        if rsi >= overbought:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.RSI_EXTREME,
                timestamp=now,
                details={"rsi": round(rsi, 2), "signal": "overbought"},
            )
        if rsi <= oversold:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.RSI_EXTREME,
                timestamp=now,
                details={"rsi": round(rsi, 2), "signal": "oversold"},
            )
        return None

    def _check_ma_crossover(
        self, pair: str, params: Dict[str, Any], now: str
    ) -> Optional[ScanResult]:
        fast_period = params.get("ma_fast_period", 9)
        slow_period = params.get("ma_slow_period", 21)
        needed = slow_period + 1
        candles = self._market_data.get_candles(pair, timeframe="1h", limit=needed)
        if not candles or len(candles) < needed:
            return None
        closes = [c["close"] for c in candles]
        fast_prev = sum(closes[-(fast_period + 1) : -1]) / fast_period
        fast_curr = sum(closes[-fast_period:]) / fast_period
        slow_prev = sum(closes[-(slow_period + 1) : -1]) / slow_period
        slow_curr = sum(closes[-slow_period:]) / slow_period
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.MA_CROSSOVER,
                timestamp=now,
                details={
                    "signal": "bullish",
                    "fast_ma": round(fast_curr, 2),
                    "slow_ma": round(slow_curr, 2),
                },
            )
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            return ScanResult(
                pair=pair,
                condition_met=ScanCondition.MA_CROSSOVER,
                timestamp=now,
                details={
                    "signal": "bearish",
                    "fast_ma": round(fast_curr, 2),
                    "slow_ma": round(slow_curr, 2),
                },
            )
        return None

    @staticmethod
    def _compute_rsi(closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
