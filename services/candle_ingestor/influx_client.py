from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from absl import logging

class InfluxDBManager:
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket # Store bucket for later use
        self.client = None
        self._connect()

    def _connect(self):
        try:
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            logging.info(f"Attempting to connect to InfluxDB at {self.url} for org '{self.org}'")
            if self.client.ping():
                logging.info("Successfully connected to InfluxDB and pinged server.")
            else:
                logging.error(f"Failed to ping InfluxDB at {self.url}. Check connection and configuration.")
                self.client = None # Prevent use of a non-functional client
        except Exception as e:
            logging.error(f"Error connecting to InfluxDB at {self.url}: {e}")
            self.client = None

    def get_client(self):
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

    def get_bucket(self):
        return self.bucket

    def get_org(self):
        return self.org

    def close(self):
        if self.client:
            self.client.close()
            logging.info("InfluxDB client closed.")
