"""Tests for the universal evolution pattern interfaces."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from services.shared.evolution import (
    Evolvable,
    EvolutionMetadata,
    ImplStatus,
    SpecStatus,
    _extract_id,
)


class FakeEvolvable(Evolvable[dict, dict]):
    """Test implementation of Evolvable."""

    def __init__(self):
        self.specs = [
            {"id": "spec-1", "name": "momentum", "avg_sharpe": 1.5},
            {"id": "spec-2", "name": "mean_reversion", "avg_sharpe": 1.2},
        ]
        self.impls = {
            "spec-1": [
                {"impl_id": "impl-1", "parameters": {"period": 14}},
            ],
            "spec-2": [
                {"impl_id": "impl-2", "parameters": {"window": 20}},
            ],
        }
        self.perfs = {
            "impl-1": {"sharpe": 1.8, "win_rate": 0.62},
            "impl-2": {"sharpe": 1.3, "win_rate": 0.55},
        }
        self.deprecated = set()

    async def get_top_specs(self, limit=10, **filters):
        return self.specs[:limit]

    async def create_spec(self, spec):
        self.specs.append(spec)
        return spec.get("id", "new-spec")

    async def deprecate_spec(self, spec_id, reason):
        self.deprecated.add(spec_id)
        return True

    async def get_implementations(self, spec_id, status=None):
        return self.impls.get(spec_id, [])

    async def create_implementation(self, spec_id, parameters):
        impl = {"impl_id": f"impl-{len(self.impls) + 1}", "parameters": parameters}
        self.impls.setdefault(spec_id, []).append(impl)
        return impl["impl_id"]

    async def update_implementation_status(self, impl_id, status):
        return True

    async def get_performance(self, impl_id):
        return self.perfs.get(impl_id, {})


@pytest.fixture
def evolvable():
    return FakeEvolvable()


class TestSpecStatus:
    def test_values(self):
        assert SpecStatus.DRAFT.value == "draft"
        assert SpecStatus.ACTIVE.value == "active"
        assert SpecStatus.DEPRECATED.value == "deprecated"


class TestImplStatus:
    def test_values(self):
        assert ImplStatus.CANDIDATE.value == "candidate"
        assert ImplStatus.VALIDATED.value == "validated"
        assert ImplStatus.DEPLOYED.value == "deployed"
        assert ImplStatus.RETIRED.value == "retired"


class TestEvolutionMetadata:
    def test_defaults(self):
        meta = EvolutionMetadata()
        assert meta.version == 1
        assert meta.parent_id is None
        assert meta.source == "manual"
        assert meta.generation == 0
        assert meta.tags == []

    def test_custom(self):
        meta = EvolutionMetadata(
            version=2,
            parent_id="spec-1",
            source="llm_generated",
            generation=3,
            tags=["experimental"],
        )
        assert meta.version == 2
        assert meta.source == "llm_generated"


class TestEvolvable:
    @pytest.mark.asyncio
    async def test_get_top_specs(self, evolvable):
        specs = await evolvable.get_top_specs(limit=1)
        assert len(specs) == 1
        assert specs[0]["name"] == "momentum"

    @pytest.mark.asyncio
    async def test_create_spec(self, evolvable):
        spec_id = await evolvable.create_spec({"id": "spec-3", "name": "breakout"})
        assert spec_id == "spec-3"
        assert len(evolvable.specs) == 3

    @pytest.mark.asyncio
    async def test_deprecate_spec(self, evolvable):
        result = await evolvable.deprecate_spec("spec-1", "underperforming")
        assert result is True
        assert "spec-1" in evolvable.deprecated

    @pytest.mark.asyncio
    async def test_get_implementations(self, evolvable):
        impls = await evolvable.get_implementations("spec-1")
        assert len(impls) == 1
        assert impls[0]["impl_id"] == "impl-1"

    @pytest.mark.asyncio
    async def test_create_implementation(self, evolvable):
        impl_id = await evolvable.create_implementation("spec-1", {"period": 21})
        assert impl_id is not None
        assert len(await evolvable.get_implementations("spec-1")) == 2

    @pytest.mark.asyncio
    async def test_get_performance(self, evolvable):
        perf = await evolvable.get_performance("impl-1")
        assert perf["sharpe"] == 1.8
        assert perf["win_rate"] == 0.62

    @pytest.mark.asyncio
    async def test_get_few_shot_examples(self, evolvable):
        examples = await evolvable.get_few_shot_examples(limit=2)
        assert len(examples) == 2
        assert examples[0]["spec"]["name"] == "momentum"
        assert examples[0]["best_implementation"]["impl_id"] == "impl-1"
        assert examples[0]["performance"]["sharpe"] == 1.8


class TestExtractId:
    def test_dict_with_id(self):
        assert _extract_id({"id": "abc"}) == "abc"

    def test_dict_with_spec_id(self):
        assert _extract_id({"spec_id": "abc"}) == "abc"

    def test_dict_with_impl_id(self):
        assert _extract_id({"impl_id": "abc"}) == "abc"

    def test_dict_without_id(self):
        assert _extract_id({"name": "foo"}) is None

    def test_none(self):
        assert _extract_id(None) is None
