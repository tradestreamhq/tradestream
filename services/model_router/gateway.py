"""Agent Gateway API — unified endpoint for routing LLM requests.

Provides a FastAPI service that:
  - Accepts task requests with agent type and context
  - Routes to the optimal model via ModelRouter
  - Tracks costs via CostTracker
  - Enforces budget via BudgetEnforcer
  - Exposes monitoring endpoints for circuit breakers, costs, and budget
"""

import logging
import os
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.model_router.ab_testing import ABTestManager
from services.model_router.budget_enforcer import BudgetEnforcer
from services.model_router.cost_tracker import CostTracker
from services.model_router.model_registry import MODELS, list_models
from services.model_router.router import ModelRouter

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Model Router Gateway",
    version="1.0.0",
    description=(
        "Unified gateway that routes LLM requests to the optimal model "
        "based on task type, cost, latency, and quality requirements."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core components
router = ModelRouter()
cost_tracker = CostTracker()
budget_enforcer = BudgetEnforcer(
    monthly_limit_usd=float(os.environ.get("MONTHLY_BUDGET_USD", "3000"))
)
ab_test_manager = ABTestManager()


# --- Request / Response models ---


class RouteRequest(BaseModel):
    """Request to route a task to the optimal model."""

    agent_type: str = Field(
        ..., description="Agent type (e.g. signal-generator, janitor)"
    )
    opportunity_score: Optional[float] = Field(
        None, description="Opportunity score for dynamic escalation (0-100)"
    )


class RouteResponse(BaseModel):
    """Model selection result."""

    model_id: str
    reason: str
    estimated_cost_per_1k_tokens: float
    max_tokens: int
    temperature: float


class UsageRequest(BaseModel):
    """Record model usage after a call completes."""

    agent_type: str
    model_id: str
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    success: bool = True
    retries: int = Field(0, ge=0)
    fallback_used: bool = False


class UsageResponse(BaseModel):
    cost_usd: float
    total_tokens: int


class CostSummaryResponse(BaseModel):
    total_cost_usd: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_retries: int
    fallback_count: int
    by_model: dict[str, float]
    by_agent: dict[str, float]


class BudgetStatusResponse(BaseModel):
    monthly_limit_usd: float
    current_cost_usd: float
    usage_pct: float
    current_tier: Optional[str]
    routing_constraints: dict


class ModelInfo(BaseModel):
    model_id: str
    display_name: str
    provider: str
    input_per_million: float
    output_per_million: float
    tau2_score: float
    avg_latency_ms: int


class CircuitBreakerStatus(BaseModel):
    model_id: str
    state: str
    failure_count: int
    failure_threshold: int


class CreateExperimentRequest(BaseModel):
    experiment_id: str
    agent_type: str
    primary_model: str
    challenger_model: str
    traffic_pct: float = Field(0.1, gt=0, le=1)
    max_runs: int = Field(100, gt=0)


class RecordExperimentResultRequest(BaseModel):
    experiment_id: str
    agent_type: str
    primary_model: str
    challenger_model: str
    primary_latency_ms: float = Field(..., ge=0)
    challenger_latency_ms: float = Field(..., ge=0)
    primary_tokens: int = Field(..., ge=0)
    challenger_tokens: int = Field(..., ge=0)


# --- Endpoints ---


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "model-router"}


@app.post("/route", response_model=RouteResponse)
async def route_request(req: RouteRequest):
    """Select the optimal model for a given agent type and context."""
    # Apply budget constraints
    current_cost = cost_tracker.get_monthly_cost()
    budget_enforcer.check(current_cost)
    constraints = budget_enforcer.get_routing_constraints()

    if constraints["force_model"]:
        router.set_max_model(None)
        from services.model_router.model_registry import get_model

        profile = get_model(constraints["force_model"])
        config = router.get_routing_config(req.agent_type)
        return RouteResponse(
            model_id=constraints["force_model"],
            reason=f"Emergency mode: forced to {constraints['force_model']}",
            estimated_cost_per_1k_tokens=profile.cost_per_1k_tokens if profile else 0,
            max_tokens=config.max_tokens if config else 2000,
            temperature=config.temperature if config else 0.3,
        )

    router.set_max_model(constraints.get("max_model"))
    selection = router.select_model(req.agent_type, req.opportunity_score)
    config = router.get_routing_config(req.agent_type)

    return RouteResponse(
        model_id=selection.model_id,
        reason=selection.reason,
        estimated_cost_per_1k_tokens=selection.estimated_cost_per_1k_tokens,
        max_tokens=config.max_tokens if config else 2000,
        temperature=config.temperature if config else 0.3,
    )


@app.post("/usage", response_model=UsageResponse)
async def record_usage(req: UsageRequest):
    """Record model usage after a call completes."""
    record = cost_tracker.record_usage(
        agent_type=req.agent_type,
        model_id=req.model_id,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        success=req.success,
        retries=req.retries,
        fallback_used=req.fallback_used,
    )
    # Check budget after recording
    current_cost = cost_tracker.get_monthly_cost()
    budget_enforcer.check(current_cost)

    return UsageResponse(cost_usd=record.cost_usd, total_tokens=record.total_tokens)


@app.get("/costs", response_model=CostSummaryResponse)
async def get_costs():
    """Get current month cost summary."""
    summary = cost_tracker.get_monthly_summary()
    return CostSummaryResponse(
        total_cost_usd=summary.total_cost_usd,
        total_requests=summary.total_requests,
        successful_requests=summary.successful_requests,
        failed_requests=summary.failed_requests,
        total_retries=summary.total_retries,
        fallback_count=summary.fallback_count,
        by_model=dict(summary.by_model),
        by_agent=dict(summary.by_agent),
    )


@app.get("/budget", response_model=BudgetStatusResponse)
async def get_budget_status():
    """Get current budget status and active degradation tier."""
    current_cost = cost_tracker.get_monthly_cost()
    budget_enforcer.check(current_cost)
    constraints = budget_enforcer.get_routing_constraints()
    usage_pct = (
        (current_cost / budget_enforcer.monthly_limit_usd * 100)
        if budget_enforcer.monthly_limit_usd > 0
        else 0
    )

    return BudgetStatusResponse(
        monthly_limit_usd=budget_enforcer.monthly_limit_usd,
        current_cost_usd=current_cost,
        usage_pct=round(usage_pct, 1),
        current_tier=(
            budget_enforcer.current_tier.action
            if budget_enforcer.current_tier
            else None
        ),
        routing_constraints=constraints,
    )


@app.get("/models", response_model=list[ModelInfo])
async def list_available_models():
    """List all available models with pricing and capabilities."""
    return [
        ModelInfo(
            model_id=m.model_id,
            display_name=m.display_name,
            provider=m.provider,
            input_per_million=m.pricing.input_per_million,
            output_per_million=m.pricing.output_per_million,
            tau2_score=m.tau2_score,
            avg_latency_ms=m.avg_latency_ms,
        )
        for m in list_models()
    ]


@app.get("/circuit-breakers", response_model=list[CircuitBreakerStatus])
async def get_circuit_breakers():
    """Get circuit breaker status for all models."""
    states = router.get_circuit_breaker_states()
    return [CircuitBreakerStatus(**s) for s in states]


@app.post("/experiments", tags=["A/B Testing"])
async def create_experiment(req: CreateExperimentRequest):
    """Create a new A/B model experiment."""
    try:
        exp = ab_test_manager.create_experiment(
            experiment_id=req.experiment_id,
            agent_type=req.agent_type,
            primary_model=req.primary_model,
            challenger_model=req.challenger_model,
            traffic_pct=req.traffic_pct,
            max_runs=req.max_runs,
        )
        return exp.summary()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/experiments", tags=["A/B Testing"])
async def list_experiments():
    """List all A/B experiments."""
    return ab_test_manager.list_experiments()


@app.get("/experiments/{experiment_id}", tags=["A/B Testing"])
async def get_experiment(experiment_id: str):
    """Get details for a specific experiment."""
    exp = ab_test_manager.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp.summary()


@app.post("/experiments/{experiment_id}/stop", tags=["A/B Testing"])
async def stop_experiment(experiment_id: str):
    """Stop an active experiment."""
    if not ab_test_manager.stop_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"status": "stopped", "experiment_id": experiment_id}


@app.post("/experiments/{experiment_id}/results", tags=["A/B Testing"])
async def record_experiment_result(
    experiment_id: str, req: RecordExperimentResultRequest
):
    """Record a result from an A/B experiment run."""
    result = ab_test_manager.record_result(
        experiment_id=experiment_id,
        agent_type=req.agent_type,
        primary_model=req.primary_model,
        challenger_model=req.challenger_model,
        primary_latency_ms=req.primary_latency_ms,
        challenger_latency_ms=req.challenger_latency_ms,
        primary_tokens=req.primary_tokens,
        challenger_tokens=req.challenger_tokens,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found or inactive")
    exp = ab_test_manager.get_experiment(experiment_id)
    return {"recorded": True, "runs": exp.runs if exp else 0}


def main():
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8081"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
