"""Tests for ServiceRunner."""

import signal
import threading
import time
import urllib.request
import urllib.error

import pytest

from services.shared.service_runner import ServiceRunner


class TestServiceRunner:
    """Tests for the ServiceRunner class."""

    def test_task_fn_is_called(self):
        call_count = 0

        def task():
            nonlocal call_count
            call_count += 1

        runner = ServiceRunner(
            service_name="test",
            interval_seconds=0,
            task_fn=task,
            health_port=0,
        )
        # Simulate shutdown after brief run
        t = threading.Thread(target=runner.run)
        t.start()
        time.sleep(0.3)
        runner._shutdown = True
        t.join(timeout=5)
        assert call_count >= 1

    def test_graceful_shutdown_on_signal(self):
        calls = []

        def task():
            calls.append(1)

        runner = ServiceRunner(
            service_name="test_shutdown",
            interval_seconds=60,
            task_fn=task,
            health_port=0,
        )

        t = threading.Thread(target=runner.run)
        t.start()
        time.sleep(0.3)
        # Trigger shutdown
        runner._handle_shutdown(signal.SIGTERM, None)
        t.join(timeout=5)

        assert runner.shutdown_requested is True
        assert len(calls) >= 1

    def test_health_check_endpoints(self):
        runner = ServiceRunner(
            service_name="test_health",
            interval_seconds=60,
            task_fn=lambda: None,
            health_port=18923,
        )
        t = threading.Thread(target=runner.run)
        t.start()
        time.sleep(0.5)

        try:
            # Liveness check should return 200
            resp = urllib.request.urlopen("http://localhost:18923/healthz")
            assert resp.status == 200

            # Readiness should return 200 after first task
            resp = urllib.request.urlopen("http://localhost:18923/readyz")
            assert resp.status == 200
        finally:
            runner._handle_shutdown(signal.SIGTERM, None)
            t.join(timeout=5)

    def test_readiness_not_ready_before_task(self):
        """Readiness returns 503 before task_fn completes when using custom ready_fn."""
        runner = ServiceRunner(
            service_name="test_ready",
            interval_seconds=60,
            task_fn=lambda: time.sleep(2),
            health_port=18924,
            ready_fn=lambda: False,
        )
        t = threading.Thread(target=runner.run)
        t.start()
        time.sleep(0.3)

        try:
            resp = urllib.request.urlopen("http://localhost:18924/readyz")
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 503
        finally:
            runner._handle_shutdown(signal.SIGTERM, None)
            t.join(timeout=5)

    def test_task_exception_does_not_crash_service(self):
        call_count = 0

        def failing_task():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("boom")

        runner = ServiceRunner(
            service_name="test_error",
            interval_seconds=0,
            task_fn=failing_task,
            health_port=0,
        )
        t = threading.Thread(target=runner.run)
        t.start()
        time.sleep(0.5)
        runner._handle_shutdown(signal.SIGTERM, None)
        t.join(timeout=5)

        # Should have been called more than once despite error
        assert call_count >= 2

    def test_iteration_count(self):
        runner = ServiceRunner(
            service_name="test_iter",
            interval_seconds=0,
            task_fn=lambda: None,
            health_port=0,
        )
        t = threading.Thread(target=runner.run)
        t.start()
        time.sleep(0.3)
        runner._handle_shutdown(signal.SIGTERM, None)
        t.join(timeout=5)

        assert runner._iteration_count >= 1
