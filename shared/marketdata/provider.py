"""
Abstract market data provider interface for multi-asset support.

Defines a common interface that all asset-class-specific data providers must
implement, enabling strategy discovery and signal generation across crypto,
stocks, forex, and commodities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AssetClass(Enum):
    """Asset class classification matching the protobuf AssetClass enum."""

    CRYPTO = "crypto"
    STOCKS = "stocks"
    FOREX = "forex"
    COMMODITIES = "commodities"


@dataclass(frozen=True)
class NormalizedCandle:
    """Unified candle representation across all asset classes.

    All providers must normalize their data into this format so that
    strategies can operate on any asset class without modification.
    """

    timestamp_ms: int  # Opening time in epoch milliseconds (UTC)
    symbol: str  # Normalized symbol (e.g., "BTC/USD", "AAPL", "EUR/USD")
    open: float
    high: float
    low: float
    close: float
    volume: float
    asset_class: AssetClass
    source: str  # Data source identifier (e.g., "binance", "alpha_vantage")

    def to_dict(self) -> dict:
        """Convert to dictionary format compatible with existing candle pipeline."""
        return {
            "timestamp_ms": self.timestamp_ms,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "currency_pair": self.symbol,
            "asset_class": self.asset_class.value,
            "source": self.source,
        }

    def is_valid(self) -> bool:
        """Check if this candle has valid OHLCV data."""
        return (
            self.open > 0
            and self.high > 0
            and self.low > 0
            and self.close > 0
            and self.high >= self.low
            and self.high >= self.open
            and self.high >= self.close
            and self.low <= self.open
            and self.low <= self.close
            and self.volume >= 0
        )


@dataclass(frozen=True)
class AssetMetadata:
    """Trading characteristics for a specific instrument."""

    symbol: str
    asset_class: AssetClass
    exchange: str
    description: str = ""

    # Trading hours (empty strings for 24/7 markets)
    trading_hours_timezone: str = ""
    market_open: str = ""
    market_close: str = ""

    # Precision and sizing
    tick_size: float = 0.01
    lot_size: float = 1.0
    price_precision: int = 2
    quantity_precision: int = 2

    # Margin requirements
    margin_requirement: float = 1.0
    maintenance_margin: float = 1.0

    # Currency pair components
    base_currency: str = ""
    quote_currency: str = "USD"


class MarketDataProvider(ABC):
    """Abstract base class for all market data providers.

    Each asset class implements this interface to provide normalized candle data
    and asset metadata. Strategies operate on NormalizedCandle objects and
    are therefore asset-class agnostic.
    """

    @abstractmethod
    def get_asset_class(self) -> AssetClass:
        """Return the asset class this provider handles."""

    @abstractmethod
    def get_supported_symbols(self) -> List[str]:
        """Return list of symbols this provider can serve data for."""

    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        """Fetch historical candle data for a symbol.

        Args:
            symbol: Instrument symbol (provider-specific format accepted,
                     will be normalized internally).
            timeframe: Candle interval (e.g., "1m", "5m", "1h", "1d").
            since: Start time in epoch milliseconds.
            limit: Maximum number of candles to return.

        Returns:
            List of NormalizedCandle objects sorted by timestamp ascending.
        """

    @abstractmethod
    def get_asset_metadata(self, symbol: str) -> Optional[AssetMetadata]:
        """Return trading metadata for a symbol, or None if unknown."""

    @abstractmethod
    def is_symbol_supported(self, symbol: str) -> bool:
        """Check whether a symbol is available from this provider."""

    def normalize_symbol(self, symbol: str) -> str:
        """Convert a raw symbol to normalized form. Override in subclasses."""
        return symbol.upper()
