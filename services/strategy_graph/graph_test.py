"""Tests for the strategy dependency graph core logic."""

from datetime import datetime, timedelta, timezone

import pytest

from services.strategy_graph.graph import StrategyGraph
from services.strategy_graph.models import (
    Conflict,
    RelationshipType,
    Signal,
    SignalDirection,
    StrategyEdge,
    StrategyNode,
)


@pytest.fixture
def graph():
    return StrategyGraph()


def _ts(minutes_offset: int = 0) -> datetime:
    return datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc) + timedelta(
        minutes=minutes_offset
    )


def _make_node(sid: str, symbols: list, sharpe: float = 1.0) -> StrategyNode:
    return StrategyNode(
        strategy_id=sid, name=f"Strategy {sid}", symbols=symbols, sharpe_ratio=sharpe
    )


class TestStrategyManagement:
    def test_add_and_get(self, graph):
        node = _make_node("s1", ["BTC/USD"])
        graph.add_strategy(node)
        assert graph.get_strategy("s1") == node

    def test_list_strategies(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["ETH/USD"]))
        assert len(graph.list_strategies()) == 2

    def test_remove_strategy(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.remove_strategy("s1")
        assert graph.get_strategy("s1") is None

    def test_remove_cleans_edges(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        assert len(graph.get_edges()) == 1  # auto-discovered
        graph.remove_strategy("s1")
        assert len(graph.get_edges()) == 0


class TestEdgeDiscovery:
    def test_same_symbol_auto_edge(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD", "ETH/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        edges = graph.get_edges()
        assert len(edges) == 1
        assert edges[0].relationship == RelationshipType.SAME_SYMBOL
        assert "BTC/USD" in edges[0].shared_symbols

    def test_no_overlap_no_edge(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["ETH/USD"]))
        assert len(graph.get_edges()) == 0

    def test_manual_edge(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["ETH/USD"]))
        edge = StrategyEdge(
            source_id="s1",
            target_id="s2",
            relationship=RelationshipType.CORRELATED,
            correlation=0.85,
        )
        graph.add_edge(edge)
        assert len(graph.get_edges()) == 1

    def test_manual_edges_preserved_on_rebuild(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["ETH/USD"]))
        edge = StrategyEdge(
            source_id="s1",
            target_id="s2",
            relationship=RelationshipType.HEDGING,
        )
        graph.add_edge(edge)
        # Adding a third strategy triggers rebuild
        graph.add_strategy(_make_node("s3", ["BTC/USD"]))
        edges = graph.get_edges()
        hedging = [e for e in edges if e.relationship == RelationshipType.HEDGING]
        assert len(hedging) == 1

    def test_neighbors(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        graph.add_strategy(_make_node("s3", ["ETH/USD"]))
        neighbors = graph.get_neighbors("s1")
        assert "s2" in neighbors
        assert "s3" not in neighbors


class TestConflictDetection:
    def test_opposing_signals_conflict(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"], sharpe=1.5))
        graph.add_strategy(_make_node("s2", ["BTC/USD"], sharpe=0.8))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.SELL, _ts(1))
        )
        conflicts = graph.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].symbol == "BTC/USD"
        assert conflicts[0].winner_strategy_id == "s1"

    def test_same_direction_no_conflict(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.BUY, _ts(1))
        )
        assert len(graph.detect_conflicts()) == 0

    def test_outside_window_no_conflict(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.SELL, _ts(10))
        )
        # Default window is 5 minutes
        assert len(graph.detect_conflicts()) == 0

    def test_custom_window(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.SELL, _ts(10))
        )
        conflicts = graph.detect_conflicts(window=timedelta(minutes=15))
        assert len(conflicts) == 1

    def test_hold_signals_ignored(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.HOLD, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.SELL, _ts(1))
        )
        assert len(graph.detect_conflicts()) == 0

    def test_sharpe_resolution(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"], sharpe=0.5))
        graph.add_strategy(_make_node("s2", ["BTC/USD"], sharpe=2.0))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.SELL, _ts(1))
        )
        conflicts = graph.detect_conflicts()
        assert conflicts[0].winner_strategy_id == "s2"

    def test_multiple_symbols(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD", "ETH/USD"], sharpe=1.0))
        graph.add_strategy(_make_node("s2", ["BTC/USD", "ETH/USD"], sharpe=0.5))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "BTC/USD", SignalDirection.SELL, _ts(1))
        )
        graph.submit_signal(
            Signal("s1", "ETH/USD", SignalDirection.SELL, _ts(0))
        )
        graph.submit_signal(
            Signal("s2", "ETH/USD", SignalDirection.BUY, _ts(1))
        )
        conflicts = graph.detect_conflicts()
        assert len(conflicts) == 2
        symbols = {c.symbol for c in conflicts}
        assert symbols == {"BTC/USD", "ETH/USD"}

    def test_clear_signals(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.clear_signals()
        assert len(graph.detect_conflicts()) == 0

    def test_same_strategy_no_self_conflict(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.BUY, _ts(0))
        )
        graph.submit_signal(
            Signal("s1", "BTC/USD", SignalDirection.SELL, _ts(1))
        )
        assert len(graph.detect_conflicts()) == 0


class TestSerialization:
    def test_graph_to_dict(self, graph):
        graph.add_strategy(_make_node("s1", ["BTC/USD"]))
        graph.add_strategy(_make_node("s2", ["BTC/USD"]))
        d = graph.to_dict()
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
