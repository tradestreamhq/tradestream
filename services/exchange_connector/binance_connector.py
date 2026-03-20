"""
Binance exchange connector using CCXT REST API.
"""

import ccxt
from absl import logging
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
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

_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeError)),
    reraise=True,
)


class BinanceConnector(ExchangeConnector):
    """Binance exchange connector via CCXT."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False,
    ):
        config = {
            "rateLimit": 1200,
            "enableRateLimit": True,
            "timeout": 30000,
        }
        if api_key:
            config["apiKey"] = api_key
        if api_secret:
            config["secret"] = api_secret

        self._exchange = ccxt.binance(config)
        if sandbox:
            self._exchange.set_sandbox_mode(True)
        self._markets_loaded = False

    @property
    def name(self) -> str:
        return "binance"

    def _ensure_markets(self) -> None:
        if not self._markets_loaded:
            self._exchange.load_markets()
            self._markets_loaded = True

    @retry(**_retry_params)
    def get_ticker(self, pair: str) -> Ticker:
        self._ensure_markets()
        data = self._exchange.fetch_ticker(pair)
        return Ticker(
            pair=pair,
            last=float(data["last"]),
            bid=float(data["bid"]) if data.get("bid") else None,
            ask=float(data["ask"]) if data.get("ask") else None,
            volume_24h=float(data["baseVolume"]) if data.get("baseVolume") else None,
            timestamp_ms=data.get("timestamp"),
        )

    @retry(**_retry_params)
    def get_orderbook(self, pair: str, depth: int = 10) -> OrderBook:
        self._ensure_markets()
        data = self._exchange.fetch_order_book(pair, limit=depth)
        return OrderBook(
            pair=pair,
            bids=[OrderBookEntry(price=b[0], quantity=b[1]) for b in data["bids"]],
            asks=[OrderBookEntry(price=a[0], quantity=a[1]) for a in data["asks"]],
            timestamp_ms=data.get("timestamp"),
        )

    @retry(**_retry_params)
    def get_candles(
        self, pair: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Candle]:
        self._ensure_markets()
        ohlcv = self._exchange.fetch_ohlcv(pair, timeframe, limit=limit)
        return [
            Candle(
                timestamp_ms=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5] or 0),
            )
            for row in ohlcv
            if row[1] and row[2] and row[3] and row[4]
        ]

    @retry(**_retry_params)
    def place_order(
        self,
        pair: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
    ) -> Order:
        self._ensure_markets()
        result = self._exchange.create_order(
            symbol=pair,
            type=order_type.value,
            side=side.value,
            amount=quantity,
            price=price,
        )
        return _ccxt_order_to_order(result)

    @retry(**_retry_params)
    def cancel_order(self, order_id: str) -> Order:
        self._ensure_markets()
        result = self._exchange.cancel_order(order_id)
        return _ccxt_order_to_order(result)

    @retry(**_retry_params)
    def get_balances(self) -> List[Balance]:
        balance_data = self._exchange.fetch_balance()
        balances = []
        for currency, info in balance_data.get("total", {}).items():
            if info and float(info) > 0:
                free = float(balance_data.get("free", {}).get(currency, 0) or 0)
                used = float(balance_data.get("used", {}).get(currency, 0) or 0)
                balances.append(Balance(currency=currency, available=free, locked=used))
        return balances

    @retry(**_retry_params)
    def get_pairs(self) -> List[str]:
        self._ensure_markets()
        return list(self._exchange.symbols)


_STATUS_MAP = {
    "open": OrderStatus.OPEN,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.CANCELLED,
    "rejected": OrderStatus.REJECTED,
}


def _ccxt_order_to_order(data: dict) -> Order:
    return Order(
        id=str(data["id"]),
        pair=data["symbol"],
        side=OrderSide(data["side"]),
        type=OrderType(data["type"]),
        quantity=float(data["amount"]),
        price=float(data["price"]) if data.get("price") else None,
        status=_STATUS_MAP.get(data.get("status", ""), OrderStatus.PENDING),
        filled_quantity=float(data.get("filled", 0) or 0),
        timestamp_ms=data.get("timestamp"),
    )
