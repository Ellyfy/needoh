# 🔩 Needoh — Autonomous CLI Coding Assistant

> *"Give it a task. Walk away."*

Needoh is an autonomous AI coding assistant that lives in your terminal. You describe a task in plain English; Needoh reasons about your codebase, reads and writes files, runs commands, searches the web, queries documentation, and keeps iterating until the job is done.

---

## Features

- **Agentic loop** — Needoh acts autonomously until the task is complete
- **Tool calling** — reads/writes files, runs shell commands, searches the web
- **MCP client** — connects to multiple MCP servers and loads tools dynamically
- **Provider abstraction** — swap between Groq (cloud) and Ollama (local) via a flag
- **Confirm / auto mode** — choose whether Needoh asks before executing commands
- **Custom RAG server** — queries LangChain docs via HyDE-enhanced retrieval
- **Streaming output** — live token-by-token responses with Rich UI

---

## Architecture

```
Developer → Needoh CLI (REPL)
               ↓
         Agentic Loop
         ┌─────────────────────────────────┐
         │ Task → LLM → Tool calls → Result│
         │         ↑______________________│
         └─────────────────────────────────┘
               ↓                    ↓
      Provider Abstraction     MCP Client
      ┌──────────────┐    ┌──────────────────────────┐
      │ Groq │ Ollama│    │ Filesystem │ Tavily │ C7  │
      └──────────────┘    │       RAG Server          │
                          └──────────────────────────┘
```

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/yourname/needoh.git
cd needoh
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Node.js MCP servers

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

### 3. Configure environment

```bash
cp .env.example .env
# Fill in your API keys
```

### 4. Ingest LangChain docs (one-time setup)

```bash
python rag_server/ingest.py
```

This downloads and embeds the LangChain documentation into a local ChromaDB vector store. Only needs to be run once.

### 5. Run Needoh

```bash
# Default (Groq, confirm mode)
python -m needoh.main

# Use Ollama
python -m needoh.main --provider ollama --model llama3

# Auto-execute mode (no confirmation prompts)
python -m needoh.main --auto
```

---

## Usage

```
⚙  needoh v0.1.0
Type your task, or /help for commands.

> refactor the auth module to use JWT instead of sessions
> write unit tests for utils/parser.py
> find all TODO comments in this codebase and create a GitHub issues list
```

### Slash commands

| Command | Description |
|---|---|
| `/help` | Show available commands |
| `/provider groq\|ollama` | Switch LLM provider |
| `/auto` | Toggle auto-execute mode |
| `/clear` | Clear conversation history |
| `/exit` | Quit Needoh |

---

## MCP Servers

| Server | Purpose |
|---|---|
| `@modelcontextprotocol/server-filesystem` | Read, write, list files on your machine |
| Tavily MCP | Live web search |
| Context7 MCP | Library documentation lookup |
| Custom RAG server | LangChain docs via HyDE retrieval |

---

## Advanced RAG: HyDE

The custom RAG server uses **Hypothetical Document Embeddings (HyDE)**. Instead of embedding the raw user query, Needoh first generates a *hypothetical answer* using the LLM, then embeds that to search the vector DB. This dramatically improves retrieval quality for technical documentation.

```
Query: "how do I add memory to a LangChain agent?"
  ↓ LLM generates hypothetical answer
"To add memory to a LangChain agent, use ConversationBufferMemory..."
  ↓ Embed hypothetical doc
  ↓ Search ChromaDB → return real matching chunks
```

---

## Project Structure

```
needoh/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── architecture_v1.md
│   └── reflection.md
├── needoh/
│   ├── main.py              # CLI entrypoint & REPL
│   ├── agent/
│   │   ├── loop.py          # Agentic loop
│   │   ├── providers.py     # LLM provider abstraction
│   │   └── tools.py         # Tool call dispatcher
│   ├── mcp/
│   │   ├── client.py        # MCP client
│   │   └── config.py        # Server configurations
│   └── ui/
│       └── display.py       # Rich terminal rendering
└── rag_server/
    ├── server.py            # MCP RAG server
    ├── ingest.py            # One-time doc ingestion
    ├── retriever.py         # HyDE retrieval logic
    └── chroma_store/        # Persisted vector DB (gitignored)
```

---

## Requirements

- Python 3.11+
- Node.js 18+ (for filesystem MCP server)
- A Groq API key (free tier available at console.groq.com)
- Optional: Ollama installed locally for offline use

## Architecture & Design
## System Overview
For detailed architecture and planning information, refer to docs/planning/architecture_v1.md

## State Diagram
The state diagram represents how Needoh progresses through its core operational stages:

* Idle – waiting for user input
* Processing Task – the LLM analyzes the request using conversation context
* Tool Selection – the system determines which tools are required
* Awaiting Confirmation – user approval step (only in confirm mode)
* Tool Execution – execution of MCP tools such as filesystem, RAG, and web search
* Displaying Results – streaming the generated response back to the user
*Task Complete – final output delivered, system ready for the next request
## Sequence Diagram
1. RAG Documentation Query
This diagram demonstrates how Needoh retrieves and processes documentation using a custom RAG pipeline enhanced with HyDE to improve retrieval accuracy.
![RAG Sequence](docs/diagrams/sequence_diagram_rag.png)
2. File Read and Edit
This sequence illustrates how the system interacts with the filesystem via MCP, including the confirmation step when operating in confirm mode.
![File Edit Sequence](docs/diagrams/sequence_diagram_file_edit.png)
3. Web Search and Implementation
This diagram shows how Needoh performs web-based research using Tavily and then generates code based on the gathered information.
![Web Search Sequence](docs/diagrams/sequence_diagram_web_search.png)