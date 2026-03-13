"""Data models for the Market Sentiment Analysis module."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OrderBookImbalance:
    """Order book imbalance at N levels of depth."""

    pair: str
    bid_volume: float
    ask_volume: float
    levels: int
    imbalance_ratio: float  # (bid - ask) / (bid + ask), range [-1, +1]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "levels": self.levels,
            "imbalance_ratio": round(self.imbalance_ratio, 6),
            "timestamp": self.timestamp,
        }


@dataclass
class TradeFlowMetrics:
    """Buy vs sell volume aggregated over a time window."""

    pair: str
    window_seconds: int
    buy_volume: float
    sell_volume: float
    buy_count: int
    sell_count: int
    net_flow: float  # buy_volume - sell_volume
    flow_ratio: float  # (buy - sell) / (buy + sell), range [-1, +1]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "window_seconds": self.window_seconds,
            "buy_volume": round(self.buy_volume, 8),
            "sell_volume": round(self.sell_volume, 8),
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "net_flow": round(self.net_flow, 8),
            "flow_ratio": round(self.flow_ratio, 6),
            "timestamp": self.timestamp,
        }


@dataclass
class WhaleTrade:
    """A large trade above a configurable threshold."""

    pair: str
    side: str  # "buy" or "sell"
    price: float
    size: float
    notional: float  # price * size
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "notional": round(self.notional, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class SentimentSnapshot:
    """Composite sentiment snapshot for a trading pair."""

    pair: str
    order_book_imbalance: Optional[OrderBookImbalance]
    trade_flow: Optional[TradeFlowMetrics]
    whale_trades: List[WhaleTrade]
    funding_rate: Optional[float]  # For perpetual futures
    funding_sentiment: float  # Derived from funding rate, range [-1, +1]
    composite_score: float  # Weighted combination, range [-1, +1]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "order_book_imbalance": (
                self.order_book_imbalance.to_dict()
                if self.order_book_imbalance
                else None
            ),
            "trade_flow": (self.trade_flow.to_dict() if self.trade_flow else None),
            "whale_trades": [w.to_dict() for w in self.whale_trades],
            "funding_rate": self.funding_rate,
            "funding_sentiment": round(self.funding_sentiment, 6),
            "composite_score": round(self.composite_score, 6),
            "timestamp": self.timestamp,
        }
