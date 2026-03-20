"""Opportunity Scoring Engine — FastAPI application."""

from typing import Optional

from fastapi import FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

from .aggregator import aggregate_signals, rank_opportunities
from .lifecycle import OpportunityTracker
from .models import ContributingSignal, OpportunityStatus


def create_app(tracker: Optional[OpportunityTracker] = None) -> FastAPI:
    """Create the Opportunity Scoring Engine FastAPI application.

    Args:
        tracker: OpportunityTracker instance. Creates a new one if None.

    Returns:
        Configured FastAPI application.
    """
    if tracker is None:
        tracker = OpportunityTracker()

    app = FastAPI(
        title="Opportunity Scoring Engine",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/opportunities",
    )

    fastapi_auth_middleware(app)
    app.include_router(create_health_router("opportunity-scoring"))

    @app.get("/", tags=["Opportunities"])
    async def list_opportunities(
        min_score: float = Query(
            0.0, ge=0, le=100, description="Minimum opportunity score"
        ),
        min_tier: Optional[str] = Query(
            None, description="Minimum tier: HOT, GOOD, NEUTRAL, LOW"
        ),
        symbol: Optional[str] = Query(None, description="Filter by trading pair"),
        status: Optional[str] = Query(None, description="Filter by lifecycle status"),
        exclude_stale: bool = Query(
            True, description="Exclude stale (>60 min) opportunities"
        ),
        limit: int = Query(50, ge=1, le=200, description="Max results"),
        offset: int = Query(0, ge=0, description="Pagination offset"),
    ):
        """List scored opportunities, ranked by composite score."""
        if min_tier and min_tier not in ("HOT", "GOOD", "NEUTRAL", "LOW"):
            return validation_error(
                "Invalid min_tier. Must be HOT, GOOD, NEUTRAL, or LOW."
            )

        if status and status not in [s.value for s in OpportunityStatus]:
            return validation_error(
                f"Invalid status. Must be one of: {', '.join(s.value for s in OpportunityStatus)}"
            )

        all_opps = tracker.list_active() if exclude_stale else tracker.list_all()

        # Filter by symbol if specified
        if symbol:
            all_opps = [o for o in all_opps if o.symbol == symbol]

        # Filter by status if specified
        if status:
            all_opps = [o for o in all_opps if o.status == status]

        ranked = rank_opportunities(
            all_opps,
            min_score=min_score,
            min_tier=min_tier,
            exclude_stale=exclude_stale,
        )

        total = len(ranked)
        page = ranked[offset : offset + limit]

        return collection_response(
            items=[o.to_dict() for o in page],
            resource_type="opportunity",
            total=total,
            limit=limit,
            offset=offset,
        )

    @app.get("/{opportunity_id}", tags=["Opportunities"])
    async def get_opportunity(opportunity_id: str):
        """Get a single opportunity by ID with full score breakdown."""
        opp = tracker.get(opportunity_id)
        if opp is None:
            return not_found("opportunity", opportunity_id)
        return success_response(
            opp.to_dict(), "opportunity", resource_id=opportunity_id
        )

    @app.post("/score", tags=["Scoring"])
    async def score_signals(body: dict):
        """Score a set of signals for a trading pair.

        Request body:
            symbol: Trading pair (e.g. "BTC/USD")
            signals: List of signal objects with source, signal_id,
                     direction, confidence, strategy_name, expected_return,
                     return_stddev
            volatility: Optional hourly volatility
            volatility_percentile: Optional 30-day percentile
        """
        symbol = body.get("symbol")
        if not symbol:
            return validation_error("symbol is required")

        raw_signals = body.get("signals", [])
        if not raw_signals:
            return validation_error("signals list is required and cannot be empty")

        signals = []
        for s in raw_signals:
            signals.append(
                ContributingSignal(
                    source=s.get("source", "unknown"),
                    signal_id=s.get("signal_id", ""),
                    direction=s.get("direction", "HOLD"),
                    confidence=float(s.get("confidence", 0.0)),
                    strategy_name=s.get("strategy_name"),
                    expected_return=s.get("expected_return"),
                    return_stddev=s.get("return_stddev"),
                )
            )

        opportunity = aggregate_signals(
            symbol=symbol,
            signals=signals,
            volatility=body.get("volatility"),
            volatility_percentile=body.get("volatility_percentile"),
        )

        if opportunity is None:
            return success_response(
                {"message": "No actionable opportunity — signals lack consensus"},
                "scoring_result",
            )

        tracker.track(opportunity)

        return success_response(
            opportunity.to_dict(),
            "opportunity",
            resource_id=opportunity.opportunity_id,
            status_code=201,
        )

    @app.patch("/{opportunity_id}/status", tags=["Lifecycle"])
    async def update_status(opportunity_id: str, body: dict):
        """Update opportunity lifecycle status.

        Request body:
            status: New status (signaled, entered, closed, expired)
            outcome_return: Return value (required when closing)
        """
        new_status = body.get("status")
        if not new_status:
            return validation_error("status is required")

        opp = tracker.get(opportunity_id)
        if opp is None:
            return not_found("opportunity", opportunity_id)

        success = False
        if new_status == OpportunityStatus.SIGNALED.value:
            success = tracker.mark_signaled(opportunity_id)
        elif new_status == OpportunityStatus.ENTERED.value:
            success = tracker.mark_entered(opportunity_id)
        elif new_status == OpportunityStatus.CLOSED.value:
            success = tracker.mark_closed(
                opportunity_id, outcome_return=body.get("outcome_return")
            )
        elif new_status == OpportunityStatus.EXPIRED.value:
            success = tracker.mark_expired(opportunity_id)
        else:
            return validation_error(
                f"Invalid status. Must be one of: signaled, entered, closed, expired"
            )

        if not success:
            return validation_error(
                f"Cannot transition from '{opp.status}' to '{new_status}'"
            )

        return success_response(
            tracker.get(opportunity_id).to_dict(),
            "opportunity",
            resource_id=opportunity_id,
        )

    @app.get("/stats/summary", tags=["Stats"])
    async def get_stats():
        """Get summary statistics for tracked opportunities."""
        return success_response(tracker.get_stats(), "opportunity_stats")

    return app
