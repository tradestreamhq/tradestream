"""Tests for the insider activity detector."""

from absl.testing import absltest

from services.prediction_markets.insider_detector import (
    InsiderActivityDetector,
)


class InsiderActivityDetectorTest(absltest.TestCase):
    def setUp(self):
        self.detector = InsiderActivityDetector(
            volume_spike_threshold=3.0,
            price_dislocation_threshold=0.15,
            min_volume_for_analysis=1000.0,
        )

    def test_volume_spike_detection(self):
        markets = [{
            "market_id": "m1",
            "question": "Rate cut?",
            "volume": 30000,
            "avg_volume": 5000,
        }]

        signals = self.detector.analyze_markets(markets)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].anomaly_type, "volume_spike")
        self.assertEqual(signals[0].severity, "HIGH")

    def test_price_dislocation_detection(self):
        markets = [{
            "market_id": "m2",
            "question": "ETF approval?",
            "volume": 5000,
            "probability": 0.80,
            "previous_probability": 0.50,
        }]

        signals = self.detector.analyze_markets(markets)

        price_signals = [s for s in signals if s.anomaly_type == "price_dislocation"]
        self.assertGreater(len(price_signals), 0)
        self.assertIn("up", price_signals[0].details)

    def test_no_signal_for_low_volume(self):
        markets = [{
            "market_id": "m3",
            "question": "Low volume market",
            "volume": 500,  # Below threshold
            "avg_volume": 100,
        }]

        signals = self.detector.analyze_markets(markets)
        self.assertEqual(len(signals), 0)

    def test_no_signal_for_normal_activity(self):
        markets = [{
            "market_id": "m4",
            "question": "Normal market",
            "volume": 5000,
            "avg_volume": 4000,
            "probability": 0.52,
            "previous_probability": 0.50,
        }]

        signals = self.detector.analyze_markets(markets)
        self.assertEqual(len(signals), 0)

    def test_critical_severity_for_extreme_spike(self):
        markets = [{
            "market_id": "m5",
            "question": "Extreme spike",
            "volume": 120000,
            "avg_volume": 5000,
        }]

        signals = self.detector.analyze_markets(markets)

        volume_signals = [s for s in signals if s.anomaly_type == "volume_spike"]
        self.assertGreater(len(volume_signals), 0)
        self.assertEqual(volume_signals[0].severity, "CRITICAL")

    def test_enrich_tracker_alerts(self):
        alerts = [{"market_id": "m1", "confidence": "HIGH"}]
        markets = [{"market_id": "m1", "volume": 50000, "liquidity": 10000,
                     "active": True}]

        enriched = self.detector.enrich_tracker_alerts(alerts, markets)

        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["current_volume"], 50000)
        self.assertEqual(enriched[0]["current_liquidity"], 10000)
        self.assertTrue(enriched[0]["market_active"])

    def test_enrich_with_missing_market(self):
        alerts = [{"market_id": "unknown", "confidence": "HIGH"}]
        markets = [{"market_id": "m1", "volume": 5000}]

        enriched = self.detector.enrich_tracker_alerts(alerts, markets)

        self.assertEqual(len(enriched), 1)
        self.assertNotIn("current_volume", enriched[0])

    def test_empty_markets(self):
        signals = self.detector.analyze_markets([])
        self.assertEqual(len(signals), 0)


if __name__ == "__main__":
    absltest.main()
