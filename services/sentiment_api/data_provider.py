"""
Data provider for the Sentiment API.

Wraps exchange connectivity (via ccxt) and internal storage to supply
order book, trade, and funding rate data to the SentimentAnalyzer.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExchangeDataProvider:
    """Provides market data from an exchange via ccxt."""

    def __init__(self, exchange_id: str = "coinbasepro"):
        import ccxt

        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown exchange: {exchange_id}")
        self.exchange = exchange_class()

    def health_check(self):
        """Verify exchange connectivity."""
        self.exchange.fetch_time()

    def get_order_book(
        self, pair: str, levels: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Fetch order book from exchange."""
        try:
            ob = self.exchange.fetch_order_book(pair, limit=levels)
            return {
                "bids": [
                    {"price": p, "size": s} for p, s in ob.get("bids", [])
                ],
                "asks": [
                    {"price": p, "size": s} for p, s in ob.get("asks", [])
                ],
            }
        except Exception:
            logger.exception("Failed to fetch order book for %s", pair)
            return None

    def get_recent_trades(
        self, pair: str, window_seconds: int = 300
    ) -> List[Dict[str, Any]]:
        """Fetch recent trades from exchange."""
        try:
            trades = self.exchange.fetch_trades(pair, limit=200)
            return [
                {
                    "side": t["side"],
                    "price": t["price"],
                    "size": t["amount"],
                    "timestamp": t["datetime"],
                }
                for t in trades
            ]
        except Exception:
            logger.exception("Failed to fetch trades for %s", pair)
            return []

    def get_funding_rate(self, pair: str) -> Optional[float]:
        """Fetch current funding rate for perpetual futures.

        Returns None if the exchange or pair does not support funding rates.
        """
        try:
            if not hasattr(self.exchange, "fetch_funding_rate"):
                return None
            result = self.exchange.fetch_funding_rate(pair)
            return result.get("fundingRate")
        except Exception:
            logger.debug("Funding rate not available for %s", pair)
            return None

    def get_sentiment_history(
        self,
        pair: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve historical sentiment snapshots.

        In production this would read from a database.
        Returns empty list as placeholder.
        """
        return []

    def get_whale_trades(
        self,
        pair: str,
        limit: int = 50,
        threshold: Optional[float] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve recent whale trades.

        In production this would read from a database of detected whale trades.
        Returns empty list as placeholder.
        """
        return []
