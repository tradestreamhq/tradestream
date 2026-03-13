"""
Trade Replay and Simulation API.

Provides endpoints to replay historical market data at configurable speeds
and place simulated trades against the replay feed. Sessions track P&L
and produce a summary when the replay completes.
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    error_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

VALID_SPEEDS = {1, 5, 10, 50}

SPEED_INTERVALS_MS = {
    1: 1000,
    5: 200,
    10: 100,
    50: 20,
}


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class StartReplayRequest(BaseModel):
    symbol: str = Field(..., description="Trading symbol (e.g. BTC/USD)")
    start_date: str = Field(..., description="Replay start date (YYYY-MM-DD or RFC3339)")
    end_date: str = Field(..., description="Replay end date (YYYY-MM-DD or RFC3339)")
    speed: int = Field(1, description="Playback speed: 1, 5, 10, or 50")
    interval: str = Field("1h", description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)")


class PlaceTradeRequest(BaseModel):
    side: TradeSide = Field(..., description="Trade side: buy or sell")
    quantity: float = Field(..., gt=0, description="Trade quantity")
    price: Optional[float] = Field(None, description="Limit price; defaults to current candle close")


class ReplaySession:
    """In-memory replay session state."""

    def __init__(
        self,
        session_id: str,
        symbol: str,
        start_date: str,
        end_date: str,
        speed: int,
        interval: str,
        candles: List[Dict[str, Any]],
    ):
        self.session_id = session_id
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.speed = speed
        self.interval = interval
        self.candles = candles
        self.tick_index = 0
        self.status = SessionStatus.ACTIVE
        self.trades: List[Dict[str, Any]] = []
        self.created_at = datetime.utcnow().isoformat() + "Z"

    def current_candle(self) -> Optional[Dict[str, Any]]:
        if self.tick_index < len(self.candles):
            return self.candles[self.tick_index]
        return None

    def advance(self) -> Optional[Dict[str, Any]]:
        candle = self.current_candle()
        if candle is not None:
            self.tick_index += 1
            if self.tick_index >= len(self.candles):
                self.status = SessionStatus.COMPLETED
        return candle

    def compute_summary(self) -> Dict[str, Any]:
        total_pnl = 0.0
        winning = 0
        losing = 0
        closed_trades = []

        # Pair buy/sell trades to compute P&L
        open_positions: List[Dict[str, Any]] = []
        for trade in self.trades:
            if trade["side"] == "buy":
                open_positions.append(trade)
            elif trade["side"] == "sell" and open_positions:
                entry = open_positions.pop(0)
                pnl = (trade["price"] - entry["price"]) * min(
                    entry["quantity"], trade["quantity"]
                )
                total_pnl += pnl
                if pnl > 0:
                    winning += 1
                elif pnl < 0:
                    losing += 1
                closed_trades.append(
                    {
                        "entry_price": entry["price"],
                        "exit_price": trade["price"],
                        "quantity": min(entry["quantity"], trade["quantity"]),
                        "pnl": round(pnl, 4),
                        "side": "long",
                    }
                )

        total_trades = len(closed_trades)
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0.0

        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "status": self.status.value,
            "total_candles": len(self.candles),
            "candles_replayed": self.tick_index,
            "total_trades": total_trades,
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 4),
            "open_positions": len(open_positions),
            "trades": self.trades,
            "closed_trades": closed_trades,
        }


# In-memory session store (keyed by session_id)
_sessions: Dict[str, ReplaySession] = {}


def get_sessions() -> Dict[str, ReplaySession]:
    return _sessions


def create_app(influxdb_client) -> FastAPI:
    """Create the Trade Replay API FastAPI application."""
    app = FastAPI(
        title="Trade Replay API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/replay",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        return {}

    app.include_router(create_health_router("replay-api", check_deps))

    replay_router = APIRouter(tags=["Replay"])

    @replay_router.post("/start")
    async def start_replay(req: StartReplayRequest):
        """Start a new replay session."""
        if req.speed not in VALID_SPEEDS:
            return validation_error(
                f"Invalid speed {req.speed}. Must be one of: {sorted(VALID_SPEEDS)}"
            )

        valid_intervals = {"1m", "5m", "15m", "1h", "4h", "1d"}
        if req.interval not in valid_intervals:
            return validation_error(
                f"Invalid interval '{req.interval}'. Must be one of: {sorted(valid_intervals)}"
            )

        candles = influxdb_client.get_candles(
            symbol=req.symbol,
            timeframe=req.interval,
            start=req.start_date,
            limit=10000,
        )

        # Filter candles within the date range
        filtered = _filter_candles(candles or [], req.start_date, req.end_date)

        if not filtered:
            return error_response(
                code="NO_DATA",
                message=f"No candle data found for {req.symbol} in the specified date range",
                status_code=404,
            )

        session_id = str(uuid.uuid4())
        session = ReplaySession(
            session_id=session_id,
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            speed=req.speed,
            interval=req.interval,
            candles=filtered,
        )
        sessions = get_sessions()
        sessions[session_id] = session

        return success_response(
            {
                "session_id": session_id,
                "symbol": req.symbol,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "speed": req.speed,
                "interval": req.interval,
                "total_candles": len(filtered),
                "tick_interval_ms": SPEED_INTERVALS_MS[req.speed],
                "status": session.status.value,
            },
            "replay_session",
            resource_id=session_id,
            status_code=201,
        )

    @replay_router.get("/{session_id}/tick")
    async def get_tick(session_id: str):
        """Get the next candle in the replay sequence."""
        sessions = get_sessions()
        session = sessions.get(session_id)
        if not session:
            return not_found("Replay session", session_id)

        if session.status == SessionStatus.COMPLETED:
            return error_response(
                code="REPLAY_COMPLETED",
                message="Replay session has ended. Fetch summary for results.",
                status_code=410,
            )

        candle = session.advance()
        if candle is None:
            session.status = SessionStatus.COMPLETED
            return error_response(
                code="REPLAY_COMPLETED",
                message="Replay session has ended. Fetch summary for results.",
                status_code=410,
            )

        return success_response(
            {
                "tick": session.tick_index,
                "total_ticks": len(session.candles),
                "remaining": len(session.candles) - session.tick_index,
                "speed": session.speed,
                "tick_interval_ms": SPEED_INTERVALS_MS[session.speed],
                "candle": candle,
                "status": session.status.value,
            },
            "replay_tick",
            resource_id=session_id,
        )

    @replay_router.post("/{session_id}/trade")
    async def place_trade(session_id: str, req: PlaceTradeRequest):
        """Place a simulated trade during replay."""
        sessions = get_sessions()
        session = sessions.get(session_id)
        if not session:
            return not_found("Replay session", session_id)

        if session.status == SessionStatus.COMPLETED:
            return error_response(
                code="REPLAY_COMPLETED",
                message="Cannot trade on a completed replay session",
                status_code=410,
            )

        if session.tick_index == 0:
            return validation_error("Must advance at least one tick before placing a trade")

        # Use the last replayed candle's close as market price
        last_candle = session.candles[session.tick_index - 1]
        price = req.price if req.price is not None else last_candle["close"]

        trade = {
            "trade_id": str(uuid.uuid4()),
            "side": req.side.value,
            "quantity": req.quantity,
            "price": price,
            "tick": session.tick_index,
            "timestamp": last_candle.get("time", session.created_at),
        }
        session.trades.append(trade)

        return success_response(
            trade,
            "replay_trade",
            resource_id=trade["trade_id"],
            status_code=201,
        )

    @replay_router.get("/{session_id}/summary")
    async def get_summary(session_id: str):
        """Get final P&L and stats after replay ends."""
        sessions = get_sessions()
        session = sessions.get(session_id)
        if not session:
            return not_found("Replay session", session_id)

        summary = session.compute_summary()
        return success_response(summary, "replay_summary", resource_id=session_id)

    app.include_router(replay_router)
    return app


def _filter_candles(
    candles: List[Dict[str, Any]], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Filter candles to only include those within the date range."""
    try:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
    except (ValueError, TypeError):
        return candles

    filtered = []
    for c in candles:
        t = c.get("time")
        if t is None:
            filtered.append(c)
            continue
        try:
            ct = _parse_date(t)
            if start <= ct <= end:
                filtered.append(c)
        except (ValueError, TypeError):
            filtered.append(c)
    return filtered


def _parse_date(date_str: str) -> datetime:
    """Parse date string in various formats."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")
