"""Tests for the Consensus API and Signal Aggregator."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.consensus_api.aggregator import (
    AggregationConfig,
    ConsensusSignal,
    Direction,
    Signal,
    SignalAggregator,
    StrategyWeight,
)
from services.consensus_api.app import create_app


class FakeRecord(dict):
    """dict-like object that also supports attribute access (like asyncpg.Record)."""

    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


# ── Aggregator Unit Tests ──


class TestStrategyWeight:
    def test_compute_weight_balanced(self):
        sw = StrategyWeight(
            strategy_id="s1",
            spec_id="sp1",
            strategy_name="test",
            win_rate=0.7,
            sharpe_ratio=1.5,
        )
        w = sw.compute_weight()
        # 0.4 * 0.7 + 0.6 * (1.5/3.0) = 0.28 + 0.30 = 0.58
        assert abs(w - 0.58) < 0.001

    def test_compute_weight_high_sharpe(self):
        sw = StrategyWeight(
            strategy_id="s1",
            spec_id="sp1",
            strategy_name="test",
            win_rate=0.5,
            sharpe_ratio=3.0,
        )
        w = sw.compute_weight()
        # 0.4 * 0.5 + 0.6 * 1.0 = 0.20 + 0.60 = 0.80
        assert abs(w - 0.80) < 0.001

    def test_compute_weight_clamped(self):
        sw = StrategyWeight(
            strategy_id="s1",
            spec_id="sp1",
            strategy_name="test",
            win_rate=1.5,
            sharpe_ratio=10.0,
        )
        w = sw.compute_weight()
        # clamped: 0.4 * 1.0 + 0.6 * 1.0 = 1.0
        assert abs(w - 1.0) < 0.001

    def test_compute_weight_zero(self):
        sw = StrategyWeight(
            strategy_id="s1",
            spec_id="sp1",
            strategy_name="test",
            win_rate=0.0,
            sharpe_ratio=-1.0,
        )
        w = sw.compute_weight()
        assert abs(w - 0.0) < 0.001


class TestSignalAggregator:
    def _make_signal(
        self, strategy_id, signal_type, strength=0.8, price=100.0, minutes_ago=0
    ):
        return Signal(
            strategy_id=strategy_id,
            spec_id=f"spec_{strategy_id}",
            instrument="BTC/USD",
            signal_type=signal_type,
            strength=strength,
            price=price,
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        )

    def _make_weights(self, strategy_ids, weight_val=0.5):
        return {
            sid: StrategyWeight(
                strategy_id=sid,
                spec_id=f"spec_{sid}",
                strategy_name=f"strat_{sid}",
                weight=weight_val,
            )
            for sid in strategy_ids
        }

    def test_aggregate_unanimous_buy(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=2))
        signals = [
            self._make_signal("s1", "BUY"),
            self._make_signal("s2", "BUY"),
            self._make_signal("s3", "BUY"),
        ]
        weights = self._make_weights(["s1", "s2", "s3"])
        result = agg.aggregate(signals, weights)

        assert result is not None
        assert result.direction == Direction.LONG
        assert result.agreeing_signals == 3
        assert result.dissenting_signals == 0
        assert result.confidence > 0.5

    def test_aggregate_unanimous_sell(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=2))
        signals = [
            self._make_signal("s1", "SELL"),
            self._make_signal("s2", "SELL"),
        ]
        weights = self._make_weights(["s1", "s2"])
        result = agg.aggregate(signals, weights)

        assert result is not None
        assert result.direction == Direction.SHORT
        assert result.agreeing_signals == 2

    def test_aggregate_mixed_signals(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=2))
        signals = [
            self._make_signal("s1", "BUY", strength=0.9),
            self._make_signal("s2", "SELL", strength=0.3),
            self._make_signal("s3", "BUY", strength=0.7),
        ]
        weights = self._make_weights(["s1", "s2", "s3"])
        result = agg.aggregate(signals, weights)

        assert result is not None
        assert result.direction == Direction.LONG
        assert result.agreeing_signals == 2
        assert result.dissenting_signals == 1

    def test_aggregate_insufficient_strategies(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=3))
        signals = [
            self._make_signal("s1", "BUY"),
            self._make_signal("s2", "BUY"),
        ]
        weights = self._make_weights(["s1", "s2"])
        result = agg.aggregate(signals, weights)
        assert result is None

    def test_aggregate_expired_signals(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=60, min_strategies=2))
        signals = [
            self._make_signal("s1", "BUY", minutes_ago=5),
            self._make_signal("s2", "BUY", minutes_ago=5),
        ]
        weights = self._make_weights(["s1", "s2"])
        result = agg.aggregate(signals, weights)
        assert result is None

    def test_aggregate_weighted_voting(self):
        """Strategy with higher weight should influence direction more."""
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=2))
        signals = [
            self._make_signal("s1", "BUY", strength=0.8),
            self._make_signal("s2", "SELL", strength=0.8),
        ]
        weights = {
            "s1": StrategyWeight(
                strategy_id="s1",
                spec_id="sp1",
                strategy_name="good",
                weight=0.9,
            ),
            "s2": StrategyWeight(
                strategy_id="s2",
                spec_id="sp2",
                strategy_name="bad",
                weight=0.1,
            ),
        }
        result = agg.aggregate(signals, weights)
        assert result is not None
        assert result.direction == Direction.LONG

    def test_aggregate_average_price(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=2))
        signals = [
            self._make_signal("s1", "BUY", price=100.0),
            self._make_signal("s2", "BUY", price=102.0),
        ]
        weights = self._make_weights(["s1", "s2"], weight_val=1.0)
        result = agg.aggregate(signals, weights)
        assert result is not None
        assert result.avg_price == 101.0

    def test_empty_signals(self):
        agg = SignalAggregator(AggregationConfig(window_seconds=600, min_strategies=1))
        result = agg.aggregate([], {})
        assert result is None


class TestAgreementMatrix:
    def test_full_agreement(self):
        agg = SignalAggregator()
        now = datetime.now(timezone.utc)
        signals_by_pair = {
            "BTC/USD": [
                Signal("s1", "sp1", "BTC/USD", "BUY", 0.8, 100.0, now),
                Signal("s2", "sp2", "BTC/USD", "BUY", 0.7, 100.0, now),
            ],
        }
        matrix = agg.compute_agreement_matrix(signals_by_pair)
        assert matrix["s1"]["s2"] == 1.0
        assert matrix["s2"]["s1"] == 1.0

    def test_no_agreement(self):
        agg = SignalAggregator()
        now = datetime.now(timezone.utc)
        signals_by_pair = {
            "BTC/USD": [
                Signal("s1", "sp1", "BTC/USD", "BUY", 0.8, 100.0, now),
                Signal("s2", "sp2", "BTC/USD", "SELL", 0.7, 100.0, now),
            ],
        }
        matrix = agg.compute_agreement_matrix(signals_by_pair)
        assert matrix["s1"]["s2"] == 0.0

    def test_partial_agreement(self):
        agg = SignalAggregator()
        now = datetime.now(timezone.utc)
        signals_by_pair = {
            "BTC/USD": [
                Signal("s1", "sp1", "BTC/USD", "BUY", 0.8, 100.0, now),
                Signal("s2", "sp2", "BTC/USD", "BUY", 0.7, 100.0, now),
            ],
            "ETH/USD": [
                Signal("s1", "sp1", "ETH/USD", "BUY", 0.8, 50.0, now),
                Signal("s2", "sp2", "ETH/USD", "SELL", 0.7, 50.0, now),
            ],
        }
        matrix = agg.compute_agreement_matrix(signals_by_pair)
        assert matrix["s1"]["s2"] == 0.5

    def test_self_agreement(self):
        agg = SignalAggregator()
        now = datetime.now(timezone.utc)
        signals_by_pair = {
            "BTC/USD": [
                Signal("s1", "sp1", "BTC/USD", "BUY", 0.8, 100.0, now),
            ],
        }
        matrix = agg.compute_agreement_matrix(signals_by_pair)
        assert matrix["s1"]["s1"] == 1.0

    def test_empty_signals(self):
        agg = SignalAggregator()
        matrix = agg.compute_agreement_matrix({})
        assert matrix == {}


class TestConsensusSignal:
    def test_agreement_ratio(self):
        cs = ConsensusSignal(
            contributing_signals=4,
            agreeing_signals=3,
            dissenting_signals=1,
        )
        assert cs.agreement_ratio() == 0.75

    def test_agreement_ratio_zero(self):
        cs = ConsensusSignal(contributing_signals=0)
        assert cs.agreement_ratio() == 0.0


# ── API Endpoint Tests ──


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "consensus-api"


class TestConsensusEndpoint:
    def test_get_consensus_no_signals(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/BTC-USD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["direction"] == "NEUTRAL"
        assert body["data"]["attributes"]["contributing_signals"] == 0

    def test_get_consensus_insufficient_strategies(self, client):
        tc, conn = client
        # First call: strategy weights
        # Second call: recent signals (only 1 strategy)
        now = datetime.now(timezone.utc)
        conn.fetch.side_effect = [
            [],  # no weights
            [
                FakeRecord(
                    strategy_id="s1",
                    spec_id="sp1",
                    instrument="BTC-USD",
                    signal_type="BUY",
                    strength=0.8,
                    price=50000.0,
                    created_at=now,
                )
            ],
        ]
        resp = tc.get("/BTC-USD")
        assert resp.status_code == 200
        body = resp.json()
        assert "Insufficient" in body["data"]["attributes"]["message"]


class TestConsensusHistoryEndpoint:
    def test_get_history(self, client):
        tc, conn = client
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        conn.fetch.return_value = [
            FakeRecord(
                id=sig_id,
                instrument="BTC-USD",
                direction="LONG",
                confidence=0.85,
                contributing_signals=3,
                agreeing_signals=2,
                dissenting_signals=1,
                weighted_score=1.2,
                avg_price=50000.0,
                signal_details=[],
                window_start=now,
                window_end=now,
                created_at=now,
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/BTC-USD/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["direction"] == "LONG"

    def test_get_history_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/BTC-USD/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert len(body["data"]) == 0


class TestConfigEndpoint:
    def test_update_config(self, client):
        tc, conn = client
        resp = tc.put(
            "/config",
            json={
                "window_seconds": 120,
                "min_strategies": 3,
                "confidence_threshold": 0.7,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["window_seconds"] == 120
        assert attrs["min_strategies"] == 3
        assert attrs["confidence_threshold"] == 0.7

    def test_update_config_partial(self, client):
        tc, conn = client
        resp = tc.put("/config", json={"window_seconds": 60})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["window_seconds"] == 60

    def test_update_config_invalid(self, client):
        tc, conn = client
        resp = tc.put("/config", json={"window_seconds": 5})
        assert resp.status_code == 422
