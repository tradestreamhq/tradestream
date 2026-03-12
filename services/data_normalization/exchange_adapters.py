"""Exchange-specific adapters that convert raw candle data to NormalizedCandle."""

import abc
from datetime import datetime, timezone
from typing import Any, Dict, List

from absl import logging

from services.data_normalization.models import NormalizedCandle


class ExchangeAdapter(abc.ABC):
    """Base class for exchange-specific candle adapters."""

    @property
    @abc.abstractmethod
    def exchange_name(self) -> str:
        """Return the canonical exchange name."""

    @abc.abstractmethod
    def normalize(self, raw: Dict[str, Any]) -> NormalizedCandle:
        """Convert a single raw candle dict into a NormalizedCandle."""

    def normalize_batch(self, raws: List[Dict[str, Any]]) -> List[NormalizedCandle]:
        """Convert a list of raw candles, skipping invalid ones."""
        results = []
        for raw in raws:
            try:
                results.append(self.normalize(raw))
            except (ValueError, KeyError, TypeError) as e:
                logging.warning(
                    f"{self.exchange_name}: skipping invalid candle: {e}"
                )
        return results


class BinanceAdapter(ExchangeAdapter):
    """Adapter for Binance kline/candle data.

    Expected raw format (REST API response element):
    {
        "t": 1672531200000,   # open time (ms)
        "o": "16500.00",      # open
        "h": "16600.00",      # high
        "l": "16400.00",      # low
        "c": "16550.00",      # close
        "v": "1234.56",       # volume
        "s": "BTCUSDT",       # symbol
    }

    Also supports the list format from fetch_ohlcv:
    [timestamp_ms, open, high, low, close, volume]
    """

    @property
    def exchange_name(self) -> str:
        return "binance"

    def normalize(self, raw: Dict[str, Any]) -> NormalizedCandle:
        if isinstance(raw, list):
            return self._from_ohlcv_list(raw)
        return self._from_dict(raw)

    def _from_dict(self, raw: Dict[str, Any]) -> NormalizedCandle:
        ts_ms = int(raw["t"])
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        symbol = raw.get("s", "UNKNOWN")
        o, h, l, c = float(raw["o"]), float(raw["h"]), float(raw["l"]), float(raw["c"])
        vol = float(raw.get("v", 0))
        vwap = None
        if vol > 0 and "q" in raw:
            vwap = float(raw["q"]) / vol
        return NormalizedCandle(
            symbol=symbol, exchange=self.exchange_name, timestamp=ts,
            open=o, high=h, low=l, close=c, volume=vol, vwap=vwap,
        )

    def _from_ohlcv_list(self, raw: list) -> NormalizedCandle:
        ts_ms, o, h, l, c, vol = raw[:6]
        ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
        symbol = raw[6] if len(raw) > 6 else "UNKNOWN"
        return NormalizedCandle(
            symbol=symbol, exchange=self.exchange_name, timestamp=ts,
            open=float(o), high=float(h), low=float(l), close=float(c),
            volume=float(vol or 0), vwap=None,
        )


class CoinbaseAdapter(ExchangeAdapter):
    """Adapter for Coinbase (Advanced Trade API) candle data.

    Expected raw format:
    {
        "start": "1672531200",   # unix timestamp (seconds, string)
        "low": "16400.00",
        "high": "16600.00",
        "open": "16500.00",
        "close": "16550.00",
        "volume": "1234.56",
        "product_id": "BTC-USD",
    }
    """

    @property
    def exchange_name(self) -> str:
        return "coinbase"

    def normalize(self, raw: Dict[str, Any]) -> NormalizedCandle:
        ts_sec = int(raw["start"])
        ts = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        symbol = raw.get("product_id", "UNKNOWN")
        return NormalizedCandle(
            symbol=symbol, exchange=self.exchange_name, timestamp=ts,
            open=float(raw["open"]), high=float(raw["high"]),
            low=float(raw["low"]), close=float(raw["close"]),
            volume=float(raw.get("volume", 0)), vwap=None,
        )


class KrakenAdapter(ExchangeAdapter):
    """Adapter for Kraken OHLC data.

    Expected raw format (REST API array element):
    [
        1672531200,       # time (unix seconds)
        "16500.00",       # open
        "16600.00",       # high
        "16400.00",       # low
        "16550.00",       # close
        "16525.00",       # vwap
        "1234.56",        # volume
        42                # count
    ]

    Also supports dict format:
    {
        "time": 1672531200,
        "open": "16500.00",
        "high": "16600.00",
        "low": "16400.00",
        "close": "16550.00",
        "vwap": "16525.00",
        "volume": "1234.56",
        "pair": "XXBTZUSD",
    }
    """

    @property
    def exchange_name(self) -> str:
        return "kraken"

    def normalize(self, raw: Any) -> NormalizedCandle:
        if isinstance(raw, list):
            return self._from_list(raw)
        return self._from_dict(raw)

    def _from_list(self, raw: list) -> NormalizedCandle:
        ts = datetime.fromtimestamp(int(raw[0]), tz=timezone.utc)
        return NormalizedCandle(
            symbol="UNKNOWN", exchange=self.exchange_name, timestamp=ts,
            open=float(raw[1]), high=float(raw[2]),
            low=float(raw[3]), close=float(raw[4]),
            vwap=float(raw[5]) if raw[5] else None,
            volume=float(raw[6]),
        )

    def _from_dict(self, raw: Dict[str, Any]) -> NormalizedCandle:
        ts = datetime.fromtimestamp(int(raw["time"]), tz=timezone.utc)
        symbol = raw.get("pair", "UNKNOWN")
        vwap = float(raw["vwap"]) if raw.get("vwap") else None
        return NormalizedCandle(
            symbol=symbol, exchange=self.exchange_name, timestamp=ts,
            open=float(raw["open"]), high=float(raw["high"]),
            low=float(raw["low"]), close=float(raw["close"]),
            volume=float(raw.get("volume", 0)), vwap=vwap,
        )


ADAPTER_REGISTRY: Dict[str, type] = {
    "binance": BinanceAdapter,
    "coinbase": CoinbaseAdapter,
    "kraken": KrakenAdapter,
}


def get_adapter(exchange: str) -> ExchangeAdapter:
    """Look up and instantiate an adapter by exchange name."""
    adapter_cls = ADAPTER_REGISTRY.get(exchange.lower())
    if adapter_cls is None:
        raise ValueError(
            f"No adapter for exchange '{exchange}'. "
            f"Available: {list(ADAPTER_REGISTRY.keys())}"
        )
    return adapter_cls()
