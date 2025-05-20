import os
import signal
import time
from datetime import datetime, timedelta, timezone

from absl import app
from absl import flags
from absl import logging

# Global flag to indicate if a shutdown signal has been received
shutdown_requested = False

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

# CoinMarketCap Flags
flags.DEFINE_string(
    "cmc_api_key", os.getenv("CMC_API_KEY"), "CoinMarketCap API Key."
)
flags.DEFINE_integer(
    "top_n_cryptos", 20, "Number of top cryptocurrencies to fetch from CMC."
)

# Tiingo Flags
flags.DEFINE_string(
    "tiingo_api_key", os.getenv("TIINGO_API_KEY"), "Tiingo API Key."
)

# InfluxDB Flags
default_influx_url = os.getenv(
    "INFLUXDB_URL",
    # Adjust this if your Helm release name for InfluxDB is different,
    # or if not running in k8s and need a direct localhost.
    "http://influxdb.tradestream-namespace.svc.cluster.local:8086",
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

# Candle Processing Flags
flags.DEFINE_integer(
    "candle_granularity_minutes", 1, "Granularity of candles in minutes."
)
flags.DEFINE_string(
    "backfill_start_date",
    "1_year_ago",
    'Start date for historical backfill (YYYY-MM-DD, "X_days_ago", "X_months_ago", "X_years_ago", or "skip").',
)
flags.DEFINE_integer(
    "tiingo_api_call_delay_seconds",
    2,
    "Delay in seconds between Tiingo API calls for different tickers/chunks during backfill and polling.",
)
flags.DEFINE_integer(
    "polling_initial_catchup_days",
    7,
    "How many days back to check for initial polling state if none is found from backfill.",
)

# Mark required flags
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
    # This dictionary will be updated with the latest backfill timestamps from this run.
    # Polling loop will independently fetch its state but this can be a fallback/informational.
    last_processed_candle_timestamps_from_current_session: dict[str, int],
):
    logging.info("Starting historical candle backfill...")
    overall_backfill_config_start_dt = parse_backfill_start_date(
        backfill_start_date_str
    )
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    # End date for historical is up to the start of the current UTC day (exclusive)
    end_date_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if overall_backfill_config_start_dt >= end_date_dt:
        logging.info(
            f"Overall backfill start date from config ({overall_backfill_config_start_dt.strftime('%Y-%m-%d')}) "
            f"is not before effective end date ({end_date_dt.strftime('%Y-%m-%d')}). Skipping backfill process."
        )
        return

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)

    for ticker in tiingo_tickers:
        current_ticker_start_dt = overall_backfill_config_start_dt
        latest_ts_processed_in_current_backfill_run = 0

        # Get last processed timestamp from InfluxDB for "backfill"
        last_backfill_ts_from_db = (
            influx_manager.get_last_processed_timestamp(
                ticker, "backfill"
            )
        )

        if last_backfill_ts_from_db:
            last_backfill_dt_from_db = datetime.fromtimestamp(
                last_backfill_ts_from_db / 1000.0, timezone.utc
            )
            # Start fetching *after* the last successfully backfilled candle
            potential_start_dt_from_db = (
                last_backfill_dt_from_db + granularity_delta
            )
            # Ensure this new start_dt does not precede the overall configured start_date_dt
            current_ticker_start_dt = max(
                overall_backfill_config_start_dt, potential_start_dt_from_db
            )
            latest_ts_processed_in_current_backfill_run = last_backfill_ts_from_db
            logging.info(
                f"Resuming backfill for {ticker} from DB state: {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(Last processed DB timestamp: {last_backfill_ts_from_db})"
            )
        else:
            logging.info(
                f"No previous backfill state found for {ticker} in DB. "
                f"Starting from configured/default: {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        if current_ticker_start_dt >= end_date_dt:
            logging.info(
                f"Ticker {ticker} already backfilled up to or beyond target end date "
                f"({current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} >= {end_date_dt.strftime('%Y-%m-%d %H:%M:%S')}). "
                f"Last processed timestamp: {latest_ts_processed_in_current_backfill_run}. Skipping."
            )
            continue

        logging.info(
            f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_date_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        chunk_start_dt = current_ticker_start_dt

        while chunk_start_dt < end_date_dt:
            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            # Fetch up to 90 days or until end_date_dt, whichever is sooner
            chunk_end_dt = min(
                chunk_start_dt + timedelta(days=89),
                end_date_dt - timedelta(microseconds=1),
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
                # Filter candles to ensure we only write those strictly after the last processed one
                # This is particularly important if chunk_start_dt was adjusted by DB state
                candles_to_write = [
                    c for c in historical_candles 
                    if c["timestamp_ms"] > latest_ts_processed_in_current_backfill_run
                ]

                if candles_to_write:
                    num_written = influx_manager.write_candles_batch(candles_to_write)
                    if num_written > 0:
                        last_written_ts = candles_to_write[-1]["timestamp_ms"]
                        influx_manager.update_last_processed_timestamp(
                            ticker, "backfill", last_written_ts
                        )
                        latest_ts_processed_in_current_backfill_run = last_written_ts
                        logging.info(f"  Successfully wrote {num_written} candles for {ticker}. Last written TS: {last_written_ts}")
                    else:
                        logging.info(f"  Write attempt for {len(candles_to_write)} candles for {ticker} resulted in 0 written.")
                else:
                    logging.info(f"  No new candles to write for {ticker} in this chunk after filtering by last processed TS ({latest_ts_processed_in_current_backfill_run}).")
            else:
                logging.info(
                    f"  No data in chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
                )

            chunk_start_dt = chunk_end_dt + timedelta(days=1)
            if chunk_start_dt < end_date_dt and len(tiingo_tickers) > 1:
                logging.info(
                    f"Waiting {api_call_delay_seconds}s before next API call/chunk for {ticker}..."
                )
                time.sleep(api_call_delay_seconds)

        if latest_ts_processed_in_current_backfill_run > 0:
            last_processed_candle_timestamps_from_current_session[ticker] = latest_ts_processed_in_current_backfill_run
        logging.info(
            f"Finished backfill for {ticker}. Last successfully processed timestamp for this run: {last_processed_candle_timestamps_from_current_session.get(ticker)}"
        )
    logging.info("Historical candle backfill completed.")


def run_polling_loop(
    influx_manager: InfluxDBManager,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catchup_days: int,
    # This dict can be pre-populated by backfill, but polling will prioritize its own DB state.
    last_processed_candle_timestamps_from_session: dict[str, int],
):
    logging.info("Starting real-time candle polling loop...")
    # Access global shutdown_requested flag
    global shutdown_requested
    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)

    # Initialize last_processed_timestamps for each ticker based on DB state or defaults
    last_processed_timestamps_for_polling = {} # Internal state for this loop
    now_utc_for_init = datetime.now(timezone.utc)
    default_catchup_start_dt_config = now_utc_for_init - timedelta(
        days=initial_catchup_days
    )
    default_catchup_start_minute_aligned = (
        (default_catchup_start_dt_config.minute // candle_granularity_minutes)
        * candle_granularity_minutes
    )
    default_catchup_start_dt_aligned = default_catchup_start_dt_config.replace(
        minute=default_catchup_start_minute_aligned, second=0, microsecond=0
    )
    default_catchup_start_ms_config = int(
        default_catchup_start_dt_aligned.timestamp() * 1000
    )

    for ticker in tiingo_tickers:
        final_start_ts_ms = None
        source_msg = ""

        # 1. Try to get "polling" state from DB
        polling_ts_db = influx_manager.get_last_processed_timestamp(
            ticker, "polling"
        )
        if polling_ts_db:
            final_start_ts_ms = polling_ts_db
            source_msg = f"Resuming polling for {ticker} from DB 'polling' state: {datetime.fromtimestamp(final_start_ts_ms/1000.0, timezone.utc).isoformat()}"
        else:
            # 2. Try to get "backfill" state from DB
            backfill_ts_db = influx_manager.get_last_processed_timestamp(
                ticker, "backfill"
            )
            if backfill_ts_db:
                final_start_ts_ms = backfill_ts_db
                source_msg = f"No 'polling' state for {ticker}. Using DB 'backfill' state: {datetime.fromtimestamp(final_start_ts_ms/1000.0, timezone.utc).isoformat()}"
            else:
                # 3. Use session state (e.g. from a very recent backfill in same script run) as a closer default if available
                session_ts = last_processed_candle_timestamps_from_session.get(ticker)
                if session_ts and session_ts > default_catchup_start_ms_config : # Ensure it's more recent than wide default
                    final_start_ts_ms = session_ts
                    source_msg = f"No DB state for {ticker}. Using current session's last processed timestamp: {datetime.fromtimestamp(final_start_ts_ms/1000.0, timezone.utc).isoformat()}"
                else:
                    # 4. Use default catch-up if no other state is found or session state is too old
                    final_start_ts_ms = default_catchup_start_ms_config
                    source_msg = (
                        f"No DB or recent session state for {ticker}. "
                        f"Setting polling start from configured catchup {initial_catchup_days} days ago: "
                        f"{default_catchup_start_dt_aligned.isoformat()}"
                    )
        
        last_processed_timestamps_for_polling[ticker] = final_start_ts_ms
        logging.info(source_msg)

    try:
        # while True: # Old line
        while not shutdown_requested: # New line
            loop_start_time = time.monotonic()
            current_cycle_time_utc = datetime.now(timezone.utc)
            logging.info(f"Starting polling cycle at {current_cycle_time_utc.isoformat()}")

            for ticker in tiingo_tickers:
                try:
                    last_ts_ms = last_processed_timestamps_for_polling.get(ticker)
                    if last_ts_ms is None: # Should not happen due to init logic
                        logging.error(f"CRITICAL: Missing last_ts_ms for {ticker} in polling loop. Re-initializing with default catchup for next cycle.")
                        last_ts_ms = default_catchup_start_ms_config # Fallback for current iteration
                        last_processed_timestamps_for_polling[ticker] = last_ts_ms
                    
                    last_known_candle_start_dt_utc = datetime.fromtimestamp(last_ts_ms / 1000.0, timezone.utc)

                    current_minute_floored = (current_cycle_time_utc.minute // candle_granularity_minutes) * candle_granularity_minutes
                    latest_closed_period_end_dt_utc = current_cycle_time_utc.replace(
                        minute=current_minute_floored, second=0, microsecond=0
                    )
                    target_latest_closed_candle_start_dt_utc = latest_closed_period_end_dt_utc - granularity_delta

                    if target_latest_closed_candle_start_dt_utc.timestamp() * 1000 <= last_ts_ms:
                        logging.debug(
                            f"Candle for {ticker} starting at {target_latest_closed_candle_start_dt_utc.isoformat()} "
                            f"(or earlier) already processed (last was {last_known_candle_start_dt_utc.isoformat()}). Skipping."
                        )
                        continue

                    query_start_dt_utc = last_known_candle_start_dt_utc + granularity_delta
                    query_end_dt_utc = target_latest_closed_candle_start_dt_utc + granularity_delta - timedelta(seconds=1)

                    if query_start_dt_utc > current_cycle_time_utc:
                        logging.debug(f"Query start time {query_start_dt_utc.isoformat()} is in the future for {ticker}. Skipping.")
                        continue
                    
                    query_end_dt_utc = min(query_end_dt_utc, current_cycle_time_utc)

                    if query_start_dt_utc > query_end_dt_utc:
                        logging.debug(f"Calculated query start {query_start_dt_utc.isoformat()} is after query end {query_end_dt_utc.isoformat()} for {ticker}. Skipping API call.")
                        continue

                    if candle_granularity_minutes >= 1440:
                        query_start_str = query_start_dt_utc.strftime("%Y-%m-%d")
                        query_end_str = query_end_dt_utc.strftime("%Y-%m-%d")
                    else:
                        query_start_str = query_start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                        query_end_str = query_end_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")

                    logging.info(f"Polling for {ticker} from {query_start_str} to {query_end_str}")

                    polled_candles = get_historical_candles_tiingo(
                        tiingo_api_key,
                        ticker,
                        query_start_str,
                        query_end_str,
                        resample_freq,
                    )

                    if polled_candles:
                        new_candles_to_write = []
                        for c in polled_candles:
                            candle_ts_ms = c["timestamp_ms"]
                            candle_end_ts_ms = candle_ts_ms + granularity_delta.total_seconds() * 1000
                            if candle_ts_ms > last_ts_ms and candle_end_ts_ms <= current_cycle_time_utc.timestamp() * 1000:
                                new_candles_to_write.append(c)
                        
                        new_candles_to_write.sort(key=lambda c: c["timestamp_ms"])

                        if new_candles_to_write:
                            logging.info(f"Fetched {len(new_candles_to_write)} new candle(s) for {ticker} via polling.")
                            num_written = influx_manager.write_candles_batch(new_candles_to_write)
                            if num_written > 0:
                                last_written_polled_ts = new_candles_to_write[-1]["timestamp_ms"]
                                influx_manager.update_last_processed_timestamp(
                                    ticker, "polling", last_written_polled_ts
                                )
                                last_processed_timestamps_for_polling[ticker] = last_written_polled_ts
                                logging.info(f"  Successfully wrote {num_written} polled candles for {ticker}. Last written TS: {last_written_polled_ts}")
                            else:
                                logging.info(f"  Write attempt for {len(new_candles_to_write)} polled candles for {ticker} resulted in 0 written.")
                        else:
                            logging.info(f"No new, fully closed candles found for {ticker} in polled range after filtering.")
                    else:
                        logging.info(f"Polling returned no data for {ticker} for period starting {query_start_str}")

                    if len(tiingo_tickers) > 1:
                        time.sleep(api_call_delay_seconds)

                except Exception as e:
                    logging.exception(f"Error polling for ticker {ticker}: {e}")

            loop_duration = time.monotonic() - loop_start_time
            sleep_time = (candle_granularity_minutes * 60) - loop_duration
            if sleep_time > 0:
                logging.info(f"Polling cycle finished in {loop_duration:.2f}s. Sleeping for {sleep_time:.2f}s.")
                time.sleep(sleep_time)
            else:
                logging.warning(
                    f"Polling cycle duration ({loop_duration:.2f}s) exceeded granularity ({candle_granularity_minutes*60}s). "
                    "Running next cycle immediately."
                )
    except KeyboardInterrupt:
        # This might still be triggered if shutdown_requested is set during a sleep or blocking call inside the loop
        # before the `while not shutdown_requested` check happens for the next iteration.
        # Or if a second SIGINT is sent.
        logging.info("Polling loop interrupted by KeyboardInterrupt (SIGINT).")
        # Ensure shutdown_requested is also set if KeyboardInterrupt occurs, to signal other parts if needed
        shutdown_requested = True 
    finally:
        if shutdown_requested:
            logging.info("Shutdown requested, exiting polling loop.")
        logging.info("Polling loop finished.")


# Signal handler function
def handle_shutdown_signal(signum, frame):
    global shutdown_requested
    logging.info(f"Received shutdown signal {signum}. Attempting graceful shutdown...")
    shutdown_requested = True


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    logging.info("Starting candle ingestor script (Python)...")
    logging.info("Configuration:")
    # ... (logging of flags as before) ...
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

    # This dictionary can store the latest timestamps processed by backfill in the current session.
    # Polling loop will primarily use DB state but can use this as a more up-to-date fallback if needed.
    last_processed_candle_timestamps_from_session = {}

    try:
        if FLAGS.backfill_start_date.lower() != "skip":
            run_backfill(
                influx_manager,
                tiingo_tickers,
                FLAGS.tiingo_api_key,
                FLAGS.backfill_start_date,
                FLAGS.candle_granularity_minutes,
                FLAGS.tiingo_api_call_delay_seconds,
                last_processed_candle_timestamps_from_session, # Updated by run_backfill
            )
        else:
            logging.info("Skipping historical backfill as per 'backfill_start_date' flag.")
            # Polling loop will initialize its state from DB or defaults.

        run_polling_loop(
            influx_manager,
            tiingo_tickers,
            FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds,
            FLAGS.polling_initial_catchup_days,
            last_processed_candle_timestamps_from_session, # Pass for potential fallback
            # test_max_cycles=None # In production, this runs indefinitely
        )

    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
    finally:
        logging.info("Main process finished. Closing InfluxDB connection.")
        influx_manager.close()

    return 0


if __name__ == "__main__":
    app.run(main)
