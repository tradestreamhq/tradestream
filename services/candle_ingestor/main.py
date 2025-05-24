import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Tuple, NamedTuple

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


# Enums for better type safety and eliminating string comparisons
class RunMode(Enum):
    WET = "wet"
    DRY = "dry"

class ProcessType(Enum):
    BACKFILL = "backfill"
    POLLING = "polling"

class ValidationResult(NamedTuple):
    is_valid: bool
    error_message: Optional[str] = None

# Configuration structures
@dataclass
class DryRunLimits:
    max_tickers: int = 1
    max_chunks_per_ticker: int = 1
    max_polling_cycles: int = 2

@dataclass
class ProcessingContext:
    run_mode: RunMode
    influx_manager: Optional[InfluxDBManager]
    tiingo_api_key: str
    candle_granularity_minutes: int
    api_call_delay_seconds: int
    last_processed_timestamps: Dict[str, int] = field(default_factory=dict)
    dry_run_limits: DryRunLimits = field(default_factory=DryRunLimits)

@dataclass
class ChunkInfo:
    start_dt: datetime
    end_dt: datetime
    start_str: str
    end_str: str

@dataclass
class ConfigFlags:
    cmc_api_key: str
    top_n_cryptos: int
    tiingo_api_key: str
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket: str
    candle_granularity_minutes: int
    backfill_start_date: str
    tiingo_api_call_delay_seconds: int
    polling_initial_catchup_days: int
    run_mode: RunMode

# Global variables for shutdown handling (preserved for compatibility)
shutdown_requested = False
influx_manager_global = None

# Flag definition and validation strategies
def _define_flags():
    """Define all command-line flags"""
    flags.DEFINE_string("cmc_api_key", os.getenv("CMC_API_KEY"), "CoinMarketCap API Key.")
    flags.DEFINE_integer("top_n_cryptos", 20, "Number of top cryptocurrencies to fetch from CMC.")
    flags.DEFINE_string("tiingo_api_key", os.getenv("TIINGO_API_KEY"), "Tiingo API Key.")
    
    default_influx_url = os.getenv("INFLUXDB_URL", "http://influxdb.tradestream-namespace.svc.cluster.local:8086")
    flags.DEFINE_string("influxdb_url", default_influx_url, "InfluxDB URL.")
    flags.DEFINE_string("influxdb_token", os.getenv("INFLUXDB_TOKEN"), "InfluxDB Token.")
    flags.DEFINE_string("influxdb_org", os.getenv("INFLUXDB_ORG"), "InfluxDB Organization.")
    flags.DEFINE_string("influxdb_bucket", os.getenv("INFLUXDB_BUCKET", "tradestream-data"), "InfluxDB Bucket for candles and state.")
    
    flags.DEFINE_integer("candle_granularity_minutes", 1, "Granularity of candles in minutes.")
    flags.DEFINE_string("backfill_start_date", "1_year_ago", 'Start date for historical backfill (YYYY-MM-DD, "X_days_ago", "X_months_ago", "X_years_ago", or "skip").')
    flags.DEFINE_integer("tiingo_api_call_delay_seconds", 2, "Delay in seconds between Tiingo API calls for different tickers/chunks during backfill and polling.")
    flags.DEFINE_integer("polling_initial_catchup_days", 7, "How many days back to check for initial polling state if none is found from backfill.")
    flags.DEFINE_enum("run_mode", "wet", ["wet", "dry"], "Run mode for the ingestor: 'wet' for live data, 'dry' for simulated data.")

# Flag validation strategies - eliminate all if statements with lookup tables
WET_MODE_VALIDATORS = {
    'cmc_api_key': lambda flags: ValidationResult(bool(flags.cmc_api_key), "CMC_API_KEY is required for 'wet' mode. Set environment variable or use --cmc_api_key."),
    'tiingo_api_key': lambda flags: ValidationResult(bool(flags.tiingo_api_key), "TIINGO_API_KEY is required for 'wet' mode. Set environment variable or use --tiingo_api_key."),
    'influxdb_token': lambda flags: ValidationResult(bool(flags.influxdb_token), "INFLUXDB_TOKEN is required for 'wet' mode. Set environment variable or use --influxdb_token."),
    'influxdb_org': lambda flags: ValidationResult(bool(flags.influxdb_org), "INFLUXDB_ORG is required for 'wet' mode. Set environment variable or use --influxdb_org."),
}

DRY_MODE_VALIDATORS = {
    # No validation needed for dry mode
}

MODE_VALIDATORS = {
    RunMode.WET: WET_MODE_VALIDATORS,
    RunMode.DRY: DRY_MODE_VALIDATORS,
}

# Strategy patterns to eliminate if statements
def _create_dummy_historical_data(ticker: str, start_dt: datetime) -> List[Dict]:
    dummy_ts_ms = int(start_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    return [{
        "timestamp_ms": dummy_ts_ms,
        "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "volume": 100.0,
        "currency_pair": ticker,
    }]

def _create_dummy_polling_data(ticker: str, start_dt: datetime) -> List[Dict]:
    dummy_ts_ms = int(start_dt.timestamp() * 1000)
    return [{
        "timestamp_ms": dummy_ts_ms,
        "open": 2.0, "high": 2.1, "low": 1.9, "close": 2.05, "volume": 50.0,
        "currency_pair": ticker,
    }]

DATA_FETCHERS = {
    RunMode.DRY: lambda ctx, ticker, chunk: _create_dummy_historical_data(ticker, chunk.start_dt),
    RunMode.WET: lambda ctx, ticker, chunk: get_historical_candles_tiingo(
        ctx.tiingo_api_key, ticker, chunk.start_str, chunk.end_str,
        get_tiingo_resample_freq(ctx.candle_granularity_minutes)
    )
}

POLLING_DATA_FETCHERS = {
    RunMode.DRY: lambda ctx, ticker, start_str, end_str, start_dt: _create_dummy_polling_data(ticker, start_dt),
    RunMode.WET: lambda ctx, ticker, start_str, end_str, start_dt: get_historical_candles_tiingo(
        ctx.tiingo_api_key, ticker, start_str, end_str,
        get_tiingo_resample_freq(ctx.candle_granularity_minutes)
    )
}

TICKER_PROVIDERS = {
    RunMode.DRY: lambda cmc_key, top_n: ["btcusd-dry", "ethusd-dry"],
    RunMode.WET: lambda cmc_key, top_n: get_top_n_crypto_symbols(cmc_key, top_n)
}

INFLUX_SETUP_STRATEGIES = {
    RunMode.DRY: lambda config: (None, "DRY RUN: Skipping InfluxDB connection."),
    RunMode.WET: lambda config: _create_influx_manager(config)
}

COMPLETION_MESSAGES = {
    RunMode.DRY: "DRY RUN: Backfill simulation complete.",
    RunMode.WET: "Historical candle backfill completed."
}

MODE_INIT_MESSAGES = {
    RunMode.DRY: "DRY RUN: Backfill will use dummy data and limited iterations.",
    RunMode.WET: None
}

POLLING_INIT_MESSAGES = {
    RunMode.DRY: "DRY RUN: Polling will use dummy data and limited iterations.",
    RunMode.WET: None
}

def handle_shutdown_signal(signum, frame):
    global shutdown_requested, influx_manager_global
    logging.info(f"Shutdown signal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
    shutdown_requested = True
    _attempt_influx_cleanup(influx_manager_global)

def _attempt_influx_cleanup(influx_manager):
    if not influx_manager:
        return
        
    try:
        logging.info("Attempting to close InfluxDB connection from signal handler...")
        influx_manager.close()
        logging.info("InfluxDB connection closed via signal handler.")
    except Exception as e:
        logging.error(f"Error closing InfluxDB connection from signal handler: {e}")

def _create_influx_manager(config: ConfigFlags) -> Tuple[Optional[InfluxDBManager], str]:
    manager = InfluxDBManager(
        url=config.influxdb_url,
        token=config.influxdb_token,
        org=config.influxdb_org,
        bucket=config.influxdb_bucket,
    )
    
    return (manager, None) if manager.get_client() else (None, "Failed to connect to InfluxDB. Exiting.")

def _validate_configuration(config: ConfigFlags) -> ValidationResult:
    validators = MODE_VALIDATORS[config.run_mode]
    
    for validator_name, validator_func in validators.items():
        result = validator_func(config)
        if not result.is_valid:
            return result
    
    return ValidationResult(True)

def _create_config_from_flags(flags_obj) -> ConfigFlags:
    return ConfigFlags(
        cmc_api_key=flags_obj.cmc_api_key,
        top_n_cryptos=flags_obj.top_n_cryptos,
        tiingo_api_key=flags_obj.tiingo_api_key,
        influxdb_url=flags_obj.influxdb_url,
        influxdb_token=flags_obj.influxdb_token,
        influxdb_org=flags_obj.influxdb_org,
        influxdb_bucket=flags_obj.influxdb_bucket,
        candle_granularity_minutes=flags_obj.candle_granularity_minutes,
        backfill_start_date=flags_obj.backfill_start_date,
        tiingo_api_call_delay_seconds=flags_obj.tiingo_api_call_delay_seconds,
        polling_initial_catchup_days=flags_obj.polling_initial_catchup_days,
        run_mode=RunMode(flags_obj.run_mode)
    )

def _should_skip_backfill(earliest_dt: datetime, end_dt: datetime) -> bool:
    if earliest_dt < end_dt:
        return False
        
    logging.info(
        f"Backfill flag start date ({earliest_dt.strftime('%Y-%m-%d')}) is not before "
        f"effective end date ({end_dt.strftime('%Y-%m-%d')}). Skipping backfill."
    )
    return True

def _get_ticker_start_date(ctx: ProcessingContext, ticker: str, earliest_dt: datetime, 
                          granularity_delta: timedelta) -> Tuple[datetime, bool]:
    db_last_ts_ms = _get_last_timestamp(ctx.influx_manager, ticker, ProcessType.BACKFILL, 
                                       ctx.last_processed_timestamps)
    
    if not db_last_ts_ms or db_last_ts_ms <= 0:
        logging.info(f"Starting new backfill for {ticker} from flag-defined start: {earliest_dt.isoformat()}")
        return earliest_dt, False
        
    dt_from_db = datetime.fromtimestamp(db_last_ts_ms / 1000.0, timezone.utc)
    next_start = dt_from_db.replace(second=0, microsecond=0) + granularity_delta
    current_start = max(earliest_dt, next_start)
    
    logging.info(f"Resuming backfill for {ticker} from DB state, effective start: {current_start.isoformat()}")
    return current_start, True

def _get_last_timestamp(influx_manager: Optional[InfluxDBManager], ticker: str, 
                       process_type: ProcessType, fallback_dict: Dict[str, int]) -> Optional[int]:
    return influx_manager.get_last_processed_timestamp(ticker, process_type.value) if influx_manager else fallback_dict.get(ticker)

def _should_skip_ticker_backfill(current_start: datetime, end_dt: datetime, 
                                ticker: str, db_last_ts_ms: Optional[int]) -> bool:
    if current_start < end_dt:
        return False
        
    logging.info(
        f"Ticker {ticker} already effectively backfilled up to or beyond target end date. "
        f"Last known DB ts: {db_last_ts_ms}. Skipping."
    )
    return True

def _create_chunk_info(start_dt: datetime, end_dt: datetime) -> ChunkInfo:
    chunk_end = min(start_dt + timedelta(days=89), end_dt - timedelta(microseconds=1))
    return ChunkInfo(
        start_dt=start_dt,
        end_dt=chunk_end,
        start_str=start_dt.strftime("%Y-%m-%d"),
        end_str=chunk_end.strftime("%Y-%m-%d")
    )

def _process_historical_chunk(ctx: ProcessingContext, ticker: str, chunk: ChunkInfo) -> List[Dict]:
    log_prefixes = {RunMode.DRY: "DRY RUN: Simulating", RunMode.WET: "  Fetching chunk for"}
    logging.info(f"{log_prefixes[ctx.run_mode]} {ticker}: {chunk.start_str} to {chunk.end_str}")
    
    fetcher = DATA_FETCHERS[ctx.run_mode]
    return fetcher(ctx, ticker, chunk)

def _write_candles_and_update_state(ctx: ProcessingContext, ticker: str, candles: List[Dict], 
                                   process_type: ProcessType) -> bool:
    if not candles:
        return False
        
    candles.sort(key=lambda c: c["timestamp_ms"])
    written_count = ctx.influx_manager.write_candles_batch(candles) if ctx.influx_manager else 0
    
    success_conditions = {
        RunMode.DRY: True,
        RunMode.WET: written_count > 0
    }
    
    if success_conditions[ctx.run_mode]:
        latest_ts = candles[-1]["timestamp_ms"]
        ctx.last_processed_timestamps[ticker] = latest_ts
        
        if ctx.influx_manager:
            ctx.influx_manager.update_last_processed_timestamp(ticker, process_type.value, latest_ts)
        
        count_msg = written_count if written_count > 0 else len(candles)
        logging.info(f"  Successfully processed {count_msg} candles. Updated {process_type.value} state for {ticker} to {latest_ts}")
        return True
    
    logging.warning(f"  Write_candles_batch reported 0 candles written for {ticker} despite having data. DB State not updated for this batch.")
    return False

def _should_continue_processing(ctx: ProcessingContext, counters: Dict[str, int]) -> bool:
    if ctx.run_mode == RunMode.WET:
        return True
        
    limits_check = {
        'tickers': counters.get('tickers', 0) < ctx.dry_run_limits.max_tickers,
        'chunks': counters.get('chunks', 0) < ctx.dry_run_limits.max_chunks_per_ticker,
        'cycles': counters.get('cycles', 0) < ctx.dry_run_limits.max_polling_cycles
    }
    
    return all(limits_check.values())

def _wait_between_api_calls(ctx: ProcessingContext, ticker_count: int):
    should_wait_conditions = {
        'multiple_tickers': ticker_count > 1,
        'wet_mode': ctx.run_mode == RunMode.WET
    }
    
    if not all(should_wait_conditions.values()):
        return
        
    logging.info(f"Waiting {ctx.api_call_delay_seconds}s before next API call...")
    for _ in range(ctx.api_call_delay_seconds):
        if shutdown_requested:
            break
        time.sleep(1)

def _process_backfill_ticker(ctx: ProcessingContext, ticker: str, earliest_dt: datetime, 
                           end_dt: datetime, granularity_delta: timedelta) -> int:
    global shutdown_requested
    
    current_start, has_existing = _get_ticker_start_date(ctx, ticker, earliest_dt, granularity_delta)
    
    if _should_skip_ticker_backfill(current_start, end_dt, ticker, 
                                   ctx.last_processed_timestamps.get(ticker)):
        return 0
    
    logging.info(f"Backfilling {ticker} from {current_start.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    chunk_start = current_start
    chunks_processed = 0
    max_ts_for_ticker = 0
    
    while chunk_start < end_dt and not shutdown_requested:
        if not _should_continue_processing(ctx, {'chunks': chunks_processed}):
            break
            
        chunk = _create_chunk_info(chunk_start, end_dt)
        candles = _process_historical_chunk(ctx, ticker, chunk)
        
        if candles and _write_candles_and_update_state(ctx, ticker, candles, ProcessType.BACKFILL):
            max_ts_for_ticker = max(max_ts_for_ticker, candles[-1]["timestamp_ms"])
        elif not candles:
            logging.info(f"  No data in chunk for {ticker}: {chunk.start_str} to {chunk.end_str}")
        
        chunks_processed += 1
        chunk_start = chunk.end_dt + timedelta(days=1)
        
        if chunk_start < end_dt and not shutdown_requested:
            _wait_between_api_calls(ctx, 1)  # Single ticker context
        
        if shutdown_requested:
            break
    
    if max_ts_for_ticker > 0:
        ctx.last_processed_timestamps[ticker] = max(
            ctx.last_processed_timestamps.get(ticker, 0), max_ts_for_ticker
        )
    
    logging.info(f"Finished backfill for {ticker}. Check InfluxDB for authoritative state.")
    return chunks_processed

def run_backfill(ctx: ProcessingContext, tickers: List[str], backfill_start_date_str: str):
    global shutdown_requested
    
    logging.info("Starting historical candle backfill...")
    init_message = MODE_INIT_MESSAGES[ctx.run_mode]
    if init_message:
        logging.info(init_message)
    
    earliest_dt = parse_backfill_start_date(backfill_start_date_str)
    end_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if _should_skip_backfill(earliest_dt, end_dt):
        return
    
    granularity_delta = timedelta(minutes=ctx.candle_granularity_minutes)
    tickers_processed = 0
    
    for ticker in tickers:
        if shutdown_requested or not _should_continue_processing(ctx, {'tickers': tickers_processed}):
            break
            
        _process_backfill_ticker(ctx, ticker, earliest_dt, end_dt, granularity_delta)
        tickers_processed += 1
    
    logging.info(COMPLETION_MESSAGES[ctx.run_mode])
    if ctx.run_mode == RunMode.DRY:
        shutdown_requested = True

def _initialize_polling_timestamp(ctx: ProcessingContext, ticker: str, initial_catchup_days: int) -> int:
    existing_ts = ctx.last_processed_timestamps.get(ticker, 0)
    if existing_ts > 0:
        logging.info(f"Using pre-existing/backfill timestamp for {ticker} for polling start: {datetime.fromtimestamp(existing_ts / 1000.0, timezone.utc).isoformat()}")
        return existing_ts
    
    # Check polling state
    polling_ts = _get_last_timestamp(ctx.influx_manager, ticker, ProcessType.POLLING, {})
    if polling_ts:
        ctx.last_processed_timestamps[ticker] = polling_ts
        logging.info(f"Found last polling state for {ticker}: {datetime.fromtimestamp(polling_ts / 1000.0, timezone.utc).isoformat()}")
        return polling_ts
    
    # Check backfill state
    backfill_ts = _get_last_timestamp(ctx.influx_manager, ticker, ProcessType.BACKFILL, {})
    if backfill_ts:
        ctx.last_processed_timestamps[ticker] = backfill_ts
        logging.info(f"No polling state for {ticker}, using last backfill state: {datetime.fromtimestamp(backfill_ts / 1000.0, timezone.utc).isoformat()}")
        return backfill_ts
    
    # Default catchup
    now_utc = datetime.now(timezone.utc)
    default_start = now_utc - timedelta(days=initial_catchup_days)
    aligned_minute = (default_start.minute // ctx.candle_granularity_minutes) * ctx.candle_granularity_minutes
    aligned_start = default_start.replace(minute=aligned_minute, second=0, microsecond=0)
    default_ts = int(aligned_start.timestamp() * 1000)
    
    ctx.last_processed_timestamps[ticker] = default_ts
    logging.info(f"No backfill or polling state for {ticker}. Setting polling start from approx {initial_catchup_days} days ago: {aligned_start.isoformat()}")
    return default_ts

def _calculate_polling_parameters(ctx: ProcessingContext, ticker: str, current_time: datetime) -> Tuple[Optional[datetime], Optional[datetime], Optional[str], Optional[str], bool]:
    last_ts_ms = ctx.last_processed_timestamps.get(ticker)
    if last_ts_ms is None:
        logging.error(f"CRITICAL: Missing last_ts_ms for {ticker} at start of polling iteration. This should not happen.")
        fallback_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)
        ctx.last_processed_timestamps[ticker] = fallback_ts
        last_ts_ms = fallback_ts
    
    last_candle_start = datetime.fromtimestamp(last_ts_ms / 1000.0, timezone.utc)
    granularity_delta = timedelta(minutes=ctx.candle_granularity_minutes)
    
    current_minute_floored = (current_time.minute // ctx.candle_granularity_minutes) * ctx.candle_granularity_minutes
    latest_closed_end = current_time.replace(minute=current_minute_floored, second=0, microsecond=0)
    target_latest_start = latest_closed_end - granularity_delta
    
    if target_latest_start.timestamp() * 1000 <= last_ts_ms:
        logging.debug(f"Candle for {ticker} starting at {target_latest_start.isoformat()} (or earlier) already processed (last was {last_candle_start.isoformat()}). Skipping.")
        return None, None, None, None, True  # Skip this ticker
    
    query_start = last_candle_start + granularity_delta
    query_end = current_time
    
    if query_start >= query_end:
        logging.debug(f"Query start time {query_start.isoformat()} is not before effective query end {query_end.isoformat()} for {ticker}. Skipping API call.")
        return None, None, None, None, True  # Skip this ticker
    
    use_time_format = ctx.candle_granularity_minutes < 1440
    format_map = {True: "%Y-%m-%dT%H:%M:%S", False: "%Y-%m-%d"}
    time_format = format_map[use_time_format]
    
    start_str = query_start.strftime(time_format)
    end_str = query_end.strftime(time_format)
    
    return query_start, query_end, start_str, end_str, False

def _process_polling_ticker(ctx: ProcessingContext, ticker: str, current_time: datetime) -> bool:
    try:
        query_start, query_end, start_str, end_str, should_skip = _calculate_polling_parameters(ctx, ticker, current_time)
        
        if should_skip:
            return True
        
        granularity_delta = timedelta(minutes=ctx.candle_granularity_minutes)
        last_ts_ms = ctx.last_processed_timestamps[ticker]
        
        log_prefixes = {RunMode.DRY: "DRY RUN: Simulating", RunMode.WET: "Polling for"}
        logging.info(f"{log_prefixes[ctx.run_mode]} {ticker} from {start_str} to {end_str}")
        
        fetcher = POLLING_DATA_FETCHERS[ctx.run_mode]
        polled_candles = fetcher(ctx, ticker, start_str, end_str, query_start)
        
        if not polled_candles:
            logging.info(f"Polling returned no data for {ticker} for period starting {start_str}")
            return True
        
        # Filter for new, closed candles
        new_candles = []
        current_ts_ms = current_time.timestamp() * 1000
        
        for candle in polled_candles:
            candle_ts_ms = candle["timestamp_ms"]
            candle_end_ts_ms = candle_ts_ms + granularity_delta.total_seconds() * 1000
            
            if candle_ts_ms > last_ts_ms and candle_end_ts_ms <= current_ts_ms:
                new_candles.append(candle)
        
        if not new_candles:
            logging.info(f"No new, fully closed candles found for {ticker} in polled range after filtering.")
            return True
        
        logging.info(f"Fetched {len(new_candles)} new, closed candle(s) for {ticker} via polling.")
        return _write_candles_and_update_state(ctx, ticker, new_candles, ProcessType.POLLING)
        
    except Exception as e:
        logging.exception(f"Error polling for ticker {ticker}: {e}")
        return True

def run_polling_loop(ctx: ProcessingContext, tickers: List[str], initial_catchup_days: int):
    global shutdown_requested
    
    logging.info("Starting real-time candle polling loop...")
    init_message = POLLING_INIT_MESSAGES[ctx.run_mode]
    if init_message:
        logging.info(init_message)
    
    # Initialize polling timestamps
    logging.info("Initializing polling timestamps...")
    for ticker in tickers:
        if shutdown_requested:
            logging.info("Shutdown requested during polling timestamp initialization.")
            return
        _initialize_polling_timestamp(ctx, ticker, initial_catchup_days)
    
    cycles_processed = 0
    
    try:
        while not shutdown_requested and _should_continue_processing(ctx, {'cycles': cycles_processed}):
            loop_start = time.monotonic()
            current_time = datetime.now(timezone.utc)
            
            logging.info(f"Starting polling cycle at {current_time.isoformat()}")
            
            for ticker in tickers:
                if shutdown_requested:
                    logging.info(f"Shutdown requested during polling for ticker {ticker}.")
                    break
                    
                _process_polling_ticker(ctx, ticker, current_time)
                
                if shutdown_requested:
                    logging.info(f"Shutdown requested after processing ticker {ticker}.")
                    break
                    
                _wait_between_api_calls(ctx, len(tickers))
                
                if shutdown_requested:
                    break
            
            if shutdown_requested:
                logging.info("Shutdown requested. Exiting polling loop.")
                break
                
            cycles_processed += 1
            
            # Sleep calculation
            loop_duration = time.monotonic() - loop_start
            sleep_time = (ctx.candle_granularity_minutes * 60) - loop_duration
            
            if sleep_time > 0:
                logging.info(f"Polling cycle finished in {loop_duration:.2f}s. Sleeping for {sleep_time:.2f}s.")
                for _ in range(int(sleep_time)):
                    if shutdown_requested:
                        break
                    time.sleep(1)
            else:
                logging.warning(
                    f"Polling cycle duration ({loop_duration:.2f}s) exceeded granularity ({ctx.candle_granularity_minutes*60}s). "
                    "Running next cycle immediately."
                )
    
    except KeyboardInterrupt:
        logging.info("Polling loop interrupted by user (KeyboardInterrupt).")
        shutdown_requested = True
    finally:
        logging.info("Polling loop finished.")

def _log_configuration(config: ConfigFlags):
    logging.info("Configuration:")
    logging.info(f"  Run Mode: {config.run_mode.value}")
    logging.info(f"  CoinMarketCap API Key: {'****' if config.cmc_api_key else 'Not Set/Loaded from Env'}")
    logging.info(f"  Top N Cryptos: {config.top_n_cryptos}")
    logging.info(f"  Tiingo API Key: {'****' if config.tiingo_api_key else 'Not Set/Loaded from Env'}")
    logging.info(f"  InfluxDB URL: {config.influxdb_url}")
    logging.info(f"  InfluxDB Token: {'****' if config.influxdb_token else 'Not Set/Loaded from Env'}")
    logging.info(f"  InfluxDB Org: {config.influxdb_org}")
    logging.info(f"  InfluxDB Bucket: {config.influxdb_bucket}")
    logging.info(f"  Candle Granularity: {config.candle_granularity_minutes} min(s)")
    logging.info(f"  Backfill Start Date: {config.backfill_start_date}")
    logging.info(f"  Tiingo API Call Delay: {config.tiingo_api_call_delay_seconds}s")
    logging.info(f"  Polling Initial Catchup Days: {config.polling_initial_catchup_days}")

def _get_tickers(config: ConfigFlags) -> List[str]:
    provider = TICKER_PROVIDERS[config.run_mode]
    tickers = provider(config.cmc_api_key, config.top_n_cryptos)
    
    if not tickers:
        logging.error("No symbols fetched. Exiting.")
        return []
        
    logging.info(f"Target Tiingo tickers: {tickers}")
    return tickers

def _prepopulate_backfill_states(ctx: ProcessingContext, tickers: List[str]):
    if ctx.run_mode == RunMode.DRY or not ctx.influx_manager:
        return
        
    logging.info("Attempting to pre-populate backfill states from InfluxDB...")
    for ticker in tickers:
        if shutdown_requested:
            break
            
        db_state_ts_ms = ctx.influx_manager.get_last_processed_timestamp(ticker, ProcessType.BACKFILL.value)
        if db_state_ts_ms:
            ctx.last_processed_timestamps[ticker] = db_state_ts_ms
            logging.info(f"  Pre-populated backfill state for {ticker}: {datetime.fromtimestamp(db_state_ts_ms / 1000.0, timezone.utc).isoformat()}")
        else:
            logging.info(f"  No prior backfill state found in DB for {ticker}.")

def _execute_main_workflow(config: ConfigFlags, influx_manager: InfluxDBManager, tickers: List[str]):
    ctx = ProcessingContext(
        run_mode=config.run_mode,
        influx_manager=influx_manager,
        tiingo_api_key=config.tiingo_api_key,
        candle_granularity_minutes=config.candle_granularity_minutes,
        api_call_delay_seconds=config.tiingo_api_call_delay_seconds,
    )
    
    skip_backfill = config.backfill_start_date.lower() == "skip"
    
    if not skip_backfill:
        _prepopulate_backfill_states(ctx, tickers)
        
        if not shutdown_requested:
            run_backfill(ctx, tickers, config.backfill_start_date)
    else:
        logging.info("Skipping historical backfill as per 'backfill_start_date' flag.")
    
    if not shutdown_requested:
        run_polling_loop(ctx, tickers, config.polling_initial_catchup_days)

def main(argv):
    global shutdown_requested, influx_manager_global
    del argv
    
    # Define flags
    _define_flags()
    
    logging.set_verbosity(logging.INFO)
    
    # Create configuration object
    config = _create_config_from_flags(flags.FLAGS)
    
    # Validate configuration using strategy pattern
    validation_result = _validate_configuration(config)
    if not validation_result.is_valid:
        logging.error(validation_result.error_message)
        sys.exit(1)
    
    logging.info(f"Starting candle ingestor script (Python) in {config.run_mode.value} mode...")
    
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    
    _log_configuration(config)
    
    # Setup InfluxDB using strategy pattern
    setup_strategy = INFLUX_SETUP_STRATEGIES[config.run_mode]
    influx_manager_global, error_message = setup_strategy(config)
    
    if error_message:
        logging.error(error_message)
        return 1
    
    if influx_manager_global:
        logging.info("InfluxDB connection established.")
    
    if shutdown_requested:
        logging.info("Shutdown requested before starting main processing.")
        if influx_manager_global:
            influx_manager_global.close()
        sys.exit(0)
    
    tickers = _get_tickers(config)
    if not tickers:
        if influx_manager_global:
            influx_manager_global.close()
        return 1
    
    try:
        _execute_main_workflow(config, influx_manager_global, tickers)
    except Exception as e:
        logging.exception(f"Critical error in main execution: {e}")
    finally:
        logging.info("Main process finished. Ensuring InfluxDB connection is closed if it was opened.")
        if influx_manager_global and influx_manager_global.get_client():
            influx_manager_global.close()
    
    if shutdown_requested:
        logging.info("Exiting due to shutdown request.")
        sys.exit(0)
    
    return 0

if __name__ == "__main__":
    app.run(main)
