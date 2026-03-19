"""
User Strategy Builder API.

No-code strategy builder allowing users to create custom trading strategies
by combining indicators, setting entry/exit conditions, validating configs,
backtesting, and publishing to the marketplace.
"""

import json
import logging
import statistics
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Header, Query
from pydantic import BaseModel, Field, validator

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Indicator Palette — available indicators with parameter descriptions
# ---------------------------------------------------------------------------

INDICATOR_CATALOG = [
    {
        "type": "RSI",
        "name": "Relative Strength Index",
        "category": "momentum",
        "description": "Measures speed and magnitude of price changes",
        "inputs": ["close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 14,
                "min": 2,
                "max": 200,
                "description": "Lookback period",
            },
        ],
        "outputs": ["value"],
    },
    {
        "type": "MACD",
        "name": "MACD",
        "category": "momentum",
        "description": "Moving Average Convergence Divergence",
        "inputs": ["close"],
        "params": [
            {
                "name": "shortPeriod",
                "type": "integer",
                "default": 12,
                "min": 2,
                "max": 100,
                "description": "Short EMA period",
            },
            {
                "name": "longPeriod",
                "type": "integer",
                "default": 26,
                "min": 2,
                "max": 200,
                "description": "Long EMA period",
            },
            {
                "name": "signalPeriod",
                "type": "integer",
                "default": 9,
                "min": 2,
                "max": 50,
                "description": "Signal line period",
            },
        ],
        "outputs": ["macd_line", "signal_line", "histogram"],
    },
    {
        "type": "SMA",
        "name": "Simple Moving Average",
        "category": "trend",
        "description": "Average closing price over a period",
        "inputs": ["close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 20,
                "min": 2,
                "max": 500,
                "description": "Lookback period",
            },
        ],
        "outputs": ["value"],
    },
    {
        "type": "EMA",
        "name": "Exponential Moving Average",
        "category": "trend",
        "description": "Weighted moving average favoring recent prices",
        "inputs": ["close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 20,
                "min": 2,
                "max": 500,
                "description": "Lookback period",
            },
        ],
        "outputs": ["value"],
    },
    {
        "type": "BOLLINGER_BANDS",
        "name": "Bollinger Bands",
        "category": "volatility",
        "description": "Volatility bands around a moving average",
        "inputs": ["close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 20,
                "min": 2,
                "max": 200,
                "description": "Moving average period",
            },
            {
                "name": "stdDev",
                "type": "double",
                "default": 2.0,
                "min": 0.5,
                "max": 5.0,
                "description": "Standard deviation multiplier",
            },
        ],
        "outputs": ["upper", "middle", "lower"],
    },
    {
        "type": "ATR",
        "name": "Average True Range",
        "category": "volatility",
        "description": "Measures market volatility",
        "inputs": ["high", "low", "close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 14,
                "min": 2,
                "max": 200,
                "description": "Lookback period",
            },
        ],
        "outputs": ["value"],
    },
    {
        "type": "STOCHASTIC",
        "name": "Stochastic Oscillator",
        "category": "momentum",
        "description": "Compares closing price to price range over a period",
        "inputs": ["high", "low", "close"],
        "params": [
            {
                "name": "kPeriod",
                "type": "integer",
                "default": 14,
                "min": 2,
                "max": 200,
                "description": "%K period",
            },
            {
                "name": "dPeriod",
                "type": "integer",
                "default": 3,
                "min": 2,
                "max": 50,
                "description": "%D smoothing period",
            },
        ],
        "outputs": ["k", "d"],
    },
    {
        "type": "ADX",
        "name": "Average Directional Index",
        "category": "trend",
        "description": "Measures trend strength",
        "inputs": ["high", "low", "close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 14,
                "min": 2,
                "max": 200,
                "description": "Lookback period",
            },
        ],
        "outputs": ["value", "plus_di", "minus_di"],
    },
    {
        "type": "CCI",
        "name": "Commodity Channel Index",
        "category": "momentum",
        "description": "Measures deviation from statistical mean",
        "inputs": ["high", "low", "close"],
        "params": [
            {
                "name": "period",
                "type": "integer",
                "default": 20,
                "min": 2,
                "max": 200,
                "description": "Lookback period",
            },
        ],
        "outputs": ["value"],
    },
    {
        "type": "OBV",
        "name": "On-Balance Volume",
        "category": "volume",
        "description": "Cumulative volume indicator",
        "inputs": ["close", "volume"],
        "params": [],
        "outputs": ["value"],
    },
    {
        "type": "VWAP",
        "name": "Volume Weighted Average Price",
        "category": "volume",
        "description": "Average price weighted by volume",
        "inputs": ["high", "low", "close", "volume"],
        "params": [],
        "outputs": ["value"],
    },
    {
        "type": "ICHIMOKU",
        "name": "Ichimoku Cloud",
        "category": "trend",
        "description": "Multi-component trend indicator",
        "inputs": ["high", "low", "close"],
        "params": [
            {
                "name": "tenkanPeriod",
                "type": "integer",
                "default": 9,
                "min": 2,
                "max": 100,
                "description": "Tenkan-sen (conversion line) period",
            },
            {
                "name": "kijunPeriod",
                "type": "integer",
                "default": 26,
                "min": 2,
                "max": 200,
                "description": "Kijun-sen (base line) period",
            },
            {
                "name": "senkouBPeriod",
                "type": "integer",
                "default": 52,
                "min": 2,
                "max": 500,
                "description": "Senkou Span B period",
            },
        ],
        "outputs": ["tenkan", "kijun", "senkou_a", "senkou_b", "chikou"],
    },
    {
        "type": "PARABOLIC_SAR",
        "name": "Parabolic SAR",
        "category": "trend",
        "description": "Stop and reverse indicator",
        "inputs": ["high", "low"],
        "params": [
            {
                "name": "accelerationFactor",
                "type": "double",
                "default": 0.02,
                "min": 0.001,
                "max": 0.5,
                "description": "Acceleration factor",
            },
            {
                "name": "maxAcceleration",
                "type": "double",
                "default": 0.2,
                "min": 0.01,
                "max": 1.0,
                "description": "Max acceleration",
            },
        ],
        "outputs": ["value"],
    },
    {
        "type": "CONSTANT",
        "name": "Constant Value",
        "category": "utility",
        "description": "A fixed numeric threshold for comparisons",
        "inputs": [],
        "params": [
            {
                "name": "value",
                "type": "double",
                "default": 0,
                "min": -99999,
                "max": 99999,
                "description": "Constant value",
            },
        ],
        "outputs": ["value"],
    },
]

INDICATOR_TYPE_SET = frozenset(ind["type"] for ind in INDICATOR_CATALOG)

# Condition types that map to Ta4j rules
CONDITION_TYPES = [
    {
        "type": "CrossedUp",
        "description": "Indicator crosses above reference",
        "requires": ["indicator", "reference"],
        "category": "crossover",
    },
    {
        "type": "CrossedDown",
        "description": "Indicator crosses below reference",
        "requires": ["indicator", "reference"],
        "category": "crossover",
    },
    {
        "type": "OverIndicator",
        "description": "Indicator is above reference",
        "requires": ["indicator", "reference"],
        "category": "comparison",
    },
    {
        "type": "UnderIndicator",
        "description": "Indicator is below reference",
        "requires": ["indicator", "reference"],
        "category": "comparison",
    },
    {
        "type": "IsRising",
        "description": "Indicator is rising over N bars",
        "requires": ["indicator", "bars"],
        "category": "trend",
    },
    {
        "type": "IsFalling",
        "description": "Indicator is falling over N bars",
        "requires": ["indicator", "bars"],
        "category": "trend",
    },
    {
        "type": "And",
        "description": "Both conditions must be true",
        "requires": ["left", "right"],
        "category": "logical",
    },
    {
        "type": "Or",
        "description": "Either condition must be true",
        "requires": ["left", "right"],
        "category": "logical",
    },
]

CONDITION_TYPE_SET = frozenset(c["type"] for c in CONDITION_TYPES)


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------


class IndicatorConfigDTO(BaseModel):
    id: str = Field(..., description="Unique identifier for this indicator instance")
    type: str = Field(..., description="Indicator type (RSI, MACD, SMA, etc.)")
    input: str = Field("close", description="Price input (close, high, low, volume)")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Indicator parameters"
    )

    @validator("type")
    def validate_type(cls, v):
        if v not in INDICATOR_TYPE_SET:
            raise ValueError(
                f"Unknown indicator type '{v}'. "
                f"Valid: {', '.join(sorted(INDICATOR_TYPE_SET))}"
            )
        return v


class ConditionConfigDTO(BaseModel):
    type: str = Field(
        ..., description="Condition type (CrossedUp, OverIndicator, etc.)"
    )
    indicator: Optional[str] = Field(None, description="Reference to an indicator id")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Condition parameters"
    )

    @validator("type")
    def validate_type(cls, v):
        if v not in CONDITION_TYPE_SET:
            raise ValueError(
                f"Unknown condition type '{v}'. "
                f"Valid: {', '.join(sorted(CONDITION_TYPE_SET))}"
            )
        return v


class StrategyConfigDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Strategy name")
    description: str = Field("", max_length=2000, description="Strategy description")
    category: str = Field("multi_indicator", description="Strategy category")
    indicators: List[IndicatorConfigDTO] = Field(
        ..., min_items=1, max_items=20, description="Indicator configurations"
    )
    entry_conditions: List[ConditionConfigDTO] = Field(
        ..., min_items=1, max_items=20, description="Entry conditions"
    )
    exit_conditions: List[ConditionConfigDTO] = Field(
        ..., min_items=1, max_items=20, description="Exit conditions"
    )
    tags: List[str] = Field(default_factory=list, max_items=10, description="Tags")


class UpdateStrategyConfigDTO(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = None
    indicators: Optional[List[IndicatorConfigDTO]] = None
    entry_conditions: Optional[List[ConditionConfigDTO]] = None
    exit_conditions: Optional[List[ConditionConfigDTO]] = None
    tags: Optional[List[str]] = None
    version: int = Field(..., description="Current version for optimistic locking")


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair (e.g. BTC/USD)")
    timeframe: str = Field("1h", description="Candle timeframe")
    start_date: Optional[str] = Field(None, description="Backtest start (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Backtest end (YYYY-MM-DD)")


class PublishToMarketplaceRequest(BaseModel):
    price: float = Field(0.0, ge=0, description="Listing price")
    author: Optional[str] = Field(None, description="Author display name")


# ---------------------------------------------------------------------------
# Validation Logic
# ---------------------------------------------------------------------------


def validate_strategy_config(config: StrategyConfigDTO) -> List[Dict[str, str]]:
    """Validate a strategy configuration for logical correctness."""
    errors = []

    # Check indicator IDs are unique
    indicator_ids = [ind.id for ind in config.indicators]
    if len(indicator_ids) != len(set(indicator_ids)):
        errors.append(
            {"field": "indicators", "message": "Indicator IDs must be unique"}
        )

    indicator_id_set = set(indicator_ids)

    # Validate entry conditions reference valid indicators
    for i, cond in enumerate(config.entry_conditions):
        if cond.indicator and cond.indicator not in indicator_id_set:
            errors.append(
                {
                    "field": f"entry_conditions[{i}].indicator",
                    "message": f"References unknown indicator '{cond.indicator}'",
                }
            )
        ref = cond.params.get("reference")
        if ref and isinstance(ref, str) and ref not in indicator_id_set:
            errors.append(
                {
                    "field": f"entry_conditions[{i}].params.reference",
                    "message": f"References unknown indicator '{ref}'",
                }
            )

    # Validate exit conditions reference valid indicators
    for i, cond in enumerate(config.exit_conditions):
        if cond.indicator and cond.indicator not in indicator_id_set:
            errors.append(
                {
                    "field": f"exit_conditions[{i}].indicator",
                    "message": f"References unknown indicator '{cond.indicator}'",
                }
            )
        ref = cond.params.get("reference")
        if ref and isinstance(ref, str) and ref not in indicator_id_set:
            errors.append(
                {
                    "field": f"exit_conditions[{i}].params.reference",
                    "message": f"References unknown indicator '{ref}'",
                }
            )

    # Validate indicator params against catalog
    catalog_map = {ind["type"]: ind for ind in INDICATOR_CATALOG}
    for i, ind in enumerate(config.indicators):
        spec = catalog_map.get(ind.type)
        if not spec:
            continue
        for param_spec in spec["params"]:
            pname = param_spec["name"]
            if pname in ind.params:
                val = ind.params[pname]
                pmin = param_spec.get("min")
                pmax = param_spec.get("max")
                if pmin is not None and val < pmin:
                    errors.append(
                        {
                            "field": f"indicators[{i}].params.{pname}",
                            "message": f"Value {val} below minimum {pmin}",
                        }
                    )
                if pmax is not None and val > pmax:
                    errors.append(
                        {
                            "field": f"indicators[{i}].params.{pname}",
                            "message": f"Value {val} above maximum {pmax}",
                        }
                    )

    return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strategy_row_to_dict(row) -> dict:
    """Convert a strategy DB row to a serialisable dict."""
    item = dict(row)
    for key in ("id", "user_id"):
        if key in item:
            item[key] = str(item[key])
    for json_key in (
        "indicators",
        "entry_conditions",
        "exit_conditions",
        "tags",
        "backtest_results",
    ):
        if json_key in item and isinstance(item[json_key], str):
            item[json_key] = json.loads(item[json_key])
    for ts_key in ("created_at", "updated_at"):
        if item.get(ts_key):
            item[ts_key] = item[ts_key].isoformat()
    return item


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the User Strategy Builder API."""
    app = FastAPI(
        title="User Strategy Builder API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategy-builder",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("strategy-builder-api", check_deps))

    # ===================================================================
    # INDICATOR PALETTE — Browse available indicators
    # ===================================================================
    palette_router = APIRouter(prefix="/palette", tags=["Indicator Palette"])

    @palette_router.get("/indicators")
    async def list_indicators(
        category: Optional[str] = Query(None, description="Filter by category"),
    ):
        """List available indicators with parameter descriptions."""
        items = INDICATOR_CATALOG
        if category:
            items = [ind for ind in items if ind["category"] == category]
        return collection_response(items, "indicator_spec", total=len(items))

    @palette_router.get("/indicators/{indicator_type}")
    async def get_indicator(indicator_type: str):
        """Get detailed info for a specific indicator type."""
        for ind in INDICATOR_CATALOG:
            if ind["type"] == indicator_type:
                return success_response(ind, "indicator_spec")
        return not_found("Indicator", indicator_type)

    @palette_router.get("/conditions")
    async def list_conditions():
        """List available condition types."""
        return collection_response(
            CONDITION_TYPES, "condition_spec", total=len(CONDITION_TYPES)
        )

    @palette_router.get("/categories")
    async def list_indicator_categories():
        """List indicator categories."""
        categories = sorted(set(ind["category"] for ind in INDICATOR_CATALOG))
        items = [
            {
                "name": c,
                "count": sum(1 for i in INDICATOR_CATALOG if i["category"] == c),
            }
            for c in categories
        ]
        return collection_response(items, "indicator_category", total=len(items))

    app.include_router(palette_router)

    # ===================================================================
    # STRATEGY CRUD — Create, read, update, delete user strategies
    # ===================================================================
    strategy_router = APIRouter(prefix="/strategies", tags=["Strategy Builder"])

    @strategy_router.post("", status_code=201)
    async def create_strategy(
        body: StrategyConfigDTO,
        x_user_id: str = Header(..., alias="X-User-Id"),
    ):
        """Create a new user strategy configuration."""
        # Validate config
        errors = validate_strategy_config(body)
        if errors:
            return validation_error("Strategy config has errors", details=errors)

        strategy_id = str(uuid.uuid4())
        query = """
            INSERT INTO user_strategies
                (id, user_id, name, description, category, indicators,
                 entry_conditions, exit_conditions, tags, version)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb, 1)
            RETURNING id, user_id, name, description, category, indicators,
                      entry_conditions, exit_conditions, tags, version,
                      is_published, backtest_results, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    strategy_id,
                    x_user_id,
                    body.name,
                    body.description,
                    body.category,
                    json.dumps([ind.dict() for ind in body.indicators]),
                    json.dumps([cond.dict() for cond in body.entry_conditions]),
                    json.dumps([cond.dict() for cond in body.exit_conditions]),
                    json.dumps(body.tags),
                )
        except Exception as e:
            logger.error("Failed to create strategy: %s", e)
            return server_error(str(e))

        item = _strategy_row_to_dict(row)
        return success_response(
            item, "user_strategy", resource_id=item["id"], status_code=201
        )

    @strategy_router.get("")
    async def list_strategies(
        x_user_id: str = Header(..., alias="X-User-Id"),
        pagination: PaginationParams = Depends(),
        category: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
    ):
        """List user's strategies."""
        conditions = ["user_id = $1::uuid"]
        params: list = [x_user_id]
        idx = 1

        if category:
            idx += 1
            conditions.append(f"category = ${idx}")
            params.append(category)
        if search:
            idx += 1
            conditions.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
            params.append(f"%{search}%")

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT id, user_id, name, description, category, indicators,
                   entry_conditions, exit_conditions, tags, version,
                   is_published, backtest_results, created_at, updated_at
            FROM user_strategies
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM user_strategies WHERE {where}"

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = [_strategy_row_to_dict(row) for row in rows]
        return collection_response(
            items,
            "user_strategy",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @strategy_router.get("/{strategy_id}")
    async def get_strategy(
        strategy_id: str,
        x_user_id: str = Header(..., alias="X-User-Id"),
    ):
        """Get a specific user strategy."""
        query = """
            SELECT id, user_id, name, description, category, indicators,
                   entry_conditions, exit_conditions, tags, version,
                   is_published, backtest_results, created_at, updated_at
            FROM user_strategies
            WHERE id = $1::uuid AND user_id = $2::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, strategy_id, x_user_id)
        if not row:
            return not_found("Strategy", strategy_id)
        item = _strategy_row_to_dict(row)
        return success_response(item, "user_strategy", resource_id=item["id"])

    @strategy_router.put("/{strategy_id}")
    async def update_strategy(
        strategy_id: str,
        body: UpdateStrategyConfigDTO,
        x_user_id: str = Header(..., alias="X-User-Id"),
    ):
        """Update a user strategy with optimistic locking."""
        # If indicators/conditions are provided, validate them
        if body.indicators and body.entry_conditions and body.exit_conditions:
            temp_config = StrategyConfigDTO(
                name=body.name or "temp",
                indicators=body.indicators,
                entry_conditions=body.entry_conditions,
                exit_conditions=body.exit_conditions,
            )
            errors = validate_strategy_config(temp_config)
            if errors:
                return validation_error("Strategy config has errors", details=errors)

        set_clauses = ["version = version + 1", "updated_at = NOW()"]
        params: list = []
        idx = 0

        for field, value in [
            ("name", body.name),
            ("description", body.description),
            ("category", body.category),
        ]:
            if value is not None:
                idx += 1
                set_clauses.append(f"{field} = ${idx}")
                params.append(value)

        for field, items in [
            ("indicators", body.indicators),
            ("entry_conditions", body.entry_conditions),
            ("exit_conditions", body.exit_conditions),
            ("tags", body.tags),
        ]:
            if items is not None:
                idx += 1
                set_clauses.append(f"{field} = ${idx}::jsonb")
                if field == "tags":
                    params.append(json.dumps(items))
                else:
                    params.append(json.dumps([i.dict() for i in items]))

        idx += 1
        strategy_idx = idx
        idx += 1
        user_idx = idx
        idx += 1
        version_idx = idx
        params.extend([strategy_id, x_user_id, body.version])

        query = f"""
            UPDATE user_strategies
            SET {', '.join(set_clauses)}
            WHERE id = ${strategy_idx}::uuid
              AND user_id = ${user_idx}::uuid
              AND version = ${version_idx}
            RETURNING id, user_id, name, description, category, indicators,
                      entry_conditions, exit_conditions, tags, version,
                      is_published, backtest_results, created_at, updated_at
        """

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            # Check if strategy exists to distinguish 404 from 409
            async with db_pool.acquire() as conn:
                exists = await conn.fetchrow(
                    "SELECT version FROM user_strategies WHERE id = $1::uuid AND user_id = $2::uuid",
                    strategy_id,
                    x_user_id,
                )
            if not exists:
                return not_found("Strategy", strategy_id)
            return error_response(
                "CONCURRENT_MODIFICATION",
                f"Strategy was modified. Current version: {exists['version']}",
                status_code=409,
            )

        item = _strategy_row_to_dict(row)
        return success_response(item, "user_strategy", resource_id=item["id"])

    @strategy_router.delete("/{strategy_id}", status_code=204)
    async def delete_strategy(
        strategy_id: str,
        x_user_id: str = Header(..., alias="X-User-Id"),
    ):
        """Delete a user strategy."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM user_strategies WHERE id = $1::uuid AND user_id = $2::uuid RETURNING id",
                strategy_id,
                x_user_id,
            )
        if not row:
            return not_found("Strategy", strategy_id)
        return None

    # ===================================================================
    # VALIDATION — Validate strategy config before saving
    # ===================================================================

    @strategy_router.post("/validate")
    async def validate_config(body: StrategyConfigDTO):
        """Validate a strategy configuration without saving."""
        errors = validate_strategy_config(body)
        result = {
            "valid": len(errors) == 0,
            "errors": errors,
            "indicator_count": len(body.indicators),
            "entry_condition_count": len(body.entry_conditions),
            "exit_condition_count": len(body.exit_conditions),
        }
        return success_response(result, "validation_result")

    # ===================================================================
    # BACKTEST — Run backtest on a user strategy
    # ===================================================================

    @strategy_router.post("/{strategy_id}/backtest")
    async def backtest_strategy(
        strategy_id: str,
        body: BacktestRequest,
        x_user_id: str = Header(..., alias="X-User-Id"),
    ):
        """Run a backtest on a user-created strategy."""
        # Fetch strategy
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, indicators, entry_conditions, exit_conditions
                   FROM user_strategies
                   WHERE id = $1::uuid AND user_id = $2::uuid""",
                strategy_id,
                x_user_id,
            )
        if not row:
            return not_found("Strategy", strategy_id)

        indicators = row["indicators"]
        entry_conditions = row["entry_conditions"]
        exit_conditions = row["exit_conditions"]
        if isinstance(indicators, str):
            indicators = json.loads(indicators)
        if isinstance(entry_conditions, str):
            entry_conditions = json.loads(entry_conditions)
        if isinstance(exit_conditions, str):
            exit_conditions = json.loads(exit_conditions)

        # Build the strategy config dict compatible with ConfigDrivenStrategyBuilder
        strategy_config = {
            "name": f"user_{strategy_id}",
            "indicators": indicators,
            "entryConditions": entry_conditions,
            "exitConditions": exit_conditions,
        }

        # Fetch candle data for the symbol
        candle_query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE currency_pair = $1
        """
        candle_params = [body.symbol]
        idx = 1
        if body.start_date:
            idx += 1
            candle_query += f" AND timestamp >= ${idx}::timestamp"
            candle_params.append(body.start_date)
        if body.end_date:
            idx += 1
            candle_query += f" AND timestamp <= ${idx}::timestamp"
            candle_params.append(body.end_date)
        candle_query += " ORDER BY timestamp ASC LIMIT 10000"

        async with db_pool.acquire() as conn:
            candle_rows = await conn.fetch(candle_query, *candle_params)

        if len(candle_rows) < 30:
            return validation_error(
                f"Insufficient candle data for {body.symbol}. "
                f"Found {len(candle_rows)} candles, need at least 30."
            )

        # Compute simple backtest metrics from strategy signals
        candles = [dict(r) for r in candle_rows]
        backtest_result = _run_simple_backtest(
            candles, indicators, entry_conditions, exit_conditions
        )

        # Store backtest results
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE user_strategies
                   SET backtest_results = $1::jsonb, updated_at = NOW()
                   WHERE id = $2::uuid""",
                json.dumps(backtest_result),
                strategy_id,
            )

        return success_response(backtest_result, "backtest_result")

    # ===================================================================
    # PUBLISH — Share strategy to marketplace
    # ===================================================================

    @strategy_router.post("/{strategy_id}/publish", status_code=201)
    async def publish_strategy(
        strategy_id: str,
        body: PublishToMarketplaceRequest,
        x_user_id: str = Header(..., alias="X-User-Id"),
    ):
        """Publish a user strategy to the marketplace."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, name, description, category, tags,
                          backtest_results, is_published
                   FROM user_strategies
                   WHERE id = $1::uuid AND user_id = $2::uuid""",
                strategy_id,
                x_user_id,
            )
        if not row:
            return not_found("Strategy", strategy_id)

        if row["is_published"]:
            return conflict("Strategy is already published")

        backtest_results = row["backtest_results"]
        if isinstance(backtest_results, str):
            backtest_results = json.loads(backtest_results)

        performance_stats = {}
        if backtest_results:
            performance_stats = {
                k: backtest_results[k]
                for k in (
                    "total_return_pct",
                    "sharpe_ratio",
                    "win_rate",
                    "max_drawdown_pct",
                    "total_trades",
                )
                if k in backtest_results
            }

        tags = row["tags"]
        if isinstance(tags, str):
            tags = json.loads(tags)

        author = body.author or x_user_id

        # Insert into marketplace_listings
        try:
            async with db_pool.acquire() as conn:
                listing_row = await conn.fetchrow(
                    """INSERT INTO marketplace_listings
                        (strategy_id, name, author, description, category, tags,
                         performance_stats, price)
                       VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8)
                       RETURNING id, strategy_id, name, author, created_at""",
                    strategy_id,
                    row["name"],
                    author,
                    row["description"] or "",
                    row["category"] or "multi_indicator",
                    tags if isinstance(tags, list) else [],
                    json.dumps(performance_stats),
                    body.price,
                )
                # Mark strategy as published
                await conn.execute(
                    "UPDATE user_strategies SET is_published = TRUE WHERE id = $1::uuid",
                    strategy_id,
                )
        except asyncpg.UniqueViolationError:
            return conflict("Strategy is already listed in the marketplace")
        except Exception as e:
            logger.error("Failed to publish strategy: %s", e)
            return server_error(str(e))

        item = dict(listing_row)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()

        return success_response(
            item, "marketplace_listing", resource_id=item["id"], status_code=201
        )

    app.include_router(strategy_router)

    return app


# ---------------------------------------------------------------------------
# Simple backtest engine (indicator-agnostic signal-based)
# ---------------------------------------------------------------------------


def _run_simple_backtest(
    candles: List[Dict],
    indicators: Any,
    entry_conditions: Any,
    exit_conditions: Any,
) -> Dict[str, Any]:
    """
    Run a simplified backtest using indicator-based entry/exit signals.

    This produces approximate metrics. For production accuracy, the config
    should be forwarded to the gRPC BacktestingService (VectorBT engine).
    """
    if not candles:
        return {"error": "No candle data"}

    closes = [float(c["close"]) for c in candles]
    n = len(closes)

    # Generate simple signals based on first indicator
    entries = [False] * n
    exits = [False] * n

    # Use a simple moving average crossover approximation
    short_period = 10
    long_period = 30

    if indicators:
        first_ind = indicators[0] if isinstance(indicators, list) else indicators
        if isinstance(first_ind, dict):
            params = first_ind.get("params", {})
            if "period" in params:
                short_period = min(int(params["period"]), n // 3)
            if "shortPeriod" in params:
                short_period = int(params["shortPeriod"])
            if "longPeriod" in params:
                long_period = int(params["longPeriod"])

    short_period = max(2, min(short_period, n // 3))
    long_period = max(short_period + 1, min(long_period, n // 2))

    # Compute SMAs
    short_sma = _sma(closes, short_period)
    long_sma = _sma(closes, long_period)

    # Generate crossover signals
    for i in range(long_period, n):
        if short_sma[i] > long_sma[i] and short_sma[i - 1] <= long_sma[i - 1]:
            entries[i] = True
        elif short_sma[i] < long_sma[i] and short_sma[i - 1] >= long_sma[i - 1]:
            exits[i] = True

    # Simulate trades
    trades = []
    in_position = False
    entry_price = 0.0

    for i in range(n):
        if entries[i] and not in_position:
            in_position = True
            entry_price = closes[i]
        elif exits[i] and in_position:
            in_position = False
            pnl_pct = ((closes[i] - entry_price) / entry_price) * 100
            trades.append(
                {
                    "entry_price": entry_price,
                    "exit_price": closes[i],
                    "pnl_pct": pnl_pct,
                }
            )

    # Close open position at end
    if in_position:
        pnl_pct = ((closes[-1] - entry_price) / entry_price) * 100
        trades.append(
            {"entry_price": entry_price, "exit_price": closes[-1], "pnl_pct": pnl_pct}
        )

    # Compute metrics
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": 0,
            "candles_analyzed": n,
            "symbol": (
                candles[0].get("currency_pair", "unknown") if candles else "unknown"
            ),
        }

    pnls = [t["pnl_pct"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    total_return = sum(pnls)
    win_rate = wins / total_trades if total_trades > 0 else 0

    # Sharpe ratio approximation
    avg_pnl = statistics.mean(pnls) if pnls else 0
    std_pnl = statistics.stdev(pnls) if len(pnls) > 1 else 1
    sharpe = (avg_pnl / std_pnl) if std_pnl > 0 else 0

    # Max drawdown from equity curve
    equity = [0.0]
    for p in pnls:
        equity.append(equity[-1] + p)
    peak = equity[0]
    max_dd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd

    return {
        "total_return_pct": round(total_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "win_rate": round(win_rate, 4),
        "max_drawdown_pct": round(-max_dd, 2),
        "total_trades": total_trades,
        "trades": trades[:50],  # Return first 50 trades for display
        "candles_analyzed": n,
    }


def _sma(values: List[float], period: int) -> List[float]:
    """Simple moving average."""
    result = [0.0] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = sum(values[i - period + 1 : i + 1]) / period
    return result
