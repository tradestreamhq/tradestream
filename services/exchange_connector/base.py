"""
Abstract base class for exchange connectors.

Provides a unified interface for interacting with cryptocurrency exchanges,
covering market data retrieval and order management.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Ticker:
    pair: str
    last: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    timestamp_ms: Optional[int] = None


@dataclass
class OrderBookEntry:
    price: float
    quantity: float


@dataclass
class OrderBook:
    pair: str
    bids: List[OrderBookEntry] = field(default_factory=list)
    asks: List[OrderBookEntry] = field(default_factory=list)
    timestamp_ms: Optional[int] = None


@dataclass
class Candle:
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Order:
    id: str
    pair: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    timestamp_ms: Optional[int] = None


@dataclass
class Balance:
    currency: str
    available: float
    locked: float = 0.0

    @property
    def total(self) -> float:
        return self.available + self.locked


class ExchangeConnector(ABC):
    """Abstract base class for exchange connectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Exchange identifier (e.g., 'binance', 'coinbase')."""

    @abstractmethod
    def get_ticker(self, pair: str) -> Ticker:
        """Get current ticker for a trading pair."""

    @abstractmethod
    def get_orderbook(self, pair: str, depth: int = 10) -> OrderBook:
        """Get order book snapshot."""

    @abstractmethod
    def get_candles(
        self, pair: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Candle]:
        """Get historical OHLCV candles."""

    @abstractmethod
    def place_order(
        self,
        pair: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
    ) -> Order:
        """Place an order on the exchange."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order:
        """Cancel an existing order."""

    @abstractmethod
    def get_balances(self) -> List[Balance]:
        """Get account balances."""

    @abstractmethod
    def get_pairs(self) -> List[str]:
        """Get available trading pairs."""
