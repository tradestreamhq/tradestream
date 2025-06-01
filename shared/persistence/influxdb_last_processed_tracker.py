from absl import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS 
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
from typing import Optional

# Define common retry parameters for InfluxDB operations
# Copied from candle_ingestor.influx_client for consistency
influx_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((InfluxDBError, ConnectionError, TimeoutError)),
    reraise=False,  # Changed to False to raise RetryError instead of original exception
)


class InfluxDBLastProcessedTracker:
    """
    Manages last processed timestamps in InfluxDB for various services and keys.
    """

    MEASUREMENT_NAME = "processing_state"  # Unified measurement name

    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client: Optional[InfluxDBClient] = None  # Initialize client to None
        try:
            self._connect_with_retry()
        except RetryError:
            logging.error(
                f"InfluxDBLastProcessedTracker: __init__ failed to connect to InfluxDB at {self.url} after all retries."
            )
            # self.client remains None as initialized
        except (
            Exception
        ) as e:  # Catch any other unexpected error during initial connection attempt
            logging.error(
                f"InfluxDBLastProcessedTracker: Unexpected error during __init__ connection attempt for {self.url}: {e}"
            )
            self.client = None  # Ensure client is None

    @retry(**influx_retry_params)
    def _connect_with_retry(self):
        # Ensure client is None before attempting to create a new one in this retryable method
        # This is important if _connect_with_retry is called outside of __init__ (e.g. for reconnect)
        self.client = None
        try:
            logging.info(
                f"InfluxDBLastProcessedTracker: Attempting to connect to InfluxDB at {self.url} for org '{self.org}'"
            )
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            if not self.client.ping():
                logging.error(
                    f"InfluxDBLastProcessedTracker: Failed to ping InfluxDB at {self.url}."
                )
                self.client = None  # Ensure client is None if ping fails
                raise InfluxDBError(
                    message="Ping failed for InfluxDBLastProcessedTracker"
                )
            logging.info(
                "InfluxDBLastProcessedTracker: Successfully connected to InfluxDB."
            )
        except Exception as e:
            logging.error(
                f"InfluxDBLastProcessedTracker: Error connecting to InfluxDB at {self.url}: {e}"
            )
            self.client = None  # Ensure client is None on any exception
            raise

    @retry(**influx_retry_params)
    def _get_last_processed_timestamp_retryable(
        self, service_identifier: str, key: str
    ) -> Optional[int]:
        if not self.client:
            logging.warning(
                "InfluxDBLastProcessedTracker: Client not initialized in _get_last_processed_timestamp_retryable. Attempting to reconnect..."
            )
            self._connect_with_retry()  # This might raise RetryError if all attempts fail
            if (
                not self.client
            ):  # If still None after successful retry (should not happen if _connect_with_retry is correct) or if retry failed and was caught by public
                logging.error(
                    "InfluxDBLastProcessedTracker: Reconnect failed or client still None. Cannot get last processed timestamp."
                )
                return None

        query_api = self.client.query_api()
        if not query_api:  # Should not happen if client is valid
            logging.error(
                "InfluxDBLastProcessedTracker: Failed to get query_api in _get_last_processed_timestamp_retryable."
            )
            return None

        # 'key' (e.g. currency_pair) and 'service_identifier' are used as tags
        flux_query = f"""
        from(bucket: "{self.bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r._measurement == "{self.MEASUREMENT_NAME}")
          |> filter(fn: (r) => r.service_identifier == "{service_identifier}")
          |> filter(fn: (r) => r.key == "{key}")
          |> filter(fn: (r) => r._field == "last_processed_timestamp_ms")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)
          |> yield(name: "last")
        """
        logging.debug(
            f"InfluxDBLastProcessedTracker: Executing Flux query for state: {flux_query}"
        )
        tables = query_api.query(query=flux_query, org=self.org)
        for table in tables:
            for record in table.records:
                timestamp_ms = record.get_value()
                logging.info(
                    f"InfluxDBLastProcessedTracker: Retrieved last processed timestamp for {service_identifier} / {key}: {timestamp_ms}"
                )
                return int(timestamp_ms)
        logging.info(
            f"InfluxDBLastProcessedTracker: No prior processing state found for {service_identifier} / {key}."
        )
        return None

    def get_last_processed_timestamp(
        self, service_identifier: str, key: str
    ) -> Optional[int]:
        try:
            return self._get_last_processed_timestamp_retryable(service_identifier, key)
        except RetryError as e:  # Catch RetryError specifically if all retries fail
            logging.error(
                f"InfluxDBLastProcessedTracker: Query for {service_identifier} / {key} failed after all retries: {e}"
            )
            # self.client might be None here if _connect_with_retry failed within _get_last_processed_timestamp_retryable
            return None
        except Exception as e:  # Catch other unexpected errors
            logging.error(
                f"InfluxDBLastProcessedTracker: Generic error querying {service_identifier} / {key}: {e}"
            )
            return None

    @retry(**influx_retry_params)
    def _update_last_processed_timestamp_retryable(
        self, service_identifier: str, key: str, timestamp_ms: int
    ):
        if not self.client:
            logging.warning(
                "InfluxDBLastProcessedTracker: Client not initialized in _update_last_processed_timestamp_retryable. Attempting to reconnect..."
            )
            self._connect_with_retry()
            if not self.client:
                logging.error(
                    "InfluxDBLastProcessedTracker: Reconnect failed. Cannot update last processed timestamp."
                )
                # If retries are exhausted in _connect_with_retry, RetryError will be raised,
                # so this explicit return might not be reached if _connect_with_retry reraises.
                # However, if _connect_with_retry failed silently (which it shouldn't with reraise=True),
                # this return is a safeguard.
                return

        write_api = self.client.write_api(
            write_options=SYNCHRONOUS
        )  # Using MS precision
        if not write_api:  # Should not happen if client is valid
            logging.error(
                "InfluxDBLastProcessedTracker: Failed to get write_api in _update_last_processed_timestamp_retryable."
            )
            return

        point = (
            Point(self.MEASUREMENT_NAME)
            .tag("service_identifier", service_identifier)
            .tag("key", key)
            .field("last_processed_timestamp_ms", int(timestamp_ms))
            # Using InfluxDB's server-side timestamp for the point itself,
            # the field stores our application-specific timestamp.
        )
        write_api.write(bucket=self.bucket, org=self.org, record=point)
        logging.info(
            f"InfluxDBLastProcessedTracker: Successfully updated processing state for {service_identifier} / {key} to {timestamp_ms}"
        )

    def update_last_processed_timestamp(
        self, service_identifier: str, key: str, timestamp_ms: int
    ):
        try:
            self._update_last_processed_timestamp_retryable(
                service_identifier, key, timestamp_ms
            )
        except RetryError as e:
            logging.error(
                f"InfluxDBLastProcessedTracker: Update for {service_identifier} / {key} failed after all retries: {e}"
            )
        except Exception as e:
            logging.error(
                f"InfluxDBLastProcessedTracker: Generic error updating {service_identifier} / {key}: {e}"
            )

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("InfluxDBLastProcessedTracker: Client connection closed.")
            except Exception as e:
                logging.error(
                    f"InfluxDBLastProcessedTracker: Error closing client connection: {e}"
                )
            finally:
                self.client = None
