"""Tests for the strategy rotation service."""

import asyncio
import http.client
import threading
import time
from datetime import datetime
from unittest import mock

import pytest

from services.strategy_rotation.main import (
    HealthHandler,
    RotationDecision,
    StrategyRotator,
    _run_rotation_cycle,
    _start_health_server,
)


class TestHealthEndpoint:
    def test_healthz_returns_200(self):
        server = _start_health_server(0)
        port = server.server_address[1]
        try:
            conn = http.client.HTTPConnection("localhost", port, timeout=2)
            conn.request("GET", "/healthz")
            resp = conn.getresponse()
            assert resp.status == 200
            body = resp.read().decode()
            assert "ok" in body
            conn.close()
        finally:
            server.shutdown()

    def test_readyz_returns_200(self):
        server = _start_health_server(0)
        port = server.server_address[1]
        try:
            conn = http.client.HTTPConnection("localhost", port, timeout=2)
            conn.request("GET", "/readyz")
            resp = conn.getresponse()
            assert resp.status == 200
            conn.close()
        finally:
            server.shutdown()

    def test_unknown_path_returns_404(self):
        server = _start_health_server(0)
        port = server.server_address[1]
        try:
            conn = http.client.HTTPConnection("localhost", port, timeout=2)
            conn.request("GET", "/unknown")
            resp = conn.getresponse()
            assert resp.status == 404
            conn.close()
        finally:
            server.shutdown()


class TestEvaluateSymbolRotation:
    def setup_method(self):
        self.rotator = StrategyRotator.__new__(StrategyRotator)
        self.rotator.db_config = {}
        self.rotator.pool = None

    def test_returns_none_for_empty_strategies(self):
        result = self.rotator._evaluate_symbol_rotation("BTC/USD", [], [])
        assert result is None

    def test_returns_decision_when_no_active_positions(self):
        strategies = [
            {
                "strategy_id": "s1",
                "strategy_type": "RSI",
                "current_score": 0.85,
            },
            {
                "strategy_id": "s2",
                "strategy_type": "MACD",
                "current_score": 0.80,
            },
        ]
        result = self.rotator._evaluate_symbol_rotation("BTC/USD", strategies, [])
        assert result is not None
        assert result.symbol == "BTC/USD"
        assert result.new_strategy_id == "s1"
        assert result.new_strategy_type == "RSI"
        assert result.old_strategy_id is None
        assert "No active positions" in result.reason


class TestRunRotationCycle:
    def test_handles_db_error_gracefully(self):
        rotator = StrategyRotator.__new__(StrategyRotator)
        rotator.pool = mock.AsyncMock()
        rotator.pool.acquire.return_value.__aenter__ = mock.AsyncMock(
            side_effect=Exception("connection refused")
        )

        count = asyncio.get_event_loop().run_until_complete(
            _run_rotation_cycle(rotator)
        )
        assert count == 0
