"""Tests for model_registry module."""

from services.model_router.model_registry import (
    GEMINI_FLASH,
    GEMINI_PRO,
    GPT_5_2,
    CLAUDE_SONNET,
    CLAUDE_OPUS,
    MODELS,
    ModelCapability,
    get_model,
    list_models,
)


class TestModelRegistry:
    def test_all_models_registered(self):
        assert len(MODELS) == 5
        assert "google/gemini-3.0-flash" in MODELS
        assert "google/gemini-3.0-pro" in MODELS
        assert "openai/gpt-5.2" in MODELS
        assert "anthropic/claude-sonnet-4.5" in MODELS
        assert "anthropic/claude-opus-4.5" in MODELS

    def test_get_model_found(self):
        m = get_model("google/gemini-3.0-flash")
        assert m is not None
        assert m.model_id == "google/gemini-3.0-flash"
        assert m.provider == "google"

    def test_get_model_not_found(self):
        assert get_model("nonexistent/model") is None

    def test_list_models_sorted_by_cost(self):
        models = list_models()
        costs = [m.cost_per_1k_tokens for m in models]
        assert costs == sorted(costs)

    def test_gemini_flash_is_cheapest(self):
        models = list_models()
        assert models[0].model_id == "google/gemini-3.0-flash"

    def test_claude_opus_is_most_expensive(self):
        models = list_models()
        assert models[-1].model_id == "anthropic/claude-opus-4.5"

    def test_pricing_per_token(self):
        flash = get_model("google/gemini-3.0-flash")
        assert flash.pricing.input_per_token == 0.10 / 1_000_000
        assert flash.pricing.output_per_token == 0.40 / 1_000_000

    def test_tau2_scores_match_spec(self):
        assert GEMINI_FLASH.tau2_score == 80.0
        assert GEMINI_PRO.tau2_score == 85.4
        assert GPT_5_2.tau2_score == 94.5
        assert CLAUDE_SONNET.tau2_score == 90.0
        assert CLAUDE_OPUS.tau2_score == 98.2

    def test_capabilities(self):
        assert ModelCapability.FAST_INFERENCE in GEMINI_FLASH.capabilities
        assert ModelCapability.CHAIN_OF_THOUGHT in GPT_5_2.capabilities
        assert ModelCapability.REASONING in CLAUDE_OPUS.capabilities

    def test_cost_per_1k_tokens(self):
        # Blended 60/40 input/output split
        flash = get_model("google/gemini-3.0-flash")
        expected = (
            flash.pricing.input_per_token * 600 + flash.pricing.output_per_token * 400
        )
        assert abs(flash.cost_per_1k_tokens - expected) < 1e-10
