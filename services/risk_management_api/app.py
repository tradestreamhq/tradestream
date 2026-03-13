"""
Risk Management REST API — RMM Level 2.

Provides endpoints for position sizing, risk limits management,
portfolio exposure analysis, risk checking middleware, and daily risk reports.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class PositionSizeRequest(BaseModel):
    account_size: float = Field(..., gt=0, description="Total account size in dollars")
    risk_pct: float = Field(
        ..., gt=0, le=1, description="Risk percentage as decimal (e.g. 0.02 for 2%)"
    )
    entry_price: float = Field(..., gt=0, description="Planned entry price")
    stop_price: float = Field(..., gt=0, description="Stop-loss price")


class RiskLimitsUpdate(BaseModel):
    max_position_size: Optional[float] = Field(
        None, gt=0, description="Maximum position size in dollars"
    )
    max_position_pct: Optional[float] = Field(
        None, gt=0, le=1, description="Maximum position size as portfolio percentage"
    )
    max_daily_loss: Optional[float] = Field(
        None, gt=0, description="Maximum daily loss in dollars"
    )
    max_daily_loss_pct: Optional[float] = Field(
        None, gt=0, le=1, description="Maximum daily loss as percentage"
    )
    max_drawdown_pct: Optional[float] = Field(
        None, gt=0, le=1, description="Maximum drawdown percentage"
    )
    max_open_positions: Optional[int] = Field(
        None, gt=0, description="Maximum number of open positions"
    )
    max_sector_exposure_pct: Optional[float] = Field(
        None, gt=0, le=1, description="Maximum sector exposure percentage"
    )
    max_correlated_exposure_pct: Optional[float] = Field(
        None, gt=0, le=1, description="Maximum correlated exposure percentage"
    )


class TradeRiskCheck(BaseModel):
    instrument: str = Field(..., description="Trading instrument symbol")
    side: str = Field(..., description="BUY or SELL", pattern="^(BUY|SELL)$")
    size: float = Field(..., gt=0, description="Trade size in units")
    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop-loss price")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Risk Management API FastAPI application."""
    app = FastAPI(
        title="Risk Management API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/risk",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("risk-management-api", check_deps))

    # =================================================================
    # POST /calculate — Position sizing calculator
    # =================================================================

    @app.post("/calculate", tags=["Position Sizing"])
    async def calculate_position_size(body: PositionSizeRequest):
        """Calculate position size and dollar risk given account parameters."""
        price_diff = abs(body.entry_price - body.stop_price)
        if price_diff == 0:
            return validation_error(
                "Entry price and stop price must be different",
                [{"field": "stop_price", "message": "Must differ from entry_price"}],
            )

        dollar_risk = body.account_size * body.risk_pct
        position_size = dollar_risk / price_diff
        position_value = position_size * body.entry_price
        risk_reward_per_unit = price_diff

        return success_response(
            {
                "position_size": round(position_size, 8),
                "dollar_risk": round(dollar_risk, 2),
                "position_value": round(position_value, 2),
                "risk_per_unit": round(risk_reward_per_unit, 8),
                "account_size": body.account_size,
                "risk_pct": body.risk_pct,
                "entry_price": body.entry_price,
                "stop_price": body.stop_price,
            },
            "position_size",
        )

    # =================================================================
    # GET /limits — Retrieve current risk limits
    # =================================================================

    @app.get("/limits", tags=["Risk Limits"])
    async def get_risk_limits():
        """Get user-configured risk limits."""
        query = """
            SELECT id, max_position_size, max_position_pct, max_daily_loss,
                   max_daily_loss_pct, max_drawdown_pct, max_open_positions,
                   max_sector_exposure_pct, max_correlated_exposure_pct,
                   created_at, updated_at
            FROM risk_limits
            ORDER BY created_at
            LIMIT 1
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query)

        if not row:
            return not_found("RiskLimits", "default")

        item = dict(row)
        item["id"] = str(item["id"])
        for key in (
            "max_position_size",
            "max_position_pct",
            "max_daily_loss",
            "max_daily_loss_pct",
            "max_drawdown_pct",
            "max_sector_exposure_pct",
            "max_correlated_exposure_pct",
        ):
            if item.get(key) is not None:
                item[key] = float(item[key])
        for key in ("created_at", "updated_at"):
            if item.get(key):
                item[key] = item[key].isoformat()

        return success_response(item, "risk_limits", resource_id=item["id"])

    # =================================================================
    # PUT /limits — Update risk limits
    # =================================================================

    @app.put("/limits", tags=["Risk Limits"])
    async def update_risk_limits(body: RiskLimitsUpdate):
        """Update user-configured risk limits."""
        updates = body.model_dump(exclude_none=True)
        if not updates:
            return validation_error("At least one field must be provided")

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(updates.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)

        query = f"""
            UPDATE risk_limits
            SET {', '.join(set_clauses)}
            WHERE id = (SELECT id FROM risk_limits ORDER BY created_at LIMIT 1)
            RETURNING id, max_position_size, max_position_pct, max_daily_loss,
                      max_daily_loss_pct, max_drawdown_pct, max_open_positions,
                      max_sector_exposure_pct, max_correlated_exposure_pct,
                      created_at, updated_at
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        if not row:
            return not_found("RiskLimits", "default")

        item = dict(row)
        item["id"] = str(item["id"])
        for key in (
            "max_position_size",
            "max_position_pct",
            "max_daily_loss",
            "max_daily_loss_pct",
            "max_drawdown_pct",
            "max_sector_exposure_pct",
            "max_correlated_exposure_pct",
        ):
            if item.get(key) is not None:
                item[key] = float(item[key])
        for key in ("created_at", "updated_at"):
            if item.get(key):
                item[key] = item[key].isoformat()

        return success_response(item, "risk_limits", resource_id=item["id"])

    # =================================================================
    # GET /exposure — Current portfolio exposure breakdown
    # =================================================================

    @app.get("/exposure", tags=["Exposure"])
    async def get_exposure():
        """Get current portfolio exposure by sector, asset class, and correlation."""
        positions_query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl
            FROM paper_portfolio
            WHERE quantity != 0
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(positions_query)

        positions = []
        total_exposure = 0.0
        by_asset_class: Dict[str, float] = {}
        by_sector: Dict[str, float] = {}

        for row in rows:
            qty = float(row["quantity"])
            price = float(row["avg_entry_price"])
            exposure = abs(qty * price)
            total_exposure += exposure
            symbol = row["symbol"]

            # Derive asset class from symbol convention
            if "/" in symbol:
                base, quote = symbol.split("/", 1)
            else:
                base, quote = symbol, "USD"

            asset_class = "crypto"
            by_asset_class[asset_class] = by_asset_class.get(asset_class, 0) + exposure

            # Use base currency as a proxy for sector grouping
            sector = base
            by_sector[sector] = by_sector.get(sector, 0) + exposure

            positions.append(
                {
                    "symbol": symbol,
                    "quantity": qty,
                    "exposure": round(exposure, 2),
                    "asset_class": asset_class,
                    "sector": sector,
                }
            )

        # Normalize to percentages
        asset_class_pct = {
            k: round(v / total_exposure, 4) if total_exposure > 0 else 0
            for k, v in by_asset_class.items()
        }
        sector_pct = {
            k: round(v / total_exposure, 4) if total_exposure > 0 else 0
            for k, v in by_sector.items()
        }

        # Simple correlation proxy: positions in the same asset class
        # are considered correlated
        correlated_groups: Dict[str, List[str]] = {}
        for pos in positions:
            ac = pos["asset_class"]
            if ac not in correlated_groups:
                correlated_groups[ac] = []
            correlated_groups[ac].append(pos["symbol"])

        return success_response(
            {
                "total_exposure": round(total_exposure, 2),
                "position_count": len(positions),
                "positions": positions,
                "by_asset_class": asset_class_pct,
                "by_sector": sector_pct,
                "correlated_groups": correlated_groups,
            },
            "portfolio_exposure",
        )

    # =================================================================
    # POST /check — Risk check middleware for trade validation
    # =================================================================

    @app.post("/check", tags=["Risk Check"])
    async def check_trade_risk(body: TradeRiskCheck):
        """Validate a proposed trade against user risk limits before execution."""
        errors: List[str] = []
        warnings: List[str] = []

        async with db_pool.acquire() as conn:
            # Fetch risk limits
            limits_row = await conn.fetchrow(
                "SELECT * FROM risk_limits ORDER BY created_at LIMIT 1"
            )
            if not limits_row:
                return server_error("Risk limits not configured")

            limits = dict(limits_row)

            # Check max open positions
            open_count = await conn.fetchval(
                "SELECT COUNT(*) FROM paper_portfolio WHERE quantity != 0"
            )
            if body.side == "BUY" and open_count >= limits["max_open_positions"]:
                errors.append(
                    f"Max open positions ({limits['max_open_positions']}) reached"
                )

            # Check position size against max
            trade_value = body.size * body.entry_price
            max_pos = float(limits["max_position_size"])
            if trade_value > max_pos:
                errors.append(
                    f"Trade value ${trade_value:.2f} exceeds max position "
                    f"size ${max_pos:.2f}"
                )

            # Check daily loss
            today_loss_row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pnl), 0) as today_loss
                FROM paper_trades
                WHERE status = 'CLOSED'
                  AND closed_at >= CURRENT_DATE
                  AND pnl < 0
                """
            )
            today_loss = abs(float(today_loss_row["today_loss"]))
            max_daily = float(limits["max_daily_loss"])
            if today_loss >= max_daily:
                errors.append(
                    f"Daily loss limit reached: ${today_loss:.2f} >= ${max_daily:.2f}"
                )

            # Check stop-loss risk if provided
            if body.stop_price:
                risk_per_unit = abs(body.entry_price - body.stop_price)
                dollar_risk = risk_per_unit * body.size
                if dollar_risk > max_daily - today_loss:
                    remaining = max_daily - today_loss
                    warnings.append(
                        f"Trade risk ${dollar_risk:.2f} exceeds remaining "
                        f"daily budget ${remaining:.2f}"
                    )

            # Check existing position for SELL
            if body.side == "SELL":
                pos_row = await conn.fetchrow(
                    "SELECT quantity FROM paper_portfolio WHERE symbol = $1",
                    body.instrument,
                )
                if not pos_row or float(pos_row["quantity"]) < body.size:
                    errors.append(
                        f"Insufficient position in {body.instrument} "
                        f"for SELL of {body.size}"
                    )

        return success_response(
            {
                "approved": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "trade": {
                    "instrument": body.instrument,
                    "side": body.side,
                    "size": body.size,
                    "entry_price": body.entry_price,
                    "value": round(body.size * body.entry_price, 2),
                },
            },
            "risk_check",
        )

    # =================================================================
    # GET /report — Daily risk report
    # =================================================================

    @app.get("/report", tags=["Report"])
    async def get_risk_report():
        """Get daily risk report with P&L, drawdown, and exposure breakdown."""
        async with db_pool.acquire() as conn:
            # Today's P&L
            today_pnl_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0) as gross_profit,
                    COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0) as gross_loss,
                    COALESCE(SUM(pnl), 0) as net_pnl,
                    COUNT(*) as trades_closed
                FROM paper_trades
                WHERE status = 'CLOSED'
                  AND closed_at >= CURRENT_DATE
                """
            )

            # Unrealized P&L
            unrealized_row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(unrealized_pnl), 0) as total_unrealized
                FROM paper_portfolio
                WHERE quantity != 0
                """
            )

            # Total realized P&L (all time) for drawdown calculation
            total_realized_row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pnl), 0) as total_realized
                FROM paper_trades
                WHERE status = 'CLOSED'
                """
            )

            # Peak equity approximation (sum of all winning trades)
            peak_row = await conn.fetchrow(
                """
                SELECT COALESCE(MAX(running_total), 0) as peak_equity
                FROM (
                    SELECT SUM(pnl) OVER (ORDER BY closed_at) as running_total
                    FROM paper_trades
                    WHERE status = 'CLOSED'
                ) sub
                """
            )

            # Position exposure
            positions = await conn.fetch(
                """
                SELECT symbol, quantity, avg_entry_price, unrealized_pnl
                FROM paper_portfolio
                WHERE quantity != 0
                ORDER BY symbol
                """
            )

            # Risk limits
            limits_row = await conn.fetchrow(
                "SELECT * FROM risk_limits ORDER BY created_at LIMIT 1"
            )

        total_realized = float(total_realized_row["total_realized"])
        total_unrealized = float(unrealized_row["total_unrealized"])
        current_equity = total_realized + total_unrealized
        peak_equity = float(peak_row["peak_equity"]) if peak_row["peak_equity"] else 0

        # Drawdown calculation
        drawdown = 0.0
        drawdown_pct = 0.0
        if peak_equity > 0:
            drawdown = peak_equity - current_equity
            drawdown_pct = drawdown / peak_equity if drawdown > 0 else 0.0

        # Build exposure breakdown
        exposure_list = []
        total_exposure = 0.0
        for row in positions:
            qty = float(row["quantity"])
            price = float(row["avg_entry_price"])
            exp = abs(qty * price)
            total_exposure += exp
            exposure_list.append(
                {
                    "symbol": row["symbol"],
                    "exposure": round(exp, 2),
                    "unrealized_pnl": float(row["unrealized_pnl"]),
                }
            )

        # Limits utilization
        limits_util = {}
        if limits_row:
            max_daily = float(limits_row["max_daily_loss"])
            today_loss = abs(float(today_pnl_row["gross_loss"]))
            limits_util = {
                "daily_loss_used": round(today_loss, 2),
                "daily_loss_limit": round(max_daily, 2),
                "daily_loss_pct_used": (
                    round(today_loss / max_daily, 4) if max_daily > 0 else 0
                ),
                "max_drawdown_pct": float(limits_row["max_drawdown_pct"]),
                "current_drawdown_pct": round(drawdown_pct, 4),
            }

        return success_response(
            {
                "date": date.today().isoformat(),
                "pnl": {
                    "gross_profit": float(today_pnl_row["gross_profit"]),
                    "gross_loss": float(today_pnl_row["gross_loss"]),
                    "net_pnl": float(today_pnl_row["net_pnl"]),
                    "trades_closed": today_pnl_row["trades_closed"],
                    "total_unrealized": total_unrealized,
                },
                "equity": {
                    "current": round(current_equity, 2),
                    "peak": round(peak_equity, 2),
                },
                "drawdown": {
                    "amount": round(drawdown, 2),
                    "pct": round(drawdown_pct, 4),
                },
                "exposure": {
                    "total": round(total_exposure, 2),
                    "positions": exposure_list,
                },
                "limits_utilization": limits_util,
            },
            "risk_report",
        )

    return app
