"""Risk dashboard aggregator.

Computes portfolio-level risk metrics across all active strategies:
- Value-at-Risk (VaR) at 95% and 99% confidence
- Portfolio beta against benchmark
- Sector/asset concentration (Herfindahl index)
- Top correlated position pairs
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.risk_dashboard.models import (
    ConcentrationMetrics,
    CorrelationPair,
    PortfolioBeta,
    RiskDashboard,
    VaRResult,
)

# Sector classification for crypto assets
CRYPTO_SECTORS = {
    "BTC": "L1",
    "ETH": "L1",
    "SOL": "L1",
    "ADA": "L1",
    "DOT": "L1",
    "AVAX": "L1",
    "MATIC": "L2",
    "LINK": "Oracle",
    "UNI": "DeFi",
    "DOGE": "Meme",
    "XRP": "Payments",
    "BNB": "Exchange",
}


def _classify_sector(symbol: str) -> str:
    """Classify a symbol into a sector."""
    base = symbol.split("-")[0].split("/")[0].upper()
    return CRYPTO_SECTORS.get(base, "Other")


def calculate_var(
    position_values: List[float],
    daily_returns: List[List[float]],
    confidence: float,
    total_equity: float,
) -> VaRResult:
    """Calculate parametric Value-at-Risk.

    Uses variance-covariance method with position weights and return data.
    Falls back to individual volatility sum when correlation data is sparse.

    Args:
        position_values: Dollar value of each position.
        daily_returns: List of daily return series per position.
        confidence: Confidence level (e.g. 0.95 or 0.99).
        total_equity: Total portfolio equity.
    """
    if not position_values or total_equity <= 0:
        return VaRResult(
            confidence_level=confidence, var_absolute=0.0, var_percent=0.0
        )

    # Z-scores for common confidence levels
    z_scores = {0.95: 1.645, 0.99: 2.326}
    z = z_scores.get(confidence, 1.645)

    # Calculate portfolio volatility
    weights = [v / total_equity for v in position_values]
    volatilities = []
    for returns in daily_returns:
        if len(returns) >= 2:
            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            volatilities.append(math.sqrt(variance))
        else:
            volatilities.append(0.0)

    # Portfolio variance using diagonal (ignoring cross-correlations for
    # parametric simplicity when we lack full covariance data)
    portfolio_variance = sum(
        (w * vol) ** 2 for w, vol in zip(weights, volatilities)
    )

    # Add cross-correlation terms if we have enough data
    n = len(weights)
    for i in range(n):
        for j in range(i + 1, n):
            if len(daily_returns[i]) >= 5 and len(daily_returns[j]) >= 5:
                corr = _pearson_correlation(daily_returns[i], daily_returns[j])
                portfolio_variance += (
                    2 * weights[i] * weights[j] * volatilities[i] * volatilities[j] * corr
                )

    portfolio_vol = math.sqrt(max(portfolio_variance, 0.0))

    var_pct = z * portfolio_vol
    var_abs = var_pct * total_equity

    return VaRResult(
        confidence_level=confidence,
        var_absolute=round(var_abs, 2),
        var_percent=round(var_pct * 100, 4),
    )


def _pearson_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation between two return series."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0

    x, y = x[:n], y[:n]
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / (n - 1)
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / (n - 1))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / (n - 1))

    if std_x == 0 or std_y == 0:
        return 0.0

    return max(-1.0, min(1.0, cov / (std_x * std_y)))


def calculate_portfolio_beta(
    portfolio_returns: List[float],
    benchmark_returns: List[float],
    benchmark_name: str = "BTC/USD",
) -> PortfolioBeta:
    """Calculate portfolio beta against a benchmark.

    Beta = Cov(portfolio, benchmark) / Var(benchmark)
    """
    n = min(len(portfolio_returns), len(benchmark_returns))
    if n < 2:
        return PortfolioBeta(beta=1.0, benchmark=benchmark_name, r_squared=0.0)

    pr = portfolio_returns[:n]
    br = benchmark_returns[:n]

    mean_p = sum(pr) / n
    mean_b = sum(br) / n

    cov = sum((pi - mean_p) * (bi - mean_b) for pi, bi in zip(pr, br)) / (n - 1)
    var_b = sum((bi - mean_b) ** 2 for bi in br) / (n - 1)
    var_p = sum((pi - mean_p) ** 2 for pi in pr) / (n - 1)

    if var_b == 0:
        return PortfolioBeta(beta=0.0, benchmark=benchmark_name, r_squared=0.0)

    beta = cov / var_b

    # R-squared
    if var_p == 0:
        r_squared = 0.0
    else:
        corr = cov / (math.sqrt(var_p) * math.sqrt(var_b))
        r_squared = corr ** 2

    return PortfolioBeta(
        beta=round(beta, 4),
        benchmark=benchmark_name,
        r_squared=round(r_squared, 4),
    )


def calculate_concentration(
    positions: List[Dict[str, Any]],
    total_exposure: float,
) -> ConcentrationMetrics:
    """Calculate Herfindahl index and sector/asset concentration.

    Herfindahl index: sum of squared weights. Range [1/n, 1].
    Values near 1/n indicate diversification; near 1 indicate concentration.
    """
    if not positions or total_exposure <= 0:
        return ConcentrationMetrics(
            herfindahl_index=0.0,
            top_holding_pct=0.0,
            top_holding_symbol="",
            sector_weights={},
            asset_weights={},
        )

    asset_weights: Dict[str, float] = {}
    sector_weights: Dict[str, float] = {}

    for pos in positions:
        symbol = pos["symbol"]
        exposure = abs(float(pos["quantity"]) * float(pos["avg_entry_price"]))
        weight = exposure / total_exposure

        asset_weights[symbol] = round(weight * 100, 2)

        sector = _classify_sector(symbol)
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight * 100

    # Herfindahl index (using decimal weights)
    hhi = sum((w / 100) ** 2 for w in asset_weights.values())

    # Round sector weights
    sector_weights = {k: round(v, 2) for k, v in sector_weights.items()}

    # Top holding
    top_symbol = max(asset_weights, key=asset_weights.get)
    top_pct = asset_weights[top_symbol]

    return ConcentrationMetrics(
        herfindahl_index=round(hhi, 4),
        top_holding_pct=top_pct,
        top_holding_symbol=top_symbol,
        sector_weights=sector_weights,
        asset_weights=asset_weights,
    )


def find_top_correlations(
    symbols: List[str],
    daily_returns: List[List[float]],
    top_n: int = 5,
) -> List[CorrelationPair]:
    """Find the most correlated position pairs.

    Args:
        symbols: List of position symbols.
        daily_returns: Corresponding daily return series.
        top_n: Number of top pairs to return.
    """
    pairs: List[CorrelationPair] = []
    n = len(symbols)

    for i in range(n):
        for j in range(i + 1, n):
            if len(daily_returns[i]) < 5 or len(daily_returns[j]) < 5:
                continue
            corr = _pearson_correlation(daily_returns[i], daily_returns[j])
            pairs.append(
                CorrelationPair(
                    symbol_a=symbols[i],
                    symbol_b=symbols[j],
                    correlation=round(corr, 4),
                )
            )

    # Sort by absolute correlation descending
    pairs.sort(key=lambda p: abs(p.correlation), reverse=True)
    return pairs[:top_n]


def aggregate_risk_dashboard(
    positions: List[Dict[str, Any]],
    daily_returns_by_symbol: Dict[str, List[float]],
    benchmark_returns: List[float],
    total_equity: float,
    active_strategy_count: int,
    benchmark_name: str = "BTC/USD",
) -> RiskDashboard:
    """Build the full risk dashboard from raw position and return data.

    Args:
        positions: List of position dicts with symbol, quantity, avg_entry_price.
        daily_returns_by_symbol: Map of symbol to daily return series.
        benchmark_returns: Daily returns for the benchmark.
        total_equity: Total portfolio equity value.
        active_strategy_count: Number of active strategies.
        benchmark_name: Name of the benchmark instrument.
    """
    if not positions:
        empty_var = VaRResult(confidence_level=0.95, var_absolute=0.0, var_percent=0.0)
        return RiskDashboard(
            var_95=empty_var,
            var_99=VaRResult(confidence_level=0.99, var_absolute=0.0, var_percent=0.0),
            portfolio_beta=PortfolioBeta(beta=0.0, benchmark=benchmark_name, r_squared=0.0),
            concentration=ConcentrationMetrics(
                herfindahl_index=0.0,
                top_holding_pct=0.0,
                top_holding_symbol="",
                sector_weights={},
                asset_weights={},
            ),
            top_correlations=[],
            total_exposure=0.0,
            position_count=0,
            active_strategy_count=active_strategy_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Compute total exposure
    total_exposure = sum(
        abs(float(p["quantity"]) * float(p["avg_entry_price"])) for p in positions
    )

    # Prepare aligned data
    symbols = [p["symbol"] for p in positions]
    position_values = [
        abs(float(p["quantity"]) * float(p["avg_entry_price"])) for p in positions
    ]
    daily_returns = [daily_returns_by_symbol.get(s, []) for s in symbols]

    # VaR
    var_95 = calculate_var(position_values, daily_returns, 0.95, total_equity)
    var_99 = calculate_var(position_values, daily_returns, 0.99, total_equity)

    # Portfolio beta: weighted average returns for portfolio
    portfolio_returns = _compute_portfolio_returns(
        symbols, position_values, daily_returns, total_equity
    )
    beta = calculate_portfolio_beta(portfolio_returns, benchmark_returns, benchmark_name)

    # Concentration
    concentration = calculate_concentration(positions, total_exposure)

    # Correlations
    top_correlations = find_top_correlations(symbols, daily_returns)

    return RiskDashboard(
        var_95=var_95,
        var_99=var_99,
        portfolio_beta=beta,
        concentration=concentration,
        top_correlations=top_correlations,
        total_exposure=round(total_exposure, 2),
        position_count=len(positions),
        active_strategy_count=active_strategy_count,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _compute_portfolio_returns(
    symbols: List[str],
    position_values: List[float],
    daily_returns: List[List[float]],
    total_equity: float,
) -> List[float]:
    """Compute weighted portfolio returns from individual position returns."""
    if total_equity <= 0 or not daily_returns:
        return []

    weights = [v / total_equity for v in position_values]

    # Find minimum return series length (align all series)
    lengths = [len(r) for r in daily_returns if len(r) > 0]
    if not lengths:
        return []
    min_len = min(lengths)

    portfolio_returns = []
    for t in range(min_len):
        weighted_return = 0.0
        for i, returns in enumerate(daily_returns):
            if t < len(returns):
                weighted_return += weights[i] * returns[t]
        portfolio_returns.append(weighted_return)

    return portfolio_returns
