"""
Comprehensive unit tests for Signal Aggregation and Consensus Engine API.
Following AAA (Arrange, Act, Assert) pattern with high coverage.
"""

import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.signal_aggregation_api.main import (
    SIGNAL_DIRECTION,
    app,
    clamp_pagination,
    compute_consensus,
    compute_decay_factor,
    compute_signal_score,
    compute_strategy_performance_score,
)

IMPORT_SUCCESS = True


def _make_signal(
    signal_type="BUY",
    strength=0.8,
    spec_id=None,
    created_at=None,
    outcome=None,
    **kwargs,
):
    """Helper to create a test signal dict."""
    sig = {
        "id": uuid4(),
        "spec_id": spec_id or uuid4(),
        "implementation_id": uuid4(),
        "instrument": "BTC-USD",
        "signal_type": signal_type,
        "strength": strength,
        "price": Decimal("50000.00"),
        "stop_loss": Decimal("48000.00"),
        "take_profit": Decimal("55000.00"),
        "outcome": outcome,
        "pnl": None,
        "pnl_percent": None,
        "timeframe": "1h",
        "metadata": None,
        "created_at": created_at or datetime.now(timezone.utc),
    }
    sig.update(kwargs)
    return sig


class TestImports(unittest.TestCase):
    """Test that all required imports are available."""

    def test_imports_success(self):
        self.assertTrue(IMPORT_SUCCESS)

    def test_flask_app_initialized(self):
        self.assertIsNotNone(app)
        self.assertIn("main", app.name)


class TestDecayFactor(unittest.TestCase):
    """Test exponential decay computation."""

    def test_zero_age_returns_one(self):
        # A fresh signal should have no decay
        result = compute_decay_factor(0, half_life_hours=24)
        self.assertAlmostEqual(result, 1.0)

    def test_one_half_life_returns_half(self):
        # After one half-life, factor should be 0.5
        result = compute_decay_factor(24, half_life_hours=24)
        self.assertAlmostEqual(result, 0.5)

    def test_two_half_lives_returns_quarter(self):
        result = compute_decay_factor(48, half_life_hours=24)
        self.assertAlmostEqual(result, 0.25)

    def test_very_old_signal_approaches_zero(self):
        result = compute_decay_factor(240, half_life_hours=24)
        self.assertLess(result, 0.001)

    def test_zero_half_life_returns_one(self):
        # Edge case: zero half-life means no decay
        result = compute_decay_factor(100, half_life_hours=0)
        self.assertAlmostEqual(result, 1.0)

    def test_negative_half_life_returns_one(self):
        result = compute_decay_factor(100, half_life_hours=-5)
        self.assertAlmostEqual(result, 1.0)

    def test_short_half_life_decays_faster(self):
        short = compute_decay_factor(12, half_life_hours=6)
        long = compute_decay_factor(12, half_life_hours=48)
        self.assertLess(short, long)


class TestStrategyPerformanceScore(unittest.TestCase):
    """Test strategy performance computation."""

    def test_no_signals_returns_neutral(self):
        result = compute_strategy_performance_score({"total_signals": 0})
        self.assertAlmostEqual(result, 0.5)

    def test_all_profitable(self):
        result = compute_strategy_performance_score(
            {"total_signals": 10, "profitable_signals": 10}
        )
        self.assertAlmostEqual(result, 1.0)

    def test_none_profitable(self):
        result = compute_strategy_performance_score(
            {"total_signals": 10, "profitable_signals": 0}
        )
        self.assertAlmostEqual(result, 0.0)

    def test_half_profitable(self):
        result = compute_strategy_performance_score(
            {"total_signals": 20, "profitable_signals": 10}
        )
        self.assertAlmostEqual(result, 0.5)

    def test_missing_keys_returns_neutral(self):
        result = compute_strategy_performance_score({})
        self.assertAlmostEqual(result, 0.5)


class TestSignalScore(unittest.TestCase):
    """Test individual signal scoring."""

    def test_buy_signal_positive(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("BUY", strength=0.9, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.8)
        self.assertGreater(score, 0)

    def test_sell_signal_negative(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("SELL", strength=0.9, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.8)
        self.assertLess(score, 0)

    def test_hold_signal_zero(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("HOLD", strength=0.9, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.8)
        self.assertAlmostEqual(score, 0.0)

    def test_older_signal_lower_magnitude(self):
        now = datetime.now(timezone.utc)
        fresh = _make_signal("BUY", strength=0.9, created_at=now)
        old = _make_signal(
            "BUY", strength=0.9, created_at=now - timedelta(hours=48)
        )
        fresh_score = compute_signal_score(fresh, now, strategy_performance=0.8)
        old_score = compute_signal_score(old, now, strategy_performance=0.8)
        self.assertGreater(abs(fresh_score), abs(old_score))

    def test_higher_confidence_higher_magnitude(self):
        now = datetime.now(timezone.utc)
        high = _make_signal("BUY", strength=0.95, created_at=now)
        low = _make_signal("BUY", strength=0.1, created_at=now)
        high_score = compute_signal_score(high, now, strategy_performance=0.5)
        low_score = compute_signal_score(low, now, strategy_performance=0.5)
        self.assertGreater(high_score, low_score)

    def test_better_performance_higher_magnitude(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("BUY", strength=0.5, created_at=now)
        good = compute_signal_score(signal, now, strategy_performance=0.9)
        bad = compute_signal_score(signal, now, strategy_performance=0.1)
        self.assertGreater(good, bad)

    def test_custom_weights(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("BUY", strength=0.9, created_at=now)
        # All weight on confidence
        score_conf = compute_signal_score(
            signal, now, strategy_performance=0.1,
            user_weights={"recency": 0.0, "performance": 0.0, "confidence": 1.0},
        )
        # All weight on performance
        score_perf = compute_signal_score(
            signal, now, strategy_performance=0.1,
            user_weights={"recency": 0.0, "performance": 1.0, "confidence": 0.0},
        )
        # High confidence (0.9) vs low performance (0.1) should differ
        self.assertGreater(score_conf, score_perf)

    def test_none_strength_defaults_to_half(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("BUY", strength=None, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.5)
        self.assertGreater(score, 0)

    def test_close_long_partial_negative(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("CLOSE_LONG", strength=0.8, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.5)
        self.assertLess(score, 0)

    def test_close_short_partial_positive(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("CLOSE_SHORT", strength=0.8, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.5)
        self.assertGreater(score, 0)

    def test_naive_datetime_handled(self):
        """Signal with naive datetime (no tzinfo) should still work."""
        now = datetime.now(timezone.utc)
        naive_time = datetime(2024, 1, 1, 12, 0, 0)
        signal = _make_signal("BUY", strength=0.5, created_at=naive_time)
        # Should not raise
        score = compute_signal_score(signal, now, strategy_performance=0.5)
        self.assertIsInstance(score, float)


class TestConsensus(unittest.TestCase):
    """Test consensus computation across multiple signals."""

    def test_empty_signals_neutral(self):
        now = datetime.now(timezone.utc)
        result = compute_consensus([], now, {})
        self.assertEqual(result["direction"], "neutral")
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["signal_count"], 0)

    def test_all_buy_signals_bullish(self):
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("BUY", strength=0.9, created_at=now),
            _make_signal("BUY", strength=0.8, created_at=now - timedelta(hours=1)),
            _make_signal("BUY", strength=0.7, created_at=now - timedelta(hours=2)),
        ]
        result = compute_consensus(signals, now, {})
        self.assertEqual(result["direction"], "bullish")
        self.assertGreater(result["score"], 0)
        self.assertEqual(result["signal_count"], 3)

    def test_all_sell_signals_bearish(self):
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("SELL", strength=0.9, created_at=now),
            _make_signal("SELL", strength=0.8, created_at=now - timedelta(hours=1)),
        ]
        result = compute_consensus(signals, now, {})
        self.assertEqual(result["direction"], "bearish")
        self.assertLess(result["score"], 0)

    def test_mixed_signals_with_buy_majority_bullish(self):
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("BUY", strength=0.9, created_at=now),
            _make_signal("BUY", strength=0.8, created_at=now),
            _make_signal("SELL", strength=0.3, created_at=now - timedelta(hours=24)),
        ]
        result = compute_consensus(signals, now, {})
        self.assertEqual(result["direction"], "bullish")

    def test_balanced_signals_neutral(self):
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("BUY", strength=0.5, created_at=now),
            _make_signal("SELL", strength=0.5, created_at=now),
        ]
        result = compute_consensus(signals, now, {})
        self.assertEqual(result["direction"], "neutral")
        self.assertAlmostEqual(result["score"], 0.0, places=2)

    def test_consensus_score_bounded(self):
        now = datetime.now(timezone.utc)
        signals = [_make_signal("BUY", strength=1.0, created_at=now)]
        result = compute_consensus(signals, now, {})
        self.assertLessEqual(result["score"], 1.0)
        self.assertGreaterEqual(result["score"], -1.0)

    def test_strategy_performance_affects_consensus(self):
        now = datetime.now(timezone.utc)
        spec = uuid4()
        signals = [_make_signal("BUY", strength=0.5, spec_id=spec, created_at=now)]
        good = compute_consensus(signals, now, {str(spec): 0.9})
        bad = compute_consensus(signals, now, {str(spec): 0.1})
        self.assertGreater(good["score"], bad["score"])

    def test_consensus_confidence_is_average(self):
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("BUY", strength=0.8, created_at=now),
            _make_signal("BUY", strength=0.4, created_at=now),
        ]
        result = compute_consensus(signals, now, {})
        self.assertAlmostEqual(result["confidence"], 0.6, places=2)

    def test_old_signals_have_less_weight(self):
        now = datetime.now(timezone.utc)
        # One fresh buy, one very old sell
        signals = [
            _make_signal("BUY", strength=0.7, created_at=now),
            _make_signal("SELL", strength=0.7, created_at=now - timedelta(hours=96)),
        ]
        result = compute_consensus(signals, now, {}, half_life_hours=24)
        # Fresh buy should dominate
        self.assertEqual(result["direction"], "bullish")


class TestClampPagination(unittest.TestCase):
    """Test pagination clamping."""

    def test_normal_values(self):
        limit, offset = clamp_pagination(50, 10)
        self.assertEqual(limit, 50)
        self.assertEqual(offset, 10)

    def test_limit_clamped_to_max(self):
        limit, offset = clamp_pagination(500, 0)
        self.assertEqual(limit, 200)

    def test_limit_clamped_to_min(self):
        limit, offset = clamp_pagination(-5, 0)
        self.assertEqual(limit, 1)

    def test_negative_offset_clamped(self):
        limit, offset = clamp_pagination(50, -10)
        self.assertEqual(offset, 0)

    def test_custom_max_limit(self):
        limit, offset = clamp_pagination(500, 0, max_limit=100)
        self.assertEqual(limit, 100)


class TestSignalDirection(unittest.TestCase):
    """Test signal direction mappings."""

    def test_buy_positive(self):
        self.assertEqual(SIGNAL_DIRECTION["BUY"], 1.0)

    def test_sell_negative(self):
        self.assertEqual(SIGNAL_DIRECTION["SELL"], -1.0)

    def test_hold_zero(self):
        self.assertEqual(SIGNAL_DIRECTION["HOLD"], 0.0)

    def test_close_long_partial_negative(self):
        self.assertEqual(SIGNAL_DIRECTION["CLOSE_LONG"], -0.5)

    def test_close_short_partial_positive(self):
        self.assertEqual(SIGNAL_DIRECTION["CLOSE_SHORT"], 0.5)


class TestHealthEndpoint(unittest.TestCase):
    """Test health check endpoint."""

    def setUp(self):
        self.client = app.test_client()

    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_health_returns_200(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "signal-aggregation-api")


class TestAggregateEndpoint(unittest.TestCase):
    """Test POST /api/v1/signals/aggregate endpoint."""

    def setUp(self):
        self.client = app.test_client()

    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_missing_symbol_returns_400(self):
        response = self.client.post(
            "/api/v1/signals/aggregate",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)

    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_no_body_returns_400(self):
        response = self.client.post(
            "/api/v1/signals/aggregate",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch("services.signal_aggregation_api.main.fetch_strategy_performances")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_aggregate_success(self, mock_perf, mock_signals):
        now = datetime.now(timezone.utc)
        spec_id = uuid4()
        mock_signals.return_value = [
            _make_signal("BUY", strength=0.9, spec_id=spec_id, created_at=now),
        ]
        mock_perf.return_value = {str(spec_id): 0.75}

        response = self.client.post(
            "/api/v1/signals/aggregate",
            data=json.dumps({"symbol": "BTC-USD"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["symbol"], "BTC-USD")
        self.assertIn("consensus", data)
        self.assertEqual(data["consensus"]["direction"], "bullish")
        self.assertEqual(len(data["signals"]), 1)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch("services.signal_aggregation_api.main.fetch_strategy_performances")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_aggregate_with_custom_weights(self, mock_perf, mock_signals):
        now = datetime.now(timezone.utc)
        mock_signals.return_value = [
            _make_signal("BUY", strength=0.9, created_at=now),
        ]
        mock_perf.return_value = {}

        response = self.client.post(
            "/api/v1/signals/aggregate",
            data=json.dumps({
                "symbol": "ETH-USD",
                "weights": {"recency": 0.5, "performance": 0.3, "confidence": 0.2},
                "half_life_hours": 12,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["parameters"]["half_life_hours"], 12)
        self.assertEqual(data["parameters"]["weights"]["recency"], 0.5)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_aggregate_empty_signals(self, mock_signals):
        mock_signals.return_value = []

        response = self.client.post(
            "/api/v1/signals/aggregate",
            data=json.dumps({"symbol": "BTC-USD"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["consensus"]["direction"], "neutral")
        self.assertEqual(data["consensus"]["signal_count"], 0)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_aggregate_db_error_returns_500(self, mock_signals):
        mock_signals.side_effect = Exception("DB connection failed")

        response = self.client.post(
            "/api/v1/signals/aggregate",
            data=json.dumps({"symbol": "BTC-USD"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn("error", data)


class TestConsensusEndpoint(unittest.TestCase):
    """Test GET /api/v1/signals/consensus endpoint."""

    def setUp(self):
        self.client = app.test_client()

    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_missing_symbol_returns_400(self):
        response = self.client.get("/api/v1/signals/consensus")
        self.assertEqual(response.status_code, 400)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch("services.signal_aggregation_api.main.fetch_strategy_performances")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_consensus_success(self, mock_perf, mock_signals):
        now = datetime.now(timezone.utc)
        mock_signals.return_value = [
            _make_signal("BUY", strength=0.8, created_at=now),
            _make_signal("BUY", strength=0.7, created_at=now),
        ]
        mock_perf.return_value = {}

        response = self.client.get("/api/v1/signals/consensus?symbol=BTC-USD")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["direction"], "bullish")
        self.assertEqual(data["symbol"], "BTC-USD")
        self.assertIn("as_of", data)
        self.assertEqual(data["signal_count"], 2)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch("services.signal_aggregation_api.main.fetch_strategy_performances")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_consensus_with_params(self, mock_perf, mock_signals):
        mock_signals.return_value = []
        mock_perf.return_value = {}

        response = self.client.get(
            "/api/v1/signals/consensus?symbol=ETH-USD&hours=12&half_life_hours=6"
        )
        self.assertEqual(response.status_code, 200)
        mock_signals.assert_called_once_with("ETH-USD", hours=12)

    @patch("services.signal_aggregation_api.main.fetch_signals_for_symbol")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_consensus_db_error_returns_500(self, mock_signals):
        mock_signals.side_effect = Exception("DB error")

        response = self.client.get("/api/v1/signals/consensus?symbol=BTC-USD")
        self.assertEqual(response.status_code, 500)


class TestHistoryEndpoint(unittest.TestCase):
    """Test GET /api/v1/signals/history endpoint."""

    def setUp(self):
        self.client = app.test_client()

    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_missing_symbol_returns_400(self):
        response = self.client.get("/api/v1/signals/history")
        self.assertEqual(response.status_code, 400)

    @patch("services.signal_aggregation_api.main.fetch_signal_history")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_history_success(self, mock_history):
        mock_history.return_value = (
            [
                {
                    "id": str(uuid4()),
                    "instrument": "BTC-USD",
                    "signal_type": "BUY",
                    "strength": 0.8,
                    "price": 50000.0,
                    "outcome": "PROFIT",
                    "pnl": 500.0,
                    "created_at": "2024-01-01T12:00:00",
                }
            ],
            1,
        )

        response = self.client.get("/api/v1/signals/history?symbol=BTC-USD")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["symbol"], "BTC-USD")
        self.assertEqual(len(data["signals"]), 1)
        self.assertEqual(data["pagination"]["total"], 1)

    @patch("services.signal_aggregation_api.main.fetch_signal_history")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_history_pagination_params(self, mock_history):
        mock_history.return_value = ([], 0)

        response = self.client.get(
            "/api/v1/signals/history?symbol=BTC-USD&days=7&limit=25&offset=50"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["pagination"]["limit"], 25)
        self.assertEqual(data["pagination"]["offset"], 50)

    @patch("services.signal_aggregation_api.main.fetch_signal_history")
    @patch.dict("os.environ", {"TRADESTREAM_API_KEY": ""})
    def test_history_db_error_returns_500(self, mock_history):
        mock_history.side_effect = Exception("DB error")

        response = self.client.get("/api/v1/signals/history?symbol=BTC-USD")
        self.assertEqual(response.status_code, 500)


class TestDecayIntegration(unittest.TestCase):
    """Integration tests for signal decay in consensus computation."""

    def test_recent_signal_dominates_old_opposite(self):
        """A recent BUY should outweigh an old SELL of equal strength."""
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("BUY", strength=0.7, created_at=now),
            _make_signal("SELL", strength=0.7,
                         created_at=now - timedelta(hours=72)),
        ]
        result = compute_consensus(signals, now, {}, half_life_hours=24)
        self.assertEqual(result["direction"], "bullish")

    def test_many_old_signals_can_overpower_one_recent(self):
        """Many old signals can still overpower a single recent signal."""
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("BUY", strength=0.5, created_at=now),
        ]
        # Add many recent sell signals
        for i in range(10):
            signals.append(
                _make_signal(
                    "SELL", strength=0.9,
                    created_at=now - timedelta(hours=i + 1),
                )
            )
        result = compute_consensus(signals, now, {}, half_life_hours=48)
        self.assertEqual(result["direction"], "bearish")

    def test_zero_half_life_no_decay(self):
        """With zero half-life, all signals have equal weight regardless of age."""
        now = datetime.now(timezone.utc)
        old = _make_signal("SELL", strength=0.8,
                           created_at=now - timedelta(hours=1000))
        fresh = _make_signal("BUY", strength=0.8, created_at=now)
        result = compute_consensus([old, fresh], now, {}, half_life_hours=0)
        # With no decay, equal strength BUY/SELL should be neutral
        self.assertEqual(result["direction"], "neutral")


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_single_signal_consensus(self):
        now = datetime.now(timezone.utc)
        signals = [_make_signal("BUY", strength=0.9, created_at=now)]
        result = compute_consensus(signals, now, {})
        self.assertEqual(result["signal_count"], 1)
        self.assertEqual(result["direction"], "bullish")

    def test_all_hold_signals_neutral(self):
        now = datetime.now(timezone.utc)
        signals = [
            _make_signal("HOLD", strength=0.9, created_at=now),
            _make_signal("HOLD", strength=0.5, created_at=now),
        ]
        result = compute_consensus(signals, now, {})
        self.assertEqual(result["direction"], "neutral")
        self.assertAlmostEqual(result["score"], 0.0)

    def test_unknown_signal_type_treated_as_hold(self):
        now = datetime.now(timezone.utc)
        signal = _make_signal("UNKNOWN_TYPE", strength=0.9, created_at=now)
        score = compute_signal_score(signal, now, strategy_performance=0.5)
        self.assertAlmostEqual(score, 0.0)

    def test_consensus_with_no_created_at(self):
        """Signals missing created_at should still be processed."""
        now = datetime.now(timezone.utc)
        signal = _make_signal("BUY", strength=0.8)
        signal["created_at"] = None
        result = compute_consensus([signal], now, {})
        self.assertEqual(result["signal_count"], 1)


if __name__ == "__main__":
    unittest.main()
