"""Strategy Optimizer service entry point."""

import logging
import os

import uvicorn

from services.strategy_optimizer.app import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8086"))
    uvicorn.run(app, host="0.0.0.0", port=port)
