"""Tests for signal fusion engine."""

from services.autonomous_runner.signal_fusion import (
    ConflictResolutionStrategy,
    FusedSignal,
    SignalAction,
    SourceSignal,
    calculate_confidence,
    fuse_signals,
)


class TestCalculateConfidence:
    def test_full_consensus_buy(self):
        signals = [
            SourceSignal(source="a", action=SignalAction.BUY, confidence=0.9),
            SourceSignal(source="b", action=SignalAction.BUY, confidence=0.8),
            SourceSignal(source="c", action=SignalAction.BUY, confidence=0.85),
        ]
        conf = calculate_confidence(signals)
        assert 0.80 <= conf <= 0.95

    def test_split_consensus_lowers_confidence(self):
        signals = [
            SourceSignal(source="a", action=SignalAction.BUY, confidence=0.8),
            SourceSignal(source="b", action=SignalAction.SELL, confidence=0.8),
        ]
        conf = calculate_confidence(signals)
        assert conf < 0.70

    def test_empty_signals(self):
        conf = calculate_confidence([])
        assert conf == 0.30

    def test_single_signal(self):
        signals = [
            SourceSignal(source="a", action=SignalAction.BUY, confidence=0.9),
        ]
        conf = calculate_confidence(signals)
        assert 0.80 <= conf <= 0.95


class TestFuseSignals:
    def test_unanimous_buy(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.9),
            SourceSignal(source="sentiment", action=SignalAction.BUY, confidence=0.7),
            SourceSignal(source="prediction_market", action=SignalAction.BUY, confidence=0.8),
        ]
        result = fuse_signals("BTC-USD", signals)
        assert result.action == SignalAction.BUY
        assert result.confidence >= 0.60
        assert result.agreement_ratio == 1.0
        assert result.symbol == "BTC-USD"

    def test_majority_buy(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.85),
            SourceSignal(source="sentiment", action=SignalAction.BUY, confidence=0.6),
            SourceSignal(source="regime_detection", action=SignalAction.SELL, confidence=0.5),
        ]
        result = fuse_signals("ETH-USD", signals)
        assert result.action == SignalAction.BUY
        assert result.agreement_ratio > 0.5

    def test_conflict_defaults_to_hold(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.6),
            SourceSignal(source="sentiment", action=SignalAction.SELL, confidence=0.6),
        ]
        result = fuse_signals(
            "SOL-USD",
            signals,
            conflict_strategy=ConflictResolutionStrategy.CONSERVATIVE,
        )
        assert result.action == SignalAction.HOLD

    def test_empty_signals_returns_hold(self):
        result = fuse_signals("BTC-USD", [])
        assert result.action == SignalAction.HOLD
        assert result.confidence == 0.30
        assert result.agreement_ratio == 0.0

    def test_highest_confidence_strategy(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.SELL, confidence=0.5),
            SourceSignal(source="sentiment", action=SignalAction.BUY, confidence=0.95),
        ]
        result = fuse_signals(
            "BTC-USD",
            signals,
            conflict_strategy=ConflictResolutionStrategy.HIGHEST_CONFIDENCE,
        )
        assert result.action == SignalAction.BUY
        assert result.conflict_resolution_applied == "highest_confidence"

    def test_conservative_requires_strong_consensus(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.9),
            SourceSignal(source="sentiment", action=SignalAction.BUY, confidence=0.85),
            SourceSignal(source="prediction_market", action=SignalAction.BUY, confidence=0.8),
            SourceSignal(source="regime_detection", action=SignalAction.HOLD, confidence=0.4),
        ]
        result = fuse_signals(
            "BTC-USD",
            signals,
            conflict_strategy=ConflictResolutionStrategy.CONSERVATIVE,
        )
        # Strong BUY consensus should pass conservative
        assert result.action in (SignalAction.BUY, SignalAction.HOLD)

    def test_source_weights_applied(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.6),
            SourceSignal(source="sentiment", action=SignalAction.SELL, confidence=0.9),
        ]
        # Strategy has higher weight than sentiment
        result = fuse_signals("BTC-USD", signals)
        # Strategy weight=0.40 vs sentiment weight=0.15
        # Strategy: 0.40 * 0.6 = 0.24, Sentiment: 0.15 * 0.9 = 0.135
        assert result.action == SignalAction.BUY

    def test_fused_signal_has_all_fields(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.8),
        ]
        result = fuse_signals("BTC-USD", signals)
        assert isinstance(result, FusedSignal)
        assert result.symbol == "BTC-USD"
        assert result.action in SignalAction
        assert 0.0 <= result.confidence <= 1.0
        assert 0.0 <= result.agreement_ratio <= 1.0
        assert result.conflict_resolution_applied != ""


class TestConflictResolution:
    def test_weighted_majority_clear_winner(self):
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.9),
            SourceSignal(source="sentiment", action=SignalAction.BUY, confidence=0.8),
            SourceSignal(source="regime_detection", action=SignalAction.SELL, confidence=0.3),
        ]
        result = fuse_signals(
            "BTC-USD",
            signals,
            conflict_strategy=ConflictResolutionStrategy.WEIGHTED_MAJORITY,
        )
        assert result.action == SignalAction.BUY

    def test_weighted_majority_near_tie_gives_hold(self):
        # Both sources equal weight and confidence
        signals = [
            SourceSignal(source="strategy_consensus", action=SignalAction.BUY, confidence=0.5),
            SourceSignal(source="prediction_market", action=SignalAction.SELL, confidence=0.5),
        ]
        result = fuse_signals(
            "BTC-USD",
            signals,
            source_weights={"strategy_consensus": 0.5, "prediction_market": 0.5},
            conflict_strategy=ConflictResolutionStrategy.WEIGHTED_MAJORITY,
        )
        assert result.action == SignalAction.HOLD
