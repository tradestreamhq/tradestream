"""
Correlation matrix calculator.

Computes rolling pairwise correlations for portfolio assets using
daily returns data and detects correlation regime changes.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Threshold for flagging a correlation breakdown (absolute change)
BREAKDOWN_THRESHOLD = 0.3


def compute_returns(prices: List[float]) -> np.ndarray:
    """Compute daily log returns from a price series."""
    arr = np.array(prices, dtype=np.float64)
    if len(arr) < 2:
        return np.array([])
    return np.diff(np.log(arr))


def compute_pairwise_correlation(
    returns_a: np.ndarray,
    returns_b: np.ndarray,
) -> Optional[float]:
    """Compute Pearson correlation between two return series.

    Returns None if either series has insufficient data or zero variance.
    """
    min_len = min(len(returns_a), len(returns_b))
    if min_len < 5:
        return None

    a = returns_a[-min_len:]
    b = returns_b[-min_len:]

    std_a = np.std(a)
    std_b = np.std(b)
    if std_a == 0 or std_b == 0:
        return None

    corr = float(np.corrcoef(a, b)[0, 1])
    if np.isnan(corr):
        return None
    return round(corr, 6)


def build_correlation_matrix(
    symbols: List[str],
    price_data: Dict[str, List[float]],
    window: int,
) -> Dict[str, Dict[str, Optional[float]]]:
    """Build a full correlation matrix for the given symbols and window.

    Args:
        symbols: List of asset symbols.
        price_data: Mapping of symbol to price series (most recent last).
        window: Number of data points for the rolling window.

    Returns:
        Nested dict: matrix[symbol_a][symbol_b] = correlation.
    """
    returns_cache: Dict[str, np.ndarray] = {}
    for sym in symbols:
        prices = price_data.get(sym, [])
        # Take only the last `window+1` prices to get `window` returns
        truncated = prices[-(window + 1) :] if len(prices) > window + 1 else prices
        returns_cache[sym] = compute_returns(truncated)

    matrix: Dict[str, Dict[str, Optional[float]]] = {}
    for sym_a in symbols:
        matrix[sym_a] = {}
        for sym_b in symbols:
            if sym_a == sym_b:
                matrix[sym_a][sym_b] = 1.0
            elif sym_b in matrix and sym_a in matrix[sym_b]:
                # Symmetric — reuse already computed value
                matrix[sym_a][sym_b] = matrix[sym_b][sym_a]
            else:
                matrix[sym_a][sym_b] = compute_pairwise_correlation(
                    returns_cache[sym_a], returns_cache[sym_b]
                )
    return matrix


def detect_breakdowns(
    current_matrix: Dict[str, Dict[str, Optional[float]]],
    historical_matrix: Dict[str, Dict[str, Optional[float]]],
    symbols: List[str],
    window: str,
    threshold: float = BREAKDOWN_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Detect significant changes between current and historical correlations.

    Returns a list of breakdown dicts for pairs that exceed the threshold.
    """
    breakdowns: List[Dict[str, Any]] = []
    seen = set()

    for sym_a in symbols:
        for sym_b in symbols:
            if sym_a >= sym_b:
                continue
            pair = (sym_a, sym_b)
            if pair in seen:
                continue
            seen.add(pair)

            current = current_matrix.get(sym_a, {}).get(sym_b)
            historical = historical_matrix.get(sym_a, {}).get(sym_b)

            if current is None or historical is None:
                continue

            change = abs(current - historical)
            if change >= threshold:
                breakdowns.append(
                    {
                        "symbol_a": sym_a,
                        "symbol_b": sym_b,
                        "previous_correlation": round(historical, 6),
                        "current_correlation": round(current, 6),
                        "change": round(change, 6),
                        "window": window,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
    return breakdowns
