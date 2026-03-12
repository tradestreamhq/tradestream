"""Tests for the Strategy Graph REST API."""

import pytest
from fastapi.testclient import TestClient

from services.strategy_graph.app import create_app
from services.strategy_graph.graph import StrategyGraph


@pytest.fixture
def client():
    graph = StrategyGraph()
    app = create_app(graph)
    return TestClient(app, raise_server_exceptions=False), graph


def _add_strategy(tc, sid="s1", name="Strat 1", symbols=None, sharpe=1.0):
    return tc.post(
        "/",
        json={
            "strategy_id": sid,
            "name": name,
            "symbols": symbols or ["BTC/USD"],
            "sharpe_ratio": sharpe,
        },
    )


class TestHealthEndpoints:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestStrategyCRUD:
    def test_create_strategy(self, client):
        tc, _ = client
        resp = _add_strategy(tc)
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == "s1"
        assert body["data"]["attributes"]["name"] == "Strat 1"

    def test_list_strategies(self, client):
        tc, _ = client
        _add_strategy(tc, "s1")
        _add_strategy(tc, "s2", name="Strat 2")
        resp = tc.get("/")
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 2

    def test_get_strategy(self, client):
        tc, _ = client
        _add_strategy(tc)
        resp = tc.get("/s1")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["strategy_id"] == "s1"

    def test_get_strategy_not_found(self, client):
        tc, _ = client
        resp = tc.get("/nonexistent")
        assert resp.status_code == 404

    def test_delete_strategy(self, client):
        tc, _ = client
        _add_strategy(tc)
        resp = tc.delete("/s1")
        assert resp.status_code == 200
        resp = tc.get("/s1")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        tc, _ = client
        resp = tc.delete("/nonexistent")
        assert resp.status_code == 404


class TestEdges:
    def test_auto_edges(self, client):
        tc, _ = client
        _add_strategy(tc, "s1", symbols=["BTC/USD"])
        _add_strategy(tc, "s2", symbols=["BTC/USD"])
        resp = tc.get("/graph/edges")
        assert resp.status_code == 200
        edges = resp.json()["data"]
        assert len(edges) == 1
        assert edges[0]["attributes"]["relationship"] == "SAME_SYMBOL"

    def test_manual_edge(self, client):
        tc, _ = client
        _add_strategy(tc, "s1", symbols=["BTC/USD"])
        _add_strategy(tc, "s2", symbols=["ETH/USD"])
        resp = tc.post(
            "/graph/edges",
            json={
                "source_id": "s1",
                "target_id": "s2",
                "relationship": "CORRELATED",
                "correlation": 0.9,
            },
        )
        assert resp.status_code == 201

    def test_edge_invalid_strategy(self, client):
        tc, _ = client
        _add_strategy(tc, "s1")
        resp = tc.post(
            "/graph/edges",
            json={
                "source_id": "s1",
                "target_id": "missing",
                "relationship": "CORRELATED",
            },
        )
        assert resp.status_code == 404

    def test_neighbors(self, client):
        tc, _ = client
        _add_strategy(tc, "s1", symbols=["BTC/USD"])
        _add_strategy(tc, "s2", symbols=["BTC/USD"])
        _add_strategy(tc, "s3", symbols=["ETH/USD"])
        resp = tc.get("/graph/neighbors/s1")
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 1


class TestSignalsAndConflicts:
    def test_submit_signal(self, client):
        tc, _ = client
        _add_strategy(tc, "s1")
        resp = tc.post(
            "/signals",
            json={
                "strategy_id": "s1",
                "symbol": "BTC/USD",
                "direction": "BUY",
            },
        )
        assert resp.status_code == 201

    def test_signal_unknown_strategy(self, client):
        tc, _ = client
        resp = tc.post(
            "/signals",
            json={
                "strategy_id": "missing",
                "symbol": "BTC/USD",
                "direction": "BUY",
            },
        )
        assert resp.status_code == 404

    def test_conflict_detection(self, client):
        tc, _ = client
        _add_strategy(tc, "s1", sharpe=2.0)
        _add_strategy(tc, "s2", sharpe=0.5)
        tc.post(
            "/signals",
            json={
                "strategy_id": "s1",
                "symbol": "BTC/USD",
                "direction": "BUY",
                "timestamp": "2026-03-12T12:00:00+00:00",
            },
        )
        tc.post(
            "/signals",
            json={
                "strategy_id": "s2",
                "symbol": "BTC/USD",
                "direction": "SELL",
                "timestamp": "2026-03-12T12:01:00+00:00",
            },
        )
        resp = tc.get("/conflicts")
        assert resp.status_code == 200
        conflicts = resp.json()["data"]
        assert len(conflicts) == 1
        assert conflicts[0]["attributes"]["winner_strategy_id"] == "s1"

    def test_no_conflicts_same_direction(self, client):
        tc, _ = client
        _add_strategy(tc, "s1")
        _add_strategy(tc, "s2")
        tc.post(
            "/signals",
            json={
                "strategy_id": "s1",
                "symbol": "BTC/USD",
                "direction": "BUY",
                "timestamp": "2026-03-12T12:00:00+00:00",
            },
        )
        tc.post(
            "/signals",
            json={
                "strategy_id": "s2",
                "symbol": "BTC/USD",
                "direction": "BUY",
                "timestamp": "2026-03-12T12:01:00+00:00",
            },
        )
        resp = tc.get("/conflicts")
        assert resp.json()["meta"]["total"] == 0


class TestGraph:
    def test_full_graph(self, client):
        tc, _ = client
        _add_strategy(tc, "s1", symbols=["BTC/USD"])
        _add_strategy(tc, "s2", symbols=["BTC/USD"])
        resp = tc.get("/graph")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert len(attrs["nodes"]) == 2
        assert len(attrs["edges"]) == 1
