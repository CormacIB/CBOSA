"""
Tests for Issue #20 — Task dataclass (shared core).

Behaviors verified through public interface only.
Task is a plain in-memory dataclass; no Qt, no database.
"""
from __future__ import annotations

from cbosa.core.task import Task


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: construction and default fields
# ---------------------------------------------------------------------------

def test_task_constructs_with_required_fields():
    task = Task(text="Send the report", source="email", source_id="msg-42")
    assert task.text == "Send the report"
    assert task.source == "email"
    assert task.source_id == "msg-42"


def test_due_date_defaults_to_none():
    task = Task(text="Review slides", source="note", source_id="note-1")
    assert task.due_date is None


def test_priority_defaults_to_none():
    task = Task(text="Review slides", source="note", source_id="note-1")
    assert task.priority is None


# ---------------------------------------------------------------------------
# Slice 2 — equality and inequality
# ---------------------------------------------------------------------------

def test_identical_tasks_are_equal():
    a = Task(text="Send report", source="email", source_id="msg-1")
    b = Task(text="Send report", source="email", source_id="msg-1")
    assert a == b


def test_tasks_with_different_text_are_not_equal():
    a = Task(text="Send report", source="email", source_id="msg-1")
    b = Task(text="Review report", source="email", source_id="msg-1")
    assert a != b


def test_tasks_with_different_source_are_not_equal():
    a = Task(text="Submit assignment", source="email", source_id="x-1")
    b = Task(text="Submit assignment", source="canvas", source_id="x-1")
    assert a != b


def test_tasks_with_different_optional_fields_are_not_equal():
    from datetime import datetime
    a = Task(text="Call back", source="email", source_id="msg-2", priority=1)
    b = Task(text="Call back", source="email", source_id="msg-2", priority=2)
    assert a != b


# ---------------------------------------------------------------------------
# Slice 3 — all three source string values are valid
# ---------------------------------------------------------------------------

def test_source_email_constructs():
    task = Task(text="Reply to Alice", source="email", source_id="msg-99")
    assert task.source == "email"


def test_source_canvas_constructs():
    task = Task(text="Submit essay", source="canvas", source_id="assignment-7")
    assert task.source == "canvas"


def test_source_note_constructs():
    task = Task(text="Add references", source="note", source_id="note-5")
    assert task.source == "note"
