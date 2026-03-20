"""Autonomous risk management for the signal pipeline.

Enforces position sizing, max concurrent signals, drawdown limits,
and per-symbol rate limits before signals are acted upon.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from services.autonomous_runner.signal_fusion import FusedSignal, SignalAction

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of a risk management check."""

    approved: bool
    original_signal: Optional[FusedSignal] = None
    adjusted_confidence: Optional[float] = None
    position_size_pct: float = 0.0
    rejection_reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class RiskManager:
    """Enforces risk limits on autonomous signal generation.

    Tracks:
    - Active signals per symbol (rate limiting)
    - Total portfolio exposure
    - Daily P&L for drawdown limits
    - Concurrent open signal count
    """

    def __init__(self, config):
        self.config = config
        self._signal_history = defaultdict(list)  # symbol -> list of timestamps
        self._active_signals = 0
        self._daily_pnl_pct = 0.0
        self._max_drawdown_pct = 0.0
        self._portfolio_exposure_pct = 0.0

    def check_signal(self, signal: FusedSignal) -> RiskCheckResult:
        """Run all risk checks on a fused signal.

        Returns RiskCheckResult indicating whether the signal is approved.
        """
        reasons = []
        warnings = []

        # 1. Minimum confidence threshold
        if signal.confidence < self.config.min_confidence_threshold:
            reasons.append(
                f"Confidence {signal.confidence:.2f} below threshold "
                f"{self.config.min_confidence_threshold:.2f}"
            )

        # 2. HOLD signals are always approved (no risk)
        if signal.action == SignalAction.HOLD:
            return RiskCheckResult(
                approved=True,
                original_signal=signal,
                adjusted_confidence=signal.confidence,
                position_size_pct=0.0,
            )

        # 3. Max concurrent signals
        if self._active_signals >= self.config.max_concurrent_signals:
            reasons.append(
                f"Max concurrent signals ({self.config.max_concurrent_signals}) reached"
            )

        # 4. Per-symbol rate limit
        now = time.time()
        hour_ago = now - 3600
        recent = [
            ts
            for ts in self._signal_history[signal.symbol]
            if ts > hour_ago
        ]
        self._signal_history[signal.symbol] = recent

        if len(recent) >= self.config.max_signals_per_symbol_per_hour:
            reasons.append(
                f"Symbol {signal.symbol} has {len(recent)} signals in the last hour "
                f"(max {self.config.max_signals_per_symbol_per_hour})"
            )

        # 5. Portfolio exposure
        if self._portfolio_exposure_pct >= self.config.max_portfolio_exposure_pct:
            reasons.append(
                f"Portfolio exposure {self._portfolio_exposure_pct:.1f}% at max "
                f"{self.config.max_portfolio_exposure_pct:.1f}%"
            )

        # 6. Daily drawdown limit
        if self._daily_pnl_pct <= -self.config.max_daily_loss_pct:
            reasons.append(
                f"Daily loss {self._daily_pnl_pct:.2f}% exceeds limit "
                f"-{self.config.max_daily_loss_pct:.1f}%"
            )

        # 7. Max drawdown
        if self._max_drawdown_pct >= self.config.max_drawdown_pct:
            reasons.append(
                f"Max drawdown {self._max_drawdown_pct:.2f}% exceeds limit "
                f"{self.config.max_drawdown_pct:.1f}%"
            )

        if reasons:
            return RiskCheckResult(
                approved=False,
                original_signal=signal,
                rejection_reasons=reasons,
                warnings=warnings,
            )

        # Calculate position size
        position_size = self._calculate_position_size(signal)

        # Adjust confidence for portfolio state
        adjusted_confidence = self._adjust_confidence(signal)

        if adjusted_confidence < self.config.min_confidence_threshold:
            reasons.append(
                f"Adjusted confidence {adjusted_confidence:.2f} below threshold "
                f"after risk adjustments"
            )
            return RiskCheckResult(
                approved=False,
                original_signal=signal,
                adjusted_confidence=adjusted_confidence,
                rejection_reasons=reasons,
                warnings=warnings,
            )

        return RiskCheckResult(
            approved=True,
            original_signal=signal,
            adjusted_confidence=adjusted_confidence,
            position_size_pct=position_size,
            warnings=warnings,
        )

    def record_signal_emitted(self, symbol: str):
        """Record that a signal was emitted for tracking."""
        self._signal_history[symbol].append(time.time())
        self._active_signals += 1

    def record_signal_closed(self, symbol: str, pnl_pct: float):
        """Record that a signal position was closed."""
        self._active_signals = max(0, self._active_signals - 1)
        self._daily_pnl_pct += pnl_pct
        if self._daily_pnl_pct < -self._max_drawdown_pct:
            self._max_drawdown_pct = abs(self._daily_pnl_pct)

    def update_portfolio_exposure(self, exposure_pct: float):
        """Update current portfolio exposure percentage."""
        self._portfolio_exposure_pct = exposure_pct

    def reset_daily(self):
        """Reset daily metrics (called at market open)."""
        self._daily_pnl_pct = 0.0

    def _calculate_position_size(self, signal: FusedSignal) -> float:
        """Calculate position size as a percentage of portfolio.

        Higher confidence -> larger position, capped at max_single_position_pct.
        """
        max_pct = self.config.max_single_position_pct
        remaining_exposure = (
            self.config.max_portfolio_exposure_pct - self._portfolio_exposure_pct
        )
        cap = min(max_pct, remaining_exposure)

        # Scale by confidence: low confidence = smaller position
        size = cap * signal.confidence
        return max(0.0, min(cap, size))

    def _adjust_confidence(self, signal: FusedSignal) -> float:
        """Adjust signal confidence based on portfolio risk state."""
        confidence = signal.confidence

        # Penalize when approaching exposure limits
        exposure_ratio = self._portfolio_exposure_pct / self.config.max_portfolio_exposure_pct
        if exposure_ratio > 0.7:
            penalty = (exposure_ratio - 0.7) * 0.3  # up to 9% penalty
            confidence -= penalty

        # Penalize when in drawdown
        if self._daily_pnl_pct < 0:
            loss_ratio = abs(self._daily_pnl_pct) / self.config.max_daily_loss_pct
            if loss_ratio > 0.5:
                penalty = (loss_ratio - 0.5) * 0.2  # up to 10% penalty
                confidence -= penalty

        return max(0.0, confidence)

    def get_status(self) -> dict:
        """Return current risk manager status."""
        return {
            "active_signals": self._active_signals,
            "max_concurrent_signals": self.config.max_concurrent_signals,
            "daily_pnl_pct": round(self._daily_pnl_pct, 4),
            "max_drawdown_pct": round(self._max_drawdown_pct, 4),
            "portfolio_exposure_pct": round(self._portfolio_exposure_pct, 2),
            "limits": {
                "max_daily_loss_pct": self.config.max_daily_loss_pct,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "max_portfolio_exposure_pct": self.config.max_portfolio_exposure_pct,
                "min_confidence": self.config.min_confidence_threshold,
            },
        }
