# Video demonstration

**Step-by-step shot list, prompts, and pacing:** [VIDEO_DEMO_GUIDE.md](VIDEO_DEMO_GUIDE.md)

## Checklist (rubric)

Record a screen capture that clearly shows:

1. **Two non-trivial autonomous tasks** (e.g. multi-file refactor, add tests, fix a bug across files—not a one-line hello world).
2. **At least three MCP servers invoked on screen**, with tool panels visible:
   - `@modelcontextprotocol/server-filesystem` (e.g. `read_file`, `write_file`, `edit_file`)
   - **Custom RAG** (`query_langchain_docs`)
   - **External** (`tavily-search` and/or Context7 `query-docs`)
3. **Agent reasoning text** and **tool call boxes** legible for the grader.
4. Optional: show **confirm mode** (`y`/`n`) on at least one tool, then show **`--auto`** for a second task.

## After recording

Replace this section with your link:

- **Video URL:** _[YouTube unlisted / Google Drive / Canvas upload]_

## Suggested run command for demo

```bash
python main.py --auto
```

Use a clean terminal font size (14–16px) and maximize the window before recording.
