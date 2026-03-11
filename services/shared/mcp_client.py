"""Shared MCP client for calling MCP server tools via HTTP.

Consolidates the duplicated _call_mcp_tool implementations from:
- orchestrator_agent/orchestrator.py
- signal_generator_agent/agent.py
- strategy_proposer_agent/agent.py
- opportunity_scorer_agent/agent.py
- paper_trading/service.py
"""

import json
import logging

import requests

logger = logging.getLogger(__name__)


def call_mcp_tool(
    tool_name: str,
    arguments: dict,
    mcp_url: str,
    *,
    timeout: int = 30,
    return_type: str = "parsed",
) -> "str | dict":
    """Call an MCP server tool via its HTTP /call-tool endpoint.

    Args:
        tool_name: Name of the MCP tool to call.
        arguments: Arguments to pass to the tool.
        mcp_url: Base URL of the MCP server (e.g. http://localhost:8081).
        timeout: HTTP request timeout in seconds.
        return_type: "parsed" returns a dict (parsed JSON or raw text fallback),
                     "string" returns a JSON string (for LLM tool responses).

    Returns:
        Parsed dict or JSON string depending on return_type.
    """
    url = f"{mcp_url.rstrip('/')}/call-tool"
    payload = {"name": tool_name, "arguments": arguments or {}}

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as e:
        logger.error("MCP call %s failed: %s", tool_name, e)
        error = {"error": str(e)}
        return json.dumps(error) if return_type == "string" else error

    # Extract text content from MCP response format
    if "content" in result and isinstance(result["content"], list):
        texts = [
            c.get("text", "")
            for c in result["content"]
            if c.get("type") == "text"
        ]
        if texts:
            combined = "\n".join(texts)
            if return_type == "string":
                return combined
            # Try to parse the combined text as JSON
            try:
                return json.loads(combined)
            except (json.JSONDecodeError, TypeError):
                return {"raw": combined}

        # No text items found in content
        if return_type == "string":
            return json.dumps(result)
        return result

    if return_type == "string":
        return json.dumps(result)
    return result


def resolve_and_call(
    tool_name: str,
    arguments: dict,
    tool_to_server: dict,
    mcp_urls: dict,
    *,
    timeout: int = 30,
    return_type: str = "parsed",
) -> "str | dict":
    """Resolve the MCP server for a tool name, then call it.

    This is the multi-server variant used by agents that dispatch tools
    to different MCP servers based on a tool-to-server mapping.

    Args:
        tool_name: Name of the MCP tool to call.
        arguments: Arguments to pass to the tool.
        tool_to_server: Mapping of tool names to server keys.
        mcp_urls: Mapping of server keys to base URLs.
        timeout: HTTP request timeout in seconds.
        return_type: "parsed" or "string".

    Returns:
        Parsed dict or JSON string depending on return_type.
    """
    server_key = tool_to_server.get(tool_name)
    if not server_key:
        error = {"error": f"Unknown tool: {tool_name}"}
        return json.dumps(error) if return_type == "string" else error

    base_url = mcp_urls.get(server_key)
    if not base_url:
        error = {"error": f"No URL configured for MCP server: {server_key}"}
        return json.dumps(error) if return_type == "string" else error

    return call_mcp_tool(
        tool_name, arguments, base_url, timeout=timeout, return_type=return_type
    )
