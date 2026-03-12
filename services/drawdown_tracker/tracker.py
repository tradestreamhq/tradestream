"""
Drawdown recovery tracker — analyses equity curves to identify drawdown events,
measure recovery progress, and estimate time-to-recovery.
"""

import logging
import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from services.drawdown_tracker.models import (
    CurrentDrawdown,
    DrawdownEvent,
    DrawdownState,
    DrawdownSummary,
)

logger = logging.getLogger(__name__)

# Minimum drawdown depth (%) to count as a distinct event
_MIN_DRAWDOWN_PCT = 0.5


def build_drawdown_events(
    equity_curve: List[Tuple[datetime, float]],
    min_drawdown_pct: float = _MIN_DRAWDOWN_PCT,
) -> List[DrawdownEvent]:
    """Walk an equity curve and extract discrete drawdown events.

    Args:
        equity_curve: chronological list of (timestamp, equity_value) pairs.
        min_drawdown_pct: ignore drawdowns shallower than this (percentage).

    Returns:
        List of DrawdownEvent instances, most recent last.
    """
    if len(equity_curve) < 2:
        return []

    events: List[DrawdownEvent] = []
    peak = equity_curve[0][1]
    peak_date = equity_curve[0][0]
    trough = peak
    trough_date = peak_date
    in_drawdown = False
    dd_start: Optional[datetime] = None

    for ts, equity in equity_curve[1:]:
        if equity >= peak:
            # New high — close any open drawdown
            if in_drawdown:
                depth = _pct_drop(peak, trough)
                if depth >= min_drawdown_pct:
                    events.append(
                        DrawdownEvent(
                            start_date=dd_start,
                            trough_date=trough_date,
                            recovery_date=ts,
                            peak_equity=peak,
                            trough_equity=trough,
                            depth_pct=depth,
                            duration_days=(ts - dd_start).days,
                            recovery_days=(ts - trough_date).days,
                            state=DrawdownState.RECOVERED,
                        )
                    )
                in_drawdown = False
            peak = equity
            peak_date = ts
            trough = equity
            trough_date = ts
        else:
            if not in_drawdown:
                in_drawdown = True
                dd_start = peak_date
            if equity < trough:
                trough = equity
                trough_date = ts

    # If still in drawdown at the end of the curve
    if in_drawdown:
        depth = _pct_drop(peak, trough)
        current_equity = equity_curve[-1][1]
        if depth >= min_drawdown_pct:
            state = (
                DrawdownState.RECOVERING
                if current_equity > trough
                else DrawdownState.IN_DRAWDOWN
            )
            events.append(
                DrawdownEvent(
                    start_date=dd_start,
                    trough_date=trough_date,
                    recovery_date=None,
                    peak_equity=peak,
                    trough_equity=trough,
                    depth_pct=depth,
                    duration_days=(equity_curve[-1][0] - dd_start).days,
                    recovery_days=None,
                    state=state,
                )
            )

    return events


def compute_current_drawdown(
    equity_curve: List[Tuple[datetime, float]],
    events: List[DrawdownEvent],
) -> CurrentDrawdown:
    """Derive the current drawdown snapshot from equity curve and events."""
    if not equity_curve:
        return CurrentDrawdown(
            state=DrawdownState.AT_PEAK,
            peak_equity=0.0,
            current_equity=0.0,
            trough_equity=0.0,
            drawdown_pct=0.0,
            recovery_pct=100.0,
            drawdown_start=None,
            estimated_recovery_days=None,
        )

    current_equity = equity_curve[-1][1]
    peak = max(eq for _, eq in equity_curve)

    # Check if the last event is still open (no recovery date)
    open_event = events[-1] if events and events[-1].recovery_date is None else None

    if open_event:
        dd_pct = _pct_drop(open_event.peak_equity, current_equity)
        trough = open_event.trough_equity
        # Recovery progress: 0% at trough, 100% at peak
        if open_event.peak_equity > trough:
            recovery_pct = (
                (current_equity - trough) / (open_event.peak_equity - trough) * 100
            )
        else:
            recovery_pct = 100.0

        est_days = estimate_recovery_days(
            open_event, current_equity, equity_curve, events
        )

        state = (
            DrawdownState.RECOVERING
            if current_equity > trough
            else DrawdownState.IN_DRAWDOWN
        )
        return CurrentDrawdown(
            state=state,
            peak_equity=open_event.peak_equity,
            current_equity=current_equity,
            trough_equity=trough,
            drawdown_pct=dd_pct,
            recovery_pct=max(0.0, min(recovery_pct, 100.0)),
            drawdown_start=open_event.start_date,
            estimated_recovery_days=est_days,
        )

    return CurrentDrawdown(
        state=DrawdownState.AT_PEAK,
        peak_equity=peak,
        current_equity=current_equity,
        trough_equity=current_equity,
        drawdown_pct=0.0,
        recovery_pct=100.0,
        drawdown_start=None,
        estimated_recovery_days=None,
    )


def estimate_recovery_days(
    open_event: DrawdownEvent,
    current_equity: float,
    equity_curve: List[Tuple[datetime, float]],
    all_events: List[DrawdownEvent],
) -> Optional[int]:
    """Estimate days until equity recovers to its prior peak.

    Uses two signals and averages them:
    1. Current trajectory: linear projection from trough toward peak.
    2. Historical average: mean recovery speed from past events.
    """
    peak = open_event.peak_equity
    trough = open_event.trough_equity

    if current_equity >= peak:
        return 0
    if current_equity <= trough:
        # No recovery progress — fall back to historical average only
        return _historical_estimate(all_events, open_event.depth_pct)

    remaining = peak - current_equity
    recovered = current_equity - trough

    # Days since trough
    now_ts = equity_curve[-1][0]
    days_since_trough = max((now_ts - open_event.trough_date).days, 1)

    # Trajectory estimate: remaining / recovery_rate
    rate = recovered / days_since_trough
    trajectory_est = math.ceil(remaining / rate) if rate > 0 else None

    hist_est = _historical_estimate(all_events, open_event.depth_pct)

    estimates = [e for e in [trajectory_est, hist_est] if e is not None]
    if not estimates:
        return None
    return round(sum(estimates) / len(estimates))


def build_summary(
    strategy_id: str,
    equity_curve: List[Tuple[datetime, float]],
) -> DrawdownSummary:
    """Build a complete drawdown summary for a strategy."""
    events = build_drawdown_events(equity_curve)
    current = compute_current_drawdown(equity_curve, events)

    depths = [e.depth_pct for e in events]
    max_dd = max(depths) if depths else 0.0
    avg_dd = sum(depths) / len(depths) if depths else 0.0

    completed = [e for e in events if e.recovery_days is not None]
    avg_recovery = (
        sum(e.recovery_days for e in completed) / len(completed)
        if completed
        else None
    )

    return DrawdownSummary(
        strategy_id=strategy_id,
        current=current,
        historical_events=events,
        max_drawdown_pct=max_dd,
        avg_drawdown_pct=avg_dd,
        avg_recovery_days=avg_recovery,
        total_drawdown_events=len(events),
    )


# --- helpers ---


def _pct_drop(peak: float, current: float) -> float:
    """Percentage drop from peak, returned as positive number."""
    if peak <= 0:
        return 0.0
    return (peak - current) / peak * 100


def _historical_estimate(
    events: List[DrawdownEvent], current_depth: float
) -> Optional[int]:
    """Estimate recovery days from historical events of comparable depth."""
    completed = [
        e
        for e in events
        if e.recovery_days is not None and e.depth_pct >= current_depth * 0.5
    ]
    if not completed:
        return None
    avg_days = sum(e.recovery_days for e in completed) / len(completed)
    return math.ceil(avg_days)
