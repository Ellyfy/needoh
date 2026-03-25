# Needoh — Architecture v1 (Planning Document)

## Overview

Needoh is an autonomous CLI coding assistant. The developer types a task;
the agent reasons, acts on the filesystem, queries documentation and the web,
runs code, and iterates until the task is complete.

## Component Breakdown

### 1. CLI REPL (`needoh/main.py`)
- Entry point using `prompt_toolkit` for readline-style input
- Streaming Rich output so the user sees tokens as they arrive
- Slash commands: /help, /provider, /auto, /clear, /exit
- Two modes: **confirm** (ask before each tool execution) and **auto** (run freely)

### 2. Agentic Loop (`needoh/agent/loop.py`)
Core cycle:
```
User task
  → build messages list
  → call LLM with tools
  → if tool_calls in response → execute tools → append results → loop
  → if no tool_calls → print final answer → done
```
Continues until the model stops requesting tools or a max-iteration limit is hit.

### 3. Provider Abstraction (`needoh/agent/providers.py`)
Abstract base class `BaseProvider` with `chat()` method.
Implementations:
- `GroqProvider` — uses langchain-groq, default model: llama-3.3-70b-versatile
- `OllamaProvider` — uses langchain-ollama for local inference

Switch via CLI flag: `--provider groq` or `--provider ollama`

### 4. Tool Call Dispatcher (`needoh/agent/tools.py`)
Receives tool call requests from the LLM.
Routes each call to the correct MCP server.
Handles confirmation prompt in confirm mode.
Formats results back for the LLM.

### 5. MCP Client (`needoh/mcp/client.py`)
Connects to all configured MCP servers on startup.
Dynamically loads their tool schemas (name, description, input schema).
Exposes a unified `call_tool(server, tool_name, args)` interface.

### 6. MCP Server Config (`needoh/mcp/config.py`)
Defines connection details for each server:
- `filesystem` — stdio, @modelcontextprotocol/server-filesystem
- `tavily` — stdio, tavily-mcp
- `context7` — stdio, @upstash/context7-mcp
- `rag` — stdio, python rag_server/server.py

### 7. Rich Display (`needoh/ui/display.py`)
- `print_banner()` — Needoh logo on startup
- `print_tool_call(name, args)` — highlighted panel when a tool is invoked
- `print_tool_result(result)` — dimmed result panel
- `stream_response(generator)` — live streaming of LLM tokens
- Status spinners during tool execution

### 8. Custom RAG MCP Server (`rag_server/`)

#### Ingestion (`ingest.py`) — run once
1. Download LangChain documentation pages
2. Split into chunks using RecursiveCharacterTextSplitter (semantic-aware)
3. Embed with `sentence-transformers/all-MiniLM-L6-v2`
4. Store in ChromaDB at `./rag_server/chroma_store`

#### HyDE Retrieval (`retriever.py`)
Advanced RAG technique: Hypothetical Document Embeddings
1. Receive user query
2. Call LLM to generate a *hypothetical answer* to the query
3. Embed the hypothetical answer (not the raw query)
4. Search ChromaDB with that embedding
5. Return top-k real document chunks

**Why HyDE?** Short technical queries ("how do I use LCEL?") embed poorly compared
to a full hypothetical answer. HyDE bridges the semantic gap between query and docs.

#### MCP Server (`server.py`)
Exposes one tool: `query_langchain_docs(query: str) -> str`
The agent calls this whenever it needs LangChain API or usage information.

## Data Flow Diagram

```
User types task
      │
      ▼
 REPL (main.py)
      │
      ▼
 Agentic Loop
      │ builds system prompt + conversation history
      ▼
 LLM (Groq/Ollama) ◄──────────────────────────┐
      │                                         │
      │ returns tool_call                       │
      ▼                                         │
 Tool Dispatcher ──► MCP Client                 │
                          │                     │
                 ┌────────┼────────┐            │
                 ▼        ▼        ▼            │
            Filesystem  Tavily  Context7        │
                          │        │            │
                     RAG Server    │            │
                          │        │            │
                          └────────┘            │
                               │                │
                         tool results           │
                               └────────────────┘
                                   (next loop iteration)
```

## Technology Choices & Rationale

| Decision | Choice | Reason |
|---|---|---|
| LLM framework | LangChain | Mature tool-calling support, clean abstraction |
| Cloud provider | Groq | Fast inference, generous free tier, llama3 access |
| Local provider | Ollama | Easy local setup, model-agnostic |
| CLI rendering | Rich | Best-in-class terminal UI for Python |
| Input handling | prompt_toolkit | History, arrow keys, multiline support |
| MCP client | official mcp SDK | First-party, best compatibility |
| Vector DB | ChromaDB | Lightweight, local, no server needed |
| Embeddings | sentence-transformers | Free, fast, runs locally |
| Advanced RAG | HyDE | Best fit for technical doc queries |

## Open Questions / Future Work
- Session persistence (save/reload conversation history)
- Multi-file diff view before accepting edits
- VS Code extension
- Support for image attachments in prompts
