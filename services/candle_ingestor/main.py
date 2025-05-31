"""
Modified main.py to use CCXT instead of Tiingo while maintaining all existing functionality.
Drop-in replacement for the original Tiingo-based candle ingestor with symbol filtering.
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
import json

from absl import app
from absl import flags
from absl import logging

from services.candle_ingestor.influx_client import InfluxDBManager
from services.candle_ingestor.ccxt_client import (
    MultiExchangeCandleClient,
    CCXTCandleClient,
)
from services.candle_ingestor.ingestion_helpers import (
    parse_backfill_start_date,
)
from shared.cryptoclient.redis_crypto_client import RedisCryptoClient
from shared.persistence.influxdb_last_processed_tracker import (
    InfluxDBLastProcessedTracker,
)
import redis

FLAGS = flags.FLAGS

# CCXT Configuration Flags
flags.DEFINE_list(
    "exchanges",
    ["binance", "coinbasepro", "kraken"],
    "List of exchanges to use for candle data (first exchange is primary, order determines priority)"
)
flags.DEFINE_integer(
    "min_exchanges_required",
    0,
    "Minimum number of exchanges required for multi-exchange aggregation (0 = auto-detect from exchange count)"
)

# InfluxDB Flags (unchanged)
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

# Redis Flags (unchanged)
default_redis_host = os.getenv("REDIS_HOST", "localhost")
flags.DEFINE_string("redis_host", default_redis_host, "Redis host.")
default_redis_port = int(os.getenv("REDIS_PORT", "6379"))
flags.DEFINE_integer("redis_port", default_redis_port, "Redis port.")
flags.DEFINE_string("redis_password", os.getenv("REDIS_PASSWORD"), "Redis password (if any).")
default_redis_key_crypto_symbols = os.getenv("REDIS_KEY_CRYPTO_SYMBOLS", "top_cryptocurrencies")
flags.DEFINE_string(
    "redis_key_crypto_symbols",
    default_redis_key_crypto_symbols,
    "Redis key to fetch the list of top cryptocurrency symbols.",
)

# Candle Processing Flags
flags.DEFINE_integer("candle_granularity_minutes", 1, "Granularity of candles in minutes.")
flags.DEFINE_string(
    "backfill_start_date",
    "1_year_ago",
    'Start date for historical backfill (YYYY-MM-DD, "X_days_ago", "X_months_ago", "X_years_ago", or "skip").',
)
flags.DEFINE_integer(
    "api_call_delay_seconds",
    2,
    "Delay in seconds between API calls for different tickers/chunks during processing.",
)
flags.DEFINE_integer(
    "catch_up_initial_days",
    7,
    "How many days back to check for initial catch-up if no prior state is found.",
)

# Run Mode Flag
flags.DEFINE_enum(
    "run_mode",
    "wet",
    ["wet", "dry"],
    "Run mode for the ingestor: 'wet' for live data, 'dry' for simulated data.",
)

# Dry Run Limit Flag  
flags.DEFINE_integer(
    "dry_run_limit",
    None,
    "Maximum number of tickers to process in dry run mode. If not specified, uses default limit.",
)

DRY_RUN_PROCESSING_LIMIT_DEFAULT = 2
SERVICE_IDENTIFIER = "candle_ingestor"


def validate_symbol_availability(
    ccxt_client, 
    symbols: list[str], 
    strategy: str, 
    min_exchanges_required: int
) -> list[str]:
    """
    Filter symbols to only those supported by minimum number of exchanges.
    
    Args:
        ccxt_client: CCXT client instance (single or multi-exchange)
        symbols: List of symbols to validate
        strategy: 'single' or 'multi'
        min_exchanges_required: Minimum exchanges required for multi-exchange mode
        
    Returns:
        List of valid symbols that meet exchange availability requirements
    """
    if strategy == 'single':
        # For single exchange, check if symbols are available on that exchange
        if hasattr(ccxt_client, 'exchange'):
            # Single exchange client
            return _validate_symbols_single_exchange(ccxt_client, symbols)
        else:
            # This shouldn't happen, but fallback
            logging.warning("Single exchange strategy but multi-exchange client provided")
            return symbols
    
    else:  # strategy == 'multi'
        # For multi-exchange, check availability across exchanges
        if hasattr(ccxt_client, 'exchanges'):
            # Multi-exchange client
            return _validate_symbols_multi_exchange(ccxt_client, symbols, min_exchanges_required)
        else:
            # This shouldn't happen, but fallback
            logging.warning("Multi-exchange strategy but single exchange client provided")
            return symbols


def _validate_symbols_single_exchange(ccxt_client, symbols: list[str]) -> list[str]:
    """Validate symbols for single exchange."""
    valid_symbols = []
    exchange_name = ccxt_client.exchange_name
    
    try:
        # Load exchange markets
        markets = ccxt_client.exchange.load_markets()
        available_symbols = set(markets.keys())
        
        for symbol in symbols:
            ccxt_symbol = ccxt_client._normalize_symbol(symbol)
            if ccxt_symbol in available_symbols:
                valid_symbols.append(symbol)
                logging.debug(f"Symbol {symbol} ({ccxt_symbol}) available on {exchange_name}")
            else:
                logging.warning(f"Symbol {symbol} ({ccxt_symbol}) not available on {exchange_name}, skipping")
        
    except Exception as e:
        logging.error(f"Error loading markets from {exchange_name}: {e}")
        logging.warning(f"Cannot validate symbols for {exchange_name}, processing all symbols")
        return symbols  # Fallback to processing all symbols
    
    logging.info(f"Symbol validation: {len(valid_symbols)}/{len(symbols)} symbols available on {exchange_name}")
    return valid_symbols


def _validate_symbols_multi_exchange(
    ccxt_client, 
    symbols: list[str], 
    min_exchanges_required: int
) -> list[str]:
    """Validate symbols for multi-exchange aggregation."""
    valid_symbols = []
    symbol_exchange_counts = {}
    
    # Check availability on each exchange
    for exchange_name, exchange_client in ccxt_client.exchanges.items():
        try:
            markets = exchange_client.exchange.load_markets()
            available_symbols = set(markets.keys())
            
            for symbol in symbols:
                ccxt_symbol = exchange_client._normalize_symbol(symbol)
                
                if symbol not in symbol_exchange_counts:
                    symbol_exchange_counts[symbol] = {
                        'count': 0,
                        'exchanges': [],
                        'ccxt_symbol': ccxt_symbol
                    }
                
                if ccxt_symbol in available_symbols:
                    symbol_exchange_counts[symbol]['count'] += 1
                    symbol_exchange_counts[symbol]['exchanges'].append(exchange_name)
                    
        except Exception as e:
            logging.warning(f"Error loading markets from {exchange_name}: {e}")
            continue
    
    # Filter symbols that meet minimum exchange requirement
    for symbol, info in symbol_exchange_counts.items():
        if info['count'] >= min_exchanges_required:
            valid_symbols.append(symbol)
            logging.info(f"Symbol {symbol} available on {info['count']} exchanges: {info['exchanges']}")
        else:
            logging.warning(
                f"Symbol {symbol} only available on {info['count']} exchanges {info['exchanges']}, "
                f"but minimum {min_exchanges_required} required. Skipping."
            )
    
    if not valid_symbols:
        logging.error(
            f"No symbols meet the minimum exchange requirement of {min_exchanges_required}. "
            f"Consider lowering --min_exchanges_required or checking symbol availability."
        )
    else:
        logging.info(
            f"Symbol validation: {len(valid_symbols)}/{len(symbols)} symbols meet "
            f"minimum {min_exchanges_required} exchange requirement"
        )
    
    return valid_symbols


def validate_and_determine_ccxt_strategy():
    """
    Validate exchange configuration and determine strategy.
    
    Returns:
        tuple: (strategy, primary_exchange, exchanges_to_use, effective_min_required)
        - strategy: 'single' or 'multi'
        - primary_exchange: name of primary exchange
        - exchanges_to_use: list of exchanges to initialize
        - effective_min_required: actual minimum exchanges required after auto-detection
    """
    exchanges = FLAGS.exchanges
    min_required = FLAGS.min_exchanges_required
    
    if not exchanges:
        raise ValueError("At least one exchange must be specified in --exchanges")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_exchanges = []
    for exchange in exchanges:
        if exchange not in seen:
            seen.add(exchange)
            unique_exchanges.append(exchange)
    
    if len(unique_exchanges) != len(exchanges):
        logging.warning(f"Removed duplicate exchanges. Using: {unique_exchanges}")
    
    primary_exchange = unique_exchanges[0]
    
    # Auto-detect minimum required if not set or invalid
    if min_required <= 0:
        effective_min_required = len(unique_exchanges)
        logging.info(f"Auto-detected min_exchanges_required: {effective_min_required} (from {len(unique_exchanges)} provided exchanges)")
    else:
        effective_min_required = min_required
    
    if len(unique_exchanges) == 1:
        logging.info(f"Single exchange mode: using {primary_exchange}")
        return 'single', primary_exchange, unique_exchanges, effective_min_required
    
    elif len(unique_exchanges) >= effective_min_required:
        logging.info(f"Multi-exchange mode: using {len(unique_exchanges)} exchanges with {primary_exchange} as primary")
        logging.info(f"Exchange priority order: {unique_exchanges}")
        logging.info(f"Minimum exchanges required: {effective_min_required}")
        return 'multi', primary_exchange, unique_exchanges, effective_min_required
    
    else:
        raise ValueError(
            f"Insufficient exchanges for multi-exchange mode. "
            f"Provided {len(unique_exchanges)} exchanges but minimum required is {effective_min_required}. "
            f"Either provide only 1 exchange for single-exchange mode, "
            f"or provide at least {effective_min_required} exchanges for multi-exchange mode."
        )


def get_ccxt_timeframe(granularity_minutes: int) -> str:
    """Convert granularity in minutes to CCXT timeframe string."""
    if granularity_minutes >= 1440:  # 1 day = 24 * 60
        days = granularity_minutes // 1440
        return f"{days}d"
    elif granularity_minutes >= 60:  # 1 hour
        hours = granularity_minutes // 60
        return f"{hours}h"
    elif granularity_minutes > 0:
        return f"{granularity_minutes}m"
    else:
        logging.warning(f"Invalid candle_granularity_minutes: {granularity_minutes}. Defaulting to '1m'.")
        return "1m"


def convert_tiingo_symbol_to_ccxt(tiingo_symbol: str) -> str:
    """Convert Tiingo-style symbol to CCXT format."""
    # Handle common patterns from Tiingo format (e.g., 'btcusd' -> 'BTC/USDT')
    if '/' in tiingo_symbol:
        return tiingo_symbol.upper()
    
    if tiingo_symbol.lower().endswith('usd'):
        base = tiingo_symbol[:-3].upper()
        return f"{base}/USDT"  # Most exchanges use USDT instead of USD
    elif tiingo_symbol.lower().endswith('btc'):
        base = tiingo_symbol[:-3].upper() 
        return f"{base}/BTC"
    
    return tiingo_symbol.upper()


def get_historical_candles_ccxt(
    ccxt_client,
    ticker: str,
    start_date_str: str,
    end_date_str: str,
    timeframe: str,
) -> list[dict]:
    """
    Fetch historical candles using CCXT client.
    
    Args:
        ccxt_client: CCXT client instance
        ticker: Symbol in Tiingo format (e.g., 'btcusd')
        start_date_str: Start date string
        end_date_str: End date string  
        timeframe: CCXT timeframe string
        
    Returns:
        List of candle dictionaries compatible with existing InfluxDB writer
    """
    try:
        # Convert Tiingo symbol to CCXT format
        ccxt_symbol = convert_tiingo_symbol_to_ccxt(ticker)
        
        # Parse date strings to timestamps
        if 'T' in start_date_str:
            start_dt = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
        start_timestamp_ms = int(start_dt.timestamp() * 1000)
        
        # Calculate limit based on timeframe and date range
        if 'T' in end_date_str:
            end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
        time_diff_hours = (end_dt - start_dt).total_seconds() / 3600
        
        # Estimate reasonable limit based on timeframe
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            limit = min(1000, int(time_diff_hours * 60 / minutes) + 10)
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            limit = min(1000, int(time_diff_hours / hours) + 10)
        else:  # days
            limit = min(1000, int(time_diff_hours / 24) + 10)
        
        # Fetch candles
        if hasattr(ccxt_client, 'get_aggregated_candles'):
            # Multi-exchange client
            candles = ccxt_client.get_aggregated_candles(
                ccxt_symbol, timeframe, start_timestamp_ms, limit
            )
        else:
            # Single exchange client
            candles = ccxt_client.get_historical_candles(
                ccxt_symbol, timeframe, start_timestamp_ms, limit
            )
        
        # Convert back to Tiingo-compatible format for existing code
        for candle in candles:
            candle['currency_pair'] = ticker  # Keep original Tiingo format
            
        return candles
        
    except Exception as e:
        logging.error(f"Error fetching candles for {ticker} via CCXT: {e}")
        return []


def run_backfill(
    influx_manager: InfluxDBManager | None,
    state_tracker: InfluxDBLastProcessedTracker | None,
    tiingo_tickers: list[str],
    ccxt_client,  # CCXT client instead of API key
    backfill_start_date_str: str,
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    last_processed_timestamps: dict[str, int],
    run_mode: str,
    dry_run_processing_limit: int | None,
):
    logging.info("Starting historical candle backfill with CCXT...")
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

    timeframe = get_ccxt_timeframe(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    dry_run_tickers_processed = 0
    effective_max_dry_run_tickers = (
        dry_run_processing_limit
        if run_mode == "dry" and dry_run_processing_limit is not None
        else len(tiingo_tickers)
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
        
        if state_tracker:
            db_last_processed_ts_ms = state_tracker.get_last_processed_timestamp(
                SERVICE_IDENTIFIER, f"{ticker}-backfill"
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
                    f"DRY RUN: Simulating CCXT API call for {ticker} (backfill): {chunk_start_str} to {chunk_end_str}"
                )
                # Generate dummy data similar to original
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
                historical_candles = get_historical_candles_ccxt(
                    ccxt_client,
                    ticker,
                    chunk_start_str,
                    chunk_end_str,
                    timeframe,
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
                    if state_tracker:
                        state_tracker.update_last_processed_timestamp(
                            SERVICE_IDENTIFIER, f"{ticker}-backfill", latest_ts_in_batch
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
                and ticker_index < len(tiingo_tickers) - 1
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
    state_tracker: InfluxDBLastProcessedTracker | None,
    tiingo_tickers: list[str],
    ccxt_client,  # CCXT client instead of API key
    candle_granularity_minutes: int,
    api_call_delay_seconds: int,
    initial_catch_up_days: int,
    last_processed_timestamps: dict[str, int],
    run_mode: str,
    dry_run_processing_limit: int | None,
):
    logging.info("Starting catch-up candle processing with CCXT...")
    if run_mode == "dry":
        logging.info("DRY RUN: Catch-up will use dummy data and limited iterations.")

    timeframe = get_ccxt_timeframe(candle_granularity_minutes)
    granularity_delta = timedelta(minutes=candle_granularity_minutes)
    effective_max_dry_run_tickers = (
        dry_run_processing_limit
        if run_mode == "dry" and dry_run_processing_limit is not None
        else len(tiingo_tickers)
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

        # Use state tracker to get catch-up state
        if not last_known_ts_ms and state_tracker:
            last_known_ts_ms = state_tracker.get_last_processed_timestamp(
                SERVICE_IDENTIFIER, f"{ticker}-catch_up"
            )

        # Fallback to backfill state if no catch-up state
        if not last_known_ts_ms and state_tracker:
            last_known_ts_ms = state_tracker.get_last_processed_timestamp(
                SERVICE_IDENTIFIER, f"{ticker}-backfill"
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
                f"DRY RUN: Simulating CCXT API call for {ticker} (catch-up): {start_date_str} to {end_date_str}"
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
            fetched_candles = get_historical_candles_ccxt(
                ccxt_client, ticker, start_date_str, end_date_str, timeframe
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
                    if state_tracker:
                        state_tracker.update_last_processed_timestamp(
                            SERVICE_IDENTIFIER, f"{ticker}-catch_up", latest_ts_in_batch
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

    redis_manager = None

    if FLAGS.run_mode == "wet":
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
        f"Starting candle ingestor script (Python) in {FLAGS.run_mode} mode with CCXT..."
    )
    logging.info("Configuration:")
    logging.info(f"  Exchanges: {FLAGS.exchanges}")
    logging.info(f"  Min exchanges required: {FLAGS.min_exchanges_required}")
    for flag_name in FLAGS:
        if flag_name not in ['exchanges', 'min_exchanges_required']:  # Already logged above
            logging.info(f"  {flag_name}: {FLAGS[flag_name].value}")

    # Validate CCXT configuration and determine strategy
    try:
        strategy, primary_exchange, exchanges_to_use, effective_min_required = validate_and_determine_ccxt_strategy()
    except ValueError as e:
        logging.error(f"CCXT configuration error: {e}")
        sys.exit(1)

    logging.info(f"CCXT Strategy: {strategy}")
    logging.info(f"Primary Exchange: {primary_exchange}")
    logging.info(f"Exchanges to use: {exchanges_to_use}")

    # Initialize CCXT client
    ccxt_client = None
    if FLAGS.run_mode == "wet":
        try:
            if strategy == "single":
                ccxt_client = CCXTCandleClient(primary_exchange)
                logging.info(f"Initialized single exchange client: {primary_exchange}")
            else:  # strategy == "multi"
                ccxt_client = MultiExchangeCandleClient(
                    exchanges=exchanges_to_use,
                    min_exchanges_required=effective_min_required
                )
                logging.info(f"Initialized multi-exchange client with {len(exchanges_to_use)} exchanges: {exchanges_to_use}")
        except Exception as e:
            logging.error(f"Failed to initialize CCXT client: {e}")
            sys.exit(1)

    influx_manager = None
    state_tracker = None
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

        state_tracker = InfluxDBLastProcessedTracker(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket,
        )
        if not state_tracker.client:
            logging.error("Failed to initialize state tracker. Exiting.")
            if influx_manager:
                influx_manager.close()
            sys.exit(1)

        try:
            redis_manager = RedisCryptoClient(
                host=FLAGS.redis_host,
                port=FLAGS.redis_port,
                password=FLAGS.redis_password,
            )
            if not redis_manager.client:
                logging.error("Failed to connect to Redis. Exiting.")
                if influx_manager:
                    influx_manager.close()
                if state_tracker:
                    state_tracker.close()
                sys.exit(1)
        except redis.exceptions.RedisError as e:
            logging.error(f"Failed to initialize Redis client: {e}. Exiting.")
            if influx_manager:
                influx_manager.close()
            if state_tracker:
                state_tracker.close()
            sys.exit(1)

    else:  # Dry run
        logging.info("DRY RUN: Skipping InfluxDB, Redis, and CCXT connections.")

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
            if state_tracker:
                state_tracker.close()
            if redis_manager and FLAGS.run_mode == "wet":
                redis_manager.close()
            sys.exit(1)

    if not tiingo_tickers and FLAGS.run_mode == "wet":
        logging.error("No symbols available to process. Exiting.")
        if influx_manager:
            influx_manager.close()
        if state_tracker:
            state_tracker.close()
        if redis_manager and FLAGS.run_mode == "wet":
            redis_manager.close()
        sys.exit(1)

    if not tiingo_tickers and FLAGS.run_mode == "dry":
        logging.warning(
            "DRY RUN: No symbols returned from dummy Redis, using fixed list for dry run."
        )
        tiingo_tickers = ["btcusd-dry", "ethusd-dry"]

    # Validate symbol availability across exchanges (only in wet mode)
    if FLAGS.run_mode == "wet" and tiingo_tickers and ccxt_client:
        logging.info("Validating symbol availability across exchanges...")
        original_count = len(tiingo_tickers)
        
        tiingo_tickers = validate_symbol_availability(
            ccxt_client=ccxt_client,
            symbols=tiingo_tickers,
            strategy=strategy,
            min_exchanges_required=effective_min_required
        )
        
        filtered_count = len(tiingo_tickers)
        if filtered_count == 0:
            logging.error("No symbols available across the required number of exchanges. Exiting.")
            if influx_manager:
                influx_manager.close()
            if state_tracker:
                state_tracker.close()
            if redis_manager:
                redis_manager.close()
            sys.exit(1)
        elif filtered_count < original_count:
            logging.info(f"Filtered symbols: {original_count} → {filtered_count} symbols will be processed")
        else:
            logging.info(f"All {original_count} symbols are available for processing")

    last_processed_candle_timestamps = {}

    try:
        if FLAGS.backfill_start_date.lower() != "skip":
            run_backfill(
                influx_manager=influx_manager,
                state_tracker=state_tracker,
                tiingo_tickers=tiingo_tickers,
                ccxt_client=ccxt_client,
                backfill_start_date_str=FLAGS.backfill_start_date,
                candle_granularity_minutes=FLAGS.candle_granularity_minutes,
                api_call_delay_seconds=FLAGS.api_call_delay_seconds,
                last_processed_timestamps=last_processed_candle_timestamps,
                run_mode=FLAGS.run_mode,
                dry_run_processing_limit=(
                    FLAGS.dry_run_limit
                    if FLAGS.dry_run_limit is not None
                    else (
                        DRY_RUN_PROCESSING_LIMIT_DEFAULT
                        if FLAGS.run_mode == "dry"
                        else None
                    )
                ),
            )
        else:
            logging.info(
                "Skipping historical backfill as per 'backfill_start_date' flag."
            )
            if FLAGS.run_mode == "wet" and state_tracker:
                for ticker in tiingo_tickers:
                    ts_catch_up = state_tracker.get_last_processed_timestamp(
                        SERVICE_IDENTIFIER, f"{ticker}-catch_up"
                    )
                    if ts_catch_up:
                        last_processed_candle_timestamps[ticker] = ts_catch_up
                    else:
                        ts_backfill = state_tracker.get_last_processed_timestamp(
                            SERVICE_IDENTIFIER, f"{ticker}-backfill"
                        )
                        if ts_backfill:
                            last_processed_candle_timestamps[ticker] = ts_backfill

        run_catch_up(
            influx_manager=influx_manager,
            state_tracker=state_tracker,
            tiingo_tickers=tiingo_tickers,
            ccxt_client=ccxt_client,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=last_processed_candle_timestamps,
            run_mode=FLAGS.run_mode,
            dry_run_processing_limit=(
                FLAGS.dry_run_limit
                if FLAGS.dry_run_limit is not None
                else (
                    DRY_RUN_PROCESSING_LIMIT_DEFAULT
                    if FLAGS.run_mode == "dry"
                    else None
                )
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
        if state_tracker:
            state_tracker.close()
        if (
            redis_manager and hasattr(redis_manager, "client") and redis_manager.client
        ):
            redis_manager.close()
        elif FLAGS.run_mode == "dry" and redis_manager:
            redis_manager.close()

    logging.info("Candle ingestor script completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    app.run(main)