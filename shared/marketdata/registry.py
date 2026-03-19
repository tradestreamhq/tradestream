"""
Market data provider registry for multi-asset support.

Manages provider instances across asset classes, routing symbol lookups
to the correct provider automatically.
"""

from typing import Dict, List, Optional

from absl import logging

from shared.marketdata.provider import (
    AssetClass,
    AssetMetadata,
    MarketDataProvider,
    NormalizedCandle,
)


class MarketDataProviderRegistry:
    """Registry that routes data requests to the appropriate provider by asset class."""

    def __init__(self):
        self._providers: Dict[AssetClass, MarketDataProvider] = {}

    def register(self, provider: MarketDataProvider) -> None:
        """Register a provider for its asset class."""
        ac = provider.get_asset_class()
        if ac in self._providers:
            logging.warning(f"Replacing existing provider for {ac.value}")
        self._providers[ac] = provider
        logging.info(f"Registered {ac.value} market data provider")

    def get_provider(self, asset_class: AssetClass) -> Optional[MarketDataProvider]:
        """Get the provider for a specific asset class."""
        return self._providers.get(asset_class)

    def get_registered_asset_classes(self) -> List[AssetClass]:
        """Return list of asset classes that have a registered provider."""
        return list(self._providers.keys())

    def find_provider_for_symbol(self, symbol: str) -> Optional[MarketDataProvider]:
        """Find which provider supports a given symbol.

        Checks all registered providers and returns the first match.
        """
        for provider in self._providers.values():
            if provider.is_symbol_supported(symbol):
                return provider
        return None

    def get_candles(
        self,
        asset_class: AssetClass,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        """Fetch candles from the provider for the given asset class."""
        provider = self._providers.get(asset_class)
        if provider is None:
            logging.error(f"No provider registered for {asset_class.value}")
            return []
        return provider.get_historical_candles(symbol, timeframe, since, limit)

    def get_metadata(
        self, asset_class: AssetClass, symbol: str
    ) -> Optional[AssetMetadata]:
        """Get asset metadata from the appropriate provider."""
        provider = self._providers.get(asset_class)
        if provider is None:
            return None
        return provider.get_asset_metadata(symbol)

    def get_all_symbols(self) -> Dict[AssetClass, List[str]]:
        """Return all supported symbols grouped by asset class."""
        return {
            ac: provider.get_supported_symbols()
            for ac, provider in self._providers.items()
        }
