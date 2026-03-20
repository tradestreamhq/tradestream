"""
Correlation and Pair Analysis Engine.

Provides rolling correlation, cointegration testing (Engle-Granger),
spread calculation, and z-score computation for pair trading strategies.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class PairAnalysis:
    """Result of a pair analysis between two assets."""

    pair1: str
    pair2: str
    correlation: float
    cointegrated: bool
    p_value: float
    spread_mean: float
    spread_std: float
    current_zscore: float
    hedge_ratio: float


def rolling_correlation(
    series1: pd.Series,
    series2: pd.Series,
    window: int = 30,
) -> pd.Series:
    """Compute rolling Pearson correlation between two price series.

    Args:
        series1: First price series.
        series2: Second price series.
        window: Rolling window size.

    Returns:
        Series of rolling correlation values.
    """
    return series1.rolling(window=window).corr(series2)


def correlation_matrix(price_data: pd.DataFrame) -> pd.DataFrame:
    """Compute NxN Pearson correlation matrix for all columns.

    Args:
        price_data: DataFrame with asset prices as columns.

    Returns:
        NxN correlation matrix DataFrame.
    """
    return price_data.corr(method="pearson")


def _ols_residuals(y: np.ndarray, x: np.ndarray) -> Tuple[np.ndarray, float]:
    """Run OLS regression y = alpha + beta*x, return residuals and beta."""
    x_with_const = np.column_stack([np.ones(len(x)), x])
    coeffs, _, _, _ = np.linalg.lstsq(x_with_const, y, rcond=None)
    residuals = y - x_with_const @ coeffs
    return residuals, coeffs[1]


def _adf_test(residuals: np.ndarray) -> float:
    """Simplified Augmented Dickey-Fuller test returning p-value.

    Tests H0: unit root exists (non-stationary) vs H1: stationary.
    Uses the Dickey-Fuller regression: delta_y = gamma * y_{t-1} + error.
    """
    y = residuals[1:]
    y_lag = residuals[:-1]
    dy = y - y_lag

    n = len(dy)
    x = y_lag.reshape(-1, 1)
    x_with_const = np.column_stack([np.ones(n), x])

    coeffs, _, _, _ = np.linalg.lstsq(x_with_const, dy, rcond=None)
    gamma = coeffs[1]

    predicted = x_with_const @ coeffs
    sse = np.sum((dy - predicted) ** 2)
    se_gamma = np.sqrt(sse / (n - 2) / np.sum((y_lag - y_lag.mean()) ** 2))

    if se_gamma == 0:
        return 1.0

    adf_stat = gamma / se_gamma

    # Approximate p-value using MacKinnon critical values for no trend
    # Critical values: 1% = -3.43, 5% = -2.86, 10% = -2.57
    if adf_stat < -3.43:
        return 0.005
    elif adf_stat < -2.86:
        return 0.03
    elif adf_stat < -2.57:
        return 0.07
    elif adf_stat < -1.94:
        return 0.15
    else:
        return 0.50


def engle_granger_test(
    series1: np.ndarray,
    series2: np.ndarray,
) -> Tuple[bool, float, float]:
    """Engle-Granger two-step cointegration test.

    Step 1: OLS regression of series1 on series2.
    Step 2: ADF test on residuals.

    Args:
        series1: Price series for first asset.
        series2: Price series for second asset.

    Returns:
        Tuple of (is_cointegrated, p_value, hedge_ratio).
    """
    residuals, hedge_ratio = _ols_residuals(series1, series2)
    p_value = _adf_test(residuals)
    is_cointegrated = p_value < 0.05
    return is_cointegrated, p_value, hedge_ratio


def compute_spread(
    series1: np.ndarray,
    series2: np.ndarray,
    hedge_ratio: float,
) -> np.ndarray:
    """Compute the spread between two assets given a hedge ratio.

    spread = series1 - hedge_ratio * series2
    """
    return series1 - hedge_ratio * series2


def compute_zscore(spread: np.ndarray, window: int = 30) -> np.ndarray:
    """Compute rolling z-score of a spread series.

    Args:
        spread: The spread series.
        window: Lookback window for mean and std.

    Returns:
        Array of z-scores (NaN for initial window period).
    """
    s = pd.Series(spread)
    mean = s.rolling(window=window).mean()
    std = s.rolling(window=window).std()
    zscore = (s - mean) / std
    return zscore.values


def analyze_pair(
    pair1_name: str,
    pair2_name: str,
    prices1: np.ndarray,
    prices2: np.ndarray,
    zscore_window: int = 30,
) -> PairAnalysis:
    """Full pair analysis: correlation, cointegration, spread, z-score.

    Args:
        pair1_name: Symbol name for first asset.
        pair2_name: Symbol name for second asset.
        prices1: Price array for first asset.
        prices2: Price array for second asset.
        zscore_window: Window for z-score rolling calculation.

    Returns:
        PairAnalysis dataclass with all metrics.
    """
    correlation = float(np.corrcoef(prices1, prices2)[0, 1])
    cointegrated, p_value, hedge_ratio = engle_granger_test(prices1, prices2)
    spread = compute_spread(prices1, prices2, hedge_ratio)
    zscores = compute_zscore(spread, window=zscore_window)

    # Use last valid z-score
    valid_zscores = zscores[~np.isnan(zscores)]
    current_zscore = float(valid_zscores[-1]) if len(valid_zscores) > 0 else 0.0

    return PairAnalysis(
        pair1=pair1_name,
        pair2=pair2_name,
        correlation=round(correlation, 6),
        cointegrated=cointegrated,
        p_value=round(p_value, 6),
        spread_mean=round(float(np.mean(spread)), 6),
        spread_std=round(float(np.std(spread)), 6),
        current_zscore=round(current_zscore, 6),
        hedge_ratio=round(hedge_ratio, 6),
    )


def find_cointegrated_pairs(
    price_data: pd.DataFrame,
    significance: float = 0.05,
) -> List[PairAnalysis]:
    """Find all cointegrated pairs from a price DataFrame.

    Args:
        price_data: DataFrame where each column is an asset's price series.
        significance: P-value threshold for cointegration.

    Returns:
        List of PairAnalysis for cointegrated pairs.
    """
    symbols = list(price_data.columns)
    results = []

    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            s1 = price_data[symbols[i]].dropna().values
            s2 = price_data[symbols[j]].dropna().values

            min_len = min(len(s1), len(s2))
            if min_len < 30:
                continue

            s1 = s1[:min_len]
            s2 = s2[:min_len]

            analysis = analyze_pair(symbols[i], symbols[j], s1, s2)
            if analysis.p_value < significance:
                results.append(analysis)

    results.sort(key=lambda x: x.p_value)
    return results
