"""Order execution simulator for paper trading.

Accepts order signals, simulates fills at market prices, and delegates
position/P&L tracking to the VirtualPortfolio.
"""

import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from services.paper_trading.models import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TradeRecord,
)
from services.paper_trading.virtual_portfolio import VirtualPortfolio


PriceFn = Callable[[str], Optional[float]]
"""A callable that returns the current price for a symbol, or None."""


class OrderExecutionSimulator:
    """Simulates order execution against market prices.

    Args:
        initial_balance: Starting virtual cash.
        price_fn: Callable returning current market price for a symbol.
        commission_rate: Fraction charged per trade (e.g. 0.001 = 0.1%).
        slippage_rate: Simulated slippage as fraction of price (e.g. 0.0005).
        max_position_pct: Max fraction of equity for a single position.
    """

    def __init__(
        self,
        initial_balance: float = 100_000.0,
        price_fn: Optional[PriceFn] = None,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        max_position_pct: float = 0.1,
    ):
        self.portfolio = VirtualPortfolio(initial_balance)
        self._price_fn = price_fn or (lambda s: None)
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_position_pct = max_position_pct
        self._orders: Dict[str, Order] = {}
        self._pending_limit_orders: Dict[str, Order] = {}

    def get_price(self, symbol: str) -> Optional[float]:
        return self._price_fn(symbol)

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> Order:
        """Submit an order to the simulator.

        Market orders are filled immediately. Limit orders are stored
        and filled when check_limit_orders is called with matching prices.
        """
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
        )
        self._orders[order_id] = order

        if order_type == OrderType.MARKET:
            self._try_fill_market(order)
        elif order_type == OrderType.LIMIT:
            if limit_price is None:
                order.status = OrderStatus.REJECTED
            else:
                self._pending_limit_orders[order_id] = order
        return order

    def _try_fill_market(self, order: Order) -> Optional[Fill]:
        """Attempt to fill a market order at the current price."""
        price = self.get_price(order.symbol)
        if price is None:
            order.status = OrderStatus.REJECTED
            return None

        # Validate sufficient funds for buys
        if order.side == OrderSide.BUY:
            cost = order.quantity * price
            if cost > self.portfolio.cash:
                order.status = OrderStatus.REJECTED
                return None

        fill_price = self._apply_slippage(price, order.side)
        commission = order.quantity * fill_price * self.commission_rate

        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
        )
        self.portfolio.apply_fill(fill)
        order.status = OrderStatus.FILLED
        return fill

    def _try_fill_limit(
        self, order: Order, current_price: float
    ) -> Optional[Fill]:
        """Attempt to fill a limit order if price condition is met."""
        if order.limit_price is None:
            return None

        should_fill = False
        if order.side == OrderSide.BUY and current_price <= order.limit_price:
            should_fill = True
        elif order.side == OrderSide.SELL and current_price >= order.limit_price:
            should_fill = True

        if not should_fill:
            return None

        # Validate sufficient funds for buys
        if order.side == OrderSide.BUY:
            cost = order.quantity * order.limit_price
            if cost > self.portfolio.cash:
                order.status = OrderStatus.REJECTED
                self._pending_limit_orders.pop(order.order_id, None)
                return None

        fill_price = order.limit_price
        commission = order.quantity * fill_price * self.commission_rate

        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
        )
        self.portfolio.apply_fill(fill)
        order.status = OrderStatus.FILLED
        self._pending_limit_orders.pop(order.order_id, None)
        return fill

    def check_limit_orders(
        self, current_prices: Optional[Dict[str, float]] = None
    ) -> List[Fill]:
        """Check all pending limit orders against current prices.

        Args:
            current_prices: Dict of symbol -> price. If None, uses price_fn.

        Returns:
            List of fills that occurred.
        """
        fills = []
        for order_id in list(self._pending_limit_orders):
            order = self._pending_limit_orders[order_id]
            if current_prices and order.symbol in current_prices:
                price = current_prices[order.symbol]
            else:
                price = self.get_price(order.symbol)
            if price is None:
                continue
            fill = self._try_fill_limit(order, price)
            if fill:
                fills.append(fill)
        return fills

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending limit order. Returns True if cancelled."""
        order = self._pending_limit_orders.pop(order_id, None)
        if order is None:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        """Apply simulated slippage to the fill price."""
        if side == OrderSide.BUY:
            return price * (1 + self.slippage_rate)
        return price * (1 - self.slippage_rate)

    def compute_position_size(
        self,
        symbol: str,
        price: Optional[float] = None,
    ) -> float:
        """Compute recommended position size based on account balance.

        Uses max_position_pct of current cash.
        """
        if price is None:
            price = self.get_price(symbol)
        if price is None or price <= 0:
            return 0.0
        return self.portfolio.max_position_size(price, self.max_position_pct)

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    @property
    def pending_orders(self) -> List[Order]:
        return list(self._pending_limit_orders.values())

    @property
    def trade_log(self) -> List[TradeRecord]:
        return self.portfolio.trade_log

    def record_daily_snapshot(
        self,
        date: str,
        current_prices: Optional[Dict[str, float]] = None,
    ):
        """Record end-of-day performance snapshot."""
        prices = current_prices or {}
        return self.portfolio.record_daily_snapshot(date, prices)

    def summary(self, current_prices: Optional[Dict[str, float]] = None) -> dict:
        """Return portfolio summary."""
        prices = current_prices or {}
        return self.portfolio.summary(prices)
