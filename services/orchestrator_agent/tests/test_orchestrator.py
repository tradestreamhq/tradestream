"""Tests for the main orchestrator module."""

import json
from unittest import mock

import pytest

from services.orchestrator_agent import config
from services.orchestrator_agent.health_monitor import HealthMonitor
from services.orchestrator_agent.orchestrator import (
    TOOL_TO_SERVER,
    fetch_active_symbols,
    run_signal_pipeline,
    run_strategy_proposer,
    run_orchestrator_loop,
)
from services.orchestrator_agent.scheduler import Scheduler
from services.shared.mcp_client import resolve_and_call


def _make_mcp_response(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class TestCallMcpTool:
    def test_unknown_tool(self):
        result = resolve_and_call(
            "unknown", {}, TOOL_TO_SERVER, {}, return_type="parsed"
        )
        assert "error" in result

    def test_missing_server_url(self):
        result = resolve_and_call(
            "get_symbols", {}, TOOL_TO_SERVER, {}, return_type="parsed"
        )
        assert "error" in result

    @mock.patch("requests.post")
    def test_successful_call(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = _make_mcp_response({"symbols": ["BTC-USD"]})
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = resolve_and_call(
            "get_symbols",
            {},
            TOOL_TO_SERVER,
            {"market": "http://market:8080"},
            return_type="parsed",
        )
        assert result == {"symbols": ["BTC-USD"]}


class TestFetchActiveSymbols:
    @mock.patch("requests.post")
    def test_returns_symbols_list(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = _make_mcp_response(
            {"symbols": ["BTC-USD", "ETH-USD"]}
        )
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        symbols = fetch_active_symbols({"market": "http://market:8080"})
        assert symbols == ["BTC-USD", "ETH-USD"]

    @mock.patch("requests.post")
    def test_raises_on_error(self, mock_post):
        mock_post.side_effect = ConnectionError("refused")
        with pytest.raises(ConnectionError):
            fetch_active_symbols({"market": "http://market:8080"})


class TestRunSignalPipeline:
    @mock.patch("services.orchestrator_agent.orchestrator._invoke_agent_http")
    @mock.patch("time.sleep")
    def test_runs_signal_then_scorer(self, mock_sleep, mock_invoke):
        signal_result = {
            "symbol": "BTC-USD",
            "action": "BUY",
            "confidence": 0.8,
        }
        score_result = {"score": 85, "tier": "HOT"}
        mock_invoke.side_effect = [signal_result, score_result]

        hm = HealthMonitor()
        agent_urls = {
            "signal_generator": "http://sg:9001",
            "opportunity_scorer": "http://os:9002",
        }
        mcp_urls = {"signal": "http://signal:8080"}

        run_signal_pipeline("BTC-USD", agent_urls, mcp_urls, hm)

        assert mock_invoke.call_count == 2
        assert hm.get_agent_health(config.AGENT_SIGNAL_GENERATOR).total_successes == 1
        assert hm.get_agent_health(config.AGENT_OPPORTUNITY_SCORER).total_successes == 1

    @mock.patch("services.orchestrator_agent.orchestrator._invoke_agent_http")
    @mock.patch("time.sleep")
    def test_skips_scorer_when_signal_skipped(self, mock_sleep, mock_invoke):
        mock_invoke.return_value = {"skipped": True, "reason": "duplicate"}

        hm = HealthMonitor()
        agent_urls = {
            "signal_generator": "http://sg:9001",
            "opportunity_scorer": "http://os:9002",
        }

        run_signal_pipeline("BTC-USD", agent_urls, {}, hm)

        mock_invoke.assert_called_once()

    @mock.patch("services.orchestrator_agent.orchestrator._invoke_agent_http")
    @mock.patch("services.orchestrator_agent.orchestrator._log_health_decision")
    @mock.patch("time.sleep")
    def test_records_failure_on_signal_error(self, mock_sleep, mock_log, mock_invoke):
        mock_invoke.side_effect = ConnectionError("refused")

        hm = HealthMonitor()
        agent_urls = {"signal_generator": "http://sg:9001"}

        run_signal_pipeline("BTC-USD", agent_urls, {}, hm)

        assert hm.get_agent_health(config.AGENT_SIGNAL_GENERATOR).total_failures == 1

    def test_skips_when_circuit_open(self):
        hm = HealthMonitor()
        # Open the circuit
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            hm.record_failure(config.AGENT_SIGNAL_GENERATOR)

        agent_urls = {"signal_generator": "http://sg:9001"}
        # Should not raise or call anything
        run_signal_pipeline("BTC-USD", agent_urls, {}, hm)


class TestRunStrategyProposer:
    @mock.patch("services.orchestrator_agent.orchestrator._invoke_agent_http")
    @mock.patch("time.sleep")
    def test_runs_successfully(self, mock_sleep, mock_invoke):
        mock_invoke.return_value = {"name": "new_strategy"}

        hm = HealthMonitor()
        agent_urls = {"strategy_proposer": "http://sp:9003"}

        run_strategy_proposer(agent_urls, {}, hm)

        assert hm.get_agent_health(config.AGENT_STRATEGY_PROPOSER).total_successes == 1

    def test_skips_when_circuit_open(self):
        hm = HealthMonitor()
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            hm.record_failure(config.AGENT_STRATEGY_PROPOSER)

        run_strategy_proposer({}, {}, hm)


class TestRunOrchestratorLoop:
    @mock.patch("services.orchestrator_agent.orchestrator.run_strategy_proposer")
    @mock.patch("services.orchestrator_agent.orchestrator.run_signal_pipeline")
    @mock.patch("services.orchestrator_agent.orchestrator.fetch_active_symbols")
    @mock.patch("time.sleep")
    def test_runs_one_cycle_then_stops(
        self, mock_sleep, mock_fetch, mock_pipeline, mock_proposer
    ):
        mock_fetch.return_value = ["BTC-USD"]

        call_count = [0]

        def shutdown_check():
            call_count[0] += 1
            # Let it run through one cycle then stop
            return call_count[0] > 3

        scheduler = Scheduler(signal_interval=60, strategy_proposer_interval=1800)
        hm = HealthMonitor()

        run_orchestrator_loop(
            mcp_urls={"market": "http://m:8080"},
            agent_urls={
                "signal_generator": "http://sg:9001",
                "opportunity_scorer": "http://os:9002",
                "strategy_proposer": "http://sp:9003",
            },
            scheduler=scheduler,
            health_monitor=hm,
            shutdown_check=shutdown_check,
        )

        mock_fetch.assert_called_once()
        mock_pipeline.assert_called_once_with(
            "BTC-USD",
            {
                "signal_generator": "http://sg:9001",
                "opportunity_scorer": "http://os:9002",
                "strategy_proposer": "http://sp:9003",
            },
            {"market": "http://m:8080"},
            hm,
        )
        mock_proposer.assert_called_once()

    @mock.patch("services.orchestrator_agent.orchestrator.run_strategy_proposer")
    @mock.patch("services.orchestrator_agent.orchestrator.run_signal_pipeline")
    @mock.patch("services.orchestrator_agent.orchestrator.fetch_active_symbols")
    @mock.patch("time.sleep")
    def test_uses_fallback_symbols_on_fetch_error(
        self, mock_sleep, mock_fetch, mock_pipeline, mock_proposer
    ):
        mock_fetch.side_effect = ConnectionError("down")

        call_count = [0]

        def shutdown_check():
            call_count[0] += 1
            return call_count[0] > 3

        scheduler = Scheduler(signal_interval=60, strategy_proposer_interval=1800)
        hm = HealthMonitor()

        run_orchestrator_loop(
            mcp_urls={},
            agent_urls={
                "signal_generator": "http://sg:9001",
                "opportunity_scorer": "http://os:9002",
                "strategy_proposer": "http://sp:9003",
            },
            scheduler=scheduler,
            health_monitor=hm,
            shutdown_check=shutdown_check,
            fallback_symbols=["ETH-USD"],
        )

        mock_pipeline.assert_called_once()
        args = mock_pipeline.call_args
        assert args[0][0] == "ETH-USD"
