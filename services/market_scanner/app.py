"""
Market Scanner REST API — RMM Level 2.

Provides endpoints to create, list, and delete market scans,
and to retrieve scan results filtered by pair or condition.
"""

import logging

from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from services.market_scanner.scanner import (
    MarketScanner,
    ScanCondition,
    ScanDefinition,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


class CreateScanRequest(BaseModel):
    pairs: List[str] = Field(..., min_length=1, description="Trading pairs to scan")
    conditions: List[ScanCondition] = Field(
        ..., min_length=1, description="Conditions to evaluate"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Condition-specific parameters"
    )


def create_app(market_data_client) -> FastAPI:
    """Create the Market Scanner API FastAPI application."""
    app = FastAPI(
        title="Market Scanner API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/scanner",
    )
    fastapi_auth_middleware(app)

    scanner = MarketScanner(market_data_client)

    async def check_deps():
        return {"scanner": "ok"}

    app.include_router(create_health_router("market-scanner", check_deps))

    router = APIRouter(tags=["Scanner"])

    @router.post("/create")
    async def create_scan(request: CreateScanRequest):
        """Define a new market scan."""
        definition = ScanDefinition(
            pairs=request.pairs,
            conditions=request.conditions,
            params=request.params,
        )
        scan = scanner.create_scan(definition)
        return success_response(
            {
                "id": scan.id,
                "pairs": scan.pairs,
                "conditions": [c.value for c in scan.conditions],
                "params": scan.params,
                "created_at": scan.created_at,
            },
            "scan",
            resource_id=scan.id,
        )

    @router.get("/results")
    async def get_results(
        pair: Optional[str] = Query(None, description="Filter by pair"),
        condition: Optional[str] = Query(None, description="Filter by condition"),
    ):
        """Get scan results, optionally filtered."""
        scanner.run_scans()
        results = scanner.get_results(pair=pair, condition=condition)
        items = [r.model_dump() for r in results]
        return collection_response(items, "scan_result")

    @router.delete("/{scan_id}")
    async def delete_scan(scan_id: str):
        """Delete a scan definition."""
        if not scanner.delete_scan(scan_id):
            return not_found("Scan", scan_id)
        return success_response({"deleted": True}, "scan", resource_id=scan_id)

    app.include_router(router)
    return app
