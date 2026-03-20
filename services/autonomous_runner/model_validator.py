"""Model validation and fallback for signal generation.

Validates that the configured LLM model supports tool calling.
Falls back to a known-good model if the preferred model lacks capabilities.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# Models known to support tool calling (no validation needed)
KNOWN_TOOL_CALLING_MODELS = frozenset(
    {
        "anthropic/claude-sonnet-4-20250514",
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-haiku-4-5",
        "anthropic/claude-haiku-4-5-20251001",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-2.0-flash",
        "google/gemini-2.5-pro-preview-06-05",
    }
)


@dataclass
class ModelValidation:
    """Result of model validation."""

    valid: bool
    model_id: str = ""
    has_tool_calling: bool = False
    has_structured_output: bool = False
    warnings: list = field(default_factory=list)
    error: str = ""


@dataclass
class ModelConfig:
    """Configuration for model validation and fallback."""

    required_capabilities: list = field(default_factory=lambda: ["tool_calling"])
    recommended_capabilities: list = field(
        default_factory=lambda: ["structured_output", "json_mode"]
    )
    recommended_models: list = field(
        default_factory=lambda: [
            "anthropic/claude-sonnet-4-20250514",
            "openai/gpt-4o",
            "google/gemini-2.0-flash",
        ]
    )
    fallback_model: str = "anthropic/claude-sonnet-4-20250514"
    min_context_window: int = 8000


class ModelValidator:
    """Validates model capabilities and provides fallback.

    Checks if a model supports tool calling (required for signal generation).
    Uses a known-models allowlist for fast validation and falls back to
    querying the OpenRouter API for unknown models.
    """

    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        openrouter_client=None,
    ):
        self.config = config or ModelConfig()
        self.client = openrouter_client
        self._validation_cache: dict[str, ModelValidation] = {}
        self._fallback_count = 0

    def validate_model(self, model_id: str) -> ModelValidation:
        """Check if model supports required capabilities.

        Uses cached results when available.
        """
        if model_id in self._validation_cache:
            return self._validation_cache[model_id]

        # Fast path: known models
        if model_id in KNOWN_TOOL_CALLING_MODELS:
            result = ModelValidation(
                valid=True,
                model_id=model_id,
                has_tool_calling=True,
                has_structured_output=True,
            )
            self._validation_cache[model_id] = result
            return result

        # Try API validation if client available
        if self.client is not None:
            result = self._validate_via_api(model_id)
            self._validation_cache[model_id] = result
            return result

        # Unknown model without API client — conservative: mark invalid
        result = ModelValidation(
            valid=False,
            model_id=model_id,
            has_tool_calling=False,
            warnings=[
                f"Model {model_id} not in known-good list and no API client to validate"
            ],
        )
        self._validation_cache[model_id] = result
        return result

    def _validate_via_api(self, model_id: str) -> ModelValidation:
        """Validate model capabilities via OpenRouter API."""
        try:
            model_info = self.client.get_model_info(model_id)
            capabilities = model_info.get("capabilities", [])

            # Handle both list and dict capability formats
            if isinstance(capabilities, dict):
                has_tool_calling = capabilities.get("tool_calling", False)
                has_structured = capabilities.get("structured_output", False)
            else:
                has_tool_calling = "tool_calling" in capabilities
                has_structured = "structured_output" in capabilities

            warnings = []
            if not has_tool_calling:
                warnings.append(f"Model {model_id} lacks tool_calling capability")
            if not has_structured:
                warnings.append(
                    f"Model {model_id} lacks structured_output (recommended)"
                )

            return ModelValidation(
                valid=has_tool_calling,
                model_id=model_id,
                has_tool_calling=has_tool_calling,
                has_structured_output=has_structured,
                warnings=warnings,
            )
        except Exception as e:
            return ModelValidation(
                valid=False,
                model_id=model_id,
                error=str(e),
            )

    def get_valid_model(self, preferred_model: str) -> str:
        """Get a valid model, falling back if necessary.

        Returns the preferred model if it supports tool calling,
        otherwise returns the fallback model.
        """
        validation = self.validate_model(preferred_model)

        if validation.valid:
            if validation.warnings:
                for w in validation.warnings:
                    logger.info("Model warning: %s", w)
            return preferred_model

        logger.warning(
            "Model %s doesn't support tool calling, falling back to %s",
            preferred_model,
            self.config.fallback_model,
        )
        self._fallback_count += 1

        return self.config.fallback_model

    @property
    def fallback_count(self) -> int:
        """Number of times fallback was triggered."""
        return self._fallback_count

    def get_status(self) -> dict:
        """Return validator status for monitoring."""
        return {
            "fallback_count": self._fallback_count,
            "cached_validations": len(self._validation_cache),
            "fallback_model": self.config.fallback_model,
        }
