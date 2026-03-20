"""Tests for the batch processor and degraded signal generation."""

import asyncio

import pytest

from services.autonomous_runner.batch_processor import (
    DEGRADATION_PENALTIES,
    BatchConfig,
    BatchProcessor,
    BatchResult,
    FailedSymbol,
    PartialDataError,
    PartialSignal,
    generate_degraded_signal,
)


class TestBatchResult:
    def test_empty_result(self):
        r = BatchResult()
        assert r.success_rate == 0.0
        assert r.total_processed == 0

    def test_all_successful(self):
        r = BatchResult(successful=["a", "b", "c"])
        assert r.success_rate == 1.0
        assert r.total_processed == 3

    def test_mixed_results(self):
        r = BatchResult(
            successful=["a"],
            failed=[FailedSymbol("X", "err", "Exception")],
            partial=[PartialSignal(signal={})],
        )
        assert r.success_rate == pytest.approx(2 / 3, abs=0.01)
        assert r.total_processed == 3


class TestPartialDataError:
    def test_penalty_calculation(self):
        err = PartialDataError(
            available_data={"strategies": []},
            missing_tools=["market_context", "volatility"],
        )
        expected = (
            DEGRADATION_PENALTIES["market_context"]
            + DEGRADATION_PENALTIES["volatility"]
        )
        assert err.confidence_penalty == expected
        assert "market_context" in err.missing_tools

    def test_unknown_tool_penalty(self):
        err = PartialDataError(
            available_data={},
            missing_tools=["unknown_source"],
        )
        assert err.confidence_penalty == 0.05  # default penalty


class TestGenerateDegradedSignal:
    def test_hold_when_no_data(self):
        result = generate_degraded_signal(
            "BTC-USD", {}, ["strategies", "market_context"]
        )
        assert result["symbol"] == "BTC-USD"
        assert result["action"] == "HOLD"
        assert result["is_degraded"] is True
        assert result["confidence"] >= 0.30

    def test_buy_when_strategies_say_buy(self):
        result = generate_degraded_signal(
            "ETH-USD",
            {"strategies": [{"signal": "BUY"}, {"signal": "BUY"}, {"signal": "SELL"}]},
            ["market_context"],
        )
        assert result["action"] == "BUY"
        assert result["is_degraded"] is True

    def test_sell_when_strategies_say_sell(self):
        result = generate_degraded_signal(
            "SOL-USD",
            {"strategies": [{"signal": "SELL"}, {"signal": "SELL"}, {"signal": "BUY"}]},
            ["volatility"],
        )
        assert result["action"] == "SELL"

    def test_confidence_penalty_applied(self):
        result = generate_degraded_signal(
            "BTC-USD", {}, ["strategies", "market_context", "volatility"]
        )
        total_penalty = (
            DEGRADATION_PENALTIES["strategies"]
            + DEGRADATION_PENALTIES["market_context"]
            + DEGRADATION_PENALTIES["volatility"]
        )
        assert result["confidence"] == pytest.approx(
            max(0.30, 0.70 - total_penalty), abs=0.01
        )
        assert result["confidence_penalty"] == pytest.approx(total_penalty, abs=0.01)

    def test_confidence_floor_is_0_30(self):
        # All sources missing should still give at least 0.30
        result = generate_degraded_signal(
            "X",
            {},
            [
                "strategies",
                "market_context",
                "volatility",
                "sentiment",
                "prediction_market",
            ],
        )
        assert result["confidence"] >= 0.30

    def test_missing_data_in_output(self):
        result = generate_degraded_signal("X", {}, ["strategies", "sentiment"])
        assert "strategies" in result["missing_data"]
        assert "sentiment" in result["missing_data"]


class TestBatchProcessor:
    def test_process_batch_all_success(self):
        processor = BatchProcessor(BatchConfig(max_concurrent_symbols=5))

        def process_fn(symbol):
            return {"symbol": symbol, "action": "BUY"}

        result = asyncio.run(processor.process_batch(["BTC", "ETH"], process_fn))
        assert len(result.successful) == 2
        assert result.success_rate == 1.0
        processor.shutdown()

    def test_process_batch_with_failures(self):
        processor = BatchProcessor(BatchConfig(max_concurrent_symbols=5))

        def process_fn(symbol):
            if symbol == "FAIL":
                raise ValueError("boom")
            return {"symbol": symbol}

        result = asyncio.run(
            processor.process_batch(["BTC", "FAIL", "ETH"], process_fn)
        )
        assert len(result.successful) == 2
        assert len(result.failed) == 1
        assert result.failed[0].symbol == "FAIL"
        processor.shutdown()

    def test_process_batch_with_partial(self):
        processor = BatchProcessor(BatchConfig(max_concurrent_symbols=5))

        def process_fn(symbol):
            if symbol == "PARTIAL":
                raise PartialDataError(
                    available_data={"symbol": symbol},
                    missing_tools=["volatility"],
                )
            return {"symbol": symbol}

        result = asyncio.run(processor.process_batch(["BTC", "PARTIAL"], process_fn))
        assert len(result.successful) == 1
        assert len(result.partial) == 1
        assert result.partial[0].missing_data == ["volatility"]
        processor.shutdown()

    def test_empty_batch(self):
        processor = BatchProcessor()
        result = asyncio.run(processor.process_batch([], lambda s: s))
        assert result.total_processed == 0
        assert result.success_rate == 0.0
        processor.shutdown()

    def test_batch_latency_recorded(self):
        processor = BatchProcessor(BatchConfig(max_concurrent_symbols=2))

        def process_fn(symbol):
            return {"symbol": symbol}

        result = asyncio.run(processor.process_batch(["A", "B"], process_fn))
        assert result.batch_latency_ms >= 0
        processor.shutdown()
