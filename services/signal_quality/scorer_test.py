"""Tests for signal quality scorer."""

import pytest

from services.signal_quality.scorer import (
    GRADE_THRESHOLDS,
    QualityScore,
    compute_grade,
    score_signal,
)


class TestComputeGrade:
    def test_grade_a(self):
        assert compute_grade(0.85) == "A"
        assert compute_grade(0.80) == "A"

    def test_grade_b(self):
        assert compute_grade(0.70) == "B"
        assert compute_grade(0.65) == "B"

    def test_grade_c(self):
        assert compute_grade(0.55) == "C"
        assert compute_grade(0.50) == "C"

    def test_grade_d(self):
        assert compute_grade(0.40) == "D"
        assert compute_grade(0.35) == "D"

    def test_grade_f(self):
        assert compute_grade(0.20) == "F"
        assert compute_grade(0.0) == "F"


class TestScoreSignal:
    def test_perfect_conditions(self):
        """All indicators agree, volume high, trend aligned, moderate volatility."""
        result = score_signal(
            entry_conditions_met=3,
            total_entry_conditions=3,
            volume_above_average=True,
            volume_ratio=1.8,
            trend_direction_matches=True,
            trend_strength=0.8,
            volatility_percentile=0.5,
        )
        assert result.grade == "A"
        assert result.confidence >= 0.80
        assert result.indicator_agreement == 1.0

    def test_poor_conditions(self):
        """Few indicators agree, low volume, counter-trend, extreme volatility."""
        result = score_signal(
            entry_conditions_met=1,
            total_entry_conditions=5,
            volume_above_average=False,
            volume_ratio=0.3,
            trend_direction_matches=False,
            trend_strength=0.9,
            volatility_percentile=0.95,
        )
        assert result.grade in ("D", "F")
        assert result.confidence < 0.40

    def test_average_conditions(self):
        """Half indicators, average volume, weak trend alignment."""
        result = score_signal(
            entry_conditions_met=2,
            total_entry_conditions=4,
            volume_above_average=True,
            volume_ratio=1.2,
            trend_direction_matches=True,
            trend_strength=0.3,
            volatility_percentile=0.5,
        )
        assert result.grade in ("B", "C")
        assert 0.45 <= result.confidence <= 0.75

    def test_zero_conditions(self):
        """Edge case: zero total conditions defaults to 0.5 agreement."""
        result = score_signal(
            entry_conditions_met=0,
            total_entry_conditions=0,
            volume_above_average=False,
            volume_ratio=1.0,
            trend_direction_matches=True,
            trend_strength=0.5,
            volatility_percentile=0.5,
        )
        assert result.indicator_agreement == 0.5

    def test_volume_ratio_capped(self):
        """Volume confirmation should be capped at 1.0."""
        result = score_signal(
            entry_conditions_met=1,
            total_entry_conditions=1,
            volume_above_average=True,
            volume_ratio=5.0,
            trend_direction_matches=True,
            trend_strength=0.5,
            volatility_percentile=0.5,
        )
        assert result.volume_confirmation == 1.0

    def test_low_volatility_penalized(self):
        """Very low volatility should reduce the volatility score."""
        result = score_signal(
            entry_conditions_met=2,
            total_entry_conditions=2,
            volume_above_average=True,
            volume_ratio=1.5,
            trend_direction_matches=True,
            trend_strength=0.5,
            volatility_percentile=0.05,
        )
        assert result.volatility_context < 0.5

    def test_high_volatility_penalized(self):
        """Very high volatility should reduce the volatility score."""
        result = score_signal(
            entry_conditions_met=2,
            total_entry_conditions=2,
            volume_above_average=True,
            volume_ratio=1.5,
            trend_direction_matches=True,
            trend_strength=0.5,
            volatility_percentile=0.95,
        )
        assert result.volatility_context < 0.5

    def test_counter_trend_with_strong_trend(self):
        """Counter-trend signal with strong trend should have low trend alignment."""
        result = score_signal(
            entry_conditions_met=2,
            total_entry_conditions=2,
            volume_above_average=True,
            volume_ratio=1.5,
            trend_direction_matches=False,
            trend_strength=0.9,
            volatility_percentile=0.5,
        )
        assert result.trend_alignment < 0.1

    def test_result_has_all_fields(self):
        result = score_signal(
            entry_conditions_met=1,
            total_entry_conditions=2,
            volume_above_average=True,
            volume_ratio=1.0,
            trend_direction_matches=True,
            trend_strength=0.5,
            volatility_percentile=0.5,
        )
        assert isinstance(result, QualityScore)
        assert hasattr(result, "confidence")
        assert hasattr(result, "indicator_agreement")
        assert hasattr(result, "volume_confirmation")
        assert hasattr(result, "trend_alignment")
        assert hasattr(result, "volatility_context")
        assert hasattr(result, "grade")
