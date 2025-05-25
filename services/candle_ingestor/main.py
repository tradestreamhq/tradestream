import os
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
    "Delay in seconds between Tiingo API calls for different tickers/chunks during processing.",
)
flags.DEFINE_integer(
    "catch_up_initial_days",  # Renamed from polling_initial_catchup_days
    7,
    "How many days back to check for initial catch-up if no prior state (backfill or catch-up) is found.",
)

# Run Mode Flag
flags.DEFINE_enum(
    "run_mode",
    "wet",
    ["wet", "dry"],
    "Run mode for the ingestor: 'wet' for live data, 'dry' for simulated data.",
)


def run_backfill(
    influx_manager: InfluxDBManager | None,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    backfill_start_date_str: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    last_processed_timestamps: dict[str, int],  # Combined state
    run_mode: str,
):
    logging.info("Starting historical candle backfill...")
    if run_mode == "dry":
        logging.info("DRY RUN: Backfill will use dummy data and limited iterations.")

    earliest_backfill_flag_dt = parse_backfill_start_date(backfill_start_date_str)
    # Backfill up to the beginning of the current day (UTC)
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

    for ticker in tiingo_tickers:
        if run_mode == "dry" and dry_run_tickers_processed >= max_dry_run_tickers:
            logging.info(
                f"DRY RUN: Reached max tickers for backfill ({max_dry_run_tickers})."
            )
            break  # For dry run, stop after processing max_dry_run_tickers
        current_run_max_ts_for_ticker = 0
        db_last_processed_ts_ms = None
        if influx_manager:
            db_last_processed_ts_ms = influx_manager.get_last_processed_timestamp(
                ticker, "backfill"  # Still check specific backfill state
            )
        else:  # Dry run or no influx
            db_last_processed_ts_ms = last_processed_timestamps.get(ticker)

        if db_last_processed_ts_ms and db_last_processed_ts_ms > 0:
            dt_from_db_ts = datetime.fromtimestamp(
                db_last_processed_ts_ms / 1000.0, timezone.utc
            )
            # Start backfill from the beginning of the next granularity period
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
                f"Ticker {ticker} already effectively backfilled up to or beyond target end date. Last known DB ts: {db_last_processed_ts_ms}. Skipping."
            )
            if run_mode == "dry":
                dry_run_tickers_processed += 1
            continue

        logging.info(
            f"Backfilling {ticker} from {current_ticker_start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_date_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        chunk_start_dt = current_ticker_start_dt
        dry_run_chunks_processed = 0

        while chunk_start_dt < end_date_dt:
            if (
                run_mode == "dry"
                and dry_run_chunks_processed >= max_dry_run_chunks_per_ticker
            ):
                logging.info(
                    f"DRY RUN: Reached max chunks for ticker {ticker} ({max_dry_run_chunks_per_ticker})."
                )
                break

            chunk_start_str = chunk_start_dt.strftime("%Y-%m-%d")
            # Ensure chunk_end_dt doesn't go beyond the overall end_date_dt
            chunk_end_dt = min(
                chunk_start_dt + timedelta(days=89),  # Tiingo's recommended max chunk
                end_date_dt
                - timedelta(microseconds=1),  # Ensure it's strictly before end_date_dt
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
                        "open": 1.0,
                        "high": 1.1,
                        "low": 0.9,
                        "close": 1.05,
                        "volume": 100.0,
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
                    if influx_manager:
                        influx_manager.update_last_processed_timestamp(
                            ticker, "backfill", latest_ts_in_batch
                        )
                    last_processed_timestamps[ticker] = (
                        latest_ts_in_batch  # Update shared state
                    )
                    logging.info(
                        f"  Successfully processed {len(historical_candles)} candles. Updated backfill state for {ticker} to {latest_ts_in_batch}"
                    )
                else:
                    logging.warning(
                        f"  Write_candles_batch reported 0 candles written for {ticker} despite having data. DB State not updated for this batch."
                    )
            else:
                logging.info(
                    f"  No data in chunk for {ticker}: {chunk_start_str} to {chunk_end_str}"
                )

            dry_run_chunks_processed += 1
            chunk_start_dt = chunk_end_dt + timedelta(
                days=1
            )  # Move to the next day for the next chunk's start
            if (
                chunk_start_dt < end_date_dt
                and len(tiingo_tickers) > 1
                and run_mode == "wet"
            ):
                logging.info(
                    f"Waiting {api_call_delay_seconds}s before next API call/chunk for {ticker}..."
                )
                time.sleep(api_call_delay_seconds)

        dry_run_tickers_processed += 1
        if current_run_max_ts_for_ticker > 0:
            # Ensure the overall last processed timestamp is updated
            last_processed_timestamps[ticker] = max(
                last_processed_timestamps.get(ticker, 0), current_run_max_ts_for_ticker
            )
        logging.info(
            f"Finished backfill for {ticker}. Check InfluxDB for authoritative state."
        )

    if run_mode == "dry":
        logging.info("DRY RUN: Backfill simulation complete.")
    else:
        logging.info("Historical candle backfill completed.")


def run_catch_up(
    influx_manager: InfluxDBManager | None,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catch_up_days: int,
    last_processed_timestamps: dict[str, int],  # Shared state
    run_mode: str,
):
    logging.info("Starting catch-up candle processing...")
    if run_mode == "dry":
        logging.info("DRY RUN: Catch-up will use dummy data and limited iterations.")

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    max_dry_run_tickers = 1
    dry_run_tickers_processed = 0

    for ticker in tiingo_tickers:
        if run_mode == "dry" and dry_run_tickers_processed >= max_dry_run_tickers:
            logging.info(
                f"DRY RUN: Reached max tickers for catch-up ({max_dry_run_tickers})."
            )
            break

        last_known_ts_ms = last_processed_timestamps.get(ticker)

        # If no state from backfill (or previous catch-up), try DB for "catch_up" state
        if not last_known_ts_ms and influx_manager:
            last_known_ts_ms = influx_manager.get_last_processed_timestamp(
                ticker, "catch_up"
            )

        # If still no state, use initial_catch_up_days
        if not last_known_ts_ms:
            catch_up_start_dt_utc = datetime.now(timezone.utc) - timedelta(
                days=initial_catch_up_days
            )
            # Align to the start of the granularity period
            aligned_minute = (
                catch_up_start_dt_utc.minute // candle_granularity_minutes
            ) * candle_granularity_minutes
            start_dt_utc = catch_up_start_dt_utc.replace(
                minute=aligned_minute, second=0, microsecond=0
            )
            logging.info(
                f"No prior state for {ticker}. Starting catch-up from approx {initial_catch_up_days} days ago: {start_dt_utc.isoformat()}"
            )
        else:
            # Start from the next period after the last known timestamp
            start_dt_utc = (
                datetime.fromtimestamp(last_known_ts_ms / 1000.0, timezone.utc)
                + granularity_delta
            )
            logging.info(
                f"Resuming catch-up for {ticker} from {start_dt_utc.isoformat()}"
            )

        end_dt_utc = datetime.now(timezone.utc)

        if start_dt_utc >= end_dt_utc:
            logging.info(
                f"Data for {ticker} is already up to date (Start: {start_dt_utc}, End: {end_dt_utc}). Skipping catch-up."
            )
            if run_mode == "dry":
                dry_run_tickers_processed += 1
            continue

        # Format for Tiingo API (handles daily vs intraday)
        if candle_granularity_minutes >= 1440:  # Daily or more
            start_date_str = start_dt_utc.strftime("%Y-%m-%d")
            end_date_str = end_dt_utc.strftime("%Y-%m-%d")
        else:  # Intraday
            start_date_str = start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
            end_date_str = end_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")

        fetched_candles = []
        if run_mode == "dry":
            logging.info(
                f"DRY RUN: Simulating Tiingo API call for {ticker} (catch-up): {start_date_str} to {end_date_str}"
            )
            dummy_ts_ms = int(start_dt_utc.timestamp() * 1000)
            fetched_candles = [
                {
                    "timestamp_ms": dummy_ts_ms,
                    "open": 3.0,
                    "high": 3.1,
                    "low": 2.9,
                    "close": 3.05,
                    "volume": 70.0,
                    "currency_pair": ticker,
                }
            ]
        else:
            logging.info(
                f"Catching up {ticker} from {start_date_str} to {end_date_str}"
            )
            fetched_candles = get_historical_candles_tiingo(
                tiingo_api_key, ticker, start_date_str, end_date_str, resample_freq
            )

        if fetched_candles:
            fetched_candles.sort(key=lambda c: c["timestamp_ms"])
            # Filter out candles that might be before or exactly at our start_dt_utc timestamp due to API behavior
            valid_candles_to_write = [
                c
                for c in fetched_candles
                if c["timestamp_ms"] >= int(start_dt_utc.timestamp() * 1000)
            ]

            if valid_candles_to_write:
                written_count = 0
                if influx_manager:
                    written_count = influx_manager.write_candles_batch(
                        valid_candles_to_write
                    )

                if written_count > 0 or run_mode == "dry":
                    latest_ts_in_batch = valid_candles_to_write[-1]["timestamp_ms"]
                    last_processed_timestamps[ticker] = (
                        latest_ts_in_batch  # Update shared state
                    )
                    if influx_manager:
                        influx_manager.update_last_processed_timestamp(
                            ticker, "catch_up", latest_ts_in_batch
                        )
                    logging.info(
                        f"  Successfully processed {len(valid_candles_to_write)} candles for {ticker} (catch-up). Updated state to {latest_ts_in_batch}"
                    )
                else:
                    logging.warning(
                        f"  Catch-up write_candles_batch reported 0 candles written for {ticker}. DB State not updated."
                    )
            else:
                logging.info(
                    f"No new, valid candles found for {ticker} in catch-up range after filtering."
                )
        else:
            logging.info(
                f"Catch-up returned no data for {ticker} for period starting {start_date_str}"
            )

        if run_mode == "dry":
            dry_run_tickers_processed += 1

        if (
            len(tiingo_tickers) > 1
            and ticker != tiingo_tickers[-1]
            and run_mode == "wet"
        ):
            logging.info(
                f"Waiting {api_call_delay_seconds}s before next API call for catch-up..."
            )
            time.sleep(api_call_delay_seconds)

    logging.info("Catch-up candle processing completed.")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    if FLAGS.run_mode == "wet":
        if not FLAGS.cmc_api_key:
            logging.error("CMC_API_KEY is required. Set via env var or flag.")
            sys.exit(1)
        if not FLAGS.tiingo_api_key:
            logging.error("TIINGO_API_KEY is required. Set via env var or flag.")
            sys.exit(1)
        if not FLAGS.influxdb_token:
            logging.error("INFLUXDB_TOKEN is required. Set via env var or flag.")
            sys.exit(1)
        if not FLAGS.influxdb_org:
            logging.error("INFLUXDB_ORG is required. Set via env var or flag.")
            sys.exit(1)

    logging.info(
        f"Starting candle ingestor script (Python) in {FLAGS.run_mode} mode..."
    )
    logging.info("Configuration:")
    # Log important flags
    for flag_name in FLAGS:
        logging.info(f"  {flag_name}: {FLAGS[flag_name].value}")

    influx_manager = None
    if FLAGS.run_mode == "wet":
        influx_manager = InfluxDBManager(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket,
        )
        if not influx_manager.get_client():
            logging.error("Failed to connect to InfluxDB. Exiting.")
            sys.exit(1)  # Critical error, exit
    else:
        logging.info("DRY RUN: Skipping InfluxDB connection.")

    tiingo_tickers = []
    if FLAGS.run_mode == "dry":
        logging.info("DRY RUN: Using dummy crypto symbols.")
        tiingo_tickers = ["btcusd-dry", "ethusd-dry"]  # Limit for dry run
    else:
        tiingo_tickers = get_top_n_crypto_symbols(
            FLAGS.cmc_api_key, FLAGS.top_n_cryptos
        )

    if not tiingo_tickers:
        logging.error("No symbols fetched. Exiting.")
        if influx_manager:
            influx_manager.close()
        sys.exit(1)
    logging.info(f"Target Tiingo tickers: {tiingo_tickers}")

    # This dictionary will hold the latest processed timestamp for each ticker,
    # shared between backfill and catch-up.
    last_processed_candle_timestamps = {}

    try:
        if FLAGS.backfill_start_date.lower() != "skip":
            run_backfill(
                influx_manager=influx_manager,
                tiingo_tickers=tiingo_tickers,
                tiingo_api_key=FLAGS.tiingo_api_key,
                backfill_start_date_str=FLAGS.backfill_start_date,
                candle_granularity_minutes=FLAGS.candle_granularity_minutes,
                api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
                last_processed_timestamps=last_processed_candle_timestamps,
                run_mode=FLAGS.run_mode,
            )
        else:
            logging.info(
                "Skipping historical backfill as per 'backfill_start_date' flag."
            )
            # If skipping backfill, we still need to initialize last_processed_candle_timestamps
            # for the catch-up phase, either from "catch_up" state or default.
            if FLAGS.run_mode == "wet" and influx_manager:
                for ticker in tiingo_tickers:
                    ts = influx_manager.get_last_processed_timestamp(ticker, "catch_up")
                    if ts:
                        last_processed_candle_timestamps[ticker] = ts
                    else:  # Also check backfill state if skipping backfill run but state might exist
                        ts_backfill = influx_manager.get_last_processed_timestamp(
                            ticker, "backfill"
                        )
                        if ts_backfill:
                            last_processed_candle_timestamps[ticker] = ts_backfill

        # Always run catch-up after backfill (or if backfill was skipped)
        run_catch_up(
            influx_manager=influx_manager,
            tiingo_tickers=tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=last_processed_candle_timestamps,
            run_mode=FLAGS.run_mode,
        )

    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
        if influx_manager:  # Ensure client is closed on error too
            influx_manager.close()
        sys.exit(1)  # Indicate failure
    finally:
        logging.info(
            "Main processing finished. Ensuring InfluxDB connection is closed if opened."
        )
        if influx_manager and influx_manager.get_client():
            influx_manager.close()

    logging.info("Candle ingestor script completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    app.run(main)
