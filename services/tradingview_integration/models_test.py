"""Tests for TradingView integration models and signal mapping."""

import pytest

from services.tradingview_integration.models import (
    ACTION_TO_SIGNAL_TYPE,
    TradingViewAction,
    TradingViewWebhookPayload,
    normalize_ticker,
    tradingview_payload_to_signal,
)


class TestNormalizeTicker:
    def test_simple_crypto(self):
        assert normalize_ticker("BTCUSD") == "BTC/USD"

    def test_crypto_usdt(self):
        assert normalize_ticker("BTCUSDT") == "BTC/USDT"

    def test_with_exchange_prefix(self):
        assert normalize_ticker("BINANCE:BTCUSDT") == "BTC/USDT"

    def test_eth_btc_pair(self):
        assert normalize_ticker("ETHBTC") == "ETH/BTC"

    def test_lowercase_input(self):
        assert normalize_ticker("btcusd") == "BTC/USD"

    def test_stock_ticker(self):
        # Single stock symbol with no known quote currency
        assert normalize_ticker("AAPL") == "AAPL"

    def test_euro_pair(self):
        assert normalize_ticker("BTCEUR") == "BTC/EUR"

    def test_gbp_pair(self):
        assert normalize_ticker("ETHGBP") == "ETH/GBP"


class TestTradingViewWebhookPayload:
    def test_minimal_payload(self):
        payload = TradingViewWebhookPayload(ticker="BTCUSD", action="buy")
        assert payload.ticker == "BTCUSD"
        assert payload.action == "buy"
        assert payload.price is None

    def test_full_payload(self):
        payload = TradingViewWebhookPayload(
            ticker="BINANCE:ETHUSDT",
            action="sell",
            price=3200.50,
            stoploss=3400.0,
            takeprofit=2800.0,
            quantity=1.5,
            strategy="momentum_eth",
            message="Crossover detected",
            time="2026-03-19T10:00:00Z",
            interval="4H",
            exchange="BINANCE",
        )
        assert payload.ticker == "BINANCE:ETHUSDT"
        assert payload.action == "sell"
        assert payload.price == 3200.50
        assert payload.stop_loss == 3400.0
        assert payload.take_profit == 2800.0
        assert payload.quantity == 1.5
        assert payload.strategy == "momentum_eth"

    def test_alias_fields(self):
        payload = TradingViewWebhookPayload(
            ticker="BTCUSD",
            action="buy",
            stoploss=60000.0,
            takeprofit=70000.0,
        )
        assert payload.stop_loss == 60000.0
        assert payload.take_profit == 70000.0


class TestTradingViewAction:
    def test_all_actions_mapped(self):
        for action in TradingViewAction:
            assert action in ACTION_TO_SIGNAL_TYPE

    def test_buy_actions(self):
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.BUY] == "BUY"
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.LONG] == "BUY"
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.EXIT_SHORT] == "BUY"

    def test_sell_actions(self):
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.SELL] == "SELL"
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.SHORT] == "SELL"
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.CLOSE] == "SELL"
        assert ACTION_TO_SIGNAL_TYPE[TradingViewAction.EXIT_LONG] == "SELL"


class TestTradingViewPayloadToSignal:
    def test_basic_buy(self):
        payload = TradingViewWebhookPayload(
            ticker="BTCUSD", action="buy", price=65000.0
        )
        signal = tradingview_payload_to_signal(payload)

        assert signal["instrument"] == "BTC/USD"
        assert signal["signal_type"] == "BUY"
        assert signal["price"] == 65000.0
        assert signal["strategy_name"] == "tradingview_alert"
        assert signal["source"] == "tradingview"
        assert signal["strength"] == 1.0

    def test_sell_with_strategy(self):
        payload = TradingViewWebhookPayload(
            ticker="ETHUSDT",
            action="sell",
            price=3200.0,
            strategy="mean_reversion",
        )
        signal = tradingview_payload_to_signal(payload)

        assert signal["instrument"] == "ETH/USDT"
        assert signal["signal_type"] == "SELL"
        assert signal["strategy_name"] == "mean_reversion"

    def test_connection_overrides(self):
        payload = TradingViewWebhookPayload(ticker="BTCUSD", action="buy")
        connection = {
            "strategy_name": "my_btc_strategy",
            "instrument": "BTC/USD",
        }
        signal = tradingview_payload_to_signal(payload, connection)

        assert signal["strategy_name"] == "my_btc_strategy"
        assert signal["instrument"] == "BTC/USD"

    def test_custom_alert_mapping(self):
        payload = TradingViewWebhookPayload(ticker="BTCUSD", action="enter")
        connection = {
            "alert_mapping": {"enter": "BUY", "exit": "SELL"},
        }
        signal = tradingview_payload_to_signal(payload, connection)

        assert signal["signal_type"] == "BUY"

    def test_unknown_action_passthrough(self):
        payload = TradingViewWebhookPayload(ticker="BTCUSD", action="scale_in")
        signal = tradingview_payload_to_signal(payload)

        assert signal["signal_type"] == "SCALE_IN"

    def test_metadata_populated(self):
        payload = TradingViewWebhookPayload(
            ticker="BTCUSD",
            action="buy",
            message="Golden cross",
            interval="1D",
            exchange="BINANCE",
            time="2026-03-19T10:00:00Z",
        )
        signal = tradingview_payload_to_signal(payload)

        meta = signal["metadata"]
        assert meta["tradingview_ticker"] == "BTCUSD"
        assert meta["tradingview_action"] == "buy"
        assert meta["tradingview_message"] == "Golden cross"
        assert meta["tradingview_interval"] == "1D"
        assert meta["tradingview_exchange"] == "BINANCE"

    def test_stop_loss_take_profit(self):
        payload = TradingViewWebhookPayload(
            ticker="BTCUSD",
            action="buy",
            price=65000.0,
            stoploss=63000.0,
            takeprofit=70000.0,
            quantity=0.5,
        )
        signal = tradingview_payload_to_signal(payload)

        assert signal["stop_loss"] == 63000.0
        assert signal["take_profit"] == 70000.0
        assert signal["position_size"] == 0.5

    def test_long_maps_to_buy(self):
        payload = TradingViewWebhookPayload(ticker="BTCUSD", action="long")
        signal = tradingview_payload_to_signal(payload)
        assert signal["signal_type"] == "BUY"

    def test_exit_long_maps_to_sell(self):
        payload = TradingViewWebhookPayload(ticker="BTCUSD", action="exit_long")
        signal = tradingview_payload_to_signal(payload)
        assert signal["signal_type"] == "SELL"
