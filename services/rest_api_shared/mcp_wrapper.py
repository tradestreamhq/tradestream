"""
Base MCP wrapper that calls REST API endpoints.

MCP servers are thin wrappers that translate tool calls into REST API requests.
This base class provides the HTTP client and common patterns.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from mcp.server import Server
from mcp.types import TextContent

logger = logging.getLogger(__name__)


class MCPAPIWrapper:
    """Base class for MCP servers wrapping REST APIs.

    Provides an HTTP client configured with the API base URL and common
    methods for GET/POST/PUT/DELETE with standardized error handling.
    """

    def __init__(self, api_base_url: str, timeout: float = 30.0):
        self.api_base_url = api_base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.api_base_url, timeout=timeout)

    def close(self):
        self.client.close()

    def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a GET request and return parsed JSON."""
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def _post(
        self, path: str, json_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a POST request and return parsed JSON."""
        response = self.client.post(path, json=json_body)
        response.raise_for_status()
        return response.json()

    def _put(
        self, path: str, json_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform a PUT request and return parsed JSON."""
        response = self.client.put(path, json=json_body)
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> Optional[Dict[str, Any]]:
        """Perform a DELETE request. Returns None for 204 responses."""
        response = self.client.delete(path)
        response.raise_for_status()
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
