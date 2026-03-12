"""Tests for the Learning Engine REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.learning_api.app import create_app


class FakeRecord(dict):
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
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestDecisionEndpoints:
    def test_list_decisions(self, client):
        tc, conn = client
        decision_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=decision_id,
                signal_id="sig-1",
                agent_name="test-agent",
                decision_type="signal",
                score=0.85,
                tier="HOT",
                reasoning="good signal",
                tool_calls=None,
                model_used="gpt-4",
                latency_ms=150,
                tokens_used=500,
                success=True,
                error_message=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/decisions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "decision"

    def test_create_decision(self, client):
        tc, conn = client
        decision_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=decision_id,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/decisions",
            json={
                "signal_id": "sig-1",
                "agent_name": "test-agent",
                "decision_type": "signal",
                "score": 0.85,
                "tier": "HOT",
                "reasoning": "good signal",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(decision_id)

    def test_get_decision_found(self, client):
        tc, conn = client
        decision_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=decision_id,
            signal_id="sig-1",
            agent_name="test-agent",
            decision_type="signal",
            score=0.85,
            tier="HOT",
            reasoning="good",
            tool_calls=None,
            model_used="gpt-4",
            latency_ms=100,
            tokens_used=300,
            success=True,
            error_message=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/decisions/{decision_id}")
        assert resp.status_code == 200

    def test_get_decision_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/decisions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_record_outcome(self, client):
        tc, conn = client
        decision_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=decision_id)

        resp = tc.put(
            f"/decisions/{decision_id}/outcome",
            json={"success": True},
        )
        assert resp.status_code == 200


class TestAnalyticsEndpoints:
    def test_get_patterns(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                agent_name="scorer",
                tier="HOT",
                count=10,
                avg_score=0.8,
                successes=8,
                failures=2,
            )
        ]

        resp = tc.get("/patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_performance(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            total_decisions=100,
            avg_score=0.75,
            avg_latency_ms=120.0,
            successes=80,
            failures=20,
            unique_agents=3,
        )

        resp = tc.get("/performance?period=7d")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["period"] == "7d"
