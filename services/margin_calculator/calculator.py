"""
Margin calculator service.

Computes margin requirements, buying power, and margin utilization
based on position size, exchange rules, and account type.
"""

from typing import Dict, Optional

from services.margin_calculator.models import (
    DEFAULT_EXCHANGE_RATES,
    ExchangeMarginRates,
    MarginRequirementRequest,
    MarginRequirementResult,
    MarginType,
)


class MarginCalculator:
    """Calculates margin requirements for different order types and exchanges."""

    def __init__(
        self,
        exchange_rates: Optional[Dict[str, ExchangeMarginRates]] = None,
    ):
        self._rates = exchange_rates or DEFAULT_EXCHANGE_RATES

    def get_exchange_rates(self, exchange: str) -> ExchangeMarginRates:
        """Return margin rates for the given exchange, falling back to default."""
        return self._rates.get(exchange, self._rates["default"])

    def compute_margin(
        self, margin_type: MarginType, notional_value: float, rates: ExchangeMarginRates
    ) -> float:
        """Compute margin requirement for a given type and notional value."""
        if margin_type == MarginType.INITIAL:
            return notional_value * rates.initial_rate
        elif margin_type == MarginType.MAINTENANCE:
            return notional_value * rates.maintenance_rate
        elif margin_type == MarginType.PORTFOLIO:
            return notional_value * rates.portfolio_rate
        raise ValueError(f"Unknown margin type: {margin_type}")

    def calculate(self, req: MarginRequirementRequest) -> MarginRequirementResult:
        """Calculate full margin requirements for an order."""
        rates = self.get_exchange_rates(req.exchange)
        notional_value = req.quantity * req.price

        initial_margin = self.compute_margin(
            MarginType.INITIAL, notional_value, rates
        )
        maintenance_margin = self.compute_margin(
            MarginType.MAINTENANCE, notional_value, rates
        )
        portfolio_margin = self.compute_margin(
            MarginType.PORTFOLIO, notional_value, rates
        )

        margin_available = req.account_equity - req.existing_margin_used
        buying_power = margin_available / rates.initial_rate if rates.initial_rate > 0 else 0.0

        margin_utilization_pct = (
            (req.existing_margin_used + initial_margin) / req.account_equity * 100
            if req.account_equity > 0
            else 100.0
        )

        can_execute = initial_margin <= margin_available
        reason = None if can_execute else (
            f"Insufficient margin: required {initial_margin:.2f}, "
            f"available {margin_available:.2f}"
        )

        return MarginRequirementResult(
            symbol=req.symbol,
            side=req.side.value,
            quantity=req.quantity,
            price=req.price,
            notional_value=round(notional_value, 2),
            exchange=req.exchange,
            initial_margin=round(initial_margin, 2),
            maintenance_margin=round(maintenance_margin, 2),
            portfolio_margin=round(portfolio_margin, 2),
            buying_power=round(buying_power, 2),
            margin_available=round(margin_available, 2),
            margin_utilization_pct=round(margin_utilization_pct, 4),
            can_execute=can_execute,
            reason=reason,
        )
