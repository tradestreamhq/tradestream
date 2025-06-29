import requests
from absl import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True,
)
def _fetch_cmc_data_with_retry(url: str, parameters: dict, headers: dict) -> dict:
    """Internal function to fetch data with retry logic."""
    logging.info(f"Attempting to fetch data from CMC: {url} with params: {parameters}")
    response = requests.get(url, params=parameters, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def get_top_n_crypto_symbols(
    api_key: str, top_n: int, convert_to_usd: bool = True
) -> list[str]:
    """
    Fetches the top N cryptocurrency symbols from CoinMarketCap.
    Returns a list of Tiingo-compatible ticker symbols (e.g., 'btcusd').
    """
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
        data = _fetch_cmc_data_with_retry(url, parameters, headers)

        if "data" not in data:
            logging.error("CMC API response missing 'data' field.")
            return []

        for currency in data["data"]:
            symbol = currency.get("symbol")
            if symbol:
                # Convert to Tiingo format, e.g., BTC -> btcusd
                # This assumes you are primarily interested in USD pairs for Tiingo
                tiingo_ticker = f"{symbol.lower()}usd"
                symbols.append(tiingo_ticker)
            if len(symbols) >= top_n:
                break
        logging.info(f"Fetched top {len(symbols)} symbols from CMC: {symbols}")
    except RetryError as retry_err:  # Catch tenacity's RetryError
        logging.error(
            f"Error calling CoinMarketCap API after multiple retries: {retry_err}"
        )
    except (
        requests.exceptions.RequestException
    ) as e:  # Should be caught by tenacity, but as a fallback
        logging.error(f"Error calling CoinMarketCap API: {e}")
    except ValueError as e:  # Includes JSONDecodeError
        logging.error(f"Error parsing CoinMarketCap API response: {e}")
    return symbols
