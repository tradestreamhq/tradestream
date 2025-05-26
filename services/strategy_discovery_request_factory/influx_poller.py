from absl import logging
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, Dialect
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import (
    SYNCHRONOUS,
)  # Not used for reads, but good to have for consistency
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from protos.marketdata_pb2 import Candle
from google.protobuf.timestamp_pb2 import Timestamp
from typing import Tuple, List, Optional

# Define common retry parameters for InfluxDB operations
influx_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((InfluxDBError, ConnectionError, TimeoutError)),
    reraise=True,
)


class InfluxPoller:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client: Optional[InfluxDBClient] = None
        self._connect_with_retry()

    @retry(**influx_retry_params)
    def _connect_with_retry(self):
        try:
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            logging.info(
                f"Attempting to connect to InfluxDB at {self.url} for org '{self.org}'"
            )
            if not self.client.ping():
                logging.error(f"Failed to ping InfluxDB at {self.url}.")
                self.client = None
                raise InfluxDBError(message="Ping failed")
            logging.info("Successfully connected to InfluxDB.")
        except Exception as e:
            logging.error(f"Error connecting to InfluxDB at {self.url}: {e}")
            self.client = None
            raise

    def fetch_new_candles(
        self, currency_pair: str, start_timestamp_ms: int = 0
    ) -> Tuple[List[Candle], int]:
        """
        Fetch new candles from InfluxDB for strategy discovery request generation.
        The candles are used to determine timing for strategy discovery time windows.
        Args:
            currency_pair: The currency pair to fetch candles for (e.g., "BTC/USD").
            start_timestamp_ms: The timestamp (in milliseconds since epoch) from which to
                                 start fetching candles. If 0, fetches all available data.
        Returns:
            A tuple containing:
                - A list of Candle protobuf messages.
                - The timestamp of the latest fetched candle in milliseconds, or
                  start_timestamp_ms if no new candles were fetched.
        """
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot fetch candles.")
            return [], start_timestamp_ms

        new_candles: List[Candle] = []
        latest_fetched_ts_ms = start_timestamp_ms
        query_api = self.client.query_api()

        # Convert start_timestamp_ms to nanoseconds for Flux query.
        # If start_timestamp_ms is 0, query from the beginning of time (InfluxDB default for range start:0).
        # Otherwise, add 1 millisecond (converted to nanoseconds) to avoid re-fetching the exact last record.
        start_range_ns = (
            (start_timestamp_ms * 1_000_000) + 1_000_000
            if start_timestamp_ms > 0
            else 0
        )

        flux_query = f"""
        from(bucket: "{self.bucket}")
          |> range(start: time(v: {start_range_ns}ns))
          |> filter(fn: (r) => r._measurement == "candles")
          |> filter(fn: (r) => r.currency_pair == "{currency_pair}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: false)
        """
        logging.debug(
            f"Executing Flux query for {currency_pair} after {start_timestamp_ms}ms: {flux_query}"
        )

        try:
            tables = query_api.query(query=flux_query, org=self.org)
            for table in tables:
                for record in table.records:
                    try:
                        time_obj = record.get_time()
                        if (
                            time_obj.tzinfo is None
                            or time_obj.tzinfo.utcoffset(time_obj) is None
                        ):
                            time_obj = time_obj.replace(tzinfo=timezone.utc)
                        else:
                            time_obj = time_obj.astimezone(timezone.utc)

                        ts_seconds = int(time_obj.timestamp())
                        ts_nanos = time_obj.microsecond * 1000

                        current_candle_ts_ms = ts_seconds * 1000 + ts_nanos // 1_000_000

                        candle = Candle(
                            timestamp=Timestamp(seconds=ts_seconds, nanos=ts_nanos),
                            currency_pair=record.values.get(
                                "currency_pair", currency_pair
                            ),
                            open=float(record.values.get("open", 0.0)),
                            high=float(record.values.get("high", 0.0)),
                            low=float(record.values.get("low", 0.0)),
                            close=float(record.values.get("close", 0.0)),
                            volume=float(record.values.get("volume", 0.0)),
                        )
                        new_candles.append(candle)
                        if current_candle_ts_ms > latest_fetched_ts_ms:
                            latest_fetched_ts_ms = current_candle_ts_ms
                    except Exception as e:
                        logging.warning(
                            f"Error processing InfluxDB record for {currency_pair}: {record.values}. Error: {e}"
                        )
            logging.info(
                f"Fetched {len(new_candles)} new candles for {currency_pair}. Latest ts: {latest_fetched_ts_ms}ms."
            )

        except InfluxDBError as e:
            logging.error(f"InfluxDB query failed for {currency_pair}: {e}")
            return [], start_timestamp_ms
        except Exception as e:
            logging.error(f"Unexpected error fetching candles for {currency_pair}: {e}")
            return [], start_timestamp_ms

        return new_candles, latest_fetched_ts_ms

    def close(self):
        if self.client:
            self.client.close()
            logging.info("InfluxDB client closed.")
            self.client = None
            