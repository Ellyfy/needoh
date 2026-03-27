"""
Resolve Chroma persist directory consistently for ingest, server, and retriever.
"""
from __future__ import annotations

import os
from pathlib import Path

_RAG_PKG = Path(__file__).resolve().parent


def get_chroma_persist_dir() -> str:
    raw = os.getenv("CHROMA_PERSIST_DIR", "").strip()
    if raw:
        p = Path(raw)
        return str(p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve())
    return str(_RAG_PKG / "chroma_store")
