"""
needoh/agent/loop.py
The core agentic loop.
"""

from __future__ import annotations

import asyncio
import json
import os
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

# Groq TPM: large tool results in history inflate every request. Truncate ToolMessage bodies
# sent to the LLM (full text is still shown in the REPL when the tool returns).
_DEFAULT_TOOL_MSG_CAP = 10000

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
- Tool calls must match each tool's schema (e.g. write_file: {"path": "...", "content": "..."}). Never use a wrapper key named "parameters"; never use XML-style tool tags.
- Always read a file before editing it
- Prefer small, focused tool calls over large ones
- Do not use edit_file when oldText or newText would span more than a single line; use write_file with the full file body instead (Groq often rejects large edit_file JSON)
- For tiny one-line inserts in an already-read file, a minimal edit_file is OK only if oldText and newText are each one line
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

    def _messages_for_llm(self) -> list[BaseMessage]:
        """Shrink history for the API: long tool outputs cause 413 TPM errors on Groq."""
        cap = int(os.getenv("NEEDOH_TOOL_OUTPUT_MAX_CHARS", str(_DEFAULT_TOOL_MSG_CAP)))
        if cap <= 0:
            return list(self.history)
        out: list[BaseMessage] = []
        for m in self.history:
            if not isinstance(m, ToolMessage):
                out.append(m)
                continue
            text = m.content if isinstance(m.content, str) else str(m.content)
            if len(text) <= cap:
                out.append(m)
                continue
            reserve = 160
            cut = max(0, cap - reserve)
            lost = len(text) - cut
            note = (
                f"\n\n...[truncated {lost} chars for LLM context; "
                "raise NEEDOH_TOOL_OUTPUT_MAX_CHARS or clear history with /clear if needed]"
            )
            out.append(
                ToolMessage(
                    content=text[:cut] + note,
                    tool_call_id=m.tool_call_id,
                )
            )
        return out

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
            return llm.invoke(self._messages_for_llm())

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
            elif (
                "rate_limit_exceeded" in err_s.lower()
                or "tokens per minute" in err_s.lower()
                or "error code: 413" in err_s.lower()
            ):
                hint = (
                    " Groq on_demand TPM: the request is too large for this model's per-minute cap. "
                    "Lower NEEDOH_TOOL_OUTPUT_MAX_CHARS (tool results in history are truncated), "
                    "start a fresh session, wait ~60s, or try a higher-TPM model (may break tools)."
                )
            elif (
                "tool_use_failed" in err_s.lower()
                or "failed_generation" in err_s.lower()
                or "parse tool call arguments" in err_s.lower()
                or "validation failed" in err_s.lower()
            ):
                hint = (
                    " Groq rejected the tool call format (wrong JSON shape, e.g. 'parameters' "
                    "instead of tool args, or XML). Default model is openai/gpt-oss-20b for reliable "
                    "tools; meta-llama/llama-4-scout-17b-16e-instruct often triggers this. "
                    "Retry or set DEFAULT_GROQ_MODEL=openai/gpt-oss-20b."
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

            spin_msg = f"Running {name}…"
            if name == "query_langchain_docs":
                spin_msg = (
                    "Running query_langchain_docs… "
                    "(first call loads local embeddings — may take 30–90s)"
                )
            with SpinnerContext(spin_msg):
                try:
                    if name == "run_shell_command":
                        result = await self._shell.run(
                            args.get("command", ""),
                            timeout=args.get("timeout", 60),
                        )
                    elif name == "change_directory":
                        result = self._shell.change_dir(args.get("path", "."))
                    elif name == "query_langchain_docs":
                        q = args.get("query", "")
                        rag_args = {
                            "query": q.strip() if isinstance(q, str) else "",
                        }
                        sec = float(os.getenv("RAG_CLIENT_TIMEOUT_SEC", "180"))
                        try:
                            result = await asyncio.wait_for(
                                self.mcp.call_tool(name, rag_args),
                                timeout=sec,
                            )
                        except asyncio.TimeoutError:
                            result = (
                                f"ERROR: query_langchain_docs exceeded {sec:.0f}s "
                                f"(RAG_CLIENT_TIMEOUT_SEC). The RAG subprocess may be "
                                "loading the embedding model or stuck; check terminal "
                                "stderr for [needoh-rag] lines."
                            )
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

