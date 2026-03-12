"""Order execution simulator for paper trading.

Simulates realistic order fills with configurable slippage, fee
calculation, limit order matching, and fill report generation.
"""

import enum
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


class OrderType(enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"


class SlippageModel(enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


@dataclass
class FeeSchedule:
    maker_fee_rate: float = 0.001
    taker_fee_rate: float = 0.002
    min_fee: float = 0.0

    def calculate_fee(self, notional: float, is_maker: bool) -> float:
        rate = self.maker_fee_rate if is_maker else self.taker_fee_rate
        fee = notional * rate
        return max(fee, self.min_fee)


@dataclass
class SlippageConfig:
    model: SlippageModel = SlippageModel.PERCENTAGE
    value: float = 0.001  # 0.1% default
    randomize: bool = True

    def apply(self, price: float, side: OrderSide) -> float:
        if self.value == 0:
            return price

        if self.randomize:
            slip = random.uniform(0, self.value)
        else:
            slip = self.value

        if self.model == SlippageModel.PERCENTAGE:
            adjustment = price * slip
        else:
            adjustment = slip

        if side == OrderSide.BUY:
            return price + adjustment
        return price - adjustment


@dataclass
class SimulatorConfig:
    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    fees: FeeSchedule = field(default_factory=FeeSchedule)
    partial_fill_enabled: bool = False
    partial_fill_min_ratio: float = 0.5

    @classmethod
    def from_dict(cls, data: dict) -> "SimulatorConfig":
        slippage_data = data.get("slippage", {})
        slippage_model = SlippageModel(slippage_data.get("model", "PERCENTAGE").upper())
        slippage = SlippageConfig(
            model=slippage_model,
            value=float(slippage_data.get("value", 0.001)),
            randomize=slippage_data.get("randomize", True),
        )

        fees_data = data.get("fees", {})
        fees = FeeSchedule(
            maker_fee_rate=float(fees_data.get("maker_fee_rate", 0.001)),
            taker_fee_rate=float(fees_data.get("taker_fee_rate", 0.002)),
            min_fee=float(fees_data.get("min_fee", 0.0)),
        )

        return cls(
            slippage=slippage,
            fees=fees,
            partial_fill_enabled=data.get("partial_fill_enabled", False),
            partial_fill_min_ratio=float(data.get("partial_fill_min_ratio", 0.5)),
        )


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")


@dataclass
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: str
    fill_price: float
    quantity: float
    fee: float
    slippage: float
    notional: float
    net_cost: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "fill_price": self.fill_price,
            "quantity": self.quantity,
            "fee": self.fee,
            "slippage": self.slippage,
            "notional": self.notional,
            "net_cost": self.net_cost,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0

    @property
    def notional_value(self) -> float:
        return abs(self.quantity) * self.avg_entry_price

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_entry_price": round(self.avg_entry_price, 8),
            "realized_pnl": round(self.realized_pnl, 8),
            "total_fees": round(self.total_fees, 8),
        }


class OrderSimulator:
    """Simulates order execution with slippage, fees, and position tracking."""

    def __init__(self, config: Optional[SimulatorConfig] = None):
        self.config = config or SimulatorConfig()
        self._orders: Dict[str, Order] = {}
        self._fills: List[Fill] = []
        self._positions: Dict[str, Position] = {}
        self._pending_limits: Dict[str, Order] = {}

    def submit_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        current_price: float,
    ) -> Fill:
        """Submit and immediately fill a market order."""
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if current_price <= 0:
            raise ValueError("current_price must be positive")

        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
        )
        self._orders[order.order_id] = order

        fill_price = self.config.slippage.apply(current_price, side)
        fill = self._execute_fill(order, fill_price, quantity, is_maker=False)
        order.status = OrderStatus.FILLED
        return fill

    def submit_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        limit_price: float,
    ) -> Order:
        """Submit a limit order. It will be filled when price crosses."""
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if limit_price <= 0:
            raise ValueError("limit_price must be positive")

        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            limit_price=limit_price,
        )
        self._orders[order.order_id] = order
        self._pending_limits[order.order_id] = order
        return order

    def check_limit_orders(self, symbol: str, current_price: float) -> List[Fill]:
        """Check pending limit orders against current price and fill eligible ones."""
        fills = []
        to_remove = []

        for order_id, order in self._pending_limits.items():
            if order.symbol != symbol:
                continue

            should_fill = False
            if order.side == OrderSide.BUY and current_price <= order.limit_price:
                should_fill = True
            elif order.side == OrderSide.SELL and current_price >= order.limit_price:
                should_fill = True

            if should_fill:
                fill = self._execute_fill(
                    order, order.limit_price, order.quantity, is_maker=True
                )
                order.status = OrderStatus.FILLED
                to_remove.append(order_id)
                fills.append(fill)

        for order_id in to_remove:
            del self._pending_limits[order_id]

        return fills

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending limit order."""
        if order_id in self._pending_limits:
            self._pending_limits[order_id].status = OrderStatus.CANCELLED
            del self._pending_limits[order_id]
            return True
        return False

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for a symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        return dict(self._positions)

    def get_fills(self, symbol: Optional[str] = None, limit: int = 100) -> List[Fill]:
        """Get fill history, optionally filtered by symbol."""
        fills = self._fills
        if symbol:
            fills = [f for f in fills if f.symbol == symbol]
        return fills[-limit:]

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get pending limit orders."""
        orders = list(self._pending_limits.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_fill_report(self, symbol: Optional[str] = None) -> dict:
        """Generate a summary fill report."""
        fills = self.get_fills(symbol=symbol, limit=10000)
        if not fills:
            return {
                "total_fills": 0,
                "total_volume": 0.0,
                "total_fees": 0.0,
                "total_slippage_cost": 0.0,
                "avg_fill_price": 0.0,
                "fills": [],
            }

        total_volume = sum(f.notional for f in fills)
        total_fees = sum(f.fee for f in fills)
        total_slippage = sum(f.slippage for f in fills)
        avg_price = sum(f.fill_price * f.quantity for f in fills) / sum(
            f.quantity for f in fills
        )

        return {
            "total_fills": len(fills),
            "total_volume": round(total_volume, 8),
            "total_fees": round(total_fees, 8),
            "total_slippage_cost": round(total_slippage, 8),
            "avg_fill_price": round(avg_price, 8),
            "fills": [f.to_dict() for f in fills],
        }

    def get_pnl_summary(self) -> dict:
        """Get P&L summary across all positions."""
        total_realized = sum(p.realized_pnl for p in self._positions.values())
        total_fees = sum(p.total_fees for p in self._positions.values())

        return {
            "total_realized_pnl": round(total_realized, 8),
            "total_fees": round(total_fees, 8),
            "net_pnl": round(total_realized - total_fees, 8),
            "positions": {
                sym: pos.to_dict() for sym, pos in self._positions.items()
            },
        }

    def reset(self) -> None:
        """Reset all simulator state."""
        self._orders.clear()
        self._fills.clear()
        self._positions.clear()
        self._pending_limits.clear()

    def _execute_fill(
        self,
        order: Order,
        fill_price: float,
        quantity: float,
        is_maker: bool,
    ) -> Fill:
        """Execute a fill and update positions."""
        notional = fill_price * quantity
        fee = self.config.fees.calculate_fee(notional, is_maker)

        # Calculate slippage cost
        if order.order_type == OrderType.MARKET:
            base_price = fill_price  # slippage already applied
            # Recover the original price to compute slippage amount
            if self.config.slippage.model == SlippageModel.PERCENTAGE:
                if order.side == OrderSide.BUY:
                    original = fill_price / (1 + self.config.slippage.value)
                else:
                    original = fill_price / (1 - self.config.slippage.value)
                slippage_cost = abs(fill_price - original) * quantity
            else:
                slippage_cost = self.config.slippage.value * quantity
        else:
            slippage_cost = 0.0

        if order.side == OrderSide.BUY:
            net_cost = notional + fee
        else:
            net_cost = notional - fee

        fill = Fill(
            fill_id=str(uuid.uuid4()),
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            fill_price=round(fill_price, 8),
            quantity=quantity,
            fee=round(fee, 8),
            slippage=round(slippage_cost, 8),
            notional=round(notional, 8),
            net_cost=round(net_cost, 8),
        )
        self._fills.append(fill)
        self._update_position(order.symbol, order.side, quantity, fill_price, fee)
        return fill

    def _update_position(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        fee: float,
    ) -> None:
        """Update position tracking after a fill."""
        if symbol not in self._positions:
            self._positions[symbol] = Position(symbol=symbol)

        pos = self._positions[symbol]
        pos.total_fees += fee

        if side == OrderSide.BUY:
            if pos.quantity >= 0:
                # Adding to long position
                total_cost = pos.avg_entry_price * pos.quantity + price * quantity
                pos.quantity += quantity
                pos.avg_entry_price = (
                    total_cost / pos.quantity if pos.quantity > 0 else 0
                )
            else:
                # Closing/reducing short position
                close_qty = min(quantity, abs(pos.quantity))
                pos.realized_pnl += (pos.avg_entry_price - price) * close_qty
                remaining_buy = quantity - close_qty
                pos.quantity += close_qty
                if remaining_buy > 0:
                    pos.quantity += remaining_buy
                    pos.avg_entry_price = price
        else:
            if pos.quantity <= 0:
                # Adding to short position
                total_cost = abs(pos.avg_entry_price * pos.quantity) + price * quantity
                pos.quantity -= quantity
                pos.avg_entry_price = (
                    total_cost / abs(pos.quantity) if pos.quantity != 0 else 0
                )
            else:
                # Closing/reducing long position
                close_qty = min(quantity, pos.quantity)
                pos.realized_pnl += (price - pos.avg_entry_price) * close_qty
                remaining_sell = quantity - close_qty
                pos.quantity -= close_qty
                if remaining_sell > 0:
                    pos.quantity -= remaining_sell
                    pos.avg_entry_price = price
