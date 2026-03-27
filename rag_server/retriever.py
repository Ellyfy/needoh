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

from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./rag_server/chroma_store")
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME    = "langchain_docs"
TOP_K              = 5   # number of chunks to return

# Prompt that instructs the LLM to write a hypothetical documentation snippet
HYDE_PROMPT = """You are a technical documentation writer for LangChain.
Write a detailed, accurate documentation snippet that would directly answer
the following question. Write it as if it were real documentation, including
code examples where relevant. Be specific and technical.

Question: {query}

Documentation snippet:"""


class HyDERetriever:
    """
    Retriever using Hypothetical Document Embeddings.

    Usage:
        retriever = HyDERetriever()
        docs = retriever.retrieve("how do I add memory to an agent?")
    """

    def __init__(self):
        self._embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self._vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=self._embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )
        self._llm = self._build_llm()

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[Document]:
        """
        Retrieve the most relevant documentation chunks for a query.

        Steps:
          1. Generate a hypothetical answer to the query using the LLM
          2. Embed the hypothetical answer
          3. Search ChromaDB with that embedding
          4. Return top_k real document chunks

        Args:
            query:  The user's question or search query.
            top_k:  Number of chunks to return.

        Returns:
            List of LangChain Document objects with page_content and metadata.
        """
        # Step 1 — Generate hypothetical answer
        hypothetical = self._generate_hypothetical(query)

        # Step 2+3 — Embed hypothetical answer and search
        results = self._vectorstore.similarity_search(
            hypothetical, k=top_k
        )
        return results

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
        Falls back to the raw query if the LLM call fails.
        """
        try:
            prompt = HYDE_PROMPT.format(query=query)
            response = self._llm.invoke(prompt)
            # LangChain returns an AIMessage; extract text content
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as exc:
            print(f"[HyDE] Hypothetical generation failed: {exc}. Using raw query.")
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
            return ChatGroq(
                model=os.getenv("DEFAULT_GROQ_MODEL", "openai/gpt-oss-20b"),
                api_key=groq_key,
                temperature=0.3,   # slight creativity for hypothetical writing
                max_tokens=400,
            )
        else:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=os.getenv("OLLAMA_MODEL", "llama3"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=0.3,
            )
