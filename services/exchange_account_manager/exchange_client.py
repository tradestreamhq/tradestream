"""Mock exchange client for balance fetching.

In production this would call real exchange APIs (via ccxt or direct REST).
The mock implementation allows development and testing without live keys.
"""

import logging
import random
from typing import Dict

logger = logging.getLogger(__name__)

# Simulated balances keyed by exchange name.
_MOCK_BALANCES: Dict[str, Dict[str, float]] = {
    "binance": {"BTC": 0.52, "ETH": 4.1, "USDT": 12500.0},
    "coinbase": {"BTC": 0.15, "ETH": 2.0, "USD": 8300.0},
    "kraken": {"BTC": 1.0, "ETH": 10.0, "USD": 5000.0},
}

# Rough USD prices for estimating total value.
_MOCK_PRICES: Dict[str, float] = {
    "BTC": 65000.0,
    "ETH": 3500.0,
    "USDT": 1.0,
    "USD": 1.0,
}


async def fetch_balances(exchange: str, api_key: str, api_secret: str) -> Dict[str, float]:
    """Return balances for the given exchange account.

    Currently returns mock data.  Replace with ccxt calls for production.
    """
    base = _MOCK_BALANCES.get(exchange.lower(), {"USDT": 1000.0})
    # Add slight randomness to simulate live balance changes.
    return {asset: round(amount * random.uniform(0.98, 1.02), 8) for asset, amount in base.items()}


def estimate_usd(balances: Dict[str, float]) -> float:
    """Estimate total USD value of *balances*."""
    return sum(
        amount * _MOCK_PRICES.get(asset, 0.0) for asset, amount in balances.items()
    )
