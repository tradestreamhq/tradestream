"""Tests for Pine Script template generation."""

import pytest

from services.tradingview_integration.models import PineScriptConfig
from services.tradingview_integration.pine_script import (
    generate_strategy_template,
    generate_webhook_indicator,
)


class TestGenerateWebhookIndicator:
    def test_basic_generation(self):
        config = PineScriptConfig(
            strategy_name="Test Strategy",
            webhook_url="https://example.com/webhook/token123",
        )
        script = generate_webhook_indicator(config)

        assert "//@version=5" in script
        assert "Test Strategy" in script
        assert "indicator(" in script
        assert "buySignal" in script
        assert "sellSignal" in script
        assert "alert(" in script
        assert "https://example.com/webhook/token123" in script

    def test_includes_stop_loss(self):
        config = PineScriptConfig(
            strategy_name="SL Test",
            webhook_url="https://example.com/hook",
            include_stop_loss=True,
        )
        script = generate_webhook_indicator(config)
        assert "stoploss" in script

    def test_excludes_stop_loss(self):
        config = PineScriptConfig(
            strategy_name="No SL",
            webhook_url="https://example.com/hook",
            include_stop_loss=False,
        )
        script = generate_webhook_indicator(config)
        assert "stoploss" not in script

    def test_includes_take_profit(self):
        config = PineScriptConfig(
            strategy_name="TP Test",
            webhook_url="https://example.com/hook",
            include_take_profit=True,
        )
        script = generate_webhook_indicator(config)
        assert "takeprofit" in script

    def test_excludes_take_profit(self):
        config = PineScriptConfig(
            strategy_name="No TP",
            webhook_url="https://example.com/hook",
            include_take_profit=False,
        )
        script = generate_webhook_indicator(config)
        assert "takeprofit" not in script

    def test_custom_ticker(self):
        config = PineScriptConfig(
            strategy_name="Custom",
            webhook_url="https://example.com/hook",
            ticker="BTCUSD",
        )
        script = generate_webhook_indicator(config)
        assert "BTCUSD" in script

    def test_default_ticker_uses_syminfo(self):
        config = PineScriptConfig(
            strategy_name="Default",
            webhook_url="https://example.com/hook",
            ticker=None,
        )
        script = generate_webhook_indicator(config)
        assert "syminfo.ticker" in script

    def test_includes_quantity_when_enabled(self):
        config = PineScriptConfig(
            strategy_name="Qty",
            webhook_url="https://example.com/hook",
            include_quantity=True,
        )
        script = generate_webhook_indicator(config)
        assert "quantity" in script

    def test_excludes_quantity_when_disabled(self):
        config = PineScriptConfig(
            strategy_name="No Qty",
            webhook_url="https://example.com/hook",
            include_quantity=False,
        )
        script = generate_webhook_indicator(config)
        assert "quantity" not in script


class TestGenerateStrategyTemplate:
    def test_basic_generation(self):
        config = PineScriptConfig(
            strategy_name="Backtest Strategy",
            webhook_url="https://example.com/webhook/abc",
        )
        script = generate_strategy_template(config)

        assert "//@version=5" in script
        assert "strategy(" in script
        assert "strategy.entry" in script
        assert "strategy.close" in script
        assert "alert_message" in script
        assert "Backtest Strategy" in script

    def test_webhook_url_in_comments(self):
        config = PineScriptConfig(
            strategy_name="Test",
            webhook_url="https://ts.example.com/webhook/xyz",
        )
        script = generate_strategy_template(config)
        assert "https://ts.example.com/webhook/xyz" in script

    def test_custom_ticker_in_strategy(self):
        config = PineScriptConfig(
            strategy_name="Custom Ticker",
            webhook_url="https://example.com/hook",
            ticker="ETHUSD",
        )
        script = generate_strategy_template(config)
        assert "ETHUSD" in script
