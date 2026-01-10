#!/usr/bin/env python3
"""
VectorBT Backtesting Microservice Entry Point.

Provides a gRPC interface for high-performance backtesting.
"""

import argparse
import logging
import signal
import sys

from services.backtesting.backtesting_service import create_grpc_server

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="VectorBT Backtesting Microservice")
    parser.add_argument("--port", type=int, default=50051, help="gRPC server port")
    args = parser.parse_args()

    logger.info("Initializing VectorBT Backtesting Service...")

    server = create_grpc_server(args.port)
    server.start()
    logger.info(f"gRPC server listening on port {args.port}")
    logger.info("Service ready to accept backtest requests")

    # Handle shutdown gracefully
    def shutdown(signum, frame):
        logger.info("Shutting down server...")
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Block until terminated
    server.wait_for_termination()


if __name__ == "__main__":
    main()
