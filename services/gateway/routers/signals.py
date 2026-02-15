"""Signals router for real-time signal streaming and history."""

import json
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from ..middleware.auth_middleware import get_current_user_or_demo, TokenData
from ..services.db import get_pool
from ..services.redis_pubsub import subscribe_signals

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/stream")
async def signal_stream(
    request: Request,
    user: Optional[TokenData] = Depends(get_current_user_or_demo),
):
    """Stream real-time trading signals via Server-Sent Events.

    Accessible to both authenticated and demo users.
    """
    session_id = f"sess-{secrets.token_hex(8)}"
    sequence = 0

    async def event_generator():
        nonlocal sequence

        # Send session start event
        sequence += 1
        yield {
            "event": "session_start",
            "id": f"{session_id}:{sequence}",
            "data": json.dumps(
                {
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_demo": user.is_demo if user else True,
                }
            ),
        }

        # Subscribe to Redis channel and stream signals
        async for signal in subscribe_signals("scored-signals"):
            if await request.is_disconnected():
                break

            sequence += 1
            yield {
                "event": "signal",
                "id": f"{session_id}:{sequence}",
                "data": json.dumps(signal),
            }

            # Send periodic heartbeat
            if sequence % 30 == 0:
                yield {
                    "event": "heartbeat",
                    "id": f"{session_id}:{sequence}",
                    "data": json.dumps(
                        {"timestamp": datetime.now(timezone.utc).isoformat()}
                    ),
                }

    return EventSourceResponse(event_generator())


@router.get("")
async def get_signals(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    symbol: Optional[str] = None,
    action: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=1),
    provider_id: Optional[str] = None,
    user: Optional[TokenData] = Depends(get_current_user_or_demo),
):
    """Get paginated signal history.

    Accessible to both authenticated and demo users.
    """
    pool = await get_pool()

    # Build query with filters
    conditions = []
    params = []
    param_count = 0

    if symbol:
        param_count += 1
        conditions.append(f"s.symbol = ${param_count}")
        params.append(symbol)

    if action:
        param_count += 1
        conditions.append(f"s.action = ${param_count}")
        params.append(action.upper())

    if min_score is not None:
        param_count += 1
        conditions.append(f"s.opportunity_score >= ${param_count}")
        params.append(min_score)

    if provider_id:
        param_count += 1
        conditions.append(f"ps.provider_id = ${param_count}")
        params.append(provider_id)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    count_query = f"""
        SELECT COUNT(*) as total
        FROM signals s
        LEFT JOIN provider_signals ps ON s.signal_id = ps.signal_id
        WHERE {where_clause}
    """
    total_result = await pool.fetchrow(count_query, *params)
    total = total_result["total"] if total_result else 0

    # Get signals
    param_count += 1
    limit_param = param_count
    param_count += 1
    offset_param = param_count

    signals_query = f"""
        SELECT
            s.signal_id,
            s.symbol,
            s.action,
            s.confidence,
            s.opportunity_score,
            s.reasoning,
            s.created_at,
            p.user_id as provider_user_id,
            p.display_name as provider_name,
            p.avatar_url as provider_avatar,
            p.is_verified as provider_verified
        FROM signals s
        LEFT JOIN provider_signals ps ON s.signal_id = ps.signal_id
        LEFT JOIN providers p ON ps.provider_id = p.user_id
        WHERE {where_clause}
        ORDER BY s.created_at DESC
        LIMIT ${limit_param} OFFSET ${offset_param}
    """
    params.extend([limit, offset])

    rows = await pool.fetch(signals_query, *params)

    signals = []
    for row in rows:
        signal = {
            "signal_id": str(row["signal_id"]),
            "symbol": row["symbol"],
            "action": row["action"],
            "confidence": float(row["confidence"]) if row["confidence"] else None,
            "opportunity_score": (
                float(row["opportunity_score"]) if row["opportunity_score"] else None
            ),
            "reasoning": row["reasoning"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

        if row["provider_user_id"]:
            signal["provider"] = {
                "user_id": str(row["provider_user_id"]),
                "display_name": row["provider_name"],
                "avatar_url": row["provider_avatar"],
                "is_verified": row["provider_verified"],
            }

        signals.append(signal)

    return {
        "signals": signals,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    user: Optional[TokenData] = Depends(get_current_user_or_demo),
):
    """Get detailed signal with full reasoning.

    Accessible to both authenticated and demo users.
    """
    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT
            s.signal_id,
            s.symbol,
            s.action,
            s.confidence,
            s.opportunity_score,
            s.reasoning,
            s.created_at,
            p.user_id as provider_user_id,
            p.display_name as provider_name,
            p.avatar_url as provider_avatar,
            p.is_verified as provider_verified,
            ps.commentary
        FROM signals s
        LEFT JOIN provider_signals ps ON s.signal_id = ps.signal_id
        LEFT JOIN providers p ON ps.provider_id = p.user_id
        WHERE s.signal_id = $1
        """,
        signal_id,
    )

    if not row:
        from fastapi import HTTPException

        raise HTTPException(404, "Signal not found")

    signal = {
        "signal_id": str(row["signal_id"]),
        "symbol": row["symbol"],
        "action": row["action"],
        "confidence": float(row["confidence"]) if row["confidence"] else None,
        "opportunity_score": (
            float(row["opportunity_score"]) if row["opportunity_score"] else None
        ),
        "reasoning": row["reasoning"],
        "commentary": row["commentary"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }

    if row["provider_user_id"]:
        signal["provider"] = {
            "user_id": str(row["provider_user_id"]),
            "display_name": row["provider_name"],
            "avatar_url": row["provider_avatar"],
            "is_verified": row["provider_verified"],
        }

    return signal
