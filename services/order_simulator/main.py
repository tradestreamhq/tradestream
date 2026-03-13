"""
Order Execution Simulator entry point.
"""

import os

import uvicorn

from services.order_simulator.app import create_app
from services.order_simulator.models import FeeSchedule, SlippageConfig, SlippageModel


def main():
    slippage_config = SlippageConfig(
        model=SlippageModel(os.environ.get("SLIPPAGE_MODEL", "PERCENTAGE")),
        value=float(os.environ.get("SLIPPAGE_VALUE", "0.001")),
    )
    fee_schedule = FeeSchedule(
        maker_fee=float(os.environ.get("MAKER_FEE", "0.001")),
        taker_fee=float(os.environ.get("TAKER_FEE", "0.002")),
    )
    initial_balance = float(os.environ.get("INITIAL_BALANCE", "100000.0"))

    app = create_app(
        initial_balance=initial_balance,
        slippage_config=slippage_config,
        fee_schedule=fee_schedule,
    )
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
