"""Tests for the alert routing service."""

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from services.alert_router.app import create_app
from services.alert_router.channels import (
    CustomWebhookChannel,
    EmailChannel,
    InAppChannel,
    SlackWebhookChannel,
    create_channel,
)
from services.alert_router.models import (
    Alert,
    ChannelConfig,
    ChannelType,
    DeliveryStatus,
    RouteConfig,
    RoutingRule,
)
from services.alert_router.router import AlertRouter


# ---- Model Tests ----


class TestModels:
    def test_channel_config_roundtrip(self):
        config = ChannelConfig(
            channel_type=ChannelType.SLACK_WEBHOOK,
            name="my-slack",
            settings={"webhook_url": "https://hooks.slack.com/xxx"},
        )
        data = config.to_dict()
        restored = ChannelConfig.from_dict(data)
        assert restored.channel_type == ChannelType.SLACK_WEBHOOK
        assert restored.name == "my-slack"
        assert restored.settings["webhook_url"] == "https://hooks.slack.com/xxx"

    def test_route_config_roundtrip(self):
        config = RouteConfig(
            user_id="user-1",
            channels=[
                ChannelConfig(
                    channel_type=ChannelType.EMAIL,
                    name="email-1",
                    settings={"smtp_host": "smtp.example.com"},
                )
            ],
            rules=[RoutingRule(alert_type="trade_signal", channel_names=["email-1"])],
            default_channels=["email-1"],
        )
        data = config.to_dict()
        restored = RouteConfig.from_dict(data)
        assert restored.user_id == "user-1"
        assert len(restored.channels) == 1
        assert len(restored.rules) == 1
        assert restored.default_channels == ["email-1"]

    def test_alert_to_dict(self):
        alert = Alert(
            alert_type="price_alert",
            title="BTC above 50k",
            message="Bitcoin crossed $50,000",
            user_id="user-1",
        )
        data = alert.to_dict()
        assert data["alert_type"] == "price_alert"
        assert data["title"] == "BTC above 50k"
        assert "alert_id" in data
        assert "timestamp" in data


# ---- Channel Tests ----


class TestSlackWebhookChannel:
    def test_send_success(self):
        config = ChannelConfig(
            channel_type=ChannelType.SLACK_WEBHOOK,
            name="slack",
            settings={"webhook_url": "https://hooks.slack.com/test"},
        )
        channel = SlackWebhookChannel(config)
        alert = Alert(
            alert_type="signal",
            title="Test",
            message="test msg",
            user_id="u1",
        )

        with mock.patch("services.alert_router.channels.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            assert channel.send(alert) is True
            mock_post.assert_called_once()

    def test_send_no_url(self):
        config = ChannelConfig(
            channel_type=ChannelType.SLACK_WEBHOOK,
            name="slack",
            settings={},
        )
        channel = SlackWebhookChannel(config)
        alert = Alert(
            alert_type="signal", title="T", message="m", user_id="u1"
        )
        assert channel.send(alert) is False


class TestCustomWebhookChannel:
    def test_send_with_signing(self):
        config = ChannelConfig(
            channel_type=ChannelType.CUSTOM_WEBHOOK,
            name="wh",
            settings={
                "webhook_url": "https://example.com/hook",
                "signing_secret": "secret123",
            },
        )
        channel = CustomWebhookChannel(config)
        alert = Alert(
            alert_type="signal", title="T", message="m", user_id="u1"
        )

        with mock.patch("services.alert_router.channels.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            assert channel.send(alert) is True
            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
            assert "X-TradeStream-Signature" in headers
            assert "X-TradeStream-Timestamp" in headers


class TestEmailChannel:
    def test_send_no_config(self):
        config = ChannelConfig(
            channel_type=ChannelType.EMAIL,
            name="email",
            settings={},
        )
        channel = EmailChannel(config)
        alert = Alert(
            alert_type="signal", title="T", message="m", user_id="u1"
        )
        assert channel.send(alert) is False

    def test_send_success(self):
        config = ChannelConfig(
            channel_type=ChannelType.EMAIL,
            name="email",
            settings={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "username": "user",
                "password": "pass",
                "from_address": "alerts@example.com",
                "to_addresses": ["user@example.com"],
            },
        )
        channel = EmailChannel(config)
        alert = Alert(
            alert_type="signal", title="Test Alert", message="msg", user_id="u1"
        )

        with mock.patch("services.alert_router.channels.smtplib.SMTP") as mock_smtp:
            mock_server = mock.MagicMock()
            mock_smtp.return_value.__enter__ = mock.MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = mock.MagicMock(return_value=False)
            assert channel.send(alert) is True
            mock_server.sendmail.assert_called_once()


class TestInAppChannel:
    def test_send_with_store_fn(self):
        stored = []
        config = ChannelConfig(
            channel_type=ChannelType.IN_APP,
            name="in-app",
            settings={"store_fn": stored.append},
        )
        channel = InAppChannel(config)
        alert = Alert(
            alert_type="signal", title="T", message="m", user_id="u1"
        )
        assert channel.send(alert) is True
        assert len(stored) == 1

    def test_send_without_store_fn(self):
        config = ChannelConfig(
            channel_type=ChannelType.IN_APP,
            name="in-app",
            settings={},
        )
        channel = InAppChannel(config)
        alert = Alert(
            alert_type="signal", title="T", message="m", user_id="u1"
        )
        assert channel.send(alert) is True


class TestCreateChannel:
    def test_creates_correct_type(self):
        config = ChannelConfig(
            channel_type=ChannelType.SLACK_WEBHOOK,
            name="s",
            settings={"webhook_url": "https://example.com"},
        )
        ch = create_channel(config)
        assert isinstance(ch, SlackWebhookChannel)

    def test_unknown_type_raises(self):
        config = ChannelConfig(
            channel_type=ChannelType.EMAIL,
            name="e",
            settings={},
        )
        config.channel_type = mock.MagicMock()
        config.channel_type.value = "unknown"
        with pytest.raises(ValueError):
            create_channel(config)


# ---- Router Tests ----


class TestAlertRouter:
    def _make_router_with_config(self):
        router = AlertRouter()
        stored = []
        config = RouteConfig(
            user_id="user-1",
            channels=[
                ChannelConfig(
                    channel_type=ChannelType.IN_APP,
                    name="in-app",
                    settings={"store_fn": stored.append},
                ),
            ],
            rules=[
                RoutingRule(alert_type="trade_signal", channel_names=["in-app"]),
            ],
            default_channels=["in-app"],
        )
        router.set_route_config(config)
        return router, stored

    def test_route_alert_matching_rule(self):
        router, stored = self._make_router_with_config()
        alert = Alert(
            alert_type="trade_signal",
            title="Buy BTC",
            message="Strong signal",
            user_id="user-1",
        )
        records = router.route_alert(alert)
        assert len(records) == 1
        assert records[0].status == DeliveryStatus.DELIVERED
        assert len(stored) == 1

    def test_route_alert_uses_default_channels(self):
        router, stored = self._make_router_with_config()
        alert = Alert(
            alert_type="unknown_type",
            title="Something",
            message="msg",
            user_id="user-1",
        )
        records = router.route_alert(alert)
        assert len(records) == 1
        assert records[0].status == DeliveryStatus.DELIVERED

    def test_route_alert_no_config(self):
        router = AlertRouter()
        alert = Alert(
            alert_type="signal",
            title="T",
            message="m",
            user_id="no-such-user",
        )
        records = router.route_alert(alert)
        assert records == []

    def test_delivery_history(self):
        router, _ = self._make_router_with_config()
        alert = Alert(
            alert_type="trade_signal",
            title="T",
            message="m",
            user_id="user-1",
        )
        router.route_alert(alert)
        history = router.get_delivery_history(user_id="user-1")
        assert len(history) == 1
        assert history[0].alert_id == alert.alert_id

    def test_delete_route_config(self):
        router, _ = self._make_router_with_config()
        assert router.delete_route_config("user-1") is True
        assert router.get_route_config("user-1") is None
        assert router.delete_route_config("user-1") is False


# ---- API Endpoint Tests ----


class TestAPI:
    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_upsert_and_get_config(self, client):
        body = {
            "user_id": "u1",
            "channels": [
                {
                    "channel_type": "in_app",
                    "name": "default",
                }
            ],
            "rules": [
                {"alert_type": "signal", "channel_names": ["default"]}
            ],
            "default_channels": ["default"],
        }
        resp = client.post("/api/v1/alerts/route-config", json=body)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["attributes"]["user_id"] == "u1"

        resp = client.get("/api/v1/alerts/route-config/u1")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["user_id"] == "u1"

    def test_get_config_not_found(self, client):
        resp = client.get("/api/v1/alerts/route-config/nonexistent")
        assert resp.status_code == 404

    def test_delete_config(self, client):
        body = {
            "user_id": "u2",
            "channels": [{"channel_type": "in_app", "name": "ch"}],
        }
        client.post("/api/v1/alerts/route-config", json=body)
        resp = client.delete("/api/v1/alerts/route-config/u2")
        assert resp.status_code == 200

    def test_upsert_config_missing_user_id(self, client):
        resp = client.post("/api/v1/alerts/route-config", json={})
        assert resp.status_code == 422

    def test_upsert_config_invalid_channel_type(self, client):
        body = {
            "user_id": "u1",
            "channels": [{"channel_type": "fax", "name": "ch"}],
        }
        resp = client.post("/api/v1/alerts/route-config", json=body)
        assert resp.status_code == 422

    def test_route_alert(self, client):
        config_body = {
            "user_id": "u1",
            "channels": [{"channel_type": "in_app", "name": "default"}],
            "rules": [{"alert_type": "signal", "channel_names": ["default"]}],
        }
        client.post("/api/v1/alerts/route-config", json=config_body)

        alert_body = {
            "alert_type": "signal",
            "title": "Test Alert",
            "message": "Test message",
            "user_id": "u1",
        }
        resp = client.post("/api/v1/alerts/route", json=alert_body)
        assert resp.status_code == 200
        data = resp.json()["data"]["attributes"]
        assert "alert_id" in data
        assert len(data["deliveries"]) == 1
        assert data["deliveries"][0]["status"] == "delivered"

    def test_route_alert_missing_fields(self, client):
        resp = client.post("/api/v1/alerts/route", json={"title": "T"})
        assert resp.status_code == 422

    def test_history_endpoint(self, client):
        config_body = {
            "user_id": "u1",
            "channels": [{"channel_type": "in_app", "name": "default"}],
            "rules": [{"alert_type": "signal", "channel_names": ["default"]}],
        }
        client.post("/api/v1/alerts/route-config", json=config_body)
        alert_body = {
            "alert_type": "signal",
            "title": "T",
            "message": "m",
            "user_id": "u1",
        }
        client.post("/api/v1/alerts/route", json=alert_body)

        resp = client.get("/api/v1/alerts/history?user_id=u1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] >= 1
        assert len(data["data"]) >= 1

    def test_history_pagination(self, client):
        resp = client.get("/api/v1/alerts/history?limit=5&offset=0")
        assert resp.status_code == 200
        assert resp.json()["meta"]["limit"] == 5
