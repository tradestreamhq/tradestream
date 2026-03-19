"""
Forex market data provider using Alpha Vantage FX API.

Provides normalized candle data for foreign exchange pairs, enabling
strategy discovery across forex markets.
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

# Forex market hours (approximate – 24h Sun 5pm–Fri 5pm ET)
_FX_TIMEZONE = "America/New_York"
_FX_MARKET_OPEN = "17:00"   # Sunday
_FX_MARKET_CLOSE = "17:00"  # Friday

# Common major forex pairs
MAJOR_PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD",
]

_TIMEFRAME_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
    "1d": "daily",
}

_av_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (requests.exceptions.RequestException, ConnectionError, TimeoutError)
    ),
    reraise=True,
)

# Pip sizes by quote currency
_PIP_SIZES = {
    "JPY": 0.01,
}
_DEFAULT_PIP_SIZE = 0.0001


class ForexMarketDataProvider(MarketDataProvider):
    """MarketDataProvider for FX pairs via Alpha Vantage."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, pairs: Optional[List[str]] = None):
        self._api_key = api_key
        self._pairs = set(self._normalize_pair(p) for p in (pairs or MAJOR_PAIRS))

    def get_asset_class(self) -> AssetClass:
        return AssetClass.FOREX

    def get_supported_symbols(self) -> List[str]:
        return sorted(self._pairs)

    def add_pair(self, pair: str) -> None:
        """Register a forex pair (e.g., 'EUR/USD')."""
        self._pairs.add(self._normalize_pair(pair))

    def remove_pair(self, pair: str) -> None:
        self._pairs.discard(self._normalize_pair(pair))

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        since: int,
        limit: int = 500,
    ) -> List[NormalizedCandle]:
        pair = self._normalize_pair(symbol)
        parts = pair.split("/")
        if len(parts) != 2:
            logging.warning(f"Invalid forex pair format: {symbol}")
            return []

        from_currency, to_currency = parts
        av_interval = _TIMEFRAME_MAP.get(timeframe)
        if av_interval is None:
            logging.warning(f"Unsupported timeframe '{timeframe}' for forex")
            return []

        try:
            raw_data = self._fetch_candles(from_currency, to_currency, av_interval)
        except Exception as e:
            logging.error(f"Failed to fetch forex candles for {pair}: {e}")
            return []

        candles = []
        for ts_str, values in raw_data.items():
            try:
                ts_ms = self._parse_timestamp(ts_str)
                if ts_ms < since:
                    continue

                nc = NormalizedCandle(
                    timestamp_ms=ts_ms,
                    symbol=pair,
                    open=float(values["1. open"]),
                    high=float(values["2. high"]),
                    low=float(values["3. low"]),
                    close=float(values["4. close"]),
                    volume=0.0,  # FX volume not available from Alpha Vantage
                    asset_class=AssetClass.FOREX,
                    source="alpha_vantage",
                )
                if nc.is_valid():
                    candles.append(nc)
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(f"Skipping malformed forex candle: {e}")

        candles.sort(key=lambda c: c.timestamp_ms)
        return candles[:limit]

    def get_asset_metadata(self, symbol: str) -> Optional[AssetMetadata]:
        pair = self._normalize_pair(symbol)
        parts = pair.split("/")
        if len(parts) != 2:
            return None

        base, quote = parts
        pip_size = _PIP_SIZES.get(quote, _DEFAULT_PIP_SIZE)

        return AssetMetadata(
            symbol=pair,
            asset_class=AssetClass.FOREX,
            exchange="forex",
            description=f"{base}/{quote} foreign exchange",
            trading_hours_timezone=_FX_TIMEZONE,
            market_open=_FX_MARKET_OPEN,
            market_close=_FX_MARKET_CLOSE,
            tick_size=pip_size,
            lot_size=1000.0,     # Mini lot
            price_precision=5 if quote != "JPY" else 3,
            quantity_precision=0,
            margin_requirement=0.02,   # 50:1 leverage
            maintenance_margin=0.01,
            base_currency=base,
            quote_currency=quote,
        )

    def is_symbol_supported(self, symbol: str) -> bool:
        return self._normalize_pair(symbol) in self._pairs

    def normalize_symbol(self, symbol: str) -> str:
        return self._normalize_pair(symbol)

    @staticmethod
    def _normalize_pair(pair: str) -> str:
        """Normalize forex pair to 'XXX/YYY' format."""
        pair = pair.upper().strip()
        if "/" in pair:
            return pair
        if len(pair) == 6:
            return f"{pair[:3]}/{pair[3:]}"
        return pair

    @retry(**_av_retry_params)
    def _fetch_candles(
        self, from_currency: str, to_currency: str, interval: str
    ) -> Dict:
        """Fetch FX candle data from Alpha Vantage."""
        if interval == "daily":
            function = "FX_DAILY"
            ts_key = "Time Series FX (Daily)"
        else:
            function = "FX_INTRADAY"
            ts_key = f"Time Series FX (Intraday)"

        params = {
            "function": function,
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "apikey": self._api_key,
            "outputsize": "compact",
        }
        if interval != "daily":
            params["interval"] = interval

        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "Error Message" in data:
            logging.error(
                f"Alpha Vantage error for {from_currency}/{to_currency}: "
                f"{data['Error Message']}"
            )
            return {}

        if "Note" in data:
            logging.warning(f"Alpha Vantage rate limit: {data['Note']}")
            return {}

        return data.get(ts_key, {})

    @staticmethod
    def _parse_timestamp(date_str: str) -> int:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse timestamp: {date_str}")
