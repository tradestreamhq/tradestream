"""ServiceRunner - Base class for long-lived services with health checks and graceful shutdown.

Converts batch scripts into proper services by providing:
- HTTP health check endpoint (liveness/readiness probes)
- Graceful shutdown on SIGINT/SIGTERM
- Periodic task scheduling with configurable intervals
- Structured logging integration
"""

import signal
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Optional

from absl import logging

from services.shared.structured_logger import StructuredLogger


class _HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""

    service_runner: Optional["ServiceRunner"] = None

    def do_GET(self):
        if self.path == "/healthz" or self.path == "/livez":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif self.path == "/readyz":
            if self.service_runner and self.service_runner.is_ready:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ready"}')
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"not_ready"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default access logs to avoid noise."""
        pass


class ServiceRunner:
    """Base runner that converts periodic batch work into a proper long-lived service.

    Usage:
        runner = ServiceRunner(
            service_name="my_service",
            interval_seconds=60,
            task_fn=my_task_function,
            health_port=8080,
        )
        runner.run()  # Blocks until shutdown signal
    """

    def __init__(
        self,
        service_name: str,
        interval_seconds: int,
        task_fn: Callable[[], None],
        health_port: int = 8080,
        ready_fn: Optional[Callable[[], bool]] = None,
    ):
        """Initialize the service runner.

        Args:
            service_name: Name used in logs and health checks.
            interval_seconds: Seconds between task executions.
            task_fn: The function to call periodically.
            health_port: Port for the HTTP health check server.
            ready_fn: Optional function that returns True when the service is ready.
                      If not provided, readiness is set after the first successful task run.
        """
        self._service_name = service_name
        self._interval_seconds = interval_seconds
        self._task_fn = task_fn
        self._health_port = health_port
        self._ready_fn = ready_fn
        self._shutdown = False
        self._log = StructuredLogger(service_name=service_name)
        self._is_ready = False
        self._health_server: Optional[HTTPServer] = None
        self._health_thread: Optional[threading.Thread] = None
        self._iteration_count = 0

    @property
    def is_ready(self) -> bool:
        if self._ready_fn:
            return self._ready_fn()
        return self._is_ready

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown

    def _handle_shutdown(self, signum, frame):
        self._log.info("Received shutdown signal", signum=signum)
        self._shutdown = True
        if self._health_server:
            threading.Thread(target=self._health_server.shutdown, daemon=True).start()

    def _start_health_server(self):
        """Start the HTTP health check server in a background thread."""
        handler = type(
            "_BoundHealthHandler",
            (_HealthHandler,),
            {"service_runner": self},
        )
        try:
            self._health_server = HTTPServer(("0.0.0.0", self._health_port), handler)
            self._health_thread = threading.Thread(
                target=self._health_server.serve_forever,
                daemon=True,
            )
            self._health_thread.start()
            self._log.info(
                "Health check server started",
                port=self._health_port,
                endpoints=["/healthz", "/readyz"],
            )
        except OSError as e:
            self._log.warning(
                "Could not start health server, continuing without it",
                error=str(e),
                port=self._health_port,
            )

    def _sleep_interruptible(self, seconds: int):
        """Sleep for the given duration, waking early on shutdown."""
        for _ in range(seconds):
            if self._shutdown:
                return
            time.sleep(1)

    def run(self):
        """Run the service loop. Blocks until shutdown signal."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self._start_health_server()

        self._log.info(
            "Service started",
            interval_seconds=self._interval_seconds,
            health_port=self._health_port,
        )

        try:
            while not self._shutdown:
                self._log.new_correlation_id()
                self._iteration_count += 1
                try:
                    self._log.info(
                        "Starting task iteration",
                        iteration=self._iteration_count,
                    )
                    self._task_fn()
                    self._is_ready = True
                    self._log.info(
                        "Task iteration completed",
                        iteration=self._iteration_count,
                    )
                except Exception as e:
                    self._log.exception(
                        "Task iteration failed",
                        iteration=self._iteration_count,
                        error=str(e),
                    )

                if not self._shutdown:
                    self._log.info(
                        "Sleeping before next iteration",
                        interval_seconds=self._interval_seconds,
                    )
                    self._sleep_interruptible(self._interval_seconds)
        finally:
            self._log.info(
                "Service shutting down",
                total_iterations=self._iteration_count,
            )
            if self._health_server:
                self._health_server.shutdown()
