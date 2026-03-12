"""Replay capability for reading market data from files for backtesting."""

import json
from pathlib import Path
from typing import Iterator, List, Union

from absl import logging

from services.market_data_pipeline.adapters import get_adapter, ExchangeAdapter
from services.market_data_pipeline.schema import OHLCV, Trade, OrderBookSnapshot
from services.market_data_pipeline.validation import OHLCVValidator, TradeValidator


class FileReplaySource:
    """Reads market data from JSON files and normalizes via exchange adapters.

    Supports replaying historical data for backtesting. Each file should contain
    a JSON array of raw exchange records, or newline-delimited JSON records.
    """

    def __init__(
        self,
        adapter: ExchangeAdapter,
        validate: bool = True,
    ):
        self.adapter = adapter
        self.validate = validate
        self._ohlcv_validator = OHLCVValidator() if validate else None
        self._trade_validator = TradeValidator() if validate else None

    def replay_ohlcv(self, file_path: Union[str, Path]) -> List[OHLCV]:
        """Load and normalize OHLCV data from a file."""
        raw_records = self._load_file(file_path)
        normalized = self.adapter.normalize_ohlcv_batch(raw_records)
        if self.validate and self._ohlcv_validator:
            self._ohlcv_validator.reset()
            normalized = self._ohlcv_validator.validate_batch(normalized)
        return sorted(normalized, key=lambda r: r.timestamp_ms)

    def replay_trades(self, file_path: Union[str, Path]) -> List[Trade]:
        """Load and normalize trade data from a file."""
        raw_records = self._load_file(file_path)
        normalized = self.adapter.normalize_trade_batch(raw_records)
        if self.validate and self._trade_validator:
            self._trade_validator.reset()
            normalized = self._trade_validator.validate_batch(normalized)
        return sorted(normalized, key=lambda r: r.timestamp_ms)

    def replay_ohlcv_iter(self, file_path: Union[str, Path]) -> Iterator[OHLCV]:
        """Iterate over OHLCV records one at a time (memory-efficient)."""
        for record in self.replay_ohlcv(file_path):
            yield record

    def _load_file(self, file_path: Union[str, Path]) -> List[dict]:
        """Load JSON records from a file.

        Supports:
        - JSON array: [{"key": "val"}, ...]
        - Newline-delimited JSON: one object per line
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        text = path.read_text().strip()
        if not text:
            return []

        if text.startswith("["):
            return json.loads(text)

        # Newline-delimited JSON
        records = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records
