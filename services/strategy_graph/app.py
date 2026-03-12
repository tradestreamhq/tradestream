"""
Strategy Graph REST API — RMM Level 2.

Provides endpoints for managing strategy dependencies and detecting
signal conflicts between strategies.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.strategy_graph.graph import StrategyGraph
from services.strategy_graph.models import (
    RelationshipType,
    Signal,
    SignalDirection,
    StrategyEdge,
    StrategyNode,
)


# --- Request DTOs ---


class StrategyCreate(BaseModel):
    strategy_id: str = Field(..., description="Unique strategy identifier")
    name: str = Field(..., description="Human-readable strategy name")
    symbols: List[str] = Field(..., min_length=1, description="Traded symbols")
    sharpe_ratio: float = Field(0.0, description="Strategy Sharpe ratio")


class EdgeCreate(BaseModel):
    source_id: str = Field(..., description="Source strategy ID")
    target_id: str = Field(..., description="Target strategy ID")
    relationship: str = Field(
        ...,
        description="Relationship type",
        pattern="^(SAME_SYMBOL|CORRELATED|HEDGING)$",
    )
    shared_symbols: List[str] = Field(default_factory=list)
    correlation: float = Field(0.0, ge=-1.0, le=1.0)


class SignalSubmit(BaseModel):
    strategy_id: str = Field(..., description="Strategy that generated the signal")
    symbol: str = Field(..., description="Target symbol")
    direction: str = Field(
        ..., description="BUY, SELL, or HOLD", pattern="^(BUY|SELL|HOLD)$"
    )
    strength: float = Field(1.0, ge=0.0, le=1.0, description="Signal strength")
    timestamp: Optional[str] = Field(
        None, description="ISO-8601 timestamp; defaults to now"
    )


# --- Application Factory ---


def create_app(graph: Optional[StrategyGraph] = None) -> FastAPI:
    """Create the Strategy Graph API FastAPI application."""
    g = graph or StrategyGraph()

    app = FastAPI(
        title="Strategy Graph API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategies",
    )

    app.include_router(create_health_router("strategy-graph"))

    # --- Strategies ---

    @app.get("/", tags=["Strategies"])
    async def list_strategies():
        """List all registered strategies."""
        items = [n.to_dict() for n in g.list_strategies()]
        return collection_response(items, "strategy")

    @app.post("/", tags=["Strategies"], status_code=201)
    async def add_strategy(body: StrategyCreate):
        """Register a new strategy in the graph."""
        node = StrategyNode(
            strategy_id=body.strategy_id,
            name=body.name,
            symbols=body.symbols,
            sharpe_ratio=body.sharpe_ratio,
        )
        g.add_strategy(node)
        return success_response(node.to_dict(), "strategy", resource_id=node.strategy_id)

    @app.get("/{strategy_id}", tags=["Strategies"])
    async def get_strategy(strategy_id: str):
        """Get a specific strategy by ID."""
        node = g.get_strategy(strategy_id)
        if not node:
            return not_found("Strategy", strategy_id)
        return success_response(node.to_dict(), "strategy", resource_id=strategy_id)

    @app.delete("/{strategy_id}", tags=["Strategies"])
    async def remove_strategy(strategy_id: str):
        """Remove a strategy from the graph."""
        if not g.get_strategy(strategy_id):
            return not_found("Strategy", strategy_id)
        g.remove_strategy(strategy_id)
        return success_response({"deleted": strategy_id}, "strategy")

    # --- Edges ---

    @app.get("/graph/edges", tags=["Graph"])
    async def list_edges():
        """List all relationship edges in the graph."""
        items = [e.to_dict() for e in g.get_edges()]
        return collection_response(items, "edge")

    @app.post("/graph/edges", tags=["Graph"], status_code=201)
    async def add_edge(body: EdgeCreate):
        """Add a relationship edge between two strategies."""
        if not g.get_strategy(body.source_id):
            return not_found("Strategy", body.source_id)
        if not g.get_strategy(body.target_id):
            return not_found("Strategy", body.target_id)
        edge = StrategyEdge(
            source_id=body.source_id,
            target_id=body.target_id,
            relationship=RelationshipType(body.relationship),
            shared_symbols=body.shared_symbols,
            correlation=body.correlation,
        )
        g.add_edge(edge)
        return success_response(edge.to_dict(), "edge")

    @app.get("/graph/neighbors/{strategy_id}", tags=["Graph"])
    async def get_neighbors(strategy_id: str):
        """Get strategies connected to the given strategy."""
        if not g.get_strategy(strategy_id):
            return not_found("Strategy", strategy_id)
        neighbor_ids = g.get_neighbors(strategy_id)
        neighbors = [
            g.get_strategy(nid).to_dict()
            for nid in neighbor_ids
            if g.get_strategy(nid)
        ]
        return collection_response(neighbors, "strategy")

    # --- Signals & Conflicts ---

    @app.post("/signals", tags=["Signals"], status_code=201)
    async def submit_signal(body: SignalSubmit):
        """Submit a trading signal for conflict detection."""
        if not g.get_strategy(body.strategy_id):
            return not_found("Strategy", body.strategy_id)
        ts = (
            datetime.fromisoformat(body.timestamp)
            if body.timestamp
            else datetime.now(timezone.utc)
        )
        signal = Signal(
            strategy_id=body.strategy_id,
            symbol=body.symbol,
            direction=SignalDirection(body.direction),
            timestamp=ts,
            strength=body.strength,
        )
        g.submit_signal(signal)
        return success_response(signal.to_dict(), "signal")

    @app.get("/conflicts", tags=["Conflicts"])
    async def get_conflicts(
        window_minutes: int = Query(5, ge=1, le=1440, description="Time window in minutes"),
    ):
        """Detect conflicting signals across strategies.

        Returns pairs of opposing signals on the same symbol within
        the specified time window. Conflicts are resolved by Sharpe ratio.
        """
        window = timedelta(minutes=window_minutes)
        conflicts = g.detect_conflicts(window=window)
        items = [c.to_dict() for c in conflicts]
        return collection_response(items, "conflict")

    @app.get("/graph", tags=["Graph"])
    async def get_graph():
        """Get the full strategy dependency graph."""
        return success_response(g.to_dict(), "strategy_graph")

    return app
