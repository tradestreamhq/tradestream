"""
Stock market data provider using Alpha Vantage API.

Provides normalized candle data for equities, enabling strategy discovery
across stocks in addition to crypto.
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

# Common US stock trading hours
_US_MARKET_OPEN = "09:30"
_US_MARKET_CLOSE = "16:00"
_US_TIMEZONE = "America/New_York"

# Retry parameters for Alpha Vantage HTTP calls
_av_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (requests.exceptions.RequestException, ConnectionError, TimeoutError)
    ),
    reraise=True,
)

# Alpha Vantage interval mapping
_TIMEFRAME_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
    "1d": "daily",
}


class StockMarketDataProvider(MarketDataProvider):
    """MarketDataProvider for US equities via Alpha Vantage.

    Requires an Alpha Vantage API key (free tier: 25 requests/day).
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, symbols: Optional[List[str]] = None):
        self._api_key = api_key
        self._symbols = set(s.upper() for s in (symbols or []))

    def get_asset_class(self) -> AssetClass:
        return AssetClass.STOCKS

    def get_supported_symbols(self) -> List[str]:
        return sorted(self._symbols)

    def add_symbol(self, symbol: str) -> None:
        """Register a stock symbol for this provider."""
        self._symbols.add(symbol.upper())

    def remove_symbol(self, symbol: str) -> None:
        """Unregister a stock symbol."""
        self._symbols.discard(symbol.upper())

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        symbol = symbol.upper()
        av_interval = _TIMEFRAME_MAP.get(timeframe)
        if av_interval is None:
            logging.warning(f"Unsupported timeframe '{timeframe}' for stocks")
            return []

        try:
            raw_data = self._fetch_candles(symbol, av_interval)
        except Exception as e:
            logging.error(f"Failed to fetch stock candles for {symbol}: {e}")
            return []

        candles = []
        for ts_str, values in raw_data.items():
            try:
                ts_ms = self._parse_timestamp(ts_str)
                if ts_ms < since:
                    continue

                nc = NormalizedCandle(
                    timestamp_ms=ts_ms,
                    symbol=symbol,
                    open=float(values["1. open"]),
                    high=float(values["2. high"]),
                    low=float(values["3. low"]),
                    close=float(values["4. close"]),
                    volume=float(values["5. volume"]),
                    asset_class=AssetClass.STOCKS,
                    source="alpha_vantage",
                )
                if nc.is_valid():
                    candles.append(nc)
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(f"Skipping malformed stock candle: {e}")

        candles.sort(key=lambda c: c.timestamp_ms)
        return candles[:limit]

    def get_asset_metadata(self, symbol: str) -> Optional[AssetMetadata]:
        symbol = symbol.upper()
        return AssetMetadata(
            symbol=symbol,
            asset_class=AssetClass.STOCKS,
            exchange="NYSE/NASDAQ",
            description=f"{symbol} equity",
            trading_hours_timezone=_US_TIMEZONE,
            market_open=_US_MARKET_OPEN,
            market_close=_US_MARKET_CLOSE,
            tick_size=0.01,
            lot_size=1.0,
            price_precision=2,
            quantity_precision=0,
            margin_requirement=0.5,
            maintenance_margin=0.25,
            base_currency=symbol,
            quote_currency="USD",
        )

    def is_symbol_supported(self, symbol: str) -> bool:
        return symbol.upper() in self._symbols

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()

    @retry(**_av_retry_params)
    def _fetch_candles(self, symbol: str, interval: str) -> Dict:
        """Fetch candle data from Alpha Vantage API."""
        if interval == "daily":
            function = "TIME_SERIES_DAILY"
            ts_key = "Time Series (Daily)"
        else:
            function = "TIME_SERIES_INTRADAY"
            ts_key = f"Time Series ({interval})"

        params = {
            "function": function,
            "symbol": symbol,
            "apikey": self._api_key,
            "outputsize": "compact",
        }
        if interval != "daily":
            params["interval"] = interval

        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "Error Message" in data:
            logging.error(f"Alpha Vantage error for {symbol}: {data['Error Message']}")
            return {}

        if "Note" in data:
            logging.warning(f"Alpha Vantage rate limit: {data['Note']}")
            return {}

        return data.get(ts_key, {})

    @staticmethod
    def _parse_timestamp(date_str: str) -> int:
        """Parse Alpha Vantage timestamp to epoch milliseconds."""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse timestamp: {date_str}")
