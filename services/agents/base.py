"""Base Agent class for all TradeStream agents.

Provides the common skeleton for LLM-driven agents that interact with MCP
servers via tool calls.  Subclasses must implement ``run()``.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from services.agents.mcp_client import MCPClient
from services.agents.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for TradeStream agents.

    Subclasses must implement ``run()`` to define the agent's behaviour.

    Attributes:
        name: Human-readable agent name.
        openrouter: Configured OpenRouter client.
        mcp: Configured MCP client.
    """

    def __init__(
        self,
        name: str,
        *,
        openrouter: OpenRouterClient | None = None,
        mcp: MCPClient | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        self.name = name
        self.openrouter = openrouter or OpenRouterClient(
            api_key=api_key, default_model=default_model
        )
        self.mcp = mcp or MCPClient()

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the agent's main logic.

        Subclasses define the specific workflow here, including LLM
        interactions and MCP tool calls.

        Returns:
            Agent-specific result (typically a dict).
        """

    def call_mcp_tool(
        self,
        server: str,
        tool: str,
        params: dict | None = None,
        *,
        timeout: int = 30,
    ) -> dict | str:
        """Call an MCP tool on a specific server.

        Args:
            server: Server key — one of "strategy", "market", or "signal".
            tool: MCP tool name.
            params: Arguments to pass to the tool.
            timeout: HTTP request timeout in seconds.

        Returns:
            Parsed response dict or error dict.
        """
        return self.mcp.call_tool(
            server=server,
            tool_name=tool,
            arguments=params or {},
            timeout=timeout,
        )
