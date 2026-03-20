"""Tests for CostTracker."""

from services.model_router.cost_tracker import CostTracker


class TestCostTracker:
    def test_record_usage_calculates_cost(self):
        tracker = CostTracker()
        record = tracker.record_usage(
            agent_type="signal-generator",
            model_id="google/gemini-3.0-flash",
            input_tokens=1000,
            output_tokens=500,
        )
        # Flash: $0.10/1M input, $0.40/1M output
        expected_cost = 1000 * 0.10 / 1_000_000 + 500 * 0.40 / 1_000_000
        assert abs(record.cost_usd - expected_cost) < 1e-10
        assert record.total_tokens == 1500

    def test_record_usage_unknown_model(self):
        tracker = CostTracker()
        record = tracker.record_usage(
            agent_type="test",
            model_id="unknown/model",
            input_tokens=100,
            output_tokens=50,
        )
        # Should use conservative estimate
        assert record.cost_usd > 0

    def test_monthly_cost(self):
        tracker = CostTracker()
        tracker.record_usage("signal-generator", "google/gemini-3.0-flash", 1000, 500)
        tracker.record_usage("janitor", "google/gemini-3.0-pro", 800, 400)
        cost = tracker.get_monthly_cost()
        assert cost > 0

    def test_monthly_summary_aggregation(self):
        tracker = CostTracker()
        tracker.record_usage("signal-generator", "google/gemini-3.0-flash", 1000, 500)
        tracker.record_usage("signal-generator", "google/gemini-3.0-flash", 1000, 500)
        tracker.record_usage("janitor", "google/gemini-3.0-pro", 800, 400, success=False)

        summary = tracker.get_monthly_summary()
        assert summary.total_requests == 3
        assert summary.successful_requests == 2
        assert summary.failed_requests == 1
        assert "google/gemini-3.0-flash" in summary.by_model
        assert "signal-generator" in summary.by_agent

    def test_cost_by_agent(self):
        tracker = CostTracker()
        tracker.record_usage("signal-generator", "google/gemini-3.0-flash", 1000, 500)
        tracker.record_usage("janitor", "google/gemini-3.0-pro", 800, 400)
        by_agent = tracker.get_cost_by_agent()
        assert "signal-generator" in by_agent
        assert "janitor" in by_agent

    def test_cost_by_model(self):
        tracker = CostTracker()
        tracker.record_usage("signal-generator", "google/gemini-3.0-flash", 1000, 500)
        tracker.record_usage("janitor", "google/gemini-3.0-pro", 800, 400)
        by_model = tracker.get_cost_by_model()
        assert "google/gemini-3.0-flash" in by_model
        assert "google/gemini-3.0-pro" in by_model

    def test_fallback_tracking(self):
        tracker = CostTracker()
        tracker.record_usage(
            "signal-generator", "google/gemini-3.0-pro", 1000, 500,
            retries=2, fallback_used=True,
        )
        summary = tracker.get_monthly_summary()
        assert summary.total_retries == 2
        assert summary.fallback_count == 1

    def test_clear(self):
        tracker = CostTracker()
        tracker.record_usage("test", "google/gemini-3.0-flash", 100, 50)
        tracker.clear()
        assert tracker.get_monthly_cost() == 0
