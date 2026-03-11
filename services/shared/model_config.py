"""Centralized LLM model configuration for all agent services.

Model names are read from environment variables with sensible defaults.
All agents should import from this module instead of hardcoding model names.
"""

import os

# OpenRouter API base URL
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)

# Primary model for complex reasoning tasks (strategy proposal, orchestration)
MODEL_PRIMARY = os.environ.get("LLM_MODEL_PRIMARY", "anthropic/claude-sonnet-4-6")

# Lightweight model for high-volume tasks (signal generation, opportunity scoring)
MODEL_LIGHTWEIGHT = os.environ.get(
    "LLM_MODEL_LIGHTWEIGHT", "anthropic/claude-haiku-4-5"
)
