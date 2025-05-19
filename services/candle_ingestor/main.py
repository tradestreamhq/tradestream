import os
import time # For sleep
from datetime import datetime, timedelta, timezone

from absl import app
from absl import flags
from absl import logging

from services.candle_ingestor.cmc_client import get_top_n_crypto_symbols
from services.candle_ingestor.influx_client import InfluxDBManager
from services.candle_ingestor.tiingo_client import (
    get_historical_candles_tiingo,
)
# Updated import:
from services.candle_ingestor.ingestion_helpers import (
    get_tiingo_resample_freq,
    parse_backfill_start_date,
)


FLAGS = flags.FLAGS
# ... (All flag definitions remain the same as in the previous step for PR4) ...
flags.DEFINE_string(
    "cmc_api_key", os.getenv("CMC_API_KEY"), "CoinMarketCap API Key."
)
flags.DEFINE_integer(
    "top_n_cryptos", 20, "Number of top cryptocurrencies to fetch from CMC."
)
flags.DEFINE_string(
    "tiingo_api_key", os.getenv("TIINGO_API_KEY"), "Tiingo API Key."
)
default_influx_url = os.getenv(
    "INFLUXDB_URL",
    "http://my-tradestream-influxdb.tradestream-namespace.svc.cluster.local:8086",
)
flags.DEFINE_string("influxdb_url", default_influx_url, "InfluxDB URL.")
flags.DEFINE_string(
    "influxdb_token", os.getenv("INFLUXDB_TOKEN"), "InfluxDB Token."
)
flags.DEFINE_string(
    "influxdb_org", os.getenv("INFLUXDB_ORG"), "InfluxDB Organization."
)
flags.DEFINE_string(
    "influxdb_bucket",
    os.getenv("INFLUXDB_BUCKET", "tradestream-data"),
    "InfluxDB Bucket for candles.",
)
flags.DEFINE_integer(
    "candle_granularity_minutes", 1, "Granularity of candles in minutes."
)
flags.DEFINE_string(
    "backfill_start_date",
    "1_year_ago",
    'Start date for historical backfill (YYYY-MM-DD, "X_days_ago", "X_months_ago", "X_years_ago").',
)
flags.DEFINE_integer(
    "tiingo_api_call_delay_seconds", 2, "Delay in seconds between Tiingo API calls for different tickers/chunks during backfill."
)

flags.mark_flag_as_required("cmc_api_key")
flags.mark_flag_as_required("tiingo_api_key")
flags.mark_flag_as_required("influxdb_token")
flags.mark_flag_as_required("influxdb_org")


def run_backfill(
    influx_manager: InfluxDBManager,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    backfill_start_date_str: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
):
    # ... (Content of run_backfill remains the same as in the previous step for PR4,
    #      it already uses the imported get_tiingo_resample_freq and parse_backfill_start_date) ...
    logging.info("Starting historical candle backfill...")
    start_date_dt = parse_backfill_start_date(backfill_start_date_str)
    end_date_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(microseconds=1)

    if start_date_dt >= end_date_dt:
        logging.info(
            f"Backfill start date ({start_date_dt.strftime('%Y-%m-%d')}) is not before end date "
            f"({end_date_dt.strftime('%Y-%m-%d')}). Skipping backfill."
        )
        return

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)

    for ticker in tiingo_tickers:
        current_ticker_start_dt = start_date_dt
        logging.info(
            f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')}"
        )
        chunk_start_dt = current_ticker_start_dt
        while chunk_start_dt < end_date_dt:
            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            chunk_end_dt = min(
                chunk_start_dt + timedelta(days=89), end_date_dt
            )
            chunk_end_str = chunk_end_dt.strftime("%Y-%m-%d")
            logging.info(
                f"  Fetching chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
            )
            historical_candles = get_historical_candles_tiingo(
                tiingo_api_key,
                ticker,
                chunk_start_str,
                chunk_end_str,
                resample_freq,
            )
            if historical_candles:
                historical_candles.sort(key=lambda c: c["timestamp_ms"])
                influx_manager.write_candles_batch(historical_candles)
            else:
                logging.info(
                    f"  No data in chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
                )
            chunk_start_dt = chunk_end_dt + timedelta(days=1)
            if chunk_start_dt < end_date_dt:
                logging.info(f"Waiting {api_call_delay_seconds}s before next API call for {ticker}...")
                time.sleep(api_call_delay_seconds)
        logging.info(f"Finished backfill for {ticker}.")
    logging.info("Historical candle backfill completed.")


def main(argv):
    # ... (Initial logging of flags and InfluxDBManager setup remains the same as PR4) ...
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    logging.info("Starting candle ingestor script (Python)...")

    logging.info("Configuration:")
    logging.info(
        f"  CoinMarketCap API Key: {'****' if FLAGS.cmc_api_key else 'Not Set/Loaded from Env'}"
    )
    logging.info(f"  Top N Cryptos: {FLAGS.top_n_cryptos}")
    logging.info(
        f"  Tiingo API Key: {'****' if FLAGS.tiingo_api_key else 'Not Set/Loaded from Env'}"
    )
    logging.info(f"  InfluxDB URL: {FLAGS.influxdb_url}")
    logging.info(
        f"  InfluxDB Token: {'****' if FLAGS.influxdb_token else 'Not Set/Loaded from Env'}"
    )
    logging.info(f"  InfluxDB Org: {FLAGS.influxdb_org}")
    logging.info(f"  InfluxDB Bucket: {FLAGS.influxdb_bucket}")
    logging.info(
        f"  Candle Granularity: {FLAGS.candle_granularity_minutes} min(s)"
    )
    logging.info(f"  Backfill Start Date: {FLAGS.backfill_start_date}")
    logging.info(f"  Tiingo API Call Delay: {FLAGS.tiingo_api_call_delay_seconds}s")

    influx_manager = InfluxDBManager(
        url=FLAGS.influxdb_url,
        token=FLAGS.influxdb_token,
        org=FLAGS.influxdb_org,
        bucket=FLAGS.influxdb_bucket,
    )

    if not influx_manager.get_client():
        logging.error("Failed to connect to InfluxDB. Exiting.")
        return 1

    tiingo_tickers = get_top_n_crypto_symbols(
        FLAGS.cmc_api_key, FLAGS.top_n_cryptos
    )

    if not tiingo_tickers:
        logging.error("No symbols fetched from CoinMarketCap. Exiting.")
        influx_manager.close()
        return 1

    logging.info(f"Target Tiingo tickers: {tiingo_tickers}")

    try:
        run_backfill(
            influx_manager,
            tiingo_tickers,
            FLAGS.tiingo_api_key,
            FLAGS.backfill_start_date,
            FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds,
        )
    except Exception as e:
        logging.exception(f"Critical error during backfill process: {e}")

    logging.info(
        "Historical backfill phase complete. Polling for recent candles (PR5) is next."
    )
    logging.info("Main process finished. Closing InfluxDB connection.")
    influx_manager.close()
    return 0


if __name__ == "__main__":
    app.run(main)
