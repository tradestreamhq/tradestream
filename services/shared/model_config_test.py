"""Tests for centralized model configuration."""

import os
from unittest import mock


class TestModelConfig:
    """Tests for model_config module."""

    def test_default_primary_model(self):
        """Primary model defaults to claude-sonnet-4-6."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in ("LLM_MODEL_PRIMARY", "LLM_MODEL_LIGHTWEIGHT", "OPENROUTER_BASE_URL")
        }
        with mock.patch.dict(os.environ, env, clear=True):
            # Re-import to pick up fresh env
            import importlib
            from services.shared import model_config
            importlib.reload(model_config)
            assert model_config.MODEL_PRIMARY == "anthropic/claude-sonnet-4-6"

    def test_default_lightweight_model(self):
        """Lightweight model defaults to claude-haiku-4-5."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in ("LLM_MODEL_PRIMARY", "LLM_MODEL_LIGHTWEIGHT", "OPENROUTER_BASE_URL")
        }
        with mock.patch.dict(os.environ, env, clear=True):
            import importlib
            from services.shared import model_config
            importlib.reload(model_config)
            assert model_config.MODEL_LIGHTWEIGHT == "anthropic/claude-haiku-4-5"

    def test_default_openrouter_base_url(self):
        """OpenRouter base URL has correct default."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in ("LLM_MODEL_PRIMARY", "LLM_MODEL_LIGHTWEIGHT", "OPENROUTER_BASE_URL")
        }
        with mock.patch.dict(os.environ, env, clear=True):
            import importlib
            from services.shared import model_config
            importlib.reload(model_config)
            assert model_config.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"

    def test_env_override_primary(self):
        """Primary model can be overridden via environment variable."""
        with mock.patch.dict(os.environ, {"LLM_MODEL_PRIMARY": "openai/gpt-4o"}):
            import importlib
            from services.shared import model_config
            importlib.reload(model_config)
            assert model_config.MODEL_PRIMARY == "openai/gpt-4o"

    def test_env_override_lightweight(self):
        """Lightweight model can be overridden via environment variable."""
        with mock.patch.dict(os.environ, {"LLM_MODEL_LIGHTWEIGHT": "openai/gpt-4o-mini"}):
            import importlib
            from services.shared import model_config
            importlib.reload(model_config)
            assert model_config.MODEL_LIGHTWEIGHT == "openai/gpt-4o-mini"

    def test_env_override_base_url(self):
        """OpenRouter base URL can be overridden via environment variable."""
        with mock.patch.dict(os.environ, {"OPENROUTER_BASE_URL": "http://localhost:8080"}):
            import importlib
            from services.shared import model_config
            importlib.reload(model_config)
            assert model_config.OPENROUTER_BASE_URL == "http://localhost:8080"
