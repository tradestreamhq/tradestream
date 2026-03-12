"""Client for fetching exchange-reported positions via CCXT."""

import logging
from typing import Dict, List

import ccxt

from services.reconciliation.models import PositionSnapshot

logger = logging.getLogger(__name__)


class ExchangePositionClient:
    """Fetches current balances/positions from an exchange using CCXT."""

    def __init__(self, exchange_name: str, api_key: str, secret: str):
        config = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "timeout": 30000,
        }
        try:
            self.exchange = getattr(ccxt, exchange_name)(config)
            self.exchange_name = exchange_name
            logger.info("Initialized exchange client for %s", exchange_name)
        except AttributeError:
            raise ValueError(f"Exchange '{exchange_name}' not supported by CCXT")

    def fetch_positions(self) -> List[PositionSnapshot]:
        """Fetch all non-zero balances from the exchange as positions."""
        balance = self.exchange.fetch_balance()
        positions = []
        total = balance.get("total", {})
        for asset, amount in total.items():
            if amount and float(amount) != 0.0:
                positions.append(
                    PositionSnapshot(
                        symbol=asset,
                        quantity=float(amount),
                        avg_entry_price=0.0,  # Exchanges don't report avg entry
                    )
                )
        return positions
