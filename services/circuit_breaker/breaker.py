"""Core circuit breaker logic for portfolio drawdown protection.

The CircuitBreaker tracks portfolio equity against its peak value and
triggers protective actions when drawdown exceeds configured thresholds.
After a halt or emergency trigger, manual acknowledgment is required
before trading can resume.
"""

import logging
import threading
import time
from typing import Callable, List, Optional

from services.circuit_breaker.models import (
    BreakerEvent,
    BreakerLevel,
    BreakerState,
    ThresholdConfig,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Monitors portfolio drawdown and halts trading when thresholds are breached."""

    def __init__(
        self,
        thresholds: Optional[ThresholdConfig] = None,
        on_trigger: Optional[Callable[[BreakerEvent], None]] = None,
    ):
        self._thresholds = thresholds or ThresholdConfig()
        self._on_trigger = on_trigger
        self._lock = threading.Lock()
        self._state = BreakerState()

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return BreakerState(
                level=self._state.level,
                drawdown_pct=self._state.drawdown_pct,
                peak_equity=self._state.peak_equity,
                current_equity=self._state.current_equity,
                is_halted=self._state.is_halted,
                halted_strategies=list(self._state.halted_strategies),
                last_triggered_at=self._state.last_triggered_at,
                reset_acknowledged=self._state.reset_acknowledged,
                events=list(self._state.events[-50:]),
            )

    @property
    def thresholds(self) -> ThresholdConfig:
        return self._thresholds

    def update_equity(self, equity: float, strategies: Optional[List[str]] = None):
        """Update current equity and evaluate drawdown thresholds.

        Args:
            equity: Current total portfolio equity.
            strategies: List of active strategy identifiers.
        """
        with self._lock:
            self._state.current_equity = equity

            if equity > self._state.peak_equity:
                self._state.peak_equity = equity

            if self._state.peak_equity <= 0:
                return

            drawdown = (self._state.peak_equity - equity) / self._state.peak_equity
            self._state.drawdown_pct = drawdown

            new_level = self._classify(drawdown)

            if new_level.value > self._state.level.value or (
                new_level == BreakerLevel.NORMAL
                and self._state.level == BreakerLevel.WARNING
            ):
                self._transition(new_level, drawdown, strategies or [])

    def _classify(self, drawdown: float) -> BreakerLevel:
        if drawdown >= self._thresholds.emergency:
            return BreakerLevel.EMERGENCY
        if drawdown >= self._thresholds.halt:
            return BreakerLevel.HALT
        if drawdown >= self._thresholds.warning:
            return BreakerLevel.WARNING
        return BreakerLevel.NORMAL

    def _transition(
        self, level: BreakerLevel, drawdown: float, strategies: List[str]
    ):
        prev = self._state.level
        self._state.level = level

        event = BreakerEvent(
            level=level,
            drawdown_pct=drawdown,
            peak_equity=self._state.peak_equity,
            current_equity=self._state.current_equity,
            message=f"Circuit breaker: {prev.value} -> {level.value} "
            f"(drawdown {drawdown:.2%})",
        )
        self._state.events.append(event)

        if level in (BreakerLevel.HALT, BreakerLevel.EMERGENCY):
            self._state.is_halted = True
            self._state.halted_strategies = list(strategies)
            self._state.last_triggered_at = time.time()
            self._state.reset_acknowledged = False
            logger.warning(event.message)
        elif level == BreakerLevel.WARNING:
            logger.warning(event.message)
        else:
            logger.info(event.message)

        if self._on_trigger:
            self._on_trigger(event)

    def reset(self, acknowledged_by: str) -> bool:
        """Reset the circuit breaker after manual acknowledgment.

        Args:
            acknowledged_by: Identifier of who is acknowledging the reset.

        Returns:
            True if reset was successful, False if breaker is not in halted state.
        """
        with self._lock:
            if not self._state.is_halted:
                return False

            prev_level = self._state.level
            self._state.level = BreakerLevel.NORMAL
            self._state.is_halted = False
            self._state.halted_strategies = []
            self._state.reset_acknowledged = True

            event = BreakerEvent(
                level=BreakerLevel.NORMAL,
                drawdown_pct=self._state.drawdown_pct,
                peak_equity=self._state.peak_equity,
                current_equity=self._state.current_equity,
                message=f"Circuit breaker reset by {acknowledged_by} "
                f"(was {prev_level.value})",
            )
            self._state.events.append(event)
            logger.info(event.message)

            if self._on_trigger:
                self._on_trigger(event)

            return True

    def is_trading_allowed(self) -> bool:
        """Check whether trading is currently permitted."""
        with self._lock:
            return not self._state.is_halted
