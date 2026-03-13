"""
Consensus API — Signal Aggregation REST API.

Provides endpoints for viewing consensus signals, historical consensus,
strategy agreement metrics, and configuring aggregation parameters.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.consensus_api.aggregator import (
    AggregationConfig,
    ConsensusSignal,
    Direction,
    Signal,
    SignalAggregator,
    StrategyWeight,
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


class AggregationConfigUpdate(BaseModel):
    window_seconds: Optional[int] = Field(None, ge=10, le=3600)
    min_strategies: Optional[int] = Field(None, ge=1, le=20)
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Consensus API FastAPI application."""
    app = FastAPI(
        title="Consensus API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/consensus",
    )
    fastapi_auth_middleware(app)

    config = AggregationConfig()
    aggregator = SignalAggregator(config)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("consensus-api", check_deps))

    async def _get_strategy_weights(conn) -> Dict[str, StrategyWeight]:
        """Load strategy weights from performance data."""
        query = """
            SELECT si.spec_id::text, si.id::text as strategy_id,
                   ss.name as strategy_name,
                   sp_wr.metric_value as win_rate,
                   sp_sr.metric_value as sharpe_ratio
            FROM strategy_implementations si
            JOIN strategy_specs ss ON si.spec_id = ss.id
            LEFT JOIN strategy_performance sp_wr
                ON sp_wr.strategy_id = si.id
                AND sp_wr.metric_type = 'win_rate'
            LEFT JOIN strategy_performance sp_sr
                ON sp_sr.strategy_id = si.id
                AND sp_sr.metric_type = 'sharpe_ratio'
            WHERE si.status IN ('VALIDATED', 'DEPLOYED')
        """
        rows = await conn.fetch(query)
        weights = {}
        for row in rows:
            sw = StrategyWeight(
                strategy_id=str(row["strategy_id"]),
                spec_id=str(row["spec_id"]),
                strategy_name=row["strategy_name"],
                win_rate=float(row["win_rate"]) if row["win_rate"] else 0.5,
                sharpe_ratio=float(row["sharpe_ratio"]) if row["sharpe_ratio"] else 0.0,
            )
            sw.compute_weight()
            weights[sw.strategy_id] = sw
        return weights

    async def _get_recent_signals(conn, instrument: str) -> List[Signal]:
        """Fetch recent signals for an instrument within the aggregation window."""
        query = """
            SELECT s.implementation_id::text as strategy_id,
                   s.spec_id::text,
                   s.instrument,
                   s.signal_type,
                   s.strength,
                   s.price,
                   s.created_at
            FROM signals s
            WHERE s.instrument = $1
              AND s.created_at >= NOW() - INTERVAL '1 second' * $2
              AND s.signal_type IN ('BUY', 'SELL', 'HOLD')
            ORDER BY s.created_at DESC
        """
        rows = await conn.fetch(query, instrument, config.window_seconds)
        signals = []
        seen_strategies = set()
        for row in rows:
            sid = row["strategy_id"]
            if sid in seen_strategies:
                continue
            seen_strategies.add(sid)
            signals.append(
                Signal(
                    strategy_id=sid,
                    spec_id=str(row["spec_id"]),
                    instrument=row["instrument"],
                    signal_type=row["signal_type"],
                    strength=float(row["strength"]) if row["strength"] else 0.5,
                    price=float(row["price"]) if row["price"] else 0.0,
                    timestamp=row["created_at"],
                )
            )
        return signals

    def _consensus_to_dict(cs: ConsensusSignal) -> Dict[str, Any]:
        result = {
            "id": cs.id,
            "instrument": cs.instrument,
            "direction": cs.direction.value,
            "confidence": cs.confidence,
            "contributing_signals": cs.contributing_signals,
            "agreeing_signals": cs.agreeing_signals,
            "dissenting_signals": cs.dissenting_signals,
            "agreement_ratio": cs.agreement_ratio(),
            "weighted_score": cs.weighted_score,
            "avg_price": cs.avg_price,
            "created_at": cs.created_at.isoformat(),
            "signal_details": cs.signal_details,
        }
        if cs.window_start:
            result["window_start"] = cs.window_start.isoformat()
        if cs.window_end:
            result["window_end"] = cs.window_end.isoformat()
        return result

    @app.get("/{pair}", tags=["Consensus"])
    async def get_consensus(pair: str):
        """Get current consensus signal for a trading pair."""
        async with db_pool.acquire() as conn:
            weights = await _get_strategy_weights(conn)
            signals = await _get_recent_signals(conn, pair)

        if not signals:
            return success_response(
                {
                    "instrument": pair,
                    "direction": Direction.NEUTRAL.value,
                    "confidence": 0.0,
                    "contributing_signals": 0,
                    "message": "No recent signals found",
                },
                "consensus_signal",
            )

        consensus = aggregator.aggregate(signals, weights)
        if consensus is None:
            return success_response(
                {
                    "instrument": pair,
                    "direction": Direction.NEUTRAL.value,
                    "confidence": 0.0,
                    "contributing_signals": len(signals),
                    "message": f"Insufficient strategies (need {config.min_strategies})",
                },
                "consensus_signal",
            )

        return success_response(
            _consensus_to_dict(consensus),
            "consensus_signal",
            resource_id=consensus.id,
        )

    @app.get("/{pair}/history", tags=["Consensus"])
    async def get_consensus_history(
        pair: str,
        pagination: PaginationParams = Depends(),
    ):
        """Get historical consensus signals for a trading pair."""
        query = """
            SELECT id, instrument, direction, confidence,
                   contributing_signals, agreeing_signals, dissenting_signals,
                   weighted_score, avg_price, signal_details,
                   window_start, window_end, created_at
            FROM consensus_signals
            WHERE instrument = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM consensus_signals WHERE instrument = $1
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, pair, pagination.limit, pagination.offset)
            total = await conn.fetchval(count_query, pair)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            for dt_field in ("window_start", "window_end", "created_at"):
                if item.get(dt_field):
                    item[dt_field] = item[dt_field].isoformat()
            if isinstance(item.get("signal_details"), str):
                item["signal_details"] = json.loads(item["signal_details"])
            items.append(item)

        return collection_response(
            items,
            "consensus_signal",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @app.get("/agreement", tags=["Consensus"])
    async def get_agreement_matrix():
        """Get strategy agreement matrix across all pairs."""
        query = """
            SELECT s.implementation_id::text as strategy_id,
                   s.instrument,
                   s.signal_type,
                   s.strength,
                   s.price,
                   s.spec_id::text,
                   s.created_at
            FROM signals s
            WHERE s.created_at >= NOW() - INTERVAL '1 hour'
              AND s.signal_type IN ('BUY', 'SELL', 'HOLD')
            ORDER BY s.created_at DESC
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        # Group signals by instrument, keeping latest per strategy
        signals_by_pair: Dict[str, List[Signal]] = {}
        seen: Dict[str, set] = {}
        for row in rows:
            instrument = row["instrument"]
            sid = row["strategy_id"]
            if instrument not in seen:
                seen[instrument] = set()
                signals_by_pair[instrument] = []
            if sid in seen[instrument]:
                continue
            seen[instrument].add(sid)
            signals_by_pair[instrument].append(
                Signal(
                    strategy_id=sid,
                    spec_id=str(row["spec_id"]),
                    instrument=instrument,
                    signal_type=row["signal_type"],
                    strength=float(row["strength"]) if row["strength"] else 0.5,
                    price=float(row["price"]) if row["price"] else 0.0,
                    timestamp=row["created_at"],
                )
            )

        matrix = aggregator.compute_agreement_matrix(signals_by_pair)

        return success_response(
            {
                "matrix": matrix,
                "pairs_analyzed": len(signals_by_pair),
                "strategies": sorted(
                    set(
                        s.strategy_id for sigs in signals_by_pair.values() for s in sigs
                    )
                ),
            },
            "agreement_matrix",
        )

    @app.put("/config", tags=["Configuration"])
    async def update_config(body: AggregationConfigUpdate):
        """Update aggregation configuration."""
        if body.window_seconds is not None:
            config.window_seconds = body.window_seconds
        if body.min_strategies is not None:
            config.min_strategies = body.min_strategies
        if body.confidence_threshold is not None:
            config.confidence_threshold = body.confidence_threshold

        return success_response(
            {
                "window_seconds": config.window_seconds,
                "min_strategies": config.min_strategies,
                "confidence_threshold": config.confidence_threshold,
            },
            "aggregation_config",
        )

    return app
