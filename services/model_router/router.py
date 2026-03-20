"""Model Router — selects optimal model based on agent type, opportunity score, and budget.

Implements the routing strategy from specs/model-routing/SPEC.md:
  - Signal Generator → Gemini Flash (high volume, routine)
  - Opportunity Scorer → Gemini Pro (multi-factor reasoning)
  - Portfolio Advisor → Dynamic escalation based on opportunity score
  - Report Generator → Gemini Flash (formatting)
  - Learning Agent → Sonnet (complex generation)
  - Janitor Agent → Gemini Pro (nuanced evaluation)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from services.model_router.model_registry import MODELS, ModelProfile, get_model

logger = logging.getLogger(__name__)


@dataclass
class ModelSelection:
    """Result of model selection."""

    model_id: str
    reason: str
    estimated_cost_per_1k_tokens: float

    @property
    def profile(self) -> Optional[ModelProfile]:
        return get_model(self.model_id)


@dataclass
class AgentRoutingConfig:
    """Routing configuration for a single agent type."""

    default_model: str
    max_tokens: int = 2000
    temperature: float = 0.3
    escalation_rules: list[dict] = field(default_factory=list)


# Default routing table per spec
DEFAULT_ROUTING: dict[str, AgentRoutingConfig] = {
    "signal-generator": AgentRoutingConfig(
        default_model="google/gemini-3.0-flash",
        max_tokens=2000,
        temperature=0.3,
    ),
    "opportunity-scorer": AgentRoutingConfig(
        default_model="google/gemini-3.0-pro",
        max_tokens=1500,
        temperature=0.2,
    ),
    "portfolio-advisor": AgentRoutingConfig(
        default_model="openai/gpt-5.2",
        max_tokens=1500,
        temperature=0.1,
        escalation_rules=[
            {"score_threshold": 70, "model": "anthropic/claude-sonnet-4.5"},
            {"score_threshold": 85, "model": "anthropic/claude-opus-4.5"},
        ],
    ),
    "report-generator": AgentRoutingConfig(
        default_model="google/gemini-3.0-flash",
        max_tokens=1000,
        temperature=0.5,
    ),
    "learning": AgentRoutingConfig(
        default_model="anthropic/claude-sonnet-4.5",
        max_tokens=4000,
        temperature=0.7,
    ),
    "janitor": AgentRoutingConfig(
        default_model="google/gemini-3.0-pro",
        max_tokens=2000,
        temperature=0.2,
    ),
}

# Fallback chain ordered cheapest-first per spec
DEFAULT_FALLBACK_CHAIN = [
    "google/gemini-3.0-flash",
    "google/gemini-3.0-pro",
    "openai/gpt-5.2",
    "anthropic/claude-sonnet-4.5",
]


@dataclass
class RetryConfig:
    max_retries: int = 2
    initial_delay_ms: int = 500
    max_delay_ms: int = 5000
    exponential_backoff: bool = True


class ModelRouterError(Exception):
    """Base error for model routing."""


class AllModelsFailedError(ModelRouterError):
    """Raised when all models in the fallback chain have failed."""


class CircuitOpenError(ModelRouterError):
    """Raised when the circuit breaker for a model is open."""


class ModelCircuitBreaker:
    """Per-model circuit breaker that disables a model after repeated failures.

    States: CLOSED (normal) → OPEN (disabled) → HALF_OPEN (testing recovery)
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        model_id: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.model_id = model_id
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        self._evaluate_state()
        return self._state

    def _evaluate_state(self):
        if self._state == self.STATE_OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.STATE_HALF_OPEN
                self._half_open_calls = 0
                logger.info("Model circuit breaker %s: OPEN → HALF_OPEN", self.model_id)

    def allow_request(self) -> bool:
        self._evaluate_state()
        if self._state == self.STATE_CLOSED:
            return True
        if self._state == self.STATE_HALF_OPEN:
            if self._half_open_calls < 1:
                self._half_open_calls += 1
                return True
            return False
        return False

    def record_success(self):
        if self._state == self.STATE_HALF_OPEN:
            self._state = self.STATE_CLOSED
            logger.info("Model circuit breaker %s: HALF_OPEN → CLOSED", self.model_id)
        self._failure_count = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == self.STATE_HALF_OPEN:
            self._state = self.STATE_OPEN
            logger.warning("Model circuit breaker %s: HALF_OPEN → OPEN", self.model_id)
        elif self._state == self.STATE_CLOSED and self._failure_count >= self.failure_threshold:
            self._state = self.STATE_OPEN
            logger.warning(
                "Model circuit breaker %s: CLOSED → OPEN after %d failures",
                self.model_id,
                self._failure_count,
            )

    def reset(self):
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._half_open_calls = 0

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
        }


class ModelRouter:
    """Routes LLM requests to the optimal model based on task type, cost, and quality.

    Features:
      - Agent-type-based model selection with opportunity-score escalation
      - Fallback chain (cheapest-first) when primary model fails
      - Per-model circuit breakers
      - Retry with exponential backoff before falling back
      - Budget-aware routing (accepts max_model cap from BudgetEnforcer)
    """

    def __init__(
        self,
        routing_table: Optional[dict[str, AgentRoutingConfig]] = None,
        fallback_chain: Optional[list[str]] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.routing_table = routing_table or dict(DEFAULT_ROUTING)
        self.fallback_chain = fallback_chain or list(DEFAULT_FALLBACK_CHAIN)
        self.retry_config = retry_config or RetryConfig()
        self._circuit_breakers: dict[str, ModelCircuitBreaker] = {}
        self._max_model: Optional[str] = None  # budget cap

    def set_max_model(self, model_id: Optional[str]):
        """Set the maximum model tier allowed (for budget degradation)."""
        self._max_model = model_id

    def _get_circuit_breaker(self, model_id: str) -> ModelCircuitBreaker:
        if model_id not in self._circuit_breakers:
            self._circuit_breakers[model_id] = ModelCircuitBreaker(model_id)
        return self._circuit_breakers[model_id]

    def select_model(
        self,
        agent_type: str,
        opportunity_score: Optional[float] = None,
    ) -> ModelSelection:
        """Select the optimal model for the given agent type and context."""
        config = self.routing_table.get(agent_type)
        if not config:
            # Unknown agent type — use cheapest
            return ModelSelection(
                model_id="google/gemini-3.0-flash",
                reason="Default fallback for unknown agent type",
                estimated_cost_per_1k_tokens=0.0003,
            )

        model_id = config.default_model
        reason = f"Default for {agent_type}"

        # Apply escalation rules (sorted descending by threshold)
        if opportunity_score is not None and config.escalation_rules:
            for rule in sorted(
                config.escalation_rules,
                key=lambda r: r["score_threshold"],
                reverse=True,
            ):
                if opportunity_score >= rule["score_threshold"]:
                    model_id = rule["model"]
                    reason = (
                        f"Escalated for {agent_type} "
                        f"(opportunity_score={opportunity_score} "
                        f">= {rule['score_threshold']})"
                    )
                    break

        # Apply budget cap
        if self._max_model:
            model_id = self._apply_budget_cap(model_id)

        profile = get_model(model_id)
        cost = profile.cost_per_1k_tokens if profile else 0.0

        return ModelSelection(
            model_id=model_id,
            reason=reason,
            estimated_cost_per_1k_tokens=cost,
        )

    def _apply_budget_cap(self, model_id: str) -> str:
        """Downgrade model if it exceeds the budget cap."""
        if not self._max_model:
            return model_id

        cap_profile = get_model(self._max_model)
        model_profile = get_model(model_id)
        if not cap_profile or not model_profile:
            return model_id

        if model_profile.cost_per_1k_tokens > cap_profile.cost_per_1k_tokens:
            logger.info(
                "Budget cap: downgrading %s to %s", model_id, self._max_model
            )
            return self._max_model
        return model_id

    def get_fallback(self, failed_model: str) -> Optional[str]:
        """Get next model in the fallback chain (cheapest-first order).

        If the failed model is in the chain, return the next one.
        If not in the chain, return the last (most capable) fallback.
        """
        try:
            idx = self.fallback_chain.index(failed_model)
            if idx + 1 < len(self.fallback_chain):
                return self.fallback_chain[idx + 1]
        except ValueError:
            pass
        # If model not in chain or at end, return the most capable fallback
        if self.fallback_chain and failed_model != self.fallback_chain[-1]:
            return self.fallback_chain[-1]
        return None

    async def call_with_fallback(
        self,
        agent_type: str,
        call_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        opportunity_score: Optional[float] = None,
        **kwargs: Any,
    ) -> tuple[Any, str]:
        """Select model, call it with retry + fallback, return (result, model_used).

        Raises AllModelsFailedError if every model in the chain fails.
        """
        selection = self.select_model(agent_type, opportunity_score)
        return await self._call_with_retry_and_fallback(
            selection.model_id, call_fn, *args, **kwargs
        )

    async def _call_with_retry_and_fallback(
        self,
        model_id: str,
        call_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        _tried: Optional[set] = None,
        **kwargs: Any,
    ) -> tuple[Any, str]:
        """Internal: retry on the current model, then fall back."""
        if _tried is None:
            _tried = set()
        _tried.add(model_id)

        cb = self._get_circuit_breaker(model_id)
        if not cb.allow_request():
            logger.warning("Circuit open for %s, skipping to fallback", model_id)
            return await self._try_fallback(model_id, call_fn, *args, _tried=_tried, **kwargs)

        last_error: Optional[Exception] = None
        delay_ms = self.retry_config.initial_delay_ms

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                result = await call_fn(model_id, *args, **kwargs)
                cb.record_success()
                return result, model_id
            except Exception as exc:
                last_error = exc
                cb.record_failure()
                logger.warning(
                    "Model %s attempt %d failed: %s", model_id, attempt + 1, exc
                )
                if attempt < self.retry_config.max_retries:
                    await asyncio.sleep(delay_ms / 1000)
                    if self.retry_config.exponential_backoff:
                        delay_ms = min(delay_ms * 2, self.retry_config.max_delay_ms)

        # Retries exhausted — try fallback
        return await self._try_fallback(
            model_id, call_fn, *args, _tried=_tried, _last_error=last_error, **kwargs
        )

    async def _try_fallback(
        self,
        failed_model: str,
        call_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        _tried: Optional[set] = None,
        _last_error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> tuple[Any, str]:
        """Try the next model in the fallback chain that hasn't been tried."""
        if _tried is None:
            _tried = set()

        # Walk the fallback chain for an untried model
        for candidate in self.fallback_chain:
            if candidate not in _tried:
                cb = self._get_circuit_breaker(candidate)
                if cb.allow_request():
                    logger.info("Falling back from %s to %s", failed_model, candidate)
                    return await self._call_with_retry_and_fallback(
                        candidate, call_fn, *args, _tried=_tried, **kwargs
                    )
                _tried.add(candidate)

        raise AllModelsFailedError(
            f"All models failed. Last error: {_last_error}"
        )

    def get_routing_config(self, agent_type: str) -> Optional[AgentRoutingConfig]:
        """Get the routing config for an agent type."""
        return self.routing_table.get(agent_type)

    def get_circuit_breaker_states(self) -> list[dict]:
        """Return state of all circuit breakers for monitoring."""
        return [cb.to_dict() for cb in self._circuit_breakers.values()]
