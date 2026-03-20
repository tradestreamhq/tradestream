"""Outcome tracker for autonomous pipeline decisions.

Periodically checks emitted signals against actual market data
to record outcomes in the decision_outcomes table. This enables
the learning feedback loop and accuracy tracking.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from services.autonomous_runner.db_persistence import DecisionPersistence

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_TARGET_RETURN_PCT = 1.0  # 1% target


@dataclass
class OutcomeConfig:
    """Configuration for outcome tracking."""

    check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS
    target_return_pct: float = DEFAULT_TARGET_RETURN_PCT


@dataclass
class OutcomeResult:
    """Result of checking a single decision's outcome."""

    decision_id: str
    symbol: str
    action: str
    entry_confidence: float
    actual_return: float = 0.0
    hit_target: bool = False
    max_drawdown: float = 0.0
    exit_price: Optional[float] = None
    entry_price: Optional[float] = None


class OutcomeTracker:
    """Tracks outcomes for emitted signals.

    Compares decision entry conditions against subsequent market
    data to determine if the signal was profitable.
    """

    def __init__(
        self,
        db: DecisionPersistence,
        mcp_call_fn: Optional[Callable] = None,
        entry_price_fn: Optional[Callable] = None,
        config: Optional[OutcomeConfig] = None,
    ):
        self._db = db
        self._mcp_call = mcp_call_fn
        self._entry_price_fn = entry_price_fn
        self.config = config or OutcomeConfig()
        self._stats = {
            "outcomes_recorded": 0,
            "outcomes_hit": 0,
            "outcomes_missed": 0,
            "check_errors": 0,
            "last_check_at": None,
        }

    def check_pending_outcomes(self) -> list:
        """Check all pending decisions for outcomes.

        Queries decisions that have been emitted but don't yet
        have recorded outcomes, then checks current prices.
        """
        if not self._db.is_available:
            return []

        pending = self._get_pending_decisions()
        if not pending:
            return []

        results = []
        for decision in pending:
            try:
                result = self._evaluate_decision(decision)
                if result:
                    self._db.record_outcome(
                        decision_id=result.decision_id,
                        actual_return=result.actual_return,
                        hit_target=result.hit_target,
                        exit_price=result.exit_price,
                        max_drawdown=result.max_drawdown,
                    )
                    self._stats["outcomes_recorded"] += 1
                    if result.hit_target:
                        self._stats["outcomes_hit"] += 1
                    else:
                        self._stats["outcomes_missed"] += 1
                    results.append(result)
            except Exception as e:
                logger.error(
                    "Failed to evaluate outcome for %s: %s",
                    decision.get("decision_id"),
                    e,
                )
                self._stats["check_errors"] += 1

        self._stats["last_check_at"] = time.time()
        return results

    def _get_pending_decisions(self) -> list:
        """Get decisions that need outcome evaluation."""
        if not self._db.is_available:
            return []

        try:
            decisions = self._db.get_recent_decisions(limit=100)
            return [
                d
                for d in decisions
                if d.get("risk_approved", False) and d.get("action") != "HOLD"
            ]
        except Exception as e:
            logger.error("Failed to get pending decisions: %s", e)
            return []

    def _evaluate_decision(self, decision: dict) -> Optional[OutcomeResult]:
        """Evaluate a single decision against current market data."""
        symbol = decision.get("symbol", "")
        action = decision.get("action", "HOLD")
        confidence = decision.get("confidence", 0.0)
        decision_id = decision.get("decision_id", "")

        if not symbol or action == "HOLD":
            return None

        # Get current price via MCP if available
        current_price = self._get_current_price(symbol)
        if current_price is None:
            return None

        # Get entry price from coordinator's tracking
        entry_price = None
        if self._entry_price_fn:
            entry_price = self._entry_price_fn(decision_id)

        # Fall back to market_context entry price
        if entry_price is None:
            market_ctx = decision.get("market_context", {})
            if isinstance(market_ctx, dict):
                entry_price = market_ctx.get("current_price")

        if entry_price is None or entry_price <= 0:
            return None

        # Compute actual return
        price_change_pct = (current_price - entry_price) / entry_price
        actual_return = price_change_pct if action == "BUY" else -price_change_pct

        target_return = self.config.target_return_pct / 100.0
        hit = actual_return >= target_return

        return OutcomeResult(
            decision_id=decision_id,
            symbol=symbol,
            action=action,
            entry_confidence=confidence,
            actual_return=round(actual_return, 6),
            hit_target=hit,
            max_drawdown=round(abs(min(0, actual_return)), 6),
            exit_price=current_price,
            entry_price=entry_price,
        )

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol via MCP."""
        if not self._mcp_call:
            return None

        try:
            result = self._mcp_call("get_latest_price", {"symbol": symbol})
            if isinstance(result, dict):
                return result.get("price", result.get("current_price"))
            if isinstance(result, (int, float)):
                return float(result)
        except Exception as e:
            logger.debug("Price fetch failed for %s: %s", symbol, e)
        return None

    def get_stats(self) -> dict:
        """Return outcome tracking statistics."""
        total = self._stats["outcomes_recorded"]
        hit_rate = self._stats["outcomes_hit"] / total if total > 0 else 0.0
        return {
            **self._stats,
            "hit_rate": round(hit_rate, 4),
            "pending_config": {
                "check_interval_seconds": self.config.check_interval_seconds,
                "lookback_hours": self.config.lookback_hours,
                "target_return_pct": self.config.target_return_pct,
            },
        }
