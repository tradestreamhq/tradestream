"""Data validation and anomaly detection for market data."""

from dataclasses import dataclass
from typing import List, Optional

from absl import logging

from services.market_data_pipeline.schema import OHLCV, Trade


@dataclass
class ValidationResult:
    """Result of validating a data record."""

    is_valid: bool
    warnings: List[str]


class OHLCVValidator:
    """Validates OHLCV records and detects anomalies."""

    def __init__(
        self,
        max_price_change_pct: float = 50.0,
        max_gap_ms: int = 300_000,  # 5 minutes for 1m candles
        min_volume: float = 0.0,
    ):
        self.max_price_change_pct = max_price_change_pct
        self.max_gap_ms = max_gap_ms
        self.min_volume = min_volume
        self._last_record: Optional[OHLCV] = None

    def validate(self, record: OHLCV) -> ValidationResult:
        """Validate a single OHLCV record, optionally against the previous one."""
        warnings = []

        # Basic structural validation
        if record.high < record.low:
            return ValidationResult(False, ["high < low"])
        if record.open <= 0 or record.close <= 0:
            return ValidationResult(False, ["non-positive price"])
        if record.volume < 0:
            return ValidationResult(False, ["negative volume"])
        if record.timestamp_ms <= 0:
            return ValidationResult(False, ["non-positive timestamp"])

        # Cross-record anomaly detection
        if self._last_record is not None:
            # Gap detection
            gap = record.timestamp_ms - self._last_record.timestamp_ms
            if gap > self.max_gap_ms:
                warnings.append(
                    f"data gap: {gap}ms between records "
                    f"(threshold: {self.max_gap_ms}ms)"
                )
            if gap < 0:
                return ValidationResult(False, ["timestamp went backwards"])

            # Spike detection
            prev_close = self._last_record.close
            if prev_close > 0:
                pct_change = abs(record.open - prev_close) / prev_close * 100
                if pct_change > self.max_price_change_pct:
                    warnings.append(
                        f"price spike: {pct_change:.1f}% change "
                        f"(threshold: {self.max_price_change_pct}%)"
                    )

        # Stale data detection: close == open == high == low
        if record.open == record.high == record.low == record.close:
            warnings.append("stale data: all prices identical")

        self._last_record = record
        return ValidationResult(True, warnings)

    def validate_batch(self, records: List[OHLCV]) -> List[OHLCV]:
        """Validate a batch, returning only valid records. Logs warnings."""
        self._last_record = None
        valid = []
        for record in sorted(records, key=lambda r: r.timestamp_ms):
            result = self.validate(record)
            if not result.is_valid:
                logging.warning(
                    f"Dropping invalid OHLCV {record.symbol}@{record.timestamp_ms}: "
                    f"{result.warnings}"
                )
                continue
            for w in result.warnings:
                logging.warning(
                    f"OHLCV anomaly {record.symbol}@{record.timestamp_ms}: {w}"
                )
            valid.append(record)
        return valid

    def reset(self):
        """Reset cross-record state."""
        self._last_record = None


class TradeValidator:
    """Validates trade records."""

    def __init__(self, max_price_change_pct: float = 50.0):
        self.max_price_change_pct = max_price_change_pct
        self._last_price: Optional[float] = None

    def validate(self, record: Trade) -> ValidationResult:
        warnings = []
        if record.price <= 0:
            return ValidationResult(False, ["non-positive price"])
        if record.volume <= 0:
            return ValidationResult(False, ["non-positive volume"])
        if record.timestamp_ms <= 0:
            return ValidationResult(False, ["non-positive timestamp"])

        if self._last_price is not None and self._last_price > 0:
            pct_change = abs(record.price - self._last_price) / self._last_price * 100
            if pct_change > self.max_price_change_pct:
                warnings.append(
                    f"price spike: {pct_change:.1f}% "
                    f"(threshold: {self.max_price_change_pct}%)"
                )

        self._last_price = record.price
        return ValidationResult(True, warnings)

    def validate_batch(self, records: List[Trade]) -> List[Trade]:
        self._last_price = None
        valid = []
        for record in sorted(records, key=lambda r: r.timestamp_ms):
            result = self.validate(record)
            if not result.is_valid:
                logging.warning(
                    f"Dropping invalid trade {record.symbol}@{record.timestamp_ms}: "
                    f"{result.warnings}"
                )
                continue
            for w in result.warnings:
                logging.warning(
                    f"Trade anomaly {record.symbol}@{record.timestamp_ms}: {w}"
                )
            valid.append(record)
        return valid

    def reset(self):
        self._last_price = None
