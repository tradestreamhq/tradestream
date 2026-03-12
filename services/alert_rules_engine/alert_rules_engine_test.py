"""Tests for the alert rules engine."""

import json
import time
from unittest import mock

import pytest

from services.alert_rules_engine.actions import dispatch_action
from services.alert_rules_engine.conditions import evaluate_condition
from services.alert_rules_engine.config import get_config
from services.alert_rules_engine.engine import AlertEngine
from services.alert_rules_engine.models import (
    ActionType,
    AlertAction,
    AlertCondition,
    AlertEvent,
    AlertRule,
    ConditionType,
)
from services.alert_rules_engine.rule_store import RuleStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(
    condition_type=ConditionType.PRICE_ABOVE,
    condition_params=None,
    action_type=ActionType.IN_APP,
    action_params=None,
    cooldown=300,
    enabled=True,
    name="Test Rule",
) -> AlertRule:
    return AlertRule(
        rule_id="",
        name=name,
        condition=AlertCondition(
            condition_type=condition_type,
            params=condition_params or {},
        ),
        action=AlertAction(
            action_type=action_type,
            params=action_params or {},
        ),
        cooldown_seconds=cooldown,
        enabled=enabled,
    )


def _make_mock_redis():
    """Create a mock Redis with hash and list operations."""
    hashes = {}
    lists = {}

    def hset(key, field, value):
        hashes.setdefault(key, {})[field] = value

    def hget(key, field):
        return hashes.get(key, {}).get(field)

    def hgetall(key):
        return dict(hashes.get(key, {}))

    def hdel(key, field):
        if key in hashes and field in hashes[key]:
            del hashes[key][field]
            return 1
        return 0

    def lpush(key, value):
        lists.setdefault(key, []).insert(0, value)

    def ltrim(key, start, end):
        if key in lists:
            lists[key] = lists[key][start : end + 1]

    def expire(key, ttl):
        pass

    def lrange(key, start, end):
        if key not in lists:
            return []
        return lists[key][start : end + 1 if end >= 0 else None]

    mock_redis = mock.MagicMock()
    mock_redis.hset = mock.MagicMock(side_effect=hset)
    mock_redis.hget = mock.MagicMock(side_effect=hget)
    mock_redis.hgetall = mock.MagicMock(side_effect=hgetall)
    mock_redis.hdel = mock.MagicMock(side_effect=hdel)

    mock_pipe = mock.MagicMock()
    mock_pipe.lpush = mock.MagicMock(side_effect=lpush)
    mock_pipe.ltrim = mock.MagicMock(side_effect=ltrim)
    mock_pipe.expire = mock.MagicMock(side_effect=expire)
    mock_pipe.execute = mock.MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.lrange = mock.MagicMock(side_effect=lrange)
    return mock_redis


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestAlertRule:
    def test_auto_generates_id(self):
        rule = _make_rule()
        assert len(rule.rule_id) == 16

    def test_auto_sets_created_at(self):
        rule = _make_rule()
        assert rule.created_at > 0

    def test_not_in_cooldown_when_never_triggered(self):
        rule = _make_rule(cooldown=60)
        assert not rule.is_in_cooldown()

    def test_in_cooldown_after_trigger(self):
        rule = _make_rule(cooldown=60)
        now = time.time()
        rule.last_triggered_at = now - 30  # 30s ago, cooldown is 60s
        assert rule.is_in_cooldown(now)

    def test_not_in_cooldown_after_expiry(self):
        rule = _make_rule(cooldown=60)
        now = time.time()
        rule.last_triggered_at = now - 120  # 120s ago, cooldown is 60s
        assert not rule.is_in_cooldown(now)

    def test_to_dict_and_from_dict_roundtrip(self):
        rule = _make_rule(
            condition_type=ConditionType.DRAWDOWN_EXCEEDS,
            condition_params={"threshold": 0.05},
            action_type=ActionType.WEBHOOK,
            action_params={"url": "https://example.com"},
        )
        d = rule.to_dict()
        restored = AlertRule.from_dict(d)
        assert restored.rule_id == rule.rule_id
        assert restored.condition.condition_type == ConditionType.DRAWDOWN_EXCEEDS
        assert restored.condition.params["threshold"] == 0.05
        assert restored.action.action_type == ActionType.WEBHOOK
        assert restored.action.params["url"] == "https://example.com"
        assert restored.cooldown_seconds == rule.cooldown_seconds


class TestAlertEvent:
    def test_auto_generates_id(self):
        event = AlertEvent(
            event_id="",
            rule_id="r1",
            rule_name="Test",
            condition_type="price_above",
            message="Price rose",
        )
        assert len(event.event_id) == 16

    def test_auto_sets_timestamp(self):
        event = AlertEvent(
            event_id="",
            rule_id="r1",
            rule_name="Test",
            condition_type="price_above",
            message="Price rose",
        )
        assert event.timestamp > 0


# ---------------------------------------------------------------------------
# Condition Tests
# ---------------------------------------------------------------------------


class TestPriceAboveCondition:
    def test_triggers_when_price_above_threshold(self):
        cond = AlertCondition(
            condition_type=ConditionType.PRICE_ABOVE,
            params={"symbol": "BTC/USD", "threshold": 50000},
        )
        market = {"BTC/USD": {"price": 51000}}
        triggered, msg, ctx = evaluate_condition(cond, market, {})
        assert triggered
        assert "51,000" in msg
        assert ctx["price"] == 51000

    def test_does_not_trigger_when_below(self):
        cond = AlertCondition(
            condition_type=ConditionType.PRICE_ABOVE,
            params={"symbol": "BTC/USD", "threshold": 50000},
        )
        market = {"BTC/USD": {"price": 49000}}
        triggered, msg, ctx = evaluate_condition(cond, market, {})
        assert not triggered

    def test_does_not_trigger_when_symbol_missing(self):
        cond = AlertCondition(
            condition_type=ConditionType.PRICE_ABOVE,
            params={"symbol": "ETH/USD", "threshold": 3000},
        )
        triggered, msg, ctx = evaluate_condition(cond, {}, {})
        assert not triggered


class TestPriceBelowCondition:
    def test_triggers_when_price_below_threshold(self):
        cond = AlertCondition(
            condition_type=ConditionType.PRICE_BELOW,
            params={"symbol": "BTC/USD", "threshold": 40000},
        )
        market = {"BTC/USD": {"price": 39000}}
        triggered, msg, ctx = evaluate_condition(cond, market, {})
        assert triggered
        assert "dropped below" in msg

    def test_does_not_trigger_when_above(self):
        cond = AlertCondition(
            condition_type=ConditionType.PRICE_BELOW,
            params={"symbol": "BTC/USD", "threshold": 40000},
        )
        market = {"BTC/USD": {"price": 41000}}
        triggered, msg, ctx = evaluate_condition(cond, market, {})
        assert not triggered


class TestDrawdownCondition:
    def test_triggers_when_drawdown_exceeds_threshold(self):
        cond = AlertCondition(
            condition_type=ConditionType.DRAWDOWN_EXCEEDS,
            params={"threshold": 0.05},
        )
        portfolio = {"daily_drawdown": 0.08}
        triggered, msg, ctx = evaluate_condition(cond, {}, portfolio)
        assert triggered
        assert "8.0%" in msg

    def test_does_not_trigger_when_below_threshold(self):
        cond = AlertCondition(
            condition_type=ConditionType.DRAWDOWN_EXCEEDS,
            params={"threshold": 0.10},
        )
        portfolio = {"daily_drawdown": 0.03}
        triggered, msg, ctx = evaluate_condition(cond, {}, portfolio)
        assert not triggered


class TestPortfolioHeatCondition:
    def test_triggers_when_heat_exceeds(self):
        cond = AlertCondition(
            condition_type=ConditionType.PORTFOLIO_HEAT_EXCEEDS,
            params={"threshold": 0.20},
        )
        portfolio = {"portfolio_heat": 0.30}
        triggered, msg, ctx = evaluate_condition(cond, {}, portfolio)
        assert triggered
        assert "30.0%" in msg

    def test_does_not_trigger_when_below(self):
        cond = AlertCondition(
            condition_type=ConditionType.PORTFOLIO_HEAT_EXCEEDS,
            params={"threshold": 0.50},
        )
        portfolio = {"portfolio_heat": 0.25}
        triggered, msg, ctx = evaluate_condition(cond, {}, portfolio)
        assert not triggered


class TestSignalMatchCondition:
    def test_triggers_on_matching_signal(self):
        cond = AlertCondition(
            condition_type=ConditionType.SIGNAL_MATCH,
            params={"symbol": "BTC/USD", "action": "BUY"},
        )
        signal = {"symbol": "BTC/USD", "action": "BUY", "confidence": 0.9}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, signal_data=signal)
        assert triggered
        assert "BUY" in msg

    def test_does_not_trigger_wrong_symbol(self):
        cond = AlertCondition(
            condition_type=ConditionType.SIGNAL_MATCH,
            params={"symbol": "ETH/USD", "action": "BUY"},
        )
        signal = {"symbol": "BTC/USD", "action": "BUY", "confidence": 0.9}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, signal_data=signal)
        assert not triggered

    def test_does_not_trigger_wrong_action(self):
        cond = AlertCondition(
            condition_type=ConditionType.SIGNAL_MATCH,
            params={"symbol": "BTC/USD", "action": "SELL"},
        )
        signal = {"symbol": "BTC/USD", "action": "BUY", "confidence": 0.9}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, signal_data=signal)
        assert not triggered

    def test_does_not_trigger_low_confidence(self):
        cond = AlertCondition(
            condition_type=ConditionType.SIGNAL_MATCH,
            params={"symbol": "BTC/USD", "min_confidence": 0.8},
        )
        signal = {"symbol": "BTC/USD", "action": "BUY", "confidence": 0.5}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, signal_data=signal)
        assert not triggered

    def test_does_not_trigger_without_signal(self):
        cond = AlertCondition(
            condition_type=ConditionType.SIGNAL_MATCH,
            params={"symbol": "BTC/USD"},
        )
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, signal_data=None)
        assert not triggered

    def test_triggers_any_symbol_when_no_filter(self):
        cond = AlertCondition(
            condition_type=ConditionType.SIGNAL_MATCH,
            params={"action": "SELL"},
        )
        signal = {"symbol": "DOGE/USD", "action": "SELL", "confidence": 0.7}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, signal_data=signal)
        assert triggered


class TestRegimeChangeCondition:
    def test_triggers_on_regime_change(self):
        cond = AlertCondition(
            condition_type=ConditionType.REGIME_CHANGE,
            params={},
        )
        regime = {"current_regime": "volatile", "previous_regime": "trending"}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, regime_data=regime)
        assert triggered
        assert "trending" in msg
        assert "volatile" in msg

    def test_does_not_trigger_same_regime(self):
        cond = AlertCondition(
            condition_type=ConditionType.REGIME_CHANGE,
            params={},
        )
        regime = {"current_regime": "trending", "previous_regime": "trending"}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, regime_data=regime)
        assert not triggered

    def test_filters_by_from_regime(self):
        cond = AlertCondition(
            condition_type=ConditionType.REGIME_CHANGE,
            params={"from_regime": "calm"},
        )
        regime = {"current_regime": "volatile", "previous_regime": "trending"}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, regime_data=regime)
        assert not triggered

    def test_filters_by_to_regime(self):
        cond = AlertCondition(
            condition_type=ConditionType.REGIME_CHANGE,
            params={"to_regime": "crash"},
        )
        regime = {"current_regime": "volatile", "previous_regime": "trending"}
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, regime_data=regime)
        assert not triggered

    def test_does_not_trigger_without_regime_data(self):
        cond = AlertCondition(
            condition_type=ConditionType.REGIME_CHANGE,
            params={},
        )
        triggered, msg, ctx = evaluate_condition(cond, {}, {}, regime_data=None)
        assert not triggered


# ---------------------------------------------------------------------------
# Rule Store Tests
# ---------------------------------------------------------------------------


class TestRuleStore:
    def test_create_and_get(self):
        store = RuleStore(_make_mock_redis())
        rule = _make_rule(name="My Rule")
        store.create(rule)
        fetched = store.get(rule.rule_id)
        assert fetched is not None
        assert fetched.name == "My Rule"
        assert fetched.rule_id == rule.rule_id

    def test_get_nonexistent(self):
        store = RuleStore(_make_mock_redis())
        assert store.get("nonexistent") is None

    def test_list_all(self):
        store = RuleStore(_make_mock_redis())
        r1 = _make_rule(name="Rule 1")
        r2 = _make_rule(name="Rule 2")
        store.create(r1)
        store.create(r2)
        rules = store.list_all()
        assert len(rules) == 2
        names = {r.name for r in rules}
        assert names == {"Rule 1", "Rule 2"}

    def test_list_enabled(self):
        store = RuleStore(_make_mock_redis())
        r1 = _make_rule(name="Enabled", enabled=True)
        r2 = _make_rule(name="Disabled", enabled=False)
        store.create(r1)
        store.create(r2)
        enabled = store.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "Enabled"

    def test_update(self):
        store = RuleStore(_make_mock_redis())
        rule = _make_rule(name="Original")
        store.create(rule)
        rule.name = "Updated"
        store.update(rule)
        fetched = store.get(rule.rule_id)
        assert fetched.name == "Updated"

    def test_delete(self):
        store = RuleStore(_make_mock_redis())
        rule = _make_rule()
        store.create(rule)
        assert store.delete(rule.rule_id) is True
        assert store.get(rule.rule_id) is None

    def test_delete_nonexistent(self):
        store = RuleStore(_make_mock_redis())
        assert store.delete("nonexistent") is False

    def test_mark_triggered(self):
        store = RuleStore(_make_mock_redis())
        rule = _make_rule()
        store.create(rule)
        now = time.time()
        store.mark_triggered(rule, now)
        fetched = store.get(rule.rule_id)
        assert fetched.last_triggered_at == now

    def test_record_and_get_events(self):
        store = RuleStore(_make_mock_redis())
        store.record_event({"rule_id": "r1", "message": "test alert"})
        events = store.get_recent_events(10)
        assert len(events) == 1
        assert events[0]["rule_id"] == "r1"


# ---------------------------------------------------------------------------
# Action Tests
# ---------------------------------------------------------------------------


class TestActions:
    def test_in_app_always_succeeds(self):
        assert dispatch_action("in_app", {}, "test", {}) is True

    def test_email_requires_to(self):
        assert dispatch_action("email", {}, "test", {}) is False

    def test_email_succeeds_with_to(self):
        assert dispatch_action("email", {"to": "user@example.com"}, "test", {}) is True

    def test_sms_requires_phone(self):
        assert dispatch_action("sms", {}, "test", {}) is False

    def test_sms_succeeds_with_phone(self):
        assert dispatch_action("sms", {"phone": "+1234567890"}, "test", {}) is True

    def test_webhook_requires_url(self):
        assert dispatch_action("webhook", {}, "test", {}) is False

    @mock.patch("services.alert_rules_engine.actions.requests.post")
    def test_webhook_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        result = dispatch_action(
            "webhook",
            {"url": "https://example.com/hook"},
            "price alert",
            {"price": 50000},
        )
        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["alert_message"] == "price alert"

    @mock.patch("services.alert_rules_engine.actions.requests.post")
    def test_webhook_failure(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=500)
        result = dispatch_action(
            "webhook",
            {"url": "https://example.com/hook"},
            "test",
            {},
        )
        assert result is False

    def test_unknown_action_type(self):
        assert dispatch_action("carrier_pigeon", {}, "test", {}) is False


# ---------------------------------------------------------------------------
# Engine Tests
# ---------------------------------------------------------------------------


class TestAlertEngine:
    def _make_engine(self):
        redis = _make_mock_redis()
        store = RuleStore(redis)
        engine = AlertEngine(store)
        return engine, store

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_evaluates_price_rule(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {}
        mock_market.return_value = {"BTC/USD": {"price": 55000}}

        rule = _make_rule(
            condition_type=ConditionType.PRICE_ABOVE,
            condition_params={"symbol": "BTC/USD", "threshold": 50000},
        )
        store.create(rule)

        events = engine.evaluate_all()
        assert len(events) == 1
        assert "55,000" in events[0].message

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_respects_cooldown(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {}
        mock_market.return_value = {"BTC/USD": {"price": 55000}}

        rule = _make_rule(
            condition_type=ConditionType.PRICE_ABOVE,
            condition_params={"symbol": "BTC/USD", "threshold": 50000},
            cooldown=600,
        )
        store.create(rule)

        # First evaluation triggers
        events = engine.evaluate_all()
        assert len(events) == 1

        # Second evaluation within cooldown does not trigger
        events = engine.evaluate_all()
        assert len(events) == 0

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_skips_disabled_rules(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {}
        mock_market.return_value = {"BTC/USD": {"price": 55000}}

        rule = _make_rule(
            condition_type=ConditionType.PRICE_ABOVE,
            condition_params={"symbol": "BTC/USD", "threshold": 50000},
            enabled=False,
        )
        store.create(rule)

        events = engine.evaluate_all()
        assert len(events) == 0

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_evaluates_drawdown_rule(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {"daily_drawdown": 0.08}
        mock_market.return_value = {}

        rule = _make_rule(
            condition_type=ConditionType.DRAWDOWN_EXCEEDS,
            condition_params={"threshold": 0.05},
        )
        store.create(rule)

        events = engine.evaluate_all()
        assert len(events) == 1
        assert "drawdown" in events[0].message.lower()

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_evaluates_signal_match_rule(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {}
        mock_market.return_value = {}

        rule = _make_rule(
            condition_type=ConditionType.SIGNAL_MATCH,
            condition_params={"symbol": "BTC/USD", "action": "BUY"},
        )
        store.create(rule)

        engine.set_signal({"symbol": "BTC/USD", "action": "BUY", "confidence": 0.9})

        events = engine.evaluate_all()
        assert len(events) == 1
        assert "BUY" in events[0].message

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_evaluates_regime_change_rule(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {}
        mock_market.return_value = {}

        rule = _make_rule(
            condition_type=ConditionType.REGIME_CHANGE,
            condition_params={},
        )
        store.create(rule)

        engine.set_regime({"current_regime": "volatile", "previous_regime": "trending"})

        events = engine.evaluate_all()
        assert len(events) == 1
        assert "regime" in events[0].message.lower()

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_no_events_when_no_rules(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        events = engine.evaluate_all()
        assert len(events) == 0
        # Should not even fetch data when there are no rules
        mock_portfolio.assert_not_called()
        mock_market.assert_not_called()

    @mock.patch.object(AlertEngine, "fetch_market_data")
    @mock.patch.object(AlertEngine, "fetch_portfolio_data")
    def test_multiple_rules_independent(self, mock_portfolio, mock_market):
        engine, store = self._make_engine()
        mock_portfolio.return_value = {"daily_drawdown": 0.08}
        mock_market.return_value = {"BTC/USD": {"price": 55000}}

        r1 = _make_rule(
            condition_type=ConditionType.PRICE_ABOVE,
            condition_params={"symbol": "BTC/USD", "threshold": 50000},
            name="Price Alert",
        )
        r2 = _make_rule(
            condition_type=ConditionType.DRAWDOWN_EXCEEDS,
            condition_params={"threshold": 0.05},
            name="Drawdown Alert",
        )
        store.create(r1)
        store.create(r2)

        events = engine.evaluate_all()
        assert len(events) == 2
        names = {e.rule_name for e in events}
        assert names == {"Price Alert", "Drawdown Alert"}


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestConfig:
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_defaults(self):
        config = get_config()
        assert config["redis_host"] == "localhost"
        assert config["redis_port"] == 6379
        assert config["eval_interval_seconds"] == 30
        assert config["api_port"] == 8098

    @mock.patch.dict(
        "os.environ",
        {
            "REDIS_HOST": "redis.prod",
            "REDIS_PORT": "6380",
            "EVAL_INTERVAL_SECONDS": "10",
            "PORTFOLIO_URL": "http://portfolio:8095",
            "MARKET_DATA_URL": "http://market:8081",
            "ALERT_API_PORT": "9090",
        },
    )
    def test_from_env(self):
        config = get_config()
        assert config["redis_host"] == "redis.prod"
        assert config["redis_port"] == 6380
        assert config["eval_interval_seconds"] == 10
        assert config["portfolio_url"] == "http://portfolio:8095"
        assert config["market_data_url"] == "http://market:8081"
        assert config["api_port"] == 9090


# ---------------------------------------------------------------------------
# REST API Tests
# ---------------------------------------------------------------------------


class TestAPI:
    def _make_app(self):
        redis = _make_mock_redis()
        store = RuleStore(redis)
        engine = AlertEngine(store)
        from services.alert_rules_engine.main import create_api

        flask_app = create_api(store, engine)
        flask_app.config["TESTING"] = True
        return flask_app.test_client(), store

    def test_health(self):
        client, _ = self._make_app()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_create_and_list_rules(self):
        client, _ = self._make_app()
        resp = client.post(
            "/rules",
            json={
                "name": "BTC Price Alert",
                "condition": {
                    "condition_type": "price_above",
                    "params": {"symbol": "BTC/USD", "threshold": 50000},
                },
                "action": {"action_type": "in_app", "params": {}},
                "cooldown_seconds": 60,
            },
        )
        assert resp.status_code == 201
        rule_id = resp.get_json()["rule_id"]

        resp = client.get("/rules")
        assert resp.status_code == 200
        rules = resp.get_json()["rules"]
        assert len(rules) == 1
        assert rules[0]["name"] == "BTC Price Alert"

    def test_get_rule(self):
        client, store = self._make_app()
        rule = _make_rule(name="Test")
        store.create(rule)

        resp = client.get(f"/rules/{rule.rule_id}")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Test"

    def test_get_rule_not_found(self):
        client, _ = self._make_app()
        resp = client.get("/rules/nonexistent")
        assert resp.status_code == 404

    def test_update_rule(self):
        client, store = self._make_app()
        rule = _make_rule(name="Original")
        store.create(rule)

        resp = client.put(
            f"/rules/{rule.rule_id}",
            json={"name": "Updated", "cooldown_seconds": 120},
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Updated"
        assert resp.get_json()["cooldown_seconds"] == 120

    def test_delete_rule(self):
        client, store = self._make_app()
        rule = _make_rule()
        store.create(rule)

        resp = client.delete(f"/rules/{rule.rule_id}")
        assert resp.status_code == 200
        assert resp.get_json()["deleted"] is True

        resp = client.delete(f"/rules/{rule.rule_id}")
        assert resp.status_code == 404

    def test_enable_disable_rule(self):
        client, store = self._make_app()
        rule = _make_rule(enabled=True)
        store.create(rule)

        resp = client.post(f"/rules/{rule.rule_id}/disable")
        assert resp.status_code == 200
        assert resp.get_json()["enabled"] is False

        resp = client.post(f"/rules/{rule.rule_id}/enable")
        assert resp.status_code == 200
        assert resp.get_json()["enabled"] is True

    def test_create_rule_invalid(self):
        client, _ = self._make_app()
        resp = client.post("/rules", json={})
        assert resp.status_code == 400

    def test_list_events(self):
        client, store = self._make_app()
        store.record_event({"rule_id": "r1", "message": "test"})
        resp = client.get("/events")
        assert resp.status_code == 200
        assert len(resp.get_json()["events"]) == 1
