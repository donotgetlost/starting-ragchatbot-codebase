# RAG Chatbot Diagnostic Test Suite — Design

**Date:** 2026-04-28  
**Symptom:** RAG chatbot returns "query failed" for content-related questions  
**Goal:** Unit tests (mocked) that isolate which component is broken, then fix it

---

## Architecture

Three test files, one per component layer. Each file mocks only the boundary it owns.

```
backend/tests/
  test_search_tool.py   — CourseSearchTool (mocks VectorStore)
  test_ai_generator.py  — AIGenerator (mocks anthropic.Anthropic client)
  test_rag_system.py    — RAGSystem (mocks AIGenerator + VectorStore + SessionManager)
```

No real ChromaDB, no real Anthropic API calls. Tests run offline and fast.

---

## test_search_tool.py

Mocks: `VectorStore` (injected directly into `CourseSearchTool.__init__`)

| # | Test | What it checks |
|---|------|----------------|
| 1 | Happy path | `search()` returns 2 docs → `execute()` returns formatted string with course title and lesson number |
| 2 | Empty results (no filter) | `search()` returns no docs → returns `"No relevant content found."` |
| 3 | Empty results (course filter) | returns `"No relevant content found in course 'X'."` |
| 4 | Search error | `SearchResults.error` is set → `execute()` returns the error string |
| 5 | Sources populated | after successful search, `tool.last_sources` contains correct `label` and `url` |
| 6 | MAX_RESULTS=0 regression | `VectorStore.search()` called with `n_results=0` → empty results path triggered |

---

## test_ai_generator.py

Mocks: `anthropic.Anthropic` (patched at import)

| # | Test | What it checks |
|---|------|----------------|
| 1 | Direct response | `stop_reason="end_turn"` → returns `content[0].text` directly |
| 2 | Tool use triggered | `stop_reason="tool_use"` → `tool_manager.execute_tool()` called with correct name and args |
| 3 | Tool result sent back | second API call includes tool result as a `user` message |
| 4 | Final response returned | second API call's text is the return value of `generate_response()` |
| 5 | No tools | when `tools=None`, API call contains no `tools` or `tool_choice` keys |

---

## test_rag_system.py

Mocks: `AIGenerator`, `VectorStore`, `SessionManager` (all injected via `RAGSystem.__init__` via config + monkey-patching)

| # | Test | What it checks |
|---|------|----------------|
| 1 | Full query flow | `query()` calls `generate_response()` with correct prompt, tools list, and tool_manager |
| 2 | Sources returned | sources from `ToolManager.get_last_sources()` returned alongside answer |
| 3 | Sources reset | `reset_sources()` called after each query so sources don't bleed across queries |
| 4 | Session history used | when `session_id` provided, `get_conversation_history()` called and passed to generator |
| 5 | Session history updated | `add_exchange()` called with query and response after successful query |
| 6 | MAX_RESULTS=0 regression | `config.MAX_RESULTS=0` → `search()` called with `n_results=0` → empty results — documents root cause of "query failed" |

---

## Known Root Cause

`config.py` line 23: `MAX_RESULTS: int = 0`

`VectorStore.search()` passes this directly to ChromaDB as `n_results`. ChromaDB raises an error or returns nothing when `n_results=0`, causing the tool to return empty results, which surfaces as "query failed" in the UI.

**Fix:** Change `MAX_RESULTS` to a sensible default (e.g., `5`).

---

## Test Infrastructure

- **Framework:** `pytest` + `unittest.mock`
- **No new dependencies** beyond what is already installed
- **Run command:** `cd backend && python -m pytest tests/ -v`
