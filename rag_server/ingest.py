"""
rag_server/ingest.py
One-time ingestion script for LangChain documentation.

Run this ONCE before starting Needoh (from the project root):
    python rag_server/ingest.py

Strategy: LangChain's docs website is fully client-side rendered (React),
so HTML scraping yields only navigation chrome. Instead we source content from:
  1. Installed package docstrings (via inspect) -- exact API reference for the
     installed version; always available offline.
  2. Raw Python source files from GitHub -- includes usage examples embedded
     in module docstrings and comments.

After this runs, the chroma_store/ directory persists on disk.
All future Needoh sessions query that store directly -- no re-ingestion needed.
"""

from __future__ import annotations

import inspect
import os
import shutil
import sys
import textwrap
import types
from pathlib import Path

# Ensure rag_server/ is importable when run from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

from chroma_dir import get_chroma_persist_dir

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME = "langchain_docs"
CHUNK_SIZE      = 600
CHUNK_OVERLAP   = 80
MIN_CHUNK_LEN   = 60

# ── GitHub raw source files to ingest ─────────────────────────────────────────
GITHUB_RAW_URLS: list[tuple[str, str]] = [
    # (url, label)
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/language_models/chat_models.py",
        "langchain_core.language_models.chat_models",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/tools/base.py",
        "langchain_core.tools.base",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/tools/convert.py",
        "langchain_core.tools.convert",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/vectorstores/base.py",
        "langchain_core.vectorstores.base",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/runnables/base.py",
        "langchain_core.runnables.base",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/messages/__init__.py",
        "langchain_core.messages",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/output_parsers/base.py",
        "langchain_core.output_parsers.base",
    ),
    (
        "https://raw.githubusercontent.com/langchain-ai/langchain/master/"
        "libs/core/langchain_core/prompts/chat.py",
        "langchain_core.prompts.chat",
    ),
]

# ── LangChain modules to extract docstrings from ──────────────────────────────
DOCSTRING_MODULES = [
    "langchain_core.language_models.chat_models",
    "langchain_core.language_models.base",
    "langchain_core.tools.base",
    "langchain_core.tools.structured",
    "langchain_core.tools.convert",
    "langchain_core.vectorstores.base",
    "langchain_core.runnables.base",
    "langchain_core.runnables.passthrough",
    "langchain_core.output_parsers.base",
    "langchain_core.output_parsers.string",
    "langchain_core.prompts.chat",
    "langchain_core.prompts.prompt",
    "langchain_core.messages.base",
    "langchain_core.messages.human",
    "langchain_core.messages.ai",
    "langchain_core.messages.system",
    "langchain_core.messages.tool",
    "langchain_text_splitters.base",
    "langchain_text_splitters.character",
    "langchain_chroma.vectorstores",
    "langchain_groq.chat_models",
    "langchain_community.document_loaders.web_base",
]


def _extract_docstrings(module_name: str) -> list[tuple[str, str]]:
    """Import a module and extract (name, docstring) pairs from all public members."""
    try:
        mod = __import__(module_name, fromlist=[""])
    except ImportError:
        return []

    results: list[tuple[str, str]] = []
    # Module-level docstring
    if mod.__doc__:
        results.append((module_name, textwrap.dedent(mod.__doc__).strip()))

    for attr_name in dir(mod):
        if attr_name.startswith("_"):
            continue
        try:
            obj = getattr(mod, attr_name)
        except Exception:
            continue

        # Classes
        if inspect.isclass(obj) and obj.__module__ == module_name:
            doc = inspect.getdoc(obj)
            if doc and len(doc) > 30:
                results.append((f"{module_name}.{attr_name}", doc))
            # Methods within the class
            for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                if method_name.startswith("_"):
                    continue
                mdoc = inspect.getdoc(method)
                if mdoc and len(mdoc) > 30:
                    results.append(
                        (f"{module_name}.{attr_name}.{method_name}", mdoc)
                    )

        # Module-level functions
        elif inspect.isfunction(obj) and obj.__module__ == module_name:
            doc = inspect.getdoc(obj)
            if doc and len(doc) > 30:
                results.append((f"{module_name}.{attr_name}", doc))

    return results


def _fetch_github_file(url: str) -> str | None:
    """Download a raw Python source file from GitHub."""
    try:
        import requests
        r = requests.get(url, timeout=20, headers={"User-Agent": "Needoh-RAG-Ingestion/0.1"})
        if r.status_code == 200:
            return r.text
    except Exception as exc:
        print(f"    warning: could not fetch {url}: {exc}")
    return None


def run_ingestion() -> None:
    """Build the LangChain documentation vector store."""
    chroma_dir = get_chroma_persist_dir()
    print("Needoh RAG Ingestion")
    print(f"   Persist path : {chroma_dir}")
    print(f"   Embedding    : {EMBEDDING_MODEL}")
    print(f"   Chunk size   : {CHUNK_SIZE} / overlap {CHUNK_OVERLAP}")
    print()

    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    # ── Embeddings ────────────────────────────────────────────────────────────
    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    all_docs: list[Document] = []

    # ── Source 1: Installed package docstrings ────────────────────────────────
    print(f"\nExtracting docstrings from {len(DOCSTRING_MODULES)} LangChain modules...")
    for mod_name in DOCSTRING_MODULES:
        pairs = _extract_docstrings(mod_name)
        if pairs:
            for name, doc in pairs:
                all_docs.append(Document(
                    page_content=f"# {name}\n\n{doc}",
                    metadata={"source": f"docstring://{name}"},
                ))
            print(f"  OK  {mod_name}  ({len(pairs)} docstrings)")
        else:
            print(f"  SKIP  {mod_name}  (not importable or no public docs)")

    # ── Source 2: GitHub raw source files ─────────────────────────────────────
    print(f"\nFetching {len(GITHUB_RAW_URLS)} source files from GitHub...")
    for url, label in GITHUB_RAW_URLS:
        content = _fetch_github_file(url)
        if content:
            all_docs.append(Document(
                page_content=content,
                metadata={"source": url, "label": label},
            ))
            print(f"  OK  {label}  ({len(content)} chars)")
        else:
            print(f"  FAIL  {label}")

    print(f"\nTotal raw documents: {len(all_docs)}")

    # ── Split into chunks ─────────────────────────────────────────────────────
    print("Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
    )
    all_chunks = splitter.split_documents(all_docs)
    chunks = [c for c in all_chunks if len(c.page_content.strip()) >= MIN_CHUNK_LEN]
    print(f"Created {len(chunks)} chunks (filtered from {len(all_chunks)}).")

    # ── Clear existing store and re-ingest ────────────────────────────────────
    chroma_path = Path(chroma_dir)
    if chroma_path.exists():
        print(f"Removing existing store at {chroma_dir}...")
        shutil.rmtree(chroma_dir)
    chroma_path.mkdir(parents=True, exist_ok=True)

    print(f"Embedding and storing in ChromaDB at {chroma_dir}...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=chroma_dir,
    )

    print(f"\nIngestion complete! {len(chunks)} chunks stored.")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Path:       {chroma_dir}")
    print("\nYou can now run Needoh -- the RAG server will query this store.")


if __name__ == "__main__":
    run_ingestion()
