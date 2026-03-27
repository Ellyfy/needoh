"""
needoh/agent/loop.py
The core agentic loop.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from agent.providers import BaseProvider
from agent.tools import ShellTool, get_local_tool_schemas
from mcpclient.client import NeedohMCPClient
from ui.display import (
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

MAX_ITERATIONS = 30

_TOOL_NAME_ALIASES = {
    "tavily_search": "tavily-search",
    "tavily_extract": "tavily-extract",
    "readfile": "read_file",
}


def _valid_tool_calls(tool_calls: list[dict]) -> list[dict]:
    out: list[dict] = []
    for tc in tool_calls or []:
        name = (tc.get("name") or "").strip()
        if not name:
            continue
        alias = _TOOL_NAME_ALIASES.get(name, name)
        out.append({**tc, "name": alias})
    return out


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
- If you are unsure about scope, ask ONE clarifying question
- Use query_langchain_docs only for LangChain / LCEL / agent API questions—not for general programming trivia
- Use tavily-search for current web information; use tavily-extract to read a specific URL
- Use resolve-library-id then query-docs (Context7) for third-party library documentation

When you are done with a task, summarise what you did concisely."""


class AgentLoop:
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
        self.history: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        self._tools = mcp_client.get_all_tools() + get_local_tool_schemas()

    async def run(self, user_input: str) -> None:
        self.history.append(HumanMessage(content=user_input))

        for iteration in range(MAX_ITERATIONS):
            response = await self._call_llm()

            valid_calls = _valid_tool_calls(response.tool_calls)

            if not valid_calls:
                self.history.append(response)
                break

            tool_results = await self._execute_tool_calls(valid_calls)

            self.history.append(response)
            for tr in tool_results:
                self.history.append(tr)

            console.print(f"\n[{DIM}]— iteration {iteration + 1} —[/]\n")

        else:
            print_error(f"Reached max iterations ({MAX_ITERATIONS}). Stopping.")

    def clear_history(self) -> None:
        self.history = [SystemMessage(content=SYSTEM_PROMPT)]

    async def _emit_assistant_text(self, text: str) -> None:
        """Print assistant text in small chunks for a streaming-style REPL."""
        if not text:
            return
        parts = re.findall(r"\S+\s*", text)
        if not parts:
            stream_llm_response(text)
            await asyncio.sleep(0)
            return
        for p in parts:
            stream_llm_response(p)
            await asyncio.sleep(0)

    async def _call_llm(self) -> AIMessage:
        console.print(f"\n[bold {ACCENT}]needoh ›[/] ", end="")

        loop = asyncio.get_event_loop()
        llm = self.provider.get_llm(tools=self._tools)

        def _invoke():
            return llm.invoke(self.history)

        try:
            response = await loop.run_in_executor(None, _invoke)
        except Exception as exc:
            print_error(f"LLM error: {exc}")
            end_stream()
            hint = ""
            err_s = str(exc)
            if "model_decommissioned" in err_s.lower() or "decommissioned" in err_s.lower():
                hint = (
                    " That Groq model was retired. Set DEFAULT_GROQ_MODEL to a current id "
                    "(see https://console.groq.com/docs/deprecations), e.g. openai/gpt-oss-20b."
                )
            elif "Failed to call a function" in err_s or "tool_use_failed" in err_s.lower():
                hint = (
                    " Groq tool calling failed (e.g. llama-3.3-70b-versatile XML tools). "
                    "Try openai/gpt-oss-20b or llama-3.1-8b-instant: DEFAULT_GROQ_MODEL or /model."
                )
            return AIMessage(
                content=f"[needoh] Model call failed: {exc}{hint}",
                tool_calls=[],
            )

        raw_content = getattr(response, "content", "") or ""
        if isinstance(raw_content, list):
            parts: list[str] = []
            for block in raw_content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(str(block))
            full_content = "".join(parts)
        else:
            full_content = str(raw_content)

        if full_content:
            await self._emit_assistant_text(full_content)

        end_stream()

        tool_calls: list[dict] = []
        raw_tcs = getattr(response, "tool_calls", None) or []
        for tc in raw_tcs:
            if isinstance(tc, dict):
                args = tc.get("args")
                if not isinstance(args, dict):
                    args = {}
                tool_calls.append({
                    "id": tc.get("id", "") or "",
                    "name": tc.get("name", "") or "",
                    "args": args,
                    "type": "tool_call",
                })
            else:
                args = getattr(tc, "args", None)
                if not isinstance(args, dict):
                    args = {}
                tool_calls.append({
                    "id": getattr(tc, "id", "") or "",
                    "name": getattr(tc, "name", "") or "",
                    "args": args,
                    "type": "tool_call",
                })

        return AIMessage(content=full_content, tool_calls=tool_calls)

    async def _execute_tool_calls(
        self, tool_calls: list[dict]
    ) -> list[ToolMessage]:
        results: list[ToolMessage] = []

        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            call_id = tc.get("id", "")

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

    @staticmethod
    def _merge_tool_call_chunk(
        accumulated: list[dict], chunk: Any
    ) -> None:
        idx = getattr(chunk, "index", 0) or 0

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
        finalised = []
        for tc in raw:
            try:
                args = json.loads(tc["args"]) if tc["args"] else {}
            except json.JSONDecodeError:
                args = {"raw": tc["args"]}
            finalised.append({
                "id": tc.get("id", ""),
                "name": tc.get("name", ""),
                "args": args,
                "type": "tool_call",
            })
        return finalised

