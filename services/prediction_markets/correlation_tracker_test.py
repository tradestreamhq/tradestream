"""Tests for the correlation tracker."""

from absl.testing import absltest

from services.prediction_markets.correlation_tracker import CorrelationTracker


class CorrelationTrackerTest(absltest.TestCase):
    def setUp(self):
        self.tracker = CorrelationTracker(
            max_observations=100,
            observation_window_hours=48.0,
        )

    def test_record_and_compute_correlation(self):
        # Record positively correlated observations
        for i in range(10):
            self.tracker.record_observation(
                event_id=f"e{i}",
                category="monetary_policy",
                asset_symbol="BTC/USD",
                probability_change=0.05 * (i + 1),
                price_change_pct=2.0 * (i + 1),
                lag_hours=24.0,
            )

        result = self.tracker.compute_correlation("monetary_policy", "BTC/USD")

        self.assertIsNotNone(result)
        self.assertGreater(result.correlation, 0.9)
        self.assertEqual(result.sample_count, 10)
        self.assertAlmostEqual(result.avg_lag_hours, 24.0)

    def test_negative_correlation(self):
        for i in range(10):
            self.tracker.record_observation(
                event_id=f"e{i}",
                category="regulatory",
                asset_symbol="ETH/USD",
                probability_change=0.05 * (i + 1),
                price_change_pct=-2.0 * (i + 1),
                lag_hours=12.0,
            )

        result = self.tracker.compute_correlation("regulatory", "ETH/USD")

        self.assertIsNotNone(result)
        self.assertLess(result.correlation, -0.9)

    def test_insufficient_data_returns_none(self):
        self.tracker.record_observation(
            event_id="e1",
            category="political",
            asset_symbol="BTC/USD",
            probability_change=0.1,
            price_change_pct=5.0,
            lag_hours=24.0,
        )

        result = self.tracker.compute_correlation("political", "BTC/USD")
        self.assertIsNone(result)

    def test_signal_quality_score(self):
        for i in range(10):
            self.tracker.record_observation(
                event_id=f"e{i}",
                category="monetary_policy",
                asset_symbol="BTC/USD",
                probability_change=0.1,
                price_change_pct=3.0,
                lag_hours=24.0,
            )

        score = self.tracker.get_signal_quality_score("monetary_policy", "BTC/USD")

        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)

    def test_signal_quality_score_insufficient_data(self):
        score = self.tracker.get_signal_quality_score("unknown", "BTC/USD")
        self.assertEqual(score, 0.5)

    def test_max_observations_enforced(self):
        tracker = CorrelationTracker(max_observations=5)

        for i in range(10):
            tracker.record_observation(
                event_id=f"e{i}",
                category="test",
                asset_symbol="BTC/USD",
                probability_change=0.1,
                price_change_pct=1.0,
                lag_hours=1.0,
            )

        key = ("test", "BTC/USD")
        self.assertEqual(len(tracker._observations[key]), 5)

    def test_get_all_correlations(self):
        for i in range(10):
            self.tracker.record_observation(
                event_id=f"e{i}",
                category="monetary_policy",
                asset_symbol="BTC/USD",
                probability_change=0.05,
                price_change_pct=2.0,
                lag_hours=24.0,
            )
            self.tracker.record_observation(
                event_id=f"f{i}",
                category="regulatory",
                asset_symbol="ETH/USD",
                probability_change=-0.05,
                price_change_pct=-1.0,
                lag_hours=12.0,
            )

        results = self.tracker.get_all_correlations()

        self.assertEqual(len(results), 2)

    def test_pearson_correlation_zero_variance(self):
        result = CorrelationTracker._pearson_correlation(
            [1.0, 1.0, 1.0], [2.0, 3.0, 4.0]
        )
        self.assertEqual(result, 0.0)

    def test_accuracy_no_valid_pairs(self):
        result = CorrelationTracker._compute_accuracy([0.0, 0.0], [0.0, 0.0])
        self.assertEqual(result, 0.5)


if __name__ == "__main__":
    absltest.main()
