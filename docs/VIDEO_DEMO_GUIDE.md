# Video demonstration guide (rubric-aligned)

Use this as a **shot list** while recording. Goal: graders see **two non-trivial autonomous tasks**, **three MCP families on screen** (filesystem, custom RAG, external), and **legible reasoning + tool calls**.

Full copy/paste prompts also live in [DEMO_TEST_PROMPTS.md](DEMO_TEST_PROMPTS.md).

---

## Before you hit Record

1. **Terminal:** Repo root (folder with `main.py`). Font **14–16px**, window **maximized**.
2. **Environment:** `.env` valid; `TAVILY_API_KEY` set if you want Tavily in the video (recommended for “external MCP”).
3. **RAG:** Run once if needed: `python rag_server/ingest.py` (first RAG query can be slow—do a dry run before recording).
4. **Command:** `python main.py --auto` keeps pacing smooth; optional: start **one** task in confirm mode to show `y`/`n`, then use `--auto` for the rest.
5. **Groq model:** Default is `openai/gpt-oss-20b` (reliable tool JSON). Avoid preview-only models during recording.

---

## What to show on camera (checklist)


| Rubric idea               | What to capture on screen                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Agent reasoning**       | Scroll so the model’s **plain-language plan/summary** is readable before/after tool bursts.                               |
| **Tool calls**            | **Tool name + arguments** visible (your UI’s tool panels / Rich output). Pause 1–2s on each important call.               |
| **Filesystem MCP**        | At least one of: `list_directory`, `read_file`, `write_file` / `edit_file`, or `run_shell_command`.                       |
| **Custom RAG MCP**        | `query_langchain_docs` (HyDE may add delay—say “waiting on RAG” if needed).                                               |
| **External MCP**          | `tavily-search` **or** Context7 (`resolve-library-id` + `query-docs`)—show **one** clearly; Tavily is easiest to narrate. |
| **Two non-trivial tasks** | Each task should chain **read → change or create → verify** (or **search → implement**), not a single one-line answer.    |


**“Three MCP servers” mapping:** graders usually expect **filesystem + RAG + (Tavily or Context7)**. Your config loads Tavily only if `TAVILY_API_KEY` is set—set it for the demo if possible.

---

## Suggested video structure (well-paced, ~8–15 min)

1. **Intro (30–45 s):** Your name, course, “Needoh CLI assistant,” repo folder visible (`cd` into project).
2. **Quick capability pass (2–4 min):** Run **one** simple prompt (Section A below) so **filesystem** tools appear—proves the stack works.
3. **Task 1 — Non-trivial (3–6 min):** Paste **Task 1** from Section B; let it run; narrate briefly what tools fired (read/edit/shell).
4. **Task 2 — Non-trivial (3–6 min):** Paste **Task 2**; ensure **Tavily** (or Context7) + **filesystem** show; mention **RAG** if you add the optional short RAG question between tasks.
5. **Outro (20–30 s):** One sentence: autonomous loop, MCP tools, Groq/Ollama optional mention.

**Pacing tips:** Don’t speed-run; **pause** on tool panels. If RAG takes long, cut edit dead air *only* after the tool name `query_langchain_docs` has been visible.

---

## Section A — Simple, fast prompts (warmup / proof of life)

Use **one** of these at the start so the video isn’t empty if Task 1 fails.

### A1 — Filesystem only (easiest)

> You are in the project root. List the files and folders here, then read `README.md` and quote the **first line only**.

*Expect:* `list_directory` + `read_file` (names may vary slightly).

### A2 — Parser question + marker file (Groq-safe)

> Read `main.py` and say which CLI flag sets the LLM model. Then use **write_file** only to create `notes/video_demo.txt` with two lines: (1) your one-sentence answer, (2) `# video-demo`. Create `notes/` if needed.

*Expect:* read + `write_file` (avoid `edit_file` on large `main.py` — Groq JSON errors).

### A3 — RAG only (can be slow)

> How do I create a custom LangChain tool with @tool decorator?

*Expect:* `query_langchain_docs`.

### A4 — Web only (needs `TAVILY_API_KEY`)

> Use web search: what is the latest stable Python 3.x **feature** release version as of today? One sentence + source.

*Expect:* `tavily-search`.

---

## Section B — Two non-trivial tasks (recommended for the rubric)

These match [DEMO_TEST_PROMPTS.md](DEMO_TEST_PROMPTS.md) **§B** and are realistic for a demo.

### Task 1 — Read → write full file → verify (filesystem + shell)

> Read `agent/loop.py`, add `# demo: <date>` under the module docstring, save using **write_file** with the **full** file (no edit_file), then run `python -m py_compile agent/loop.py` and report success or failure.

*Narration cue:* “Read, rewrite file with write_file, compile.”

### Task 2 — Web → new file (Tavily + filesystem)

> Search the web for a minimal Python `structlog` setup example. Create folder `examples` if needed and add `examples/structlog_minimal.py` with a short runnable example under 40 lines. One sentence on what you used from the web.

*Requires:* `TAVILY_API_KEY` in `.env`.

**Alternative if Tavily is unavailable** (still non-trivial, uses Context7 + filesystem):

> Use Context7: resolve the library id for `pydantic`, then query-docs for how to define a simple model with a string field. Create `examples/pydantic_minimal.py` with a tiny runnable example under 25 lines.

---

## Section C — Guarantee all three MCP types in one recording

If Task 2 used only Tavily, add **one short RAG question** between tasks (from A3), **or** use this combined-style prompt **once** (heavier, but covers everything):

> Using the LangChain docs tool only: explain what LCEL stands for in one sentence. Then search the web for the current year’s Python 3 feature release version (one sentence + source). Finally, create `notes/demo_note.txt` with those two answers as two lines.

*Expect:* `query_langchain_docs` + `tavily-search` + filesystem write.

---

## After recording

Put your link in [video_demo.md](video_demo.md) (YouTube unlisted, Drive, or course upload—whatever the rubric allows).

---

## Troubleshooting (don’t waste tape)


| Symptom                      | Quick fix                                                                             |
| ---------------------------- | ------------------------------------------------------------------------------------- |
| No Tavily tools              | Set `TAVILY_API_KEY`; restart Needoh.                                                 |
| RAG timeout / slow           | Pre-run one RAG query before recording; use `--auto`.                                 |
| `ModuleNotFoundError: agent` | `cd` to repo root (where `main.py` is).                                               |
| Groq 413 / TPM too low       | Lower `NEEDOH_TOOL_OUTPUT_MAX_CHARS`, use `/clear`, or wait ~60s. See [Groq limits](https://console.groq.com/docs). |
| Groq model error             | Set `DEFAULT_GROQ_MODEL=…` in `.env` or `/model …` per [Groq docs](https://console.groq.com/docs). |


