"""MCP client for routing tool calls to K8s-hosted MCP servers.

Reads base URLs from environment variables:
  - STRATEGY_MCP_URL  (default http://strategy-mcp:8080)
  - MARKET_MCP_URL    (default http://market-mcp:8080)
  - SIGNAL_MCP_URL    (default http://signal-mcp:8080)
"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_URLS: dict[str, str] = {
    "strategy": "http://strategy-mcp:8080",
    "market": "http://market-mcp:8080",
    "signal": "http://signal-mcp:8080",
}

_ENV_VARS: dict[str, str] = {
    "strategy": "STRATEGY_MCP_URL",
    "market": "MARKET_MCP_URL",
    "signal": "SIGNAL_MCP_URL",
}


class MCPClient:
    """Routes MCP tool calls to the correct K8s service."""

    def __init__(self, urls: dict[str, str] | None = None):
        """Initialise with explicit URLs or read from the environment.

        Args:
            urls: Optional mapping of server key -> base URL.  Keys that
                are not provided fall back to the corresponding env var
                or the built-in default.
        """
        self._urls: dict[str, str] = {}
        for key in _DEFAULT_URLS:
            if urls and key in urls:
                self._urls[key] = urls[key]
            else:
                self._urls[key] = os.environ.get(
                    _ENV_VARS[key], _DEFAULT_URLS[key]
                )

    def get_url(self, server: str) -> str:
        """Return the base URL for *server*.

        Raises:
            ValueError: If *server* is not a known MCP server key.
        """
        if server not in self._urls:
            raise ValueError(
                f"Unknown MCP server: {server!r}. "
                f"Valid keys: {sorted(self._urls)}"
            )
        return self._urls[server]

    def call_tool(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: int = 30,
    ) -> dict | str:
        """Call an MCP tool on the specified server.

        Args:
            server: One of "strategy", "market", or "signal".
            tool_name: Name of the MCP tool.
            arguments: Tool arguments.
            timeout: HTTP request timeout in seconds.

        Returns:
            Parsed response dict, or an error dict on failure.
        """
        base_url = self.get_url(server)
        url = f"{base_url.rstrip('/')}/call-tool"
        payload = {"name": tool_name, "arguments": arguments or {}}

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as exc:
            logger.error("MCP call %s on %s failed: %s", tool_name, server, exc)
            return {"error": str(exc)}

        # Extract text content from MCP response envelope
        if "content" in result and isinstance(result["content"], list):
            texts = [
                c.get("text", "")
                for c in result["content"]
                if c.get("type") == "text"
            ]
            if texts:
                combined = "\n".join(texts)
                try:
                    return json.loads(combined)
                except (json.JSONDecodeError, TypeError):
                    return {"raw": combined}

        return result
