# Group Project 2 — submission checklist (Needoh)

Use this against the official rubric. Items marked **you** are manual (Git, Canvas, video).

## Repository & planning (10 pts)

| Requirement | Status |
|-------------|--------|
| GitHub repo link submitted | **you** |
| Commit history shows **planning before implementation** (early commits = docs/diagrams/specs) | **you** |
| Planning docs in repo ([docs/planning/architecture_v1.md](planning/architecture_v1.md), etc.) | Present |
| **State diagram** image in [docs/diagrams/](diagrams/README.md) | **you** — add PNGs per diagrams README |
| **Sequence diagrams** (≥2 scenarios, ≥3 end-to-end flows total per spec) | **you** — add PNGs |
| README with setup | [README.md](../README.md) |
| `requirements.txt` | [requirements.txt](../requirements.txt) |
| Clean, commented code | Review as a team |

## Agentic loop & architecture (20 pts)

| Requirement | Needoh implementation |
|---------------|------------------------|
| Autonomous loop: task → LLM → tools → results → repeat | [agent/loop.py](../agent/loop.py) |
| Modular layout (CLI / agent / MCP / UI / RAG server) | `agent/`, `mcpclient/`, `ui/`, `rag_server/` |
| Provider abstraction: **cloud + Ollama** | [agent/providers.py](../agent/providers.py) — Groq + Ollama |

## Tool calling & CLI (20 pts)

| Requirement | Needoh implementation |
|---------------|------------------------|
| Read / write / edit files (via filesystem MCP) | MCP tools + system prompt |
| Shell commands | `run_shell_command`, `change_directory` in [agent/tools.py](../agent/tools.py) |
| Search codebase | filesystem `search_files` / `grep` via shell |
| **Confirm** vs **auto** | default confirm; `--auto` and `/auto` |
| Tool calls visible in terminal | Rich panels in [ui/display.py](../ui/display.py) |
| Status during tools | `SpinnerContext` |
| Streaming-style assistant output | Word-chunk emit in `AgentLoop._emit_assistant_text` |

## MCP integration (20 pts)

| Server | Role |
|--------|------|
| `@modelcontextprotocol/server-filesystem` | [mcpclient/config.py](../mcpclient/config.py) |
| External (Tavily + Context7) | Same; Tavily skipped if `TAVILY_API_KEY` empty — **set key for full credit** |
| Tools loaded dynamically | [mcpclient/client.py](../mcpclient/client.py) |

## Custom RAG MCP + advanced technique (20 pts)

| Requirement | Implementation |
|-------------|------------------|
| Ingest once, persistent Chroma | [rag_server/ingest.py](../rag_server/ingest.py), `rag_server/chroma_store/` (gitignored) |
| Chunk, embed, store | ingest + [rag_server/retriever.py](../rag_server/retriever.py) |
| Advanced RAG | **HyDE** in retriever |
| MCP tool | `query_langchain_docs` in [rag_server/server.py](../rag_server/server.py) |

## Reflection & video (10 pts)

| Item | Location / action |
|------|-------------------|
| Written reflection (design, LLM comparison, HyDE insight, what you’d change) | [docs/reflection.md](reflection.md) — expand if needed |
| Original vs updated architecture diagram if design drifted | **you** + note in reflection |
| Video: 2 non-trivial tasks, 3 MCP servers visible | **you** — [video_demo.md](video_demo.md) |

## Hygiene

- Never commit `.env` (already in `.gitignore`).
- For the demo, ensure `TAVILY_API_KEY` is set so the external MCP is actually invoked on screen.
