# Demo & QA prompts for Needoh

## Before you run anything

1. **Open a terminal in the repository root** — the folder that contains `main.py`, `agent/`, `rag_server/`, and `README.md`  
   Example: `cd "C:\Users\...\needoh"` (not the parent `GenPro 2` folder unless you use `python needoh\main.py`).

2. **One-time RAG setup** (if not done yet):

   ```bash
   python rag_server/ingest.py
   ```

3. **`.env`** — no PowerShell pasted inside the file. Only `KEY=value` lines and `#` comments. If you see `python-dotenv could not parse line …`, open `.env` and remove stray `@"` / `Out-File` lines.

4. **Groq + tools:** Default is **`openai/gpt-oss-20b`** (reliable tool JSON). **413 TPM:** shorten history, lower `NEEDOH_TOOL_OUTPUT_MAX_CHARS`, or wait. **Llama 4 Scout** can hit **tool_use_failed** (wrong tool JSON shape). Avoid `llama-3.3-70b-versatile` for fragile tool JSON. Override via `DEFAULT_GROQ_MODEL` or `--model`.

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

### 1b) Parser question + marker file (Groq-safe — use instead of editing `main.py`)

**Prompt:**

> Read `main.py` and answer in chat: which CLI flag sets the LLM model name? Then use **write_file** only (not edit_file) to create `notes/video_demo.txt` with exactly two lines: line 1 is your one-sentence answer; line 2 is only `# video-demo`. Create folder `notes` first if needed.

**Expect:** `read_text_file` + maybe `create_directory` + `write_file`.

**Why:** Prompts like “add a comment inside `main.py`” tempt `edit_file` with huge multi-line JSON; Groq often returns **400 `Failed to parse tool call arguments as JSON`**.

---

### 2) Custom RAG MCP (`query_langchain_docs` + HyDE)

**Prompt (quick RAG):**

> Use the LangChain documentation tool only. In **three short bullet points**, what does the LangChain documentation say **Chroma** is used for as a **vector store**? Pull wording from retrieved chunks only.

**Expect:** `query_langchain_docs`.  
**Note:** The RAG server runs in a **separate Python process** from `main.py`, so it loads **sentence-transformers** again (ingest does not share that memory). First load in that process is often **30–90s** on CPU, then HyDE adds a short Groq call. **`RAG_WARMUP` defaults to on** so loading usually overlaps MCP startup. Set **`RAG_LOG_TIMING=true`** for `[needoh-rag timing]` on stderr. **`HYDE_ENABLED=false`** skips HyDE for a faster (weaker) demo.

**If you always get “No relevant documentation” or Chroma errors:** run once from repo root: `python rag_server/ingest.py` (needs network). The vector DB is stored under `rag_server/chroma_store/` by default (same path the MCP server uses even if your cwd changes).

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

### Task 1 — Read → write full file → verify (filesystem + shell)

**Prompt:**

> Read `agent/loop.py`. Add a new line directly under the module docstring that says `# demo: <today's date>`. Use **write_file** with the **entire** updated file contents (do not use edit_file). Then run `python -m py_compile agent/loop.py` and say if it succeeded.

**Expect:** read + `write_file` + `run_shell_command`.  
**Tip:** If the model still tries `edit_file` and Groq errors, say explicitly: “Use write_file only with the complete file.”

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
