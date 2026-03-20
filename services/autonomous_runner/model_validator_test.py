"""Tests for model validation and fallback."""

import pytest

from services.autonomous_runner.model_validator import (
    KNOWN_TOOL_CALLING_MODELS,
    ModelConfig,
    ModelValidation,
    ModelValidator,
)


class TestModelValidator:
    def test_known_model_is_valid(self):
        validator = ModelValidator()
        result = validator.validate_model("anthropic/claude-sonnet-4-20250514")
        assert result.valid is True
        assert result.has_tool_calling is True

    def test_known_model_cached(self):
        validator = ModelValidator()
        r1 = validator.validate_model("openai/gpt-4o")
        r2 = validator.validate_model("openai/gpt-4o")
        assert r1 is r2  # Same object from cache

    def test_unknown_model_without_client_is_invalid(self):
        validator = ModelValidator()
        result = validator.validate_model("unknown/model-xyz")
        assert result.valid is False
        assert result.has_tool_calling is False
        assert len(result.warnings) > 0

    def test_unknown_model_with_api_valid(self):
        class FakeClient:
            def get_model_info(self, model_id):
                return {"capabilities": ["tool_calling", "structured_output"]}

        validator = ModelValidator(openrouter_client=FakeClient())
        result = validator.validate_model("custom/my-model")
        assert result.valid is True
        assert result.has_tool_calling is True
        assert result.has_structured_output is True

    def test_unknown_model_with_api_no_tool_calling(self):
        class FakeClient:
            def get_model_info(self, model_id):
                return {"capabilities": ["chat"]}

        validator = ModelValidator(openrouter_client=FakeClient())
        result = validator.validate_model("custom/chat-only")
        assert result.valid is False
        assert result.has_tool_calling is False

    def test_unknown_model_with_api_dict_capabilities(self):
        class FakeClient:
            def get_model_info(self, model_id):
                return {
                    "capabilities": {
                        "tool_calling": True,
                        "structured_output": False,
                    }
                }

        validator = ModelValidator(openrouter_client=FakeClient())
        result = validator.validate_model("custom/dict-caps")
        assert result.valid is True
        assert result.has_tool_calling is True
        assert result.has_structured_output is False

    def test_api_error_returns_invalid(self):
        class FakeClient:
            def get_model_info(self, model_id):
                raise ConnectionError("API down")

        validator = ModelValidator(openrouter_client=FakeClient())
        result = validator.validate_model("custom/erroring")
        assert result.valid is False
        assert "API down" in result.error

    def test_get_valid_model_known(self):
        validator = ModelValidator()
        model = validator.get_valid_model("openai/gpt-4o")
        assert model == "openai/gpt-4o"
        assert validator.fallback_count == 0

    def test_get_valid_model_fallback(self):
        config = ModelConfig(fallback_model="anthropic/claude-sonnet-4-20250514")
        validator = ModelValidator(config=config)
        model = validator.get_valid_model("unknown/bad-model")
        assert model == "anthropic/claude-sonnet-4-20250514"
        assert validator.fallback_count == 1

    def test_get_valid_model_fallback_increments(self):
        validator = ModelValidator()
        validator.get_valid_model("bad/1")
        validator.get_valid_model("bad/2")
        assert validator.fallback_count == 2

    def test_get_status(self):
        validator = ModelValidator()
        validator.validate_model("openai/gpt-4o")
        status = validator.get_status()
        assert status["cached_validations"] == 1
        assert status["fallback_count"] == 0

    def test_all_known_models_are_valid(self):
        validator = ModelValidator()
        for model_id in KNOWN_TOOL_CALLING_MODELS:
            result = validator.validate_model(model_id)
            assert result.valid is True, f"Known model {model_id} should be valid"
