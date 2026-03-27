"""
rag_server/server.py
Custom MCP server that exposes LangChain documentation via HyDE retrieval.

This server is started by the Needoh MCP client as a subprocess.
It exposes one tool: query_langchain_docs(query)

The agent calls this tool automatically whenever it needs information about
LangChain APIs, patterns, or usage examples.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path

# Ensure the rag_server directory is importable BEFORE any local imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chroma_dir import get_chroma_persist_dir

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

load_dotenv()

CHROMA_PERSIST_DIR = get_chroma_persist_dir()

# ── Server setup ──────────────────────────────────────────────────────────────
app = Server("needoh-rag")

# Lazy-load the retriever so the server starts fast and loads
# the heavy embedding model only when the first query arrives
_retriever = None
_retriever_lock = threading.Lock()


def get_retriever():
    """Return the HyDERetriever, initialising it on first call (thread-safe)."""
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                chroma_path = Path(CHROMA_PERSIST_DIR)
                if not chroma_path.exists() or not (chroma_path / "chroma.sqlite3").exists():
                    raise RuntimeError(
                        f"ChromaDB store not found or incomplete at '{CHROMA_PERSIST_DIR}'.\n"
                        "Run from the project root: python rag_server/ingest.py"
                    )
                from retriever import HyDERetriever

                _retriever = HyDERetriever()
    return _retriever

def _rag_warmup_enabled() -> bool:
    raw = os.getenv("RAG_WARMUP", "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _background_warmup() -> None:
    """Preload embeddings in background (default on; RAG_WARMUP=false to skip)."""
    if not _rag_warmup_enabled():
        return

    def _run() -> None:
        try:
            print(
                "[needoh-rag] RAG_WARMUP: loading local embeddings + Chroma in background…",
                file=sys.stderr,
            )
            get_retriever().warm_embeddings()
            print("[needoh-rag] RAG_WARMUP: embedding model ready.", file=sys.stderr)
        except Exception as exc:
            print(f"[needoh-rag] RAG_WARMUP failed: {exc}", file=sys.stderr)

    threading.Thread(target=_run, daemon=True).start()

# ── MCP tool definitions ──────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Advertise the tools this server provides to the MCP client."""
    return [
        types.Tool(
            name="query_langchain_docs",
            description=(
                "Search the LangChain documentation for information about "
                "LangChain APIs, concepts, patterns, and usage examples. "
                "Use this whenever you need to know how to use LangChain: "
                "agents, chains, memory, tools, LCEL, embeddings, vectorstores, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language question about LangChain. "
                            "Be specific: e.g. 'how do I add conversation memory to an agent' "
                            "rather than just 'memory'."
                        ),
                    }
                },
                "required": ["query"],
            },
        )
    ]


@app.call_tool()
async def call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent]:
    """Handle a tool call from the MCP client."""
    if name != "query_langchain_docs":
        raise ValueError(f"Unknown tool: {name}")

    raw_q = arguments.get("query", "")
    query = raw_q.strip() if isinstance(raw_q, str) else ""
    if not query:
        return [types.TextContent(type="text", text="Error: query cannot be empty.")]

    try:
        retriever = get_retriever()

        def _run() -> str:
            return retriever.retrieve_as_text(query)

        result = await asyncio.to_thread(_run)
        return [types.TextContent(type="text", text=result)]

    except RuntimeError as exc:
        return [types.TextContent(type="text", text=f"RAG server error: {exc}")]
    except Exception as exc:
        return [types.TextContent(type="text", text=f"Retrieval failed: {exc}")]


# ── Entrypoint ────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    _background_warmup()
    asyncio.run(main())
