"""Tests for retirement criteria evaluation logic."""

from datetime import datetime, timedelta, timezone

import pytest

from services.janitor_agent.retirement_criteria import (
    Implementation,
    RetirementConfig,
    RetirementDecision,
    Spec,
    apply_batch_limits,
    can_reactivate,
    evaluate_implementation,
    evaluate_spec,
)


def _make_impl(**overrides) -> Implementation:
    """Create a test implementation with sensible defaults."""
    defaults = dict(
        impl_id="impl-001",
        spec_id="spec-001",
        symbol="BTC/USD",
        status="VALIDATED",
        forward_sharpe=0.2,
        forward_accuracy=0.40,
        forward_trades=150,
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
        updated_at=datetime.now(timezone.utc) - timedelta(days=60),
        sharpe_trend="DECLINING",
        spec_source="LLM_GENERATED",
        spec_name="TEST_STRATEGY",
        preferred_regime=None,
    )
    defaults.update(overrides)
    return Implementation(**defaults)


def _default_config() -> RetirementConfig:
    return RetirementConfig()


class TestEvaluateImplementation:
    def test_retires_when_all_criteria_met(self):
        impl = _make_impl()
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is True
        assert "Retired" in decision.reason

    def test_protects_canonical_specs(self):
        impl = _make_impl(spec_source="CANONICAL")
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "CANONICAL" in decision.reason

    def test_rejects_insufficient_signals(self):
        impl = _make_impl(forward_trades=50)
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "Insufficient signals" in decision.reason

    def test_rejects_too_young(self):
        impl = _make_impl(
            created_at=datetime.now(timezone.utc) - timedelta(days=90)
        )
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "Too young" in decision.reason

    def test_rejects_acceptable_sharpe(self):
        impl = _make_impl(forward_sharpe=0.8)
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "Sharpe acceptable" in decision.reason

    def test_rejects_acceptable_accuracy(self):
        impl = _make_impl(forward_accuracy=0.55)
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "Accuracy acceptable" in decision.reason

    def test_rejects_non_declining_trend(self):
        impl = _make_impl(sharpe_trend="IMPROVING")
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "not DECLINING" in decision.reason

    def test_rejects_no_better_alternatives(self):
        impl = _make_impl()
        config = _default_config()
        decision = evaluate_implementation(
            impl, config, better_alternative_exists=False
        )
        assert decision.should_retire is False
        assert "No better alternatives" in decision.reason

    def test_defers_for_regime_mismatch(self):
        impl = _make_impl(preferred_regime="trending_up")
        config = _default_config()
        decision = evaluate_implementation(
            impl, config, better_alternative_exists=True, current_regime="ranging"
        )
        assert decision.should_retire is False
        assert "Deferring" in decision.reason

    def test_retires_when_regime_matches(self):
        impl = _make_impl(preferred_regime="ranging")
        config = _default_config()
        decision = evaluate_implementation(
            impl, config, better_alternative_exists=True, current_regime="ranging"
        )
        assert decision.should_retire is True

    def test_respects_modification_grace_period(self):
        impl = _make_impl(
            updated_at=datetime.now(timezone.utc) - timedelta(days=5)
        )
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.should_retire is False
        assert "Recently modified" in decision.reason

    def test_decision_includes_metadata(self):
        impl = _make_impl()
        config = _default_config()
        decision = evaluate_implementation(impl, config, better_alternative_exists=True)
        assert decision.impl_id == "impl-001"
        assert decision.spec_id == "spec-001"
        assert decision.final_sharpe == 0.2
        assert decision.final_accuracy == 0.40
        assert decision.age_days is not None
        assert decision.signal_count == 150


class TestEvaluateSpec:
    def test_retires_when_all_impls_retired(self):
        spec = Spec(spec_id="spec-001", name="TEST", source="LLM_GENERATED")
        decision = evaluate_spec(spec, active_impl_count=0, total_impl_count=3)
        assert decision.should_retire is True
        assert "All 3 implementations retired" in decision.reason

    def test_protects_canonical(self):
        spec = Spec(spec_id="spec-001", name="TEST", source="CANONICAL")
        decision = evaluate_spec(spec, active_impl_count=0, total_impl_count=3)
        assert decision.should_retire is False
        assert "CANONICAL" in decision.reason

    def test_rejects_when_active_impls_remain(self):
        spec = Spec(spec_id="spec-001", name="TEST", source="LLM_GENERATED")
        decision = evaluate_spec(spec, active_impl_count=2, total_impl_count=5)
        assert decision.should_retire is False
        assert "2 active implementations remain" in decision.reason

    def test_rejects_when_no_implementations(self):
        spec = Spec(spec_id="spec-001", name="TEST", source="LLM_GENERATED")
        decision = evaluate_spec(spec, active_impl_count=0, total_impl_count=0)
        assert decision.should_retire is False
        assert "No implementations" in decision.reason


class TestCanReactivate:
    def test_eligible_for_reactivation(self):
        config = _default_config()
        ok, reason = can_reactivate(
            reactivation_count=0,
            days_since_retirement=45,
            can_reactivate_flag=True,
            config=config,
        )
        assert ok is True
        assert "Eligible" in reason

    def test_rejects_non_reactivatable(self):
        config = _default_config()
        ok, reason = can_reactivate(
            reactivation_count=0,
            days_since_retirement=45,
            can_reactivate_flag=False,
            config=config,
        )
        assert ok is False
        assert "non-reactivatable" in reason

    def test_rejects_too_many_attempts(self):
        config = _default_config()
        ok, reason = can_reactivate(
            reactivation_count=3,
            days_since_retirement=45,
            can_reactivate_flag=True,
            config=config,
        )
        assert ok is False
        assert "Maximum" in reason

    def test_rejects_cooling_off_period(self):
        config = _default_config()
        ok, reason = can_reactivate(
            reactivation_count=0,
            days_since_retirement=10,
            can_reactivate_flag=True,
            config=config,
        )
        assert ok is False
        assert "Cooling off" in reason


class TestApplyBatchLimits:
    def _make_decision(self, impl_id: str) -> RetirementDecision:
        return RetirementDecision(
            should_retire=True,
            reason="Test",
            impl_id=impl_id,
            spec_id="spec-001",
        )

    def test_respects_absolute_limit(self):
        config = RetirementConfig(max_retirements_per_run=3)
        candidates = [self._make_decision(f"impl-{i}") for i in range(5)]
        approved, skipped = apply_batch_limits(candidates, total_active=1000, config=config)
        assert len(approved) == 3
        assert len(skipped) == 2

    def test_respects_percentage_limit(self):
        config = RetirementConfig(
            max_retirements_per_run=50,
            max_retirement_percentage=10.0,
        )
        candidates = [self._make_decision(f"impl-{i}") for i in range(10)]
        # 10% of 20 active = 2
        approved, skipped = apply_batch_limits(candidates, total_active=20, config=config)
        assert len(approved) == 2
        assert len(skipped) == 8

    def test_skips_non_retire_candidates(self):
        config = _default_config()
        candidates = [
            RetirementDecision(should_retire=False, reason="Skip", impl_id="impl-1"),
            self._make_decision("impl-2"),
        ]
        approved, skipped = apply_batch_limits(candidates, total_active=100, config=config)
        assert len(approved) == 1
        assert approved[0].impl_id == "impl-2"

    def test_allows_at_least_one(self):
        config = RetirementConfig(
            max_retirements_per_run=50,
            max_retirement_percentage=1.0,
        )
        candidates = [self._make_decision("impl-1")]
        # 1% of 5 = 0, but we allow at least 1
        approved, skipped = apply_batch_limits(candidates, total_active=5, config=config)
        assert len(approved) == 1
