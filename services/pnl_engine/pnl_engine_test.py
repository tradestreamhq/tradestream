"""Tests for PnL calculation engine with FIFO, LIFO, and average cost basis."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.pnl_engine.pnl_engine import CostBasisMethod, PnLEngine


def _ts(hour: int) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


class TestFIFO:
    def test_single_lot_full_sell(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("10"), _ts(1))
        realized = engine.add_sell("BTC", Decimal("120"), Decimal("10"), _ts(2))

        assert len(realized) == 1
        assert realized[0].pnl == Decimal("200")
        assert realized[0].lot_entry_price == Decimal("100")
        assert engine.get_position("BTC").total_size == 0

    def test_multi_lot_fifo_order(self):
        """First-in lots are consumed first."""
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("5"), _ts(1))
        engine.add_buy("BTC", Decimal("200"), Decimal("5"), _ts(2))

        realized = engine.add_sell("BTC", Decimal("150"), Decimal("7"), _ts(3))

        # FIFO: first lot (5@100) fully consumed, then 2 from second lot (2@200)
        assert len(realized) == 2
        assert realized[0].lot_entry_price == Decimal("100")
        assert realized[0].size == Decimal("5")
        assert realized[0].pnl == Decimal("250")  # (150-100)*5
        assert realized[1].lot_entry_price == Decimal("200")
        assert realized[1].size == Decimal("2")
        assert realized[1].pnl == Decimal("-100")  # (150-200)*2

        pos = engine.get_position("BTC")
        assert pos.total_size == Decimal("3")
        assert pos.lots[0].entry_price == Decimal("200")

    def test_partial_lot_sell(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("10"), _ts(1))
        realized = engine.add_sell("BTC", Decimal("110"), Decimal("3"), _ts(2))

        assert len(realized) == 1
        assert realized[0].size == Decimal("3")
        assert realized[0].pnl == Decimal("30")
        assert engine.get_position("BTC").total_size == Decimal("7")

    def test_multiple_sells_across_lots(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("5"), _ts(1))
        engine.add_buy("BTC", Decimal("150"), Decimal("5"), _ts(2))
        engine.add_buy("BTC", Decimal("200"), Decimal("5"), _ts(3))

        # First sell: consumes lot 1 fully + 2 from lot 2
        r1 = engine.add_sell("BTC", Decimal("180"), Decimal("7"), _ts(4))
        assert len(r1) == 2

        # Second sell: consumes remaining 3 from lot 2 + 2 from lot 3
        r2 = engine.add_sell("BTC", Decimal("250"), Decimal("5"), _ts(5))
        assert len(r2) == 2
        assert r2[0].lot_entry_price == Decimal("150")
        assert r2[0].size == Decimal("3")
        assert r2[1].lot_entry_price == Decimal("200")
        assert r2[1].size == Decimal("2")


class TestLIFO:
    def test_multi_lot_lifo_order(self):
        """Last-in lots are consumed first."""
        engine = PnLEngine(CostBasisMethod.LIFO)
        engine.add_buy("ETH", Decimal("100"), Decimal("5"), _ts(1))
        engine.add_buy("ETH", Decimal("200"), Decimal("5"), _ts(2))

        realized = engine.add_sell("ETH", Decimal("150"), Decimal("7"), _ts(3))

        # LIFO: second lot (5@200) consumed first, then 2 from first lot (2@100)
        assert len(realized) == 2
        assert realized[0].lot_entry_price == Decimal("200")
        assert realized[0].size == Decimal("5")
        assert realized[0].pnl == Decimal("-250")  # (150-200)*5
        assert realized[1].lot_entry_price == Decimal("100")
        assert realized[1].size == Decimal("2")
        assert realized[1].pnl == Decimal("100")  # (150-100)*2

        pos = engine.get_position("ETH")
        assert pos.total_size == Decimal("3")
        assert pos.lots[0].entry_price == Decimal("100")

    def test_lifo_three_lots(self):
        engine = PnLEngine(CostBasisMethod.LIFO)
        engine.add_buy("ETH", Decimal("50"), Decimal("10"), _ts(1))
        engine.add_buy("ETH", Decimal("100"), Decimal("10"), _ts(2))
        engine.add_buy("ETH", Decimal("150"), Decimal("10"), _ts(3))

        realized = engine.add_sell("ETH", Decimal("120"), Decimal("15"), _ts(4))

        # LIFO: lot3 (10@150) first, then lot2 (5@100)
        assert len(realized) == 2
        assert realized[0].lot_entry_price == Decimal("150")
        assert realized[0].size == Decimal("10")
        assert realized[1].lot_entry_price == Decimal("100")
        assert realized[1].size == Decimal("5")

        pos = engine.get_position("ETH")
        assert pos.total_size == Decimal("15")


class TestAverageCost:
    def test_average_cost_single_sell(self):
        engine = PnLEngine(CostBasisMethod.AVERAGE)
        engine.add_buy("SOL", Decimal("100"), Decimal("10"), _ts(1))
        engine.add_buy("SOL", Decimal("200"), Decimal("10"), _ts(2))

        # Average cost = (100*10 + 200*10) / 20 = 150
        realized = engine.add_sell("SOL", Decimal("180"), Decimal("10"), _ts(3))

        assert len(realized) == 1
        assert realized[0].lot_entry_price == Decimal("150")
        assert realized[0].size == Decimal("10")
        assert realized[0].pnl == Decimal("300")  # (180-150)*10

        pos = engine.get_position("SOL")
        assert pos.total_size == Decimal("10")

    def test_average_cost_full_liquidation(self):
        engine = PnLEngine(CostBasisMethod.AVERAGE)
        engine.add_buy("SOL", Decimal("100"), Decimal("5"), _ts(1))
        engine.add_buy("SOL", Decimal("200"), Decimal("5"), _ts(2))

        realized = engine.add_sell("SOL", Decimal("170"), Decimal("10"), _ts(3))

        assert realized[0].pnl == Decimal("200")  # (170-150)*10
        pos = engine.get_position("SOL")
        assert pos.total_size == Decimal("0")

    def test_average_cost_sequential_sells(self):
        engine = PnLEngine(CostBasisMethod.AVERAGE)
        engine.add_buy("SOL", Decimal("100"), Decimal("20"), _ts(1))
        engine.add_buy("SOL", Decimal("200"), Decimal("20"), _ts(2))

        # Avg = 150. Sell half
        r1 = engine.add_sell("SOL", Decimal("180"), Decimal("20"), _ts(3))
        assert r1[0].pnl == Decimal("600")  # (180-150)*20

        # Remaining avg still 150. Add more at 300
        engine.add_buy("SOL", Decimal("300"), Decimal("20"), _ts(4))
        # New avg = (150*20 + 300*20) / 40 = 225
        pos = engine.get_position("SOL")
        assert pos.avg_entry_price == Decimal("225")


class TestUnrealizedPnL:
    def test_unrealized_pnl(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("5"), _ts(1))
        engine.add_buy("BTC", Decimal("200"), Decimal("5"), _ts(2))

        pos = engine.get_position("BTC")
        unrealized = pos.unrealized_pnl(Decimal("150"))

        assert len(unrealized) == 2
        assert unrealized[0].pnl == Decimal("250")  # (150-100)*5
        assert unrealized[1].pnl == Decimal("-250")  # (150-200)*5

        total = pos.total_unrealized_pnl(Decimal("150"))
        assert total == Decimal("0")

    def test_unrealized_after_partial_sell(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("10"), _ts(1))
        engine.add_sell("BTC", Decimal("120"), Decimal("3"), _ts(2))

        pos = engine.get_position("BTC")
        total = pos.total_unrealized_pnl(Decimal("130"))
        assert total == Decimal("210")  # (130-100)*7


class TestEdgeCases:
    def test_sell_exceeds_position_raises(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("5"), _ts(1))

        with pytest.raises(ValueError, match="exceeds position size"):
            engine.add_sell("BTC", Decimal("110"), Decimal("10"), _ts(2))

    def test_sell_empty_position_raises(self):
        engine = PnLEngine(CostBasisMethod.FIFO)

        with pytest.raises(ValueError, match="exceeds position size"):
            engine.add_sell("BTC", Decimal("100"), Decimal("1"), _ts(1))

    def test_multiple_symbols(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("5"), _ts(1))
        engine.add_buy("ETH", Decimal("50"), Decimal("10"), _ts(1))

        engine.add_sell("BTC", Decimal("120"), Decimal("5"), _ts(2))

        assert engine.get_position("BTC").total_realized_pnl == Decimal("100")
        assert engine.get_position("ETH").total_size == Decimal("10")
        assert engine.get_position("ETH").total_realized_pnl == Decimal("0")

    def test_pnl_pct(self):
        engine = PnLEngine(CostBasisMethod.FIFO)
        engine.add_buy("BTC", Decimal("100"), Decimal("10"), _ts(1))
        realized = engine.add_sell("BTC", Decimal("120"), Decimal("10"), _ts(2))

        assert realized[0].pnl_pct == Decimal("20")
