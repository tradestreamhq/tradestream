"""Tests for strategy template library and API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_api.app import create_app
from services.strategy_api.templates import (
    Signal,
    _ema,
    _rsi,
    _sma,
    build_default_registry,
    default_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Template registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_default_registry_has_five_templates(self):
        templates = default_registry.list_all()
        assert len(templates) == 5

    def test_template_ids(self):
        expected = {"sma_crossover", "rsi_mean_reversion", "breakout", "momentum", "vwap"}
        actual = {t.id for t in default_registry.list_all()}
        assert actual == expected

    def test_get_known_template(self):
        t = default_registry.get("sma_crossover")
        assert t is not None
        assert t.name == "SMA Crossover"

    def test_get_unknown_template(self):
        assert default_registry.get("nonexistent") is None

    def test_template_defaults(self):
        t = default_registry.get("rsi_mean_reversion")
        defaults = t.defaults()
        assert defaults["rsi_period"] == 14
        assert defaults["overbought"] == 70
        assert defaults["oversold"] == 30

    def test_validate_params_valid(self):
        t = default_registry.get("sma_crossover")
        errors = t.validate_params({"fast_period": 5, "slow_period": 20})
        assert errors == []

    def test_validate_params_out_of_range(self):
        t = default_registry.get("sma_crossover")
        errors = t.validate_params({"fast_period": 0, "slow_period": 20})
        assert len(errors) == 1
        assert "fast_period" in errors[0]

    def test_validate_params_wrong_type(self):
        t = default_registry.get("sma_crossover")
        errors = t.validate_params({"fast_period": "abc"})
        assert len(errors) == 1

    def test_merge_params(self):
        t = default_registry.get("sma_crossover")
        merged = t.merge_params({"fast_period": 5})
        assert merged["fast_period"] == 5
        assert merged["slow_period"] == 30  # default

    def test_to_summary(self):
        t = default_registry.get("breakout")
        summary = t.to_summary()
        assert "id" in summary
        assert "name" in summary
        assert "description" in summary
        assert "category" in summary
        assert "parameters" not in summary

    def test_to_detail(self):
        t = default_registry.get("breakout")
        detail = t.to_detail()
        assert "parameters" in detail
        assert "defaults" in detail
        assert len(detail["parameters"]) == 2


# ---------------------------------------------------------------------------
# Signal logic tests — indicator helpers
# ---------------------------------------------------------------------------


class TestIndicatorHelpers:
    def test_sma_basic(self):
        assert _sma([1, 2, 3, 4, 5], 3) == pytest.approx(4.0)

    def test_sma_insufficient_data(self):
        assert _sma([1, 2], 5) is None

    def test_rsi_all_gains(self):
        closes = [10, 11, 12, 13, 14, 15, 16]
        assert _rsi(closes, 5) == pytest.approx(100.0)

    def test_rsi_all_losses(self):
        closes = [16, 15, 14, 13, 12, 11, 10]
        rsi_val = _rsi(closes, 5)
        assert rsi_val is not None
        assert rsi_val < 1  # near zero

    def test_rsi_insufficient_data(self):
        assert _rsi([1, 2], 5) is None

    def test_ema_basic(self):
        vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = _ema(vals, 3)
        assert result is not None
        assert isinstance(result, float)

    def test_ema_insufficient_data(self):
        assert _ema([1, 2], 5) is None


# ---------------------------------------------------------------------------
# Signal logic tests — SMA Crossover
# ---------------------------------------------------------------------------


class TestSMACrossoverSignal:
    def test_buy_signal(self):
        # Fast SMA > Slow SMA → BUY
        # 30 data points, recent prices rising
        closes = list(range(1, 31))
        t = default_registry.get("sma_crossover")
        signal = t.signal_fn({"fast_period": 5, "slow_period": 20}, {"closes": closes})
        assert signal == Signal.BUY

    def test_sell_signal(self):
        # Fast SMA < Slow SMA → SELL
        closes = list(range(30, 0, -1))
        t = default_registry.get("sma_crossover")
        signal = t.signal_fn({"fast_period": 5, "slow_period": 20}, {"closes": closes})
        assert signal == Signal.SELL

    def test_insufficient_data(self):
        t = default_registry.get("sma_crossover")
        signal = t.signal_fn({"fast_period": 5, "slow_period": 20}, {"closes": [1, 2, 3]})
        assert signal == Signal.HOLD


# ---------------------------------------------------------------------------
# Signal logic tests — RSI Mean Reversion
# ---------------------------------------------------------------------------


class TestRSIMeanReversionSignal:
    def test_oversold_buy(self):
        # Falling prices → low RSI → BUY
        closes = [50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35]
        t = default_registry.get("rsi_mean_reversion")
        signal = t.signal_fn(
            {"rsi_period": 14, "overbought": 70, "oversold": 30}, {"closes": closes}
        )
        assert signal == Signal.BUY

    def test_overbought_sell(self):
        # Rising prices → high RSI → SELL
        closes = [35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50]
        t = default_registry.get("rsi_mean_reversion")
        signal = t.signal_fn(
            {"rsi_period": 14, "overbought": 70, "oversold": 30}, {"closes": closes}
        )
        assert signal == Signal.SELL

    def test_neutral_hold(self):
        # Mix of ups and downs → moderate RSI → HOLD
        closes = [40, 42, 41, 43, 40, 42, 41, 43, 40, 42, 41, 43, 40, 42, 41, 43]
        t = default_registry.get("rsi_mean_reversion")
        signal = t.signal_fn(
            {"rsi_period": 14, "overbought": 70, "oversold": 30}, {"closes": closes}
        )
        assert signal == Signal.HOLD


# ---------------------------------------------------------------------------
# Signal logic tests — Breakout
# ---------------------------------------------------------------------------


class TestBreakoutSignal:
    def test_upside_breakout(self):
        # Price breaks above recent high with volume surge
        closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 15]
        volumes = [100] * 20 + [200]
        t = default_registry.get("breakout")
        signal = t.signal_fn(
            {"lookback_period": 20, "volume_multiplier": 1.5},
            {"closes": closes, "volumes": volumes},
        )
        assert signal == Signal.BUY

    def test_downside_breakout(self):
        closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 5]
        volumes = [100] * 20 + [200]
        t = default_registry.get("breakout")
        signal = t.signal_fn(
            {"lookback_period": 20, "volume_multiplier": 1.5},
            {"closes": closes, "volumes": volumes},
        )
        assert signal == Signal.SELL

    def test_no_breakout(self):
        closes = [10] * 21
        volumes = [100] * 21
        t = default_registry.get("breakout")
        signal = t.signal_fn(
            {"lookback_period": 20, "volume_multiplier": 1.5},
            {"closes": closes, "volumes": volumes},
        )
        assert signal == Signal.HOLD

    def test_insufficient_volume(self):
        # Price breaks out but volume too low
        closes = [10] * 20 + [15]
        volumes = [100] * 20 + [110]  # only 1.1x, below 1.5x
        t = default_registry.get("breakout")
        signal = t.signal_fn(
            {"lookback_period": 20, "volume_multiplier": 1.5},
            {"closes": closes, "volumes": volumes},
        )
        assert signal == Signal.HOLD


# ---------------------------------------------------------------------------
# Signal logic tests — Momentum
# ---------------------------------------------------------------------------


class TestMomentumSignal:
    def test_positive_momentum_buy(self):
        # Strong upward momentum + price above EMA
        closes = list(range(80, 101))  # 80..100, 21 values
        t = default_registry.get("momentum")
        signal = t.signal_fn(
            {"momentum_period": 14, "ema_period": 20, "threshold": 2.0},
            {"closes": closes},
        )
        assert signal == Signal.BUY

    def test_negative_momentum_sell(self):
        closes = list(range(120, 99, -1))  # 120..100, 21 values
        t = default_registry.get("momentum")
        signal = t.signal_fn(
            {"momentum_period": 14, "ema_period": 20, "threshold": 2.0},
            {"closes": closes},
        )
        assert signal == Signal.SELL

    def test_weak_momentum_hold(self):
        closes = [100] * 21
        t = default_registry.get("momentum")
        signal = t.signal_fn(
            {"momentum_period": 14, "ema_period": 20, "threshold": 2.0},
            {"closes": closes},
        )
        assert signal == Signal.HOLD


# ---------------------------------------------------------------------------
# Signal logic tests — VWAP
# ---------------------------------------------------------------------------


class TestVWAPSignal:
    def test_below_vwap_buy(self):
        # Price well below VWAP → BUY
        closes = [100] * 19 + [90]
        highs = [102] * 19 + [91]
        lows = [98] * 19 + [89]
        volumes = [1000] * 20
        t = default_registry.get("vwap")
        signal = t.signal_fn(
            {"period": 20, "deviation_threshold": 0.02},
            {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes},
        )
        assert signal == Signal.BUY

    def test_above_vwap_sell(self):
        closes = [100] * 19 + [110]
        highs = [102] * 19 + [111]
        lows = [98] * 19 + [109]
        volumes = [1000] * 20
        t = default_registry.get("vwap")
        signal = t.signal_fn(
            {"period": 20, "deviation_threshold": 0.02},
            {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes},
        )
        assert signal == Signal.SELL

    def test_near_vwap_hold(self):
        closes = [100] * 20
        highs = [101] * 20
        lows = [99] * 20
        volumes = [1000] * 20
        t = default_registry.get("vwap")
        signal = t.signal_fn(
            {"period": 20, "deviation_threshold": 0.02},
            {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes},
        )
        assert signal == Signal.HOLD


# ---------------------------------------------------------------------------
# API endpoint tests — GET /templates
# ---------------------------------------------------------------------------


class TestTemplateEndpoints:
    def test_list_templates(self, client):
        tc, _ = client
        resp = tc.get("/templates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 5
        assert len(body["data"]) == 5
        for item in body["data"]:
            assert item["type"] == "strategy_template"
            assert "name" in item["attributes"]
            assert "description" in item["attributes"]

    def test_get_template_found(self, client):
        tc, _ = client
        resp = tc.get("/templates/sma_crossover")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "sma_crossover"
        attrs = body["data"]["attributes"]
        assert attrs["name"] == "SMA Crossover"
        assert "parameters" in attrs
        assert "defaults" in attrs
        assert len(attrs["parameters"]) == 2

    def test_get_template_not_found(self, client):
        tc, _ = client
        resp = tc.get("/templates/nonexistent")
        assert resp.status_code == 404

    def test_get_each_template(self, client):
        tc, _ = client
        for tid in ["sma_crossover", "rsi_mean_reversion", "breakout", "momentum", "vwap"]:
            resp = tc.get(f"/templates/{tid}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["data"]["id"] == tid
            assert len(body["data"]["attributes"]["parameters"]) > 0


# ---------------------------------------------------------------------------
# API endpoint tests — POST /from-template
# ---------------------------------------------------------------------------


class TestCreateFromTemplate:
    def test_create_from_template_success(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="my_sma",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/from-template",
            json={
                "template_id": "sma_crossover",
                "name": "my_sma",
                "parameters": {"fast_period": 5, "slow_period": 50},
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(spec_id)
        attrs = body["data"]["attributes"]
        assert attrs["template_id"] == "sma_crossover"
        assert attrs["parameters"]["fast_period"] == 5
        assert attrs["parameters"]["slow_period"] == 50

    def test_create_from_template_defaults(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="default_rsi",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/from-template",
            json={
                "template_id": "rsi_mean_reversion",
                "name": "default_rsi",
                "parameters": {},
            },
        )
        assert resp.status_code == 201
        attrs = resp.json()["data"]["attributes"]
        assert attrs["parameters"]["rsi_period"] == 14
        assert attrs["parameters"]["overbought"] == 70

    def test_create_from_template_unknown_template(self, client):
        tc, _ = client
        resp = tc.post(
            "/from-template",
            json={
                "template_id": "nonexistent",
                "name": "my_strat",
                "parameters": {},
            },
        )
        assert resp.status_code == 404

    def test_create_from_template_invalid_params(self, client):
        tc, _ = client
        resp = tc.post(
            "/from-template",
            json={
                "template_id": "sma_crossover",
                "name": "bad_params",
                "parameters": {"fast_period": 0},
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_create_from_template_missing_name(self, client):
        tc, _ = client
        resp = tc.post(
            "/from-template",
            json={"template_id": "sma_crossover"},
        )
        assert resp.status_code == 422
