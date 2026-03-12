"""
Strategy dependency graph service.

Models relationships between strategies and detects conflicting signals
before execution. Conflicts are resolved using priority rules where
strategies with higher Sharpe ratios take precedence.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from services.strategy_graph.models import (
    Conflict,
    RelationshipType,
    Signal,
    SignalDirection,
    StrategyEdge,
    StrategyNode,
)


class StrategyGraph:
    """Directed graph of strategy relationships with conflict detection."""

    def __init__(self) -> None:
        self._nodes: Dict[str, StrategyNode] = {}
        self._edges: List[StrategyEdge] = []
        self._signals: List[Signal] = []

    # --- Node management ---

    def add_strategy(self, node: StrategyNode) -> None:
        """Add a strategy node to the graph."""
        self._nodes[node.strategy_id] = node
        self._rebuild_edges()

    def remove_strategy(self, strategy_id: str) -> None:
        """Remove a strategy node and its edges."""
        self._nodes.pop(strategy_id, None)
        self._edges = [
            e
            for e in self._edges
            if e.source_id != strategy_id and e.target_id != strategy_id
        ]

    def get_strategy(self, strategy_id: str) -> Optional[StrategyNode]:
        return self._nodes.get(strategy_id)

    def list_strategies(self) -> List[StrategyNode]:
        return list(self._nodes.values())

    # --- Edge management ---

    def add_edge(self, edge: StrategyEdge) -> None:
        """Manually add a relationship edge."""
        self._edges.append(edge)

    def get_edges(self) -> List[StrategyEdge]:
        return list(self._edges)

    def get_neighbors(self, strategy_id: str) -> List[str]:
        """Get IDs of strategies connected to the given strategy."""
        neighbors = set()
        for e in self._edges:
            if e.source_id == strategy_id:
                neighbors.add(e.target_id)
            elif e.target_id == strategy_id:
                neighbors.add(e.source_id)
        return list(neighbors)

    # --- Automatic edge discovery ---

    def _rebuild_edges(self) -> None:
        """Rebuild edges by detecting same-symbol overlaps between strategies."""
        existing_pairs = {
            (e.source_id, e.target_id)
            for e in self._edges
            if e.relationship != RelationshipType.SAME_SYMBOL
        }
        # Keep manually added non-SAME_SYMBOL edges
        manual_edges = [
            e for e in self._edges if e.relationship != RelationshipType.SAME_SYMBOL
        ]
        self._edges = list(manual_edges)

        ids = sorted(self._nodes.keys())
        for i, id_a in enumerate(ids):
            for id_b in ids[i + 1 :]:
                node_a = self._nodes[id_a]
                node_b = self._nodes[id_b]
                shared = list(set(node_a.symbols) & set(node_b.symbols))
                if shared:
                    self._edges.append(
                        StrategyEdge(
                            source_id=id_a,
                            target_id=id_b,
                            relationship=RelationshipType.SAME_SYMBOL,
                            shared_symbols=sorted(shared),
                        )
                    )

    # --- Signal management ---

    def submit_signal(self, signal: Signal) -> None:
        """Submit a trading signal from a strategy."""
        self._signals.append(signal)

    def clear_signals(self) -> None:
        self._signals.clear()

    # --- Conflict detection ---

    def detect_conflicts(
        self, window: timedelta = timedelta(minutes=5)
    ) -> List[Conflict]:
        """Detect opposing signals on the same symbol within a time window.

        Two signals conflict when:
        - They target the same symbol
        - They have opposing directions (BUY vs SELL)
        - They fall within the specified time window

        Conflicts are resolved by Sharpe ratio: the strategy with the
        higher Sharpe ratio wins.
        """
        if not self._signals:
            return []

        # Group signals by symbol
        by_symbol: Dict[str, List[Signal]] = defaultdict(list)
        for sig in self._signals:
            if sig.direction != SignalDirection.HOLD:
                by_symbol[sig.symbol].append(sig)

        conflicts: List[Conflict] = []

        for symbol, signals in by_symbol.items():
            # Sort by timestamp
            signals.sort(key=lambda s: s.timestamp)

            # Find groups of opposing signals within the time window
            buy_signals = [s for s in signals if s.direction == SignalDirection.BUY]
            sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]

            if not buy_signals or not sell_signals:
                continue

            # Check each pair of opposing signals for time overlap
            paired: set = set()
            for buy in buy_signals:
                for sell in sell_signals:
                    if buy.strategy_id == sell.strategy_id:
                        continue
                    time_diff = abs(
                        (buy.timestamp - sell.timestamp).total_seconds()
                    )
                    if time_diff <= window.total_seconds():
                        pair_key = tuple(
                            sorted([buy.strategy_id, sell.strategy_id])
                        )
                        if pair_key not in paired:
                            paired.add(pair_key)
                            conflicting = [buy, sell]
                            winner = self._resolve_by_sharpe(conflicting)
                            conflicts.append(
                                Conflict(
                                    symbol=symbol,
                                    signals=conflicting,
                                    winner_strategy_id=winner,
                                    reason="higher_sharpe_ratio",
                                )
                            )

        return conflicts

    def _resolve_by_sharpe(self, signals: List[Signal]) -> str:
        """Resolve a conflict by choosing the strategy with higher Sharpe ratio."""
        best_id = signals[0].strategy_id
        best_sharpe = -float("inf")

        for sig in signals:
            node = self._nodes.get(sig.strategy_id)
            sharpe = node.sharpe_ratio if node else 0.0
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_id = sig.strategy_id

        return best_id

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
        }
