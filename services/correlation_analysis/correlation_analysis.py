"""Correlation analysis for portfolio diversification.

Calculates rolling correlation matrices between asset pairs, detects
correlation regime changes, identifies highly correlated clusters, and
generates diversification recommendations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CorrelationPair:
    """Correlation between two assets."""

    asset_a: str
    asset_b: str
    correlation: float
    lookback_periods: int


@dataclass
class CorrelationRegimeChange:
    """Detected change in correlation regime between two assets."""

    asset_a: str
    asset_b: str
    previous_correlation: float
    current_correlation: float
    change: float
    is_significant: bool


@dataclass
class CorrelationCluster:
    """Group of highly correlated assets."""

    assets: List[str]
    avg_intra_correlation: float


@dataclass
class DiversificationRecommendation:
    """Recommendation for improving portfolio diversification."""

    message: str
    severity: str  # "high", "medium", "low"
    affected_assets: List[str]


@dataclass
class CorrelationAlert:
    """Alert when portfolio correlation exceeds threshold."""

    metric: str
    value: float
    threshold: float
    message: str


@dataclass
class CorrelationAnalysisResult:
    """Complete result of correlation analysis."""

    correlation_matrix: Dict[str, Dict[str, float]]
    regime_changes: List[CorrelationRegimeChange]
    clusters: List[CorrelationCluster]
    recommendations: List[DiversificationRecommendation]
    alerts: List[CorrelationAlert]
    avg_pairwise_correlation: float


DEFAULT_SHORT_LOOKBACK = 30
DEFAULT_LONG_LOOKBACK = 90
DEFAULT_CORRELATION_THRESHOLD = 0.7
DEFAULT_REGIME_CHANGE_THRESHOLD = 0.3
DEFAULT_PORTFOLIO_CORRELATION_ALERT = 0.6


def compute_rolling_correlation(
    returns_a: np.ndarray,
    returns_b: np.ndarray,
    window: int,
) -> np.ndarray:
    """Compute rolling Pearson correlation between two return series.

    Args:
        returns_a: Array of returns for asset A.
        returns_b: Array of returns for asset B.
        window: Rolling window size.

    Returns:
        Array of rolling correlations. Length = len(returns) - window + 1.
    """
    n = len(returns_a)
    if n < window or window < 2:
        return np.array([])

    correlations = np.empty(n - window + 1)
    for i in range(n - window + 1):
        a_slice = returns_a[i : i + window]
        b_slice = returns_b[i : i + window]

        std_a = np.std(a_slice, ddof=1)
        std_b = np.std(b_slice, ddof=1)

        if std_a == 0 or std_b == 0:
            correlations[i] = 0.0
        else:
            correlations[i] = np.corrcoef(a_slice, b_slice)[0, 1]

    return correlations


def compute_correlation_matrix(
    returns: Dict[str, np.ndarray],
    lookback: int = DEFAULT_SHORT_LOOKBACK,
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise correlation matrix from asset returns.

    Args:
        returns: Map of asset symbol to return series (arrays of same length).
        lookback: Number of periods to use for correlation calculation.

    Returns:
        Nested dict of symbol -> symbol -> correlation value.
    """
    symbols = sorted(returns.keys())
    matrix: Dict[str, Dict[str, float]] = {}

    for sym_a in symbols:
        matrix[sym_a] = {}
        for sym_b in symbols:
            if sym_a == sym_b:
                matrix[sym_a][sym_b] = 1.0
            elif sym_b in matrix and sym_a in matrix[sym_b]:
                matrix[sym_a][sym_b] = matrix[sym_b][sym_a]
            else:
                r_a = returns[sym_a][-lookback:]
                r_b = returns[sym_b][-lookback:]
                min_len = min(len(r_a), len(r_b))
                if min_len < 3:
                    matrix[sym_a][sym_b] = 0.0
                else:
                    r_a = r_a[-min_len:]
                    r_b = r_b[-min_len:]
                    std_a = np.std(r_a, ddof=1)
                    std_b = np.std(r_b, ddof=1)
                    if std_a == 0 or std_b == 0:
                        matrix[sym_a][sym_b] = 0.0
                    else:
                        matrix[sym_a][sym_b] = float(np.corrcoef(r_a, r_b)[0, 1])

    return matrix


def detect_regime_changes(
    returns: Dict[str, np.ndarray],
    short_lookback: int = DEFAULT_SHORT_LOOKBACK,
    long_lookback: int = DEFAULT_LONG_LOOKBACK,
    threshold: float = DEFAULT_REGIME_CHANGE_THRESHOLD,
) -> List[CorrelationRegimeChange]:
    """Detect significant changes in correlation regime.

    Compares short-term correlation to long-term correlation for each pair.
    A significant change means the absolute difference exceeds the threshold.

    Args:
        returns: Map of asset symbol to return series.
        short_lookback: Short window for recent correlation.
        long_lookback: Long window for historical correlation.
        threshold: Minimum absolute change to flag as significant.

    Returns:
        List of detected regime changes, sorted by absolute change descending.
    """
    symbols = sorted(returns.keys())
    changes: List[CorrelationRegimeChange] = []

    short_matrix = compute_correlation_matrix(returns, short_lookback)
    long_matrix = compute_correlation_matrix(returns, long_lookback)

    seen = set()
    for sym_a in symbols:
        for sym_b in symbols:
            if sym_a >= sym_b:
                continue
            pair = (sym_a, sym_b)
            if pair in seen:
                continue
            seen.add(pair)

            short_corr = short_matrix.get(sym_a, {}).get(sym_b, 0.0)
            long_corr = long_matrix.get(sym_a, {}).get(sym_b, 0.0)
            change = short_corr - long_corr
            is_significant = abs(change) >= threshold

            if is_significant:
                changes.append(
                    CorrelationRegimeChange(
                        asset_a=sym_a,
                        asset_b=sym_b,
                        previous_correlation=round(long_corr, 4),
                        current_correlation=round(short_corr, 4),
                        change=round(change, 4),
                        is_significant=True,
                    )
                )

    changes.sort(key=lambda c: abs(c.change), reverse=True)
    return changes


def identify_correlated_clusters(
    correlation_matrix: Dict[str, Dict[str, float]],
    threshold: float = DEFAULT_CORRELATION_THRESHOLD,
) -> List[CorrelationCluster]:
    """Identify clusters of highly correlated assets using greedy clustering.

    Assets with pairwise correlation >= threshold are grouped together.

    Args:
        correlation_matrix: Pairwise correlation matrix.
        threshold: Minimum correlation to consider assets as clustered.

    Returns:
        List of clusters with 2+ assets, sorted by avg correlation descending.
    """
    symbols = sorted(correlation_matrix.keys())
    assigned = set()
    clusters: List[CorrelationCluster] = []

    # Build adjacency: pairs with correlation >= threshold
    adjacency: Dict[str, set] = {s: set() for s in symbols}
    for sym_a in symbols:
        for sym_b in symbols:
            if sym_a != sym_b:
                corr = correlation_matrix.get(sym_a, {}).get(sym_b, 0.0)
                if corr >= threshold:
                    adjacency[sym_a].add(sym_b)

    # Greedy: pick the symbol with most high-correlation neighbors
    for sym in sorted(symbols, key=lambda s: len(adjacency[s]), reverse=True):
        if sym in assigned:
            continue
        if not adjacency[sym]:
            continue

        # Start a cluster with this symbol and its neighbors
        cluster_members = {sym}
        for neighbor in adjacency[sym]:
            if neighbor in assigned:
                continue
            # Check that neighbor is highly correlated with all cluster members
            all_correlated = all(
                correlation_matrix.get(neighbor, {}).get(m, 0.0) >= threshold
                for m in cluster_members
            )
            if all_correlated:
                cluster_members.add(neighbor)

        if len(cluster_members) < 2:
            continue

        members = sorted(cluster_members)
        assigned.update(members)

        # Compute avg intra-cluster correlation
        pair_corrs = []
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                pair_corrs.append(correlation_matrix.get(a, {}).get(b, 0.0))

        avg_corr = float(np.mean(pair_corrs)) if pair_corrs else 0.0
        clusters.append(
            CorrelationCluster(
                assets=members,
                avg_intra_correlation=round(avg_corr, 4),
            )
        )

    clusters.sort(key=lambda c: c.avg_intra_correlation, reverse=True)
    return clusters


def generate_recommendations(
    correlation_matrix: Dict[str, Dict[str, float]],
    clusters: List[CorrelationCluster],
    regime_changes: List[CorrelationRegimeChange],
    portfolio_symbols: List[str],
    threshold: float = DEFAULT_CORRELATION_THRESHOLD,
) -> List[DiversificationRecommendation]:
    """Generate diversification recommendations based on analysis.

    Args:
        correlation_matrix: Pairwise correlation matrix.
        clusters: Identified correlated clusters.
        regime_changes: Detected regime changes.
        portfolio_symbols: Symbols currently in the portfolio.
        threshold: Correlation threshold for warnings.

    Returns:
        List of recommendations sorted by severity.
    """
    recommendations: List[DiversificationRecommendation] = []
    portfolio_set = set(portfolio_symbols)

    # Warn about highly correlated pairs in portfolio
    seen = set()
    for sym_a in portfolio_symbols:
        for sym_b in portfolio_symbols:
            if sym_a >= sym_b:
                continue
            pair = (sym_a, sym_b)
            if pair in seen:
                continue
            seen.add(pair)

            corr = correlation_matrix.get(sym_a, {}).get(sym_b, 0.0)
            if corr >= threshold:
                severity = "high" if corr >= 0.9 else "medium"
                recommendations.append(
                    DiversificationRecommendation(
                        message=(
                            f"{sym_a} and {sym_b} have high correlation "
                            f"({corr:.2f}). Consider reducing exposure to one."
                        ),
                        severity=severity,
                        affected_assets=[sym_a, sym_b],
                    )
                )

    # Warn about clusters where multiple portfolio assets belong
    for cluster in clusters:
        in_portfolio = [a for a in cluster.assets if a in portfolio_set]
        if len(in_portfolio) >= 2:
            recommendations.append(
                DiversificationRecommendation(
                    message=(
                        f"Portfolio has {len(in_portfolio)} assets in a "
                        f"correlated cluster (avg r={cluster.avg_intra_correlation:.2f}): "
                        f"{', '.join(in_portfolio)}. Diversification is limited."
                    ),
                    severity="high",
                    affected_assets=in_portfolio,
                )
            )

    # Warn about regime changes involving portfolio assets
    for change in regime_changes:
        involved = []
        if change.asset_a in portfolio_set:
            involved.append(change.asset_a)
        if change.asset_b in portfolio_set:
            involved.append(change.asset_b)
        if involved:
            direction = "increased" if change.change > 0 else "decreased"
            recommendations.append(
                DiversificationRecommendation(
                    message=(
                        f"Correlation regime change: {change.asset_a}/{change.asset_b} "
                        f"correlation {direction} from {change.previous_correlation:.2f} "
                        f"to {change.current_correlation:.2f}. Review position sizing."
                    ),
                    severity="medium",
                    affected_assets=[change.asset_a, change.asset_b],
                )
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: severity_order.get(r.severity, 2))
    return recommendations


def check_portfolio_correlation_alerts(
    correlation_matrix: Dict[str, Dict[str, float]],
    portfolio_symbols: List[str],
    alert_threshold: float = DEFAULT_PORTFOLIO_CORRELATION_ALERT,
) -> List[CorrelationAlert]:
    """Check if portfolio-level correlation exceeds thresholds.

    Args:
        correlation_matrix: Pairwise correlation matrix.
        portfolio_symbols: Symbols currently in the portfolio.
        alert_threshold: Threshold for average pairwise correlation alert.

    Returns:
        List of triggered alerts.
    """
    alerts: List[CorrelationAlert] = []

    if len(portfolio_symbols) < 2:
        return alerts

    # Calculate average pairwise correlation for portfolio
    pair_corrs = []
    for i, sym_a in enumerate(portfolio_symbols):
        for sym_b in portfolio_symbols[i + 1 :]:
            corr = correlation_matrix.get(sym_a, {}).get(sym_b, 0.0)
            pair_corrs.append(corr)

    if not pair_corrs:
        return alerts

    avg_corr = float(np.mean(pair_corrs))
    max_corr = float(np.max(pair_corrs))

    if avg_corr >= alert_threshold:
        alerts.append(
            CorrelationAlert(
                metric="avg_pairwise_correlation",
                value=round(avg_corr, 4),
                threshold=alert_threshold,
                message=(
                    f"Portfolio average pairwise correlation ({avg_corr:.2f}) "
                    f"exceeds threshold ({alert_threshold:.2f}). "
                    f"Portfolio may lack diversification."
                ),
            )
        )

    if max_corr >= 0.95:
        alerts.append(
            CorrelationAlert(
                metric="max_pairwise_correlation",
                value=round(max_corr, 4),
                threshold=0.95,
                message=(
                    f"Maximum pairwise correlation ({max_corr:.2f}) is near 1.0. "
                    f"Some positions may be effectively duplicated."
                ),
            )
        )

    return alerts


def run_correlation_analysis(
    returns: Dict[str, np.ndarray],
    portfolio_symbols: List[str],
    short_lookback: int = DEFAULT_SHORT_LOOKBACK,
    long_lookback: int = DEFAULT_LONG_LOOKBACK,
    correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
    regime_change_threshold: float = DEFAULT_REGIME_CHANGE_THRESHOLD,
    portfolio_alert_threshold: float = DEFAULT_PORTFOLIO_CORRELATION_ALERT,
) -> CorrelationAnalysisResult:
    """Run complete correlation analysis.

    Args:
        returns: Map of asset symbol to return series (numpy arrays).
        portfolio_symbols: Symbols currently held in the portfolio.
        short_lookback: Short window for recent correlation.
        long_lookback: Long window for historical correlation.
        correlation_threshold: Threshold for high-correlation pairs.
        regime_change_threshold: Threshold for regime change detection.
        portfolio_alert_threshold: Threshold for portfolio-level alerts.

    Returns:
        Complete analysis result with matrix, clusters, recommendations, alerts.
    """
    # Compute correlation matrix using short lookback
    matrix = compute_correlation_matrix(returns, short_lookback)

    # Detect regime changes
    regime_changes = detect_regime_changes(
        returns, short_lookback, long_lookback, regime_change_threshold
    )

    # Identify clusters
    clusters = identify_correlated_clusters(matrix, correlation_threshold)

    # Generate recommendations
    recommendations = generate_recommendations(
        matrix, clusters, regime_changes, portfolio_symbols, correlation_threshold
    )

    # Check alerts
    alerts = check_portfolio_correlation_alerts(
        matrix, portfolio_symbols, portfolio_alert_threshold
    )

    # Compute average pairwise correlation across all assets
    symbols = sorted(returns.keys())
    pair_corrs = []
    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i + 1 :]:
            pair_corrs.append(matrix.get(sym_a, {}).get(sym_b, 0.0))

    avg_pairwise = float(np.mean(pair_corrs)) if pair_corrs else 0.0

    return CorrelationAnalysisResult(
        correlation_matrix=matrix,
        regime_changes=regime_changes,
        clusters=clusters,
        recommendations=recommendations,
        alerts=alerts,
        avg_pairwise_correlation=round(avg_pairwise, 4),
    )
