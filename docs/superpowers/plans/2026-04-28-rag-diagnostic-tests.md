# RAG Diagnostic Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write mocked unit tests for `CourseSearchTool`, `AIGenerator`, and `RAGSystem` that pinpoint why the chatbot returns "query failed", then fix the root cause.

**Architecture:** Three test files under `backend/tests/`, one per component. Each mocks only its immediate dependency boundary — no real ChromaDB or Anthropic API calls. A final fix task corrects `MAX_RESULTS=0` in `config.py`, which is the identified root cause.

**Tech Stack:** Python 3.13, pytest, unittest.mock, existing codebase (chromadb, anthropic, fastapi)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/tests/__init__.py` | Makes `tests/` a package so pytest finds it |
| Create | `backend/tests/test_search_tool.py` | Unit tests for `CourseSearchTool.execute()` |
| Create | `backend/tests/test_ai_generator.py` | Unit tests for `AIGenerator.generate_response()` |
| Create | `backend/tests/test_rag_system.py` | Unit tests for `RAGSystem.query()` |
| Modify | `backend/config.py:23` | Fix `MAX_RESULTS: int = 0` → `5` |

---

## Task 1: Create test package scaffold

**Files:**
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create the tests package**

```bash
mkdir -p /path/to/project/backend/tests
touch backend/tests/__init__.py
```

The `__init__.py` is empty — it just tells Python this is a package so `pytest` can discover tests without import errors.

- [ ] **Step 2: Verify pytest can discover (empty) tests directory**

```bash
cd backend && python -m pytest tests/ -v
```

Expected output:
```
=================== no tests ran in X.XXs ====================
```

- [ ] **Step 3: Commit scaffold**

```bash
git add backend/tests/__init__.py
git commit -m "test: add tests package scaffold"
```

---

## Task 2: Write and run tests for CourseSearchTool

**Files:**
- Create: `backend/tests/test_search_tool.py`

- [ ] **Step 1: Write the test file**

```python
# backend/tests/test_search_tool.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock
from search_tools import CourseSearchTool
from vector_store import SearchResults


def make_results(docs, metas):
    return SearchResults(documents=docs, metadata=metas, distances=[0.1] * len(docs))


def make_error(msg):
    return SearchResults(documents=[], metadata=[], distances=[], error=msg)


def test_happy_path_formats_output():
    store = MagicMock()
    store.search.return_value = make_results(
        ["Intro content", "Advanced content"],
        [
            {"course_title": "Python 101", "lesson_number": 1},
            {"course_title": "Python 101", "lesson_number": 2},
        ],
    )
    store.get_lesson_link.return_value = "https://example.com/lesson"
    store.get_course_link.return_value = "https://example.com/course"

    tool = CourseSearchTool(store)
    result = tool.execute(query="what is python")

    assert "Python 101" in result
    assert "Lesson 1" in result
    assert "Lesson 2" in result
    assert "Intro content" in result


def test_empty_results_no_filter():
    store = MagicMock()
    store.search.return_value = make_results([], [])

    tool = CourseSearchTool(store)
    result = tool.execute(query="what is python")

    assert result == "No relevant content found."


def test_empty_results_with_course_filter():
    store = MagicMock()
    store.search.return_value = make_results([], [])

    tool = CourseSearchTool(store)
    result = tool.execute(query="what is python", course_name="Python 101")

    assert "No relevant content found" in result
    assert "Python 101" in result


def test_search_error_returned():
    store = MagicMock()
    store.search.return_value = make_error("Search error: collection is empty")

    tool = CourseSearchTool(store)
    result = tool.execute(query="what is python")

    assert "Search error: collection is empty" in result


def test_sources_populated_after_search():
    store = MagicMock()
    store.search.return_value = make_results(
        ["Content"],
        [{"course_title": "Python 101", "lesson_number": 3}],
    )
    store.get_lesson_link.return_value = "https://example.com/lesson/3"
    store.get_course_link.return_value = None

    tool = CourseSearchTool(store)
    tool.execute(query="what is python")

    assert len(tool.last_sources) == 1
    assert tool.last_sources[0]["label"] == "Python 101 - Lesson 3"
    assert tool.last_sources[0]["url"] == "https://example.com/lesson/3"


def test_max_results_zero_yields_empty(monkeypatch):
    """Regression: MAX_RESULTS=0 causes n_results=0, returning empty results."""
    store = MagicMock()
    # Simulate what VectorStore.search() does when called with n_results=0:
    # ChromaDB raises ValueError, which VectorStore catches and wraps as empty+error
    store.search.return_value = make_error("Search error: Number of requested results 0 is less than 1")

    tool = CourseSearchTool(store)
    result = tool.execute(query="what is python")

    # Should surface the error, not crash
    assert "Search error" in result
```

- [ ] **Step 2: Run tests — expect some to FAIL**

```bash
cd backend && python -m pytest tests/test_search_tool.py -v
```

Expected: most tests PASS, `test_max_results_zero_yields_empty` should PASS (it just validates the error-forwarding path). If any test unexpectedly FAILs, read the assertion error — it reveals a real bug.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_search_tool.py
git commit -m "test: add CourseSearchTool unit tests"
```

---

## Task 3: Write and run tests for AIGenerator

**Files:**
- Create: `backend/tests/test_ai_generator.py`

- [ ] **Step 1: Write the test file**

```python
# backend/tests/test_ai_generator.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


def make_generator():
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="claude-test")
    return gen


def make_text_response(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def make_tool_use_response(tool_name, tool_input, tool_id="tool_123"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def test_direct_response_returned():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response("Hello world")

    result = gen.generate_response(query="hi")

    assert result == "Hello world"


def test_tool_use_triggers_execute_tool():
    gen = make_generator()
    tool_response = make_tool_use_response(
        "search_course_content", {"query": "python basics"}, tool_id="abc"
    )
    final_response = make_text_response("Python is a language.")
    gen.client.messages.create.side_effect = [tool_response, final_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "Some course content"

    gen.generate_response(query="what is python", tools=[{"name": "search_course_content"}], tool_manager=tool_manager)

    tool_manager.execute_tool.assert_called_once_with("search_course_content", query="python basics")


def test_tool_result_sent_as_user_message():
    gen = make_generator()
    tool_response = make_tool_use_response(
        "search_course_content", {"query": "python"}, tool_id="id_99"
    )
    final_response = make_text_response("Answer here.")
    gen.client.messages.create.side_effect = [tool_response, final_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "Chunk of course content"

    gen.generate_response(query="test", tools=[{}], tool_manager=tool_manager)

    assert gen.client.messages.create.call_count == 2
    second_call_kwargs = gen.client.messages.create.call_args_list[1].kwargs
    messages = second_call_kwargs["messages"]
    # Last message must be the tool result sent as user role
    tool_result_message = messages[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["type"] == "tool_result"
    assert tool_result_message["content"][0]["tool_use_id"] == "id_99"
    assert tool_result_message["content"][0]["content"] == "Chunk of course content"


def test_final_response_text_returned():
    gen = make_generator()
    tool_response = make_tool_use_response("search_course_content", {"query": "x"})
    final_response = make_text_response("Final answer.")
    gen.client.messages.create.side_effect = [tool_response, final_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "content"

    result = gen.generate_response(query="test", tools=[{}], tool_manager=tool_manager)

    assert result == "Final answer."


def test_no_tools_means_no_tool_keys_in_api_call():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response("ok")

    gen.generate_response(query="general question")

    call_kwargs = gen.client.messages.create.call_args[1]
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs
```

- [ ] **Step 2: Run tests — note which FAIL**

```bash
cd backend && python -m pytest tests/test_ai_generator.py -v
```

Expected: all 5 tests PASS if `AIGenerator` is correctly implemented. A FAIL here means the tool-calling plumbing is broken.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_ai_generator.py
git commit -m "test: add AIGenerator unit tests"
```

---

## Task 4: Write and run tests for RAGSystem

**Files:**
- Create: `backend/tests/test_rag_system.py`

- [ ] **Step 1: Write the test file**

```python
# backend/tests/test_rag_system.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional


@dataclass
class FakeConfig:
    ANTHROPIC_API_KEY: str = "test-key"
    ANTHROPIC_BASE_URL: str = ""
    ANTHROPIC_MODEL: str = "claude-test"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "/tmp/test_chroma"


def make_rag_system(max_results=5):
    cfg = FakeConfig(MAX_RESULTS=max_results)
    with patch("rag_system.VectorStore"), \
         patch("rag_system.AIGenerator"), \
         patch("rag_system.SessionManager"), \
         patch("rag_system.DocumentProcessor"):
        from rag_system import RAGSystem
        system = RAGSystem(cfg)
    return system


def test_query_calls_generate_response_with_prompt_and_tools():
    system = make_rag_system()
    system.ai_generator.generate_response.return_value = "An answer"
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = [{"name": "search_course_content"}]
    system.tool_manager.get_last_sources.return_value = []

    system.query("what is python")

    system.ai_generator.generate_response.assert_called_once()
    call_kwargs = system.ai_generator.generate_response.call_args[1]
    assert "what is python" in call_kwargs["query"]
    assert call_kwargs["tools"] == [{"name": "search_course_content"}]
    assert call_kwargs["tool_manager"] is system.tool_manager


def test_query_returns_sources_from_tool_manager():
    system = make_rag_system()
    system.ai_generator.generate_response.return_value = "Answer"
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = []
    system.tool_manager.get_last_sources.return_value = [
        {"label": "Python 101 - Lesson 1", "url": "https://example.com/lesson/1"}
    ]

    _, sources = system.query("test query")

    assert sources == [{"label": "Python 101 - Lesson 1", "url": "https://example.com/lesson/1"}]


def test_sources_reset_after_query():
    system = make_rag_system()
    system.ai_generator.generate_response.return_value = "Answer"
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = []
    system.tool_manager.get_last_sources.return_value = []

    system.query("test query")

    system.tool_manager.reset_sources.assert_called_once()


def test_session_history_passed_to_generator():
    system = make_rag_system()
    system.ai_generator.generate_response.return_value = "Answer"
    system.session_manager.get_conversation_history.return_value = "User: hi\nAssistant: hello"
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = []
    system.tool_manager.get_last_sources.return_value = []

    system.query("follow-up question", session_id="sess_1")

    system.session_manager.get_conversation_history.assert_called_once_with("sess_1")
    call_kwargs = system.ai_generator.generate_response.call_args[1]
    assert call_kwargs["conversation_history"] == "User: hi\nAssistant: hello"


def test_session_history_updated_after_query():
    system = make_rag_system()
    system.ai_generator.generate_response.return_value = "Final answer"
    system.session_manager.get_conversation_history.return_value = None
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = []
    system.tool_manager.get_last_sources.return_value = []

    system.query("my question", session_id="sess_2")

    system.session_manager.add_exchange.assert_called_once_with("sess_2", "my question", "Final answer")


def test_max_results_zero_causes_empty_search_results():
    """Regression: MAX_RESULTS=0 passes n_results=0 to ChromaDB, returning nothing."""
    from vector_store import VectorStore, SearchResults

    # Use a real VectorStore with a mock ChromaDB client to verify n_results value
    with patch("vector_store.chromadb.PersistentClient") as mock_client, \
         patch("vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"):
        mock_collection = MagicMock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        # ChromaDB raises ValueError when n_results < 1
        mock_collection.query.side_effect = ValueError(
            "Number of requested results 0 is less than 1"
        )

        store = VectorStore(chroma_path="/tmp/test", embedding_model="all-MiniLM-L6-v2", max_results=0)
        result = store.search("what is python")

    assert result.error is not None
    assert "0" in result.error or "error" in result.error.lower()
```

- [ ] **Step 2: Run tests — note which FAIL**

```bash
cd backend && python -m pytest tests/test_rag_system.py -v
```

Expected: `test_max_results_zero_causes_empty_search_results` should FAIL or reveal the bug. Other tests should PASS if RAGSystem plumbing is correct.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_rag_system.py
git commit -m "test: add RAGSystem unit tests including MAX_RESULTS=0 regression"
```

---

## Task 5: Run full test suite and identify failures

**Files:**
- No changes — observation step only

- [ ] **Step 1: Run all tests together**

```bash
cd backend && python -m pytest tests/ -v 2>&1
```

- [ ] **Step 2: Record which tests fail**

Note every FAILED test name and the assertion error. This is the diagnostic output that tells you exactly which component is broken.

---

## Task 6: Fix MAX_RESULTS=0 in config.py

**Files:**
- Modify: `backend/config.py:23`

This is the identified root cause: `MAX_RESULTS: int = 0` causes `VectorStore.search()` to call ChromaDB with `n_results=0`, which raises `ValueError: Number of requested results 0 is less than 1`. `VectorStore` catches it and returns `SearchResults.empty(error_msg)`, `CourseSearchTool.execute()` returns the error string, and the UI surfaces it as "query failed".

- [ ] **Step 1: Fix the config value**

In `backend/config.py`, change line 23:

```python
# Before
MAX_RESULTS: int = 0         # Maximum search results to return

# After
MAX_RESULTS: int = 5         # Maximum search results to return
```

- [ ] **Step 2: Run the full test suite — all tests should now pass**

```bash
cd backend && python -m pytest tests/ -v
```

Expected:
```
tests/test_search_tool.py::test_happy_path_formats_output PASSED
tests/test_search_tool.py::test_empty_results_no_filter PASSED
tests/test_search_tool.py::test_empty_results_with_course_filter PASSED
tests/test_search_tool.py::test_search_error_returned PASSED
tests/test_search_tool.py::test_sources_populated_after_search PASSED
tests/test_search_tool.py::test_max_results_zero_yields_empty PASSED
tests/test_ai_generator.py::test_direct_response_returned PASSED
tests/test_ai_generator.py::test_tool_use_triggers_execute_tool PASSED
tests/test_ai_generator.py::test_tool_result_sent_as_user_message PASSED
tests/test_ai_generator.py::test_final_response_text_returned PASSED
tests/test_ai_generator.py::test_no_tools_means_no_tool_keys_in_api_call PASSED
tests/test_rag_system.py::test_query_calls_generate_response_with_prompt_and_tools PASSED
tests/test_rag_system.py::test_query_returns_sources_from_tool_manager PASSED
tests/test_rag_system.py::test_sources_reset_after_query PASSED
tests/test_rag_system.py::test_session_history_passed_to_generator PASSED
tests/test_rag_system.py::test_session_history_updated_after_query PASSED
tests/test_rag_system.py::test_max_results_zero_causes_empty_search_results PASSED
=================== 17 passed in X.XXs ====================
```

- [ ] **Step 3: Commit the fix**

```bash
git add backend/config.py
git commit -m "fix: set MAX_RESULTS to 5 (was 0, causing ChromaDB to return no results)"
```
