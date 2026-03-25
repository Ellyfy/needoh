"""
rag_server/server.py
Custom MCP server that exposes LangChain documentation via HyDE retrieval.

This server is started by the Needoh MCP client as a subprocess.
It exposes one tool: query_langchain_docs(query)

The agent calls this tool automatically whenever it needs information about
LangChain APIs, patterns, or usage examples.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

load_dotenv()

# Ensure the rag_server directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./rag_server/chroma_store")

# ── Server setup ──────────────────────────────────────────────────────────────
app = Server("needoh-rag")

# Lazy-load the retriever so the server starts fast and loads
# the heavy embedding model only when the first query arrives
_retriever = None


def get_retriever():
    """Return the HyDERetriever, initialising it on first call."""
    global _retriever
    if _retriever is None:
        # Verify the vector store exists before trying to load it
        if not Path(CHROMA_PERSIST_DIR).exists():
            raise RuntimeError(
                f"ChromaDB store not found at '{CHROMA_PERSIST_DIR}'.\n"
                "Run: python rag_server/ingest.py"
            )
        from retriever import HyDERetriever
        _retriever = HyDERetriever()
    return _retriever


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

    query = arguments.get("query", "").strip()
    if not query:
        return [types.TextContent(type="text", text="Error: query cannot be empty.")]

    try:
        retriever = get_retriever()
        result = retriever.retrieve_as_text(query)
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
    asyncio.run(main())
