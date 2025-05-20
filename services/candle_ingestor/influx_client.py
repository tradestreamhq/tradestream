from absl import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError


class InfluxDBManager:
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        self._connect()

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
                logging.error(
                    f"Failed to ping InfluxDB at {self.url}. Check connection and configuration."
                )
                self.client = None  # Prevent use of a non-functional client
        except Exception as e:
            logging.error(
                f"Error connecting to InfluxDB at {self.url}: {e}"
            )
            self.client = None

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

    def write_candles_batch(self, candles_data: list[dict]) -> int:
        """Writes a batch of candle data (list of dicts) to InfluxDB."""
        if not self.client:
            logging.error(
                "InfluxDB client not initialized. Cannot write candles."
            )
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
        if write_api:
            try:
                write_api.write(
                    bucket=self.bucket, org=self.org, record=points
                )
                logging.info(
                    f"Successfully wrote {len(points)} candle points to InfluxDB for {candles_data[0].get('currency_pair', 'N/A')}."
                )
                return len(points)
            except InfluxDBError as e: # More specific error handling
                logging.error(f"InfluxDBError writing batch: {e}")
            except Exception as e:
                logging.error(f"Generic error writing batch to InfluxDB: {e}")
        return 0

    def get_last_processed_timestamp(self, symbol: str, ingestion_type: str) -> int | None:
        """
        Queries InfluxDB for the last processed timestamp for a given symbol and ingestion type.
        Returns timestamp in milliseconds, or None.
        """
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot query state.")
            return None

        query_api = self.get_query_api()
        if not query_api:
            return None

        # Flux query to get the most recent last_processed_timestamp_ms
        # The state measurement is assumed to be in the same bucket as candle data.
        # If it's in a different bucket, adjust self.bucket in the query.
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
        try:
            tables = query_api.query(query=flux_query, org=self.org)
            for table in tables:
                for record in table.records:
                    timestamp_ms = record.get_value()
                    logging.info(f"Retrieved last processed timestamp for {symbol} ({ingestion_type}): {timestamp_ms}")
                    return int(timestamp_ms) # Ensure it's an int
            logging.info(f"No prior processing state found for {symbol} ({ingestion_type}).")
        except InfluxDBError as e:
            logging.error(f"InfluxDBError querying processing state for {symbol} ({ingestion_type}): {e}")
        except Exception as e:
            logging.error(f"Generic error querying processing state for {symbol} ({ingestion_type}): {e}")
        return None

    def update_last_processed_timestamp(self, symbol: str, ingestion_type: str, timestamp_ms: int):
        """
        Writes/updates the last processed timestamp for a symbol and ingestion type in InfluxDB.
        """
        if not self.client:
            logging.error("InfluxDB client not initialized. Cannot update state.")
            return

        write_api = self.get_write_api()
        if not write_api:
            return

        point = (
            Point("ingestor_processing_state")
            .tag("symbol", symbol)
            .tag("ingestion_type", ingestion_type)
            .field("last_processed_timestamp_ms", int(timestamp_ms)) # Ensure integer
            # InfluxDB automatically adds a timestamp for the write itself
        )
        try:
            write_api.write(bucket=self.bucket, org=self.org, record=point)
            logging.info(f"Successfully updated processing state for {symbol} ({ingestion_type}) to {timestamp_ms}")
        except InfluxDBError as e:
            logging.error(f"InfluxDBError updating processing state for {symbol} ({ingestion_type}): {e}")
        except Exception as e:
            logging.error(f"Generic error updating processing state for {symbol} ({ingestion_type}): {e}")


    def close(self):
        if self.client:
            self.client.close()
            logging.info("InfluxDB client closed.")
