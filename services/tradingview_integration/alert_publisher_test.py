"""Tests for TradingView alert publisher."""

from unittest.mock import MagicMock, patch

import pytest

from services.tradingview_integration.alert_publisher import (
    TradingViewAlertPublisher,
    _instrument_to_ticker,
)


class TestInstrumentToTicker:
    def test_crypto_pair(self):
        assert _instrument_to_ticker("BTC/USD") == "BTCUSD"

    def test_crypto_usdt(self):
        assert _instrument_to_ticker("ETH/USDT") == "ETHUSDT"

    def test_no_slash(self):
        assert _instrument_to_ticker("AAPL") == "AAPL"

    def test_empty(self):
        assert _instrument_to_ticker("") == ""


class TestFormatPayload:
    def test_buy_signal(self):
        signal = {
            "instrument": "BTC/USD",
            "signal_type": "BUY",
            "price": 65000.0,
            "strategy_name": "momentum_btc",
            "stop_loss": 63000.0,
            "take_profit": 70000.0,
            "position_size": 0.5,
        }
        payload = TradingViewAlertPublisher.format_payload(signal)

        assert payload["ticker"] == "BTCUSD"
        assert payload["action"] == "buy"
        assert payload["price"] == 65000.0
        assert payload["strategy"] == "momentum_btc"
        assert payload["stoploss"] == 63000.0
        assert payload["takeprofit"] == 70000.0
        assert payload["quantity"] == 0.5

    def test_sell_signal(self):
        signal = {
            "instrument": "ETH/USDT",
            "signal_type": "SELL",
            "price": 3200.0,
            "strategy_name": "mean_reversion",
        }
        payload = TradingViewAlertPublisher.format_payload(signal)

        assert payload["ticker"] == "ETHUSDT"
        assert payload["action"] == "sell"
        assert "stoploss" not in payload
        assert "takeprofit" not in payload

    def test_stop_loss_signal(self):
        signal = {
            "instrument": "BTC/USD",
            "signal_type": "STOP_LOSS",
            "price": 60000.0,
            "strategy_name": "test",
        }
        payload = TradingViewAlertPublisher.format_payload(signal)
        assert payload["action"] == "close"

    def test_missing_strategy_defaults(self):
        signal = {
            "instrument": "BTC/USD",
            "signal_type": "BUY",
            "price": 65000.0,
        }
        payload = TradingViewAlertPublisher.format_payload(signal)
        assert payload["strategy"] == "tradestream"


class TestPublishSignal:
    @patch("services.tradingview_integration.alert_publisher.requests.post")
    def test_successful_delivery(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        publisher = TradingViewAlertPublisher("https://example.com/hook")
        result = publisher.publish_signal({
            "instrument": "BTC/USD",
            "signal_type": "BUY",
            "price": 65000.0,
        })

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"]["ticker"] == "BTCUSD"

    @patch("services.tradingview_integration.alert_publisher.requests.post")
    def test_client_error_returns_false(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_post.return_value = mock_resp

        publisher = TradingViewAlertPublisher("https://example.com/hook")
        result = publisher.publish_signal({
            "instrument": "BTC/USD",
            "signal_type": "BUY",
            "price": 65000.0,
        })

        assert result is False
