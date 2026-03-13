"""Tests for the Strategy Template Library REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_template_api.app import create_app


class FakeRecord(dict):
    """dict-like object that also supports attribute access (like asyncpg.Record)."""

    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    """Create a mock asyncpg pool with async context manager support."""
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


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-template-api"


class TestListTemplates:
    def test_list_all_templates(self, client):
        tc, _ = client
        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] >= 5
        assert all(item["type"] == "strategy_template" for item in body["data"])

    def test_list_templates_has_expected_ids(self, client):
        tc, _ = client
        resp = tc.get("/")
        body = resp.json()
        ids = {item["attributes"]["id"] for item in body["data"]}
        assert "ma-crossover" in ids
        assert "rsi-mean-reversion" in ids
        assert "bollinger-breakout" in ids
        assert "macd-momentum" in ids
        assert "volume-weighted-trend" in ids

    def test_list_templates_filter_by_category(self, client):
        tc, _ = client
        resp = tc.get("/?category=trend-following")
        body = resp.json()
        assert body["meta"]["total"] >= 1
        for item in body["data"]:
            assert item["attributes"]["category"] == "trend-following"

    def test_list_templates_filter_unknown_category(self, client):
        tc, _ = client
        resp = tc.get("/?category=nonexistent")
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert body["data"] == []

    def test_list_template_summary_fields(self, client):
        tc, _ = client
        resp = tc.get("/")
        body = resp.json()
        first = body["data"][0]["attributes"]
        assert "id" in first
        assert "name" in first
        assert "description" in first
        assert "category" in first
        assert "complexity" in first
        assert "recommended_markets" in first
        assert "risk_profile" in first


class TestGetTemplate:
    def test_get_template_found(self, client):
        tc, _ = client
        resp = tc.get("/ma-crossover")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "ma-crossover"
        attrs = body["data"]["attributes"]
        assert "strategy_config" in attrs
        assert "parameter_docs" in attrs
        assert len(attrs["strategy_config"]["indicators"]) == 2

    def test_get_template_not_found(self, client):
        tc, _ = client
        resp = tc.get("/nonexistent-template")
        assert resp.status_code == 404

    def test_get_template_has_parameter_docs(self, client):
        tc, _ = client
        resp = tc.get("/rsi-mean-reversion")
        body = resp.json()
        attrs = body["data"]["attributes"]
        param_docs = attrs["parameter_docs"]
        assert "rsiPeriod" in param_docs
        assert "description" in param_docs["rsiPeriod"]
        assert "recommended_range" in param_docs["rsiPeriod"]
        assert "impact" in param_docs["rsiPeriod"]

    def test_get_template_strategy_config_valid(self, client):
        tc, _ = client
        resp = tc.get("/bollinger-breakout")
        body = resp.json()
        config = body["data"]["attributes"]["strategy_config"]
        assert "name" in config
        assert "indicators" in config
        assert "entryConditions" in config
        assert "exitConditions" in config
        assert "parameters" in config


class TestInstantiateTemplate:
    def test_instantiate_success(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="My MA Strategy",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/ma-crossover/instantiate",
            json={"name": "My MA Strategy", "parameter_overrides": {"fastPeriod": 8}},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(spec_id)
        assert body["data"]["attributes"]["name"] == "My MA Strategy"
        assert body["data"]["attributes"]["template_id"] == "ma-crossover"

    def test_instantiate_template_not_found(self, client):
        tc, _ = client
        resp = tc.post(
            "/nonexistent/instantiate",
            json={"name": "test"},
        )
        assert resp.status_code == 404

    def test_instantiate_missing_name(self, client):
        tc, _ = client
        resp = tc.post(
            "/ma-crossover/instantiate",
            json={"parameter_overrides": {}},
        )
        assert resp.status_code == 422

    def test_instantiate_duplicate_name(self, client):
        tc, conn = client
        import asyncpg as apg

        conn.fetchrow.side_effect = apg.UniqueViolationError("")

        resp = tc.post(
            "/ma-crossover/instantiate",
            json={"name": "Existing Strategy"},
        )
        assert resp.status_code == 409

    def test_instantiate_with_overrides_applied(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="Custom RSI",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/rsi-mean-reversion/instantiate",
            json={
                "name": "Custom RSI",
                "parameter_overrides": {
                    "rsiPeriod": 7,
                    "oversoldLevel": 25.0,
                },
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        params = body["data"]["attributes"]["parameters"]
        rsi_param = next(p for p in params if p["name"] == "rsiPeriod")
        assert rsi_param["defaultValue"] == 7
        oversold_param = next(p for p in params if p["name"] == "oversoldLevel")
        assert oversold_param["defaultValue"] == 25.0

    def test_instantiate_db_persists_correct_data(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="MACD Test",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        tc.post(
            "/macd-momentum/instantiate",
            json={"name": "MACD Test"},
        )

        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        query = call_args[0][0]
        assert "INSERT INTO strategy_specs" in query
        assert call_args[0][1] == "MACD Test"
        # Verify indicators are serialized as JSON
        indicators = json.loads(call_args[0][2])
        assert isinstance(indicators, list)
        assert indicators[0]["type"] == "MACD"

    def test_instantiate_no_overrides(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="Default Volume Trend",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/volume-weighted-trend/instantiate",
            json={"name": "Default Volume Trend"},
        )
        assert resp.status_code == 201
        body = resp.json()
        params = body["data"]["attributes"]["parameters"]
        fast = next(p for p in params if p["name"] == "fastPeriod")
        assert fast["defaultValue"] == 10


class TestTemplateData:
    def test_all_templates_have_required_fields(self, client):
        tc, _ = client
        resp = tc.get("/")
        body = resp.json()
        for item in body["data"]:
            template_id = item["attributes"]["id"]
            detail_resp = tc.get(f"/{template_id}")
            assert detail_resp.status_code == 200
            attrs = detail_resp.json()["data"]["attributes"]
            config = attrs["strategy_config"]
            assert len(config["indicators"]) >= 1
            assert len(config["entryConditions"]) >= 1
            assert len(config["exitConditions"]) >= 1
            assert len(config["parameters"]) >= 1
            assert "parameter_docs" in attrs
            assert "recommended_markets" in attrs
            assert "risk_profile" in attrs
