"""
Stock screener engine — evaluates filter criteria against market data.

Supports filtering by price range, volume, RSI, moving averages, and sector.
Each matched instrument receives a score based on how many criteria it satisfies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FilterOperator(str, Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    BETWEEN = "between"


@dataclass
class FilterCriterion:
    field: str
    operator: FilterOperator
    value: Any
    value_max: Optional[Any] = None  # used for BETWEEN


@dataclass
class ScanRequest:
    filters: List[FilterCriterion]
    sector: Optional[str] = None
    limit: int = 50


@dataclass
class ScanResult:
    symbol: str
    current_price: float
    volume: float
    matched_criteria: List[str]
    score: float


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    volume: float
    rsi: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    sector: Optional[str] = None
    change_pct: Optional[float] = None


# Map user-facing field names to MarketSnapshot attributes
_FIELD_MAP = {
    "price": "price",
    "volume": "volume",
    "rsi": "rsi",
    "sma_20": "sma_20",
    "sma_50": "sma_50",
    "sma_200": "sma_200",
    "ema_12": "ema_12",
    "ema_26": "ema_26",
    "change_pct": "change_pct",
}


def _evaluate_criterion(snapshot: MarketSnapshot, criterion: FilterCriterion) -> bool:
    """Check whether a single criterion matches the snapshot."""
    attr_name = _FIELD_MAP.get(criterion.field)
    if attr_name is None:
        return False

    actual = getattr(snapshot, attr_name, None)
    if actual is None:
        return False

    op = criterion.operator
    val = criterion.value

    if op == FilterOperator.GT:
        return actual > val
    elif op == FilterOperator.GTE:
        return actual >= val
    elif op == FilterOperator.LT:
        return actual < val
    elif op == FilterOperator.LTE:
        return actual <= val
    elif op == FilterOperator.EQ:
        return actual == val
    elif op == FilterOperator.BETWEEN:
        if criterion.value_max is None:
            return False
        return val <= actual <= criterion.value_max

    return False


def run_scan(snapshots: List[MarketSnapshot], request: ScanRequest) -> List[ScanResult]:
    """Run a scan against a list of market snapshots.

    Returns matching instruments sorted by score (descending).
    """
    results: List[ScanResult] = []

    for snap in snapshots:
        # Sector filter
        if request.sector and snap.sector != request.sector:
            continue

        matched: List[str] = []
        for criterion in request.filters:
            if _evaluate_criterion(snap, criterion):
                desc = f"{criterion.field} {criterion.operator.value} {criterion.value}"
                if criterion.operator == FilterOperator.BETWEEN:
                    desc = f"{criterion.field} between {criterion.value} and {criterion.value_max}"
                matched.append(desc)

        if matched:
            score = len(matched) / len(request.filters) if request.filters else 0.0
            results.append(
                ScanResult(
                    symbol=snap.symbol,
                    current_price=snap.price,
                    volume=snap.volume,
                    matched_criteria=matched,
                    score=round(score, 4),
                )
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[: request.limit]


# --- Built-in Presets ---

BUILT_IN_PRESETS: Dict[str, Dict[str, Any]] = {
    "high_volume_breakout": {
        "id": "high_volume_breakout",
        "name": "High Volume Breakout",
        "description": "Stocks with volume > 2x average and price above SMA 20",
        "filters": [
            {"field": "volume", "operator": "gte", "value": 1_000_000},
            {"field": "price", "operator": "gt", "value": 0},
        ],
        "sector": None,
    },
    "oversold_bounce": {
        "id": "oversold_bounce",
        "name": "Oversold Bounce",
        "description": "RSI below 30, potential reversal candidates",
        "filters": [
            {"field": "rsi", "operator": "lte", "value": 30},
            {"field": "volume", "operator": "gte", "value": 500_000},
        ],
        "sector": None,
    },
    "golden_cross": {
        "id": "golden_cross",
        "name": "Golden Cross",
        "description": "SMA 50 crossing above SMA 200",
        "filters": [
            {"field": "sma_50", "operator": "gt", "value": 0},
            {"field": "sma_200", "operator": "gt", "value": 0},
        ],
        "sector": None,
    },
    "overbought": {
        "id": "overbought",
        "name": "Overbought",
        "description": "RSI above 70, potential pullback candidates",
        "filters": [
            {"field": "rsi", "operator": "gte", "value": 70},
        ],
        "sector": None,
    },
    "penny_stocks": {
        "id": "penny_stocks",
        "name": "Penny Stocks",
        "description": "Low-priced stocks with notable volume",
        "filters": [
            {"field": "price", "operator": "lte", "value": 5.0},
            {"field": "volume", "operator": "gte", "value": 100_000},
        ],
        "sector": None,
    },
}
