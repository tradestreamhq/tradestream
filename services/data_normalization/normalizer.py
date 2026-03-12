"""High-level normalization entry point for candle data from multiple exchanges."""

from typing import Any, Dict, List

from absl import logging

from services.data_normalization.exchange_adapters import get_adapter
from services.data_normalization.models import NormalizedCandle


def normalize_candles(
    exchange: str, raw_candles: List[Dict[str, Any]]
) -> List[NormalizedCandle]:
    """Normalize a batch of raw candles from a given exchange.

    Args:
        exchange: Exchange name (e.g. "binance", "coinbase", "kraken").
        raw_candles: List of raw candle dicts/lists in exchange-native format.

    Returns:
        List of validated NormalizedCandle instances. Invalid candles are
        logged and skipped.
    """
    adapter = get_adapter(exchange)
    candles = adapter.normalize_batch(raw_candles)
    logging.info(
        f"Normalized {len(candles)}/{len(raw_candles)} candles from {exchange}"
    )
    return candles


def normalize_single(
    exchange: str, raw_candle: Dict[str, Any]
) -> NormalizedCandle:
    """Normalize a single raw candle. Raises on invalid data."""
    adapter = get_adapter(exchange)
    return adapter.normalize(raw_candle)
