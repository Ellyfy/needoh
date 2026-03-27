"""
needoh/mcpclient/config.py
MCP server connection configurations.

Each entry in SERVERS defines how to start / connect to an MCP server.
The MCP client reads this at startup and launches each server as a subprocess.

Windows note: npx must be invoked via "cmd /c npx" to resolve correctly
when running inside a Python subprocess on Windows.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _rag_server_path() -> str:
    """Absolute path to the custom RAG MCP server script."""
    here = Path(__file__).resolve().parent.parent
    return str(here / "rag_server" / "server.py")


def _npx_cmd() -> tuple[str, list[str]]:
    """
    Return the correct command + prefix args to run npx on this OS.
    On Windows, npx must be run via cmd /c to resolve correctly.
    On Mac/Linux, npx works directly.
    """
    if sys.platform == "win32":
        return "cmd", ["/c", "npx"]
    return "npx", []


_CMD, _PREFIX = _npx_cmd()


def _filesystem_allowed_dirs() -> list[str]:
    """Roots passed to @modelcontextprotocol/server-filesystem."""
    raw = os.getenv("FILESYSTEM_ALLOWED_DIRS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [str(Path.cwd().resolve())]


def build_servers() -> list[dict]:
    """
    Build MCP server configs. Tavily is omitted if TAVILY_API_KEY is unset so
    npx does not crash with environment variable is required.
    """
    servers: list[dict] = [
        {
            "name": "filesystem",
            "command": _CMD,
            "args": [
                *_PREFIX,
                "-y",
                "@modelcontextprotocol/server-filesystem",
                *_filesystem_allowed_dirs(),
            ],
            "env": {},
        },
    ]

    if os.getenv("TAVILY_API_KEY", "").strip():
        servers.append(
            {
                "name": "tavily",
                "command": _CMD,
                "args": [*_PREFIX, "-y", "tavily-mcp@0.1.4"],
                "env": {
                    "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
                },
            }
        )

    servers.extend(
        [
            {
                "name": "context7",
                "command": _CMD,
                "args": [*_PREFIX, "-y", "@upstash/context7-mcp@latest"],
                "env": {},
            },
            {
                "name": "rag",
                "command": sys.executable,
                "args": [_rag_server_path()],
                "env": {
                    "CHROMA_PERSIST_DIR": os.getenv(
                        "CHROMA_PERSIST_DIR", "./rag_server/chroma_store"
                    ),
                    "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
                    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
                    "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                    "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL", "llama3"),
                },
            },
        ]
    )

    return servers


SERVERS: list[dict] = build_servers()
