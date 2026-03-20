"""Tests for BudgetEnforcer."""

from services.model_router.budget_enforcer import BudgetEnforcer, DegradationTier


class TestBudgetEnforcer:
    def test_no_tier_below_threshold(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        result = enforcer.check(current_cost=2000)
        assert result is None

    def test_alert_at_80_pct(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        tier = enforcer.check(current_cost=2400)  # 80%
        assert tier is not None
        assert tier.action == "alert"

    def test_reduce_premium_at_90_pct(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        tier = enforcer.check(current_cost=2700)  # 90%
        assert tier is not None
        assert tier.action == "reduce_premium"

    def test_reduce_frequency_at_95_pct(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        tier = enforcer.check(current_cost=2850)  # 95%
        assert tier is not None
        assert tier.action == "reduce_frequency"

    def test_emergency_mode_at_100_pct(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        tier = enforcer.check(current_cost=3000)  # 100%
        assert tier is not None
        assert tier.action == "emergency_mode"

    def test_routing_constraints_alert(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.check(current_cost=2400)
        constraints = enforcer.get_routing_constraints()
        assert constraints["max_model"] is None
        assert constraints["force_model"] is None

    def test_routing_constraints_reduce_premium(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.check(current_cost=2700)
        constraints = enforcer.get_routing_constraints()
        assert constraints["max_model"] == "anthropic/claude-sonnet-4.5"
        assert constraints["force_model"] is None

    def test_routing_constraints_emergency(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.check(current_cost=3000)
        constraints = enforcer.get_routing_constraints()
        assert constraints["force_model"] == "google/gemini-3.0-flash"

    def test_alert_callback_invoked(self):
        alerts = []
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.set_alert_callback(lambda msg, sev, details: alerts.append((msg, sev, details)))
        enforcer.check(current_cost=2700)
        assert len(alerts) == 1
        assert alerts[0][1] == "warning"

    def test_critical_severity_at_95(self):
        alerts = []
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.set_alert_callback(lambda msg, sev, details: alerts.append((msg, sev, details)))
        enforcer.check(current_cost=2850)
        assert len(alerts) == 1
        assert alerts[0][1] == "critical"

    def test_tier_does_not_re_alert(self):
        alerts = []
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.set_alert_callback(lambda msg, sev, details: alerts.append(1))
        enforcer.check(current_cost=2400)
        enforcer.check(current_cost=2400)
        # Only one alert — tier didn't change
        assert len(alerts) == 1

    def test_to_dict(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        enforcer.check(current_cost=2700)
        d = enforcer.to_dict()
        assert d["monthly_limit_usd"] == 3000
        assert d["current_tier"] == "reduce_premium"
        assert d["tier_threshold_pct"] == 90

    def test_zero_limit(self):
        enforcer = BudgetEnforcer(monthly_limit_usd=0)
        result = enforcer.check(current_cost=100)
        assert result is None
