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
    "InfluxDB Bucket for candles and state.", # Clarified bucket usage
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
    # last_backfilled_timestamps is now primarily for in-run tracking,
    # initial state comes from DB before this function is called.
    # It could be removed if all state is managed strictly via DB calls within the loop.
    # For now, let's assume it's pre-populated with DB state by the caller (main function).
    last_backfilled_timestamps: dict[str, int],
):
    logging.info("Starting historical candle backfill...")
    # Overall earliest start date from flags
    earliest_backfill_flag_dt = parse_backfill_start_date(backfill_start_date_str)
    # End date for historical is up to the start of the current UTC day (exclusive)
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

    for ticker in tiingo_tickers:
        current_run_max_ts_for_ticker = 0 # Tracks max timestamp *within this specific run_backfill execution*

        # Determine the actual start date for this specific ticker
        db_last_backfill_ts_ms = last_backfilled_timestamps.get(ticker) # Pre-populated from DB by main()

        if db_last_backfill_ts_ms and db_last_backfill_ts_ms > 0:
            dt_from_db_ts = datetime.fromtimestamp(db_last_backfill_ts_ms / 1000.0, timezone.utc)
            # Start fetching for the period *after* the last successfully recorded candle
            potential_next_start_from_db = dt_from_db_ts.replace(second=0, microsecond=0) + granularity_delta
            # current_ticker_start_dt is the later of the flag-defined start or the DB state
            current_ticker_start_dt = max(earliest_backfill_flag_dt, potential_next_start_from_db)
            logging.info(f"Resuming backfill for {ticker} from DB state, effective start: {current_ticker_start_dt.isoformat()}")
        else:
            # No DB state for this ticker, use the original start_date_dt from flags/parsing
            current_ticker_start_dt = earliest_backfill_flag_dt
            logging.info(f"Starting new backfill for {ticker} from flag-defined start: {current_ticker_start_dt.isoformat()}")


        if current_ticker_start_dt >= end_date_dt:
            logging.info(f"Ticker {ticker} already effectively backfilled up to or beyond target end date. Last known DB ts: {db_last_backfill_ts_ms}. Skipping.")
            continue

        logging.info(
            f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_date_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        chunk_start_dt = current_ticker_start_dt

        while chunk_start_dt < end_date_dt:
            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            chunk_end_dt = min(
                chunk_start_dt + timedelta(days=89), end_date_dt - timedelta(microseconds=1)
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
                written_count = influx_manager.write_candles_batch(historical_candles)
                if written_count > 0:
                    latest_ts_in_batch = historical_candles[-1]["timestamp_ms"]
                    current_run_max_ts_for_ticker = max(current_run_max_ts_for_ticker, latest_ts_in_batch)
                    # Update InfluxDB state immediately after successful batch write
                    influx_manager.update_last_processed_timestamp(ticker, "backfill", latest_ts_in_batch)
                    logging.info(f"  Successfully wrote {written_count} candles. Updated InfluxDB backfill state for {ticker} to {latest_ts_in_batch}")
                else:
                    logging.warning(f"  Write_candles_batch reported 0 candles written for {ticker} despite having data. DB State not updated for this batch.")
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

        # Update the passed-in dict with the latest timestamp from this specific run (optional, as DB is primary)
        if current_run_max_ts_for_ticker > 0:
             last_backfilled_timestamps[ticker] = max(last_backfilled_timestamps.get(ticker, 0), current_run_max_ts_for_ticker)

        logging.info(
            f"Finished backfill for {ticker}. Check InfluxDB for authoritative state."
        )
    logging.info("Historical candle backfill completed.")


def run_polling_loop(
    influx_manager: InfluxDBManager,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catchup_days: int,
    # This dict is now primarily an in-memory cache, initialized from DB.
    last_processed_timestamps: dict[str, int],
):
    logging.info("Starting real-time candle polling loop...")
    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)

    # Initialize last_processed_timestamps for tickers if not already set (e.g. by backfill stage)
    logging.info("Initializing polling timestamps from InfluxDB or defaults...")
    for ticker_symbol in tiingo_tickers:
        if ticker_symbol not in last_processed_timestamps or last_processed_timestamps.get(ticker_symbol, 0) == 0:
            polling_state_ts_ms = influx_manager.get_last_processed_timestamp(ticker_symbol, "polling")
            if polling_state_ts_ms:
                last_processed_timestamps[ticker_symbol] = polling_state_ts_ms
                logging.info(f"Found last polling state for {ticker_symbol}: {datetime.fromtimestamp(polling_state_ts_ms / 1000.0, timezone.utc).isoformat()}")
            else:
                # If no polling state, check if backfill state exists (already in last_processed_timestamps from main)
                backfill_state_ts_ms = last_processed_timestamps.get(ticker_symbol) # From main's pre-population
                if backfill_state_ts_ms:
                    # No specific polling state, but backfill state exists. We can use this.
                    # The value is already in last_processed_timestamps, so no need to set it again.
                    logging.info(f"No polling state for {ticker_symbol}, using last backfill state: {datetime.fromtimestamp(backfill_state_ts_ms / 1000.0, timezone.utc).isoformat()}")
                else:
                    # Fallback to default catchup if no state found at all
                    now_utc_for_init = datetime.now(timezone.utc)
                    default_catchup_start_dt = now_utc_for_init - timedelta(days=initial_catchup_days)
                    default_catchup_start_minute = (
                        (default_catchup_start_dt.minute // candle_granularity_minutes)
                        * candle_granularity_minutes
                    )
                    default_catchup_start_dt_aligned = default_catchup_start_dt.replace(
                        minute=default_catchup_start_minute, second=0, microsecond=0
                    )
                    default_catchup_start_ms = int(default_catchup_start_dt_aligned.timestamp() * 1000)
                    last_processed_timestamps[ticker_symbol] = default_catchup_start_ms
                    logging.info(
                        f"No backfill or polling state for {ticker_symbol}. "
                        f"Setting polling start from approx {initial_catchup_days} days ago: {default_catchup_start_dt_aligned.isoformat()}"
                    )
        else: # Timestamp for this ticker was already present (likely from backfill state propagation)
             logging.info(f"Using pre-existing/backfill timestamp for {ticker_symbol} for polling start: {datetime.fromtimestamp(last_processed_timestamps[ticker_symbol] / 1000.0, timezone.utc).isoformat()}")


    try:
        while True:
            loop_start_time = time.monotonic()
            current_cycle_time_utc = datetime.now(timezone.utc)
            logging.info(f"Starting polling cycle at {current_cycle_time_utc.isoformat()}")

            for ticker in tiingo_tickers:
                try:
                    last_ts_ms = last_processed_timestamps.get(ticker)
                    if last_ts_ms is None: # Should have been initialized above
                        logging.error(f"CRITICAL: Missing last_ts_ms for {ticker} at start of polling iteration. This should not happen.")
                        # As a safeguard, re-initialize to a very safe default to avoid infinite loops on bad data
                        last_ts_ms = (datetime.now(timezone.utc) - timedelta(days=initial_catchup_days)).timestamp() * 1000
                        last_processed_timestamps[ticker] = int(last_ts_ms)

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
                    # Tiingo's /prices endpoint end date for intraday seems to be exclusive for the day part if time not specified.
                    # For polling, we want up to the most recently *fully closed* candle period.
                    query_end_dt_utc = target_latest_closed_candle_start_dt_utc # Inclusive start of the last *closed* candle period.
                                                                               # Tiingo API usually needs end date to be "up to"
                                                                               # For safety, let's query up to current time to catch late data, then filter.
                    effective_query_end_dt_utc = current_cycle_time_utc


                    if query_start_dt_utc >= effective_query_end_dt_utc: # query_end_dt_utc changed to current_cycle_time_utc
                        logging.debug(f"Query start time {query_start_dt_utc.isoformat()} is not before effective query end {effective_query_end_dt_utc.isoformat()} for {ticker}. Skipping API call.")
                        continue

                    if candle_granularity_minutes >= 1440: # Daily
                        query_start_str = query_start_dt_utc.strftime("%Y-%m-%d")
                        query_end_str = effective_query_end_dt_utc.strftime("%Y-%m-%d")
                    else: # Intraday
                        query_start_str = query_start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                        query_end_str = effective_query_end_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")


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
                            # Ensure candle start is after last processed, and candle period is fully closed
                            candle_end_ts_ms = candle_ts_ms + granularity_delta.total_seconds() * 1000
                            if candle_ts_ms > last_ts_ms and candle_end_ts_ms <= current_cycle_time_utc.timestamp() * 1000:
                                new_candles_to_write.append(c)

                        new_candles_to_write.sort(key=lambda c: c["timestamp_ms"])

                        if new_candles_to_write:
                            logging.info(f"Fetched {len(new_candles_to_write)} new, closed candle(s) for {ticker} via polling.")
                            written_count = influx_manager.write_candles_batch(new_candles_to_write)
                            if written_count > 0:
                                latest_polled_ts_ms = new_candles_to_write[-1]["timestamp_ms"]
                                last_processed_timestamps[ticker] = latest_polled_ts_ms # Update in-memory dict
                                influx_manager.update_last_processed_timestamp(ticker, "polling", latest_polled_ts_ms) # Update DB state
                                logging.info(f"  Successfully wrote {written_count} candles. Updated InfluxDB polling state for {ticker} to {latest_polled_ts_ms}")
                            else:
                                logging.warning(f"  Polling write_candles_batch reported 0 candles written for {ticker}. DB State not updated for this batch.")
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
        logging.info("Polling loop interrupted by user.")
    finally:
        logging.info("Polling loop finished.")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)
    logging.info("Starting candle ingestor script (Python)...")
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

    # This dictionary will store the last processed timestamp (from DB or this run)
    # for each ticker, primarily for backfill state.
    # Polling loop will manage its own state more directly from DB first.
    last_processed_candle_timestamps = {}

    try:
        if FLAGS.backfill_start_date.lower() != "skip":
            logging.info("Attempting to pre-populate backfill states from InfluxDB...")
            for ticker_symbol in tiingo_tickers:
                db_state_ts_ms = influx_manager.get_last_processed_timestamp(ticker_symbol, "backfill")
                if db_state_ts_ms:
                    last_processed_candle_timestamps[ticker_symbol] = db_state_ts_ms
                    logging.info(f"  Pre-populated backfill state for {ticker_symbol}: {datetime.fromtimestamp(db_state_ts_ms / 1000.0, timezone.utc).isoformat()}")
                else:
                    logging.info(f"  No prior backfill state found in DB for {ticker_symbol}.")

            run_backfill(
                influx_manager,
                tiingo_tickers,
                FLAGS.tiingo_api_key,
                FLAGS.backfill_start_date,
                FLAGS.candle_granularity_minutes,
                FLAGS.tiingo_api_call_delay_seconds,
                last_processed_candle_timestamps, # Pass the pre-populated map
            )
        else:
            logging.info("Skipping historical backfill as per 'backfill_start_date' flag.")
            # If skipping backfill, we still might want to populate last_processed_candle_timestamps
            # from DB in case there was a partial backfill before "skip" was set.
            # Or, rely on polling loop's initialization to pick up backfill state if it exists.
            # For clarity, if backfill is skipped, we assume polling will handle init from scratch or existing state.


        # The last_processed_candle_timestamps dict now contains the most recent backfill timestamps
        # (either from DB before run_backfill or updated by run_backfill itself).
        # run_polling_loop will use this as a fallback if no specific "polling" state is found.
        run_polling_loop(
            influx_manager,
            tiingo_tickers,
            FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds,
            FLAGS.polling_initial_catchup_days,
            last_processed_candle_timestamps, # Pass the potentially populated/updated map
        )

    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
    finally:
        logging.info("Main process finished. Closing InfluxDB connection.")
        influx_manager.close()

    return 0


if __name__ == "__main__":
    app.run(main)
