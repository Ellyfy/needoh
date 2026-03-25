# Needoh — Written Reflection

## 1. Design Decisions

### Why Groq?
Groq offers extremely fast inference (often 400–700 tokens/second on Llama 3 models)
compared to other providers. For an interactive coding assistant where the developer
is waiting on responses, latency matters enormously. The free tier is also generous
enough for development and demo use.

### Why HyDE for RAG?
Raw user queries for technical docs tend to be short and ambiguous
(e.g. "langchain memory agent"). Embedding that query directly often misses relevant
chunks that use different vocabulary. HyDE solves this by generating a full
hypothetical documentation paragraph first, which is much richer semantically and
lands closer to real documentation in vector space.

Reference: Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance Labels"
(ACL 2023). https://arxiv.org/abs/2212.10496

### Why MCP for tool integration?
MCP gives a clean separation between the agent core and its capabilities. Adding a
new tool or data source is just adding a new server config — the agentic loop never
needs to change. It also means tools can be reused across different agents in the future.

### Confirm vs Auto mode
Auto mode is powerful but risky — the agent can delete or overwrite files without
warning. Confirm mode (the default) gives the developer a chance to review every
tool call before it runs, which is important when working on unfamiliar codebases.

---

## 2. LLM Comparison: Same Task, Two Models

**Task used for comparison:**
> "Read main.py and add docstrings to every function that is missing one."

### Model A: `llama-3.3-70b-versatile` (Groq)
- **Speed:** ~420 tokens/sec — near-instant responses
- **Tool use accuracy:** Correctly identified which functions lacked docstrings,
  used read_file first before editing
- **Code quality:** Docstrings were accurate and followed Google style
- **Weaknesses:** Occasionally over-explained in the docstring body

### Model B: `llama3` (Ollama, local)
- **Speed:** ~18 tokens/sec — noticeably slower for long files
- **Tool use accuracy:** Also correct, but sometimes requested the same file twice
- **Code quality:** Docstrings were shorter and sometimes omitted Args/Returns
- **Weaknesses:** Less consistent formatting across functions

**Insight:** For an interactive coding assistant, Groq's speed advantage is
significant — waiting 30 seconds for a tool call response breaks the development
flow. For offline or privacy-sensitive work, Ollama is still a solid fallback.

---

## 3. Advanced RAG Analysis: HyDE Impact

**Without HyDE** (embedding raw query directly):
- Query: "how do I persist agent memory between sessions"
- Top result: chunk about in-memory buffer (not persistence)
- Relevance score: mediocre

**With HyDE** (embedding hypothetical answer):
- Hypothetical generated: "To persist agent memory between sessions in LangChain,
  you can use SQLiteEntityMemory or save the memory object to disk using pickle..."
- Top result: chunk about SQLiteEntityMemory and persistence patterns
- Relevance: directly on target

HyDE works best when the query vocabulary doesn't overlap well with the documentation
vocabulary. For very specific queries ("ChatGroq class constructor arguments") it
offers less improvement since the query itself is already dense enough.

---

## 4. What I Would Do Differently

- **Session persistence from the start** — adding it later required touching the
  conversation history logic in multiple places. It should have been built in.
- **Async MCP client from day one** — the MCP SDK is async-first and fighting that
  early on added complexity. Designing the whole system as async from the beginning
  would have been cleaner.
- **Smaller, more focused RAG chunks** — chunk size of 800 was sometimes too large,
  including irrelevant content around the key sentences. ~400 tokens with more overlap
  would likely improve retrieval precision.
- **Add eval metrics for RAG** — I measured retrieval quality manually. Using RAGAs
  or a small test set with ground-truth answers would give a more objective view of
  whether HyDE was actually helping.

---

## 5. Architecture Changes During Development

The original architecture (v1) had the tool dispatcher as a separate module that the
loop called into. During implementation, it became cleaner to handle MCP routing
directly in the loop (`client.call_tool`) and keep `tools.py` only for local tools
(shell). The local tool schemas are merged into the MCP tool list before being passed
to the LLM, so the model has a single unified view of all capabilities.

---

## 6. Architecture Evolution & Diagrams

### Planning vs Implementation

The original architecture (v1) outlined in `docs/planning/architecture_v1.md` proposed a separate Tool Dispatcher module. During implementation, we found it cleaner to handle MCP routing directly within the agentic loop (`agent/loop.py`), with local tools (like shell execution) merged into the MCP tool list before being passed to the LLM.

This simplification meant:
- **Fewer moving parts** — one unified interface instead of separate dispatcher
- **Clearer code flow** — tool routing logic lives in one place
- **Easier maintenance** — changes to tool handling don't span multiple files

### Visual Documentation

The following diagrams illustrate the final implemented architecture:

#### State Diagram
Located at `docs/diagrams/state_diagram.png`

Shows the complete state machine from user input through task completion, including both confirm and auto execution modes. Key insight: the "Awaiting Confirmation" state is only entered in confirm mode, creating two parallel execution paths.

#### Sequence Diagrams
Located at `docs/diagrams/`

Three scenarios demonstrating different aspects of the system:

1. **RAG Documentation Query** — demonstrates the HyDE retrieval process where the LLM generates a hypothetical answer, we embed it, then search the vector database for matching real documentation
2. **File Read and Edit** — shows the filesystem MCP server with the confirmation flow, illustrating how users can review changes before they're applied
3. **Web Search + Implementation** — displays autonomous multi-step reasoning: research via Tavily, synthesis of findings, and code generation

These diagrams proved invaluable during debugging, as they made it easy to trace exactly where in the flow issues were occurring.
