#!/usr/bin/env python3
"""
VectorBT Backtesting Microservice Entry Point.

Provides both gRPC and HTTP/REST interfaces for backtesting.
"""

import argparse
import json
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from services.backtesting.backtesting_service import BacktestingServiceImpl

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BacktestHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for REST interface (for testing without gRPC)."""

    service: BacktestingServiceImpl = None

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/backtest":
            self._handle_backtest()
        elif self.path == "/batch":
            self._handle_batch()
        elif self.path == "/health":
            self._handle_health()
        else:
            self._send_error(404, "Not found")

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/indicators":
            self._handle_list_indicators()
        else:
            self._send_error(404, "Not found")

    def _handle_backtest(self):
        """Handle single backtest request."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request = json.loads(body.decode("utf-8"))

            result = self.service.run_backtest(request)

            self._send_json(200, result)
        except ValueError as e:
            self._send_error(400, str(e))
        except Exception as e:
            logger.exception("Backtest failed")
            self._send_error(500, str(e))

    def _handle_batch(self):
        """Handle batch backtest request."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request = json.loads(body.decode("utf-8"))

            candles = request.get("candles", [])
            strategy_name = request.get("strategyName", "")
            parameter_sets = request.get("parameterSets", [])

            results = self.service.run_batch_backtest(
                candles, strategy_name, parameter_sets
            )

            self._send_json(200, {"results": results})
        except ValueError as e:
            self._send_error(400, str(e))
        except Exception as e:
            logger.exception("Batch backtest failed")
            self._send_error(500, str(e))

    def _handle_health(self):
        """Handle health check."""
        self._send_json(200, {"status": "healthy", "service": "vectorbt-backtesting"})

    def _handle_list_indicators(self):
        """List available indicators."""
        from indicator_registry import get_default_registry

        indicators = get_default_registry().list_indicators()
        self._send_json(200, {"indicators": indicators})

    def _send_json(self, status: int, data: Dict[str, Any]):
        """Send JSON response."""
        response = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)

    def _send_error(self, status: int, message: str):
        """Send error response."""
        self._send_json(status, {"error": message})

    def log_message(self, format: str, *args):
        """Override to use Python logging."""
        logger.info("%s - %s", self.address_string(), format % args)


def run_http_server(port: int, service: BacktestingServiceImpl):
    """Run the HTTP server."""
    BacktestHTTPHandler.service = service
    server = HTTPServer(("0.0.0.0", port), BacktestHTTPHandler)
    logger.info("HTTP server listening on port %d", port)
    logger.info("  POST /backtest - Run single backtest")
    logger.info("  POST /batch - Run batch backtests")
    logger.info("  GET /health - Health check")
    logger.info("  GET /indicators - List available indicators")
    server.serve_forever()


def run_grpc_server(port: int):
    """Run the gRPC server."""
    try:
        import grpc
        from concurrent import futures

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        # Add service when protobuf stubs are generated
        server.add_insecure_port(f"[::]:{port}")
        server.start()
        logger.info(f"gRPC server listening on port {port}")
        server.wait_for_termination()
    except ImportError:
        logger.error("gRPC not available. Install grpcio.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="VectorBT Backtesting Microservice")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--grpc-port", type=int, default=50051, help="gRPC port")
    parser.add_argument(
        "--mode", choices=["http", "grpc", "both"], default="http", help="Server mode"
    )
    args = parser.parse_args()

    logger.info("Initializing VectorBT Backtesting Service...")
    service = BacktestingServiceImpl()
    logger.info("Service initialized successfully")

    if args.mode == "http":
        run_http_server(args.port, service)
    elif args.mode == "grpc":
        run_grpc_server(args.grpc_port)
    else:
        # Run both in separate threads
        import threading

        http_thread = threading.Thread(
            target=run_http_server, args=(args.port, service)
        )
        http_thread.daemon = True
        http_thread.start()
        run_grpc_server(args.grpc_port)


if __name__ == "__main__":
    main()
