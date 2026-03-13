"""
Order Execution Simulator engine.

Handles order placement, fill simulation with slippage and fees,
partial fills based on volume, and order lifecycle management.
"""

import logging
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from services.order_simulator.models import (
    FeeSchedule,
    OrderFill,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    SlippageConfig,
    SlippageModel,
)

logger = logging.getLogger(__name__)


class OrderSimulator:
    """Simulates order execution with realistic fill models."""

    def __init__(
        self,
        initial_balance: float = 100_000.0,
        slippage_config: Optional[SlippageConfig] = None,
        fee_schedule: Optional[FeeSchedule] = None,
        max_fill_ratio: float = 0.3,
    ):
        self.slippage_config = slippage_config or SlippageConfig()
        self.fee_schedule = fee_schedule or FeeSchedule()
        self.max_fill_ratio = max_fill_ratio

        self._orders: Dict[str, SimulatedOrder] = {}
        self._cash_balance: float = initial_balance
        self._initial_balance: float = initial_balance
        self._positions: Dict[str, float] = {}
        self._position_avg_prices: Dict[str, float] = {}

    @property
    def orders(self) -> Dict[str, SimulatedOrder]:
        return self._orders

    @property
    def cash_balance(self) -> float:
        return self._cash_balance

    @property
    def positions(self) -> Dict[str, float]:
        return self._positions

    @property
    def position_avg_prices(self) -> Dict[str, float]:
        return self._position_avg_prices

    def place_order(self, order: SimulatedOrder) -> SimulatedOrder:
        """Place an order into the simulator."""
        if order.order_type != OrderType.MARKET and order.price is None:
            raise ValueError(
                f"{order.order_type.value} orders require a price"
            )

        self._orders[order.id] = order
        order.status = OrderStatus.OPEN
        order.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("Order placed: %s %s %s %.4f @ %s",
                     order.side.value, order.order_type.value,
                     order.instrument, order.quantity,
                     order.price or "MARKET")
        return order

    def cancel_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """Cancel an open order."""
        order = self._orders.get(order_id)
        if order is None:
            return None
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED):
            return None
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc).isoformat()
        return order

    def process_market_tick(
        self,
        instrument: str,
        bid: float,
        ask: float,
        volume: float = 1_000_000.0,
        volatility: float = 0.02,
    ) -> List[OrderFill]:
        """Process a market tick and attempt to fill eligible orders."""
        fills = []
        now = datetime.now(timezone.utc).isoformat()

        for order in list(self._orders.values()):
            if order.instrument != instrument:
                continue
            if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                continue

            # Check expiration
            if order.expires_at and order.expires_at < now:
                order.status = OrderStatus.EXPIRED
                order.updated_at = now
                continue

            fill = self._try_fill(order, bid, ask, volume, volatility)
            if fill:
                fills.append(fill)

        return fills

    def _try_fill(
        self,
        order: SimulatedOrder,
        bid: float,
        ask: float,
        volume: float,
        volatility: float,
    ) -> Optional[OrderFill]:
        """Attempt to fill an order based on current market conditions."""
        mid = (bid + ask) / 2.0
        should_fill, base_price = self._should_fill(order, bid, ask)
        if not should_fill:
            return None

        remaining = order.quantity - order.filled_quantity
        fill_qty = self._compute_fill_quantity(remaining, volume)
        if fill_qty <= 0:
            return None

        slippage = self._compute_slippage(base_price, order.side, volatility)
        fill_price = base_price + slippage

        is_maker = order.order_type == OrderType.LIMIT
        fee_rate = self.fee_schedule.maker_fee if is_maker else self.fee_schedule.taker_fee
        fee = abs(fill_qty * fill_price * fee_rate)

        # Update balance and positions
        cost = fill_qty * fill_price + fee
        if order.side == OrderSide.BUY:
            if self._cash_balance < cost:
                return None
            self._cash_balance -= cost
            self._update_position(order.instrument, fill_qty, fill_price)
        else:
            current_pos = self._positions.get(order.instrument, 0.0)
            if current_pos < fill_qty:
                return None
            self._cash_balance += fill_qty * fill_price - fee
            self._update_position(order.instrument, -fill_qty, fill_price)

        fill = OrderFill(
            order_id=order.id,
            fill_price=round(fill_price, 8),
            quantity=round(fill_qty, 8),
            fee=round(fee, 8),
            slippage=round(slippage, 8),
        )

        order.fills.append(fill)
        order.filled_quantity = round(order.filled_quantity + fill_qty, 8)
        order.total_fees = round(order.total_fees + fee, 8)
        total_cost = sum(f.fill_price * f.quantity for f in order.fills)
        order.average_fill_price = round(total_cost / order.filled_quantity, 8)

        if abs(order.filled_quantity - order.quantity) < 1e-10:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        order.updated_at = datetime.now(timezone.utc).isoformat()
        return fill

    def _should_fill(
        self, order: SimulatedOrder, bid: float, ask: float
    ) -> Tuple[bool, float]:
        """Determine if an order should fill and at what base price."""
        if order.order_type == OrderType.MARKET:
            price = ask if order.side == OrderSide.BUY else bid
            return True, price

        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and ask <= order.price:
                return True, ask
            if order.side == OrderSide.SELL and bid >= order.price:
                return True, bid
            return False, 0.0

        if order.order_type == OrderType.STOP_LOSS:
            if order.side == OrderSide.SELL and bid <= order.price:
                return True, bid
            if order.side == OrderSide.BUY and ask >= order.price:
                return True, ask
            return False, 0.0

        if order.order_type == OrderType.TAKE_PROFIT:
            if order.side == OrderSide.SELL and bid >= order.price:
                return True, bid
            if order.side == OrderSide.BUY and ask <= order.price:
                return True, ask
            return False, 0.0

        return False, 0.0

    def _compute_fill_quantity(self, remaining: float, volume: float) -> float:
        """Compute fill quantity based on available volume."""
        max_from_volume = volume * self.max_fill_ratio
        return min(remaining, max_from_volume)

    def _compute_slippage(
        self, base_price: float, side: OrderSide, volatility: float
    ) -> float:
        """Compute slippage based on the configured model."""
        direction = 1.0 if side == OrderSide.BUY else -1.0

        if self.slippage_config.model == SlippageModel.FIXED:
            return direction * self.slippage_config.value

        if self.slippage_config.model == SlippageModel.PERCENTAGE:
            return direction * base_price * self.slippage_config.value

        if self.slippage_config.model == SlippageModel.VOLATILITY:
            random_factor = random.uniform(0.5, 1.5)
            return direction * base_price * volatility * self.slippage_config.value * random_factor

        return 0.0

    def _update_position(
        self, instrument: str, quantity_delta: float, price: float
    ) -> None:
        """Update position tracking."""
        current_qty = self._positions.get(instrument, 0.0)
        current_avg = self._position_avg_prices.get(instrument, 0.0)

        new_qty = current_qty + quantity_delta

        if abs(new_qty) < 1e-10:
            self._positions.pop(instrument, None)
            self._position_avg_prices.pop(instrument, None)
            return

        if quantity_delta > 0:
            if current_qty > 0:
                total_cost = current_avg * current_qty + price * quantity_delta
                new_avg = total_cost / new_qty
            else:
                new_avg = price
        else:
            new_avg = current_avg

        self._positions[instrument] = round(new_qty, 8)
        self._position_avg_prices[instrument] = round(new_avg, 8)

    def get_open_orders(self, instrument: Optional[str] = None) -> List[SimulatedOrder]:
        """Get all open/partially filled orders, optionally filtered by instrument."""
        result = []
        for order in self._orders.values():
            if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                continue
            if instrument and order.instrument != instrument:
                continue
            result.append(order)
        return result

    def get_all_orders(self, instrument: Optional[str] = None) -> List[SimulatedOrder]:
        """Get all orders, optionally filtered by instrument."""
        if instrument:
            return [o for o in self._orders.values() if o.instrument == instrument]
        return list(self._orders.values())

    def get_balance_summary(self) -> dict:
        """Get current balance and position summary."""
        return {
            "cash_balance": round(self._cash_balance, 2),
            "initial_balance": self._initial_balance,
            "positions": {
                k: {
                    "quantity": v,
                    "avg_entry_price": self._position_avg_prices.get(k, 0.0),
                }
                for k, v in self._positions.items()
            },
            "open_order_count": len(self.get_open_orders()),
            "total_order_count": len(self._orders),
        }
