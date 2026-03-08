"""
InfluxDB client for the market MCP server.
Queries candle data from InfluxDB.
"""

from typing import Any, Dict, List, Optional

from absl import logging
from influxdb_client import InfluxDBClient


class InfluxDBMarketClient:
    """Client for querying market candle data from InfluxDB."""

    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None

    def connect(self) -> None:
        """Establish connection to InfluxDB."""
        logging.info(f"Connecting to InfluxDB at {self.url}")
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        if not self.client.ping():
            raise ConnectionError(f"Failed to ping InfluxDB at {self.url}")
        logging.info("Successfully connected to InfluxDB")

    def _query(self, flux_query: str) -> List[Dict[str, Any]]:
        """Execute a Flux query and return results as list of dicts."""
        if not self.client:
            raise RuntimeError("InfluxDB connection not established")
        query_api = self.client.query_api()
        tables = query_api.query(flux_query, org=self.org)
        results = []
        for table in tables:
            for record in table.records:
                results.append(record.values)
        return results

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query candle data from InfluxDB.

        Args:
            symbol: Currency pair (e.g., BTC/USD).
            timeframe: Candle timeframe (e.g., 1m, 5m, 1h).
            start: Start time in RFC3339 or relative (e.g., -1h). Defaults to -1h.
            end: End time in RFC3339 or relative. Defaults to now().
            limit: Maximum number of candles to return.

        Returns:
            List of candle dicts with timestamp, open, high, low, close, volume.
        """
        if start is None:
            start = "-1h"
        range_clause = f"|> range(start: {start})"
        if end is not None:
            range_clause = f"|> range(start: {start}, stop: {end})"

        query = f"""
from(bucket: "{self.bucket}")
  {range_clause}
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
  |> limit(n: {limit})
"""
        records = self._query(query)
        candles = []
        for r in records:
            candles.append(
                {
                    "timestamp": (
                        r.get("_time", "").isoformat()
                        if hasattr(r.get("_time", ""), "isoformat")
                        else str(r.get("_time", ""))
                    ),
                    "open": r.get("open"),
                    "high": r.get("high"),
                    "low": r.get("low"),
                    "close": r.get("close"),
                    "volume": r.get("volume"),
                }
            )
        return candles

    def get_latest_price(self, symbol: str) -> Dict[str, Any]:
        """Get the most recent candle close price for a symbol.

        Returns:
            Dict with symbol, price, volume_24h, change_24h, timestamp.
        """
        # Get the latest candle
        latest_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
"""
        latest = self._query(latest_query)
        if not latest:
            return {
                "symbol": symbol,
                "price": None,
                "volume_24h": None,
                "change_24h": None,
                "timestamp": None,
            }

        current_price = latest[0].get("close")
        timestamp = latest[0].get("_time", "")

        # Get 24h volume and price change
        summary_query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
"""
        records_24h = self._query(summary_query)
        volume_24h = sum(r.get("volume", 0) or 0 for r in records_24h)
        change_24h = None
        if records_24h and current_price is not None:
            first_close = records_24h[0].get("close")
            if first_close and first_close != 0:
                change_24h = ((current_price - first_close) / first_close) * 100

        return {
            "symbol": symbol,
            "price": current_price,
            "volume_24h": volume_24h,
            "change_24h": round(change_24h, 4) if change_24h is not None else None,
            "timestamp": (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp)
            ),
        }

    def get_volatility(self, symbol: str, period_minutes: int = 60) -> Dict[str, Any]:
        """Compute volatility metrics from recent candles.

        Args:
            symbol: Currency pair.
            period_minutes: Lookback period in minutes.

        Returns:
            Dict with symbol, volatility (stddev of returns), atr, period.
        """
        query = f"""
from(bucket: "{self.bucket}")
  |> range(start: -{period_minutes}m)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
"""
        records = self._query(query)
        if len(records) < 2:
            return {
                "symbol": symbol,
                "volatility": None,
                "atr": None,
                "period": period_minutes,
            }

        # Compute returns for stddev
        closes = [r.get("close") for r in records if r.get("close") is not None]
        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] != 0:
                returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

        volatility = None
        if returns:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = round(variance**0.5, 8)

        # Compute ATR (Average True Range)
        true_ranges = []
        for i in range(1, len(records)):
            high = records[i].get("high", 0) or 0
            low = records[i].get("low", 0) or 0
            prev_close = records[i - 1].get("close", 0) or 0
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        atr = round(sum(true_ranges) / len(true_ranges), 8) if true_ranges else None

        return {
            "symbol": symbol,
            "volatility": volatility,
            "atr": atr,
            "period": period_minutes,
        }

    def get_market_summary(self, symbol: str) -> Dict[str, Any]:
        """Get aggregated market summary for a symbol.

        Returns:
            Dict with price, change_1h, change_24h, volume_24h, volatility,
            high_24h, low_24h, vwap.
        """
        # Get 24h candle data
        query_24h = f"""
from(bucket: "{self.bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "candles")
  |> filter(fn: (r) => r.currency_pair == "{symbol}")
  |> filter(fn: (r) => r._field == "open" or r._field == "high" or r._field == "low" or r._field == "close" or r._field == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
"""
        records = self._query(query_24h)
        if not records:
            return {
                "symbol": symbol,
                "price": None,
                "change_1h": None,
                "change_24h": None,
                "volume_24h": None,
                "volatility": None,
                "high_24h": None,
                "low_24h": None,
                "vwap": None,
            }

        current_price = records[-1].get("close")
        first_close_24h = records[0].get("close")

        # 24h metrics
        highs = [r.get("high", 0) or 0 for r in records]
        lows = [r.get("low", 0) or 0 for r in records if (r.get("low") or 0) > 0]
        volumes = [r.get("volume", 0) or 0 for r in records]
        high_24h = max(highs) if highs else None
        low_24h = min(lows) if lows else None
        volume_24h = sum(volumes)

        # VWAP calculation
        vwap = None
        total_volume = sum(volumes)
        if total_volume > 0:
            # Use typical price * volume
            vwap_numerator = sum(
                (
                    (r.get("high", 0) or 0)
                    + (r.get("low", 0) or 0)
                    + (r.get("close", 0) or 0)
                )
                / 3
                * (r.get("volume", 0) or 0)
                for r in records
            )
            vwap = round(vwap_numerator / total_volume, 8)

        # 24h change
        change_24h = None
        if first_close_24h and first_close_24h != 0 and current_price is not None:
            change_24h = round(
                ((current_price - first_close_24h) / first_close_24h) * 100, 4
            )

        # 1h change - find candle closest to 1h ago
        change_1h = None
        one_hour_records = [r for i, r in enumerate(records) if i >= len(records) - 60]
        if one_hour_records and current_price is not None:
            first_close_1h = one_hour_records[0].get("close")
            if first_close_1h and first_close_1h != 0:
                change_1h = round(
                    ((current_price - first_close_1h) / first_close_1h) * 100, 4
                )

        # Volatility (stddev of returns over 24h)
        closes = [r.get("close") for r in records if r.get("close") is not None]
        volatility = None
        if len(closes) >= 2:
            returns = []
            for i in range(1, len(closes)):
                if closes[i - 1] != 0:
                    returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
            if returns:
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                volatility = round(variance**0.5, 8)

        return {
            "symbol": symbol,
            "price": current_price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "vwap": vwap,
        }

    def close(self) -> None:
        """Close the InfluxDB connection."""
        if self.client:
            self.client.close()
            logging.info("InfluxDB connection closed")
