"""
Strategy Optimizer REST API.

Provides endpoints to run grid search optimization over the backtesting engine,
check optimization status, and retrieve ranked results.
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field

from services.backtesting.vectorbt_runner import VectorBTRunner
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware
from services.strategy_optimizer.grid_search import (
    GridSearchConfig,
    GridSearchOptimizer,
    GridSearchResult,
    ParameterRange,
)

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class ParameterRangeDTO(BaseModel):
    name: str = Field(..., description="Parameter name")
    min_value: float = Field(..., description="Minimum value")
    max_value: float = Field(..., description="Maximum value")
    step: float = Field(..., description="Step size")


class OptimizerRunRequest(BaseModel):
    strategy_name: str = Field(..., description="Strategy to optimize (e.g. SMA_RSI)")
    parameter_ranges: List[ParameterRangeDTO] = Field(
        ..., description="Parameter ranges for grid search"
    )
    instrument: str = Field(..., description="Trading instrument (e.g. BTC/USD)")
    start_date: str = Field(..., description="Backtest start date (ISO format)")
    end_date: str = Field(..., description="Backtest end date (ISO format)")
    top_n: int = Field(10, ge=1, le=100, description="Number of top results to return")


class OptimizationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- In-memory job store ---


class OptimizationJob:
    def __init__(self, job_id: str, request: OptimizerRunRequest, total: int):
        self.job_id = job_id
        self.request = request
        self.status = OptimizationStatus.PENDING
        self.total_combinations = total
        self.results: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None


class JobStore:
    def __init__(self):
        self._jobs: Dict[str, OptimizationJob] = {}
        self._lock = Lock()

    def create(self, request: OptimizerRunRequest, total: int) -> OptimizationJob:
        job_id = str(uuid.uuid4())
        job = OptimizationJob(job_id, request, total)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[OptimizationJob]:
        with self._lock:
            return self._jobs.get(job_id)


# --- Application Factory ---


def create_app(
    market_data_fn=None,
    runner: Optional[VectorBTRunner] = None,
) -> FastAPI:
    """Create the Strategy Optimizer FastAPI application.

    Args:
        market_data_fn: Async callable(instrument, start, end) -> pd.DataFrame.
                        If None, generates synthetic data for testing.
        runner: VectorBTRunner instance. If None, creates a default one.
    """
    app = FastAPI(
        title="Strategy Optimizer API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/optimizer",
    )
    fastapi_auth_middleware(app)
    app.include_router(create_health_router("strategy-optimizer"))

    store = JobStore()
    optimizer = GridSearchOptimizer(runner)
    executor = ThreadPoolExecutor(max_workers=2)

    def _run_optimization(job: OptimizationJob):
        """Execute optimization in background thread."""
        job.status = OptimizationStatus.RUNNING
        try:
            if market_data_fn:
                import asyncio

                loop = asyncio.new_event_loop()
                ohlcv = loop.run_until_complete(
                    market_data_fn(
                        job.request.instrument,
                        job.request.start_date,
                        job.request.end_date,
                    )
                )
                loop.close()
            else:
                ohlcv = _generate_synthetic_ohlcv(500)

            config = GridSearchConfig(
                strategy_name=job.request.strategy_name,
                parameter_ranges=[
                    ParameterRange(
                        name=pr.name,
                        min_value=pr.min_value,
                        max_value=pr.max_value,
                        step=pr.step,
                    )
                    for pr in job.request.parameter_ranges
                ],
                top_n=job.request.top_n,
            )

            results = optimizer.run(ohlcv, config)
            job.results = [
                {
                    "rank": r.rank,
                    "parameters": r.parameters,
                    "metrics": r.metrics,
                }
                for r in results
            ]
            job.status = OptimizationStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.error("Optimization %s failed: %s", job.job_id, e, exc_info=True)
            job.status = OptimizationStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)

    router = APIRouter(tags=["Optimizer"])

    @router.post("/run", status_code=202)
    async def run_optimizer(body: OptimizerRunRequest):
        """Submit a grid search optimization run."""
        # Validate parameter ranges
        for pr in body.parameter_ranges:
            if pr.min_value > pr.max_value:
                return validation_error(
                    f"Parameter '{pr.name}': min_value must be <= max_value"
                )
            if pr.step <= 0:
                return validation_error(f"Parameter '{pr.name}': step must be positive")

        ranges = [
            ParameterRange(
                name=pr.name,
                min_value=pr.min_value,
                max_value=pr.max_value,
                step=pr.step,
            )
            for pr in body.parameter_ranges
        ]
        config = GridSearchConfig(
            strategy_name=body.strategy_name,
            parameter_ranges=ranges,
            top_n=body.top_n,
        )

        job = store.create(body, config.total_combinations)
        executor.submit(_run_optimization, job)

        return success_response(
            data={
                "job_id": job.job_id,
                "strategy_name": body.strategy_name,
                "total_combinations": job.total_combinations,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
            },
            resource_type="optimization_job",
            resource_id=job.job_id,
            status_code=202,
        )

    @router.get("/{job_id}/status")
    async def get_status(job_id: str):
        """Get the status of an optimization run."""
        job = store.get(job_id)
        if not job:
            return not_found("OptimizationJob", job_id)

        data = {
            "job_id": job.job_id,
            "strategy_name": job.request.strategy_name,
            "status": job.status.value,
            "total_combinations": job.total_combinations,
            "created_at": job.created_at.isoformat(),
        }
        if job.completed_at:
            data["completed_at"] = job.completed_at.isoformat()
        if job.error:
            data["error"] = job.error
        if job.status == OptimizationStatus.COMPLETED:
            data["result_count"] = len(job.results)

        return success_response(data, "optimization_status", resource_id=job.job_id)

    @router.get("/{job_id}/results")
    async def get_results(
        job_id: str,
        top_n: int = Query(10, ge=1, le=100, description="Number of top results"),
    ):
        """Get results of a completed optimization run."""
        job = store.get(job_id)
        if not job:
            return not_found("OptimizationJob", job_id)

        if job.status == OptimizationStatus.PENDING:
            return success_response(
                {
                    "job_id": job.job_id,
                    "status": "PENDING",
                    "message": "Not started yet",
                },
                "optimization_results",
                resource_id=job.job_id,
            )

        if job.status == OptimizationStatus.RUNNING:
            return success_response(
                {"job_id": job.job_id, "status": "RUNNING", "message": "Still running"},
                "optimization_results",
                resource_id=job.job_id,
            )

        if job.status == OptimizationStatus.FAILED:
            return server_error(f"Optimization failed: {job.error}")

        results = job.results[:top_n]
        return collection_response(
            results,
            "optimization_result",
            total=len(job.results),
        )

    app.include_router(router)
    return app


def _generate_synthetic_ohlcv(bars: int = 500) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    import numpy as np

    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=bars, freq="1min")
    close = 100 + np.cumsum(np.random.randn(bars) * 0.5)
    close = np.maximum(close, 10)  # Keep prices positive

    return pd.DataFrame(
        {
            "open": close + np.random.randn(bars) * 0.1,
            "high": close + abs(np.random.randn(bars) * 0.5),
            "low": close - abs(np.random.randn(bars) * 0.5),
            "close": close,
            "volume": np.random.randint(100, 10000, bars).astype(float),
        },
        index=dates,
    )
