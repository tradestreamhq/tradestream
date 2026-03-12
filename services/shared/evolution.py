"""Universal Evolution Pattern for TradeStream subsystems.

Every subsystem follows the same lifecycle:

    Specs -> Implementations -> Execution -> Performance -> Evolution
    (and back to Specs)

This module defines the abstract interfaces that each subsystem implements
to participate in the evolution loop. The pattern enables:

- Consistent versioning across subsystems
- GA/LLM-driven optimization using top performers as few-shot examples
- Automated deprecation of underperformers
- Standardized migration between spec versions

Reference implementation: Strategy Derivation (services/strategy_mcp).

Example:
    class StrategyEvolvable(Evolvable[StrategySpec, StrategyImpl]):
        async def get_top_specs(self, limit=10):
            return await self._db.get_top_specs(limit=limit)

        async def create_spec(self, spec):
            return await self._db.create_spec(spec)

        async def get_implementations(self, spec_id):
            return await self._db.get_implementations(spec_id)

        async def get_performance(self, impl_id):
            return await self._db.get_performance(impl_id)

        async def deprecate(self, spec_id, reason):
            return await self._db.deprecate(spec_id, reason)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar


class SpecStatus(Enum):
    """Lifecycle status for a spec."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ImplStatus(Enum):
    """Lifecycle status for an implementation."""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    RETIRED = "retired"


@dataclass
class EvolutionMetadata:
    """Metadata tracking the evolution history of a spec or implementation."""

    version: int = 1
    parent_id: str | None = None
    source: str = "manual"  # "manual", "llm_generated", "ga_optimized"
    generation: int = 0
    tags: list[str] = field(default_factory=list)


# Type variables for specs and implementations
Spec = TypeVar("Spec")
Impl = TypeVar("Impl")


class Evolvable(ABC, Generic[Spec, Impl]):
    """Interface for subsystems that follow the universal evolution pattern.

    Each subsystem has:
    - Specs: templates defining WHAT is possible (e.g., strategy types)
    - Implementations: specific instances with tuned parameters
    - Performance metrics for measuring what works
    - Evolution logic for improving over time

    Subsystems implementing this interface can be driven by the same
    GA/LLM optimization pipeline.
    """

    # --- Spec Layer ---

    @abstractmethod
    async def get_top_specs(
        self, limit: int = 10, **filters: Any
    ) -> list[Spec]:
        """Get top-performing specs ranked by aggregate performance."""

    @abstractmethod
    async def create_spec(self, spec: Spec) -> str:
        """Create a new spec. Returns the spec ID."""

    @abstractmethod
    async def deprecate_spec(self, spec_id: str, reason: str) -> bool:
        """Mark a spec as deprecated."""

    # --- Implementation Layer ---

    @abstractmethod
    async def get_implementations(
        self, spec_id: str, status: ImplStatus | None = None
    ) -> list[Impl]:
        """Get implementations for a spec, optionally filtered by status."""

    @abstractmethod
    async def create_implementation(
        self, spec_id: str, parameters: dict[str, Any]
    ) -> str:
        """Create a new implementation of a spec. Returns the impl ID."""

    @abstractmethod
    async def update_implementation_status(
        self, impl_id: str, status: ImplStatus
    ) -> bool:
        """Transition an implementation to a new lifecycle status."""

    # --- Performance Layer ---

    @abstractmethod
    async def get_performance(
        self, impl_id: str
    ) -> dict[str, Any]:
        """Get performance metrics for an implementation."""

    # --- Evolution Layer ---

    async def get_few_shot_examples(
        self, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Get top performers formatted as few-shot examples for LLM generation.

        Default implementation fetches top specs with their best implementations
        and performance data. Override for subsystem-specific formatting.
        """
        top_specs = await self.get_top_specs(limit=limit)
        examples = []
        for spec in top_specs:
            spec_id = _extract_id(spec)
            if spec_id is None:
                continue
            impls = await self.get_implementations(spec_id)
            best_impl = impls[0] if impls else None
            perf = None
            if best_impl is not None:
                impl_id = _extract_id(best_impl)
                if impl_id is not None:
                    perf = await self.get_performance(impl_id)
            examples.append(
                {
                    "spec": spec,
                    "best_implementation": best_impl,
                    "performance": perf,
                }
            )
        return examples


def _extract_id(obj: Any) -> str | None:
    """Extract an ID from a spec or implementation object."""
    if isinstance(obj, dict):
        return obj.get("id") or obj.get("spec_id") or obj.get("impl_id")
    return getattr(obj, "id", None) or getattr(obj, "spec_id", None)
