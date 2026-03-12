"""Trade journal service for logging and querying trade decisions."""

import json
from datetime import datetime
from typing import Any, Optional

from absl import logging

from services.trade_journal.models import JournalEntry, Outcome, Side


class TradeJournal:
    """In-memory trade journal with search and filter capabilities.

    Stores journal entries and provides query methods for reviewing
    trade decisions, strategies, and outcomes.
    """

    def __init__(self) -> None:
        self._entries: dict[str, JournalEntry] = {}

    def log_entry(
        self,
        trade_id: str,
        strategy: str,
        symbol: str,
        side: str,
        entry_price: float,
        entry_rationale: str,
        signals_at_entry: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> JournalEntry:
        """Log a new trade entry at open time."""
        entry = JournalEntry(
            trade_id=trade_id,
            strategy=strategy,
            symbol=symbol,
            side=Side(side),
            entry_price=entry_price,
            entry_rationale=entry_rationale,
            signals_at_entry=signals_at_entry or {},
            tags=tags or [],
        )
        self._entries[entry.id] = entry
        logging.info("Journal entry created: %s for trade %s", entry.id, trade_id)
        return entry

    def close_entry(
        self,
        entry_id: str,
        exit_price: float,
        exit_rationale: str,
        lessons: Optional[str] = None,
    ) -> JournalEntry:
        """Close an existing journal entry with exit analysis."""
        entry = self._entries.get(entry_id)
        if entry is None:
            raise KeyError(f"Journal entry {entry_id} not found")

        entry.exit_price = exit_price
        entry.exit_rationale = exit_rationale
        entry.closed_at = datetime.utcnow()
        entry.lessons = lessons

        # Calculate PnL
        if entry.side == Side.BUY:
            entry.pnl = exit_price - entry.entry_price
        else:
            entry.pnl = entry.entry_price - exit_price

        # Determine outcome
        if entry.pnl > 0:
            entry.outcome = Outcome.WIN
        elif entry.pnl < 0:
            entry.outcome = Outcome.LOSS
        else:
            entry.outcome = Outcome.BREAKEVEN

        logging.info(
            "Journal entry closed: %s outcome=%s pnl=%.4f",
            entry_id,
            entry.outcome.value,
            entry.pnl,
        )
        return entry

    def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        return self._entries.get(entry_id)

    def search(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None,
        outcome: Optional[str] = None,
        side: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[JournalEntry]:
        """Search entries with filters. All filters are AND-combined."""
        results = list(self._entries.values())

        if strategy:
            results = [e for e in results if e.strategy == strategy]
        if symbol:
            results = [e for e in results if e.symbol == symbol]
        if outcome:
            results = [e for e in results if e.outcome == Outcome(outcome)]
        if side:
            results = [e for e in results if e.side == Side(side)]
        if start_date:
            start = datetime.fromisoformat(start_date)
            results = [e for e in results if e.created_at >= start]
        if end_date:
            end = datetime.fromisoformat(end_date)
            results = [e for e in results if e.created_at <= end]
        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set.intersection(e.tags)]

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results

    def all_entries(self) -> list[JournalEntry]:
        entries = list(self._entries.values())
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries

    def summary(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate summary statistics for matching entries."""
        entries = self.search(strategy=strategy, symbol=symbol)
        closed = [e for e in entries if e.outcome != Outcome.OPEN]

        if not closed:
            return {
                "total_entries": len(entries),
                "closed_entries": 0,
                "open_entries": len(entries),
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
            }

        wins = sum(1 for e in closed if e.outcome == Outcome.WIN)
        losses = sum(1 for e in closed if e.outcome == Outcome.LOSS)
        breakeven = sum(1 for e in closed if e.outcome == Outcome.BREAKEVEN)
        total_pnl = sum(e.pnl for e in closed if e.pnl is not None)

        return {
            "total_entries": len(entries),
            "closed_entries": len(closed),
            "open_entries": len(entries) - len(closed),
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(wins / len(closed) * 100, 2) if closed else 0.0,
            "total_pnl": round(total_pnl, 8),
            "avg_pnl": round(total_pnl / len(closed), 8) if closed else 0.0,
        }
