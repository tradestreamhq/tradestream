from absl import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
from typing import List, Dict, Optional


# Define common retry parameters for InfluxDB operations
influx_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (InfluxDBError, ConnectionError, TimeoutError)
    ),
    reraise=True,
)


class InfluxDBManager:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client: Optional[InfluxDBClient] = None
        try:
            self._connect()
        except Exception as e:
            logging.warning(
                f"InfluxDBManager __init__ failed to connect after retries: {e}"
            )


    @retry(**influx_retry_params)
    def _connect(self):
        try:
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            logging.info(
                f"Attempting to connect to InfluxDB at {self.url} for org '{self.org}'"
            )
            if not self.client.ping():
                logging.error(
                    f"Failed to ping InfluxDB at {self.url}. Check connection and configuration."
                )
                self.client = None
                raise InfluxDBError(message="Ping failed")

            logging.info("Successfully connected to InfluxDB and pinged server.")
        except Exception as e:
            logging.error(f"Error connecting to InfluxDB at {self.url}: {e}")
            self.client = None
            raise

    def get_client(self) -> Optional[InfluxDBClient]:
        return self.client

    def get_write_api(self, write_options=SYNCHRONOUS):
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot get write_api.")
            return None
        return self.client.write_api(write_options=write_options)

    def get_query_api(self):
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot get query_api.")
            return None
        return self.client.query_api()

    def get_bucket(self) -> str:
        return self.bucket

    def get_org(self) -> str:
        return self.org

    @retry(**influx_retry_params)
    def _write_candles_batch_retryable(self, candles_data: List[Dict]) -> int:
        if not self.client:
            logging.error(
                "InfluxDB client not initialized in _write_candles_batch_retryable."
            )
            return 0
        if not candles_data:
            return 0

        points = []
        for candle_dict in candles_data:
            try:
                currency_pair_tag = str(candle_dict["currency_pair"])
                timestamp_ms = int(candle_dict["timestamp_ms"])
                open_val = float(candle_dict["open"])
                high_val = float(candle_dict["high"])
                low_val = float(candle_dict["low"])
                close_val = float(candle_dict["close"])
                volume_val = float(candle_dict["volume"])

                point = (
                    Point("candles") # Measurement name for candles
                    .tag("currency_pair", currency_pair_tag)
                    .field("open", open_val)
                    .field("high", high_val)
                    .field("low", low_val)
                    .field("close", close_val)
                    .field("volume", volume_val)
                    .time(timestamp_ms, WritePrecision.MS)
                )
                points.append(point)
            except KeyError as ke:
                logging.warning(
                    f"Skipping candle due to missing key {ke}: {candle_dict}"
                )
            except (TypeError, ValueError) as ve:
                logging.warning(
                    f"Skipping candle due to value error {ve}: {candle_dict}"
                )

        if not points:
            logging.info("No valid points to write after filtering.")
            return 0

        write_api = self.get_write_api()
        if write_api:
            write_api.write(bucket=self.bucket, org=self.org, record=points)
            logging.info(
                f"Successfully wrote {len(points)} candle points to InfluxDB for {candles_data[0].get('currency_pair', 'N/A')}."
            )
            return len(points)
        return 0

    def write_candles_batch(self, candles_data: List[Dict]) -> int:
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot write candles.")
            return 0
        try:
            return self._write_candles_batch_retryable(candles_data)
        except RetryError as e: # Catch RetryError specifically
            logging.error(f"InfluxDBError writing batch after all retries: {e}")
            return 0
        except Exception as e: # Catch other unexpected errors
            logging.error(
                f"Generic error writing batch to InfluxDB after all retries: {e}"
            )
            return 0

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("InfluxDB client closed.")
            except Exception as e:
                logging.error(f"Error closing InfluxDB client: {e}")
            finally:
                self.client = None
                