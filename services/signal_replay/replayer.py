"""Signal replay service for strategy debugging and analysis.

Replays historical trade signals through a strategy simulation,
producing a step-by-step decision log for debugging and analysis.
"""

from collections.abc import Generator

from services.signal_replay.models import (
    DecisionLogEntry,
    HistoricalSignal,
    ReplayConfig,
    ReplayDecision,
    ReplayResult,
    SignalAction,
    StrategyState,
)


def _make_flat_state(realized_pnl: float = 0.0, trade_count: int = 0) -> StrategyState:
    """Create a flat (no position) strategy state."""
    return StrategyState(
        position="FLAT",
        realized_pnl=realized_pnl,
        trade_count=trade_count,
    )


class SignalReplayer:
    """Replays historical signals and simulates strategy decisions step by step.

    Supports two modes:
    - Step-through: advance one signal at a time via `step()`
    - Batch: replay all signals at once via `replay_all()`
    """

    def __init__(self, config: ReplayConfig, signals: list[HistoricalSignal]):
        self._config = config
        self._signals = self._filter_and_sort(signals)
        self._state = _make_flat_state()
        self._step_index = 0
        self._decision_log: list[DecisionLogEntry] = []

    def _filter_and_sort(self, signals: list[HistoricalSignal]) -> list[HistoricalSignal]:
        """Filter signals by config criteria and sort by timestamp."""
        filtered = [
            s
            for s in signals
            if s.symbol == self._config.symbol
            and s.strategy_name == self._config.strategy_name
            and (self._config.start_timestamp_ms == 0 or s.timestamp_ms >= self._config.start_timestamp_ms)
            and (self._config.end_timestamp_ms == 0 or s.timestamp_ms <= self._config.end_timestamp_ms)
        ]
        return sorted(filtered, key=lambda s: s.timestamp_ms)

    @property
    def state(self) -> StrategyState:
        """Current strategy state."""
        return self._state

    @property
    def signals(self) -> list[HistoricalSignal]:
        """Filtered and sorted signals for this replay."""
        return self._signals

    @property
    def decision_log(self) -> list[DecisionLogEntry]:
        """Decision log entries produced so far."""
        return self._decision_log

    @property
    def is_complete(self) -> bool:
        """Whether all signals have been replayed."""
        return self._step_index >= len(self._signals)

    def _evaluate_signal(self, signal: HistoricalSignal) -> tuple[ReplayDecision, str]:
        """Determine what decision the strategy makes given the signal and current state."""
        position = self._state.position

        if signal.action == SignalAction.STOP_LOSS and position == "LONG":
            return ReplayDecision.STOP_OUT, "Stop loss triggered"

        if signal.action == SignalAction.BUY:
            if position == "FLAT":
                return ReplayDecision.ENTER_LONG, f"Buy signal at {signal.price}"
            return ReplayDecision.HOLD, "Already in position, holding"

        if signal.action == SignalAction.SELL:
            if position == "LONG":
                return ReplayDecision.EXIT_LONG, f"Sell signal at {signal.price}"
            return ReplayDecision.SKIP, "No position to sell"

        if signal.action in (SignalAction.HOLD, SignalAction.NONE):
            return ReplayDecision.HOLD, "Hold/no-action signal"

        return ReplayDecision.SKIP, f"Unhandled signal action: {signal.action}"

    def _apply_decision(
        self, decision: ReplayDecision, signal: HistoricalSignal
    ) -> tuple[StrategyState, float]:
        """Apply a decision to produce a new state. Returns (new_state, pnl_delta)."""
        pnl_delta = 0.0

        if decision == ReplayDecision.ENTER_LONG:
            new_state = StrategyState(
                position="LONG",
                entry_price=signal.price,
                unrealized_pnl=0.0,
                realized_pnl=self._state.realized_pnl,
                trade_count=self._state.trade_count,
                current_size=self._config.position_size,
            )
            return new_state, pnl_delta

        if decision in (ReplayDecision.EXIT_LONG, ReplayDecision.STOP_OUT):
            pnl_delta = (signal.price - self._state.entry_price) * self._state.current_size
            new_state = _make_flat_state(
                realized_pnl=self._state.realized_pnl + pnl_delta,
                trade_count=self._state.trade_count + 1,
            )
            return new_state, pnl_delta

        # HOLD or SKIP — update unrealized P&L if in position
        if self._state.position == "LONG":
            unrealized = (signal.price - self._state.entry_price) * self._state.current_size
            new_state = StrategyState(
                position="LONG",
                entry_price=self._state.entry_price,
                unrealized_pnl=unrealized,
                realized_pnl=self._state.realized_pnl,
                trade_count=self._state.trade_count,
                current_size=self._state.current_size,
            )
            return new_state, pnl_delta

        return StrategyState(
            position=self._state.position,
            entry_price=self._state.entry_price,
            unrealized_pnl=self._state.unrealized_pnl,
            realized_pnl=self._state.realized_pnl,
            trade_count=self._state.trade_count,
            current_size=self._state.current_size,
        ), pnl_delta

    def step(self) -> DecisionLogEntry | None:
        """Advance one signal and return the decision log entry, or None if complete."""
        if self.is_complete:
            return None

        signal = self._signals[self._step_index]
        state_before = StrategyState(
            position=self._state.position,
            entry_price=self._state.entry_price,
            unrealized_pnl=self._state.unrealized_pnl,
            realized_pnl=self._state.realized_pnl,
            trade_count=self._state.trade_count,
            current_size=self._state.current_size,
        )

        decision, notes = self._evaluate_signal(signal)
        new_state, pnl_delta = self._apply_decision(decision, signal)
        self._state = new_state

        entry = DecisionLogEntry(
            step=self._step_index,
            signal=signal,
            state_before=state_before,
            decision=decision,
            state_after=new_state,
            pnl_delta=pnl_delta,
            notes=notes,
        )
        self._decision_log.append(entry)
        self._step_index += 1
        return entry

    def step_through(self) -> Generator[DecisionLogEntry, None, None]:
        """Generator that yields decision log entries one at a time."""
        while not self.is_complete:
            entry = self.step()
            if entry is not None:
                yield entry

    def replay_all(self) -> ReplayResult:
        """Replay all signals in batch mode and return the complete result."""
        while not self.is_complete:
            self.step()

        win_count = sum(1 for e in self._decision_log if e.pnl_delta > 0)
        loss_count = sum(1 for e in self._decision_log if e.pnl_delta < 0)

        return ReplayResult(
            strategy_name=self._config.strategy_name,
            symbol=self._config.symbol,
            total_signals=len(self._signals),
            decision_log=list(self._decision_log),
            total_pnl=self._state.realized_pnl,
            total_trades=self._state.trade_count,
            win_count=win_count,
            loss_count=loss_count,
        )
