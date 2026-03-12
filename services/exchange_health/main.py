"""Entry point for the Exchange Health API service."""

import logging
import os

import ccxt
import uvicorn

from services.exchange_health.app import create_app
from services.exchange_health.monitor import ExchangeHealthMonitor

logger = logging.getLogger(__name__)


def _build_exchanges() -> dict:
    """Build ccxt exchange instances from environment config.

    Expects EXCHANGE_IDS as a comma-separated list (e.g. "coinbasepro,binance").
    """
    exchange_ids = os.environ.get("EXCHANGE_IDS", "coinbasepro").split(",")
    exchanges = {}
    for eid in exchange_ids:
        eid = eid.strip()
        if not eid:
            continue
        try:
            cls = getattr(ccxt, eid)
            exchanges[eid] = cls({"enableRateLimit": True})
        except AttributeError:
            logger.warning("Unknown exchange: %s", eid)
    return exchanges


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    interval = float(os.environ.get("CHECK_INTERVAL", "30"))

    exchanges = _build_exchanges()
    monitor = ExchangeHealthMonitor(exchanges, check_interval=interval)
    monitor.start()

    app = create_app(monitor)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
