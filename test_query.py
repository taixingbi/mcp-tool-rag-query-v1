"""Integration tests for RAG query pipeline."""
import pytest

from query import run_query


def test_run_query_returns_answer():
    """RAG pipeline returns a non-empty string response."""
    answer = run_query("What is this about?")
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0


def test_run_query_compensation_returns_grounded_answer():
    """When corpus has compensation data, answer should reference it or state no context."""
    answer = run_query("what compensation")
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0
    # Either cites salary/compensation from context, or states context lacks it
    has_salary_info = any(
        word in answer.lower() for word in ["salary", "compensation", "180", "240", "000"]
    )
    has_no_context = "does not" in answer.lower() or "no information" in answer.lower()
    assert has_salary_info or has_no_context


def test_run_query_visa_returns_grounded_answer():
    """When corpus has visa data, answer should reference it or state no context."""
    answer = run_query("what visa status")
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0
    has_visa_info = any(
        word in answer.lower() for word in ["visa", "h4", "ead", "sponsorship"]
    )
    has_no_context = "does not" in answer.lower() or "no information" in answer.lower()
    assert has_visa_info or has_no_context
