from datetime import datetime, timezone
import time  # Added for sleep

from absl import logging
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)


# Custom retry condition for Tiingo HTTP 429
def _retry_if_tiingo_rate_limit_or_request_exception(exception):
    if (
        isinstance(exception, requests.exceptions.HTTPError)
        and exception.response.status_code == 429
    ):
        retry_after_header = exception.response.headers.get("Retry-After")
        if retry_after_header:
            try:
                sleep_seconds = int(retry_after_header)
                logging.warning(
                    f"Tiingo API rate limit hit (429). Retrying after {sleep_seconds} seconds."
                )
                time.sleep(sleep_seconds)
                return True  # Indicate that we should retry
            except ValueError:
                logging.error(
                    f"Tiingo API rate limit hit (429) but could not parse Retry-After header: {retry_after_header}. Will use default backoff."
                )
        else:
            logging.warning(
                "Tiingo API rate limit hit (429) but no Retry-After header found. Will use default backoff."
            )
        return True  # Still retry for 429, tenacity will handle wait if sleep didn't happen
    # For other request exceptions, let tenacity handle it
    return isinstance(exception, requests.exceptions.RequestException)


@retry(
    stop=stop_after_attempt(7),
    wait=wait_exponential(multiplier=1, min=5, max=120),
    retry=_retry_if_tiingo_rate_limit_or_request_exception,
    reraise=True,
)
def _fetch_tiingo_data_with_retry(url: str, params: dict, headers: dict) -> dict:
    """Internal function to fetch data from Tiingo with retry logic."""
    logging.info(f"Attempting to fetch data from Tiingo: {url} with params: {params}")
    response = requests.get(url, params=params, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def get_top_n_crypto_symbols(
    api_key: str, top_n: int, convert_to_usd: bool = True
) -> list[str]:
    """
    Fetches the top N cryptocurrency symbols from CoinMarketCap.
    Returns a list of Tiingo-compatible ticker symbols (e.g., 'btcusd').
    """
    # This function remains unchanged as per the PR description for tiingo_client.py focus.
    # Assuming _fetch_cmc_data_with_retry is defined in cmc_client.py and handles its own retries.
    # If retries were also needed here for CMC within this file, _fetch_cmc_data_with_retry would be used.
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    parameters = {
        "start": "1",
        "limit": str(top_n),
        "convert": "USD" if convert_to_usd else "",
    }
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": api_key,
    }
    symbols = []
    try:
        response = requests.get(url, params=parameters, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" not in data:
            logging.error("CMC API response missing 'data' field.")
            return []

        for currency in data["data"]:
            symbol = currency.get("symbol")
            if symbol:
                tiingo_ticker = f"{symbol.lower()}usd"
                symbols.append(tiingo_ticker)
            if len(symbols) >= top_n:
                break
        logging.info(f"Fetched top {len(symbols)} symbols from CMC: {symbols}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling CoinMarketCap API: {e}")
    except ValueError as e:  # Includes JSONDecodeError
        logging.error(f"Error parsing CoinMarketCap API response: {e}")
    return symbols


def _parse_tiingo_timestamp(date_str: str) -> int:
    """Parses Tiingo's timestamp and returns epoch milliseconds UTC."""
    try:
        dt_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        else:
            dt_obj = dt_obj.astimezone(timezone.utc)
        return int(dt_obj.timestamp() * 1000)
    except ValueError:
        # Fallback for just date, assume start of day UTC
        dt_obj = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt_obj.timestamp() * 1000)


def get_historical_candles_tiingo(
    api_key: str,
    ticker: str,  # e.g., "btcusd"
    start_date_str: str,  # YYYY-MM-DD
    end_date_str: str,  # YYYY-MM-DD
    resample_freq: str,  # e.g., "1min", "1hour", "1day"
) -> list[dict]:
    """
    Fetches historical candles from Tiingo for a single ticker.
    Returns a list of dictionaries, each representing a candle.
    """
    base_url = "https://api.tiingo.com/tiingo/crypto/prices"
    params = {
        "tickers": ticker,
        "startDate": start_date_str,
        "endDate": end_date_str,
        "resampleFreq": resample_freq,
        "token": api_key,
        "format": "json",
    }
    headers = {"Content-Type": "application/json"}
    candles_data = []
    try:
        data = _fetch_tiingo_data_with_retry(base_url, params, headers)

        if not data:
            logging.info(
                f"No historical data returned from Tiingo for {ticker} for the period {start_date_str} to {end_date_str}."
            )
            return []

        if isinstance(data, list) and len(data) > 0:
            ticker_data_list = data[0]  # First element is for the requested ticker
            if (
                ticker_data_list.get("ticker", "").lower() == ticker.lower()
                and "priceData" in ticker_data_list
            ):
                for candle_item in ticker_data_list["priceData"]:
                    try:
                        candles_data.append(
                            {
                                "timestamp_ms": _parse_tiingo_timestamp(
                                    candle_item["date"]
                                ),
                                "open": float(candle_item["open"]),
                                "high": float(candle_item["high"]),
                                "low": float(candle_item["low"]),
                                "close": float(candle_item["close"]),
                                "volume": float(candle_item["volume"]),
                                "currency_pair": ticker,
                            }
                        )
                    except (TypeError, ValueError, KeyError) as field_e:
                        logging.warning(
                            f"Skipping malformed candle item for {ticker} due to {field_e}: {candle_item}"
                        )

                logging.info(
                    f"Fetched {len(candles_data)} historical candles for {ticker} from Tiingo."
                )
            else:
                logging.warning(
                    f"Unexpected data structure or ticker mismatch for {ticker} in Tiingo response: {data}"
                )
        else:
            logging.warning(
                f"Unexpected response format (empty list or not a list) from Tiingo for {ticker}: {data}"
            )
    except RetryError as retry_err:
        logging.error(
            f"Tiingo API request failed after multiple retries for {ticker}: {retry_err}"
        )
    except requests.exceptions.HTTPError as http_err:
        # This might be redundant if RetryError catches it, but good for other HTTP errors not retried
        logging.error(
            f"HTTP error calling Tiingo API for {ticker} ({start_date_str} to {end_date_str}): {http_err.response.status_code} - {http_err.response.text}"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error calling Tiingo API for {ticker}: {e}")
    except ValueError as e:  # Includes JSONDecodeError
        logging.error(f"Error parsing Tiingo API response for {ticker}: {e}")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred fetching historical data for {ticker}: {e}"
        )
    return candles_data
