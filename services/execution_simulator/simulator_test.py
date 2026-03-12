"""Tests for the execution simulator module.

All tests use deterministic random seeds for reproducibility.
"""

import math
import random

import pytest

from services.execution_simulator.simulator import (
    ExecutionResult,
    ExecutionSimulator,
    FillStatus,
    LatencyConfig,
    LatencyDistribution,
    OrderBookConfig,
    OrderSide,
    OrderType,
    SimulatorConfig,
    SlippageConfig,
)

SEED = 42


@pytest.fixture
def rng():
    return random.Random(SEED)


@pytest.fixture
def default_sim(rng):
    return ExecutionSimulator(rng=rng)


@pytest.fixture
def config():
    return SimulatorConfig(
        slippage=SlippageConfig(base_bps=5.0, volume_impact_bps=10.0),
        latency=LatencyConfig(
            distribution=LatencyDistribution.UNIFORM,
            min_ms=1.0,
            max_ms=50.0,
        ),
        order_book=OrderBookConfig(depth_base=100.0, depth_multiplier=5.0),
        limit_fill_decay=2.0,
    )


@pytest.fixture
def sim(config, rng):
    return ExecutionSimulator(config=config, rng=rng)


# ---------------------------------------------------------------
# Market Orders
# ---------------------------------------------------------------


class TestMarketOrders:
    def test_full_fill_small_order(self, sim):
        """A small order relative to book depth should fully fill."""
        result = sim.execute_market_order(OrderSide.BUY, 10.0, 100.0)
        assert result.status == FillStatus.FILLED
        assert result.filled_quantity == 10.0
        assert result.order_type == OrderType.MARKET
        assert result.side == OrderSide.BUY

    def test_buy_slippage_increases_price(self, sim):
        """Buy market orders should fill above mid-price due to slippage."""
        result = sim.execute_market_order(OrderSide.BUY, 10.0, 100.0)
        assert result.average_price > 100.0

    def test_sell_slippage_decreases_price(self, sim):
        """Sell market orders should fill below mid-price due to slippage."""
        result = sim.execute_market_order(OrderSide.SELL, 10.0, 100.0)
        assert result.average_price < 100.0

    def test_slippage_is_deterministic(self):
        """Two simulators with the same seed should produce identical results."""
        sim1 = ExecutionSimulator(rng=random.Random(SEED))
        sim2 = ExecutionSimulator(rng=random.Random(SEED))
        r1 = sim1.execute_market_order(OrderSide.BUY, 10.0, 100.0)
        r2 = sim2.execute_market_order(OrderSide.BUY, 10.0, 100.0)
        assert r1.average_price == r2.average_price
        assert r1.filled_quantity == r2.filled_quantity
        assert r1.total_slippage_bps == r2.total_slippage_bps

    def test_volume_dependent_slippage(self):
        """Larger orders should incur higher slippage via volume impact."""
        cfg = SimulatorConfig(
            slippage=SlippageConfig(base_bps=0.0, volume_impact_bps=100.0),
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        # Small order: low fill ratio.
        sim_small = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        r_small = sim_small.execute_market_order(OrderSide.BUY, 10.0, 100.0)

        # Large order: high fill ratio.
        sim_large = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        r_large = sim_large.execute_market_order(OrderSide.BUY, 900.0, 100.0)

        assert r_large.total_slippage_bps > r_small.total_slippage_bps

    def test_partial_fill_when_exceeding_depth(self):
        """Order larger than available depth should result in partial fill."""
        cfg = SimulatorConfig(
            order_book=OrderBookConfig(depth_base=10.0, depth_multiplier=1.0),
        )
        # depth_base=10, multiplier=1 => available = 10 (no random range)
        # But there's still rng * base * (mult - 1) = 0, so available = 10.
        sim = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        result = sim.execute_market_order(OrderSide.BUY, 50.0, 100.0)
        assert result.status == FillStatus.PARTIAL
        assert result.filled_quantity == 10.0

    def test_fill_has_positive_latency(self, sim):
        """Every fill should have a positive latency value."""
        result = sim.execute_market_order(OrderSide.BUY, 5.0, 100.0)
        assert len(result.fills) == 1
        assert result.fills[0].latency_ms > 0
        assert result.total_latency_ms > 0

    def test_slippage_bps_calculation(self):
        """Verify slippage BPS matches expected formula."""
        cfg = SimulatorConfig(
            slippage=SlippageConfig(base_bps=10.0, volume_impact_bps=0.0),
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        sim = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        result = sim.execute_market_order(OrderSide.BUY, 1.0, 10000.0)
        # base_bps=10, volume_impact=0 => slippage = 10 bps
        assert result.total_slippage_bps == 10.0
        expected_price = 10000.0 * (1.0 + 10.0 / 10_000)
        assert result.average_price == pytest.approx(expected_price)


# ---------------------------------------------------------------
# Limit Orders
# ---------------------------------------------------------------


class TestLimitOrders:
    def test_marketable_limit_buy_fills_as_market(self, sim):
        """A buy limit at or above mid should behave like a market order."""
        result = sim.execute_limit_order(OrderSide.BUY, 10.0, 105.0, 100.0)
        assert result.status in (FillStatus.FILLED, FillStatus.PARTIAL)
        # Should have slippage since it crossed the spread.
        assert result.total_slippage_bps > 0

    def test_marketable_limit_sell_fills_as_market(self, sim):
        """A sell limit at or below mid should behave like a market order."""
        result = sim.execute_limit_order(OrderSide.SELL, 10.0, 95.0, 100.0)
        assert result.status in (FillStatus.FILLED, FillStatus.PARTIAL)
        assert result.total_slippage_bps > 0

    def test_limit_order_no_slippage_when_filled(self):
        """Non-marketable limit orders fill at the limit price (no slippage)."""
        cfg = SimulatorConfig(limit_fill_decay=0.001)  # High fill prob.
        sim = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        result = sim.execute_limit_order(OrderSide.BUY, 5.0, 99.0, 100.0)
        if result.status != FillStatus.UNFILLED:
            assert result.total_slippage_bps == 0.0
            assert result.average_price == 99.0

    def test_fill_probability_decreases_with_distance(self):
        """Orders farther from mid should fill less often."""
        cfg = SimulatorConfig(
            limit_fill_decay=2.0,
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        close_fills = 0
        far_fills = 0
        trials = 500

        for i in range(trials):
            sim_close = ExecutionSimulator(config=cfg, rng=random.Random(i))
            r = sim_close.execute_limit_order(OrderSide.BUY, 1.0, 99.9, 100.0)
            if r.status != FillStatus.UNFILLED:
                close_fills += 1

            sim_far = ExecutionSimulator(config=cfg, rng=random.Random(i))
            r = sim_far.execute_limit_order(OrderSide.BUY, 1.0, 95.0, 100.0)
            if r.status != FillStatus.UNFILLED:
                far_fills += 1

        assert close_fills > far_fills

    def test_limit_order_deterministic(self):
        """Same seed should produce identical limit order results."""
        cfg = SimulatorConfig(limit_fill_decay=1.0)
        sim1 = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        sim2 = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        r1 = sim1.execute_limit_order(OrderSide.BUY, 10.0, 99.0, 100.0)
        r2 = sim2.execute_limit_order(OrderSide.BUY, 10.0, 99.0, 100.0)
        assert r1.status == r2.status
        assert r1.filled_quantity == r2.filled_quantity
        assert r1.average_price == r2.average_price


# ---------------------------------------------------------------
# Latency Simulation
# ---------------------------------------------------------------


class TestLatencySimulation:
    def test_uniform_latency_within_bounds(self):
        """Uniform latency should fall within [min_ms, max_ms]."""
        cfg = SimulatorConfig(
            latency=LatencyConfig(
                distribution=LatencyDistribution.UNIFORM,
                min_ms=10.0,
                max_ms=20.0,
            ),
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        for i in range(100):
            sim = ExecutionSimulator(config=cfg, rng=random.Random(i))
            r = sim.execute_market_order(OrderSide.BUY, 1.0, 100.0)
            assert 10.0 <= r.total_latency_ms <= 20.0

    def test_normal_latency_non_negative(self):
        """Normal latency should be clamped to non-negative."""
        cfg = SimulatorConfig(
            latency=LatencyConfig(
                distribution=LatencyDistribution.NORMAL,
                mean_ms=5.0,
                std_ms=100.0,  # Wide std to test clamping.
            ),
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        for i in range(100):
            sim = ExecutionSimulator(config=cfg, rng=random.Random(i))
            r = sim.execute_market_order(OrderSide.BUY, 1.0, 100.0)
            assert r.total_latency_ms >= 0.0

    def test_normal_latency_distribution_mean(self):
        """Normal latency samples should cluster around the mean."""
        cfg = SimulatorConfig(
            latency=LatencyConfig(
                distribution=LatencyDistribution.NORMAL,
                mean_ms=50.0,
                std_ms=5.0,
            ),
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        latencies = []
        for i in range(200):
            sim = ExecutionSimulator(config=cfg, rng=random.Random(i))
            r = sim.execute_market_order(OrderSide.BUY, 1.0, 100.0)
            latencies.append(r.total_latency_ms)
        avg = sum(latencies) / len(latencies)
        assert 40.0 < avg < 60.0


# ---------------------------------------------------------------
# Execution Statistics
# ---------------------------------------------------------------


class TestExecutionStatistics:
    def test_statistics_after_market_orders(self):
        """Statistics should reflect executed market orders."""
        sim = ExecutionSimulator(
            config=SimulatorConfig(
                order_book=OrderBookConfig(
                    depth_base=1000.0, depth_multiplier=1.0
                ),
            ),
            rng=random.Random(SEED),
        )
        for _ in range(10):
            sim.execute_market_order(OrderSide.BUY, 5.0, 100.0)

        stats = sim.get_statistics()
        assert stats["total_orders"] == 10
        assert stats["total_fills"] == 10
        assert stats["fill_rate"] == 1.0
        assert stats["avg_slippage_bps"] > 0
        assert stats["avg_fill_time_ms"] > 0

    def test_statistics_with_unfilled_orders(self):
        """Unfilled orders should decrease the fill rate."""
        cfg = SimulatorConfig(
            limit_fill_decay=100.0,  # Very aggressive decay => low fill prob.
            order_book=OrderBookConfig(depth_base=1000.0, depth_multiplier=1.0),
        )
        sim = ExecutionSimulator(config=cfg, rng=random.Random(SEED))
        for _ in range(20):
            sim.execute_limit_order(OrderSide.BUY, 1.0, 90.0, 100.0)

        stats = sim.get_statistics()
        assert stats["total_orders"] == 20
        assert stats["fill_rate"] < 1.0

    def test_reset_statistics(self, default_sim):
        """reset_statistics should zero all counters."""
        default_sim.execute_market_order(OrderSide.BUY, 5.0, 100.0)
        default_sim.reset_statistics()
        stats = default_sim.get_statistics()
        assert stats["total_orders"] == 0
        assert stats["total_fills"] == 0
        assert stats["fill_rate"] == 0.0
        assert stats["avg_slippage_bps"] == 0.0
        assert stats["avg_fill_time_ms"] == 0.0

    def test_empty_statistics(self):
        """Fresh simulator should report zero statistics."""
        sim = ExecutionSimulator()
        stats = sim.get_statistics()
        assert stats["total_orders"] == 0
        assert stats["fill_rate"] == 0.0


# ---------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------


class TestEdgeCases:
    def test_zero_quantity_order(self, sim):
        """Zero-quantity order should return unfilled."""
        result = sim.execute_market_order(OrderSide.BUY, 0.0, 100.0)
        # Depending on depth, 0 <= available, so min(0, available) = 0 => unfilled
        assert result.filled_quantity == 0.0
        assert result.status == FillStatus.UNFILLED

    def test_very_large_order(self, sim):
        """Very large order should partially fill up to available depth."""
        result = sim.execute_market_order(OrderSide.BUY, 1_000_000.0, 100.0)
        assert result.status == FillStatus.PARTIAL
        assert result.filled_quantity < 1_000_000.0
        assert result.filled_quantity > 0

    def test_limit_price_equals_mid(self, sim):
        """Limit buy at mid should be treated as marketable."""
        result = sim.execute_limit_order(OrderSide.BUY, 5.0, 100.0, 100.0)
        assert result.status in (FillStatus.FILLED, FillStatus.PARTIAL)

    def test_default_config(self):
        """Simulator with default config should work."""
        sim = ExecutionSimulator(rng=random.Random(SEED))
        result = sim.execute_market_order(OrderSide.BUY, 10.0, 50000.0)
        assert result.filled_quantity > 0
