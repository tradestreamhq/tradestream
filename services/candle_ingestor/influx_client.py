from absl import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException as InfluxApiException
import requests # For requests.exceptions.ConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

TENACITY_LOGGER = logging.get_absl_logger()

# Define the state measurement name as a class constant
INGESTOR_PROCESSING_STATE_MEASUREMENT = "ingestor_processing_state"

RETRYABLE_INFLUX_EXCEPTIONS = (
    requests.exceptions.ConnectionError, # Network issues
    InfluxApiException, # API errors from InfluxDB, some might be transient
)

class InfluxDBManager:
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        self._connect() # Initial connection attempt

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RETRYABLE_INFLUX_EXCEPTIONS),
        before_sleep=before_sleep_log(TENACITY_LOGGER, logging.INFO),
    )
    def _connect(self):
        # This method now primarily focuses on the connection and ping.
        # Error handling for the initial setup is managed by tenacity.
        self.client = InfluxDBClient(
            url=self.url, token=self.token, org=self.org
        )
        logging.info(
            f"Attempting to connect to InfluxDB at {self.url} for org '{self.org}' (Attempt {getattr(self._connect, 'retry', {}).get('statistics', {}).get('attempt_number', 1)})"
        )
        if not self.client.ping():
            # This path might indicate a configuration issue more than a transient one if ping consistently fails.
            # However, network issues could also cause ping to fail.
            logging.error(
                f"Failed to ping InfluxDB at {self.url}. This might be a transient issue or configuration error."
            )
            # Raising an exception ensures tenacity retries if it's a retryable one.
            # Using a generic exception here, but specific ones from ping() if available would be better.
            raise requests.exceptions.ConnectionError(f"Failed to ping InfluxDB at {self.url}") 
        logging.info(
            "Successfully connected to InfluxDB and pinged server."
        )
        # If connection fails after retries, self.client might remain None or an unusable client.
        # Subsequent calls will check self.client.

    def get_client(self):
        # Ensure connection is re-attempted if client is None (e.g. initial _connect failed all retries)
        if self.client is None:
            logging.warning("InfluxDB client was None. Attempting to reconnect.")
            try:
                self._connect() # This will use tenacity
            except Exception as e: # Catch if _connect itself fails all retries
                logging.error(f"Reconnection attempt failed after retries: {e}")
                self.client = None # Ensure client is still None
        return self.client

    def get_write_api(self, write_options=SYNCHRONOUS):
        # Ensure client is available before getting write_api
        current_client = self.get_client()
        if not current_client:
            logging.error(
                "InfluxDB client not available. Cannot get write_api."
            )
            return None
        return current_client.write_api(write_options=write_options)

    def get_query_api(self):
        # Ensure client is available before getting query_api
        current_client = self.get_client()
        if not current_client:
            logging.error(
                "InfluxDB client not available. Cannot get query_api."
            )
            return None
        return current_client.query_api()

    def get_bucket(self):
        return self.bucket

    def get_org(self):
        return self.org

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RETRYABLE_INFLUX_EXCEPTIONS),
        before_sleep=before_sleep_log(TENACITY_LOGGER, logging.INFO),
    )
    def write_candles_batch(self, candles_data: list[dict]) -> int:
        """Writes a batch of candle data (list of dicts) to InfluxDB."""
        # get_client() call at the start of get_write_api() handles client readiness.
        if not self.get_client(): # Double check, though get_write_api should handle it
            logging.error("InfluxDB client not initialized after retries. Cannot write candles.")
            return 0

        if not candles_data:
            return 0

        points = []
        for candle_dict in candles_data:
            try:
                # Ensure all fields are present and correctly typed before creating Point
                currency_pair_tag = str(candle_dict["currency_pair"]) # Tag values must be strings
                timestamp_ms = int(candle_dict["timestamp_ms"])
                open_val = float(candle_dict["open"])
                high_val = float(candle_dict["high"])
                low_val = float(candle_dict["low"])
                close_val = float(candle_dict["close"])
                volume_val = float(candle_dict["volume"])

                point = (
                    Point("candles")  # Measurement name
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
        if not write_api:
            logging.error("Failed to get write_api. Cannot write batch to InfluxDB.")
            # This implies connection issues were not resolved by retries in get_client/_connect
            return 0
        
        # The try-except block for the write operation itself is now managed by Tenacity's @retry decorator
        # for RETRYABLE_INFLUX_EXCEPTIONS.
        # If a non-retryable error occurs within this block (not ConnectionError or InfluxApiException),
        # it will propagate out of the tenacity retry loop.
        write_api.write(
            bucket=self.bucket, org=self.org, record=points
        )
        logging.info(
            f"Successfully wrote {len(points)} candle points to InfluxDB for {candles_data[0].get('currency_pair', 'N/A')}."
        )
        return len(points)
        # No explicit return 0 for error cases here, as tenacity will re-raise if all attempts fail for retryable exceptions.
        # If it's a non-retryable exception, it will propagate naturally.

    def close(self):
        current_client = self.get_client() # Attempt to connect if necessary before closing
        if current_client:
            current_client.close()
            logging.info("InfluxDB client closed.")
        else:
            logging.info("InfluxDB client was not initialized; no connection to close.")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RETRYABLE_INFLUX_EXCEPTIONS),
        before_sleep=before_sleep_log(TENACITY_LOGGER, logging.INFO),
    )
    def get_last_processed_timestamp(
        self, symbol: str, ingestion_type: str
    ) -> int | None:
        """
        Queries InfluxDB for the last processed timestamp for a given symbol and ingestion type.
        """
        # get_client() call at the start of get_query_api() handles client readiness.
        if not self.get_client(): # Double check
            logging.error("InfluxDB client not initialized after retries. Cannot query last processed timestamp.")
            return None

        # Flux query to get the last processed timestamp
        # We are storing last_processed_timestamp_ms as a field, not _value.
        # We sort by _time descending (InfluxDB's implicit timestamp for the record)
        # and take the last one.
        query = f"""
        from(bucket: "{self.bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r._measurement == "{INGESTOR_PROCESSING_STATE_MEASUREMENT}")
          |> filter(fn: (r) => r.symbol == "{symbol}")
          |> filter(fn: (r) => r.ingestion_type == "{ingestion_type}")
          |> sort(columns: ["_time"], desc: true)
          |> tail(n: 1)
          |> keep(columns: ["last_processed_timestamp_ms"])
        """
        query_api = self.get_query_api()
        if not query_api:
            logging.error("Failed to get query_api. Cannot query last processed timestamp.")
            return None

        # The try-except for the query operation is now managed by Tenacity for RETRYABLE_INFLUX_EXCEPTIONS
        logging.info(
            f"Querying last processed timestamp for symbol='{symbol}', type='{ingestion_type}' (Attempt {getattr(self.get_last_processed_timestamp, 'retry', {}).get('statistics', {}).get('attempt_number', 1)})"
        )
        tables = query_api.query(query, org=self.org)

        if not tables:
            logging.info(
                f"No previous state found for symbol='{symbol}', type='{ingestion_type}'."
            )
            return None

        for table in tables:
            if not table.records:
                continue
            for record in table.records:
                if "last_processed_timestamp_ms" in record.values:
                    timestamp = record.values["last_processed_timestamp_ms"]
                    logging.info(
                        f"Found last processed timestamp for symbol='{symbol}', type='{ingestion_type}': {timestamp}"
                    )
                    return int(timestamp)
                else:
                    logging.warning(
                        f"Record found for symbol='{symbol}', type='{ingestion_type}' but 'last_processed_timestamp_ms' field is missing."
                    )
                    return None
        
        logging.info(
            f"No record containing 'last_processed_timestamp_ms' found after querying for symbol='{symbol}', type='{ingestion_type}'."
        )
        return None
        # Non-retryable exceptions from parsing logic above will propagate.

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RETRYABLE_INFLUX_EXCEPTIONS),
        before_sleep=before_sleep_log(TENACITY_LOGGER, logging.INFO),
    )
    def update_last_processed_timestamp(
        self, symbol: str, ingestion_type: str, timestamp_ms: int
    ):
        """
        Writes or updates the last processed timestamp for a given symbol and ingestion type.
        """
        # get_client() call at the start of get_write_api() handles client readiness.
        if not self.get_client(): # Double check
            logging.error("InfluxDB client not initialized after retries. Cannot update last processed timestamp.")
            return # Or raise an error if a return value isn't expected by caller on failure

        point = (
            Point(INGESTOR_PROCESSING_STATE_MEASUREMENT)
            .tag("symbol", symbol)
            .tag("ingestion_type", ingestion_type)
            .field("last_processed_timestamp_ms", timestamp_ms)
            # .time(timestamp_ms, WritePrecision.MS) # We want InfluxDB to set its own timestamp for updated_at
        )

        write_api = self.get_write_api()
        if not write_api:
            logging.error("Failed to get write_api. Cannot update last processed timestamp.")
            return # Or raise

        point = (
            Point(INGESTOR_PROCESSING_STATE_MEASUREMENT)
            .tag("symbol", symbol)
            .tag("ingestion_type", ingestion_type)
            .field("last_processed_timestamp_ms", timestamp_ms)
        )

        # The try-except for the write operation is now managed by Tenacity for RETRYABLE_INFLUX_EXCEPTIONS
        write_api.write(bucket=self.bucket, org=self.org, record=point)
        logging.info(
            f"Successfully updated last processed timestamp for symbol='{symbol}', type='{ingestion_type}' to {timestamp_ms} (Attempt {getattr(self.update_last_processed_timestamp, 'retry', {}).get('statistics', {}).get('attempt_number', 1)})."
        )
        # If all retries fail for retryable exceptions, tenacity will re-raise.
        # Non-retryable exceptions will propagate.
