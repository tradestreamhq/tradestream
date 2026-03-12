"""Order execution simulator for backtesting and paper trading.

Models realistic order fills with configurable slippage, partial fills,
and latency simulation to produce more accurate backtest results.
"""

import enum
import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional


class OrderType(enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class FillStatus(enum.Enum):
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    UNFILLED = "UNFILLED"


class LatencyDistribution(enum.Enum):
    UNIFORM = "UNIFORM"
    NORMAL = "NORMAL"


@dataclass
class SlippageConfig:
    """Configuration for slippage modeling.

    Attributes:
        base_bps: Fixed slippage in basis points applied to every market order.
        volume_impact_bps: Additional slippage per unit of fill ratio
            (fill_qty / available_depth). When fill_qty equals available_depth,
            the full volume_impact_bps is added.
    """

    base_bps: float = 5.0
    volume_impact_bps: float = 10.0


@dataclass
class LatencyConfig:
    """Configuration for latency simulation.

    Attributes:
        distribution: Type of random distribution for delay sampling.
        min_ms: Minimum latency in milliseconds (uniform lower bound).
        max_ms: Maximum latency in milliseconds (uniform upper bound).
        mean_ms: Mean latency for normal distribution.
        std_ms: Standard deviation for normal distribution.
    """

    distribution: LatencyDistribution = LatencyDistribution.UNIFORM
    min_ms: float = 1.0
    max_ms: float = 50.0
    mean_ms: float = 25.0
    std_ms: float = 10.0


@dataclass
class OrderBookConfig:
    """Configuration for simulated order book depth.

    Attributes:
        depth_base: Base available quantity at the best price level.
        depth_multiplier: Multiplier applied to depth_base to get total
            available depth across price levels.
    """

    depth_base: float = 100.0
    depth_multiplier: float = 5.0


@dataclass
class SimulatorConfig:
    """Top-level configuration for the execution simulator."""

    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    order_book: OrderBookConfig = field(default_factory=OrderBookConfig)
    limit_fill_decay: float = 2.0


@dataclass
class Fill:
    """A single fill event."""

    price: float
    quantity: float
    slippage_bps: float
    latency_ms: float
    timestamp: float


@dataclass
class ExecutionResult:
    """Result of simulating an order execution."""

    order_type: OrderType
    side: OrderSide
    requested_quantity: float
    filled_quantity: float
    average_price: float
    status: FillStatus
    fills: list[Fill]
    total_slippage_bps: float
    total_latency_ms: float


class ExecutionSimulator:
    """Simulates order execution with realistic market microstructure effects.

    Supports market orders (with slippage) and limit orders (with fill
    probability). Tracks aggregate execution statistics for analysis.

    Args:
        config: Simulator configuration parameters.
        rng: Random number generator for reproducibility. When ``None``,
            a default ``random.Random`` instance is created.
    """

    def __init__(
        self,
        config: Optional[SimulatorConfig] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._config = config or SimulatorConfig()
        self._rng = rng or random.Random()

        # Execution statistics accumulators.
        self._total_slippage_bps: float = 0.0
        self._total_fill_time_ms: float = 0.0
        self._total_fills: int = 0
        self._total_orders: int = 0
        self._filled_orders: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_market_order(
        self,
        side: OrderSide,
        quantity: float,
        mid_price: float,
    ) -> ExecutionResult:
        """Simulate a market order execution.

        The order may be partially filled depending on simulated order
        book depth. Slippage is computed from a fixed base component plus
        a volume-dependent component.

        Args:
            side: BUY or SELL.
            quantity: Desired fill quantity.
            mid_price: Current mid-market price.

        Returns:
            ExecutionResult with fill details.
        """
        self._total_orders += 1
        available = self._available_depth()
        fill_qty = min(quantity, available)

        if fill_qty <= 0:
            return self._unfilled_result(OrderType.MARKET, side, quantity)

        fill_ratio = fill_qty / available
        slippage_bps = (
            self._config.slippage.base_bps
            + self._config.slippage.volume_impact_bps * fill_ratio
        )
        direction = 1.0 if side == OrderSide.BUY else -1.0
        fill_price = mid_price * (1.0 + direction * slippage_bps / 10_000)

        latency = self._sample_latency()
        now = time.monotonic()

        fill = Fill(
            price=fill_price,
            quantity=fill_qty,
            slippage_bps=slippage_bps,
            latency_ms=latency,
            timestamp=now,
        )

        status = FillStatus.FILLED if fill_qty >= quantity else FillStatus.PARTIAL
        self._record_stats(slippage_bps, latency, filled=True)

        return ExecutionResult(
            order_type=OrderType.MARKET,
            side=side,
            requested_quantity=quantity,
            filled_quantity=fill_qty,
            average_price=fill_price,
            status=status,
            fills=[fill],
            total_slippage_bps=slippage_bps,
            total_latency_ms=latency,
        )

    def execute_limit_order(
        self,
        side: OrderSide,
        quantity: float,
        limit_price: float,
        mid_price: float,
    ) -> ExecutionResult:
        """Simulate a limit order execution.

        Fill probability decreases exponentially with distance from the
        mid-price. If filled, partial fills are determined by simulated
        book depth.

        Args:
            side: BUY or SELL.
            quantity: Desired fill quantity.
            limit_price: Limit price for the order.
            mid_price: Current mid-market price.

        Returns:
            ExecutionResult with fill details.
        """
        self._total_orders += 1

        # Check if limit price is marketable (would cross the spread).
        if side == OrderSide.BUY and limit_price >= mid_price:
            return self.execute_market_order(side, quantity, mid_price)
        if side == OrderSide.SELL and limit_price <= mid_price:
            return self.execute_market_order(side, quantity, mid_price)

        # Compute fill probability based on distance from mid.
        distance_bps = abs(limit_price - mid_price) / mid_price * 10_000
        decay = self._config.limit_fill_decay
        fill_prob = math.exp(-decay * distance_bps / 100)

        if self._rng.random() > fill_prob:
            self._record_stats(0.0, 0.0, filled=False)
            return self._unfilled_result(OrderType.LIMIT, side, quantity)

        available = self._available_depth()
        fill_qty = min(quantity, available)
        if fill_qty <= 0:
            return self._unfilled_result(OrderType.LIMIT, side, quantity)

        latency = self._sample_latency()
        now = time.monotonic()

        fill = Fill(
            price=limit_price,
            quantity=fill_qty,
            slippage_bps=0.0,
            latency_ms=latency,
            timestamp=now,
        )

        status = FillStatus.FILLED if fill_qty >= quantity else FillStatus.PARTIAL
        self._record_stats(0.0, latency, filled=True)

        return ExecutionResult(
            order_type=OrderType.LIMIT,
            side=side,
            requested_quantity=quantity,
            filled_quantity=fill_qty,
            average_price=limit_price,
            status=status,
            fills=[fill],
            total_slippage_bps=0.0,
            total_latency_ms=latency,
        )

    def get_statistics(self) -> dict:
        """Return aggregate execution statistics.

        Returns:
            Dictionary with avg_slippage_bps, fill_rate, and avg_fill_time_ms.
        """
        avg_slippage = (
            self._total_slippage_bps / self._total_fills
            if self._total_fills > 0
            else 0.0
        )
        fill_rate = (
            self._filled_orders / self._total_orders
            if self._total_orders > 0
            else 0.0
        )
        avg_fill_time = (
            self._total_fill_time_ms / self._total_fills
            if self._total_fills > 0
            else 0.0
        )
        return {
            "avg_slippage_bps": avg_slippage,
            "fill_rate": fill_rate,
            "avg_fill_time_ms": avg_fill_time,
            "total_orders": self._total_orders,
            "total_fills": self._total_fills,
        }

    def reset_statistics(self) -> None:
        """Reset all accumulated execution statistics."""
        self._total_slippage_bps = 0.0
        self._total_fill_time_ms = 0.0
        self._total_fills = 0
        self._total_orders = 0
        self._filled_orders = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _available_depth(self) -> float:
        """Sample available order book depth."""
        base = self._config.order_book.depth_base
        mult = self._config.order_book.depth_multiplier
        return base + self._rng.random() * base * (mult - 1)

    def _sample_latency(self) -> float:
        """Sample latency in milliseconds from the configured distribution."""
        cfg = self._config.latency
        if cfg.distribution == LatencyDistribution.UNIFORM:
            return self._rng.uniform(cfg.min_ms, cfg.max_ms)
        # NORMAL distribution — clamp to non-negative.
        return max(0.0, self._rng.gauss(cfg.mean_ms, cfg.std_ms))

    def _record_stats(
        self, slippage_bps: float, latency_ms: float, filled: bool
    ) -> None:
        if filled:
            self._total_slippage_bps += slippage_bps
            self._total_fill_time_ms += latency_ms
            self._total_fills += 1
            self._filled_orders += 1

    def _unfilled_result(
        self, order_type: OrderType, side: OrderSide, quantity: float
    ) -> ExecutionResult:
        return ExecutionResult(
            order_type=order_type,
            side=side,
            requested_quantity=quantity,
            filled_quantity=0.0,
            average_price=0.0,
            status=FillStatus.UNFILLED,
            fills=[],
            total_slippage_bps=0.0,
            total_latency_ms=0.0,
        )
