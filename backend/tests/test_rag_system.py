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
    # Verify ChromaDB was actually called with n_results=0 — proving the root cause
    mock_collection.query.assert_called_once()
    actual_n_results = mock_collection.query.call_args.kwargs.get("n_results") or mock_collection.query.call_args[1].get("n_results")
    assert actual_n_results == 0, f"Expected n_results=0, got {actual_n_results}"


def test_no_session_history_when_no_session_id():
    system = make_rag_system()
    system.ai_generator.generate_response.return_value = "Answer"
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = []
    system.tool_manager.get_last_sources.return_value = []

    system.query("standalone question")

    system.session_manager.get_conversation_history.assert_not_called()
    system.session_manager.add_exchange.assert_not_called()
    call_kwargs = system.ai_generator.generate_response.call_args[1]
    assert call_kwargs["conversation_history"] is None
