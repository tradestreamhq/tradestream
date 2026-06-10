"""Deterministic paper execution primitives.

This module implements the first code boundary from the paper execution
adapter spec. It is intentionally pure: it does not talk to brokers,
credentials, databases, or live execution APIs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional


AssetClass = Literal["crypto", "equities", "forex"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["market"]


@dataclass(frozen=True)
class TradeIntent:
    """Normalized request from a strategy or agent."""

    intent_id: str
    strategy_id: str
    instrument: str
    asset_class: AssetClass
    venue: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    max_notional_usd: Optional[Decimal]
    signal_timestamp_utc: datetime
    rationale_ref: str


@dataclass(frozen=True)
class MarketSnapshot:
    """Reproducible market state used for paper simulation."""

    snapshot_id: str
    instrument: str
    venue: str
    best_bid: Decimal
    best_ask: Decimal
    captured_at_utc: datetime
    data_source: str
    fee_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("5")
    latency_ms: int = 250


@dataclass(frozen=True)
class PaperFill:
    """Simulated execution result for one intent."""

    intent_id: str
    status: Literal["filled", "rejected"]
    fill_price: Optional[Decimal]
    fill_quantity: Decimal
    fee_quote: Decimal
    slippage_vs_mid: Optional[Decimal]
    latency_ms: int
    snapshot_id: str
    reject_reason: Optional[str] = None


class DeterministicPaperExecutionAdapter:
    """Simulates market fills against explicit snapshots."""

    def __init__(self, max_snapshot_age_seconds: int = 60):
        self._max_snapshot_age_seconds = max_snapshot_age_seconds

    def simulate_fill(
        self,
        intent: TradeIntent,
        snapshot: MarketSnapshot,
        now_utc: datetime,
    ) -> PaperFill:
        """Simulate a fill or deterministic rejection for an intent."""

        reject_reason = self._reject_reason(intent, snapshot, now_utc)
        if reject_reason is not None:
            return PaperFill(
                intent_id=intent.intent_id,
                status="rejected",
                fill_price=None,
                fill_quantity=Decimal("0"),
                fee_quote=Decimal("0"),
                slippage_vs_mid=None,
                latency_ms=snapshot.latency_ms,
                snapshot_id=snapshot.snapshot_id,
                reject_reason=reject_reason,
            )

        mid = (snapshot.best_bid + snapshot.best_ask) / Decimal("2")
        reference_price = snapshot.best_ask if intent.side == "buy" else snapshot.best_bid
        slippage_multiplier = snapshot.slippage_bps / Decimal("10000")
        price_delta = reference_price * slippage_multiplier
        fill_price = (
            reference_price + price_delta
            if intent.side == "buy"
            else reference_price - price_delta
        )
        fill_price = _quantize_usd(fill_price)
        fee_quote = _quantize_usd(
            fill_price * intent.quantity * snapshot.fee_bps / Decimal("10000")
        )

        return PaperFill(
            intent_id=intent.intent_id,
            status="filled",
            fill_price=fill_price,
            fill_quantity=intent.quantity,
            fee_quote=fee_quote,
            slippage_vs_mid=_quantize_usd(abs(fill_price - mid)),
            latency_ms=snapshot.latency_ms,
            snapshot_id=snapshot.snapshot_id,
        )

    def _reject_reason(
        self,
        intent: TradeIntent,
        snapshot: MarketSnapshot,
        now_utc: datetime,
    ) -> Optional[str]:
        if intent.order_type != "market":
            return "unsupported_order_type"
        if intent.quantity <= 0:
            return "invalid_quantity"
        if intent.instrument != snapshot.instrument:
            return "instrument_mismatch"
        if intent.venue != snapshot.venue:
            return "venue_mismatch"
        if snapshot.best_bid <= 0 or snapshot.best_ask <= 0:
            return "invalid_snapshot_price"
        if snapshot.best_bid > snapshot.best_ask:
            return "crossed_snapshot"
        if _age_seconds(snapshot.captured_at_utc, now_utc) > self._max_snapshot_age_seconds:
            return "stale_snapshot"

        reference_price = snapshot.best_ask if intent.side == "buy" else snapshot.best_bid
        notional = reference_price * intent.quantity
        if (
            intent.max_notional_usd is not None
            and intent.side == "buy"
            and notional > intent.max_notional_usd
        ):
            return "max_notional_exceeded"
        return None


def _age_seconds(earlier: datetime, later: datetime) -> float:
    if earlier.tzinfo is None:
        earlier = earlier.replace(tzinfo=timezone.utc)
    if later.tzinfo is None:
        later = later.replace(tzinfo=timezone.utc)
    return (later - earlier).total_seconds()


def _quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
