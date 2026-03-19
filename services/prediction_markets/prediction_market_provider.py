"""Prediction market data provider implementing MarketDataProvider.

Exposes prediction market probability data as normalized candles,
enabling prediction market time-series to be consumed by the same
pipeline as traditional market data.
"""

import time
from typing import List, Optional

from absl import logging

from services.prediction_markets.kalshi_client import KalshiClient
from services.prediction_markets.polymarket_client import PolymarketInsiderClient
from shared.marketdata.provider import (
    AssetClass,
    AssetMetadata,
    MarketDataProvider,
    NormalizedCandle,
)


# Prediction markets use a virtual asset class
PREDICTION_MARKET_ASSET_CLASS = AssetClass.CRYPTO


class PredictionMarketProvider(MarketDataProvider):
    """MarketDataProvider that normalizes prediction market probabilities.

    Converts prediction market probability data into NormalizedCandle format
    where:
    - open/high/low/close represent probability values (0.0-1.0)
    - volume represents trading volume in the prediction market
    - symbol is the prediction market event identifier

    This allows prediction market data to flow through the same data pipeline
    and be analyzed alongside traditional price data.
    """

    def __init__(
        self,
        kalshi_client: KalshiClient = None,
        polymarket_client: PolymarketInsiderClient = None,
    ):
        self._kalshi = kalshi_client
        self._polymarket = polymarket_client
        self._known_symbols = set()

    def get_asset_class(self) -> AssetClass:
        return PREDICTION_MARKET_ASSET_CLASS

    def get_supported_symbols(self) -> List[str]:
        """Return prediction market event tickers as symbols."""
        symbols = list(self._known_symbols)

        # Discover symbols from Kalshi if available
        if self._kalshi:
            try:
                result = self._kalshi.get_crypto_relevant_markets_safe()
                for market in result.get("markets", []):
                    ticker = market.get("ticker", "")
                    if ticker:
                        symbol = f"PM:{ticker}"
                        symbols.append(symbol)
                        self._known_symbols.add(symbol)
            except Exception as e:
                logging.warning(f"Failed to discover Kalshi symbols: {e}")

        return sorted(set(symbols))

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        """Fetch probability history as candles.

        For prediction markets, each candle represents a probability snapshot.
        Currently returns the latest snapshot only (real-time data).
        Historical time-series would require a database backing.
        """
        candles = []

        if symbol.startswith("PM:") and self._kalshi:
            ticker = symbol[3:]  # Remove "PM:" prefix
            try:
                orderbook = self._kalshi.get_market_orderbook(ticker)
                ob = orderbook.get("orderbook", orderbook)
                yes_price = self._extract_best_price(ob.get("yes", []))
                no_price = self._extract_best_price(ob.get("no", []))
                prob = (
                    yes_price
                    if yes_price > 0
                    else (1.0 - no_price if no_price > 0 else 0)
                )

                if prob > 0:
                    candles.append(
                        NormalizedCandle(
                            timestamp_ms=int(time.time() * 1000),
                            symbol=symbol,
                            open=prob,
                            high=prob,
                            low=prob,
                            close=prob,
                            volume=0,
                            asset_class=self.get_asset_class(),
                            source="kalshi",
                        )
                    )
            except Exception as e:
                logging.warning(f"Failed to fetch candle for {symbol}: {e}")

        return candles

    def get_asset_metadata(self, symbol: str) -> Optional[AssetMetadata]:
        """Return metadata for a prediction market symbol."""
        if not self.is_symbol_supported(symbol):
            return None

        return AssetMetadata(
            symbol=symbol,
            asset_class=self.get_asset_class(),
            exchange="prediction_market",
            description=f"Prediction market: {symbol}",
            tick_size=0.01,
            lot_size=1.0,
            price_precision=2,
            quantity_precision=0,
            base_currency="PROB",
            quote_currency="USD",
        )

    def is_symbol_supported(self, symbol: str) -> bool:
        """Check if symbol is a known prediction market event."""
        if symbol in self._known_symbols:
            return True
        if symbol.startswith("PM:"):
            return True
        return False

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize prediction market symbol."""
        if not symbol.startswith("PM:"):
            return f"PM:{symbol.upper()}"
        return symbol.upper()

    @staticmethod
    def _extract_best_price(price_levels: list) -> float:
        """Extract best price from an order book side."""
        if not price_levels:
            return 0.0
        # price_levels can be [[price, size], ...] or [{"price": ..., "quantity": ...}]
        if isinstance(price_levels[0], (list, tuple)):
            return float(price_levels[0][0])
        if isinstance(price_levels[0], dict):
            return float(price_levels[0].get("price", 0))
        return 0.0
