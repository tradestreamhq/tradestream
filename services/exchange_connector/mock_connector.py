"""
Mock exchange connector for testing.

Simulates exchange behavior with configurable state and deterministic responses.
"""

import time
import uuid
from typing import Dict, List, Optional

from services.exchange_connector.base import (
    Balance,
    Candle,
    ExchangeConnector,
    Order,
    OrderBook,
    OrderBookEntry,
    OrderSide,
    OrderStatus,
    OrderType,
    Ticker,
)


class MockExchangeConnector(ExchangeConnector):
    """In-memory mock exchange for testing."""

    def __init__(
        self,
        exchange_name: str = "mock",
        pairs: Optional[List[str]] = None,
        balances: Optional[Dict[str, float]] = None,
    ):
        self._name = exchange_name
        self._pairs = pairs or ["BTC/USD", "ETH/USD", "SOL/USD"]
        self._balances = balances or {"USD": 10000.0, "BTC": 1.0, "ETH": 10.0}
        self._orders: Dict[str, Order] = {}
        self._prices: Dict[str, float] = {
            "BTC/USD": 60000.0,
            "ETH/USD": 3000.0,
            "SOL/USD": 150.0,
        }

    @property
    def name(self) -> str:
        return self._name

    def set_price(self, pair: str, price: float) -> None:
        """Set mock price for a pair."""
        self._prices[pair] = price

    def get_ticker(self, pair: str) -> Ticker:
        price = self._prices.get(pair)
        if price is None:
            raise ValueError(f"Unknown pair: {pair}")
        spread = price * 0.001
        return Ticker(
            pair=pair,
            last=price,
            bid=price - spread,
            ask=price + spread,
            volume_24h=1000.0,
            timestamp_ms=int(time.time() * 1000),
        )

    def get_orderbook(self, pair: str, depth: int = 10) -> OrderBook:
        price = self._prices.get(pair)
        if price is None:
            raise ValueError(f"Unknown pair: {pair}")
        bids = [
            OrderBookEntry(price=price - (i + 1) * 0.5, quantity=1.0 + i * 0.1)
            for i in range(depth)
        ]
        asks = [
            OrderBookEntry(price=price + (i + 1) * 0.5, quantity=1.0 + i * 0.1)
            for i in range(depth)
        ]
        return OrderBook(
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp_ms=int(time.time() * 1000),
        )

    def get_candles(
        self, pair: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Candle]:
        price = self._prices.get(pair)
        if price is None:
            raise ValueError(f"Unknown pair: {pair}")
        now_ms = int(time.time() * 1000)
        interval_ms = _timeframe_to_ms(timeframe)
        candles = []
        for i in range(limit):
            ts = now_ms - (limit - i) * interval_ms
            candles.append(
                Candle(
                    timestamp_ms=ts,
                    open=price * (1 - 0.01 * (limit - i) / limit),
                    high=price * 1.005,
                    low=price * 0.995,
                    close=price * (1 - 0.005 * (limit - i) / limit),
                    volume=100.0 + i,
                )
            )
        return candles

    def place_order(
        self,
        pair: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
    ) -> Order:
        if pair not in self._prices:
            raise ValueError(f"Unknown pair: {pair}")
        fill_price = price if price else self._prices[pair]
        order = Order(
            id=str(uuid.uuid4()),
            pair=pair,
            side=side,
            type=order_type,
            quantity=quantity,
            price=fill_price,
            status=(
                OrderStatus.FILLED
                if order_type == OrderType.MARKET
                else OrderStatus.OPEN
            ),
            filled_quantity=quantity if order_type == OrderType.MARKET else 0.0,
            timestamp_ms=int(time.time() * 1000),
        )
        self._orders[order.id] = order
        return order

    def cancel_order(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            raise ValueError(f"Cannot cancel order in status: {order.status}")
        order.status = OrderStatus.CANCELLED
        return order

    def get_balances(self) -> List[Balance]:
        return [
            Balance(currency=currency, available=amount)
            for currency, amount in self._balances.items()
        ]

    def get_pairs(self) -> List[str]:
        return list(self._pairs)


def _timeframe_to_ms(timeframe: str) -> int:
    """Convert timeframe string to milliseconds."""
    multipliers = {
        "m": 60 * 1000,
        "h": 60 * 60 * 1000,
        "d": 24 * 60 * 60 * 1000,
    }
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    return value * multipliers.get(unit, 60 * 60 * 1000)
