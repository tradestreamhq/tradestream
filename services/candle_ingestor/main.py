import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

from absl import app
from absl import flags
from absl import logging

from services.candle_ingestor.influx_client import InfluxDBManager
from services.candle_ingestor.tiingo_client import (
    get_historical_candles_tiingo,
)
from services.candle_ingestor.ingestion_helpers import (
    get_tiingo_resample_freq,
    parse_backfill_start_date,
)
from shared.cryptoclient.cmc_client import get_top_n_crypto_symbols
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker # New import

FLAGS = flags.FLAGS

# CoinMarketCap Flags
flags.DEFINE_string("cmc_api_key", os.getenv("CMC_API_KEY"), "CoinMarketCap API Key.")
flags.DEFINE_integer(
    "top_n_cryptos", 20, "Number of top cryptocurrencies to fetch from CMC."
)

# Tiingo Flags
flags.DEFINE_string("tiingo_api_key", os.getenv("TIINGO_API_KEY"), "Tiingo API Key.")

# InfluxDB Flags
default_influx_url = os.getenv(
    "INFLUXDB_URL",
    "http://influxdb.tradestream-namespace.svc.cluster.local:8086",
)
flags.DEFINE_string("influxdb_url", default_influx_url, "InfluxDB URL.")
flags.DEFINE_string("influxdb_token", os.getenv("INFLUXDB_TOKEN"), "InfluxDB Token.")
flags.DEFINE_string("influxdb_org", os.getenv("INFLUXDB_ORG"), "InfluxDB Organization.")
flags.DEFINE_string(
    "influxdb_bucket",
    os.getenv("INFLUXDB_BUCKET", "tradestream-data"),
    "InfluxDB Bucket for candles and state.",
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

# Run Mode Flag
flags.DEFINE_enum(
    "run_mode",
    "wet",
    ["wet", "dry"],
    "Run mode for the ingestor: 'wet' for live data, 'dry' for simulated data.",
)


# Global variables for shutdown handling
shutdown_requested = False
influx_manager_global: Optional[InfluxDBManager] = None
timestamp_tracker_global: Optional[InfluxDBLastProcessedTracker] = None # New global for tracker


def handle_shutdown_signal(signum, frame):
    global shutdown_requested, influx_manager_global, timestamp_tracker_global
    logging.info(
        f"Shutdown signal {signal.Signals(signum).name} received. Initiating graceful shutdown..."
    )
    shutdown_requested = True
    if influx_manager_global:
        try:
            logging.info(
                "Attempting to close InfluxDB connection (manager) from signal handler..."
            )
            influx_manager_global.close()
            logging.info("InfluxDB connection (manager) closed via signal handler.")
        except Exception as e:
            logging.error(f"Error closing InfluxDB connection (manager) from signal handler: {e}")
    if timestamp_tracker_global:
        try:
            logging.info(
                "Attempting to close InfluxDB connection (tracker) from signal handler..."
            )
            timestamp_tracker_global.close()
            logging.info("InfluxDB connection (tracker) closed via signal handler.")
        except Exception as e:
            logging.error(f"Error closing InfluxDB connection (tracker) from signal handler: {e}")


def run_backfill(
    influx_manager: Optional[InfluxDBManager],
    timestamp_tracker: Optional[InfluxDBLastProcessedTracker], # Added tracker
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    backfill_start_date_str: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    last_backfilled_timestamps: dict[str, int], # This could potentially be removed if tracker is source of truth
    run_mode: str,
):
    global shutdown_requested
    logging.info("Starting historical candle backfill...")
    if run_mode == "dry":
        logging.info("DRY RUN: Backfill will use dummy data and limited iterations.")

    earliest_backfill_flag_dt = parse_backfill_start_date(backfill_start_date_str)
    end_date_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if earliest_backfill_flag_dt >= end_date_dt:
        logging.info(
            f"Backfill flag start date ({earliest_backfill_flag_dt.strftime('%Y-%m-%d')}) is not before "
            f"effective end date ({end_date_dt.strftime('%Y-%m-%d')}). Skipping backfill."
        )
        return

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    dry_run_tickers_processed = 0
    max_dry_run_tickers = 1
    max_dry_run_chunks_per_ticker = 1
    
    service_id_backfill = "candle_ingestor_backfill"

    for ticker in tiingo_tickers:
        if shutdown_requested:
            logging.info(
                "Shutdown requested during backfill. Aborting backfill for remaining tickers."
            )
            break

        if run_mode == "dry" and dry_run_tickers_processed >= max_dry_run_tickers:
            logging.info(
                f"DRY RUN: Reached max tickers for backfill ({max_dry_run_tickers})."
            )
            shutdown_requested = True # In dry run, exit after processing a few
            break
        current_run_max_ts_for_ticker = 0
        db_last_backfill_ts_ms = None
        if timestamp_tracker: # Use the new tracker
            db_last_backfill_ts_ms = timestamp_tracker.get_last_processed_timestamp(
                service_identifier=service_id_backfill, key=ticker
            )
        elif run_mode == "dry": # Fallback for dry run if tracker not present
             db_last_backfill_ts_ms = last_backfilled_timestamps.get(ticker)


        if db_last_backfill_ts_ms and db_last_backfill_ts_ms > 0:
            dt_from_db_ts = datetime.fromtimestamp(
                db_last_backfill_ts_ms / 1000.0, timezone.utc
            )
            potential_next_start_from_db = (
                dt_from_db_ts.replace(second=0, microsecond=0) + granularity_delta
            )
            current_ticker_start_dt = max(
                earliest_backfill_flag_dt, potential_next_start_from_db
            )
            logging.info(
                f"Resuming backfill for {ticker} from DB state, effective start: {current_ticker_start_dt.isoformat()}"
            )
        else:
            current_ticker_start_dt = earliest_backfill_flag_dt
            logging.info(
                f"Starting new backfill for {ticker} from flag-defined start: {current_ticker_start_dt.isoformat()}"
            )

        if current_ticker_start_dt >= end_date_dt:
            logging.info(
                f"Ticker {ticker} already effectively backfilled up to or beyond target end date. Last known DB ts: {db_last_backfill_ts_ms}. Skipping."
            )
            continue

        logging.info(
            f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_date_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        chunk_start_dt = current_ticker_start_dt
        dry_run_chunks_processed = 0

        while chunk_start_dt < end_date_dt:
            if shutdown_requested:
                logging.info(
                    f"Shutdown requested during backfill for ticker {ticker}. Aborting current ticker."
                )
                break

            if (
                run_mode == "dry"
                and dry_run_chunks_processed >= max_dry_run_chunks_per_ticker
            ):
                logging.info(
                    f"DRY RUN: Reached max chunks for ticker {ticker} ({max_dry_run_chunks_per_ticker})."
                )
                break

            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            chunk_end_dt = min(
                chunk_start_dt + timedelta(days=89), # Tiingo historical API best practice for large pulls
                end_date_dt - timedelta(microseconds=1), # Ensure end_date is exclusive
            )
            chunk_end_str = chunk_end_dt.strftime("%Y-%m-%d")

            historical_candles = []
            if run_mode == "dry":
                logging.info(
                    f"DRY RUN: Simulating Tiingo API call for {ticker}: {chunk_start_str} to {chunk_end_str}"
                )
                dummy_ts_ms = int(
                    chunk_start_dt.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).timestamp()
                    * 1000
                )
                historical_candles = [
                    {
                        "timestamp_ms": dummy_ts_ms,
                        "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "volume": 100.0,
                        "currency_pair": ticker,
                    }
                ]
            else:
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
                written_count = 0
                if influx_manager:
                    written_count = influx_manager.write_candles_batch(
                        historical_candles
                    )

                if written_count > 0 or run_mode == "dry":
                    latest_ts_in_batch = historical_candles[-1]["timestamp_ms"]
                    current_run_max_ts_for_ticker = max(
                        current_run_max_ts_for_ticker, latest_ts_in_batch
                    )
                    if timestamp_tracker: # Use the new tracker
                        timestamp_tracker.update_last_processed_timestamp(
                            service_identifier=service_id_backfill, key=ticker, timestamp_ms=latest_ts_in_batch
                        )
                    last_backfilled_timestamps[ticker] = latest_ts_in_batch # Keep local for dry run potentially
                    logging.info(
                        f"  Successfully processed {len(historical_candles)} candles. Updated backfill state for {ticker} to {latest_ts_in_batch}"
                    )
                else: # if written_count == 0 and run_mode == "wet"
                    logging.warning(
                        f"  Write_candles_batch reported 0 candles written for {ticker} despite having data. DB State not updated for this batch."
                    )
            else:
                logging.info(
                    f"  No data in chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
                )

            dry_run_chunks_processed += 1
            chunk_start_dt = chunk_end_dt + timedelta(days=1) # Move to the next day for the next chunk
            if (
                chunk_start_dt < end_date_dt
                and len(tiingo_tickers) > 1
                and run_mode == "wet"
            ):
                logging.info(
                    f"Waiting {api_call_delay_seconds}s before next API call/chunk for {ticker}..."
                )
                for _ in range(api_call_delay_seconds):
                    if shutdown_requested:
                        break
                    time.sleep(1)
                if shutdown_requested:
                    break
        
        dry_run_tickers_processed +=1
        if shutdown_requested:
            logging.info(f"Shutdown requested after processing chunks for {ticker}.")
            break

        if current_run_max_ts_for_ticker > 0 :
             last_backfilled_timestamps[ticker] = max(last_backfilled_timestamps.get(ticker, 0), current_run_max_ts_for_ticker)

        logging.info(
            f"Finished backfill for {ticker}. Check InfluxDB for authoritative state."
        )

    if run_mode == "dry":
        logging.info("DRY RUN: Backfill simulation complete.")
        shutdown_requested = True # Ensure dry run exits after backfill simulation
    else:
        logging.info("Historical candle backfill completed.")


def run_polling_loop(
    influx_manager: Optional[InfluxDBManager],
    timestamp_tracker: Optional[InfluxDBLastProcessedTracker], # Added tracker
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catchup_days: int,
    last_processed_timestamps: dict[str, int], # This can be mainly for dry run or if tracker fails
    run_mode: str,
):
    global shutdown_requested
    logging.info("Starting real-time candle polling loop...")
    if run_mode == "dry":
        logging.info("DRY RUN: Polling will use dummy data and limited iterations.")

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    
    service_id_polling = "candle_ingestor_polling"
    service_id_backfill = "candle_ingestor_backfill"


    logging.info("Initializing polling timestamps...")
    for ticker_symbol in tiingo_tickers:
        if shutdown_requested:
            logging.info("Shutdown requested during polling timestamp initialization.")
            return

        # Prioritize tracker, then local dict (for dry run or resilience)
        initial_ts_from_tracker = None
        if timestamp_tracker:
            initial_ts_from_tracker = timestamp_tracker.get_last_processed_timestamp(
                service_identifier=service_id_polling, key=ticker_symbol
            )
            if not initial_ts_from_tracker: # If no polling state, check backfill state from tracker
                initial_ts_from_tracker = timestamp_tracker.get_last_processed_timestamp(
                    service_identifier=service_id_backfill, key=ticker_symbol
                )
        
        if initial_ts_from_tracker:
            last_processed_timestamps[ticker_symbol] = initial_ts_from_tracker
            logging.info(
                f"Using last processed timestamp for {ticker_symbol} from tracker: {datetime.fromtimestamp(initial_ts_from_tracker / 1000.0, timezone.utc).isoformat()}"
            )
        elif ticker_symbol not in last_processed_timestamps or last_processed_timestamps.get(ticker_symbol, 0) == 0:
            # Fallback to default catchup if no state in tracker or local dict
            now_utc_for_init = datetime.now(timezone.utc)
            default_catchup_start_dt = now_utc_for_init - timedelta(
                days=initial_catchup_days
            )
            default_catchup_start_minute = (
                default_catchup_start_dt.minute // candle_granularity_minutes
            ) * candle_granularity_minutes
            default_catchup_start_dt_aligned = default_catchup_start_dt.replace(
                minute=default_catchup_start_minute,
                second=0,
                microsecond=0,
            )
            default_catchup_start_ms = int(
                default_catchup_start_dt_aligned.timestamp() * 1000
            )
            last_processed_timestamps[ticker_symbol] = default_catchup_start_ms
            logging.info(
                f"No backfill or polling state for {ticker_symbol}. "
                f"Setting polling start from approx {initial_catchup_days} days ago: {default_catchup_start_dt_aligned.isoformat()}"
            )
        else: # Timestamp already in last_processed_timestamps (e.g. from backfill in this run)
             logging.info(
                f"Using pre-existing/backfill timestamp for {ticker_symbol} for polling start: {datetime.fromtimestamp(last_processed_timestamps[ticker_symbol] / 1000.0, timezone.utc).isoformat()}"
            )


    dry_run_polling_cycles = 0
    max_dry_run_polling_cycles = 2 # For dry run, only do a couple of cycles

    try:
        while not shutdown_requested:
            loop_start_time = time.monotonic()
            current_cycle_time_utc = datetime.now(timezone.utc)
            logging.info(
                f"Starting polling cycle at {current_cycle_time_utc.isoformat()}"
            )

            if (
                run_mode == "dry"
                and dry_run_polling_cycles >= max_dry_run_polling_cycles
            ):
                logging.info(
                    f"DRY RUN: Reached max polling cycles ({max_dry_run_polling_cycles})."
                )
                shutdown_requested = True
                break

            for ticker in tiingo_tickers:
                if shutdown_requested:
                    logging.info(
                        f"Shutdown requested during polling for ticker {ticker}."
                    )
                    break
                try:
                    last_ts_ms = last_processed_timestamps.get(ticker)
                    if last_ts_ms is None: # Should have been initialized
                        logging.error(
                            f"CRITICAL: Missing last_ts_ms for {ticker} at start of polling iteration. This should not happen."
                        )
                        # As a very defensive measure, re-initialize to avoid None.
                        last_ts_ms = int(
                            (
                                datetime.now(timezone.utc)
                                - timedelta(days=initial_catchup_days)
                            ).timestamp()
                            * 1000
                        )
                        last_processed_timestamps[ticker] = last_ts_ms


                    last_known_candle_start_dt_utc = datetime.fromtimestamp(
                        last_ts_ms / 1000.0, timezone.utc
                    )

                    # Determine the end of the latest *potentially closed* period based on current time
                    current_minute_floored = (
                        current_cycle_time_utc.minute // candle_granularity_minutes
                    ) * candle_granularity_minutes
                    latest_closed_period_end_dt_utc = current_cycle_time_utc.replace(
                        minute=current_minute_floored, second=0, microsecond=0
                    )
                    # The start time of the latest *potentially closed* candle
                    target_latest_closed_candle_start_dt_utc = (
                        latest_closed_period_end_dt_utc - granularity_delta
                    )


                    if (
                        target_latest_closed_candle_start_dt_utc.timestamp() * 1000
                        <= last_ts_ms
                    ):
                        logging.debug(
                            f"Candle for {ticker} starting at {target_latest_closed_candle_start_dt_utc.isoformat()} "
                            f"(or earlier) already processed (last was {last_known_candle_start_dt_utc.isoformat()}). Skipping."
                        )
                        continue

                    # Query from the start of the next expected candle after the last known one
                    query_start_dt_utc = (
                        last_known_candle_start_dt_utc + granularity_delta
                    )
                    # Query up to the current time to catch up
                    effective_query_end_dt_utc = current_cycle_time_utc


                    if query_start_dt_utc >= effective_query_end_dt_utc:
                        logging.debug(
                            f"Query start time {query_start_dt_utc.isoformat()} is not before effective query end {effective_query_end_dt_utc.isoformat()} for {ticker}. Skipping API call."
                        )
                        continue


                    query_start_str = (
                        query_start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                        if candle_granularity_minutes < 1440 # Daily uses YYYY-MM-DD
                        else query_start_dt_utc.strftime("%Y-%m-%d")
                    )
                    query_end_str = ( # End date for Tiingo historical API is exclusive for daily, inclusive for intraday generally.
                                      # For polling, we query up to "now".
                        effective_query_end_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                        if candle_granularity_minutes < 1440
                        else effective_query_end_dt_utc.strftime("%Y-%m-%d")
                    )


                    polled_candles = []
                    if run_mode == "dry":
                        logging.info(
                            f"DRY RUN: Simulating Tiingo API call for {ticker} from {query_start_str} to {query_end_str}"
                        )
                        # Simulate one new candle for dry run
                        dummy_ts_ms = int(query_start_dt_utc.timestamp() * 1000)
                        polled_candles = [
                            {
                                "timestamp_ms": dummy_ts_ms,
                                "open": 2.0, "high": 2.1, "low": 1.9, "close": 2.05, "volume": 50.0,
                                "currency_pair": ticker,
                            }
                        ]
                    else:
                        logging.info(
                            f"Polling for {ticker} from {query_start_str} to {query_end_str}"
                        )
                        polled_candles = get_historical_candles_tiingo(
                            tiingo_api_key,
                            ticker,
                            query_start_str,
                            query_end_str, # Query up to current time
                            resample_freq,
                        )

                    if polled_candles:
                        new_candles_to_write = []
                        for c in polled_candles:
                            candle_ts_ms = c["timestamp_ms"]
                            # Ensure candle is fully closed relative to current cycle time
                            # Candle start + duration <= current cycle time (approximately)
                            # A candle starting at 10:00 for 1min is closed at 10:01
                            candle_end_ts_ms = (
                                candle_ts_ms + granularity_delta.total_seconds() * 1000
                            )

                            if (
                                candle_ts_ms > last_ts_ms and # Newer than last processed
                                candle_end_ts_ms <= current_cycle_time_utc.timestamp() * 1000 + 1000 # Closed by now (add small buffer)
                            ):
                                new_candles_to_write.append(c)

                        new_candles_to_write.sort(key=lambda c: c["timestamp_ms"])

                        if new_candles_to_write:
                            logging.info(
                                f"Fetched {len(new_candles_to_write)} new, closed candle(s) for {ticker} via polling."
                            )
                            written_count = 0
                            if influx_manager:
                                written_count = influx_manager.write_candles_batch(
                                    new_candles_to_write
                                )

                            if written_count > 0 or run_mode == "dry":
                                latest_polled_ts_ms = new_candles_to_write[-1][
                                    "timestamp_ms"
                                ]
                                last_processed_timestamps[ticker] = latest_polled_ts_ms
                                if timestamp_tracker: # Use the new tracker
                                    timestamp_tracker.update_last_processed_timestamp(
                                        service_identifier=service_id_polling, key=ticker, timestamp_ms=latest_polled_ts_ms
                                    )
                                logging.info(
                                    f"  Successfully processed {written_count if written_count > 0 else len(new_candles_to_write)} candles. Updated polling state for {ticker} to {latest_polled_ts_ms}"
                                )
                            else: # written_count == 0 and run_mode == "wet"
                                logging.warning(
                                    f"  Polling write_candles_batch reported 0 candles written for {ticker}. DB State not updated for this batch."
                                )
                        else:
                            logging.info(
                                f"No new, fully closed candles found for {ticker} in polled range after filtering."
                            )
                    else:
                        logging.info(
                            f"Polling returned no data for {ticker} for period starting {query_start_str}"
                        )
                    
                    if shutdown_requested:
                        logging.info(
                            f"Shutdown requested after processing ticker {ticker}."
                        )
                        break

                    if len(tiingo_tickers) > 1 and run_mode == "wet":
                        # Delay between API calls for different tickers
                        for _ in range(api_call_delay_seconds):
                            if shutdown_requested:
                                break
                            time.sleep(1)
                        if shutdown_requested:
                            break

                except Exception as e:
                    logging.exception(f"Error polling for ticker {ticker}: {e}")
            
            if shutdown_requested:
                logging.info("Shutdown requested. Exiting polling loop.")
                break

            dry_run_polling_cycles += 1
            loop_duration = time.monotonic() - loop_start_time
            # Calculate sleep time to align with the start of the next candle_granularity_minutes interval
            # This helps maintain a consistent polling rhythm.
            # Example: if granularity is 1 min, and loop took 10s, sleep for 50s.
            # If loop took 70s, sleep for (120s - 70s) = 50s (to align with the next-next minute)
            
            # Calculate how many full intervals the loop took
            intervals_in_loop = loop_duration / (candle_granularity_minutes * 60)
            # Calculate the end time of the next full interval from the loop_start_time
            next_interval_boundary_duration = (int(intervals_in_loop) + 1) * (candle_granularity_minutes * 60)
            
            sleep_time = next_interval_boundary_duration - loop_duration
            if sleep_time <= 0: # If loop took longer than an interval, calculate sleep till next one
                sleep_time = (candle_granularity_minutes * 60) - (loop_duration % (candle_granularity_minutes * 60))
                if sleep_time <=0 : # Should not happen if logic above is correct but as a fallback
                    sleep_time = (candle_granularity_minutes * 60)


            if sleep_time > 0:
                logging.info(
                    f"Polling cycle finished in {loop_duration:.2f}s. Sleeping for {sleep_time:.2f}s."
                )
                for _ in range(int(sleep_time)): # Iterate for number of seconds
                    if shutdown_requested:
                        break
                    time.sleep(1)
                if shutdown_requested:
                    break
            else: # Should ideally not happen with the improved sleep calculation
                logging.warning(
                    f"Polling cycle duration ({loop_duration:.2f}s) was close to or exceeded granularity ({candle_granularity_minutes*60}s). "
                    "Running next cycle immediately or with minimal delay."
                )


    except KeyboardInterrupt:
        logging.info("Polling loop interrupted by user (KeyboardInterrupt).")
        shutdown_requested = True
    finally:
        logging.info("Polling loop finished.")


def main(argv):
    global shutdown_requested, influx_manager_global, timestamp_tracker_global
    del argv
    logging.set_verbosity(logging.INFO)

    if FLAGS.run_mode == "wet":
        if not FLAGS.cmc_api_key:
            logging.error("CMC_API_KEY is required for 'wet' mode. Set environment variable or use --cmc_api_key.")
            sys.exit(1)
        if not FLAGS.tiingo_api_key:
            logging.error("TIINGO_API_KEY is required for 'wet' mode. Set environment variable or use --tiingo_api_key.")
            sys.exit(1)
        if not FLAGS.influxdb_token:
            logging.error("INFLUXDB_TOKEN is required for 'wet' mode. Set environment variable or use --influxdb_token.")
            sys.exit(1)
        if not FLAGS.influxdb_org:
            logging.error("INFLUXDB_ORG is required for 'wet' mode. Set environment variable or use --influxdb_org.")
            sys.exit(1)

    logging.info(f"Starting candle ingestor script (Python) in {FLAGS.run_mode} mode...")

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    logging.info("Configuration:")
    # ... (logging of flags remains the same) ...
    logging.info(f"  Run Mode: {FLAGS.run_mode}")
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


    if FLAGS.run_mode == "wet":
        influx_manager_global = InfluxDBManager(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket,
        )
        if not influx_manager_global.get_client():
            logging.error("Failed to connect to InfluxDB (Manager). Exiting.")
            return 1
        
        timestamp_tracker_global = InfluxDBLastProcessedTracker(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket, # Assuming tracker uses the same bucket for its state
        )
        if not timestamp_tracker_global.client: # Check client directly after construction attempt
            logging.error("Failed to connect to InfluxDB (Timestamp Tracker). Exiting.")
            if influx_manager_global: influx_manager_global.close() # cleanup
            return 1
    else:
        logging.info("DRY RUN: Skipping InfluxDB connections.")
        influx_manager_global = None
        timestamp_tracker_global = None


    if shutdown_requested:
        logging.info("Shutdown requested before starting main processing.")
        if influx_manager_global: influx_manager_global.close()
        if timestamp_tracker_global: timestamp_tracker_global.close()
        sys.exit(0)

    tiingo_tickers = []
    if FLAGS.run_mode == "dry":
        logging.info("DRY RUN: Using dummy crypto symbols.")
        tiingo_tickers = ["btcusd-dry", "ethusd-dry"] # Suffix for clarity in dry run
    else:
        tiingo_tickers = get_top_n_crypto_symbols(
            FLAGS.cmc_api_key, FLAGS.top_n_cryptos
        )

    if not tiingo_tickers:
        logging.error("No symbols fetched. Exiting.")
        if influx_manager_global: influx_manager_global.close()
        if timestamp_tracker_global: timestamp_tracker_global.close()
        return 1
    logging.info(f"Target Tiingo tickers: {tiingo_tickers}")

    # This dictionary can still be used for dry run or if tracker isn't available,
    # but the tracker becomes the primary source of truth for 'wet' mode.
    last_processed_candle_timestamps = {}


    try:
        if FLAGS.backfill_start_date.lower() != "skip":
            # No need to pre-populate last_processed_candle_timestamps from tracker here for backfill,
            # run_backfill itself will query the tracker.
            if not shutdown_requested:
                run_backfill(
                    influx_manager=influx_manager_global,
                    timestamp_tracker=timestamp_tracker_global,
                    tiingo_tickers=tiingo_tickers,
                    tiingo_api_key=FLAGS.tiingo_api_key,
                    backfill_start_date_str=FLAGS.backfill_start_date,
                    candle_granularity_minutes=FLAGS.candle_granularity_minutes,
                    api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
                    last_backfilled_timestamps=last_processed_candle_timestamps, # Still pass for dry run compatibility
                    run_mode=FLAGS.run_mode,
                )
        else:
            logging.info(
                "Skipping historical backfill as per 'backfill_start_date' flag."
            )

        if not shutdown_requested : # Don't start polling if backfill (especially dry run) requested shutdown
            run_polling_loop(
                influx_manager=influx_manager_global,
                timestamp_tracker=timestamp_tracker_global,
                tiingo_tickers=tiingo_tickers,
                tiingo_api_key=FLAGS.tiingo_api_key,
                candle_granularity_minutes=FLAGS.candle_granularity_minutes,
                api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
                initial_catchup_days=FLAGS.polling_initial_catchup_days,
                last_processed_timestamps=last_processed_candle_timestamps, # Still pass for dry/resilience
                run_mode=FLAGS.run_mode,
            )

    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
    finally:
        logging.info(
            "Main process finished. Ensuring InfluxDB connections are closed if they were opened."
        )
        if influx_manager_global: # Check if it was initialized
            influx_manager_global.close()
        if timestamp_tracker_global: # Check if it was initialized
            timestamp_tracker_global.close()


    if shutdown_requested:
        logging.info("Exiting due to shutdown request.")
        sys.exit(0)

    return 0


if __name__ == "__main__":
    app.run(main)
    