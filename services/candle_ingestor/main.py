from absl import app
from absl import flags
from absl import logging
import os

from services.candle_ingestor.cmc_client import get_top_n_crypto_symbols
from services.candle_ingestor.influx_client import InfluxDBManager

FLAGS = flags.FLAGS

# CoinMarketCap Flags
flags.DEFINE_string('cmc_api_key', os.getenv('CMC_API_KEY'), 'CoinMarketCap API Key.')
flags.DEFINE_integer('top_n_cryptos', 20, 'Number of top cryptocurrencies to fetch from CMC.')

# Tiingo Flags
flags.DEFINE_string('tiingo_api_key', os.getenv('TIINGO_API_KEY'), 'Tiingo API Key.')

# InfluxDB Flags
# Default InfluxDB URL assumes it's running in the same k8s cluster in 'tradestream-namespace'
# and the service is named 'influxdb' (adjust 'my-tradestream-influxdb' if that's the Helm release name)
flags.DEFINE_string('influxdb_url', os.getenv('INFLUXDB_URL', 'http://my-tradestream-influxdb.tradestream-namespace.svc.cluster.local:8086'), 'InfluxDB URL.')
flags.DEFINE_string('influxdb_token', os.getenv('INFLUXDB_TOKEN'), 'InfluxDB Token.')
flags.DEFINE_string('influxdb_org', os.getenv('INFLUXDB_ORG'), 'InfluxDB Organization.')
flags.DEFINE_string('influxdb_bucket', os.getenv('INFLUXDB_BUCKET', 'tradestream-data'), 'InfluxDB Bucket for candles.')

# Candle Processing Flags
flags.DEFINE_integer('candle_granularity_minutes', 1, 'Granularity of candles in minutes.')
flags.DEFINE_string('backfill_start_date', '1_year_ago',
                    'Start date for historical backfill (YYYY-MM-DD, "X_days_ago", "X_months_ago", "X_years_ago").')

# Mark required flags (absl-py will exit if these are not provided and don't have a default from os.getenv that resolves)
flags.mark_flag_as_required('cmc_api_key')
flags.mark_flag_as_required('tiingo_api_key')
flags.mark_flag_as_required('influxdb_token')
flags.mark_flag_as_required('influxdb_org')


def main(argv):
    del argv # Unused.
    logging.set_verbosity(logging.INFO) # Default to INFO level
    logging.info('Starting candle ingestor script (Python)...')

    logging.info('Configuration:')
    logging.info(f'  CoinMarketCap API Key: {"****" if FLAGS.cmc_api_key else "Not Set/Loaded from Env"}')
    logging.info(f'  Top N Cryptos: {FLAGS.top_n_cryptos}')
    logging.info(f'  Tiingo API Key: {"****" if FLAGS.tiingo_api_key else "Not Set/Loaded from Env"}')
    logging.info(f'  InfluxDB URL: {FLAGS.influxdb_url}')
    logging.info(f'  InfluxDB Token: {"****" if FLAGS.influxdb_token else "Not Set/Loaded from Env"}')
    logging.info(f'  InfluxDB Org: {FLAGS.influxdb_org}')
    logging.info(f'  InfluxDB Bucket: {FLAGS.influxdb_bucket}')
    logging.info(f'  Candle Granularity: {FLAGS.candle_granularity_minutes} min(s)')
    logging.info(f'  Backfill Start Date: {FLAGS.backfill_start_date}')

    # 1. Connect to InfluxDB
    influx_manager = InfluxDBManager(
        url=FLAGS.influxdb_url,
        token=FLAGS.influxdb_token,
        org=FLAGS.influxdb_org,
        bucket=FLAGS.influxdb_bucket
    )

    if not influx_manager.get_client():
        logging.error("Failed to connect to InfluxDB. Exiting.")
        return 1 # Indicate error

    # 2. Fetch top N cryptos from CMC
    logging.info(f"Fetching top {FLAGS.top_n_cryptos} crypto symbols from CoinMarketCap...")
    # Assuming USD pairs for Tiingo, adjust if necessary
    tiingo_tickers = get_top_n_crypto_symbols(FLAGS.cmc_api_key, FLAGS.top_n_cryptos)

    if not tiingo_tickers:
        logging.error("No symbols fetched from CoinMarketCap. Exiting.")
        influx_manager.close()
        return 1

    logging.info(f"Target Tiingo tickers: {tiingo_tickers}")

    # Placeholder for future logic
    logging.info('Script setup complete. Further implementation in subsequent PRs.')
    # - Backfill historical data from Tiingo REST (PR4)
    # - Start polling Tiingo REST for recent candles (PR5)

    logging.info("Initialization complete. Awaiting further implementation for data processing.")
    influx_manager.close()
    return 0

if __name__ == '__main__':
    app.run(main)
