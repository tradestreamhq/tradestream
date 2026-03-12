"""Tests for the Reconciliation REST API."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.reconciliation.app import create_app


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


class TestRunReconciliation:
    def test_run_no_positions(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.post("/run", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "MATCHED"

    def test_run_with_phantom_positions(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(symbol="BTC/USD", quantity=1.0, avg_entry_price=50000.0)
        ]
        resp = tc.post("/run", json={})
        assert resp.status_code == 200
        body = resp.json()
        report = body["data"]["attributes"]
        assert report["status"] == "DISCREPANCIES_FOUND"
        assert len(report["discrepancies"]) == 1
        assert report["discrepancies"][0]["type"] == "PHANTOM_POSITION"

    def test_run_with_threshold(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.post("/run", json={"auto_reconcile_threshold": 0.1})
        assert resp.status_code == 200


class TestGetReport:
    def test_no_report_yet(self, client):
        tc, _ = client
        resp = tc.get("/report")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body["data"]["attributes"]

    def test_report_after_run(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        tc.post("/run", json={})
        resp = tc.get("/report")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "MATCHED"
