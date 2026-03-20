"""Response metadata helpers for MCP servers.

Wraps tool results with latency, cache status, and source info per the MCP servers spec.
"""

import json
import time
from typing import Any, Optional

from mcp.types import TextContent


def wrap_response(
    data: Any,
    *,
    start_time: float,
    cached: bool = False,
    cache_ttl_remaining: Optional[float] = None,
    source: str = "postgresql",
) -> list[TextContent]:
    """Wrap a tool result with _metadata and return as TextContent list.

    Args:
        data: The tool result dict/list.
        start_time: time.monotonic() captured before the operation.
        cached: Whether the result came from cache.
        cache_ttl_remaining: Seconds remaining on the cache entry.
        source: Data source name (e.g. "postgresql", "influxdb", "redis").

    Returns:
        List with a single TextContent containing the JSON response.
    """
    latency_ms = int((time.monotonic() - start_time) * 1000)
    metadata: dict[str, Any] = {
        "latency_ms": latency_ms,
        "cached": cached,
        "cache_ttl_remaining": (
            round(cache_ttl_remaining, 1) if cache_ttl_remaining is not None else None
        ),
        "source": source,
    }
    response: dict[str, Any] = {
        "data": data,
        "_metadata": metadata,
    }
    return [TextContent(type="text", text=json.dumps(response, default=str))]


def wrap_error(
    error: dict[str, Any],
    *,
    start_time: float,
) -> list[TextContent]:
    """Wrap an error response with _metadata.

    Args:
        error: Error dict with code/message/details.
        start_time: time.monotonic() captured before the operation.

    Returns:
        List with a single TextContent containing the JSON error response.
    """
    latency_ms = int((time.monotonic() - start_time) * 1000)
    response: dict[str, Any] = {
        "error": error,
        "_metadata": {"latency_ms": latency_ms},
    }
    return [TextContent(type="text", text=json.dumps(response, default=str))]
