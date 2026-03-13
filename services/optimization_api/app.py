"""
Strategy Parameter Optimization REST API.

POST /api/optimization/run — submit optimization job
GET  /api/optimization/{job_id} — check optimization status and results
GET  /api/optimization/jobs — list optimization jobs
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.optimization_api.optimization_service import (
    CategoricalParamSpace,
    JobStatus,
    NumericParamSpace,
    Objective,
    OptimizationResult,
    SearchMethod,
    TrialResult,
    generate_param_grid,
    get_objective_value,
    rank_results,
    sample_random_params,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class NumericParam(BaseModel):
    name: str
    min: float
    max: float
    step: float


class CategoricalParam(BaseModel):
    name: str
    options: List[Any]


class ParameterSpace(BaseModel):
    numeric: List[NumericParam] = Field(default_factory=list)
    categorical: List[CategoricalParam] = Field(default_factory=list)


class DateRange(BaseModel):
    start: str = Field(..., description="Start date (ISO format)")
    end: str = Field(..., description="End date (ISO format)")


class OptimizationRunRequest(BaseModel):
    strategy_id: str = Field(..., description="Strategy name or ID to optimize")
    parameter_space: ParameterSpace
    objective: str = Field(
        "sharpe", description="Objective metric: sharpe, return, or drawdown"
    )
    date_range: DateRange
    search_method: str = Field("grid", description="Search method: grid or random")
    max_combinations: int = Field(
        1000, ge=1, le=50000, description="Max combinations for random search"
    )
    instrument: str = Field("BTC/USD", description="Trading instrument symbol")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool, backtest_fn=None) -> FastAPI:
    """Create the Optimization API FastAPI application.

    Args:
        db_pool: asyncpg connection pool.
        backtest_fn: Optional callable(strategy_name, parameters, instrument,
                     start_date, end_date) -> dict of metrics. Used for
                     dependency injection in tests.
    """
    app = FastAPI(
        title="Strategy Parameter Optimization API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/optimization",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("optimization-api", check_deps))

    router = APIRouter(tags=["Optimization"])

    # In-memory job store for running jobs (DB is source of truth once complete)
    _running_jobs: Dict[str, OptimizationResult] = {}

    async def _run_backtest(
        strategy_name: str,
        parameters: Dict[str, Any],
        instrument: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Run a single backtest and return metrics dict."""
        if backtest_fn:
            return await backtest_fn(
                strategy_name, parameters, instrument, start_date, end_date
            )
        # Default: query the backtesting service via gRPC
        # For now, return empty metrics (integration point)
        raise NotImplementedError(
            "gRPC backtesting integration not yet wired — provide backtest_fn"
        )

    async def _execute_optimization(
        job_id: str,
        request: OptimizationRunRequest,
    ):
        """Execute optimization in the background."""
        job = _running_jobs[job_id]
        job.status = JobStatus.RUNNING

        try:
            objective = Objective(request.objective)

            # Parse parameter spaces
            numeric = [
                NumericParamSpace(
                    name=p.name, min=p.min, max=p.max, step=p.step
                )
                for p in request.parameter_space.numeric
            ]
            categorical = [
                CategoricalParamSpace(name=p.name, options=p.options)
                for p in request.parameter_space.categorical
            ]

            # Generate parameter combinations
            search = SearchMethod(request.search_method)
            if search == SearchMethod.GRID:
                combos = generate_param_grid(numeric, categorical)
            else:
                combos = sample_random_params(
                    numeric, categorical, request.max_combinations
                )

            job.total_combinations = len(combos)
            trials: List[TrialResult] = []

            for i, params in enumerate(combos):
                try:
                    metrics = await _run_backtest(
                        request.strategy_id,
                        params,
                        request.instrument,
                        request.date_range.start,
                        request.date_range.end,
                    )
                    trial = TrialResult(
                        parameters=params,
                        objective_value=0.0,  # set after ranking
                        sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
                        cumulative_return=metrics.get("cumulative_return", 0.0),
                        max_drawdown=metrics.get("max_drawdown", 0.0),
                        number_of_trades=metrics.get("number_of_trades", 0),
                        win_rate=metrics.get("win_rate", 0.0),
                        profit_factor=metrics.get("profit_factor", 0.0),
                        sortino_ratio=metrics.get("sortino_ratio", 0.0),
                        strategy_score=metrics.get("strategy_score", 0.0),
                    )
                    trial.objective_value = get_objective_value(trial, objective)
                    trials.append(trial)
                except Exception as e:
                    logger.warning("Trial %d failed for params %s: %s", i, params, e)

                job.completed_combinations = i + 1

            # Rank results
            ranked = rank_results(trials, objective)
            job.ranked_results = ranked
            if ranked:
                job.best_parameters = ranked[0].parameters
                job.best_objective_value = ranked[0].objective_value
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc).isoformat()

            # Persist to database
            await _save_optimization_result(job)

        except Exception as e:
            logger.exception("Optimization job %s failed", job_id)
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc).isoformat()
            await _save_optimization_result(job)

    async def _save_optimization_result(result: OptimizationResult):
        """Persist optimization result to PostgreSQL."""
        try:
            top_results = [
                {
                    "parameters": t.parameters,
                    "objective_value": t.objective_value,
                    "sharpe_ratio": t.sharpe_ratio,
                    "cumulative_return": t.cumulative_return,
                    "max_drawdown": t.max_drawdown,
                    "number_of_trades": t.number_of_trades,
                    "win_rate": t.win_rate,
                    "profit_factor": t.profit_factor,
                    "sortino_ratio": t.sortino_ratio,
                    "strategy_score": t.strategy_score,
                }
                for t in result.ranked_results[:100]  # store top 100
            ]
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO optimization_jobs
                        (id, strategy_id, status, search_method, objective,
                         total_combinations, completed_combinations,
                         best_parameters, best_objective_value,
                         ranked_results, error, created_at, completed_at)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6, $7,
                            $8::jsonb, $9, $10::jsonb, $11, $12::timestamptz, $13::timestamptz)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        completed_combinations = EXCLUDED.completed_combinations,
                        best_parameters = EXCLUDED.best_parameters,
                        best_objective_value = EXCLUDED.best_objective_value,
                        ranked_results = EXCLUDED.ranked_results,
                        error = EXCLUDED.error,
                        completed_at = EXCLUDED.completed_at
                    """,
                    result.job_id,
                    result.strategy_id,
                    result.status.value,
                    result.search_method.value,
                    result.objective.value,
                    result.total_combinations,
                    result.completed_combinations,
                    json.dumps(result.best_parameters) if result.best_parameters else None,
                    result.best_objective_value,
                    json.dumps(top_results),
                    result.error,
                    result.created_at,
                    result.completed_at,
                )
        except Exception as e:
            logger.error("Failed to persist optimization result: %s", e)

    @router.post("/run", status_code=202)
    async def submit_optimization(body: OptimizationRunRequest):
        # Validate objective
        try:
            Objective(body.objective)
        except ValueError:
            return validation_error(
                f"Invalid objective '{body.objective}'. Must be one of: sharpe, return, drawdown"
            )

        # Validate search method
        try:
            SearchMethod(body.search_method)
        except ValueError:
            return validation_error(
                f"Invalid search_method '{body.search_method}'. Must be one of: grid, random"
            )

        if not body.parameter_space.numeric and not body.parameter_space.categorical:
            return validation_error("parameter_space must define at least one parameter")

        # Validate numeric params
        for p in body.parameter_space.numeric:
            if p.min > p.max:
                return validation_error(f"Parameter '{p.name}': min ({p.min}) > max ({p.max})")
            if p.step <= 0:
                return validation_error(f"Parameter '{p.name}': step must be positive")

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        job = OptimizationResult(
            job_id=job_id,
            strategy_id=body.strategy_id,
            status=JobStatus.PENDING,
            search_method=SearchMethod(body.search_method),
            objective=Objective(body.objective),
            total_combinations=0,
            completed_combinations=0,
            created_at=now,
        )
        _running_jobs[job_id] = job

        # Fire and forget
        asyncio.create_task(_execute_optimization(job_id, body))

        return success_response(
            {
                "job_id": job_id,
                "strategy_id": body.strategy_id,
                "status": job.status.value,
                "search_method": body.search_method,
                "objective": body.objective,
                "created_at": now,
            },
            "optimization_job",
            resource_id=job_id,
            status_code=202,
        )

    @router.get("/{job_id}")
    async def get_optimization_status(job_id: str):
        # Check in-memory first (for running jobs)
        if job_id in _running_jobs:
            job = _running_jobs[job_id]
            data = {
                "job_id": job.job_id,
                "strategy_id": job.strategy_id,
                "status": job.status.value,
                "search_method": job.search_method.value,
                "objective": job.objective.value,
                "total_combinations": job.total_combinations,
                "completed_combinations": job.completed_combinations,
                "best_parameters": job.best_parameters,
                "best_objective_value": job.best_objective_value,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "error": job.error,
            }
            if job.status == JobStatus.COMPLETED:
                data["ranked_results"] = [
                    {
                        "parameters": t.parameters,
                        "objective_value": t.objective_value,
                        "sharpe_ratio": t.sharpe_ratio,
                        "cumulative_return": t.cumulative_return,
                        "max_drawdown": t.max_drawdown,
                        "number_of_trades": t.number_of_trades,
                        "win_rate": t.win_rate,
                        "profit_factor": t.profit_factor,
                        "sortino_ratio": t.sortino_ratio,
                        "strategy_score": t.strategy_score,
                    }
                    for t in job.ranked_results[:50]
                ]
            return success_response(data, "optimization_job", resource_id=job_id)

        # Check database
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, strategy_id, status, search_method, objective,
                       total_combinations, completed_combinations,
                       best_parameters, best_objective_value,
                       ranked_results, error, created_at, completed_at
                FROM optimization_jobs WHERE id = $1::uuid
                """,
                job_id,
            )
        if not row:
            return not_found("Optimization job", job_id)

        data = {
            "job_id": str(row["id"]),
            "strategy_id": row["strategy_id"],
            "status": row["status"],
            "search_method": row["search_method"],
            "objective": row["objective"],
            "total_combinations": row["total_combinations"],
            "completed_combinations": row["completed_combinations"],
            "best_parameters": row["best_parameters"],
            "best_objective_value": row["best_objective_value"],
            "ranked_results": row["ranked_results"],
            "error": row["error"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }
        return success_response(data, "optimization_job", resource_id=str(row["id"]))

    @router.get("")
    async def list_optimization_jobs(
        pagination: PaginationParams = Depends(),
        strategy_id: Optional[str] = Query(None, description="Filter by strategy"),
        status: Optional[str] = Query(None, description="Filter by status"),
    ):
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if strategy_id:
            idx += 1
            conditions.append(f"strategy_id = ${idx}")
            params.append(strategy_id)

        if status:
            idx += 1
            conditions.append(f"status = ${idx}")
            params.append(status)

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, strategy_id, status, search_method, objective,
                   total_combinations, completed_combinations,
                   best_parameters, best_objective_value,
                   error, created_at, completed_at
            FROM optimization_jobs
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"""
            SELECT COUNT(*) FROM optimization_jobs WHERE {where}
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = []
        for row in rows:
            item = {
                "job_id": str(row["id"]),
                "strategy_id": row["strategy_id"],
                "status": row["status"],
                "search_method": row["search_method"],
                "objective": row["objective"],
                "total_combinations": row["total_combinations"],
                "completed_combinations": row["completed_combinations"],
                "best_parameters": row["best_parameters"],
                "best_objective_value": row["best_objective_value"],
                "error": row["error"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            }
            items.append(item)

        return collection_response(
            items,
            "optimization_job",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(router)
    return app
