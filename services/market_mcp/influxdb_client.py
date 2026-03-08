"""InfluxDB client for querying candle data."""

from absl import logging
from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

influx_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (InfluxDBError, ConnectionError, TimeoutError)
    ),
    reraise=True,
)


class InfluxDBQueryClient:
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        try:
            self._connect()
        except Exception as e:
            logging.warning(
                f"InfluxDBQueryClient failed to connect after retries: {e}"
            )

    @retry(**influx_retry_params)
    def _connect(self):
        try:
            self.client = InfluxDBClient(
                url=self.url, token=self.token, org=self.org
            )
            if not self.client.ping():
                self.client = None
                raise InfluxDBError(message="Ping failed")
            logging.info("Successfully connected to InfluxDB.")
        except Exception as e:
            logging.error(f"Error connecting to InfluxDB at {self.url}: {e}")
            self.client = None
            raise

    def query(self, flux_query: str) -> list[dict]:
        """Execute a Flux query and return results as list of dicts."""
        if not self.client:
            logging.error("InfluxDB client not initialized.")
            return []
        try:
            return self._query_retryable(flux_query)
        except Exception as e:
            logging.error(f"Query failed after retries: {e}")
            return []

    @retry(**influx_retry_params)
    def _query_retryable(self, flux_query: str) -> list[dict]:
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
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query candles from InfluxDB.

        Args:
            symbol: Currency pair (e.g. "BTC/USD").
            timeframe: Candle timeframe for aggregation window (e.g. "1m", "5m", "1h").
            start: Start time in RFC3339 or relative (e.g. "-1h"). Defaults to recent.
            end: End time in RFC3339 or relative. Defaults to now.
            limit: Maximum number of candles to return.

        Returns:
            List of candle dicts with timestamp, open, high, low, close, volume.
        """
        if start is None:
            start = "-24h"
        if end is None:
            end = "now()"
        else:
            end = f'time(v: "{end}")'

        # Build range clause
        if start.startswith("-"):
            range_clause = f"range(start: {start}, stop: {end})"
        else:
            range_clause = f'range(start: time(v: "{start}"), stop: {end})'

        flux = f'''
from(bucket: "{self.bucket}")
  |> {range_clause}
  |> filter(fn: (r) => r["_measurement"] == "candles")
  |> filter(fn: (r) => r["currency_pair"] == "{symbol}")
  |> filter(fn: (r) => r["_field"] == "open" or r["_field"] == "high" or r["_field"] == "low" or r["_field"] == "close" or r["_field"] == "volume")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
'''
        raw = self.query(flux)
        candles = []
        for r in raw:
            candles.append({
                "timestamp": r.get("_time", "").isoformat() if hasattr(r.get("_time", ""), "isoformat") else str(r.get("_time", "")),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
            })
        return candles

    def get_latest_candle(self, symbol: str) -> dict | None:
        """Get the most recent candle for a symbol."""
        candles = self.get_candles(symbol, limit=1)
        return candles[0] if candles else None

    def get_candles_for_period(
        self, symbol: str, period_minutes: int
    ) -> list[dict]:
        """Get candles for the last N minutes."""
        return self.get_candles(
            symbol, start=f"-{period_minutes}m", limit=period_minutes + 10
        )

    def get_candles_for_24h(self, symbol: str) -> list[dict]:
        """Get candles for the last 24 hours."""
        return self.get_candles(symbol, start="-24h", limit=1500)

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("InfluxDB client closed.")
            except Exception as e:
                logging.error(f"Error closing InfluxDB client: {e}")
            finally:
                self.client = None
