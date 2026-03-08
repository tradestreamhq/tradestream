"""
InfluxDB client for the market MCP server.
Queries candle data from the InfluxDB candles bucket.
"""

import math
from typing import Any, Dict, List, Optional

from absl import logging
from influxdb_client import InfluxDBClient


class MarketInfluxDBClient:
    """Client for querying candle data from InfluxDB."""

    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None

    def connect(self) -> None:
        """Establish connection to InfluxDB."""
        logging.info(f"Connecting to InfluxDB at {self.url}")
        self.client = InfluxDBClient(
            url=self.url,
            token=self.token,
            org=self.org,
        )
        # Verify connection by checking health
        health = self.client.health()
        logging.info(f"InfluxDB health: {health.status}")

    def close(self) -> None:
        """Close the InfluxDB connection."""
        if self.client:
            self.client.close()
            logging.info("InfluxDB connection closed")

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query candle data from InfluxDB.

        Args:
            symbol: Trading symbol (e.g., BTC/USD).
            timeframe: Candle timeframe (e.g., 1m, 5m, 1h).
            start: Start time in RFC3339 format (optional).
            end: End time in RFC3339 format (optional).
            limit: Maximum number of candles to return.

        Returns:
            List of candle dicts with timestamp, open, high, low, close, volume.
        """
        if not self.client:
            raise RuntimeError("InfluxDB connection not established")

        query_api = self.client.query_api()

        # Build the Flux query
        range_clause = self._build_range_clause(start, end)
        query = f"""
from(bucket: "{self.bucket}")
  |> range({range_clause})
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
"""

        tables = query_api.query(query, org=self.org)

        candles = []
        for table in tables:
            for record in table.records:
                candles.append({
                    "timestamp": record.get_time().isoformat(),
                    "open": record.values.get("open"),
                    "high": record.values.get("high"),
                    "low": record.values.get("low"),
                    "close": record.values.get("close"),
                    "volume": record.values.get("volume"),
                })

        return candles

    def get_latest_price(self, symbol: str) -> Dict[str, Any]:
        """Get the most recent candle close price.

        Args:
            symbol: Trading symbol (e.g., BTC/USD).

        Returns:
            Dict with symbol, price, volume_24h, change_24h, timestamp.
        """
        if not self.client:
            raise RuntimeError("InfluxDB connection not established")

        query_api = self.client.query_api()

        # Get the latest candle
        latest_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
"""

        # Get 24h ago candle for change calculation
        change_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -25h, stop: -23h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "close")
  |> last()
"""

        # Get 24h volume
        volume_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "volume")
  |> sum()
"""

        latest_tables = query_api.query(latest_query, org=self.org)
        change_tables = query_api.query(change_query, org=self.org)
        volume_tables = query_api.query(volume_query, org=self.org)

        price = None
        timestamp = None
        for table in latest_tables:
            for record in table.records:
                price = record.values.get("close")
                timestamp = record.get_time().isoformat()

        price_24h_ago = None
        for table in change_tables:
            for record in table.records:
                price_24h_ago = record.values.get("_value")

        volume_24h = 0.0
        for table in volume_tables:
            for record in table.records:
                volume_24h = record.values.get("_value", 0.0)

        change_24h = None
        if price is not None and price_24h_ago is not None and price_24h_ago != 0:
            change_24h = ((price - price_24h_ago) / price_24h_ago) * 100

        return {
            "symbol": symbol,
            "price": price,
            "volume_24h": volume_24h,
            "change_24h": change_24h,
            "timestamp": timestamp,
        }

    def get_volatility(
        self, symbol: str, period_minutes: int = 60
    ) -> Dict[str, Any]:
        """Compute volatility metrics from recent candle data.

        Args:
            symbol: Trading symbol (e.g., BTC/USD).
            period_minutes: Lookback period in minutes.

        Returns:
            Dict with symbol, volatility (stddev of returns), atr, period.
        """
        if not self.client:
            raise RuntimeError("InfluxDB connection not established")

        query_api = self.client.query_api()

        # Get candles for the period
        query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -{period_minutes}m)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
"""

        tables = query_api.query(query, org=self.org)

        closes = []
        highs = []
        lows = []
        prev_closes = []
        for table in tables:
            for record in table.records:
                close = record.values.get("close")
                high = record.values.get("high")
                low = record.values.get("low")
                if close is not None:
                    closes.append(close)
                if high is not None and low is not None:
                    highs.append(high)
                    lows.append(low)

        # Calculate returns stddev
        volatility = None
        if len(closes) >= 2:
            returns = []
            for i in range(1, len(closes)):
                if closes[i - 1] != 0:
                    returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
            if returns:
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                volatility = math.sqrt(variance)

        # Calculate ATR (Average True Range)
        atr = None
        if len(highs) >= 2 and len(closes) >= 2:
            true_ranges = []
            for i in range(1, min(len(highs), len(closes))):
                prev_close = closes[i - 1]
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - prev_close),
                    abs(lows[i] - prev_close),
                )
                true_ranges.append(tr)
            if true_ranges:
                atr = sum(true_ranges) / len(true_ranges)

        return {
            "symbol": symbol,
            "volatility": volatility,
            "atr": atr,
            "period": period_minutes,
        }

    def get_market_summary(self, symbol: str) -> Dict[str, Any]:
        """Get aggregated market summary for a symbol.

        Args:
            symbol: Trading symbol (e.g., BTC/USD).

        Returns:
            Dict with price, change_1h, change_24h, volume_24h, volatility,
            high_24h, low_24h, vwap.
        """
        if not self.client:
            raise RuntimeError("InfluxDB connection not established")

        query_api = self.client.query_api()

        # Get 24h candles for aggregation
        candles_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
"""

        # Get 1h ago price for change_1h
        price_1h_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -65m, stop: -55m)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "close")
  |> last()
"""

        tables = query_api.query(candles_query, org=self.org)
        price_1h_tables = query_api.query(price_1h_query, org=self.org)

        closes = []
        highs = []
        lows = []
        volumes = []
        vwap_numerator = 0.0

        for table in tables:
            for record in table.records:
                close = record.values.get("close")
                high = record.values.get("high")
                low = record.values.get("low")
                volume = record.values.get("volume")
                if close is not None:
                    closes.append(close)
                if high is not None:
                    highs.append(high)
                if low is not None:
                    lows.append(low)
                if volume is not None:
                    volumes.append(volume)
                # Typical price * volume for VWAP
                if close is not None and high is not None and low is not None and volume is not None:
                    typical_price = (high + low + close) / 3
                    vwap_numerator += typical_price * volume

        price = closes[-1] if closes else None
        price_24h_ago = closes[0] if closes else None
        high_24h = max(highs) if highs else None
        low_24h = min(lows) if lows else None
        volume_24h = sum(volumes) if volumes else None
        vwap = vwap_numerator / volume_24h if volume_24h else None

        change_24h = None
        if price is not None and price_24h_ago is not None and price_24h_ago != 0:
            change_24h = ((price - price_24h_ago) / price_24h_ago) * 100

        price_1h_ago = None
        for table in price_1h_tables:
            for record in table.records:
                price_1h_ago = record.values.get("_value")

        change_1h = None
        if price is not None and price_1h_ago is not None and price_1h_ago != 0:
            change_1h = ((price - price_1h_ago) / price_1h_ago) * 100

        # Calculate volatility (stddev of returns)
        volatility = None
        if len(closes) >= 2:
            returns = []
            for i in range(1, len(closes)):
                if closes[i - 1] != 0:
                    returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
            if returns:
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                volatility = math.sqrt(variance)

        return {
            "symbol": symbol,
            "price": price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "vwap": vwap,
        }

    def _build_range_clause(
        self, start: Optional[str] = None, end: Optional[str] = None
    ) -> str:
        """Build a Flux range clause from start/end parameters."""
        if start and end:
            return f'start: {start}, stop: {end}'
        elif start:
            return f'start: {start}'
        elif end:
            return f'start: -30d, stop: {end}'
        else:
            return 'start: -30d'
