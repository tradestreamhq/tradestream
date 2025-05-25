import os
import sys
import time
from datetime import datetime, timedelta, timezone
import json  # Added for potential parsing if Redis stored raw JSON string for list

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
from shared.cryptoclient.redis_crypto_client import (
    RedisCryptoClient,
)  # Import Redis Client
import redis  # Import for redis exceptions

FLAGS = flags.FLAGS

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

# Redis Flags
default_redis_host = os.getenv(
    "REDIS_HOST", "localhost"
)  # Default will be overridden by Helm in k8s
flags.DEFINE_string("redis_host", default_redis_host, "Redis host.")
default_redis_port = int(os.getenv("REDIS_PORT", "6379"))
flags.DEFINE_integer("redis_port", default_redis_port, "Redis port.")
flags.DEFINE_string(
    "redis_password", os.getenv("REDIS_PASSWORD"), "Redis password (if any)."
)
default_redis_key_crypto_symbols = os.getenv(
    "REDIS_KEY_CRYPTO_SYMBOLS", "top_cryptocurrencies"
)
flags.DEFINE_string(
    "redis_key_crypto_symbols",
    default_redis_key_crypto_symbols,
    "Redis key to fetch the list of top cryptocurrency symbols.",
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
    "catch_up_initial_days",
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

DRY_RUN_PROCESSING_LIMIT_DEFAULT = 2  # Default limit for symbols in dry run


def run_backfill(
    influx_manager: InfluxDBManager | None,
    tiingo_tickers: list[str],
    tiingo_api_key: str,
    backfill_start_date_str: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    last_processed_timestamps: dict[str, int],
    run_mode: str,
    dry_run_processing_limit: int | None,
):
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
    effective_max_dry_run_tickers = (
        dry_run_processing_limit
        if run_mode == "dry" and dry_run_processing_limit is not None
        else len(tiingo_tickers)  # Process all tickers if not dry or no limit
    )
    max_dry_run_chunks_per_ticker = 1

    for ticker_index, ticker in enumerate(tiingo_tickers):
        if (
            run_mode == "dry"
            and dry_run_tickers_processed >= effective_max_dry_run_tickers
        ):
            logging.info(
                f"DRY RUN: Reached max tickers for backfill ({effective_max_dry_run_tickers})."
            )
            break
        current_run_max_ts_for_ticker = 0
        db_last_processed_ts_ms = None
        if influx_manager:
            db_last_processed_ts_ms = influx_manager.get_last_processed_timestamp(
                ticker, "backfill"
            )
        else:
            db_last_processed_ts_ms = last_processed_timestamps.get(ticker)

        if db_last_processed_ts_ms and db_last_processed_ts_ms > 0:
            dt_from_db_ts = datetime.fromtimestamp(
                db_last_processed_ts_ms / 1000.0, timezone.utc
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
            chunk_end_dt_candidate = chunk_start_dt + timedelta(days=89)
            chunk_end_dt = min(
                chunk_end_dt_candidate, end_date_dt - timedelta(microseconds=1)
            )

            if chunk_end_dt < chunk_start_dt:
                chunk_end_dt = end_date_dt - timedelta(microseconds=1)

            chunk_end_str = chunk_end_dt.strftime("%Y-%m-%d")

            historical_candles = []
            if run_mode == "dry":
                logging.info(
                    f"DRY RUN: Simulating Tiingo API call for {ticker} (backfill): {chunk_start_str} to {chunk_end_str}"
                )
                if candle_granularity_minutes >= 1440:
                    aligned_chunk_start_dt = chunk_start_dt.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                elif candle_granularity_minutes >= 60:
                    aligned_chunk_start_dt = chunk_start_dt.replace(
                        minute=0, second=0, microsecond=0
                    )
                else:
                    aligned_minute = (
                        chunk_start_dt.minute // candle_granularity_minutes
                    ) * candle_granularity_minutes
                    aligned_chunk_start_dt = chunk_start_dt.replace(
                        minute=aligned_minute, second=0, microsecond=0
                    )

                dummy_ts_ms = int(aligned_chunk_start_dt.timestamp() * 1000)
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
                    last_processed_timestamps[ticker] = latest_ts_in_batch
                    logging.info(
                        f"   Successfully processed {len(historical_candles)} candles. Updated backfill state for {ticker} to {latest_ts_in_batch}"
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
            chunk_start_dt = chunk_end_dt + timedelta(days=1)
            if (
                chunk_start_dt < end_date_dt
                and ticker_index
                < len(tiingo_tickers) - 1  # Only delay if not the last ticker overall
                and run_mode == "wet"
            ):
                logging.info(
                    f"Waiting {api_call_delay_seconds}s before next API call/chunk for {ticker}..."
                )
                time.sleep(api_call_delay_seconds)

        dry_run_tickers_processed += 1

        if current_run_max_ts_for_ticker > 0:
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
    last_processed_timestamps: dict[str, int],
    run_mode: str,
    dry_run_processing_limit: int | None,
):
    logging.info("Starting catch-up candle processing...")
    if run_mode == "dry":
        logging.info("DRY RUN: Catch-up will use dummy data and limited iterations.")

    resample_freq = get_tiingo_resample_freq(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    effective_max_dry_run_tickers = (
        dry_run_processing_limit
        if run_mode == "dry" and dry_run_processing_limit is not None
        else len(tiingo_tickers)  # Process all tickers if not dry or no limit
    )
    dry_run_tickers_processed = 0

    for ticker_index, ticker in enumerate(tiingo_tickers):
        if (
            run_mode == "dry"
            and dry_run_tickers_processed >= effective_max_dry_run_tickers
        ):
            logging.info(
                f"DRY RUN: Reached max tickers for catch-up ({effective_max_dry_run_tickers})."
            )
            break

        last_known_ts_ms = last_processed_timestamps.get(ticker)

        if not last_known_ts_ms and influx_manager:
            last_known_ts_ms = influx_manager.get_last_processed_timestamp(
                ticker, "catch_up"
            )

        if not last_known_ts_ms and influx_manager:
            last_known_ts_ms = influx_manager.get_last_processed_timestamp(
                ticker, "backfill"
            )

        if not last_known_ts_ms:
            catch_up_start_dt_utc = datetime.now(timezone.utc) - timedelta(
                days=initial_catch_up_days
            )
            if candle_granularity_minutes >= 1440:
                start_dt_utc = catch_up_start_dt_utc.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            elif candle_granularity_minutes >= 60:
                start_dt_utc = catch_up_start_dt_utc.replace(
                    minute=0, second=0, microsecond=0
                )
            else:
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

        if candle_granularity_minutes >= 1440:
            start_date_str = start_dt_utc.strftime("%Y-%m-%d")
            end_date_str = end_dt_utc.strftime("%Y-%m-%d")
        else:
            start_date_str = start_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")
            end_date_str = end_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")

        fetched_candles = []
        if run_mode == "dry":
            logging.info(
                f"DRY RUN: Simulating Tiingo API call for {ticker} (catch-up): {start_date_str} to {end_date_str}"
            )
            if start_dt_utc < end_dt_utc:
                dummy_ts_ms = int(start_dt_utc.timestamp() * 1000)
                fetched_candles = [
                    {
                        "timestamp_ms": dummy_ts_ms,
                        "open": 2.0,
                        "high": 2.1,
                        "low": 1.9,
                        "close": 2.05,
                        "volume": 200.0,
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
                    last_processed_timestamps[ticker] = latest_ts_in_batch
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

        dry_run_tickers_processed += 1

        if ticker_index < len(tiingo_tickers) - 1 and run_mode == "wet":
            logging.info(
                f"Waiting {api_call_delay_seconds}s before next API call for catch-up..."
            )
            time.sleep(api_call_delay_seconds)

    logging.info("Catch-up candle processing completed.")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    redis_manager = None  # Initialize to None

    if FLAGS.run_mode == "wet":
        if not FLAGS.tiingo_api_key:
            logging.error("TIINGO_API_KEY is required. Set via env var or flag.")
            sys.exit(1)
        if not FLAGS.influxdb_token:
            logging.error("INFLUXDB_TOKEN is required. Set via env var or flag.")
            sys.exit(1)
        if not FLAGS.influxdb_org:
            logging.error("INFLUXDB_ORG is required. Set via env var or flag.")
            sys.exit(1)
        if not FLAGS.redis_host:
            logging.error("REDIS_HOST is required. Set via env var or flag.")
            sys.exit(1)

    logging.info(
        f"Starting candle ingestor script (Python) in {FLAGS.run_mode} mode..."
    )
    logging.info("Configuration:")
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
            logging.error("Failed to connect to InfluxDB after retries. Exiting.")
            sys.exit(1)

        try:
            redis_manager = RedisCryptoClient(
                host=FLAGS.redis_host,
                port=FLAGS.redis_port,
                password=FLAGS.redis_password,
            )
            if not redis_manager.get_client():  # Check if connection was successful
                logging.error("Failed to connect to Redis. Exiting.")
                if influx_manager:
                    influx_manager.close()
                sys.exit(1)
        except redis.exceptions.RedisError as e:
            logging.error(f"Failed to initialize Redis client: {e}. Exiting.")
            if influx_manager:
                influx_manager.close()
            sys.exit(1)

    else:  # Dry run
        logging.info("DRY RUN: Skipping InfluxDB and Redis connections.")

        # For dry run, we can simulate a Redis client that returns dummy data
        class DryRunRedisClient:
            def get_top_crypto_pairs_from_redis(self, key):
                logging.info(f"DRY RUN: Simulating fetch from Redis for key '{key}'")
                return ["btcusd-dry", "ethusd-dry"]

            def close(self):
                logging.info("DRY RUN: Simulating Redis client close.")

        redis_manager = DryRunRedisClient()

    tiingo_tickers = []
    if redis_manager:
        try:
            logging.info(
                f"Fetching top crypto symbols from Redis key '{FLAGS.redis_key_crypto_symbols}'..."
            )
            tiingo_tickers = redis_manager.get_top_crypto_pairs_from_redis(
                FLAGS.redis_key_crypto_symbols
            )
            if not tiingo_tickers:
                logging.warning(
                    "No symbols fetched from Redis. Will not process any candles."
                )
            else:
                logging.info(f"Fetched symbols from Redis: {tiingo_tickers}")
        except Exception as e:
            logging.error(f"Failed to fetch symbols from Redis: {e}. Exiting.")
            if influx_manager:
                influx_manager.close()
            if redis_manager and FLAGS.run_mode == "wet":
                redis_manager.close()  # only close real client
            sys.exit(1)

    if (
        not tiingo_tickers and FLAGS.run_mode == "wet"
    ):  # Still exit if wet run and no symbols
        logging.error("No symbols available to process. Exiting.")
        if influx_manager:
            influx_manager.close()
        if redis_manager and FLAGS.run_mode == "wet":
            redis_manager.close()
        sys.exit(1)

    if not tiingo_tickers and FLAGS.run_mode == "dry":
        logging.warning(
            "DRY RUN: No symbols returned from dummy Redis, using fixed list for dry run."
        )
        tiingo_tickers = ["btcusd-dry", "ethusd-dry"]

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
                dry_run_processing_limit=(
                    DRY_RUN_PROCESSING_LIMIT_DEFAULT
                    if FLAGS.run_mode == "dry"
                    else None
                ),
            )
        else:
            logging.info(
                "Skipping historical backfill as per 'backfill_start_date' flag."
            )
            if FLAGS.run_mode == "wet" and influx_manager:
                for ticker in tiingo_tickers:
                    ts_catch_up = influx_manager.get_last_processed_timestamp(
                        ticker, "catch_up"
                    )
                    if ts_catch_up:
                        last_processed_candle_timestamps[ticker] = ts_catch_up
                    else:
                        ts_backfill = influx_manager.get_last_processed_timestamp(
                            ticker, "backfill"
                        )
                        if ts_backfill:
                            last_processed_candle_timestamps[ticker] = ts_backfill

        run_catch_up(
            influx_manager=influx_manager,
            tiingo_tickers=tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=last_processed_candle_timestamps,
            run_mode=FLAGS.run_mode,
            dry_run_processing_limit=(
                DRY_RUN_PROCESSING_LIMIT_DEFAULT if FLAGS.run_mode == "dry" else None
            ),
        )

    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
        sys.exit(1)
    finally:
        logging.info(
            "Main processing finished. Ensuring connections are closed if opened."
        )
        if influx_manager and influx_manager.get_client():
            influx_manager.close()
        if (
            redis_manager and hasattr(redis_manager, "client") and redis_manager.client
        ):  # Check if it's the real client
            redis_manager.close()
        elif (
            FLAGS.run_mode == "dry" and redis_manager
        ):  # For dry run, call its dummy close
            redis_manager.close()

    logging.info("Candle ingestor script completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    app.run(main)
