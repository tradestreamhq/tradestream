"""Unified market data schema for cross-exchange normalization."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DataType(Enum):
    OHLCV = "ohlcv"
    TRADE = "trade"
    ORDER_BOOK = "order_book"


@dataclass(frozen=True)
class OHLCV:
    """Unified OHLCV (candlestick) record."""

    timestamp_ms: int
    symbol: str
    exchange: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: str = "1m"

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "interval": self.interval,
        }


@dataclass(frozen=True)
class Trade:
    """Unified trade record."""

    timestamp_ms: int
    symbol: str
    exchange: str
    price: float
    volume: float
    trade_id: str
    side: Optional[str] = None  # "buy" or "sell"

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "price": self.price,
            "volume": self.volume,
            "trade_id": self.trade_id,
            "side": self.side,
        }


@dataclass(frozen=True)
class PriceLevel:
    """Single price level in an order book."""

    price: float
    size: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Unified order book snapshot."""

    timestamp_ms: int
    symbol: str
    exchange: str
    bids: tuple  # tuple of PriceLevel
    asks: tuple  # tuple of PriceLevel

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "bids": [{"price": b.price, "size": b.size} for b in self.bids],
            "asks": [{"price": a.price, "size": a.size} for a in self.asks],
        }
