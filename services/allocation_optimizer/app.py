"""
Allocation Optimizer REST API — RMM Level 2.

Provides mean-variance portfolio optimization for multi-strategy capital allocation.
"""

import logging
from typing import List

import numpy as np
from fastapi import FastAPI

from services.allocation_optimizer.models import (
    EfficientFrontierResponse,
    OptimizationRequest,
    OptimizationResult,
)
from services.allocation_optimizer.optimizer import (
    compute_efficient_frontier,
    optimize_max_sharpe,
    optimize_min_variance,
    optimize_target_return,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    success_response,
    validation_error,
    server_error,
)

logger = logging.getLogger(__name__)


def _to_returns_matrix(strategies) -> tuple:
    """Convert strategy returns to numpy matrix and id list."""
    strategy_ids = [s.strategy_id for s in strategies]
    # Truncate to shortest series so all strategies align
    min_len = min(len(s.returns) for s in strategies)
    returns_matrix = np.array([s.returns[:min_len] for s in strategies]).T
    return strategy_ids, returns_matrix


def create_app() -> FastAPI:
    """Create the Allocation Optimizer FastAPI application."""
    app = FastAPI(
        title="Allocation Optimizer API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/allocation",
    )

    app.include_router(create_health_router("allocation-optimizer"))

    @app.post("/optimize", tags=["Optimization"])
    async def optimize(req: OptimizationRequest):
        """Compute optimal allocation weights for the given strategies."""
        # Validate strategy returns have enough data
        min_periods = min(len(s.returns) for s in req.strategies)
        if min_periods < 2:
            return validation_error("Each strategy must have at least 2 return periods")

        if req.objective == "target_return" and req.target_return is None:
            return validation_error(
                "target_return is required when objective is 'target_return'"
            )

        if req.min_weight > req.max_weight:
            return validation_error("min_weight must be <= max_weight")

        n = len(req.strategies)
        if req.min_weight * n > 1.0:
            return validation_error(
                f"min_weight {req.min_weight} x {n} strategies > 1.0; no feasible allocation"
            )

        try:
            strategy_ids, returns_matrix = _to_returns_matrix(req.strategies)

            if req.objective == "max_sharpe":
                result = optimize_max_sharpe(
                    strategy_ids,
                    returns_matrix,
                    req.risk_free_rate,
                    req.min_weight,
                    req.max_weight,
                )
            elif req.objective == "min_variance":
                result = optimize_min_variance(
                    strategy_ids,
                    returns_matrix,
                    req.risk_free_rate,
                    req.min_weight,
                    req.max_weight,
                )
            else:
                result = optimize_target_return(
                    strategy_ids,
                    returns_matrix,
                    req.target_return,
                    req.risk_free_rate,
                    req.min_weight,
                    req.max_weight,
                )

            return success_response(result.model_dump(), "optimization_result")

        except Exception as e:
            logger.exception("Optimization failed")
            return server_error(f"Optimization failed: {e}")

    @app.post("/efficient-frontier", tags=["Optimization"])
    async def efficient_frontier(req: OptimizationRequest):
        """Compute the efficient frontier for the given strategies."""
        min_periods = min(len(s.returns) for s in req.strategies)
        if min_periods < 2:
            return validation_error("Each strategy must have at least 2 return periods")

        if req.min_weight > req.max_weight:
            return validation_error("min_weight must be <= max_weight")

        n = len(req.strategies)
        if req.min_weight * n > 1.0:
            return validation_error(
                f"min_weight {req.min_weight} x {n} strategies > 1.0; no feasible allocation"
            )

        try:
            strategy_ids, returns_matrix = _to_returns_matrix(req.strategies)
            frontier = compute_efficient_frontier(
                strategy_ids,
                returns_matrix,
                req.risk_free_rate,
                req.min_weight,
                req.max_weight,
            )
            return success_response(frontier.model_dump(), "efficient_frontier")

        except Exception as e:
            logger.exception("Efficient frontier computation failed")
            return server_error(f"Efficient frontier computation failed: {e}")

    return app
