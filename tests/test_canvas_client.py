"""
Tests for Issue #10 — CanvasApiClient.

All HTTP is intercepted at the httpx transport layer.
No real network calls are made.
"""
from __future__ import annotations

import pytest
import httpx

from cbosa.modules.canvas_store import CanvasApiClient, CanvasApiError


# ---------------------------------------------------------------------------
# Mock transport helpers
# ---------------------------------------------------------------------------

class _MockTransport(httpx.BaseTransport):
    """Static route table: url_substring → (status_code, json_body)."""

    def __init__(self, routes: dict) -> None:
        self._routes = routes

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for fragment, (status, body) in self._routes.items():
            if fragment in url:
                return httpx.Response(status, json=body)
        return httpx.Response(404, json={"errors": [{"message": "not found"}]})


def _client(routes: dict) -> CanvasApiClient:
    transport = _MockTransport(routes)
    http = httpx.Client(transport=transport, base_url="https://canvas.example.com")
    return CanvasApiClient(http_client=http)


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: list_courses returns a list of dicts
# ---------------------------------------------------------------------------

def test_list_courses_returns_list():
    client = _client({
        "/api/v1/courses": (200, [
            {"id": 1, "name": "Biology 101", "enrollment_state": "active"},
        ])
    })
    courses = client.list_courses()
    assert isinstance(courses, list)
    assert len(courses) == 1


def test_list_courses_has_id_and_name():
    client = _client({
        "/api/v1/courses": (200, [
            {"id": 42, "name": "History 201", "enrollment_state": "active"},
        ])
    })
    course = client.list_courses()[0]
    assert course["id"] == 42
    assert course["name"] == "History 201"


# ---------------------------------------------------------------------------
# Slice 2 — list_assignments returns assignments with due dates
# ---------------------------------------------------------------------------

def test_list_assignments_returns_list():
    client = _client({
        "/api/v1/courses/1/assignments": (200, [
            {"id": 10, "name": "Lab Report 1", "due_at": "2026-06-01T23:59:00Z",
             "points_possible": 100.0},
        ])
    })
    assignments = client.list_assignments(course_id=1)
    assert isinstance(assignments, list)
    assert len(assignments) == 1


def test_list_assignments_has_required_fields():
    client = _client({
        "/api/v1/courses/5/assignments": (200, [
            {"id": 99, "name": "Essay", "due_at": "2026-07-15T23:59:00Z",
             "points_possible": 50.0},
        ])
    })
    a = client.list_assignments(course_id=5)[0]
    assert a["id"] == 99
    assert a["name"] == "Essay"
    assert a["due_at"] == "2026-07-15T23:59:00Z"
    assert a["points_possible"] == 50.0


def test_list_assignments_null_due_date_becomes_empty_string():
    """Assignments with null due_at are included with empty string."""
    client = _client({
        "/api/v1/courses/1/assignments": (200, [
            {"id": 5, "name": "Unscheduled", "due_at": None, "points_possible": 0.0},
        ])
    })
    a = client.list_assignments(course_id=1)[0]
    assert a["due_at"] == ""


# ---------------------------------------------------------------------------
# Slice 3 — list_submissions returns grade data
# ---------------------------------------------------------------------------

def test_list_submissions_returns_list():
    client = _client({
        "/api/v1/courses/1/students/submissions": (200, [
            {"assignment_id": 10, "score": 88.0, "grade": "B+",
             "workflow_state": "graded"},
        ])
    })
    subs = client.list_submissions(course_id=1)
    assert isinstance(subs, list)


def test_list_submissions_has_score_and_grade():
    client = _client({
        "/api/v1/courses/3/students/submissions": (200, [
            {"assignment_id": 7, "score": 95.0, "grade": "A",
             "workflow_state": "graded"},
        ])
    })
    sub = client.list_submissions(course_id=3)[0]
    assert sub["assignment_id"] == 7
    assert sub["score"] == 95.0
    assert sub["grade"] == "A"


def test_list_submissions_null_score_becomes_none():
    """Ungraded submissions have null score — returned as None."""
    client = _client({
        "/api/v1/courses/1/students/submissions": (200, [
            {"assignment_id": 2, "score": None, "grade": None,
             "workflow_state": "submitted"},
        ])
    })
    sub = client.list_submissions(course_id=1)[0]
    assert sub["score"] is None


# ---------------------------------------------------------------------------
# Slice 4 — list_files returns course file list
# ---------------------------------------------------------------------------

def test_list_files_returns_list():
    client = _client({
        "/api/v1/courses/1/files": (200, [
            {"id": 300, "display_name": "Syllabus.pdf",
             "url": "https://canvas.example.com/files/300", "size": 102400},
        ])
    })
    files = client.list_files(course_id=1)
    assert isinstance(files, list)
    assert len(files) == 1


def test_list_files_has_name_and_url():
    client = _client({
        "/api/v1/courses/2/files": (200, [
            {"id": 11, "display_name": "Week1.pptx",
             "url": "https://canvas.example.com/files/11", "size": 2048},
        ])
    })
    f = client.list_files(course_id=2)[0]
    assert f["name"] == "Week1.pptx"
    assert "files/11" in f["url"]


# ---------------------------------------------------------------------------
# Slice 5 — HTTP errors raise CanvasApiError
# ---------------------------------------------------------------------------

def test_http_401_raises_canvas_api_error():
    client = _client({
        "/api/v1/courses": (401, {"errors": [{"message": "Invalid access token"}]}),
    })
    with pytest.raises(CanvasApiError, match="401"):
        client.list_courses()


def test_http_404_raises_canvas_api_error():
    client = _client({
        "/api/v1/courses/999/assignments": (404, {"errors": [{"message": "not found"}]}),
    })
    with pytest.raises(CanvasApiError, match="404"):
        client.list_assignments(course_id=999)
