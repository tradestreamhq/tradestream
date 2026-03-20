"""Model Registry — defines available LLM models with capabilities, costs, and latency profiles.

All models are accessed via OpenRouter. Pricing is per 1M tokens (2026 rates).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModelCapability(str, Enum):
    """Capabilities a model may support."""

    TOOL_USE = "tool_use"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    STRUCTURED_OUTPUT = "structured_output"
    FAST_INFERENCE = "fast_inference"


@dataclass(frozen=True)
class ModelPricing:
    """Cost per 1M tokens."""

    input_per_million: float
    output_per_million: float

    @property
    def input_per_token(self) -> float:
        return self.input_per_million / 1_000_000

    @property
    def output_per_token(self) -> float:
        return self.output_per_million / 1_000_000


@dataclass(frozen=True)
class ModelProfile:
    """Full profile for a registered model."""

    model_id: str
    display_name: str
    provider: str
    pricing: ModelPricing
    tau2_score: float  # Tool-use benchmark score (0-100)
    avg_latency_ms: int  # Typical first-token latency
    max_tokens: int
    capabilities: tuple[ModelCapability, ...] = field(default_factory=tuple)
    deprecated: bool = False

    @property
    def cost_per_1k_tokens(self) -> float:
        """Blended cost estimate assuming 60/40 input/output split."""
        return self.pricing.input_per_token * 600 + self.pricing.output_per_token * 400


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

MODELS: dict[str, ModelProfile] = {}


def _register(profile: ModelProfile) -> ModelProfile:
    MODELS[profile.model_id] = profile
    return profile


GEMINI_FLASH = _register(
    ModelProfile(
        model_id="google/gemini-3.0-flash",
        display_name="Gemini 3.0 Flash",
        provider="google",
        pricing=ModelPricing(input_per_million=0.10, output_per_million=0.40),
        tau2_score=80.0,
        avg_latency_ms=200,
        max_tokens=8192,
        capabilities=(
            ModelCapability.TOOL_USE,
            ModelCapability.FAST_INFERENCE,
            ModelCapability.STRUCTURED_OUTPUT,
        ),
    )
)

GEMINI_PRO = _register(
    ModelProfile(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro",
        provider="google",
        pricing=ModelPricing(input_per_million=1.25, output_per_million=5.00),
        tau2_score=85.4,
        avg_latency_ms=500,
        max_tokens=8192,
        capabilities=(
            ModelCapability.TOOL_USE,
            ModelCapability.REASONING,
            ModelCapability.MULTIMODAL,
            ModelCapability.STRUCTURED_OUTPUT,
        ),
    )
)

GPT_5_2 = _register(
    ModelProfile(
        model_id="openai/gpt-5.2",
        display_name="GPT-5.2 Thinking",
        provider="openai",
        pricing=ModelPricing(input_per_million=1.75, output_per_million=14.00),
        tau2_score=94.5,
        avg_latency_ms=800,
        max_tokens=8192,
        capabilities=(
            ModelCapability.TOOL_USE,
            ModelCapability.REASONING,
            ModelCapability.CHAIN_OF_THOUGHT,
            ModelCapability.STRUCTURED_OUTPUT,
        ),
    )
)

CLAUDE_SONNET = _register(
    ModelProfile(
        model_id="anthropic/claude-sonnet-4.5",
        display_name="Claude Sonnet 4.5",
        provider="anthropic",
        pricing=ModelPricing(input_per_million=3.00, output_per_million=15.00),
        tau2_score=90.0,
        avg_latency_ms=600,
        max_tokens=8192,
        capabilities=(
            ModelCapability.TOOL_USE,
            ModelCapability.REASONING,
            ModelCapability.CHAIN_OF_THOUGHT,
            ModelCapability.STRUCTURED_OUTPUT,
        ),
    )
)

CLAUDE_OPUS = _register(
    ModelProfile(
        model_id="anthropic/claude-opus-4.5",
        display_name="Claude Opus 4.5",
        provider="anthropic",
        pricing=ModelPricing(input_per_million=15.00, output_per_million=75.00),
        tau2_score=98.2,
        avg_latency_ms=1200,
        max_tokens=8192,
        capabilities=(
            ModelCapability.TOOL_USE,
            ModelCapability.REASONING,
            ModelCapability.CHAIN_OF_THOUGHT,
            ModelCapability.MULTIMODAL,
            ModelCapability.STRUCTURED_OUTPUT,
        ),
    )
)


def get_model(model_id: str) -> Optional[ModelProfile]:
    """Look up a model by its OpenRouter ID."""
    return MODELS.get(model_id)


def list_models(*, include_deprecated: bool = False) -> list[ModelProfile]:
    """Return all registered models, sorted cheapest-first."""
    models = list(MODELS.values())
    if not include_deprecated:
        models = [m for m in models if not m.deprecated]
    return sorted(models, key=lambda m: m.cost_per_1k_tokens)
