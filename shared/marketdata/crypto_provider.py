"""
Crypto market data provider wrapping existing CCXT integration.

Adapts CCXTCandleClient to the MarketDataProvider interface, enabling
crypto data to flow through the same pipeline as stocks, forex, etc.
"""

from typing import List, Optional

from absl import logging

from services.candle_ingestor.ccxt_client import CCXTCandleClient
from shared.marketdata.provider import (
    AssetClass,
    AssetMetadata,
    MarketDataProvider,
    NormalizedCandle,
)


class CryptoMarketDataProvider(MarketDataProvider):
    """MarketDataProvider backed by CCXT for cryptocurrency exchanges."""

    def __init__(self, exchange_name: str = "binance"):
        self._client = CCXTCandleClient(exchange_name)
        self._exchange_name = exchange_name

    def get_asset_class(self) -> AssetClass:
        return AssetClass.CRYPTO

    def get_supported_symbols(self) -> List[str]:
        return sorted(self._client.available_symbols)

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        raw_candles = self._client.get_historical_candles(
            symbol, timeframe, since, limit
        )
        candles = []
        for c in raw_candles:
            nc = NormalizedCandle(
                timestamp_ms=c["timestamp_ms"],
                symbol=c["currency_pair"],
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
                asset_class=AssetClass.CRYPTO,
                source=c.get("exchange", self._exchange_name),
            )
            if nc.is_valid():
                candles.append(nc)
            else:
                logging.warning(f"Skipping invalid crypto candle: {c}")
        return candles

    def get_asset_metadata(self, symbol: str) -> Optional[AssetMetadata]:
        normalized = self.normalize_symbol(symbol)
        if not self.is_symbol_supported(symbol):
            return None

        parts = normalized.split("/")
        base = parts[0] if len(parts) > 0 else symbol
        quote = parts[1] if len(parts) > 1 else "USD"

        return AssetMetadata(
            symbol=normalized,
            asset_class=AssetClass.CRYPTO,
            exchange=self._exchange_name,
            description=f"{base}/{quote} on {self._exchange_name}",
            # Crypto markets trade 24/7
            trading_hours_timezone="",
            market_open="",
            market_close="",
            tick_size=0.01,
            lot_size=0.001,
            price_precision=2,
            quantity_precision=8,
            margin_requirement=1.0,
            maintenance_margin=1.0,
            base_currency=base,
            quote_currency=quote,
        )

    def is_symbol_supported(self, symbol: str) -> bool:
        return self._client.is_symbol_supported(symbol)

    def normalize_symbol(self, symbol: str) -> str:
        return self._client._normalize_symbol(symbol)
