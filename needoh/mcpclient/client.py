"""
needoh/mcp/client.py
MCP client — connects to all configured MCP servers, loads their tools
dynamically, and dispatches tool calls.

Architecture:
  NeedohMCPClient
    ├── connects to N servers (each as a subprocess via stdio transport)
    ├── loads tool schemas from each server
    └── call_tool(tool_name, args) → routes to the right server
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from needoh.mcpclient.config import SERVERS
from needoh.ui.display import console, print_info, print_error, DIM


class NeedohMCPClient:
    """
    Manages connections to all MCP servers.

    Usage:
        async with NeedohMCPClient() as client:
            tools = client.get_all_tools()
            result = await client.call_tool("read_file", {"path": "/tmp/foo.py"})
    """

    def __init__(self):
        # server_name → ClientSession
        self._sessions: dict[str, ClientSession] = {}
        # tool_name → server_name (for routing)
        self._tool_registry: dict[str, str] = {}
        # All tool schemas as LangChain-compatible dicts
        self._tools: list[dict] = []
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "NeedohMCPClient":
        await self._connect_all()
        return self

    async def __aexit__(self, *args):
        await self._exit_stack.aclose()

    # ── Connection ────────────────────────────────────────────────────────────

    async def _connect_all(self) -> None:
        """Start all MCP servers and load their tools."""
        for cfg in SERVERS:
            try:
                await self._connect_server(cfg)
            except Exception as exc:
                print_error(f"Could not connect to MCP server '{cfg['name']}': {exc}")

    async def _connect_server(self, cfg: dict) -> None:
        """Connect to a single MCP server and register its tools."""
        name = cfg["name"]
        console.print(f"  [{DIM}]connecting to MCP server: {name}…[/]")

        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env") or None,
        )

        # Start the subprocess and open a session
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        session: ClientSession = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        self._sessions[name] = session

        # Load tools from this server
        tools_response = await session.list_tools()
        for tool in tools_response.tools:
            self._tool_registry[tool.name] = name
            self._tools.append(self._to_langchain_tool(tool))

        print_info(
            f"  {name}: loaded {len(tools_response.tools)} tool(s) "
            f"({', '.join(t.name for t in tools_response.tools)})"
        )

    # ── Tool registry ─────────────────────────────────────────────────────────

    def get_all_tools(self) -> list[dict]:
        """Return all tool schemas in LangChain bind_tools format."""
        return self._tools

    def get_tool_names(self) -> list[str]:
        """Return a flat list of all available tool names."""
        return list(self._tool_registry.keys())

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """
        Execute a tool on the appropriate MCP server.

        Args:
            tool_name: Name of the tool to call.
            args:      Arguments dict as requested by the LLM.

        Returns:
            String result from the tool.

        Raises:
            KeyError: If the tool is not registered.
        """
        if tool_name not in self._tool_registry:
            raise KeyError(
                f"Tool '{tool_name}' not found. "
                f"Available: {', '.join(self._tool_registry)}"
            )

        server_name = self._tool_registry[tool_name]
        session = self._sessions[server_name]

        response = await session.call_tool(tool_name, args)

        # MCP returns a list of content blocks; join text blocks into one string
        parts: list[str] = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_langchain_tool(mcp_tool) -> dict:
        """
        Convert an MCP Tool object to the dict format expected by
        LangChain's bind_tools().
        """
        return {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": (
                mcp_tool.inputSchema
                if isinstance(mcp_tool.inputSchema, dict)
                else {"type": "object", "properties": {}}
            ),
        }
