"""Tests for the deterministic opportunity scoring engine (scoring.py).

Covers the spec formula: Sharpe adjustment, regime detection, score caching,
tier assignment, and score breakdown.
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.opportunity_scorer_agent.scoring import (
    DEFAULT_WEIGHTS,
    FRESHNESS_WINDOW_MIN,
    ScoredSignal,
    apply_sharpe_adjustment,
    assign_tier,
    calculate_expected_return,
    calculate_opportunity_score,
    compute_score_breakdown,
    detect_regime_from_percentile,
    get_regime_adjusted_caps,
)


class TestRegimeCaps:
    """Tests for market regime normalization caps."""

    def test_normal_regime(self):
        caps = get_regime_adjusted_caps("normal")
        assert caps.max_return == 0.05
        assert caps.max_volatility == 0.03

    def test_high_volatility_regime(self):
        caps = get_regime_adjusted_caps("high_volatility")
        assert caps.max_return == 0.08
        assert caps.max_volatility == 0.05

    def test_extreme_regime(self):
        caps = get_regime_adjusted_caps("extreme")
        assert caps.max_return == 0.15
        assert caps.max_volatility == 0.10

    def test_unknown_regime_defaults_to_normal(self):
        caps = get_regime_adjusted_caps("unknown")
        assert caps.max_return == 0.05
        assert caps.max_volatility == 0.03


class TestSharpeAdjustment:
    """Tests for the Sharpe-like risk adjustment."""

    def test_zero_stddev_returns_raw(self):
        """No variance data — use raw return."""
        assert apply_sharpe_adjustment(0.03, 0.0) == 0.03

    def test_negative_stddev_returns_raw(self):
        assert apply_sharpe_adjustment(0.03, -1.0) == 0.03

    def test_equal_return_and_stddev(self):
        """Sharpe = 1.0, adjustment = 0.5/2.0 = 0.25, multiplier = 0.75."""
        result = apply_sharpe_adjustment(0.03, 0.03)
        # sharpe_factor = 1.0, adj_mult = 0.5/2.0 = 0.25, result = 0.03 * 0.75 = 0.0225
        assert abs(result - 0.0225) < 1e-9

    def test_high_sharpe_capped(self):
        """Sharpe > 2.0 should be capped at 2.0, giving full multiplier 1.0."""
        result = apply_sharpe_adjustment(0.03, 0.01)
        # sharpe = 3.0, capped at 2.0, adj_mult = 1.0, result = 0.03 * 1.0 = 0.03
        assert abs(result - 0.03) < 1e-9

    def test_low_sharpe_penalizes(self):
        """Sharpe = 0.5, adjustment = 0.25/2.0 = 0.125, multiplier = 0.625."""
        result = apply_sharpe_adjustment(0.03, 0.06)
        expected = 0.03 * (0.5 + 0.5 * (0.5 / 2.0))
        assert abs(result - expected) < 1e-9

    def test_spec_example_strategy_a(self):
        """Spec: Strategy A: 3% return, 1% stddev -> Sharpe=3 (capped at 2)."""
        result = apply_sharpe_adjustment(0.03, 0.01)
        assert abs(result - 0.03) < 1e-9  # Full adjustment

    def test_spec_example_strategy_b(self):
        """Spec: Strategy B: 3% return, 3% stddev -> Sharpe=1."""
        result = apply_sharpe_adjustment(0.03, 0.03)
        expected = 0.03 * (0.5 + 0.5 * (1.0 / 2.0))
        assert abs(result - expected) < 1e-9

    def test_spec_example_strategy_c(self):
        """Spec: Strategy C: 3% return, 6% stddev -> Sharpe=0.5."""
        result = apply_sharpe_adjustment(0.03, 0.06)
        expected = 0.03 * (0.5 + 0.5 * (0.5 / 2.0))
        assert abs(result - expected) < 1e-9


class TestRegimeDetection:
    """Tests for regime detection from volatility percentile."""

    def test_normal_regime(self):
        assert detect_regime_from_percentile(0.50) == "normal"

    def test_high_volatility_at_boundary(self):
        assert detect_regime_from_percentile(0.80) == "high_volatility"

    def test_high_volatility_above_boundary(self):
        assert detect_regime_from_percentile(0.90) == "high_volatility"

    def test_extreme_at_boundary(self):
        assert detect_regime_from_percentile(0.95) == "extreme"

    def test_extreme_above_boundary(self):
        assert detect_regime_from_percentile(0.99) == "extreme"

    def test_zero_percentile(self):
        assert detect_regime_from_percentile(0.0) == "normal"

    def test_just_below_high_vol(self):
        assert detect_regime_from_percentile(0.79) == "normal"

    def test_just_below_extreme(self):
        assert detect_regime_from_percentile(0.94) == "high_volatility"


class TestCalculateOpportunityScore:
    """Tests for the main scoring formula."""

    def test_perfect_score(self):
        """All factors at max under normal regime."""
        score = calculate_opportunity_score(
            confidence=1.0,
            expected_return=0.05,  # Equals max_return for normal
            return_stddev=0.0,  # No Sharpe penalty
            consensus_pct=1.0,
            volatility=0.03,  # Equals max_volatility for normal
            minutes_ago=0,
            market_regime="normal",
        )
        assert score == 100.0

    def test_zero_score(self):
        """All factors at minimum."""
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,  # Full freshness decay
            market_regime="normal",
        )
        assert score == 0.0

    def test_confidence_only(self):
        """Only confidence contributes."""
        score = calculate_opportunity_score(
            confidence=1.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score == 25.0

    def test_expected_return_only(self):
        """Only expected return contributes (no Sharpe penalty)."""
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.05,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score == 30.0

    def test_consensus_only(self):
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=1.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score == 20.0

    def test_volatility_only(self):
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.03,
            minutes_ago=60,
        )
        assert score == 15.0

    def test_freshness_only(self):
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=0,
        )
        assert score == 10.0

    def test_freshness_at_30_min(self):
        """50% freshness at 30 minutes."""
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=30,
        )
        assert score == 5.0

    def test_sharpe_adjustment_affects_score(self):
        """High stddev should reduce the expected return contribution."""
        score_low_risk = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        score_high_risk = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.03,
            return_stddev=0.06,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score_low_risk > score_high_risk

    def test_extreme_regime_widens_caps(self):
        """Same volatility scores lower under extreme regime (wider cap)."""
        score_normal = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.03,
            minutes_ago=60,
            market_regime="normal",
        )
        score_extreme = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.03,
            minutes_ago=60,
            market_regime="extreme",
        )
        assert score_normal > score_extreme  # 0.03/0.03 > 0.03/0.10

    def test_return_exceeding_cap_is_clamped(self):
        """Returns above the cap should max out at 1.0."""
        score = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.10,  # 2x the normal cap of 0.05
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score == 30.0  # Same as max

    def test_deterministic(self):
        """Same inputs always produce the same score."""
        kwargs = dict(
            confidence=0.82,
            expected_return=0.032,
            return_stddev=0.015,
            consensus_pct=0.80,
            volatility=0.021,
            minutes_ago=0,
            market_regime="normal",
        )
        scores = [calculate_opportunity_score(**kwargs) for _ in range(100)]
        assert len(set(scores)) == 1

    def test_realistic_scenario(self):
        """A realistic signal with known inputs should produce expected score."""
        score = calculate_opportunity_score(
            confidence=0.82,
            expected_return=0.032,
            return_stddev=0.015,
            consensus_pct=0.80,
            volatility=0.021,
            minutes_ago=0,
            market_regime="normal",
        )
        # All components positive, should be in GOOD-HOT range
        assert 60 <= score <= 100


class TestAssignTier:
    """Tests for tier assignment."""

    def test_hot(self):
        assert assign_tier(80) == "HOT"
        assert assign_tier(100) == "HOT"

    def test_good(self):
        assert assign_tier(60) == "GOOD"
        assert assign_tier(79.9) == "GOOD"

    def test_neutral(self):
        assert assign_tier(40) == "NEUTRAL"
        assert assign_tier(59.9) == "NEUTRAL"

    def test_low(self):
        assert assign_tier(0) == "LOW"
        assert assign_tier(39.9) == "LOW"

    def test_boundaries(self):
        assert assign_tier(79.99) == "GOOD"
        assert assign_tier(80.0) == "HOT"


class TestCalculateExpectedReturn:
    """Tests for weighted expected return calculation."""

    def test_empty_list(self):
        ret, std = calculate_expected_return([])
        assert ret == 0.0
        assert std == 0.0

    def test_single_strategy(self):
        ret, std = calculate_expected_return([(0.03, 0.01, 1.0)])
        assert abs(ret - 0.03) < 1e-9
        assert abs(std - 0.01) < 1e-9

    def test_weighted_average(self):
        """Two strategies with different weights."""
        ret, std = calculate_expected_return(
            [
                (0.02, 0.01, 1.0),  # Lower return, lower weight
                (0.04, 0.02, 3.0),  # Higher return, higher weight
            ]
        )
        expected_ret = (0.02 * 1.0 + 0.04 * 3.0) / 4.0
        expected_std = (0.01 * 1.0 + 0.02 * 3.0) / 4.0
        assert abs(ret - expected_ret) < 1e-9
        assert abs(std - expected_std) < 1e-9

    def test_zero_total_weight(self):
        ret, std = calculate_expected_return([(0.03, 0.01, 0.0)])
        assert ret == 0.0
        assert std == 0.0


class TestScoreBreakdown:
    """Tests for the detailed score breakdown."""

    def test_breakdown_structure(self):
        result = compute_score_breakdown(
            confidence=0.82,
            expected_return=0.032,
            return_stddev=0.015,
            consensus_pct=0.80,
            volatility=0.021,
            volatility_percentile=0.65,
            minutes_ago=0,
            market_regime="normal",
        )
        assert "opportunity_score" in result
        assert "opportunity_tier" in result
        assert "market_regime" in result
        assert "opportunity_factors" in result

        factors = result["opportunity_factors"]
        assert "confidence" in factors
        assert "expected_return" in factors
        assert "consensus" in factors
        assert "volatility" in factors
        assert "freshness" in factors

    def test_breakdown_contributions_sum_to_score(self):
        result = compute_score_breakdown(
            confidence=0.82,
            expected_return=0.032,
            return_stddev=0.015,
            consensus_pct=0.80,
            volatility=0.021,
            volatility_percentile=0.65,
            minutes_ago=0,
            market_regime="normal",
        )
        factors = result["opportunity_factors"]
        contrib_sum = sum(f["contribution"] for f in factors.values())
        assert (
            abs(contrib_sum - result["opportunity_score"]) < 0.2
        )  # Rounding tolerance

    def test_breakdown_tier_matches_score(self):
        result = compute_score_breakdown(
            confidence=1.0,
            expected_return=0.05,
            return_stddev=0.0,
            consensus_pct=1.0,
            volatility=0.03,
            volatility_percentile=0.50,
            minutes_ago=0,
            market_regime="normal",
        )
        assert result["opportunity_tier"] == "HOT"

    def test_breakdown_includes_risk_adjusted(self):
        result = compute_score_breakdown(
            confidence=0.5,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.5,
            volatility=0.02,
            volatility_percentile=0.50,
            minutes_ago=0,
            market_regime="normal",
        )
        er_factor = result["opportunity_factors"]["expected_return"]
        assert "risk_adjusted" in er_factor
        assert er_factor["risk_adjusted"] > 0

    def test_breakdown_freshness_cached_flag(self):
        result = compute_score_breakdown(
            confidence=0.5,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.5,
            volatility=0.02,
            volatility_percentile=0.50,
            minutes_ago=0,
            market_regime="normal",
        )
        assert result["opportunity_factors"]["freshness"]["cached"] is True


class TestScoredSignal:
    """Tests for the ScoredSignal dataclass with cached scoring."""

    def test_from_signal_creates_scored(self):
        scored = ScoredSignal.from_signal(
            signal_id="sig-001",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.85,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.80,
            volatility=0.021,
            volatility_percentile=0.65,
            strategies_analyzed=5,
            strategies_agreeing=4,
        )
        assert scored.signal_id == "sig-001"
        assert scored.symbol == "BTC/USD"
        assert scored.opportunity_score > 0
        assert scored.opportunity_tier in ("HOT", "GOOD", "NEUTRAL", "LOW")
        assert scored.market_regime == "normal"

    def test_score_is_cached_at_creation(self):
        """Score should not change over time."""
        scored = ScoredSignal.from_signal(
            signal_id="sig-002",
            symbol="ETH/USD",
            action="BUY",
            confidence=0.90,
            expected_return=0.04,
            return_stddev=0.01,
            consensus_pct=0.90,
            volatility=0.025,
            volatility_percentile=0.70,
            strategies_analyzed=5,
            strategies_agreeing=4,
        )
        score_at_creation = scored.opportunity_score
        # Score is a frozen value — accessing it again gives the same result
        assert scored.opportunity_score == score_at_creation

    def test_display_age_increases(self):
        """Display age should reflect actual time elapsed."""
        scored = ScoredSignal.from_signal(
            signal_id="sig-003",
            symbol="SOL/USD",
            action="SELL",
            confidence=0.70,
            expected_return=0.02,
            return_stddev=0.01,
            consensus_pct=0.60,
            volatility=0.015,
            volatility_percentile=0.50,
            strategies_analyzed=3,
            strategies_agreeing=2,
        )
        # Just created, so display age should be 0
        assert scored.display_age_minutes >= 0

    def test_is_stale_at_creation(self):
        """Freshly created signal should not be stale."""
        scored = ScoredSignal.from_signal(
            signal_id="sig-004",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.80,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.70,
            volatility=0.02,
            volatility_percentile=0.60,
            strategies_analyzed=4,
            strategies_agreeing=3,
        )
        assert not scored.is_stale

    def test_stale_after_60_minutes(self):
        """Signal older than 60 minutes should be stale."""
        scored = ScoredSignal.from_signal(
            signal_id="sig-005",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.80,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.70,
            volatility=0.02,
            volatility_percentile=0.60,
            strategies_analyzed=4,
            strategies_agreeing=3,
        )
        # Manually set scored_at to 61 minutes ago
        scored.scored_at = datetime.now(timezone.utc) - timedelta(minutes=61)
        assert scored.is_stale

    def test_auto_detects_regime_from_percentile(self):
        """When market_regime is None, it should be detected from percentile."""
        scored_normal = ScoredSignal.from_signal(
            signal_id="sig-006",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.80,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.70,
            volatility=0.02,
            volatility_percentile=0.50,
            strategies_analyzed=4,
            strategies_agreeing=3,
        )
        assert scored_normal.market_regime == "normal"

        scored_extreme = ScoredSignal.from_signal(
            signal_id="sig-007",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.80,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.70,
            volatility=0.02,
            volatility_percentile=0.96,
            strategies_analyzed=4,
            strategies_agreeing=3,
        )
        assert scored_extreme.market_regime == "extreme"

    def test_freshness_always_zero_at_creation(self):
        """Score should be computed with minutes_ago=0 (cached at creation)."""
        scored = ScoredSignal.from_signal(
            signal_id="sig-008",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.80,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.70,
            volatility=0.02,
            volatility_percentile=0.50,
            strategies_analyzed=4,
            strategies_agreeing=3,
        )
        # Freshness factor should have been scored at 0 minutes
        freshness = scored.opportunity_factors["freshness"]
        assert freshness["value"] == 0
        assert freshness["cached"] is True

    def test_explicit_regime_overrides_detection(self):
        """When market_regime is provided, percentile-based detection is skipped."""
        scored = ScoredSignal.from_signal(
            signal_id="sig-009",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.80,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.70,
            volatility=0.02,
            volatility_percentile=0.50,  # Would be "normal"
            strategies_analyzed=4,
            strategies_agreeing=3,
            market_regime="extreme",  # Override
        )
        assert scored.market_regime == "extreme"
