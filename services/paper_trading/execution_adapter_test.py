"""Tests for deterministic paper execution primitives."""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.paper_trading.execution_adapter import (
    DeterministicPaperExecutionAdapter,
    MarketSnapshot,
    TradeIntent,
)


NOW = datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc)


def make_intent(**overrides):
    values = {
        "intent_id": "intent-1",
        "strategy_id": "strategy-a",
        "instrument": "BTC-USD",
        "asset_class": "crypto",
        "venue": "coinbase",
        "side": "buy",
        "order_type": "market",
        "quantity": Decimal("0.01"),
        "max_notional_usd": Decimal("1000"),
        "signal_timestamp_utc": NOW,
        "rationale_ref": "decision-1",
    }
    values.update(overrides)
    return TradeIntent(**values)


def make_snapshot(**overrides):
    values = {
        "snapshot_id": "snapshot-1",
        "instrument": "BTC-USD",
        "venue": "coinbase",
        "best_bid": Decimal("49990.00"),
        "best_ask": Decimal("50010.00"),
        "captured_at_utc": NOW - timedelta(seconds=5),
        "data_source": "stored-book",
        "fee_bps": Decimal("10"),
        "slippage_bps": Decimal("5"),
        "latency_ms": 250,
    }
    values.update(overrides)
    return MarketSnapshot(**values)


class DeterministicPaperExecutionAdapterTest(unittest.TestCase):
    def test_buy_fill_uses_ask_plus_slippage_and_fee(self):
        adapter = DeterministicPaperExecutionAdapter()

        fill = adapter.simulate_fill(make_intent(), make_snapshot(), NOW)

        self.assertEqual(fill.status, "filled")
        self.assertEqual(fill.fill_price, Decimal("50035.01"))
        self.assertEqual(fill.fill_quantity, Decimal("0.01"))
        self.assertEqual(fill.fee_quote, Decimal("0.50"))
        self.assertEqual(fill.slippage_vs_mid, Decimal("35.01"))
        self.assertEqual(fill.snapshot_id, "snapshot-1")
        self.assertIsNone(fill.reject_reason)

    def test_sell_fill_uses_bid_minus_slippage_and_fee(self):
        adapter = DeterministicPaperExecutionAdapter()

        fill = adapter.simulate_fill(
            make_intent(side="sell", max_notional_usd=None),
            make_snapshot(),
            NOW,
        )

        self.assertEqual(fill.status, "filled")
        self.assertEqual(fill.fill_price, Decimal("49965.01"))
        self.assertEqual(fill.fee_quote, Decimal("0.50"))
        self.assertEqual(fill.slippage_vs_mid, Decimal("34.99"))

    def test_replay_is_deterministic_for_same_intent_snapshot_and_clock(self):
        adapter = DeterministicPaperExecutionAdapter()
        intent = make_intent()
        snapshot = make_snapshot()

        first = adapter.simulate_fill(intent, snapshot, NOW)
        second = adapter.simulate_fill(intent, snapshot, NOW)

        self.assertEqual(first, second)

    def test_rejects_stale_snapshot_without_fill_price(self):
        adapter = DeterministicPaperExecutionAdapter(max_snapshot_age_seconds=30)

        fill = adapter.simulate_fill(
            make_intent(),
            make_snapshot(captured_at_utc=NOW - timedelta(seconds=31)),
            NOW,
        )

        self.assertEqual(fill.status, "rejected")
        self.assertEqual(fill.reject_reason, "stale_snapshot")
        self.assertIsNone(fill.fill_price)
        self.assertEqual(fill.fill_quantity, Decimal("0"))

    def test_rejects_buy_that_exceeds_max_notional(self):
        adapter = DeterministicPaperExecutionAdapter()

        fill = adapter.simulate_fill(
            make_intent(quantity=Decimal("1"), max_notional_usd=Decimal("100")),
            make_snapshot(),
            NOW,
        )

        self.assertEqual(fill.status, "rejected")
        self.assertEqual(fill.reject_reason, "max_notional_exceeded")

    def test_rejects_mismatched_instrument_before_simulating(self):
        adapter = DeterministicPaperExecutionAdapter()

        fill = adapter.simulate_fill(
            make_intent(instrument="ETH-USD"), make_snapshot(), NOW
        )

        self.assertEqual(fill.status, "rejected")
        self.assertEqual(fill.reject_reason, "instrument_mismatch")


if __name__ == "__main__":
    unittest.main()
