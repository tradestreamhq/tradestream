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
    last_backfilled_timestamps: dict[str, int],
):
    logging.info("Starting historical candle backfill...")
    start_date_dt = parse_backfill_start_date(backfill_start_date_str)
    # End date for historical is up to the start of the current UTC day (exclusive)
    end_date_dt = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if start_date_dt >= end_date_dt:
        logging.info(
            f"Backfill start date ({start_date_dt.strftime('%Y-%m-%d')}) is not before "
            f"effective end date ({end_date_dt.strftime('%Y-%m-%d')}). Skipping backfill."
        )
        return

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)

    for ticker in tiingo_tickers:
        # TODO (PR6): Query InfluxDB for the last known candle for this ticker
        # and adjust current_ticker_start_dt if it's more recent than start_date_dt.
        current_ticker_start_dt = start_date_dt
        max_timestamp_for_ticker_in_backfill = (
            last_backfilled_timestamps.get(ticker, 0)
        ) # Use existing if available

        # Adjust start if already partially backfilled and that point is after calculated start_date_dt
        if max_timestamp_for_ticker_in_backfill > 0:
            dt_from_ts = datetime.fromtimestamp(max_timestamp_for_ticker_in_backfill / 1000.0, timezone.utc)
            # Start from the next candle interval
            potential_next_start = dt_from_ts.replace(second=0, microsecond=0) + timedelta(minutes=candle_granularity_minutes)
            current_ticker_start_dt = max(current_ticker_start_dt, potential_next_start)
        
        if current_ticker_start_dt >= end_date_dt:
            logging.info(f"Ticker {ticker} already backfilled up to or beyond target end date. Last backfilled ts: {max_timestamp_for_ticker_in_backfill}. Skipping.")
            continue

        logging.info(
            f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_date_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        chunk_start_dt = current_ticker_start_dt
        
        while chunk_start_dt < end_date_dt:
            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            # Fetch up to 90 days or until end_date_dt, whichever is sooner
            chunk_end_dt = min(
                chunk_start_dt + timedelta(days=89), end_date_dt - timedelta(microseconds=1) # Ensure end is inclusive for daily, and not overlapping for intraday
            )
            chunk_end_str = chunk_end_dt.strftime("%Y-%m-%d")

            logging.info(
                f"  Fetching chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
            )
            historical_candles = get_historical_candles_tiingo(
                tiingo_api_key,
                ticker,
                chunk_start_str, # Tiingo /prices takes date strings for historical
                chunk_end_str,
                resample_freq,
            )
            if historical_candles:
                historical_candles.sort(key=lambda c: c["timestamp_ms"])
                influx_manager.write_candles_batch(historical_candles)
                if historical_candles: # update max_timestamp
                    max_timestamp_for_ticker_in_backfill = max(
                        max_timestamp_for_ticker_in_backfill,
                        historical_candles[-1]["timestamp_ms"],
                    )
            else:
                logging.info(
                    f"  No data in chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
                )

            chunk_start_dt = chunk_end_dt + timedelta(days=1) # Next chunk starts the following day
            if chunk_start_dt < end_date_dt and len(tiingo_tickers) > 1: # Avoid sleep if only one ticker or last chunk
                logging.info(
                    f"Waiting {api_call_delay_seconds}s before next API call/chunk for {ticker}..."
                )
                time.sleep(api_call_delay_seconds)
        
        if max_timestamp_for_ticker_in_backfill > 0:
            last_backfilled_timestamps[ticker] = max_timestamp_for_ticker_in_backfill
        logging.info(
            f"Finished backfill for {ticker}. Last backfilled ts: {last_backfilled_timestamps.get(ticker)}"
        )
    logging.info("Historical candle backfill completed.")


def run_polling_loop(
    influx_manager: InfluxDBManager,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catchup_days: int,
    last_processed_timestamps: dict[str, int],
    test_max_cycles: int | None = None, # New parameter for testing
):
    logging.info("Starting real-time candle polling loop...")
    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)

    # Initialize last_processed_timestamps for tickers not set by backfill
    now_utc_for_init = datetime.now(timezone.utc)
    default_catchup_start_dt = now_utc_for_init - timedelta(days=initial_catchup_days)
    # Align to the start of its candle period
    default_catchup_start_minute = (default_catchup_start_dt.minute // candle_granularity_minutes) * candle_granularity_minutes
    default_catchup_start_dt_aligned = default_catchup_start_dt.replace(minute=default_catchup_start_minute, second=0, microsecond=0)
    default_catchup_start_ms = int(default_catchup_start_dt_aligned.timestamp() * 1000)


    for ticker in tiingo_tickers:
        if ticker not in last_processed_timestamps or last_processed_timestamps.get(ticker, 0) == 0:
            # TODO (PR6): Query InfluxDB for the true last point for this ticker.
            # For now, if no backfill data, or if backfill resulted in 0, start from catchup.
            logging.info(
                f"No valid backfill timestamp for {ticker}, "
                f"setting polling start from approx {initial_catchup_days} days ago: {default_catchup_start_dt_aligned.isoformat()}"
            )
            last_processed_timestamps[ticker] = default_catchup_start_ms
    
    cycles_run = 0
    try:
        while True:
            if test_max_cycles is not None and cycles_run >= test_max_cycles:
                logging.info(f"Reached test_max_cycles ({test_max_cycles}). Exiting polling loop.")
                break
            cycles_run += 1

            loop_start_time = time.monotonic()
            current_cycle_time_utc = datetime.now(timezone.utc)
            logging.info(
                f"Starting polling cycle #{cycles_run} at {current_cycle_time_utc.isoformat()}"
            )

            for ticker in tiingo_tickers:
                try:
                    last_ts_ms = last_processed_timestamps.get(ticker)
                    if last_ts_ms is None: # Should have been initialized above
                        logging.error(f"CRITICAL: Missing last_ts_ms for {ticker}. Re-initializing with default catchup.")
                        last_ts_ms = default_catchup_start_ms
                        last_processed_timestamps[ticker] = last_ts_ms
                    
                    last_known_candle_start_dt_utc = datetime.fromtimestamp(last_ts_ms / 1000.0, timezone.utc)

                    # Determine the start of the most recently *fully closed* candle period
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

                    # Query from the start of the *next expected* candle period
                    query_start_dt_utc = last_known_candle_start_dt_utc + granularity_delta
                    # Query up to the end of the `target_latest_closed_candle_start_dt_utc` period.
                    query_end_dt_utc = target_latest_closed_candle_start_dt_utc + granularity_delta - timedelta(seconds=1)

                    if query_start_dt_utc > current_cycle_time_utc:
                        logging.debug(f"Query start time {query_start_dt_utc.isoformat()} is in the future for {ticker}. Skipping.")
                        continue
                    
                    query_end_dt_utc = min(query_end_dt_utc, current_cycle_time_utc) # Don't query beyond current time

                    if query_start_dt_utc > query_end_dt_utc :
                        logging.debug(f"Calculated query start {query_start_dt_utc.isoformat()} is after query end {query_end_dt_utc.isoformat()} for {ticker}. Skipping API call.")
                        continue

                    # Tiingo uses YYYY-MM-DD for daily, YYYY-MM-DDTHH:MM:SS for intraday startDate/endDate for /prices
                    if candle_granularity_minutes >= 1440: # Daily
                        query_start_str = query_start_dt_utc.strftime("%Y-%m-%d")
                        query_end_str = query_end_dt_utc.strftime("%Y-%m-%d")
                    else: # Intraday
                        query_start_str = query_start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                        query_end_str = query_end_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
                    
                    logging.info(
                        f"Polling for {ticker} from {query_start_str} to {query_end_str}"
                    )
                    
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
                            logging.info(
                                f"Fetched {len(new_candles_to_write)} new candle(s) for {ticker} via polling."
                            )
                            influx_manager.write_candles_batch(new_candles_to_write)
                            last_processed_timestamps[ticker] = new_candles_to_write[-1]["timestamp_ms"]
                        else:
                            logging.info(
                                f"No new, fully closed candles found for {ticker} in polled range after filtering."
                            )
                    else:
                        logging.info(
                            f"Polling returned no data for {ticker} for period starting {query_start_str}"
                        )
                    
                    if len(tiingo_tickers) > 1:
                        time.sleep(api_call_delay_seconds)

                except Exception as e:
                    logging.exception(f"Error polling for ticker {ticker}: {e}")

            loop_duration = time.monotonic() - loop_start_time
            sleep_time = (candle_granularity_minutes * 60) - loop_duration
            if sleep_time > 0:
                logging.info(
                    f"Polling cycle #{cycles_run} finished in {loop_duration:.2f}s. Sleeping for {sleep_time:.2f}s."
                )
                time.sleep(sleep_time)
            else:
                logging.warning(
                    f"Polling cycle #{cycles_run} duration ({loop_duration:.2f}s) "
                    f"exceeded granularity ({candle_granularity_minutes*60}s). "
                    f"Running next cycle immediately."
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
                last_processed_candle_timestamps,
            )
        else:
            logging.info("Skipping historical backfill as per 'backfill_start_date' flag.")
            # Initialize timestamps for polling if backfill is skipped
            # This init is now handled at the start of run_polling_loop if needed

        run_polling_loop(
            influx_manager,
            tiingo_tickers,
            FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds,
            FLAGS.polling_initial_catchup_days,
            last_processed_candle_timestamps, # Pass the potentially populated map
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
