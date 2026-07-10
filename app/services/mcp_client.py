"""Load tools from the hosted PostgreSQL MCP server (Streamable HTTP)."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


def is_mcp_enabled() -> bool:
    return os.getenv("ENABLE_MCP", "false").lower() in ("true", "1", "yes")


def _connection_config() -> dict:
    url = os.getenv("MCP_HTTP_URL", "http://127.0.0.1:3000/mcp")
    headers: dict[str, str] = {}
    api_key = os.getenv("MCP_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return {
        "postgresql": {
            "transport": "streamable_http",
            "url": url,
            "headers": headers or None,
        }
    }


async def _fetch_tools_async() -> list[BaseTool]:
    client = MultiServerMCPClient(_connection_config())
    return await client.get_tools()


def _fetch_tools_sync() -> list[BaseTool]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_fetch_tools_async())

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, _fetch_tools_async()).result()


@lru_cache(maxsize=1)
def load_mcp_tools() -> tuple[BaseTool, ...]:
    """Return MCP tools as a hashable tuple for agent caching."""
    if not is_mcp_enabled():
        return ()
    tools = _fetch_tools_sync()
    if not tools:
        raise RuntimeError("ENABLE_MCP=true but PostgreSQL MCP returned no tools")
    return tuple(tools)
