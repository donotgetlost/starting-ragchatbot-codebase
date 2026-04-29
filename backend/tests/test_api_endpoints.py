import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

def test_query_returns_answer_and_session_id(api_client):
    response = api_client.post("/api/query", json={"query": "What is Python?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Mocked AI answer."
    assert data["session_id"] == "session_1"
    assert isinstance(data["sources"], list)


def test_query_without_session_id_auto_creates_session(api_client, mock_rag_system):
    api_client.post("/api/query", json={"query": "Explain loops"})

    mock_rag_system.session_manager.create_session.assert_called_once()


def test_query_with_existing_session_id_reuses_it(api_client, mock_rag_system):
    api_client.post("/api/query", json={"query": "Explain loops", "session_id": "sess_abc"})

    mock_rag_system.session_manager.create_session.assert_not_called()
    mock_rag_system.query.assert_called_once_with("Explain loops", "sess_abc")


def test_query_returns_sources(api_client, mock_rag_system):
    mock_rag_system.query.return_value = (
        "Answer",
        [{"label": "Python 101 - Lesson 1", "url": "https://example.com/1"}],
    )

    response = api_client.post("/api/query", json={"query": "What is a list?"})

    data = response.json()
    assert len(data["sources"]) == 1
    assert data["sources"][0]["label"] == "Python 101 - Lesson 1"


def test_query_500_on_rag_exception(api_client, mock_rag_system):
    mock_rag_system.query.side_effect = RuntimeError("DB unavailable")

    response = api_client.post("/api/query", json={"query": "What is Python?"})

    assert response.status_code == 500
    assert "DB unavailable" in response.json()["detail"]


def test_query_requires_query_field(api_client):
    response = api_client.post("/api/query", json={})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

def test_delete_session_clears_history(api_client, mock_rag_system):
    response = api_client.delete("/api/session/sess_xyz")

    assert response.status_code == 200
    assert response.json() == {"status": "cleared"}
    mock_rag_system.session_manager.clear_session.assert_called_once_with("sess_xyz")


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

def test_courses_returns_stats(api_client, mock_rag_system):
    mock_rag_system.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python 101", "FastAPI Basics"],
    }

    response = api_client.get("/api/courses")

    assert response.status_code == 200
    data = response.json()
    assert data["total_courses"] == 2
    assert "Python 101" in data["course_titles"]
    assert "FastAPI Basics" in data["course_titles"]


def test_courses_500_on_analytics_exception(api_client, mock_rag_system):
    mock_rag_system.get_course_analytics.side_effect = RuntimeError("Analytics broken")

    response = api_client.get("/api/courses")

    assert response.status_code == 500
    assert "Analytics broken" in response.json()["detail"]
