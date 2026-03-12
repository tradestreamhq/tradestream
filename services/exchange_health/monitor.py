"""Exchange health monitor service.

Periodically pings configured exchanges via ccxt to track connectivity,
latency, and rate limit consumption.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

from services.exchange_health.metrics import (
    aggregate_status,
    check_alerts,
    update_baseline,
)
from services.exchange_health.models import (
    Alert,
    ConnectionStatus,
    ExchangeHealth,
    RateLimitInfo,
)

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL = 30  # seconds


class ExchangeHealthMonitor:
    """Monitors health of configured exchange connections."""

    def __init__(
        self,
        exchanges: Dict,
        check_interval: float = DEFAULT_CHECK_INTERVAL,
    ):
        """Initialize the health monitor.

        Args:
            exchanges: Dict mapping exchange_id to ccxt exchange instances.
            check_interval: Seconds between health check pings.
        """
        self._exchanges = exchanges
        self._check_interval = check_interval
        self._health: Dict[str, ExchangeHealth] = {}
        self._alerts: List[Alert] = []
        self._task: Optional[asyncio.Task] = None

        for exchange_id in exchanges:
            self._health[exchange_id] = ExchangeHealth(exchange_id=exchange_id)

    @property
    def health(self) -> Dict[str, ExchangeHealth]:
        return self._health

    @property
    def alerts(self) -> List[Alert]:
        return list(self._alerts)

    def get_exchange_health(self, exchange_id: str) -> Optional[ExchangeHealth]:
        return self._health.get(exchange_id)

    def get_summary(self) -> Dict:
        """Return aggregate health summary and per-exchange details."""
        summary = aggregate_status(self._health)
        summary["exchanges"] = {
            eid: eh.to_dict() for eid, eh in self._health.items()
        }
        summary["recent_alerts"] = [a.to_dict() for a in self._alerts[-20:]]
        return summary

    async def check_exchange(self, exchange_id: str) -> None:
        """Perform a single health check ping for an exchange."""
        exchange = self._exchanges.get(exchange_id)
        health = self._health.get(exchange_id)
        if not exchange or not health:
            return

        start = time.monotonic()
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, exchange.fetch_time
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            health.latency.record(elapsed_ms)
            health.last_check = time.time()
            health.last_error = None

            if elapsed_ms > 5000:
                health.status = ConnectionStatus.DEGRADED
            else:
                health.status = ConnectionStatus.CONNECTED

            rate_limit = getattr(exchange, "rateLimit", None)
            if rate_limit:
                health.rate_limit = RateLimitInfo(
                    remaining=getattr(exchange, "rateLimitRemaining", rate_limit),
                    total=rate_limit,
                )

            update_baseline(health)

        except Exception as exc:
            health.status = ConnectionStatus.DISCONNECTED
            health.last_error = str(exc)
            health.last_check = time.time()
            logger.warning("Health check failed for %s: %s", exchange_id, exc)

        new_alerts = check_alerts(health)
        if new_alerts:
            self._alerts.extend(new_alerts)
            # Keep alert history bounded
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]

    async def check_all(self) -> None:
        """Run health checks for all configured exchanges."""
        tasks = [self.check_exchange(eid) for eid in self._exchanges]
        await asyncio.gather(*tasks)

    async def _run_loop(self) -> None:
        """Background loop that periodically checks all exchanges."""
        while True:
            try:
                await self.check_all()
            except Exception:
                logger.exception("Error in health check loop")
            await asyncio.sleep(self._check_interval)

    def start(self) -> None:
        """Start the background health check loop."""
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._run_loop())

    def stop(self) -> None:
        """Stop the background health check loop."""
        if self._task and not self._task.done():
            self._task.cancel()
