"""
Base MCP wrapper that calls REST API endpoints.

MCP servers are thin wrappers that translate tool calls into REST API requests.
This base class provides the HTTP client and common patterns, with built-in
retry logic and circuit breaker protection for resilience.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type

import httpx
from mcp.server import Server
from mcp.types import TextContent

logger = logging.getLogger(__name__)

# Transient HTTP errors that warrant retry
TRANSIENT_HTTP_STATUS_CODES = {502, 503, 504, 429}
TRANSIENT_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.PoolTimeout,
    httpx.ConnectTimeout,
    ConnectionError,
    TimeoutError,
)


class MCPAPIWrapper:
    """Base class for MCP servers wrapping REST APIs.

    Provides an HTTP client configured with the API base URL and common
    methods for GET/POST/PUT/DELETE with retry and circuit breaker protection.
    """

    def __init__(
        self,
        api_base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 30.0,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.api_base_url, timeout=timeout)
        self._max_retries = max_retries

        # Circuit breaker state
        self._failure_count = 0
        self._failure_threshold = circuit_failure_threshold
        self._recovery_timeout = circuit_recovery_timeout
        self._circuit_open_until: float = 0.0

    def close(self):
        self.client.close()

    @property
    def _is_circuit_open(self) -> bool:
        if self._circuit_open_until == 0.0:
            return False
        if time.monotonic() >= self._circuit_open_until:
            self._circuit_open_until = 0.0
            self._failure_count = 0
            return False
        return True

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._circuit_open_until = time.monotonic() + self._recovery_timeout
            logger.warning(
                "MCP wrapper circuit breaker OPEN after %d failures. "
                "Recovery in %ds.",
                self._failure_count,
                self._recovery_timeout,
            )

    def _is_retryable(self, exc: BaseException) -> bool:
        if isinstance(exc, TRANSIENT_EXCEPTIONS):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in TRANSIENT_HTTP_STATUS_CODES
        return False

    def _request_with_resilience(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Execute an HTTP request with retry and circuit breaker protection."""
        if self._is_circuit_open:
            raise httpx.HTTPError(
                f"Circuit breaker open for {self.api_base_url}. "
                f"Retry after {self._circuit_open_until - time.monotonic():.0f}s."
            )

        last_exc: Optional[BaseException] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self.client.request(method, path, **kwargs)
                response.raise_for_status()
                self._record_success()
                return response
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable(exc):
                    self._record_failure()
                    raise

                if attempt == self._max_retries:
                    self._record_failure()
                    raise

                delay = min(0.5 * (2 ** (attempt - 1)), 10.0)
                logger.warning(
                    "MCP request %s %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    method,
                    path,
                    attempt,
                    self._max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)

        self._record_failure()
        raise last_exc  # type: ignore[misc]

    def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a GET request and return parsed JSON."""
        response = self._request_with_resilience("GET", path, params=params)
        return response.json()

    def _post(
        self, path: str, json_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a POST request and return parsed JSON."""
        response = self._request_with_resilience("POST", path, json=json_body)
        return response.json()

    def _put(
        self, path: str, json_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a PUT request and return parsed JSON."""
        response = self._request_with_resilience("PUT", path, json=json_body)
        return response.json()

    def _delete(self, path: str) -> Optional[Dict[str, Any]]:
        """Perform a DELETE request. Returns None for 204 responses."""
        response = self._request_with_resilience("DELETE", path)
        if response.status_code == 204:
            return None
        return response.json()

    @staticmethod
    def _text(data: Any) -> List[TextContent]:
        """Wrap data as MCP TextContent."""
        return [TextContent(type="text", text=json.dumps(data, default=str))]

    @staticmethod
    def _error_text(message: str) -> List[TextContent]:
        """Wrap error message as MCP TextContent."""
        return [TextContent(type="text", text=json.dumps({"error": message}))]
