# Diagrams (submission)

The course requires **state** and **sequence** diagrams as image files.

## What to add here

Export PNG (or SVG) from Lucidchart, draw.io, or similar and place them in this folder:

| File (matches [README.md](../README.md) links) | Content |
|------------------------------------------------|---------|
| `State_Diagram.png` | UML state machine: Idle → processing → tool selection → confirmation (if any) → execution → streaming → done |
| `Sequence_Diagram_RAG_Query.png` | User → CLI → Agent → LLM → MCP client → **RAG server** → Chroma; include HyDE step |
| `Sequence_diagram_File_read_Edit.png` | User → CLI → Agent → LLM → **filesystem MCP**; show confirm prompt if using confirm mode |
| `Sequence_Diagram_web_search.png` | User → CLI → Agent → LLM → **Tavily** (or other external MCP) → filesystem / answer |

If your README image paths differ slightly, either rename files to match or update the README links once.

## If architecture changed during development

Keep the **original** planning diagram and add **`architecture_v2.png`** (or similar) plus a short note in [reflection.md](../reflection.md) explaining what changed and why.

## References

- [UML state machine diagrams (Lucidchart)](https://www.lucidchart.com/pages/tutorial/uml-state-machine-diagram)
- [UML sequence diagrams (Lucidchart)](https://www.lucidchart.com/pages/uml-sequence-diagram)
