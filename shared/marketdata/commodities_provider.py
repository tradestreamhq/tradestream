"""
Commodities market data provider using Alpha Vantage API.

Provides normalized candle data for commodity futures (gold, silver, oil, etc.),
enabling strategy discovery across commodities markets.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from absl import logging
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from shared.marketdata.provider import (
    AssetClass,
    AssetMetadata,
    MarketDataProvider,
    NormalizedCandle,
)

# Common commodity symbols and their Alpha Vantage function mappings
_COMMODITY_FUNCTIONS = {
    "WTI": "WTI",  # West Texas Intermediate crude oil
    "BRENT": "BRENT",  # Brent crude oil
    "NATURAL_GAS": "NATURAL_GAS",
    "COPPER": "COPPER",
    "ALUMINUM": "ALUMINUM",
    "WHEAT": "WHEAT",
    "CORN": "CORN",
    "COTTON": "COTTON",
    "SUGAR": "SUGAR",
    "COFFEE": "COFFEE",
}

# Alpha Vantage interval mapping for commodity data
_INTERVAL_MAP = {
    "1d": "daily",
    "1w": "weekly",
    "1M": "monthly",
}

_av_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (requests.exceptions.RequestException, ConnectionError, TimeoutError)
    ),
    reraise=True,
)


class CommoditiesMarketDataProvider(MarketDataProvider):
    """MarketDataProvider for commodities via Alpha Vantage."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, symbols: Optional[List[str]] = None):
        self._api_key = api_key
        self._symbols = set(
            s.upper() for s in (symbols or list(_COMMODITY_FUNCTIONS.keys()))
        )

    def get_asset_class(self) -> AssetClass:
        return AssetClass.COMMODITIES

    def get_supported_symbols(self) -> List[str]:
        return sorted(self._symbols)

    def add_symbol(self, symbol: str) -> None:
        self._symbols.add(symbol.upper())

    def remove_symbol(self, symbol: str) -> None:
        self._symbols.discard(symbol.upper())

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        symbol = symbol.upper()
        av_function = _COMMODITY_FUNCTIONS.get(symbol)
        if av_function is None:
            logging.warning(f"Unsupported commodity symbol: {symbol}")
            return []

        av_interval = _INTERVAL_MAP.get(timeframe)
        if av_interval is None:
            logging.warning(
                f"Unsupported timeframe '{timeframe}' for commodities "
                f"(supported: {list(_INTERVAL_MAP.keys())})"
            )
            return []

        try:
            raw_data = self._fetch_commodity_data(av_function, av_interval)
        except Exception as e:
            logging.error(f"Failed to fetch commodity data for {symbol}: {e}")
            return []

        candles = []
        for entry in raw_data:
            try:
                date_str = entry.get("date", "")
                value_str = entry.get("value", "")
                if not date_str or value_str == ".":
                    continue

                ts_ms = self._parse_timestamp(date_str)
                if ts_ms < since:
                    continue

                price = float(value_str)
                if price <= 0:
                    continue

                nc = NormalizedCandle(
                    timestamp_ms=ts_ms,
                    symbol=symbol,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=0.0,
                    asset_class=AssetClass.COMMODITIES,
                    source="alpha_vantage",
                )
                candles.append(nc)
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(f"Skipping malformed commodity data point: {e}")

        candles.sort(key=lambda c: c.timestamp_ms)
        return candles[:limit]

    def get_asset_metadata(self, symbol: str) -> Optional[AssetMetadata]:
        symbol = symbol.upper()
        return AssetMetadata(
            symbol=symbol,
            asset_class=AssetClass.COMMODITIES,
            exchange="COMEX/NYMEX",
            description=f"{symbol} commodity futures",
            trading_hours_timezone="America/New_York",
            market_open="09:30",
            market_close="14:30",
            tick_size=0.01,
            lot_size=1.0,
            price_precision=2,
            quantity_precision=0,
            margin_requirement=0.1,
            maintenance_margin=0.05,
            base_currency=symbol,
            quote_currency="USD",
        )

    def is_symbol_supported(self, symbol: str) -> bool:
        return symbol.upper() in self._symbols

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()

    @retry(**_av_retry_params)
    def _fetch_commodity_data(self, function: str, interval: str) -> List[Dict]:
        """Fetch commodity price data from Alpha Vantage."""
        params = {
            "function": function,
            "interval": interval,
            "apikey": self._api_key,
        }

        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "Error Message" in data:
            logging.error(f"Alpha Vantage error: {data['Error Message']}")
            return []

        if "Note" in data:
            logging.warning(f"Alpha Vantage rate limit: {data['Note']}")
            return []

        return data.get("data", [])

    @staticmethod
    def _parse_timestamp(date_str: str) -> int:
        for fmt in ("%Y-%m-%d",):
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse timestamp: {date_str}")
