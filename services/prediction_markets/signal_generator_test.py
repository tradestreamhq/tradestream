"""Tests for the prediction market signal generator."""

from absl.testing import absltest

from services.prediction_markets.signal_generator import (
    PredictionMarketSignalGenerator,
    SignalType,
    ThresholdConfig,
)


class PredictionMarketSignalGeneratorTest(absltest.TestCase):
    def setUp(self):
        self.config = ThresholdConfig(
            bullish_threshold=0.70,
            bearish_threshold=0.30,
            spike_threshold=0.10,
            volume_anomaly_multiplier=3.0,
        )
        self.generator = PredictionMarketSignalGenerator(
            config=self.config,
            target_symbols=["BTC/USD", "ETH/USD"],
        )

    def test_bullish_threshold_crossing(self):
        events = [{
            "event_id": "fed-rate-1",
            "category": "monetary_policy",
            "question": "Will Fed cut rates?",
            "probability": 0.75,
            "previous_probability": 0.65,
            "volume": 10000,
        }]

        signals = self.generator.generate_signals(events)

        self.assertGreater(len(signals), 0)
        btc_signals = [s for s in signals if s.affected_asset == "BTC/USD"]
        self.assertGreater(len(btc_signals), 0)
        self.assertEqual(btc_signals[0].signal_type,
                         SignalType.PROBABILITY_THRESHOLD)

    def test_bearish_threshold_crossing(self):
        events = [{
            "event_id": "etf-1",
            "category": "crypto_specific",
            "question": "Will BTC ETF be approved?",
            "probability": 0.25,
            "previous_probability": 0.35,
            "volume": 5000,
        }]

        signals = self.generator.generate_signals(events)

        threshold_signals = [
            s for s in signals
            if s.signal_type == SignalType.PROBABILITY_THRESHOLD
        ]
        self.assertGreater(len(threshold_signals), 0)

    def test_no_signal_when_within_thresholds(self):
        events = [{
            "event_id": "test-1",
            "category": "monetary_policy",
            "question": "Neutral event",
            "probability": 0.50,
            "previous_probability": 0.48,
            "volume": 1000,
        }]

        signals = self.generator.generate_signals(events)

        # No threshold or spike signals for small change
        threshold_signals = [
            s for s in signals
            if s.signal_type == SignalType.PROBABILITY_THRESHOLD
        ]
        self.assertEqual(len(threshold_signals), 0)

    def test_spike_detection(self):
        events = [{
            "event_id": "spike-1",
            "category": "regulatory",
            "question": "SEC approval?",
            "probability": 0.60,
            "previous_probability": 0.40,
            "volume": 10000,
        }]

        signals = self.generator.generate_signals(events)

        spike_signals = [
            s for s in signals
            if s.signal_type == SignalType.PROBABILITY_SPIKE
        ]
        self.assertGreater(len(spike_signals), 0)

    def test_volume_anomaly_detection(self):
        events = [{
            "event_id": "vol-1",
            "category": "monetary_policy",
            "question": "Rate decision",
            "probability": 0.50,
            "previous_probability": 0.50,
            "volume": 40000,
            "avg_volume": 10000,
        }]

        signals = self.generator.generate_signals(events)

        volume_signals = [
            s for s in signals
            if s.signal_type == SignalType.VOLUME_ANOMALY
        ]
        self.assertGreater(len(volume_signals), 0)

    def test_insider_alert_processing(self):
        insider_alerts = [{
            "wallet_address": "0x7a3f91abc",
            "market_id": "market-1",
            "market_question": "Fed Rate Cut",
            "side": "BUY",
            "position_size": 15000,
            "price": 0.75,
            "confidence": "HIGH",
        }]

        signals = self.generator.generate_signals([], insider_alerts)

        insider_signals = [
            s for s in signals
            if s.signal_type == SignalType.INSIDER_ACTIVITY
        ]
        self.assertGreater(len(insider_signals), 0)
        self.assertIn("0x7a3f91abc", insider_signals[0].reasoning)

    def test_low_confidence_insider_alerts_ignored(self):
        insider_alerts = [{
            "wallet_address": "0xabc",
            "market_id": "m1",
            "market_question": "Test",
            "side": "BUY",
            "position_size": 100,
            "price": 0.5,
            "confidence": "LOW",
        }]

        signals = self.generator.generate_signals([], insider_alerts)

        insider_signals = [
            s for s in signals
            if s.signal_type == SignalType.INSIDER_ACTIVITY
        ]
        self.assertEqual(len(insider_signals), 0)

    def test_signal_strength_bounded(self):
        events = [{
            "event_id": "strong-1",
            "category": "monetary_policy",
            "question": "Massive move",
            "probability": 0.99,
            "previous_probability": 0.10,
            "volume": 100000,
            "avg_volume": 1000,
        }]

        signals = self.generator.generate_signals(events)

        for s in signals:
            self.assertGreaterEqual(s.signal_strength, 0.0)
            self.assertLessEqual(s.signal_strength, 1.0)

    def test_empty_events_no_signals(self):
        signals = self.generator.generate_signals([])
        self.assertEqual(len(signals), 0)

    def test_target_symbol_filtering(self):
        generator = PredictionMarketSignalGenerator(
            config=self.config,
            target_symbols=["BTC/USD"],  # Only BTC
        )
        events = [{
            "event_id": "filter-1",
            "category": "monetary_policy",
            "question": "Rate cut",
            "probability": 0.80,
            "previous_probability": 0.60,
            "volume": 10000,
        }]

        signals = generator.generate_signals(events)

        # All signals should be for BTC/USD only
        for s in signals:
            self.assertEqual(s.affected_asset, "BTC/USD")


if __name__ == "__main__":
    absltest.main()
