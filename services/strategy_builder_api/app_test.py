"""Tests for the User Strategy Builder API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_builder_api.app import (
    INDICATOR_CATALOG,
    CONDITION_TYPES,
    create_app,
    validate_strategy_config,
    StrategyConfigDTO,
    IndicatorConfigDTO,
    ConditionConfigDTO,
    _run_simple_backtest,
)


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
    return TestClient(app, raise_server_exceptions=False), conn


USER_ID = str(uuid.uuid4())
HEADERS = {"X-User-Id": USER_ID}


def _valid_strategy_body():
    return {
        "name": "My RSI Strategy",
        "description": "Buy when RSI crosses below 30",
        "category": "momentum",
        "indicators": [
            {"id": "rsi_1", "type": "RSI", "input": "close", "params": {"period": 14}},
            {
                "id": "threshold_1",
                "type": "CONSTANT",
                "input": "close",
                "params": {"value": 30},
            },
        ],
        "entry_conditions": [
            {
                "type": "CrossedDown",
                "indicator": "rsi_1",
                "params": {"reference": "threshold_1"},
            },
        ],
        "exit_conditions": [
            {
                "type": "CrossedUp",
                "indicator": "rsi_1",
                "params": {"reference": "threshold_1"},
            },
        ],
        "tags": ["rsi", "momentum"],
    }


def _fake_strategy_row(strategy_id=None, user_id=None):
    return FakeRecord(
        id=strategy_id or uuid.uuid4(),
        user_id=user_id or uuid.UUID(USER_ID),
        name="My RSI Strategy",
        description="Buy when RSI crosses below 30",
        category="momentum",
        indicators=json.dumps(
            [
                {
                    "id": "rsi_1",
                    "type": "RSI",
                    "input": "close",
                    "params": {"period": 14},
                },
            ]
        ),
        entry_conditions=json.dumps(
            [
                {"type": "CrossedDown", "indicator": "rsi_1", "params": {}},
            ]
        ),
        exit_conditions=json.dumps(
            [
                {"type": "CrossedUp", "indicator": "rsi_1", "params": {}},
            ]
        ),
        tags=json.dumps(["rsi", "momentum"]),
        version=1,
        is_published=False,
        backtest_results=None,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )


# ===================================================================
# Health
# ===================================================================


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-builder-api"


# ===================================================================
# Indicator Palette
# ===================================================================


class TestIndicatorPalette:
    def test_list_all_indicators(self, client):
        tc, _ = client
        resp = tc.get("/palette/indicators")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == len(INDICATOR_CATALOG)

    def test_list_indicators_by_category(self, client):
        tc, _ = client
        resp = tc.get("/palette/indicators?category=momentum")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] > 0
        for item in body["data"]:
            assert item["attributes"]["category"] == "momentum"

    def test_get_specific_indicator(self, client):
        tc, _ = client
        resp = tc.get("/palette/indicators/RSI")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["type"] == "RSI"
        assert len(attrs["params"]) > 0

    def test_get_unknown_indicator(self, client):
        tc, _ = client
        resp = tc.get("/palette/indicators/NONEXISTENT")
        assert resp.status_code == 404

    def test_list_conditions(self, client):
        tc, _ = client
        resp = tc.get("/palette/conditions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == len(CONDITION_TYPES)

    def test_list_indicator_categories(self, client):
        tc, _ = client
        resp = tc.get("/palette/categories")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] > 0


# ===================================================================
# Strategy CRUD
# ===================================================================


class TestCreateStrategy:
    def test_create_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = _fake_strategy_row(strategy_id)

        resp = tc.post("/strategies", json=_valid_strategy_body(), headers=HEADERS)
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(strategy_id)
        assert body["data"]["attributes"]["name"] == "My RSI Strategy"

    def test_create_missing_name(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        del body["name"]
        resp = tc.post("/strategies", json=body, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_invalid_indicator_type(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["indicators"][0]["type"] = "FAKE_INDICATOR"
        resp = tc.post("/strategies", json=body, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_invalid_condition_type(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["entry_conditions"][0]["type"] = "FAKE_CONDITION"
        resp = tc.post("/strategies", json=body, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_missing_indicators(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["indicators"] = []
        resp = tc.post("/strategies", json=body, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_duplicate_indicator_ids(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["indicators"] = [
            {
                "id": "same_id",
                "type": "RSI",
                "input": "close",
                "params": {"period": 14},
            },
            {
                "id": "same_id",
                "type": "SMA",
                "input": "close",
                "params": {"period": 20},
            },
        ]
        resp = tc.post("/strategies", json=body, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_bad_indicator_reference(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["entry_conditions"][0]["indicator"] = "nonexistent_indicator"
        resp = tc.post("/strategies", json=body, headers=HEADERS)
        assert resp.status_code == 422

    def test_create_missing_user_header(self, client):
        tc, _ = client
        resp = tc.post("/strategies", json=_valid_strategy_body())
        assert resp.status_code == 422


class TestListStrategies:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetch.return_value = [_fake_strategy_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/strategies", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1

    def test_list_with_search(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies?search=rsi", headers=HEADERS)
        assert resp.status_code == 200

    def test_list_with_category(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies?category=momentum", headers=HEADERS)
        assert resp.status_code == 200


class TestGetStrategy:
    def test_get_found(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = _fake_strategy_row(strategy_id)

        resp = tc.get(f"/strategies/{strategy_id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == str(strategy_id)

    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}", headers=HEADERS)
        assert resp.status_code == 404


class TestUpdateStrategy:
    def test_update_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        updated_row = _fake_strategy_row(strategy_id)
        updated_row["version"] = 2
        conn.fetchrow.return_value = updated_row

        resp = tc.put(
            f"/strategies/{strategy_id}",
            json={"name": "Updated Name", "version": 1},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_update_version_conflict(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            None,  # UPDATE returns nothing (version mismatch)
            FakeRecord(version=3),  # Exists check
        ]

        resp = tc.put(
            f"/strategies/{strategy_id}",
            json={"name": "Updated Name", "version": 1},
            headers=HEADERS,
        )
        assert resp.status_code == 409

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [None, None]

        resp = tc.put(
            f"/strategies/{uuid.uuid4()}",
            json={"name": "Updated Name", "version": 1},
            headers=HEADERS,
        )
        assert resp.status_code == 404


class TestDeleteStrategy:
    def test_delete_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=strategy_id)

        resp = tc.delete(f"/strategies/{strategy_id}", headers=HEADERS)
        assert resp.status_code == 204

    def test_delete_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/strategies/{uuid.uuid4()}", headers=HEADERS)
        assert resp.status_code == 404


# ===================================================================
# Validation
# ===================================================================


class TestValidation:
    def test_validate_valid_config(self, client):
        tc, _ = client
        resp = tc.post("/strategies/validate", json=_valid_strategy_body())
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["valid"] is True
        assert attrs["errors"] == []

    def test_validate_duplicate_indicator_ids(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["indicators"] = [
            {"id": "dup", "type": "RSI", "input": "close", "params": {"period": 14}},
            {"id": "dup", "type": "SMA", "input": "close", "params": {"period": 20}},
        ]
        resp = tc.post("/strategies/validate", json=body)
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["valid"] is False
        assert len(attrs["errors"]) > 0

    def test_validate_bad_indicator_reference(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["entry_conditions"][0]["indicator"] = "no_such_indicator"
        resp = tc.post("/strategies/validate", json=body)
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["valid"] is False

    def test_validate_param_out_of_range(self, client):
        tc, _ = client
        body = _valid_strategy_body()
        body["indicators"][0]["params"]["period"] = 999  # max is 200 for RSI
        resp = tc.post("/strategies/validate", json=body)
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["valid"] is False


# ===================================================================
# Backtest
# ===================================================================


class TestBacktest:
    def test_backtest_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=strategy_id,
            indicators=json.dumps(
                [
                    {
                        "id": "sma_short",
                        "type": "SMA",
                        "input": "close",
                        "params": {"period": 10},
                    },
                ]
            ),
            entry_conditions=json.dumps(
                [{"type": "CrossedUp", "indicator": "sma_short", "params": {}}]
            ),
            exit_conditions=json.dumps(
                [{"type": "CrossedDown", "indicator": "sma_short", "params": {}}]
            ),
        )
        # Return enough candle data
        candle_rows = [
            FakeRecord(
                timestamp=datetime(2026, 1, 1, i, tzinfo=timezone.utc),
                open=100 + i * 0.5,
                high=101 + i * 0.5,
                low=99 + i * 0.5,
                close=100 + i * 0.5 + (1 if i % 10 < 5 else -1),
                volume=1000,
            )
            for i in range(100)
        ]
        conn.fetch.return_value = candle_rows

        resp = tc.post(
            f"/strategies/{strategy_id}/backtest",
            json={"symbol": "BTC/USD"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert "total_return_pct" in attrs
        assert "sharpe_ratio" in attrs
        assert "win_rate" in attrs
        assert "total_trades" in attrs

    def test_backtest_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/backtest",
            json={"symbol": "BTC/USD"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_backtest_insufficient_data(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=strategy_id,
            indicators=json.dumps(
                [
                    {
                        "id": "rsi_1",
                        "type": "RSI",
                        "input": "close",
                        "params": {"period": 14},
                    }
                ]
            ),
            entry_conditions=json.dumps(
                [{"type": "CrossedDown", "indicator": "rsi_1", "params": {}}]
            ),
            exit_conditions=json.dumps(
                [{"type": "CrossedUp", "indicator": "rsi_1", "params": {}}]
            ),
        )
        conn.fetch.return_value = [
            FakeRecord(
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1000,
            )
        ] * 5  # Only 5 candles

        resp = tc.post(
            f"/strategies/{strategy_id}/backtest",
            json={"symbol": "BTC/USD"},
            headers=HEADERS,
        )
        assert resp.status_code == 422


# ===================================================================
# Publish to Marketplace
# ===================================================================


class TestPublish:
    def test_publish_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        listing_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            # First call: fetch strategy
            FakeRecord(
                id=strategy_id,
                name="My Strategy",
                description="Test",
                category="momentum",
                tags=json.dumps(["rsi"]),
                backtest_results=json.dumps(
                    {"total_return_pct": 15.5, "sharpe_ratio": 1.2}
                ),
                is_published=False,
            ),
            # Second call: insert listing
            FakeRecord(
                id=listing_id,
                strategy_id=strategy_id,
                name="My Strategy",
                author=USER_ID,
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            f"/strategies/{strategy_id}/publish",
            json={"price": 0},
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["id"] == str(listing_id)

    def test_publish_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/publish",
            json={"price": 0},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_publish_already_published(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=strategy_id,
            name="My Strategy",
            description="Test",
            category="momentum",
            tags=json.dumps(["rsi"]),
            backtest_results=None,
            is_published=True,
        )

        resp = tc.post(
            f"/strategies/{strategy_id}/publish",
            json={"price": 0},
            headers=HEADERS,
        )
        assert resp.status_code == 409


# ===================================================================
# Unit tests for validation logic
# ===================================================================


class TestValidateStrategyConfig:
    def test_valid_config(self):
        config = StrategyConfigDTO(
            name="Test",
            indicators=[
                IndicatorConfigDTO(
                    id="rsi_1", type="RSI", input="close", params={"period": 14}
                ),
                IndicatorConfigDTO(
                    id="const_1", type="CONSTANT", input="close", params={"value": 30}
                ),
            ],
            entry_conditions=[
                ConditionConfigDTO(
                    type="CrossedDown",
                    indicator="rsi_1",
                    params={"reference": "const_1"},
                ),
            ],
            exit_conditions=[
                ConditionConfigDTO(
                    type="CrossedUp", indicator="rsi_1", params={"reference": "const_1"}
                ),
            ],
        )
        errors = validate_strategy_config(config)
        assert errors == []

    def test_duplicate_indicator_ids(self):
        config = StrategyConfigDTO(
            name="Test",
            indicators=[
                IndicatorConfigDTO(id="dup", type="RSI", input="close", params={}),
                IndicatorConfigDTO(id="dup", type="SMA", input="close", params={}),
            ],
            entry_conditions=[
                ConditionConfigDTO(type="CrossedUp", indicator="dup", params={})
            ],
            exit_conditions=[
                ConditionConfigDTO(type="CrossedDown", indicator="dup", params={})
            ],
        )
        errors = validate_strategy_config(config)
        assert any("unique" in e["message"].lower() for e in errors)

    def test_invalid_indicator_reference(self):
        config = StrategyConfigDTO(
            name="Test",
            indicators=[
                IndicatorConfigDTO(id="rsi_1", type="RSI", input="close", params={}),
            ],
            entry_conditions=[
                ConditionConfigDTO(
                    type="CrossedUp", indicator="nonexistent", params={}
                ),
            ],
            exit_conditions=[
                ConditionConfigDTO(type="CrossedDown", indicator="rsi_1", params={}),
            ],
        )
        errors = validate_strategy_config(config)
        assert any("nonexistent" in e["message"] for e in errors)

    def test_param_below_minimum(self):
        config = StrategyConfigDTO(
            name="Test",
            indicators=[
                IndicatorConfigDTO(
                    id="rsi_1", type="RSI", input="close", params={"period": 0}
                ),
            ],
            entry_conditions=[
                ConditionConfigDTO(type="CrossedUp", indicator="rsi_1", params={})
            ],
            exit_conditions=[
                ConditionConfigDTO(type="CrossedDown", indicator="rsi_1", params={})
            ],
        )
        errors = validate_strategy_config(config)
        assert any("below minimum" in e["message"].lower() for e in errors)

    def test_param_above_maximum(self):
        config = StrategyConfigDTO(
            name="Test",
            indicators=[
                IndicatorConfigDTO(
                    id="rsi_1", type="RSI", input="close", params={"period": 999}
                ),
            ],
            entry_conditions=[
                ConditionConfigDTO(type="CrossedUp", indicator="rsi_1", params={})
            ],
            exit_conditions=[
                ConditionConfigDTO(type="CrossedDown", indicator="rsi_1", params={})
            ],
        )
        errors = validate_strategy_config(config)
        assert any("above maximum" in e["message"].lower() for e in errors)


# ===================================================================
# Unit tests for simple backtest engine
# ===================================================================


class TestSimpleBacktest:
    def test_basic_backtest(self):
        # Create price data with a clear trend reversal
        candles = []
        for i in range(100):
            price = 100 + (i if i < 50 else 100 - i)
            candles.append(
                {
                    "open": price - 0.5,
                    "high": price + 1,
                    "low": price - 1,
                    "close": price,
                    "volume": 1000,
                }
            )

        indicators = [{"id": "sma_1", "type": "SMA", "params": {"period": 10}}]
        entry_conds = [{"type": "CrossedUp", "indicator": "sma_1", "params": {}}]
        exit_conds = [{"type": "CrossedDown", "indicator": "sma_1", "params": {}}]

        result = _run_simple_backtest(candles, indicators, entry_conds, exit_conds)
        assert "total_return_pct" in result
        assert "sharpe_ratio" in result
        assert "win_rate" in result
        assert "max_drawdown_pct" in result
        assert "total_trades" in result
        assert result["candles_analyzed"] == 100

    def test_empty_candles(self):
        result = _run_simple_backtest([], [], [], [])
        assert result.get("error") == "No candle data"

    def test_flat_market_no_trades(self):
        candles = [
            {"open": 100, "high": 100, "low": 100, "close": 100, "volume": 1000}
            for _ in range(100)
        ]
        result = _run_simple_backtest(candles, [], [], [])
        assert result["total_trades"] == 0
        assert result["total_return_pct"] == 0.0
