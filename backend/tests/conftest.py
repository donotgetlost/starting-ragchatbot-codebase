"""
Shared pytest fixtures for the RAG chatbot test suite.

Usage in any test file:
    def test_something(mock_rag_system, api_client):
        ...
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List


# ---------------------------------------------------------------------------
# Fake config — reusable across unit and integration tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core component mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_config():
    """FakeConfig instance with safe test defaults."""
    return FakeConfig()


@pytest.fixture
def mock_vector_store():
    """Mocked VectorStore with sensible defaults."""
    store = MagicMock()
    store.search.return_value = MagicMock(
        documents=[], metadata=[], distances=[], error=None
    )
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    store.get_course_count.return_value = 0
    store.get_existing_course_titles.return_value = []
    return store


@pytest.fixture
def mock_ai_generator():
    """Mocked AIGenerator that returns a plain answer string."""
    gen = MagicMock()
    gen.generate_response.return_value = "Mocked AI answer."
    return gen


@pytest.fixture
def mock_session_manager():
    """Mocked SessionManager with a pre-seeded session."""
    sm = MagicMock()
    sm.create_session.return_value = "session_1"
    sm.get_conversation_history.return_value = None
    return sm


# ---------------------------------------------------------------------------
# RAGSystem mock — higher-level fixture combining the above
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system(mock_session_manager, mock_ai_generator, mock_vector_store):
    """
    Fully mocked RAGSystem suitable for API endpoint tests.

    Pre-configured return values:
    - query() → ("Mocked AI answer.", [])
    - get_course_analytics() → {total_courses: 0, course_titles: []}
    - session_manager.create_session() → "session_1"
    """
    rag = MagicMock()
    rag.session_manager = mock_session_manager
    rag.ai_generator = mock_ai_generator
    rag.vector_store = mock_vector_store
    rag.query.return_value = ("Mocked AI answer.", [])
    rag.get_course_analytics.return_value = {
        "total_courses": 0,
        "course_titles": [],
    }
    return rag


# ---------------------------------------------------------------------------
# Test FastAPI app factory — avoids static file mount from production app.py
# ---------------------------------------------------------------------------

def _build_test_app(rag_system) -> FastAPI:
    """Minimal FastAPI app mirroring production endpoints, safe for testing."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[dict]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        rag_system.session_manager.clear_session(session_id)
        return {"status": "cleared"}

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def api_client(mock_rag_system):
    """
    TestClient for the test FastAPI app, pre-wired to mock_rag_system.

    Use mock_rag_system fixture alongside this to inspect calls:
        def test_foo(api_client, mock_rag_system):
            api_client.post("/api/query", json={"query": "hi"})
            mock_rag_system.query.assert_called_once()
    """
    return TestClient(_build_test_app(mock_rag_system))
