"""
needoh/agent/providers.py
LLM provider abstraction layer.

Supports:
  - GroqProvider  (cloud, fast inference via Groq API)
  - OllamaProvider (local models via Ollama)

Both expose the same interface so the agentic loop never
needs to know which provider is in use.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Iterator

from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str = ""
    model: str = ""

    @abstractmethod
    def get_llm(self, tools: list[dict] | None = None) -> BaseChatModel:
        """
        Return a LangChain chat model instance, optionally bound to tools.
        
        Args:
            tools: List of tool schemas to bind to the model.
                   If None, returns a plain chat model.
        """
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[BaseMessage],
        tools: list[dict] | None = None,
    ) -> Iterator[Any]:
        """
        Stream a response from the LLM.

        Args:
            messages: Conversation history as LangChain messages.
            tools: Tool schemas available to the model.

        Yields:
            LangChain AIMessageChunk objects.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"


class GroqProvider(BaseProvider):
    """
    Cloud LLM via Groq API.
    Groq offers very fast inference with Llama 3 and other open models.
    Get a free API key at: https://console.groq.com

    Default model is openai/gpt-oss-20b: Groq-compatible tool-call JSON. Llama 4 Scout and some
    Llama instants emit invalid shapes (e.g. a "parameters" wrapper) and return tool_use_failed.
    TPM is lower (~8K) than Scout; Needoh truncates long tool results in history
    (NEEDOH_TOOL_OUTPUT_MAX_CHARS) to reduce 413 errors. Override via DEFAULT_GROQ_MODEL.
    """

    name = "groq"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("DEFAULT_GROQ_MODEL", "openai/gpt-oss-20b")
        self._api_key = os.getenv("GROQ_API_KEY")
        if not self._api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Add it to your .env file.\n"
                "Get a free key at: https://console.groq.com"
            )

    def get_llm(self, tools: list[dict] | None = None) -> BaseChatModel:
        from langchain_groq import ChatGroq

        # Groq: invoke() with bind_tools + streaming=True uses the SSE API and often
        # raises APIError("Failed to call a function..."). Non-streaming create() is
        # stable for tool calls. Plain (no tools) keeps streaming for provider.stream().
        use_stream = tools is None
        llm = ChatGroq(
            model=self.model,
            api_key=self._api_key,
            temperature=0,
            streaming=use_stream,
        )
        if tools:
            return llm.bind_tools(tools)
        return llm

    def stream(
        self,
        messages: list[BaseMessage],
        tools: list[dict] | None = None,
    ) -> Iterator[Any]:
        llm = self.get_llm(tools=tools)
        yield from llm.stream(messages)


class OllamaProvider(BaseProvider):
    """
    Local LLM via Ollama.
    Ollama runs models locally — no API key required.
    Install from: https://ollama.com
    """

    name = "ollama"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def get_llm(self, tools: list[dict] | None = None) -> BaseChatModel:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=0,
        )
        if tools:
            return llm.bind_tools(tools)
        return llm

    def stream(
        self,
        messages: list[BaseMessage],
        tools: list[dict] | None = None,
    ) -> Iterator[Any]:
        llm = self.get_llm(tools=tools)
        yield from llm.stream(messages)


# ── Factory ──────────────────────────────────────────────────────────────────

PROVIDERS: dict[str, type[BaseProvider]] = {
    "groq":   GroqProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str, model: str | None = None) -> BaseProvider:
    """
    Instantiate a provider by name.

    Args:
        name:  "groq" or "ollama"
        model: Optional model name override.

    Raises:
        ValueError: If the provider name is unknown.
    """
    name = name.lower()
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(PROVIDERS)}"
        )
    return PROVIDERS[name](model=model)
