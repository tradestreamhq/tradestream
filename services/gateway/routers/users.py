"""User settings and watchlist router."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..middleware.auth_middleware import get_current_user, TokenData
from ..services.db import get_pool

router = APIRouter(prefix="/api/user", tags=["user"])


# Request/Response Models
class SettingsUpdate(BaseModel):
    risk_tolerance: Optional[str] = None
    min_opportunity_score: Optional[float] = None
    default_action_filter: Optional[List[str]] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None


class WatchlistAddRequest(BaseModel):
    symbol: str
    notes: Optional[str] = None
    alert_enabled: bool = True
    position_size: Optional[float] = None
    entry_price: Optional[float] = None


class SavedViewRequest(BaseModel):
    name: str
    description: Optional[str] = None
    filters: dict
    is_default: bool = False


# Settings Endpoints
@router.get("/settings")
async def get_settings(user: TokenData = Depends(get_current_user)):
    """Get user settings."""
    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT risk_tolerance, min_opportunity_score, default_action_filter,
               theme, timezone, onboarding_completed, onboarding_step
        FROM user_settings
        WHERE user_id = $1
        """,
        user.sub,
    )

    if not row:
        # Create default settings if not exists
        await pool.execute(
            "INSERT INTO user_settings (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user.sub,
        )
        return {
            "risk_tolerance": "moderate",
            "min_opportunity_score": 0.60,
            "default_action_filter": ["BUY", "SELL", "HOLD"],
            "theme": "dark",
            "timezone": "UTC",
            "onboarding_completed": False,
            "onboarding_step": 0,
        }

    return {
        "risk_tolerance": row["risk_tolerance"],
        "min_opportunity_score": (
            float(row["min_opportunity_score"])
            if row["min_opportunity_score"]
            else 0.60
        ),
        "default_action_filter": row["default_action_filter"]
        or ["BUY", "SELL", "HOLD"],
        "theme": row["theme"],
        "timezone": row["timezone"],
        "onboarding_completed": row["onboarding_completed"],
        "onboarding_step": row["onboarding_step"],
    }


@router.put("/settings")
async def update_settings(
    data: SettingsUpdate,
    user: TokenData = Depends(get_current_user),
):
    """Update user settings."""
    pool = await get_pool()

    # Build dynamic update query
    updates = []
    params = []
    param_count = 0

    if data.risk_tolerance is not None:
        if data.risk_tolerance not in ("conservative", "moderate", "aggressive"):
            raise HTTPException(400, "Invalid risk_tolerance value")
        param_count += 1
        updates.append(f"risk_tolerance = ${param_count}")
        params.append(data.risk_tolerance)

    if data.min_opportunity_score is not None:
        if not 0 <= data.min_opportunity_score <= 1:
            raise HTTPException(400, "min_opportunity_score must be between 0 and 1")
        param_count += 1
        updates.append(f"min_opportunity_score = ${param_count}")
        params.append(data.min_opportunity_score)

    if data.default_action_filter is not None:
        valid_actions = {"BUY", "SELL", "HOLD"}
        if not all(a.upper() in valid_actions for a in data.default_action_filter):
            raise HTTPException(400, "Invalid action filter values")
        param_count += 1
        updates.append(f"default_action_filter = ${param_count}")
        params.append([a.upper() for a in data.default_action_filter])

    if data.theme is not None:
        if data.theme not in ("dark", "light", "system"):
            raise HTTPException(400, "Invalid theme value")
        param_count += 1
        updates.append(f"theme = ${param_count}")
        params.append(data.theme)

    if data.timezone is not None:
        param_count += 1
        updates.append(f"timezone = ${param_count}")
        params.append(data.timezone)

    if not updates:
        raise HTTPException(400, "No fields to update")

    param_count += 1
    params.append(user.sub)

    query = f"""
        UPDATE user_settings
        SET {', '.join(updates)}, updated_at = NOW()
        WHERE user_id = ${param_count}
    """

    await pool.execute(query, *params)

    return await get_settings(user)


@router.post("/settings/complete-onboarding")
async def complete_onboarding(user: TokenData = Depends(get_current_user)):
    """Mark onboarding as completed."""
    pool = await get_pool()

    await pool.execute(
        "UPDATE user_settings SET onboarding_completed = TRUE WHERE user_id = $1",
        user.sub,
    )

    return {"message": "Onboarding completed"}


# Watchlist Endpoints
@router.get("/watchlist")
async def get_watchlist(user: TokenData = Depends(get_current_user)):
    """Get user's watchlist."""
    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT symbol, notes, alert_enabled, position_size, entry_price, added_at
        FROM user_watchlists
        WHERE user_id = $1
        ORDER BY added_at DESC
        """,
        user.sub,
    )

    watchlist = [
        {
            "symbol": row["symbol"],
            "notes": row["notes"],
            "alert_enabled": row["alert_enabled"],
            "position_size": (
                float(row["position_size"]) if row["position_size"] else None
            ),
            "entry_price": float(row["entry_price"]) if row["entry_price"] else None,
            "added_at": row["added_at"].isoformat() if row["added_at"] else None,
        }
        for row in rows
    ]

    return {"watchlist": watchlist}


@router.post("/watchlist", status_code=201)
async def add_to_watchlist(
    data: WatchlistAddRequest,
    user: TokenData = Depends(get_current_user),
):
    """Add symbol to watchlist."""
    pool = await get_pool()

    try:
        await pool.execute(
            """
            INSERT INTO user_watchlists (user_id, symbol, notes, alert_enabled, position_size, entry_price)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id, symbol) DO UPDATE SET
                notes = EXCLUDED.notes,
                alert_enabled = EXCLUDED.alert_enabled,
                position_size = EXCLUDED.position_size,
                entry_price = EXCLUDED.entry_price
            """,
            user.sub,
            data.symbol.upper(),
            data.notes,
            data.alert_enabled,
            data.position_size,
            data.entry_price,
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to add to watchlist: {str(e)}")

    return {
        "symbol": data.symbol.upper(),
        "notes": data.notes,
        "alert_enabled": data.alert_enabled,
        "position_size": data.position_size,
        "entry_price": data.entry_price,
        "message": "Added to watchlist",
    }


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    user: TokenData = Depends(get_current_user),
):
    """Remove symbol from watchlist."""
    pool = await get_pool()

    result = await pool.execute(
        "DELETE FROM user_watchlists WHERE user_id = $1 AND symbol = $2",
        user.sub,
        symbol.upper(),
    )

    if result == "DELETE 0":
        raise HTTPException(404, "Symbol not in watchlist")

    return {"message": f"Removed {symbol.upper()} from watchlist"}


# Saved Views Endpoints
@router.get("/saved-views")
async def get_saved_views(user: TokenData = Depends(get_current_user)):
    """Get saved filter views."""
    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT id, name, description, filters, is_default, sort_order, created_at
        FROM saved_views
        WHERE user_id = $1
        ORDER BY sort_order, created_at
        """,
        user.sub,
    )

    views = [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "filters": row["filters"],
            "is_default": row["is_default"],
            "sort_order": row["sort_order"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]

    return {"saved_views": views}


@router.post("/saved-views", status_code=201)
async def create_saved_view(
    data: SavedViewRequest,
    user: TokenData = Depends(get_current_user),
):
    """Create new saved view."""
    pool = await get_pool()

    # If setting as default, unset other defaults
    if data.is_default:
        await pool.execute(
            "UPDATE saved_views SET is_default = FALSE WHERE user_id = $1",
            user.sub,
        )

    row = await pool.fetchrow(
        """
        INSERT INTO saved_views (user_id, name, description, filters, is_default)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, name, description, filters, is_default, created_at
        """,
        user.sub,
        data.name,
        data.description,
        data.filters,
        data.is_default,
    )

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "filters": row["filters"],
        "is_default": row["is_default"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.delete("/saved-views/{view_id}")
async def delete_saved_view(
    view_id: str,
    user: TokenData = Depends(get_current_user),
):
    """Delete saved view."""
    pool = await get_pool()

    result = await pool.execute(
        "DELETE FROM saved_views WHERE id = $1 AND user_id = $2",
        view_id,
        user.sub,
    )

    if result == "DELETE 0":
        raise HTTPException(404, "View not found")

    return {"message": "View deleted"}
