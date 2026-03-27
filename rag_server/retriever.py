"""
rag_server/retriever.py
HyDE (Hypothetical Document Embeddings) retriever for LangChain docs.

Advanced RAG technique:
  Instead of embedding the raw user query — which is often short and vague —
  HyDE first asks an LLM to write a *hypothetical answer* to the query,
  then embeds that answer to search the vector store.

  The hypothetical answer is much richer than the original query and
  therefore lands much closer to the real documentation in embedding space.

Reference: Gao et al., "Precise Zero-Shot Dense Retrieval without
           Relevance Labels", ACL 2023. https://arxiv.org/abs/2212.10496
"""

from __future__ import annotations

import os
import sys
import threading
import time

from chroma_dir import get_chroma_persist_dir
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

CHROMA_PERSIST_DIR = get_chroma_persist_dir()
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME    = "langchain_docs"
TOP_K              = int(os.getenv("RAG_TOP_K", "5"))

_HYDE_TRUE = frozenset({"1", "true", "yes", "on"})


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in _HYDE_TRUE

HYDE_PROMPT = """You are a technical documentation writer for LangChain.
Write a concise documentation-style answer (2-4 short paragraphs max) that would
directly answer the question. Include API or code mentions where relevant.

Question: {query}

Documentation snippet:"""



class HyDERetriever:
    """HyDE retriever; HuggingFace embeddings load lazily on first retrieve()."""

    _store_lock = threading.Lock()
    _load_notice_printed = False
    _init_failed: str | None = None

    def __init__(self):
        self._embeddings = None
        self._vectorstore = None
        self._llm = None
        # Default off: HyDE adds a second LLM call and is a common hang source; enable via HYDE_ENABLED=true.
        self._hyde_enabled = _env_flag("HYDE_ENABLED", default=False)

    @staticmethod
    def _log_timing(phase: str, t0: float) -> float:
        if not _env_flag("RAG_LOG_TIMING", default=False):
            return time.monotonic()
        t1 = time.monotonic()
        print(f"[needoh-rag timing] {phase}: {t1 - t0:.2f}s", file=sys.stderr)
        return t1

    def _ensure_vectorstore(self) -> None:
        if self._vectorstore is not None:
            return
        failed = HyDERetriever._init_failed
        if failed is not None:
            raise RuntimeError(failed)
        with self._store_lock:
            if self._vectorstore is not None:
                return
            failed = HyDERetriever._init_failed
            if failed is not None:
                raise RuntimeError(failed)
            t0 = time.monotonic()
            if not HyDERetriever._load_notice_printed:
                print(
                    "[needoh-rag] Loading sentence-transformers + Chroma "
                    f"({EMBEDDING_MODEL}) — often 30–90s the first time in this process.",
                    file=sys.stderr,
                    flush=True,
                )
                HyDERetriever._load_notice_printed = True

            timeout = float(os.getenv("RAG_EMBED_INIT_TIMEOUT_SEC", "120"))
            result_box: list = []

            def _load() -> None:
                try:
                    emb = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
                    vs = Chroma(
                        collection_name=COLLECTION_NAME,
                        embedding_function=emb,
                        persist_directory=CHROMA_PERSIST_DIR,
                    )
                    result_box.append(("ok", emb, vs))
                except Exception as e:
                    result_box.append(("err", e))

            th = threading.Thread(target=_load, daemon=True, name="needoh-embed-init")
            th.start()
            th.join(timeout=timeout)
            if th.is_alive():
                msg = (
                    f"Local embedding model + Chroma init exceeded {timeout}s "
                    "(slow disk/network downloading the model). "
                    "Set RAG_EMBED_INIT_TIMEOUT_SEC or pre-cache the model; "
                    "check rag MCP stderr."
                )
                HyDERetriever._init_failed = msg
                print(f"[needoh-rag] {msg}", file=sys.stderr, flush=True)
                raise RuntimeError(msg)
            if not result_box:
                msg = "Embedding init finished without result."
                HyDERetriever._init_failed = msg
                raise RuntimeError(msg)
            item = result_box[0]
            if item[0] == "err":
                exc = item[1]
                HyDERetriever._init_failed = str(exc)
                raise exc
            _, self._embeddings, self._vectorstore = item
            self._log_timing("HuggingFaceEmbeddings + Chroma init", t0)

    def _ensure_llm(self) -> None:
        if self._llm is None:
            self._llm = self._build_llm()

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[Document]:
        """Retrieve the most relevant documentation chunks for a query."""
        t0 = time.monotonic()
        self._ensure_vectorstore()
        t0 = self._log_timing("after vectorstore ready", t0)
        assert self._vectorstore is not None
        if self._hyde_enabled:
            self._ensure_llm()
            hypothetical = self._generate_hypothetical(query)
            t0 = self._log_timing("HyDE LLM hypothetical", t0)
        else:
            hypothetical = query
        docs = self._vectorstore.similarity_search(hypothetical, k=top_k)
        self._log_timing("Chroma similarity_search", t0)
        return docs

    def warm_embeddings(self) -> None:
        """Preload embedding model + Chroma (optional RAG_WARMUP in server)."""
        self._ensure_vectorstore()

    def retrieve_as_text(self, query: str, top_k: int = TOP_K) -> str:
        """
        Retrieve and format results as a single string for the MCP response.
        """
        docs = self.retrieve(query, top_k=top_k)
        if not docs:
            return "No relevant documentation found."

        parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            parts.append(f"[{i}] Source: {source}\n{doc.page_content}")

        return "\n\n---\n\n".join(parts)

    # ── Private ───────────────────────────────────────────────────────────────

    def _generate_hypothetical(self, query: str) -> str:
        """
        Ask the LLM to write a hypothetical documentation answer.
        Falls back to the raw query if the LLM call fails or times out.
        """
        try:
            prompt = HYDE_PROMPT.format(query=query)
            messages = [HumanMessage(content=prompt)]
            timeout = float(os.getenv("RAG_HYDE_TIMEOUT_SEC", "120"))

            # Thread.join(timeout), not ThreadPoolExecutor: on timeout, executor
            # __exit__ calls shutdown(wait=True) and blocks until a stuck Groq
            # invoke() returns — effectively forever.
            result_holder: list = []
            exc_holder: list = []

            def _worker() -> None:
                try:
                    assert self._llm is not None
                    result_holder.append(self._llm.invoke(messages))
                except Exception as e:
                    exc_holder.append(e)

            th = threading.Thread(target=_worker, daemon=True, name="needoh-hyde")
            th.start()
            th.join(timeout=timeout)
            if th.is_alive():
                print(
                    f"[HyDE] Groq/Ollama call exceeded {timeout}s; using raw query for embedding.",
                    file=sys.stderr,
                    flush=True,
                )
                return query
            if exc_holder:
                raise exc_holder[0]
            if not result_holder:
                return query
            response = result_holder[0]
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as exc:
            print(f"[HyDE] Hypothetical generation failed: {exc}. Using raw query.", flush=True)
            return query

    @staticmethod
    def _build_llm():
        """
        Build an LLM for hypothetical generation.
        Prefers Groq for speed; falls back to Ollama.
        """
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            from langchain_groq import ChatGroq
            hyde_max = int(os.getenv("RAG_HYDE_MAX_TOKENS", "256"))
            return ChatGroq(
                model=os.getenv("DEFAULT_GROQ_MODEL", "openai/gpt-oss-20b"),
                api_key=groq_key,
                temperature=0.3,
                max_tokens=hyde_max,
                streaming=False,
            )
        else:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=os.getenv("OLLAMA_MODEL", "llama3"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=0.3,
            )
