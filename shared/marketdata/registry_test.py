"""Tests for MarketDataProviderRegistry."""

import unittest
from typing import List, Optional

from shared.marketdata.provider import (
    AssetClass,
    AssetMetadata,
    MarketDataProvider,
    NormalizedCandle,
)
from shared.marketdata.registry import MarketDataProviderRegistry


class FakeProvider(MarketDataProvider):
    """Fake provider for testing the registry."""

    def __init__(self, asset_class: AssetClass, symbols: List[str]):
        self._asset_class = asset_class
        self._symbols = set(symbols)

    def get_asset_class(self) -> AssetClass:
        return self._asset_class

    def get_supported_symbols(self) -> List[str]:
        return sorted(self._symbols)

    def get_historical_candles(
        self, symbol, timeframe, since, limit=500
    ) -> List[NormalizedCandle]:
        return [
            NormalizedCandle(
                timestamp_ms=since,
                symbol=symbol,
                open=100.0,
                high=110.0,
                low=90.0,
                close=105.0,
                volume=1000.0,
                asset_class=self._asset_class,
                source="fake",
            )
        ]

    def get_asset_metadata(self, symbol) -> Optional[AssetMetadata]:
        if symbol in self._symbols:
            return AssetMetadata(
                symbol=symbol,
                asset_class=self._asset_class,
                exchange="fake",
            )
        return None

    def is_symbol_supported(self, symbol) -> bool:
        return symbol in self._symbols


class MarketDataProviderRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = MarketDataProviderRegistry()
        self.crypto = FakeProvider(AssetClass.CRYPTO, ["BTC/USD", "ETH/USD"])
        self.stocks = FakeProvider(AssetClass.STOCKS, ["AAPL", "MSFT"])
        self.registry.register(self.crypto)
        self.registry.register(self.stocks)

    def test_get_provider(self):
        self.assertIs(
            self.registry.get_provider(AssetClass.CRYPTO), self.crypto
        )
        self.assertIs(
            self.registry.get_provider(AssetClass.STOCKS), self.stocks
        )
        self.assertIsNone(self.registry.get_provider(AssetClass.FOREX))

    def test_registered_asset_classes(self):
        classes = self.registry.get_registered_asset_classes()
        self.assertIn(AssetClass.CRYPTO, classes)
        self.assertIn(AssetClass.STOCKS, classes)
        self.assertEqual(len(classes), 2)

    def test_find_provider_for_symbol(self):
        p = self.registry.find_provider_for_symbol("BTC/USD")
        self.assertIs(p, self.crypto)

        p = self.registry.find_provider_for_symbol("AAPL")
        self.assertIs(p, self.stocks)

        p = self.registry.find_provider_for_symbol("UNKNOWN")
        self.assertIsNone(p)

    def test_get_candles(self):
        candles = self.registry.get_candles(
            AssetClass.CRYPTO, "BTC/USD", "1h", 1700000000000
        )
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].asset_class, AssetClass.CRYPTO)

    def test_get_candles_no_provider(self):
        candles = self.registry.get_candles(
            AssetClass.FOREX, "EUR/USD", "1h", 1700000000000
        )
        self.assertEqual(len(candles), 0)

    def test_get_metadata(self):
        meta = self.registry.get_metadata(AssetClass.STOCKS, "AAPL")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.asset_class, AssetClass.STOCKS)

    def test_get_all_symbols(self):
        all_syms = self.registry.get_all_symbols()
        self.assertIn(AssetClass.CRYPTO, all_syms)
        self.assertIn(AssetClass.STOCKS, all_syms)
        self.assertIn("BTC/USD", all_syms[AssetClass.CRYPTO])
        self.assertIn("AAPL", all_syms[AssetClass.STOCKS])

    def test_replace_provider(self):
        new_crypto = FakeProvider(AssetClass.CRYPTO, ["SOL/USD"])
        self.registry.register(new_crypto)
        self.assertIs(self.registry.get_provider(AssetClass.CRYPTO), new_crypto)


if __name__ == "__main__":
    unittest.main()
