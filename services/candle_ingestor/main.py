import os
import time
from datetime import datetime, timedelta, timezone

from absl import app
from absl import flags
from absl import logging

from services.candle_ingestor.cmc_client import get_top_n_crypto_symbols
from services.candle_ingestor.influx_client import InfluxDBManager
from services.candle_ingestor.tiingo_client import (
    get_historical_candles_tiingo,
)
from services.candle_ingestor.ingestion_helpers import (
    get_tiingo_resample_freq,
    parse_backfill_start_date,
)

FLAGS = flags.FLAGS
# ... (Flag definitions remain the same) ...
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
flags.DEFINE_integer(
    "polling_initial_catchup_days", 7, "How many days back to check for initial polling state if none is found."
)


flags.mark_flag_as_required("cmc_api_key")
flags.mark_flag_as_required("tiingo_api_key")
flags.mark_flag_as_required("influxdb_token")
flags.mark_flag_as_required("influxdb_org")


# --- Backfill Function (from PR4, assumed complete for this PR) ---
def run_backfill(
    influx_manager: InfluxDBManager,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    backfill_start_date_str: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    # This will be used by polling loop to initialize last_polled_candle_timestamps
    last_backfilled_timestamps: dict[str, int] 
):
    logging.info("Starting historical candle backfill...")
    start_date_dt = parse_backfill_start_date(backfill_start_date_str)
    end_date_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(microseconds=1)

    if start_date_dt >= end_date_dt:
        logging.info(f"Backfill start date is not before end date. Skipping backfill.")
        return

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    for ticker in tiingo_tickers:
        current_ticker_start_dt = start_date_dt
        logging.info(f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d')} to {end_date_dt.strftime('%Y-%m-%d')}")
        chunk_start_dt = current_ticker_start_dt
        max_timestamp_for_ticker_in_backfill = 0

        while chunk_start_dt < end_date_dt:
            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            chunk_end_dt = min(chunk_start_dt + timedelta(days=89), end_date_dt)
            chunk_end_str = chunk_end_dt.strftime("%Y-%m-%d")
            logging.info(f"  Fetching chunk for {ticker}: {chunk_start_str} to {chunk_end_str}")
            historical_candles = get_historical_candles_tiingo(
                tiingo_api_key, ticker, chunk_start_str, chunk_end_str, resample_freq
            )
            if historical_candles:
                historical_candles.sort(key=lambda c: c["timestamp_ms"])
                influx_manager.write_candles_batch(historical_candles)
                if historical_candles: # update max_timestamp
                    max_timestamp_for_ticker_in_backfill = max(max_timestamp_for_ticker_in_backfill, historical_candles[-1]["timestamp_ms"])
            else:
                logging.info(f"  No data in chunk for {ticker}: {chunk_start_str} to {chunk_end_str}")
            
            chunk_start_dt = chunk_end_dt + timedelta(days=1)
            if chunk_start_dt < end_date_dt:
                logging.info(f"Waiting {api_call_delay_seconds}s before next API call for {ticker}...")
                time.sleep(api_call_delay_seconds)
        
        if max_timestamp_for_ticker_in_backfill > 0:
            last_backfilled_timestamps[ticker] = max_timestamp_for_ticker_in_backfill
        logging.info(f"Finished backfill for {ticker}. Last backfilled ts: {last_backfilled_timestamps.get(ticker)}")
    logging.info("Historical candle backfill completed.")


# --- Polling Loop (New for PR5) ---
def run_polling_loop(
    influx_manager: InfluxDBManager,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catchup_days: int,
    # Pass the map that was populated by backfill
    last_processed_timestamps: dict[str, int] 
):
    logging.info("Starting real-time candle polling loop...")
    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)

    # Initialize last_processed_timestamps if not already set by backfill
    # For symbols not in backfill map, or if backfill was skipped.
    # Query InfluxDB for the actual latest candle for robustness (PR6 task)
    # For PR5, if not in map, we start from `initial_catchup_days` ago.
    now_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    default_catchup_start_ms = now_utc_ms - timedelta(days=initial_catchup_days).total_seconds() * 1000

    for ticker in tiingo_tickers:
        if ticker not in last_processed_timestamps:
            # Basic catch-up start point if no backfill data for this ticker
            # This should ideally query InfluxDB for the true last point (PR6)
            logging.info(f"No backfill timestamp for {ticker}, setting polling start from approx {initial_catchup_days} days ago.")
            last_processed_timestamps[ticker] = default_catchup_start_ms


    try:
        while True:
            loop_start_time = time.monotonic()
            now_utc = datetime.now(timezone.utc)
            logging.info(f"Starting polling cycle at {now_utc.isoformat()}")

            for ticker in tiingo_tickers:
                try:
                    last_ts_ms = last_processed_timestamps.get(ticker)
                    if last_ts_ms is None:
                        logging.warning(f"Missing last timestamp for {ticker}, skipping this cycle for it.")
                        continue

                    last_dt_utc = datetime.fromtimestamp(last_ts_ms / 1000.0, timezone.utc)
                    
                    # Determine the start of the *next* candle period we need
                    next_candle_start_dt_utc = last_dt_utc.replace(second=0, microsecond=0)
                    # Align to granularity boundary
                    offset_minutes = next_candle_start_dt_utc.minute % candle_granularity_minutes
                    if offset_minutes > 0: # If not already on a boundary from previous poll
                        next_candle_start_dt_utc -= timedelta(minutes=offset_minutes)
                    
                    # If last_ts_ms was the start of the last candle, the next one starts after granularity
                    # This logic needs to be careful to not miss the candle whose start_time is last_ts_ms
                    # if last_ts_ms itself was a candle start.
                    # Let's assume last_ts_ms is the timestamp *of the last candle*.
                    # The next candle we want is the one starting *after* that.
                    
                    # Simplified: poll for the window that *should have just closed*
                    # Current time, truncated to the current candle's granularity
                    current_period_start_minute = (now_utc.minute // candle_granularity_minutes) * candle_granularity_minutes
                    current_period_start_dt_utc = now_utc.replace(minute=current_period_start_minute, second=0, microsecond=0)
                    
                    # The most recently *closed* candle started one granularity period before current_period_start_dt_utc
                    target_candle_start_dt_utc = current_period_start_dt_utc - granularity_delta

                    if target_candle_start_dt_utc.timestamp() * 1000 <= last_ts_ms:
                        logging.debug(f"Already processed candle for {ticker} at or after {target_candle_start_dt_utc.isoformat()}, skipping.")
                        continue # Already have this or newer

                    # Fetch data from the start of the last known candle up to the most recent potential closed candle.
                    # Tiingo's startDate is inclusive.
                    query_start_date_str = (datetime.fromtimestamp(last_ts_ms / 1000.0, timezone.utc) + granularity_delta).strftime("%Y-%m-%d")
                    # endDate for Tiingo historical API is inclusive.
                    # We want candles up to the one that just closed.
                    query_end_date_str = target_candle_start_dt_utc.strftime("%Y-%m-%d")
                    
                    # For intraday, Tiingo expects YYYY-MM-DDTHH:MM:SS for startDate/endDate if time is relevant
                    # For simplicity, if daily, just use date. If intraday, use more precise times.
                    if candle_granularity_minutes < 1440: # intraday
                        query_start_datetime_str = (datetime.fromtimestamp(last_ts_ms / 1000.0, timezone.utc) + granularity_delta).strftime("%Y-%m-%dT%H:%M:%S")
                        query_end_datetime_str = target_candle_start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                        
                        # Fetch slightly more to ensure the target candle is included if Tiingo aligns to strict boundaries
                        query_end_for_api = (target_candle_start_dt_utc + granularity_delta - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")

                        logging.info(f"Polling for {ticker} from {query_start_datetime_str} up to target start {target_candle_start_dt_utc.isoformat()}")
                        polled_candles = get_historical_candles_tiingo(
                            tiingo_api_key,
                            ticker,
                            query_start_datetime_str, # Start from after the last known
                            query_end_for_api,      # End at the end of the target candle period
                            resample_freq,
                        )
                    else: # daily
                        polled_candles = get_historical_candles_tiingo(
                            tiingo_api_key,
                            ticker,
                            query_start_date_str,
                            query_end_date_str,
                            resample_freq,
                        )

                    if polled_candles:
                        # Filter to ensure we only process new candles and exactly the target one if available
                        new_candles_to_write = [
                            c for c in polled_candles if c["timestamp_ms"] > last_ts_ms and 
                            # Ensure we only take candles that have fully closed relative to 'now_utc'
                            (c["timestamp_ms"] + granularity_delta.total_seconds() * 1000) <= (now_utc.timestamp() * 1000)
                        ]
                        new_candles_to_write.sort(key=lambda c: c["timestamp_ms"])

                        if new_candles_to_write:
                            logging.info(f"Fetched {len(new_candles_to_write)} new candle(s) for {ticker} via polling.")
                            influx_manager.write_candles_batch(new_candles_to_write)
                            last_processed_timestamps[ticker] = new_candles_to_write[-1]["timestamp_ms"]
                        else:
                            logging.info(f"No new, closed candles found for {ticker} in polled range.")
                    else:
                        logging.info(f"Polling returned no data for {ticker} for target period around {target_candle_start_dt_utc.isoformat()}")
                    
                    time.sleep(api_call_delay_seconds) # Delay between tickers

                except Exception as e:
                    logging.exception(f"Error polling for ticker {ticker}: {e}")
                    # Continue to next ticker

            loop_duration = time.monotonic() - loop_start_time
            sleep_time = (candle_granularity_minutes * 60) - loop_duration
            if sleep_time > 0:
                logging.info(f"Polling cycle finished in {loop_duration:.2f}s. Sleeping for {sleep_time:.2f}s.")
                time.sleep(sleep_time)
            else:
                logging.warning(f"Polling cycle duration ({loop_duration:.2f}s) exceeded granularity ({candle_granularity_minutes*60}s). Running next cycle immediately.")

    except KeyboardInterrupt:
        logging.info("Polling loop interrupted by user.")
    finally:
        logging.info("Polling loop finished.")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)
    logging.info("Starting candle ingestor script (Python)...")
    # ... (Log flag values - same as before) ...
    logging.info("Configuration:")
    logging.info(f"  CoinMarketCap API Key: {'****' if FLAGS.cmc_api_key else 'Not Set/Loaded from Env'}")
    logging.info(f"  Top N Cryptos: {FLAGS.top_n_cryptos}")
    logging.info(f"  Tiingo API Key: {'****' if FLAGS.tiingo_api_key else 'Not Set/Loaded from Env'}")
    logging.info(f"  InfluxDB URL: {FLAGS.influxdb_url}")
    logging.info(f"  InfluxDB Token: {'****' if FLAGS.influxdb_token else 'Not Set/Loaded from Env'}")
    logging.info(f"  InfluxDB Org: {FLAGS.influxdb_org}")
    logging.info(f"  InfluxDB Bucket: {FLAGS.influxdb_bucket}")
    logging.info(f"  Candle Granularity: {FLAGS.candle_granularity_minutes} min(s)")
    logging.info(f"  Backfill Start Date: {FLAGS.backfill_start_date}")
    logging.info(f"  Tiingo API Call Delay: {FLAGS.tiingo_api_call_delay_seconds}s")
    logging.info(f"  Polling Initial Catchup Days: {FLAGS.polling_initial_catchup_days}")


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

    # This map will store the timestamp of the last candle successfully processed, per ticker
    # It will be populated by backfill and then used/updated by the polling loop.
    last_processed_candle_timestamps = {} 

    try:
        if FLAGS.backfill_start_date.lower() != "skip":
            run_backfill(
                influx_manager,
                tiingo_tickers,
                FLAGS.tiingo_api_key,
                FLAGS.backfill_start_date,
                FLAGS.candle_granularity_minutes,
                FLAGS.tiingo_api_call_delay_seconds,
                last_processed_candle_timestamps # Pass the map to be populated
            )
        else:
            logging.info("Skipping historical backfill as per 'backfill_start_date' flag.")
            # Initialize timestamps for polling if backfill is skipped
            now_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            default_poll_start_ms = now_utc_ms - timedelta(days=FLAGS.polling_initial_catchup_days).total_seconds() * 1000
            for ticker in tiingo_tickers:
                last_processed_candle_timestamps[ticker] = default_poll_start_ms


        # Start polling for "real-time" (recent closed) candles
        run_polling_loop(
            influx_manager,
            tiingo_tickers,
            FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds,
            FLAGS.polling_initial_catchup_days,
            last_processed_candle_timestamps # Use the populated/initialized map
        )

    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
    finally:
        logging.info("Main process finished. Closing InfluxDB connection.")
        influx_manager.close()
    
    return 0


if __name__ == "__main__":
    app.run(main)
