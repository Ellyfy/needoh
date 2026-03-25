"""
needoh/agent/loop.py
The core agentic loop.

Cycle:
  1. User task → build messages
  2. Call LLM (streaming)
  3. If response contains tool calls → execute them → append results → goto 2
  4. If no tool calls → print final answer → done

The loop runs until the model stops requesting tools or MAX_ITERATIONS
is reached (safety valve).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from needoh.agent.providers import BaseProvider
from needoh.agent.tools import ShellTool, get_local_tool_schemas
from needoh.mcpclient.client import NeedohMCPClient
from needoh.ui.display import (
    SpinnerContext,
    end_stream,
    print_confirm_prompt,
    print_error,
    print_tool_call,
    print_tool_result,
    stream_llm_response,
    console,
    ACCENT,
    DIM,
)

# Safety valve — prevents infinite loops on runaway models
MAX_ITERATIONS = 30

SYSTEM_PROMPT = """You are Needoh, an expert autonomous coding assistant.
You operate directly on the developer's filesystem and codebase.

Your job:
- Understand the developer's task completely before acting
- Use tools to read existing code before writing or editing anything
- Make targeted, minimal changes unless a full rewrite is requested
- Run commands to verify your changes work
- Report clearly when the task is done

Guidelines:
- Always read a file before editing it
- Prefer small, focused tool calls over large ones
- If you're unsure about scope, ask ONE clarifying question
- Use the RAG server (query_langchain_docs) when you need LangChain API details
- Use web search (tavily_search) for anything requiring current information

When you are done with a task, summarise what you did concisely."""


class AgentLoop:
    """
    Drives the agentic loop for a single session.

    Args:
        provider:   LLM provider (Groq or Ollama)
        mcp_client: Connected MCP client with all tools loaded
        auto:       If True, execute tools without user confirmation
    """

    def __init__(
        self,
        provider: BaseProvider,
        mcp_client: NeedohMCPClient,
        auto: bool = False,
    ):
        self.provider = provider
        self.mcp = mcp_client
        self.auto = auto
        self._shell = ShellTool()
        # Persistent conversation history across turns
        self.history: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        # Merge MCP tools + local tools (shell) into one list for the LLM
        self._tools = mcp_client.get_all_tools() + get_local_tool_schemas()

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self, user_input: str) -> None:
        """
        Process one user task through the full agentic loop.
        Streams LLM output to the terminal and executes tool calls.
        """
        self.history.append(HumanMessage(content=user_input))

        for iteration in range(MAX_ITERATIONS):
            # ── Call LLM ──────────────────────────────────────────────────────
            response = await self._call_llm()

            # ── No tool calls → final answer, we're done ──────────────────────
            if not response.tool_calls:
                break

            # ── Execute each requested tool call ──────────────────────────────
            tool_results = await self._execute_tool_calls(response.tool_calls)

            # Append the assistant message and all tool results to history
            self.history.append(response)
            for tr in tool_results:
                self.history.append(tr)

            console.print(f"\n[{DIM}]— iteration {iteration + 1} —[/]\n")

        else:
            print_error(f"Reached max iterations ({MAX_ITERATIONS}). Stopping.")

    def clear_history(self) -> None:
        """Reset conversation history (keeps the system prompt)."""
        self.history = [SystemMessage(content=SYSTEM_PROMPT)]

    # ── LLM call (streaming) ──────────────────────────────────────────────────

    async def _call_llm(self) -> AIMessage:
        """
        Stream a response from the LLM.
        Prints tokens as they arrive; collects the full message for tool parsing.
        Returns the complete AIMessage.
        """
        full_content = ""
        tool_calls_raw: list[dict] = []

        console.print(f"\n[bold {ACCENT}]needoh ›[/] ", end="")

        # Run streaming in a thread so asyncio event loop stays free
        loop = asyncio.get_event_loop()
        chunks = await loop.run_in_executor(
            None,
            lambda: list(self.provider.stream(self.history, tools=self._tools)),
        )

        for chunk in chunks:
            # Stream text content
            if chunk.content:
                stream_llm_response(chunk.content)
                full_content += chunk.content

            # Accumulate tool call deltas
            if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                for tc_chunk in chunk.tool_call_chunks:
                    self._merge_tool_call_chunk(tool_calls_raw, tc_chunk)

        end_stream()

        # Build a proper AIMessage with parsed tool calls
        tool_calls = self._finalise_tool_calls(tool_calls_raw)
        return AIMessage(content=full_content, tool_calls=tool_calls)

    # ── Tool execution ────────────────────────────────────────────────────────

    async def _execute_tool_calls(
        self, tool_calls: list[dict]
    ) -> list[ToolMessage]:
        """
        Execute a list of tool calls (sequentially).
        Handles confirmation in non-auto mode.
        Returns a list of ToolMessage results.
        """
        results: list[ToolMessage] = []

        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            call_id = tc.get("id", "")

            # ── Confirm mode ─────────────────────────────────────────────────
            if not self.auto:
                approved = print_confirm_prompt(name, args)
                if not approved:
                    results.append(ToolMessage(
                        content="Tool execution skipped by user.",
                        tool_call_id=call_id,
                    ))
                    continue
            else:
                print_tool_call(name, args)

            # ── Execute — route to local tool or MCP ─────────────────────────
            with SpinnerContext(f"Running {name}…"):
                try:
                    if name == "run_shell_command":
                        result = await self._shell.run(
                            args.get("command", ""),
                            timeout=args.get("timeout", 60),
                        )
                    elif name == "change_directory":
                        result = self._shell.change_dir(args.get("path", "."))
                    else:
                        result = await self.mcp.call_tool(name, args)
                except Exception as exc:
                    result = f"ERROR: {exc}"

            print_tool_result(result, tool_name=name)
            results.append(ToolMessage(content=result, tool_call_id=call_id))

        return results

    # ── Tool call helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _merge_tool_call_chunk(
        accumulated: list[dict], chunk: Any
    ) -> None:
        """
        Merge a streaming tool_call_chunk into the accumulated list.
        LangChain streams tool calls in pieces; we reassemble them here.
        """
        idx = getattr(chunk, "index", 0) or 0

        # Grow the list if this is a new index
        while len(accumulated) <= idx:
            accumulated.append({"id": "", "name": "", "args": "", "index": idx})

        entry = accumulated[idx]
        if getattr(chunk, "id", None):
            entry["id"] = chunk.id
        if getattr(chunk, "name", None):
            entry["name"] += chunk.name
        if getattr(chunk, "args", None):
            entry["args"] += chunk.args

    @staticmethod
    def _finalise_tool_calls(raw: list[dict]) -> list[dict]:
        """
        Parse accumulated tool call dicts.
        Converts the JSON-string args field into a proper dict.
        """
        finalised = []
        for tc in raw:
            try:
                args = json.loads(tc["args"]) if tc["args"] else {}
            except json.JSONDecodeError:
                args = {"raw": tc["args"]}
            finalised.append({
                "id":   tc.get("id", ""),
                "name": tc.get("name", ""),
                "args": args,
                "type": "tool_call",
            })
        return finalised
