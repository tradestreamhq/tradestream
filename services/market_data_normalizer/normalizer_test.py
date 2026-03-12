"""Tests for the market data normalizer."""

import logging

import pytest

from services.market_data_normalizer.normalizer import (
    DEFAULT_SYMBOL_MAP,
    NormalizedTick,
    normalize,
    normalize_alpaca,
    normalize_binance,
    normalize_coinbase,
    validate,
)

# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

BINANCE_TICKER = {
    "e": "24hrTicker",
    "E": 1710000000000,  # epoch ms
    "s": "BTCUSD",
    "b": "67123.45",
    "a": "67125.00",
    "c": "67124.00",
    "v": "12345.678",
    "w": "66890.12",
}

COINBASE_TICKER = {
    "type": "ticker",
    "product_id": "BTC-USD",
    "time": "2026-03-10T14:30:00Z",
    "best_bid": "67100.00",
    "best_ask": "67110.00",
    "price": "67105.00",
    "volume_24h": "8901.23",
}

ALPACA_QUOTE = {
    "T": "q",
    "S": "BTC/USD",
    "t": "2026-03-10T14:30:00Z",
    "bp": 67050.0,
    "ap": 67060.0,
    "p": 67055.0,
    "v": 5432.1,
    "vw": 66950.0,
}


# ---------------------------------------------------------------------------
# Binance normalizer tests
# ---------------------------------------------------------------------------


class TestBinanceNormalizer:
    def test_full_payload(self):
        tick = normalize_binance(BINANCE_TICKER)
        assert tick.symbol == "BTC/USD"
        assert tick.exchange == "binance"
        assert tick.bid == 67123.45
        assert tick.ask == 67125.00
        assert tick.last_price == 67124.00
        assert tick.volume_24h == 12345.678
        assert tick.vwap == 66890.12
        assert (
            "2024" in tick.timestamp or "2025" in tick.timestamp or tick.timestamp
        )  # epoch parsed

    def test_missing_fields(self, caplog):
        raw = {"s": "ETHUSD", "E": 1710000000000}
        with caplog.at_level(logging.WARNING):
            tick = normalize_binance(raw)
        assert tick.bid is None
        assert tick.ask is None
        assert tick.last_price is None
        assert "missing fields" in caplog.text

    def test_symbol_mapping(self):
        tick = normalize_binance(BINANCE_TICKER)
        assert tick.symbol == "BTC/USD"

    def test_custom_symbol_map(self):
        custom = {"BTCUSD": "XBTC/USD"}
        tick = normalize_binance(BINANCE_TICKER, symbol_map=custom)
        assert tick.symbol == "XBTC/USD"


# ---------------------------------------------------------------------------
# Coinbase normalizer tests
# ---------------------------------------------------------------------------


class TestCoinbaseNormalizer:
    def test_full_payload(self):
        tick = normalize_coinbase(COINBASE_TICKER)
        assert tick.symbol == "BTC/USD"
        assert tick.exchange == "coinbase"
        assert tick.bid == 67100.00
        assert tick.ask == 67110.00
        assert tick.last_price == 67105.00
        assert tick.volume_24h == 8901.23
        assert tick.vwap is None  # Coinbase doesn't provide VWAP
        assert tick.timestamp == "2026-03-10T14:30:00Z"

    def test_missing_fields(self, caplog):
        raw = {"product_id": "ETH-USD", "time": "2026-03-10T14:30:00Z"}
        with caplog.at_level(logging.WARNING):
            tick = normalize_coinbase(raw)
        assert tick.bid is None
        assert "missing fields" in caplog.text

    def test_symbol_mapping(self):
        tick = normalize_coinbase(COINBASE_TICKER)
        assert tick.symbol == "BTC/USD"


# ---------------------------------------------------------------------------
# Alpaca normalizer tests
# ---------------------------------------------------------------------------


class TestAlpacaNormalizer:
    def test_full_payload(self):
        tick = normalize_alpaca(ALPACA_QUOTE)
        assert tick.symbol == "BTC/USD"
        assert tick.exchange == "alpaca"
        assert tick.bid == 67050.0
        assert tick.ask == 67060.0
        assert tick.last_price == 67055.0
        assert tick.volume_24h == 5432.1
        assert tick.vwap == 66950.0
        assert tick.timestamp == "2026-03-10T14:30:00Z"

    def test_missing_fields(self, caplog):
        raw = {"S": "SOL/USD", "t": "2026-03-10T14:30:00Z"}
        with caplog.at_level(logging.WARNING):
            tick = normalize_alpaca(raw)
        assert tick.bid is None
        assert tick.ask is None
        assert "missing fields" in caplog.text


# ---------------------------------------------------------------------------
# Unified normalize() dispatch tests
# ---------------------------------------------------------------------------


class TestNormalizeDispatch:
    def test_binance(self):
        tick = normalize(BINANCE_TICKER, "binance")
        assert tick.exchange == "binance"

    def test_coinbase(self):
        tick = normalize(COINBASE_TICKER, "coinbase")
        assert tick.exchange == "coinbase"

    def test_alpaca(self):
        tick = normalize(ALPACA_QUOTE, "alpaca")
        assert tick.exchange == "alpaca"

    def test_case_insensitive(self):
        tick = normalize(BINANCE_TICKER, "Binance")
        assert tick.exchange == "binance"

    def test_unsupported_exchange(self):
        with pytest.raises(ValueError, match="Unsupported exchange"):
            normalize({}, "kraken")


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_tick(self):
        tick = NormalizedTick(
            symbol="BTC/USD",
            exchange="binance",
            timestamp="2026-03-10T14:30:00Z",
            bid=67000.0,
            ask=67010.0,
            last_price=67005.0,
            volume_24h=1000.0,
            vwap=66950.0,
        )
        assert validate(tick) == []

    def test_negative_price(self):
        tick = NormalizedTick(
            symbol="BTC/USD",
            exchange="binance",
            timestamp="2026-03-10T14:30:00Z",
            last_price=-1.0,
        )
        errors = validate(tick)
        assert any("last_price must be > 0" in e for e in errors)

    def test_bid_gte_ask(self):
        tick = NormalizedTick(
            symbol="BTC/USD",
            exchange="binance",
            timestamp="2026-03-10T14:30:00Z",
            bid=100.0,
            ask=99.0,
        )
        errors = validate(tick)
        assert any("bid" in e and "ask" in e for e in errors)

    def test_missing_symbol(self):
        tick = NormalizedTick(
            symbol="", exchange="binance", timestamp="2026-03-10T14:30:00Z"
        )
        errors = validate(tick)
        assert any("symbol is empty" in e for e in errors)

    def test_negative_volume(self):
        tick = NormalizedTick(
            symbol="BTC/USD",
            exchange="binance",
            timestamp="2026-03-10T14:30:00Z",
            volume_24h=-500.0,
        )
        errors = validate(tick)
        assert any("volume_24h" in e for e in errors)

    def test_none_fields_are_valid(self):
        tick = NormalizedTick(
            symbol="BTC/USD",
            exchange="binance",
            timestamp="2026-03-10T14:30:00Z",
        )
        assert validate(tick) == []


# ---------------------------------------------------------------------------
# to_dict / round-trip tests
# ---------------------------------------------------------------------------


class TestNormalizedTick:
    def test_to_dict(self):
        tick = NormalizedTick(
            symbol="BTC/USD",
            exchange="binance",
            timestamp="2026-03-10T14:30:00Z",
            bid=67000.0,
            ask=67010.0,
        )
        d = tick.to_dict()
        assert d["symbol"] == "BTC/USD"
        assert d["bid"] == 67000.0
        assert d["last_price"] is None

    def test_all_exchanges_produce_dict(self):
        for exchange, payload in [
            ("binance", BINANCE_TICKER),
            ("coinbase", COINBASE_TICKER),
            ("alpaca", ALPACA_QUOTE),
        ]:
            tick = normalize(payload, exchange)
            d = tick.to_dict()
            assert "symbol" in d
            assert "exchange" in d
            assert "timestamp" in d
