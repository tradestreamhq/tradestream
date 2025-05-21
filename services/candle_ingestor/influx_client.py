from absl import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError

# Define common retry parameters for InfluxDB operations
influx_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((InfluxDBError, ConnectionError, TimeoutError)), # Added ConnectionError, TimeoutError
    reraise=True
)

class InfluxDBManager:
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        try:
            self._connect()
        except Exception as e: # Catch exceptions reraised by _connect after retries
            logging.warning(f"InfluxDBManager __init__ failed to connect after retries: {e}")
            # self.client is already None, which is correct.

    @retry(**influx_retry_params)
    def _connect(self):
        try:
            self.client = InfluxDBClient(
                url=self.url, token=self.token, org=self.org
            )
            logging.info(
                f"Attempting to connect to InfluxDB at {self.url} for org '{self.org}'"
            )
            if self.client.ping():
                logging.info(
                    "Successfully connected to InfluxDB and pinged server."
                )
            else:
                # This path might be less common as ping() itself might raise on failure
                logging.error(
                    f"Failed to ping InfluxDB at {self.url}. Check connection and configuration."
                )
                self.client = None
                raise InfluxDBError(message="Ping failed") # Raise to trigger retry
        except Exception as e:
            logging.error(
                f"Error connecting to InfluxDB at {self.url}: {e}"
            )
            self.client = None
            raise # Reraise to allow tenacity to retry

    def get_client(self):
        return self.client

    def get_write_api(self, write_options=SYNCHRONOUS):
        if not self.client:
            logging.error(
                "InfluxDB client not initialized. Cannot get write_api."
            )
            return None
        return self.client.write_api(write_options=write_options)

    def get_query_api(self):
        if not self.client:
            logging.error(
                "InfluxDB client not initialized. Cannot get query_api."
            )
            return None
        return self.client.query_api()

    def get_bucket(self):
        return self.bucket

    def get_org(self):
        return self.org

    @retry(**influx_retry_params)
    def _write_candles_batch_retryable(self, candles_data: list[dict]) -> int:
        if not self.client:
            logging.error("InfluxDB client not initialized in _write_candles_batch_retryable.")
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
                    Point("candles")
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
                logging.warning(f"Skipping candle due to missing key {ke}: {candle_dict}")
            except (TypeError, ValueError) as ve:
                logging.warning(f"Skipping candle due to value error {ve}: {candle_dict}")

        if not points:
            logging.info("No valid points to write after filtering.")
            return 0

        write_api = self.get_write_api()
        if write_api:
            write_api.write(
                bucket=self.bucket, org=self.org, record=points
            )
            logging.info(
                f"Successfully wrote {len(points)} candle points to InfluxDB for {candles_data[0].get('currency_pair', 'N/A')}."
            )
            return len(points)
        return 0


    def write_candles_batch(self, candles_data: list[dict]) -> int:
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot write candles.")
            return 0
        try:
            return self._write_candles_batch_retryable(candles_data)
        except (InfluxDBError, ConnectionError, TimeoutError) as e:
            logging.error(f"InfluxDBError writing batch after all retries: {e}")
            return 0
        except Exception as e:
            logging.error(f"Generic error writing batch to InfluxDB after all retries: {e}")
            return 0

    @retry(**influx_retry_params)
    def _get_last_processed_timestamp_retryable(self, symbol: str, ingestion_type: str) -> int | None:
        if not self.client:
            logging.error("InfluxDB client not initialized in _get_last_processed_timestamp_retryable.")
            return None

        query_api = self.get_query_api()
        if not query_api:
            logging.error("Failed to get query_api in _get_last_processed_timestamp_retryable.")
            return None

        flux_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r._measurement == "ingestor_processing_state")
          |> filter(fn: (r) => r.symbol == "{symbol}")
          |> filter(fn: (r) => r.ingestion_type == "{ingestion_type}")
          |> filter(fn: (r) => r._field == "last_processed_timestamp_ms")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)
          |> yield(name: "last")
        '''
        logging.debug(f"Executing Flux query for state: {flux_query}")
        tables = query_api.query(query=flux_query, org=self.org)
        for table in tables:
            for record in table.records:
                timestamp_ms = record.get_value()
                logging.info(f"Retrieved last processed timestamp for {symbol} ({ingestion_type}): {timestamp_ms}")
                return int(timestamp_ms)
        logging.info(f"No prior processing state found for {symbol} ({ingestion_type}).")
        return None

    def get_last_processed_timestamp(self, symbol: str, ingestion_type: str) -> int | None:
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot query state.")
            return None
        try:
            return self._get_last_processed_timestamp_retryable(symbol, ingestion_type)
        except (InfluxDBError, ConnectionError, TimeoutError) as e:
            logging.error(f"Query for {symbol} ({ingestion_type}) failed after all retries: {e}")
            return None
        except Exception as e:
            logging.error(f"Generic error querying {symbol} ({ingestion_type}) after all retries: {e}")
            return None

    @retry(**influx_retry_params)
    def _update_last_processed_timestamp_retryable(self, symbol: str, ingestion_type: str, timestamp_ms: int):
        if not self.client:
            logging.error("InfluxDB client not initialized in _update_last_processed_timestamp_retryable.")
            return
        write_api = self.get_write_api()
        if not write_api:
            logging.error("Failed to get write_api in _update_last_processed_timestamp_retryable.")
            return

        point = (
            Point("ingestor_processing_state")
            .tag("symbol", symbol)
            .tag("ingestion_type", ingestion_type)
            .field("last_processed_timestamp_ms", int(timestamp_ms))
        )
        write_api.write(bucket=self.bucket, org=self.org, record=point)
        logging.info(f"Successfully updated processing state for {symbol} ({ingestion_type}) to {timestamp_ms}")

    def update_last_processed_timestamp(self, symbol: str, ingestion_type: str, timestamp_ms: int):
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot update state.")
            return
        try:
            self._update_last_processed_timestamp_retryable(symbol, ingestion_type, timestamp_ms)
        except (InfluxDBError, ConnectionError, TimeoutError) as e:
            logging.error(f"Update for {symbol} ({ingestion_type}) failed after all retries: {e}")
        except Exception as e:
            logging.error(f"Generic error updating {symbol} ({ingestion_type}) after all retries: {e}")

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("InfluxDB client closed.")
                self.client = None # Explicitly set to None after closing
            except Exception as e:
                logging.error(f"Error closing InfluxDB client: {e}")
