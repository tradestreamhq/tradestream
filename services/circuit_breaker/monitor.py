"""Portfolio drawdown monitor that feeds the circuit breaker.

Periodically queries portfolio equity from the database and updates
the circuit breaker with the latest value.
"""

import asyncio
import logging
from typing import List, Optional

import asyncpg

from services.circuit_breaker.breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class DrawdownMonitor:
    """Polls portfolio equity and feeds it into the CircuitBreaker."""

    def __init__(
        self,
        breaker: CircuitBreaker,
        db_pool: asyncpg.Pool,
        poll_interval_seconds: float = 10.0,
    ):
        self._breaker = breaker
        self._db_pool = db_pool
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "Drawdown monitor started (interval=%.1fs)", self._poll_interval
        )

    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Drawdown monitor stopped")

    async def _poll_loop(self):
        while self._running:
            try:
                equity, strategies = await self._fetch_equity()
                if equity is not None:
                    self._breaker.update_equity(equity, strategies)
            except Exception:
                logger.exception("Error polling portfolio equity")
            await asyncio.sleep(self._poll_interval)

    async def _fetch_equity(self) -> tuple:
        """Query current portfolio equity and active strategies.

        Returns:
            Tuple of (total_equity, list_of_strategy_names).
        """
        equity_query = """
            SELECT
                COALESCE(SUM(unrealized_pnl), 0) as total_unrealized
            FROM paper_portfolio
        """
        realized_query = """
            SELECT COALESCE(SUM(pnl), 0) as total_realized
            FROM paper_trades
            WHERE status = 'CLOSED'
        """
        strategies_query = """
            SELECT DISTINCT strategy_name
            FROM paper_trades
            WHERE status = 'OPEN'
        """
        async with self._db_pool.acquire() as conn:
            unrealized_row = await conn.fetchrow(equity_query)
            realized_row = await conn.fetchrow(realized_query)
            strategy_rows = await conn.fetch(strategies_query)

        total_unrealized = float(unrealized_row["total_unrealized"])
        total_realized = float(realized_row["total_realized"])
        equity = total_realized + total_unrealized
        strategies = [row["strategy_name"] for row in strategy_rows]
        return equity, strategies
