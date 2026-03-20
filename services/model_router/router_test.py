"""Tests for ModelRouter: routing logic, fallback chains, and circuit breakers."""

import asyncio

import pytest

from services.model_router.router import (
    AllModelsFailedError,
    ModelCircuitBreaker,
    ModelRouter,
    ModelSelection,
    RetryConfig,
)


class TestModelSelection:
    def test_signal_generator_uses_flash(self):
        router = ModelRouter()
        sel = router.select_model("signal-generator")
        assert sel.model_id == "google/gemini-3.0-flash"

    def test_opportunity_scorer_uses_pro(self):
        router = ModelRouter()
        sel = router.select_model("opportunity-scorer")
        assert sel.model_id == "google/gemini-3.0-pro"

    def test_portfolio_advisor_default(self):
        router = ModelRouter()
        sel = router.select_model("portfolio-advisor")
        assert sel.model_id == "openai/gpt-5.2"

    def test_portfolio_advisor_high_opportunity(self):
        router = ModelRouter()
        sel = router.select_model("portfolio-advisor", opportunity_score=75)
        assert sel.model_id == "anthropic/claude-sonnet-4.5"

    def test_portfolio_advisor_critical_opportunity(self):
        router = ModelRouter()
        sel = router.select_model("portfolio-advisor", opportunity_score=90)
        assert sel.model_id == "anthropic/claude-opus-4.5"

    def test_portfolio_advisor_below_threshold(self):
        router = ModelRouter()
        sel = router.select_model("portfolio-advisor", opportunity_score=50)
        assert sel.model_id == "openai/gpt-5.2"

    def test_report_generator_uses_flash(self):
        router = ModelRouter()
        sel = router.select_model("report-generator")
        assert sel.model_id == "google/gemini-3.0-flash"

    def test_learning_uses_sonnet(self):
        router = ModelRouter()
        sel = router.select_model("learning")
        assert sel.model_id == "anthropic/claude-sonnet-4.5"

    def test_janitor_uses_pro(self):
        router = ModelRouter()
        sel = router.select_model("janitor")
        assert sel.model_id == "google/gemini-3.0-pro"

    def test_unknown_agent_defaults_to_flash(self):
        router = ModelRouter()
        sel = router.select_model("unknown-agent")
        assert sel.model_id == "google/gemini-3.0-flash"

    def test_budget_cap_downgrades_model(self):
        router = ModelRouter()
        router.set_max_model("anthropic/claude-sonnet-4.5")
        sel = router.select_model("portfolio-advisor", opportunity_score=90)
        # Should be capped at Sonnet instead of Opus
        assert sel.model_id == "anthropic/claude-sonnet-4.5"

    def test_budget_cap_no_effect_on_cheaper_model(self):
        router = ModelRouter()
        router.set_max_model("anthropic/claude-sonnet-4.5")
        sel = router.select_model("signal-generator")
        assert sel.model_id == "google/gemini-3.0-flash"


class TestFallbackChain:
    def test_fallback_from_flash_to_pro(self):
        router = ModelRouter()
        fb = router.get_fallback("google/gemini-3.0-flash")
        assert fb == "google/gemini-3.0-pro"

    def test_fallback_from_pro_to_gpt(self):
        router = ModelRouter()
        fb = router.get_fallback("google/gemini-3.0-pro")
        assert fb == "openai/gpt-5.2"

    def test_fallback_from_gpt_to_sonnet(self):
        router = ModelRouter()
        fb = router.get_fallback("openai/gpt-5.2")
        assert fb == "anthropic/claude-sonnet-4.5"

    def test_fallback_from_sonnet_is_none(self):
        router = ModelRouter()
        fb = router.get_fallback("anthropic/claude-sonnet-4.5")
        assert fb is None

    def test_fallback_unknown_model_uses_last(self):
        router = ModelRouter()
        fb = router.get_fallback("anthropic/claude-opus-4.5")
        assert fb == "anthropic/claude-sonnet-4.5"


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = ModelCircuitBreaker("test-model")
        assert cb.state == "closed"
        assert cb.allow_request()

    def test_opens_after_threshold(self):
        cb = ModelCircuitBreaker("test-model", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert not cb.allow_request()

    def test_transitions_to_half_open(self):
        cb = ModelCircuitBreaker(
            "test-model", failure_threshold=2, recovery_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        import time

        time.sleep(0.02)
        assert cb.state == "half_open"
        assert cb.allow_request()

    def test_half_open_success_closes(self):
        cb = ModelCircuitBreaker(
            "test-model", failure_threshold=2, recovery_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        import time

        time.sleep(0.02)
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_failure_reopens(self):
        cb = ModelCircuitBreaker(
            "test-model", failure_threshold=2, recovery_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        import time

        time.sleep(0.02)
        cb.allow_request()  # triggers half_open
        cb.record_failure()
        assert cb.state == "open"

    def test_reset(self):
        cb = ModelCircuitBreaker("test-model", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        cb.reset()
        assert cb.state == "closed"
        assert cb.allow_request()

    def test_to_dict(self):
        cb = ModelCircuitBreaker("test-model")
        d = cb.to_dict()
        assert d["model_id"] == "test-model"
        assert d["state"] == "closed"
        assert d["failure_count"] == 0


class TestCallWithFallback:
    @pytest.mark.asyncio
    async def test_successful_call(self):
        router = ModelRouter(retry_config=RetryConfig(max_retries=0))

        async def mock_call(model_id, prompt):
            return {"response": f"from {model_id}"}

        result, model_used = await router.call_with_fallback(
            "signal-generator", mock_call, "test prompt"
        )
        assert model_used == "google/gemini-3.0-flash"
        assert result["response"] == "from google/gemini-3.0-flash"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        router = ModelRouter(retry_config=RetryConfig(max_retries=0))
        call_count = 0

        async def failing_flash(model_id, prompt):
            nonlocal call_count
            call_count += 1
            if model_id == "google/gemini-3.0-flash":
                raise Exception("Flash is down")
            return {"response": f"from {model_id}"}

        result, model_used = await router.call_with_fallback(
            "signal-generator", failing_flash, "test"
        )
        assert model_used == "google/gemini-3.0-pro"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_before_fallback(self):
        router = ModelRouter(
            retry_config=RetryConfig(max_retries=2, initial_delay_ms=1)
        )
        attempts = []

        async def flaky_call(model_id, prompt):
            attempts.append(model_id)
            if len(attempts) <= 2:
                raise Exception("temporary failure")
            return {"response": "ok"}

        result, model_used = await router.call_with_fallback(
            "signal-generator", flaky_call, "test"
        )
        # Should have retried 3 times on flash (initial + 2 retries) then succeeded
        assert model_used == "google/gemini-3.0-flash"
        assert len(attempts) == 3

    @pytest.mark.asyncio
    async def test_all_models_fail_raises(self):
        router = ModelRouter(retry_config=RetryConfig(max_retries=0))

        async def always_fail(model_id, prompt):
            raise Exception(f"{model_id} failed")

        with pytest.raises(AllModelsFailedError):
            await router.call_with_fallback("signal-generator", always_fail, "test")

    @pytest.mark.asyncio
    async def test_circuit_breaker_skips_model(self):
        router = ModelRouter(retry_config=RetryConfig(max_retries=0))
        # Manually trip the circuit breaker for flash
        cb = router._get_circuit_breaker("google/gemini-3.0-flash")
        for _ in range(5):
            cb.record_failure()

        async def mock_call(model_id, prompt):
            return {"response": f"from {model_id}"}

        result, model_used = await router.call_with_fallback(
            "signal-generator", mock_call, "test"
        )
        # Should skip flash (circuit open) and use pro
        assert model_used == "google/gemini-3.0-pro"
