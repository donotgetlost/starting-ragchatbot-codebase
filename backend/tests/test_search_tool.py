# backend/tests/test_search_tool.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
    store.search.return_value = make_error(
        "Search error: Number of requested results 0 is less than 1"
    )

    tool = CourseSearchTool(store)
    result = tool.execute(query="what is python")

    # Should surface the error, not crash
    assert "Search error" in result
