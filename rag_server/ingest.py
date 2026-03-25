"""
rag_server/ingest.py
One-time ingestion script for LangChain documentation.

Run this ONCE before starting Needoh:
    python rag_server/ingest.py

What it does:
  1. Fetches LangChain documentation pages from the web
  2. Splits them into chunks using RecursiveCharacterTextSplitter
  3. Embeds each chunk with sentence-transformers (runs locally, no API key)
  4. Stores everything in ChromaDB at ./rag_server/chroma_store

After this runs, the chroma_store/ directory persists on disk.
All future Needoh sessions query that store directly — no re-ingestion needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./rag_server/chroma_store")
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME    = "langchain_docs"
CHUNK_SIZE         = 800
CHUNK_OVERLAP      = 100

# LangChain documentation URLs to ingest
DOC_URLS: list[str] = [
    "https://python.langchain.com/docs/introduction/",
    "https://python.langchain.com/docs/concepts/",
    "https://python.langchain.com/docs/tutorials/llm_chain/",
    "https://python.langchain.com/docs/tutorials/chatbot/",
    "https://python.langchain.com/docs/tutorials/rag/",
    "https://python.langchain.com/docs/tutorials/agents/",
    "https://python.langchain.com/docs/how_to/",
    "https://python.langchain.com/docs/concepts/agents/",
    "https://python.langchain.com/docs/concepts/tools/",
    "https://python.langchain.com/docs/concepts/memory/",
    "https://python.langchain.com/docs/concepts/chains/",
    "https://python.langchain.com/docs/integrations/chat/groq/",
    "https://python.langchain.com/docs/integrations/vectorstores/chroma/",
]


def run_ingestion() -> None:
    """Download, chunk, embed, and store LangChain docs into ChromaDB."""
    print("🔩 Needoh RAG Ingestion")
    print(f"   Persist path : {CHROMA_PERSIST_DIR}")
    print(f"   Embedding    : {EMBEDDING_MODEL}")
    print(f"   Chunk size   : {CHUNK_SIZE} / overlap {CHUNK_OVERLAP}")
    print()

    # ── Lazy imports (heavy, only needed during ingestion) ────────────────────
    import os as _os
    _os.environ.setdefault("USER_AGENT", "Needoh-RAG-Ingestion/0.1")

    from langchain_community.document_loaders import WebBaseLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings

    # ── Embeddings (local, no API key) ────────────────────────────────────────
    print("Loading embedding model…")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # ── Load documents ────────────────────────────────────────────────────────
    print(f"Fetching {len(DOC_URLS)} documentation pages…")
    all_docs = []
    for url in DOC_URLS:
        try:
            loader = WebBaseLoader(url)
            docs = loader.load()
            all_docs.extend(docs)
            print(f"  ✓ {url}  ({len(docs)} page(s))")
        except Exception as exc:
            print(f"  ✗ {url}  — {exc}")

    if not all_docs:
        print("No documents loaded. Check your internet connection.")
        sys.exit(1)

    print(f"\nLoaded {len(all_docs)} raw document(s).")

    # ── Split into chunks ─────────────────────────────────────────────────────
    print("Splitting into chunks…")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Split on natural boundaries first (headers, paragraphs, sentences)
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)
    print(f"Created {len(chunks)} chunks.")

    # ── Persist to ChromaDB ───────────────────────────────────────────────────
    print(f"Embedding and storing in ChromaDB at {CHROMA_PERSIST_DIR}…")
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    print(f"\n✅ Ingestion complete! {len(chunks)} chunks stored.")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Path:       {CHROMA_PERSIST_DIR}")
    print("\nYou can now run Needoh — the RAG server will query this store.")


if __name__ == "__main__":
    run_ingestion()
