# Demo & QA prompts for Needoh

## Before you run anything

1. **Open a terminal in the repository root** — the folder that contains `main.py`, `agent/`, `rag_server/`, and `README.md`  
   Example: `cd "C:\Users\...\needoh"` (not the parent `GenPro 2` folder unless you use `python needoh\main.py`).

2. **One-time RAG setup** (if not done yet):

   ```bash
   python rag_server/ingest.py
   ```

3. **`.env`** — no PowerShell pasted inside the file. Only `KEY=value` lines and `#` comments. If you see `python-dotenv could not parse line …`, open `.env` and remove stray `@"` / `Out-File` lines.

4. **Groq + tools:** Avoid `llama-3.3-70b-versatile` for tool calling — it often returns XML like `<function=...>` and Groq responds with **400 `tool_use_failed`**. `llama-3.1-70b-versatile` was **decommissioned** by Groq. The project default is **`openai/gpt-oss-20b`**. Override via `DEFAULT_GROQ_MODEL` or `--model` (e.g. `llama-3.1-8b-instant`, `openai/gpt-oss-120b`).

5. **Run the assistant:**

   ```bash
   python main.py
   ```

   For demos without confirm prompts:

   ```bash
   python main.py --auto
   ```

6. **If you get `ModuleNotFoundError: No module named 'agent'`** — you are not in the repo root, or `main.py` was moved. `cd` to the folder that contains `main.py` and try again.

---

## A. Rubric coverage — prove each MCP server (copy/paste)

### 1) Filesystem MCP (sanity)

**Prompt:**

> You are in the project root. List the names of files and folders here, then read `README.md` and tell me the exact first line of text in that file.

**Expect (tool panel):** `list_directory`, `read_file`, or `read_text_file`.

**Tip:** On Windows, paths are often like `README.md` or `.\README.md` under the allowed root.

---

### 2) Custom RAG MCP (`query_langchain_docs` + HyDE)

**Prompt:**

> Use the LangChain documentation tool only. Question: How does LangChain `bind_tools` work on a chat model, and what is the typical pattern for an agent that calls tools in a loop? Answer using retrieved doc chunks.

**Expect:** `query_langchain_docs`.  
**Note:** First call can take **30–90+ seconds** (loads embeddings + HyDE LLM step). Later calls are faster.

---

### 3) External MCP — Tavily (web)

**Prompt:**

> Use web search. What is the latest stable Python 3.x feature release version number as of today? One sentence answer with a source.

**Expect:** `tavily-search` (sometimes `tavily-extract`).  
**Requires:** `TAVILY_API_KEY` in `.env`. If Tavily is skipped at startup, the key is missing or empty.

---

### 4) External MCP — Context7 (library docs)

**Prompt:**

> Use Context7: resolve the library id for `langchain`, then use query-docs to summarize how to install or get started with LangChain in Python (short bullet list).

**Expect:** `resolve-library-id` then `query-docs`.

---

## B. Two non-trivial tasks (strong video material)

### Task 1 — Read → edit → verify (filesystem + shell)

**Prompt:**

> Open `agent/loop.py`, add a new comment line directly under the module docstring that says `# demo: <today's date>`, then run `python -m py_compile agent/loop.py` and tell me if it succeeded.

**Expect:** filesystem read + `edit_file` or `write_file`, then `run_shell_command`.

---

### Task 2 — Web search → new file (Tavily + filesystem)

**Prompt:**

> Search the web for a minimal `structlog` Python setup example. Create a new folder `examples` if needed and add `examples/structlog_minimal.py` with a short runnable example (under 40 lines). Briefly cite what you used from the web.

**Expect:** `tavily-search` / `tavily-extract`, then `write_file` or `create_directory` + `write_file`.

---

### Task 3 — LangChain deep dive (RAG + optional filesystem)

**Prompt:**

> Using only `query_langchain_docs`, explain the difference between LCEL and a classic `LLMChain`. Then, if the answer mentions specific module names, create `notes/langchain_lcel_note.txt` with a 5-line summary.

**Expect:** `query_langchain_docs`; possibly filesystem writes.

---

## C. Provider comparison (for written reflection)

Run the **same** prompt under **Groq** and **Ollama**; note speed and tool-use quality.

```bash
python main.py --provider groq --model openai/gpt-oss-20b --auto
```

```bash
python main.py --provider ollama --model llama3 --auto
```

**Prompt:**

> Read `mcpclient/client.py` and summarize in exactly three bullets: what `NeedohMCPClient` does at startup, how it routes a tool call, and how it converts MCP tools for the LLM.

---

## D. Quick health checks

| Check | Command (from repo root) |
|-------|---------------------------|
| Imports | `python -c "from agent.loop import AgentLoop; print('ok')"` |
| Help | `python main.py --help` |
| Compile | `python -m compileall -q agent mcpclient ui main.py` |
| RAG path | `python -c "from mcpclient.config import _rag_server_path; print(_rag_server_path())"` — should print `...\rag_server\server.py` and file should exist |
| MCP + `.env` | Start `python main.py` and confirm four servers connect (or three if Tavily key empty) |

---

## E. Confirm mode demo (show `y` / `n`)

```bash
python main.py
```

**Prompt:**

> Read `requirements.txt` and tell me the first package listed.

When the tool panel appears, type **`y`** then Enter to approve, or **`n`** to skip.

---

## F. Questions to ask yourself before submitting

1. Does the **video** clearly show **filesystem**, **RAG** (`query_langchain_docs`), and **external** (Tavily or Context7) tool names in panels?  
2. Are **two tasks** clearly non-trivial (multi-step, not one-line answers)?  
3. Does **reflection** include **two LLMs on the same task** and a real note on **HyDE**?  
4. Are **state + sequence** diagram PNGs in `docs/diagrams/` with names matching `README.md`?  
5. Does **git history** show **planning/docs commits before** big implementation commits?  
6. Is **`.env` never committed** and **`.env.example` complete** for teammates?
