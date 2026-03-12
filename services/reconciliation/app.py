"""
Position Reconciliation REST API — RMM Level 2.

Provides endpoints to run position reconciliation and retrieve reports.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.reconciliation.exchange_client import ExchangePositionClient
from services.reconciliation.models import ReconciliationReport
from services.reconciliation.reconciler import (
    auto_reconcile_position,
    get_internal_positions,
    reconcile,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import server_error, success_response
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


class RunReconciliationRequest(BaseModel):
    auto_reconcile_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Max absolute quantity difference to auto-reconcile. 0 disables.",
    )


def create_app(
    db_pool: asyncpg.Pool,
    exchange_client: Optional[ExchangePositionClient] = None,
) -> FastAPI:
    """Create the Reconciliation API FastAPI application."""
    app = FastAPI(
        title="Reconciliation API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/reconciliation",
    )
    fastapi_auth_middleware(app)

    # Store the latest report in-memory for the GET endpoint
    latest_report: dict = {"report": None}

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("reconciliation-api", check_deps))

    @app.post("/run", tags=["Reconciliation"])
    async def run_reconciliation(body: RunReconciliationRequest):
        """Run a position reconciliation comparing internal vs exchange positions."""
        try:
            internal_positions = await get_internal_positions(db_pool)

            if exchange_client:
                exchange_positions = exchange_client.fetch_positions()
            else:
                # No exchange client configured — compare against empty
                # (useful for detecting phantom positions in paper-trading mode)
                exchange_positions = []

            report = reconcile(
                internal=internal_positions,
                exchange=exchange_positions,
                auto_reconcile_threshold=body.auto_reconcile_threshold,
            )

            # Apply auto-reconciliation to the database
            if report.auto_reconciled_count > 0 and exchange_client:
                for d in report.discrepancies:
                    if d.auto_reconciled and d.exchange_quantity is not None:
                        await auto_reconcile_position(
                            db_pool, d.symbol, d.exchange_quantity
                        )

            latest_report["report"] = report
            return success_response(report.to_dict(), "reconciliation_report")

        except Exception as e:
            logger.exception("Reconciliation run failed")
            return server_error(f"Reconciliation failed: {e}")

    @app.get("/report", tags=["Reconciliation"])
    async def get_report():
        """Get the most recent reconciliation report."""
        report = latest_report.get("report")
        if report is None:
            return success_response(
                {"message": "No reconciliation has been run yet."},
                "reconciliation_report",
            )
        return success_response(report.to_dict(), "reconciliation_report")

    return app
