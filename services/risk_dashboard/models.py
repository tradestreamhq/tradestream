"""Data models for the risk dashboard service."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class VaRResult:
    """Value-at-Risk calculation result."""

    confidence_level: float  # e.g. 0.95 or 0.99
    var_absolute: float  # Dollar amount at risk
    var_percent: float  # Percentage of portfolio


@dataclass
class PortfolioBeta:
    """Portfolio beta against a benchmark."""

    beta: float
    benchmark: str
    r_squared: float  # Goodness of fit


@dataclass
class ConcentrationMetrics:
    """Sector and asset concentration metrics."""

    herfindahl_index: float  # 0-1, higher = more concentrated
    top_holding_pct: float
    top_holding_symbol: str
    sector_weights: Dict[str, float]  # sector -> weight %
    asset_weights: Dict[str, float]  # symbol -> weight %


@dataclass
class CorrelationPair:
    """A pair of correlated positions."""

    symbol_a: str
    symbol_b: str
    correlation: float


@dataclass
class RiskDashboard:
    """Aggregated risk dashboard for all active strategies."""

    var_95: VaRResult
    var_99: VaRResult
    portfolio_beta: PortfolioBeta
    concentration: ConcentrationMetrics
    top_correlations: List[CorrelationPair]
    total_exposure: float
    position_count: int
    active_strategy_count: int
    timestamp: str
