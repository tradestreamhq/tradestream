"""
SentimentAnalyzer — computes market sentiment from order book, trade flow,
whale activity, and funding rate data.
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from services.sentiment_api.models import (
    OrderBookImbalance,
    SentimentSnapshot,
    TradeFlowMetrics,
    WhaleTrade,
)

# Default weights for composite score
DEFAULT_WEIGHTS = {
    "order_book": 0.30,
    "trade_flow": 0.30,
    "whale": 0.20,
    "funding": 0.20,
}

# Default whale trade threshold in notional (price * size)
DEFAULT_WHALE_THRESHOLD = 100_000.0

# Default funding rate normalization factor
# Funding rates are typically small (e.g., 0.01% = 0.0001), so we scale them
FUNDING_RATE_SCALE = 10_000.0


class SentimentAnalyzer:
    """Computes market sentiment from multiple data sources."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        whale_threshold: float = DEFAULT_WHALE_THRESHOLD,
        funding_rate_scale: float = FUNDING_RATE_SCALE,
    ):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self.whale_threshold = whale_threshold
        self.funding_rate_scale = funding_rate_scale

    def compute_order_book_imbalance(
        self,
        pair: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        levels: int = 10,
        timestamp: Optional[str] = None,
    ) -> OrderBookImbalance:
        """Compute order book imbalance from bid/ask levels.

        Args:
            pair: Trading pair (e.g., "BTC/USD").
            bids: List of (price, size) tuples, best bid first.
            asks: List of (price, size) tuples, best ask first.
            levels: Number of levels to consider.
            timestamp: ISO timestamp, defaults to now.
        """
        bid_volume = sum(size for _, size in bids[:levels])
        ask_volume = sum(size for _, size in asks[:levels])
        total = bid_volume + ask_volume

        if total == 0:
            ratio = 0.0
        else:
            ratio = (bid_volume - ask_volume) / total

        return OrderBookImbalance(
            pair=pair,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            levels=min(levels, max(len(bids), len(asks))),
            imbalance_ratio=max(-1.0, min(1.0, ratio)),
            timestamp=timestamp or _now_iso(),
        )

    def compute_trade_flow(
        self,
        pair: str,
        trades: List[Dict],
        window_seconds: int = 300,
        timestamp: Optional[str] = None,
    ) -> TradeFlowMetrics:
        """Compute trade flow sentiment from recent trades.

        Args:
            pair: Trading pair.
            trades: List of dicts with keys: side ("buy"/"sell"), price, size.
            window_seconds: Time window the trades cover.
            timestamp: ISO timestamp, defaults to now.
        """
        buy_volume = 0.0
        sell_volume = 0.0
        buy_count = 0
        sell_count = 0

        for t in trades:
            size = float(t.get("size", 0))
            if t.get("side") == "buy":
                buy_volume += size
                buy_count += 1
            elif t.get("side") == "sell":
                sell_volume += size
                sell_count += 1

        total = buy_volume + sell_volume
        net_flow = buy_volume - sell_volume
        flow_ratio = (buy_volume - sell_volume) / total if total > 0 else 0.0

        return TradeFlowMetrics(
            pair=pair,
            window_seconds=window_seconds,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            buy_count=buy_count,
            sell_count=sell_count,
            net_flow=net_flow,
            flow_ratio=max(-1.0, min(1.0, flow_ratio)),
            timestamp=timestamp or _now_iso(),
        )

    def detect_whale_trades(
        self,
        pair: str,
        trades: List[Dict],
        threshold: Optional[float] = None,
    ) -> List[WhaleTrade]:
        """Detect large trades above the notional threshold.

        Args:
            pair: Trading pair.
            trades: List of dicts with keys: side, price, size, timestamp.
            threshold: Minimum notional value. Defaults to self.whale_threshold.
        """
        threshold = threshold if threshold is not None else self.whale_threshold
        whales = []

        for t in trades:
            price = float(t.get("price", 0))
            size = float(t.get("size", 0))
            notional = price * size
            if notional >= threshold:
                whales.append(
                    WhaleTrade(
                        pair=pair,
                        side=t.get("side", "unknown"),
                        price=price,
                        size=size,
                        notional=notional,
                        timestamp=t.get("timestamp", _now_iso()),
                    )
                )

        return whales

    def compute_funding_sentiment(self, funding_rate: Optional[float]) -> float:
        """Convert funding rate to sentiment score [-1, +1].

        Positive funding rate = longs pay shorts = bearish pressure.
        Negative funding rate = shorts pay longs = bullish pressure.
        We invert the sign: negative funding → positive sentiment.
        """
        if funding_rate is None:
            return 0.0

        # Scale and clamp using tanh for smooth bounds
        scaled = funding_rate * self.funding_rate_scale
        return max(-1.0, min(1.0, -math.tanh(scaled)))

    def compute_whale_sentiment(self, whale_trades: List[WhaleTrade]) -> float:
        """Compute sentiment from whale trades based on net buy/sell notional.

        Returns a value in [-1, +1].
        """
        if not whale_trades:
            return 0.0

        buy_notional = sum(w.notional for w in whale_trades if w.side == "buy")
        sell_notional = sum(w.notional for w in whale_trades if w.side == "sell")
        total = buy_notional + sell_notional

        if total == 0:
            return 0.0

        return max(-1.0, min(1.0, (buy_notional - sell_notional) / total))

    def compute_snapshot(
        self,
        pair: str,
        bids: Optional[List[Tuple[float, float]]] = None,
        asks: Optional[List[Tuple[float, float]]] = None,
        trades: Optional[List[Dict]] = None,
        funding_rate: Optional[float] = None,
        levels: int = 10,
        window_seconds: int = 300,
        timestamp: Optional[str] = None,
    ) -> SentimentSnapshot:
        """Compute a full sentiment snapshot for a pair.

        All data sources are optional; missing sources contribute 0 and their
        weight is redistributed to available sources.
        """
        ts = timestamp or _now_iso()

        # Order book imbalance
        ob_imbalance = None
        if bids is not None and asks is not None:
            ob_imbalance = self.compute_order_book_imbalance(
                pair, bids, asks, levels, ts
            )

        # Trade flow
        trade_flow = None
        if trades is not None:
            trade_flow = self.compute_trade_flow(pair, trades, window_seconds, ts)

        # Whale trades
        whale_trades = []
        if trades is not None:
            whale_trades = self.detect_whale_trades(pair, trades)

        # Funding sentiment
        funding_sentiment = self.compute_funding_sentiment(funding_rate)

        # Composite score with dynamic weight redistribution
        components = {}
        if ob_imbalance is not None:
            components["order_book"] = ob_imbalance.imbalance_ratio
        if trade_flow is not None:
            components["trade_flow"] = trade_flow.flow_ratio
        if whale_trades:
            components["whale"] = self.compute_whale_sentiment(whale_trades)
        if funding_rate is not None:
            components["funding"] = funding_sentiment

        composite = self._weighted_score(components)

        return SentimentSnapshot(
            pair=pair,
            order_book_imbalance=ob_imbalance,
            trade_flow=trade_flow,
            whale_trades=whale_trades,
            funding_rate=funding_rate,
            funding_sentiment=funding_sentiment,
            composite_score=composite,
            timestamp=ts,
        )

    def _weighted_score(self, components: Dict[str, float]) -> float:
        """Compute weighted average, redistributing weight from missing components."""
        if not components:
            return 0.0

        total_weight = sum(self.weights.get(k, 0) for k in components)
        if total_weight == 0:
            return 0.0

        score = sum(
            (self.weights.get(k, 0) / total_weight) * v for k, v in components.items()
        )
        return max(-1.0, min(1.0, score))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
