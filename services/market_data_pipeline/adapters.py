"""Exchange-specific adapters for normalizing raw data into unified schema."""

import abc
import json
from typing import List

from absl import logging

from services.market_data_pipeline.schema import (
    OHLCV,
    Trade,
    OrderBookSnapshot,
    PriceLevel,
)


class ExchangeAdapter(abc.ABC):
    """Base class for exchange-specific data adapters."""

    @property
    @abc.abstractmethod
    def exchange_name(self) -> str:
        """Canonical exchange identifier."""

    @abc.abstractmethod
    def normalize_ohlcv(self, raw: dict) -> OHLCV:
        """Convert a single raw OHLCV record to unified format."""

    @abc.abstractmethod
    def normalize_trade(self, raw: dict) -> Trade:
        """Convert a single raw trade record to unified format."""

    @abc.abstractmethod
    def normalize_order_book(self, raw: dict) -> OrderBookSnapshot:
        """Convert a raw order book snapshot to unified format."""

    def normalize_ohlcv_batch(self, records: List[dict]) -> List[OHLCV]:
        results = []
        for record in records:
            try:
                results.append(self.normalize_ohlcv(record))
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(
                    f"{self.exchange_name}: Skipping invalid OHLCV record: {e}"
                )
        return results

    def normalize_trade_batch(self, records: List[dict]) -> List[Trade]:
        results = []
        for record in records:
            try:
                results.append(self.normalize_trade(record))
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(
                    f"{self.exchange_name}: Skipping invalid trade record: {e}"
                )
        return results


class BinanceAdapter(ExchangeAdapter):
    """Adapter for Binance exchange data format.

    Binance OHLCV format (REST /api/v3/klines):
        [open_time, open, high, low, close, volume, close_time, ...]

    Binance trade format (REST /api/v3/trades):
        {"id": ..., "price": "...", "qty": "...", "time": ..., "isBuyerMaker": bool}

    Binance order book format (REST /api/v3/depth):
        {"lastUpdateId": ..., "bids": [["price", "qty"], ...], "asks": [...]}
    """

    @property
    def exchange_name(self) -> str:
        return "binance"

    def normalize_ohlcv(self, raw: dict) -> OHLCV:
        # Binance kline can come as a list [timestamp, O, H, L, C, V, ...]
        # or as a dict with named fields.
        if isinstance(raw, (list, tuple)):
            return OHLCV(
                timestamp_ms=int(raw[0]),
                symbol=raw[-1] if isinstance(raw[-1], str) else "",
                exchange=self.exchange_name,
                open=float(raw[1]),
                high=float(raw[2]),
                low=float(raw[3]),
                close=float(raw[4]),
                volume=float(raw[5]),
            )
        return OHLCV(
            timestamp_ms=int(raw["timestamp"]),
            symbol=raw["symbol"],
            exchange=self.exchange_name,
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw["volume"]),
        )

    def normalize_trade(self, raw: dict) -> Trade:
        side = "sell" if raw.get("isBuyerMaker", False) else "buy"
        return Trade(
            timestamp_ms=int(raw["time"]),
            symbol=raw.get("symbol", ""),
            exchange=self.exchange_name,
            price=float(raw["price"]),
            volume=float(raw["qty"]),
            trade_id=str(raw["id"]),
            side=side,
        )

    def normalize_order_book(self, raw: dict) -> OrderBookSnapshot:
        bids = tuple(
            PriceLevel(price=float(b[0]), size=float(b[1])) for b in raw["bids"]
        )
        asks = tuple(
            PriceLevel(price=float(a[0]), size=float(a[1])) for a in raw["asks"]
        )
        return OrderBookSnapshot(
            timestamp_ms=int(raw.get("timestamp", 0)),
            symbol=raw.get("symbol", ""),
            exchange=self.exchange_name,
            bids=bids,
            asks=asks,
        )


class CoinbaseAdapter(ExchangeAdapter):
    """Adapter for Coinbase exchange data format.

    Coinbase OHLCV format (REST /products/{id}/candles):
        [timestamp_unix, low, high, open, close, volume]
        Note: timestamp is in seconds, not milliseconds.
        Note: field order differs from Binance (low before high, open before close).

    Coinbase trade format (REST /products/{id}/trades):
        {"trade_id": ..., "price": "...", "size": "...", "time": "ISO8601", "side": "buy"|"sell"}

    Coinbase order book format (REST /products/{id}/book?level=2):
        {"bids": [["price", "size", num_orders], ...], "asks": [...], "sequence": ...}
    """

    @property
    def exchange_name(self) -> str:
        return "coinbase"

    def normalize_ohlcv(self, raw: dict) -> OHLCV:
        # Coinbase candle array: [time_unix, low, high, open, close, volume]
        if isinstance(raw, (list, tuple)):
            timestamp_s = raw[0]
            # Coinbase uses seconds; convert to ms
            timestamp_ms = (
                int(timestamp_s) * 1000 if timestamp_s < 1e12 else int(timestamp_s)
            )
            return OHLCV(
                timestamp_ms=timestamp_ms,
                symbol=raw[-1] if isinstance(raw[-1], str) else "",
                exchange=self.exchange_name,
                open=float(raw[3]),
                high=float(raw[2]),
                low=float(raw[1]),
                close=float(raw[4]),
                volume=float(raw[5]),
            )
        # Dict format
        ts = raw["timestamp"]
        timestamp_ms = int(ts) * 1000 if ts < 1e12 else int(ts)
        return OHLCV(
            timestamp_ms=timestamp_ms,
            symbol=raw["symbol"],
            exchange=self.exchange_name,
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw["volume"]),
        )

    def normalize_trade(self, raw: dict) -> Trade:
        # Coinbase uses ISO8601 time strings or unix timestamps
        ts = raw["time"]
        if isinstance(ts, str):
            from datetime import datetime, timezone

            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            timestamp_ms = int(dt.timestamp() * 1000)
        else:
            timestamp_ms = int(ts) * 1000 if ts < 1e12 else int(ts)
        return Trade(
            timestamp_ms=timestamp_ms,
            symbol=raw.get("product_id", raw.get("symbol", "")),
            exchange=self.exchange_name,
            price=float(raw["price"]),
            volume=float(raw["size"]),
            trade_id=str(raw["trade_id"]),
            side=raw.get("side"),
        )

    def normalize_order_book(self, raw: dict) -> OrderBookSnapshot:
        bids = tuple(
            PriceLevel(price=float(b[0]), size=float(b[1])) for b in raw["bids"]
        )
        asks = tuple(
            PriceLevel(price=float(a[0]), size=float(a[1])) for a in raw["asks"]
        )
        return OrderBookSnapshot(
            timestamp_ms=int(raw.get("timestamp", 0)),
            symbol=raw.get("symbol", ""),
            exchange=self.exchange_name,
            bids=bids,
            asks=asks,
        )


# Registry of available adapters
ADAPTER_REGISTRY = {
    "binance": BinanceAdapter,
    "coinbase": CoinbaseAdapter,
}


def get_adapter(exchange: str) -> ExchangeAdapter:
    """Get an adapter for the given exchange name."""
    adapter_cls = ADAPTER_REGISTRY.get(exchange.lower())
    if adapter_cls is None:
        raise ValueError(
            f"No adapter for exchange '{exchange}'. "
            f"Available: {list(ADAPTER_REGISTRY.keys())}"
        )
    return adapter_cls()
