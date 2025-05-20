import requests
from absl import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

TENACITY_LOGGER = logging.get_absl_logger()

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    before_sleep=before_sleep_log(TENACITY_LOGGER, logging.INFO),
)
def get_top_n_crypto_symbols(api_key: str, top_n: int, convert_to_usd: bool = True) -> list[str]:
    """
    Fetches the top N cryptocurrency symbols from CoinMarketCap.
    Returns a list of Tiingo-compatible ticker symbols (e.g., 'btcusd').
    """
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    parameters = {
        'start': '1',
        'limit': str(top_n),
        'convert': 'USD' if convert_to_usd else '' # Only add convert if needed
    }
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': api_key,
    }
    symbols = []
    try:
        response = requests.get(url, params=parameters, headers=headers, timeout=10)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()

        if 'data' not in data:
            logging.error("CMC API response missing 'data' field.")
            return []

        for currency in data['data']:
            symbol = currency.get('symbol')
            if symbol:
                # Convert to Tiingo format, e.g., BTC -> btcusd
                # This assumes you are primarily interested in USD pairs for Tiingo
                tiingo_ticker = f"{symbol.lower()}usd"
                symbols.append(tiingo_ticker)
            if len(symbols) >= top_n:
                break
        logging.info(f"Fetched top {len(symbols)} symbols from CMC: {symbols}")
    # except requests.exceptions.RequestException as e: # Tenacity will handle this
    #     logging.error(f"Error calling CoinMarketCap API: {e}")
    except ValueError as e: # Includes JSONDecodeError, not typically a retryable network error
        logging.error(f"Error parsing CoinMarketCap API response: {e}")
        # Not re-raising here, as it's likely a persistent issue with the response format or data.
    return symbols
