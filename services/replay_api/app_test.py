"""Comprehensive tests for the Trade Replay and Simulation API."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.replay_api.app import (
    ReplaySession,
    SessionStatus,
    _filter_candles,
    _parse_date,
    create_app,
    get_sessions,
)

SAMPLE_CANDLES = [
    {
        "time": "2026-01-01T00:00:00Z",
        "open": 60000.0,
        "high": 61000.0,
        "low": 59000.0,
        "close": 60500.0,
        "volume": 100.0,
    },
    {
        "time": "2026-01-01T01:00:00Z",
        "open": 60500.0,
        "high": 62000.0,
        "low": 60000.0,
        "close": 61500.0,
        "volume": 150.0,
    },
    {
        "time": "2026-01-01T02:00:00Z",
        "open": 61500.0,
        "high": 63000.0,
        "low": 61000.0,
        "close": 62500.0,
        "volume": 200.0,
    },
    {
        "time": "2026-01-01T03:00:00Z",
        "open": 62500.0,
        "high": 63500.0,
        "low": 62000.0,
        "close": 63000.0,
        "volume": 120.0,
    },
    {
        "time": "2026-01-01T04:00:00Z",
        "open": 63000.0,
        "high": 63200.0,
        "low": 61500.0,
        "close": 62000.0,
        "volume": 180.0,
    },
]


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    get_sessions().clear()
    yield
    get_sessions().clear()


@pytest.fixture
def client():
    influxdb = MagicMock()
    app = create_app(influxdb)
    return TestClient(app, raise_server_exceptions=False), influxdb


class TestHealthEndpoint:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestStartReplay:
    def test_start_replay_success(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES

        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "speed": 5,
                "interval": "1h",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "replay_session"
        attrs = body["data"]["attributes"]
        assert attrs["symbol"] == "BTC/USD"
        assert attrs["speed"] == 5
        assert attrs["total_candles"] == 5
        assert attrs["tick_interval_ms"] == 200
        assert attrs["status"] == "active"
        assert "session_id" in attrs

    def test_start_replay_default_speed(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES

        resp = tc.post(
            "/start",
            json={
                "symbol": "ETH/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
        )
        assert resp.status_code == 201
        attrs = resp.json()["data"]["attributes"]
        assert attrs["speed"] == 1
        assert attrs["tick_interval_ms"] == 1000

    def test_start_replay_invalid_speed(self, client):
        tc, influxdb = client

        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "speed": 3,
            },
        )
        assert resp.status_code == 422
        assert "VALIDATION_ERROR" in resp.json()["error"]["code"]

    def test_start_replay_invalid_interval(self, client):
        tc, influxdb = client

        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "interval": "2h",
            },
        )
        assert resp.status_code == 422

    def test_start_replay_no_data(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = []

        resp = tc.post(
            "/start",
            json={
                "symbol": "UNKNOWN/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NO_DATA"

    def test_start_replay_all_speeds(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES

        for speed, expected_ms in [(1, 1000), (5, 200), (10, 100), (50, 20)]:
            get_sessions().clear()
            resp = tc.post(
                "/start",
                json={
                    "symbol": "BTC/USD",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-02",
                    "speed": speed,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["data"]["attributes"]["tick_interval_ms"] == expected_ms


class TestTick:
    def _start_session(self, tc, influxdb, candles=None):
        influxdb.get_candles.return_value = candles or SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "speed": 1,
            },
        )
        return resp.json()["data"]["attributes"]["session_id"]

    def test_tick_advances(self, client):
        tc, influxdb = client
        sid = self._start_session(tc, influxdb)

        resp = tc.get(f"/{sid}/tick")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["tick"] == 1
        assert attrs["remaining"] == 4
        assert attrs["candle"]["close"] == 60500.0

    def test_tick_sequence(self, client):
        tc, influxdb = client
        sid = self._start_session(tc, influxdb)

        for i in range(5):
            resp = tc.get(f"/{sid}/tick")
            assert resp.status_code == 200
            attrs = resp.json()["data"]["attributes"]
            assert attrs["tick"] == i + 1

    def test_tick_exhaustion_marks_completed(self, client):
        tc, influxdb = client
        sid = self._start_session(tc, influxdb)

        # Exhaust all 5 candles
        for _ in range(5):
            resp = tc.get(f"/{sid}/tick")
            assert resp.status_code == 200

        # 6th tick should return 410
        resp = tc.get(f"/{sid}/tick")
        assert resp.status_code == 410
        assert resp.json()["error"]["code"] == "REPLAY_COMPLETED"

    def test_tick_not_found(self, client):
        tc, _ = client
        resp = tc.get("/nonexistent/tick")
        assert resp.status_code == 404

    def test_tick_returns_candle_data(self, client):
        tc, influxdb = client
        sid = self._start_session(tc, influxdb)

        resp = tc.get(f"/{sid}/tick")
        candle = resp.json()["data"]["attributes"]["candle"]
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle
        assert "time" in candle


class TestTrade:
    def _start_and_tick(self, tc, influxdb, ticks=1, candles=None):
        influxdb.get_candles.return_value = candles or SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "speed": 1,
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]
        for _ in range(ticks):
            tc.get(f"/{sid}/tick")
        return sid

    def test_place_buy_trade(self, client):
        tc, influxdb = client
        sid = self._start_and_tick(tc, influxdb)

        resp = tc.post(
            f"/{sid}/trade",
            json={"side": "buy", "quantity": 1.0},
        )
        assert resp.status_code == 201
        attrs = resp.json()["data"]["attributes"]
        assert attrs["side"] == "buy"
        assert attrs["quantity"] == 1.0
        assert attrs["price"] == 60500.0  # close of first candle

    def test_place_trade_with_limit_price(self, client):
        tc, influxdb = client
        sid = self._start_and_tick(tc, influxdb)

        resp = tc.post(
            f"/{sid}/trade",
            json={"side": "buy", "quantity": 0.5, "price": 60000.0},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["attributes"]["price"] == 60000.0

    def test_place_sell_trade(self, client):
        tc, influxdb = client
        sid = self._start_and_tick(tc, influxdb, ticks=2)

        resp = tc.post(
            f"/{sid}/trade",
            json={"side": "sell", "quantity": 1.0},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["attributes"]["side"] == "sell"

    def test_trade_before_tick(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "speed": 1,
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]

        resp = tc.post(
            f"/{sid}/trade",
            json={"side": "buy", "quantity": 1.0},
        )
        assert resp.status_code == 422

    def test_trade_on_completed_session(self, client):
        tc, influxdb = client
        sid = self._start_and_tick(tc, influxdb, ticks=5)

        resp = tc.post(
            f"/{sid}/trade",
            json={"side": "buy", "quantity": 1.0},
        )
        assert resp.status_code == 410

    def test_trade_not_found(self, client):
        tc, _ = client
        resp = tc.post(
            "/nonexistent/trade",
            json={"side": "buy", "quantity": 1.0},
        )
        assert resp.status_code == 404


class TestSummary:
    def _run_replay_with_trades(self, tc, influxdb):
        influxdb.get_candles.return_value = SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "speed": 10,
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]

        # Tick 1: close=60500
        tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "buy", "quantity": 1.0})

        # Tick 2: close=61500
        tc.get(f"/{sid}/tick")

        # Tick 3: close=62500
        tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "sell", "quantity": 1.0})

        # Exhaust remaining ticks
        tc.get(f"/{sid}/tick")
        tc.get(f"/{sid}/tick")

        return sid

    def test_summary_with_trades(self, client):
        tc, influxdb = client
        sid = self._run_replay_with_trades(tc, influxdb)

        resp = tc.get(f"/{sid}/summary")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_trades"] == 1
        assert attrs["winning_trades"] == 1
        assert attrs["total_pnl"] == 2000.0  # 62500 - 60500
        assert attrs["win_rate"] == 100.0
        assert attrs["status"] == "completed"

    def test_summary_no_trades(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]

        resp = tc.get(f"/{sid}/summary")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_trades"] == 0
        assert attrs["total_pnl"] == 0.0
        assert attrs["win_rate"] == 0.0

    def test_summary_losing_trade(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]

        # Buy at tick 3 (close=62500), sell at tick 5 (close=62000)
        for _ in range(3):
            tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "buy", "quantity": 2.0})

        for _ in range(2):
            tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "sell", "quantity": 2.0})

        resp = tc.get(f"/{sid}/summary")
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_pnl"] == -1000.0  # (62000 - 62500) * 2
        assert attrs["losing_trades"] == 1
        assert attrs["win_rate"] == 0.0

    def test_summary_not_found(self, client):
        tc, _ = client
        resp = tc.get("/nonexistent/summary")
        assert resp.status_code == 404

    def test_summary_active_session(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]
        tc.get(f"/{sid}/tick")

        resp = tc.get(f"/{sid}/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["status"] == "active"

    def test_summary_multiple_round_trips(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = SAMPLE_CANDLES
        resp = tc.post(
            "/start",
            json={
                "symbol": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
        )
        sid = resp.json()["data"]["attributes"]["session_id"]

        # Buy at tick 1 (60500), sell at tick 2 (61500) = +1000
        tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "buy", "quantity": 1.0})
        tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "sell", "quantity": 1.0})

        # Buy at tick 3 (62500), sell at tick 4 (63000) = +500
        tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "buy", "quantity": 1.0})
        tc.get(f"/{sid}/tick")
        tc.post(f"/{sid}/trade", json={"side": "sell", "quantity": 1.0})

        resp = tc.get(f"/{sid}/summary")
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_trades"] == 2
        assert attrs["total_pnl"] == 1500.0
        assert attrs["winning_trades"] == 2
        assert attrs["win_rate"] == 100.0


class TestReplaySessionUnit:
    """Unit tests for the ReplaySession class."""

    def test_advance_returns_candles_in_order(self):
        session = ReplaySession(
            session_id="test",
            symbol="BTC/USD",
            start_date="2026-01-01",
            end_date="2026-01-02",
            speed=1,
            interval="1h",
            candles=SAMPLE_CANDLES,
        )
        for i, expected in enumerate(SAMPLE_CANDLES):
            candle = session.advance()
            assert candle == expected

    def test_advance_marks_completed(self):
        session = ReplaySession(
            session_id="test",
            symbol="BTC/USD",
            start_date="2026-01-01",
            end_date="2026-01-02",
            speed=1,
            interval="1h",
            candles=SAMPLE_CANDLES[:1],
        )
        session.advance()
        assert session.status == SessionStatus.COMPLETED

    def test_advance_returns_none_when_exhausted(self):
        session = ReplaySession(
            session_id="test",
            symbol="BTC/USD",
            start_date="2026-01-01",
            end_date="2026-01-02",
            speed=1,
            interval="1h",
            candles=[],
        )
        assert session.advance() is None

    def test_compute_summary_no_trades(self):
        session = ReplaySession(
            session_id="test",
            symbol="BTC/USD",
            start_date="2026-01-01",
            end_date="2026-01-02",
            speed=1,
            interval="1h",
            candles=SAMPLE_CANDLES,
        )
        summary = session.compute_summary()
        assert summary["total_trades"] == 0
        assert summary["total_pnl"] == 0.0

    def test_compute_summary_with_open_position(self):
        session = ReplaySession(
            session_id="test",
            symbol="BTC/USD",
            start_date="2026-01-01",
            end_date="2026-01-02",
            speed=1,
            interval="1h",
            candles=SAMPLE_CANDLES,
        )
        session.trades.append(
            {"side": "buy", "quantity": 1.0, "price": 60000.0, "tick": 1}
        )
        summary = session.compute_summary()
        assert summary["open_positions"] == 1
        assert summary["total_trades"] == 0


class TestFilterCandles:
    def test_filter_within_range(self):
        result = _filter_candles(SAMPLE_CANDLES, "2026-01-01", "2026-01-01")
        assert len(result) == 5  # All candles on 2026-01-01

    def test_filter_empty_list(self):
        result = _filter_candles([], "2026-01-01", "2026-01-02")
        assert result == []

    def test_filter_no_match(self):
        result = _filter_candles(SAMPLE_CANDLES, "2025-01-01", "2025-01-02")
        assert len(result) == 0


class TestParseDate:
    def test_parse_rfc3339(self):
        dt = _parse_date("2026-01-01T00:00:00Z")
        assert dt.year == 2026

    def test_parse_date_only(self):
        dt = _parse_date("2026-01-01")
        assert dt.month == 1

    def test_parse_invalid(self):
        with pytest.raises(ValueError):
            _parse_date("not-a-date")
