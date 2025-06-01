"""
Production-ready CCXT client for candle ingestion.
Simplified version focused on reliability and integration with existing infrastructure.
"""

import ccxt
from datetime import datetime, timezone
from typing import List, Dict, Optional
from absl import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Retry parameters for exchange operations
exchange_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeError)),
    reraise=True,
)


class CCXTCandleClient:
    """Single exchange candle client using CCXT"""

    def __init__(self, exchange_name: str = "binance"):
        self.exchange_name = exchange_name
        config = {
            "rateLimit": 1200,
            "enableRateLimit": True,
            "timeout": 30000,
        }

        try:
            self.exchange = getattr(ccxt, exchange_name)(config)
            logging.info(f"Initialized CCXT client for {exchange_name}")
        except AttributeError:
            raise ValueError(f"Exchange '{exchange_name}' not supported by CCXT")

    @retry(**exchange_retry_params)
    def get_historical_candles(
        self, symbol: str, timeframe: str, since: int, limit: int = 500
    ) -> List[Dict]:
        """Fetch historical candles from single exchange"""
        try:
            market_symbol = self._normalize_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(market_symbol, timeframe, since, limit)
            return self._format_candles(ohlcv, symbol)

        except ccxt.BaseError as e:
            logging.error(
                f"CCXT error fetching {symbol} from {self.exchange_name}: {e}"
            )
            raise

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol format (e.g., 'btcusd' -> 'BTC/USD')"""
        if "/" in symbol:
            return symbol.upper()

        if symbol.lower().endswith("usd"):
            base = symbol[:-3].upper()
            return f"{base}/USD"
        elif symbol.lower().endswith("btc"):
            base = symbol[:-3].upper()
            return f"{base}/BTC"

        return symbol.upper()

    def _format_candles(self, ohlcv_data: List, symbol: str) -> List[Dict]:
        """Format CCXT OHLCV data to internal candle format"""
        candles = []
        for ohlcv in ohlcv_data:
            timestamp_ms, open_price, high, low, close, volume = ohlcv

            # Skip invalid candles
            if not all([open_price, high, low, close]) or high < low:
                logging.warning(f"Skipping invalid candle for {symbol}: {ohlcv}")
                continue

            candles.append(
                {
                    "timestamp_ms": int(timestamp_ms),
                    "open": float(open_price),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0),
                    "currency_pair": symbol,
                    "exchange": self.exchange_name,
                }
            )
        return candles


class MultiExchangeCandleClient:
    """Multi-exchange aggregated candle client"""

    def __init__(self, exchanges: List[str] = None, min_exchanges_required: int = 2):
        if exchanges is None:
            exchanges = ["binance", "coinbasepro", "kraken"]

        self.exchanges = {}
        self.min_exchanges_required = min_exchanges_required

        for exchange_name in exchanges:
            try:
                self.exchanges[exchange_name] = CCXTCandleClient(exchange_name)
                logging.info(f"Added exchange: {exchange_name}")
            except Exception as e:
                logging.warning(f"Failed to initialize {exchange_name}: {e}")

    def get_aggregated_candles(
        self, symbol: str, timeframe: str, since: int, limit: int = 500
    ) -> List[Dict]:
        """Fetch candles from multiple exchanges and aggregate them"""
        exchange_candles = {}

        # Fetch from all exchanges
        for name, client in self.exchanges.items():
            try:
                candles = client.get_historical_candles(symbol, timeframe, since, limit)
                if candles:
                    exchange_candles[name] = candles
                logging.info(f"Fetched {len(candles)} candles from {name}")
            except Exception as e:
                logging.warning(f"Failed to fetch from {name}: {e}")
                continue

        if len(exchange_candles) < self.min_exchanges_required:
            logging.warning(
                f"Only {len(exchange_candles)} exchanges available, minimum is {self.min_exchanges_required}"
            )
            if exchange_candles:
                # Return candles from available exchanges (fallback to single exchange)
                return list(exchange_candles.values())[0]
            return []

        return self._aggregate_candles(exchange_candles, symbol)

    def _aggregate_candles(self, exchange_candles: Dict, symbol: str) -> List[Dict]:
        """Aggregate candles using volume-weighted average pricing"""
        # Group candles by timestamp
        timestamp_groups = {}

        for exchange, candles in exchange_candles.items():
            for candle in candles:
                ts = candle["timestamp_ms"]
                if ts not in timestamp_groups:
                    timestamp_groups[ts] = []
                timestamp_groups[ts].append(candle)

        aggregated = []
        for timestamp, candles in timestamp_groups.items():
            if len(candles) >= 2:  # Require multiple exchanges
                agg_candle = self._volume_weighted_average(candles, symbol)
                aggregated.append(agg_candle)

        return sorted(aggregated, key=lambda x: x["timestamp_ms"])

    def _volume_weighted_average(self, candles: List[Dict], symbol: str) -> Dict:
        """Calculate volume-weighted average candle"""
        total_volume = sum(c["volume"] for c in candles)

        if total_volume == 0:
            # Fall back to simple average if no volume data
            return self._simple_average(candles, symbol)

        # VWAP for open and close prices
        vwap_open = sum(c["open"] * c["volume"] for c in candles) / total_volume
        vwap_close = sum(c["close"] * c["volume"] for c in candles) / total_volume

        return {
            "timestamp_ms": candles[0]["timestamp_ms"],
            "open": vwap_open,
            "high": max(c["high"] for c in candles),
            "low": min(c["low"] for c in candles),
            "close": vwap_close,
            "volume": total_volume,
            "currency_pair": symbol,
            "exchange": "aggregated",
            "source_exchanges": [c["exchange"] for c in candles],
        }

    def _simple_average(self, candles: List[Dict], symbol: str) -> Dict:
        """Simple average when volume data is unavailable"""
        count = len(candles)

        return {
            "timestamp_ms": candles[0]["timestamp_ms"],
            "open": sum(c["open"] for c in candles) / count,
            "high": max(c["high"] for c in candles),
            "low": min(c["low"] for c in candles),
            "close": sum(c["close"] for c in candles) / count,
            "volume": sum(c["volume"] for c in candles),
            "currency_pair": symbol,
            "exchange": "averaged",
            "source_exchanges": [c["exchange"] for c in candles],
        }
        