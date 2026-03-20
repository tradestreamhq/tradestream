"""Database storage for signal reasoning."""

import json
import logging
from dataclasses import asdict
from typing import Optional

from services.prediction_reasoning.models import (
    ConfidenceBreakdown,
    ContributingFactor,
    HistoricalPattern,
    MarketContext,
    RiskFactor,
    SignalReasoning,
)

logger = logging.getLogger(__name__)


def _serialize_factors(factors):
    """Serialize contributing factors to JSON-safe dicts."""
    return [asdict(f) for f in factors]


def _serialize_risk_factors(risks):
    """Serialize risk factors to JSON-safe dicts."""
    return [asdict(r) for r in risks]


async def save_reasoning(db_pool, reasoning: SignalReasoning) -> str:
    """Persist a signal reasoning to the database.

    Returns the generated reasoning ID.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO signal_reasoning
               (signal_id, strategy_name, symbol, signal_type,
                contributing_factors, indicator_values, market_context,
                confidence_breakdown, explanation_text, historical_context,
                risk_factors, validation_level,
                expected_return, expected_return_ci_lower, expected_return_ci_upper,
                predicted_timeframe_hours)
               VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb,
                       $8::jsonb, $9, $10, $11::jsonb, $12, $13, $14, $15, $16)
               RETURNING id""",
            reasoning.signal_id,
            reasoning.strategy_name,
            reasoning.symbol,
            reasoning.signal_type,
            json.dumps(_serialize_factors(reasoning.contributing_factors)),
            json.dumps(reasoning.indicator_values),
            json.dumps(asdict(reasoning.market_context)),
            json.dumps(asdict(reasoning.confidence_breakdown)),
            reasoning.explanation_text,
            (
                reasoning.historical_pattern.description
                if reasoning.historical_pattern
                else None
            ),
            json.dumps(_serialize_risk_factors(reasoning.risk_factors)),
            reasoning.validation_level,
            reasoning.expected_return,
            reasoning.expected_return_ci_lower,
            reasoning.expected_return_ci_upper,
            reasoning.predicted_timeframe_hours,
        )
        return str(row["id"])


async def get_reasoning_by_signal_id(db_pool, signal_id: str) -> Optional[dict]:
    """Retrieve reasoning for a given signal ID."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, signal_id, strategy_name, symbol, signal_type,
                      contributing_factors, indicator_values, market_context,
                      confidence_breakdown, explanation_text, historical_context,
                      risk_factors, validation_level,
                      expected_return, expected_return_ci_lower,
                      expected_return_ci_upper, predicted_timeframe_hours,
                      created_at
               FROM signal_reasoning
               WHERE signal_id = $1::uuid
               ORDER BY created_at DESC
               LIMIT 1""",
            signal_id,
        )
        if not row:
            return None
        return _row_to_dict(row)


async def get_reasoning_by_id(db_pool, reasoning_id: str) -> Optional[dict]:
    """Retrieve reasoning by its own ID."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, signal_id, strategy_name, symbol, signal_type,
                      contributing_factors, indicator_values, market_context,
                      confidence_breakdown, explanation_text, historical_context,
                      risk_factors, validation_level,
                      expected_return, expected_return_ci_lower,
                      expected_return_ci_upper, predicted_timeframe_hours,
                      created_at
               FROM signal_reasoning
               WHERE id = $1::uuid""",
            reasoning_id,
        )
        if not row:
            return None
        return _row_to_dict(row)


async def list_reasoning(
    db_pool,
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """List reasoning records with optional filters."""
    conditions = []
    params = []
    idx = 1

    if strategy_name:
        conditions.append(f"strategy_name = ${idx}")
        params.append(strategy_name)
        idx += 1
    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.extend([limit, offset])

    query = f"""
        SELECT id, signal_id, strategy_name, symbol, signal_type,
               contributing_factors, indicator_values, market_context,
               confidence_breakdown, explanation_text, historical_context,
               risk_factors, validation_level,
               expected_return, expected_return_ci_lower,
               expected_return_ci_upper, predicted_timeframe_hours,
               created_at
        FROM signal_reasoning
        {where}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict:
    """Convert a database row to a serializable dict."""
    d = dict(row)
    d["id"] = str(d["id"])
    d["signal_id"] = str(d["signal_id"])

    # JSONB columns are already parsed by asyncpg
    for decimal_key in (
        "expected_return",
        "expected_return_ci_lower",
        "expected_return_ci_upper",
    ):
        if d.get(decimal_key) is not None:
            d[decimal_key] = float(d[decimal_key])

    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()

    return d
