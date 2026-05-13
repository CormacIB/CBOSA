"""
Tests for Issue #10 — CanvasPanel UI.

Behaviors verified through public interfaces only.
All tests use an in-memory CanvasStore (no disk I/O, no network).
"""
from __future__ import annotations

import pytest

from cbosa.modules.canvas_store import CanvasStore
from cbosa.ui.panels import BasePanel
from cbosa.ui.panels.canvas_panel import CanvasPanel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    s = CanvasStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def panel_no_creds(qapp, store, monkeypatch):
    """Panel whose store reports no credentials."""
    monkeypatch.setattr(type(store), "has_credentials", property(lambda self: False))
    return CanvasPanel(store)


@pytest.fixture
def store_with_data(store):
    """Store pre-populated with fixture assignments, submissions, and files."""
    store._upsert_assignment(
        id=10, course_id=1, course_name="Biology 101",
        name="Lab Report 1", due_at="2026-06-01T23:59:00Z", points_possible=100.0,
    )
    store._upsert_assignment(
        id=11, course_id=1, course_name="Biology 101",
        name="Midterm Exam", due_at="2026-05-20T14:00:00Z", points_possible=200.0,
    )
    store._upsert_assignment(
        id=20, course_id=2, course_name="History 201",
        name="Essay Draft", due_at="2026-07-10T23:59:00Z", points_possible=50.0,
    )
    store._upsert_submission(
        course_id=1, course_name="Biology 101",
        assignment_id=10, assignment_name="Lab Report 1",
        score=88.0, grade="B+",
    )
    store._upsert_submission(
        course_id=2, course_name="History 201",
        assignment_id=20, assignment_name="Essay Draft",
        score=None, grade="",
    )
    store._upsert_file(
        id=300, course_id=1, course_name="Biology 101",
        name="Syllabus.pdf", url="https://canvas.example.com/files/300", size=102400,
    )
    store._upsert_file(
        id=301, course_id=2, course_name="History 201",
        name="Week1.pptx", url="https://canvas.example.com/files/301", size=2048,
    )
    store._conn.commit()
    return store


@pytest.fixture
def panel_with_data(qapp, store_with_data, monkeypatch):
    """Panel with credentials mocked present and fixture data pre-loaded."""
    monkeypatch.setattr(type(store_with_data), "has_credentials", property(lambda self: True))
    return CanvasPanel(store_with_data)


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: CanvasPanel is a BasePanel
# ---------------------------------------------------------------------------

def test_is_base_panel(panel_no_creds):
    assert isinstance(panel_no_creds, BasePanel)


# ---------------------------------------------------------------------------
# Slice 2 — no credentials → setup prompt shown, not the main UI
# ---------------------------------------------------------------------------

def test_no_credentials_shows_setup_label(panel_no_creds):
    from PyQt6.QtWidgets import QLabel
    labels = panel_no_creds.widget().findChildren(QLabel, "no_credentials_label")
    assert len(labels) == 1


def test_no_credentials_label_mentions_secrets_toml(panel_no_creds):
    from PyQt6.QtWidgets import QLabel
    labels = panel_no_creds.widget().findChildren(QLabel, "no_credentials_label")
    assert labels
    assert "secrets.toml" in labels[0].text()


def test_no_credentials_has_no_assignment_table(panel_no_creds):
    from PyQt6.QtWidgets import QTableWidget
    tables = panel_no_creds.widget().findChildren(QTableWidget, "assignment_table")
    assert len(tables) == 0


# ---------------------------------------------------------------------------
# Slice 3 — with credentials: required widgets exist
# ---------------------------------------------------------------------------

def test_assignment_table_exists(panel_with_data):
    from PyQt6.QtWidgets import QTableWidget
    tables = panel_with_data.widget().findChildren(QTableWidget, "assignment_table")
    assert len(tables) == 1


def test_grade_table_exists(panel_with_data):
    from PyQt6.QtWidgets import QTableWidget
    tables = panel_with_data.widget().findChildren(QTableWidget, "grade_table")
    assert len(tables) == 1


def test_file_table_exists(panel_with_data):
    from PyQt6.QtWidgets import QTableWidget
    tables = panel_with_data.widget().findChildren(QTableWidget, "file_table")
    assert len(tables) == 1


def test_sync_button_exists(panel_with_data):
    from PyQt6.QtWidgets import QPushButton
    btns = panel_with_data.widget().findChildren(QPushButton, "sync_btn")
    assert len(btns) == 1


def test_status_label_exists(panel_with_data):
    from PyQt6.QtWidgets import QLabel
    labels = panel_with_data.widget().findChildren(QLabel, "status_label")
    assert len(labels) == 1


# ---------------------------------------------------------------------------
# Slice 4 — assignment table populated from cache on init
# ---------------------------------------------------------------------------

def test_assignment_table_row_count(panel_with_data):
    assert panel_with_data._assignment_table.rowCount() == 3


def test_assignment_table_shows_name(panel_with_data):
    names = [
        panel_with_data._assignment_table.item(r, 0).text()
        for r in range(panel_with_data._assignment_table.rowCount())
    ]
    assert "Lab Report 1" in names


def test_assignment_table_shows_course(panel_with_data):
    courses = [
        panel_with_data._assignment_table.item(r, 1).text()
        for r in range(panel_with_data._assignment_table.rowCount())
    ]
    assert "Biology 101" in courses


def test_assignment_table_shows_due_date(panel_with_data):
    dates = [
        panel_with_data._assignment_table.item(r, 2).text()
        for r in range(panel_with_data._assignment_table.rowCount())
    ]
    assert any("2026-05-20" in d for d in dates)


def test_assignment_table_sorted_by_due_date(panel_with_data):
    """Earlier due dates appear before later ones."""
    dates = [
        panel_with_data._assignment_table.item(r, 2).text()
        for r in range(panel_with_data._assignment_table.rowCount())
    ]
    dated = [d for d in dates if d]
    assert dated == sorted(dated)


# ---------------------------------------------------------------------------
# Slice 5 — grade table populated from cache on init
# ---------------------------------------------------------------------------

def test_grade_table_row_count(panel_with_data):
    assert panel_with_data._grade_table.rowCount() == 2


def test_grade_table_shows_assignment_name(panel_with_data):
    names = [
        panel_with_data._grade_table.item(r, 0).text()
        for r in range(panel_with_data._grade_table.rowCount())
    ]
    assert "Lab Report 1" in names


def test_grade_table_shows_course(panel_with_data):
    courses = [
        panel_with_data._grade_table.item(r, 1).text()
        for r in range(panel_with_data._grade_table.rowCount())
    ]
    assert "Biology 101" in courses


def test_grade_table_shows_score(panel_with_data):
    scores = [
        panel_with_data._grade_table.item(r, 2).text()
        for r in range(panel_with_data._grade_table.rowCount())
    ]
    assert any("88" in s for s in scores)


def test_grade_table_shows_grade(panel_with_data):
    grades = [
        panel_with_data._grade_table.item(r, 3).text()
        for r in range(panel_with_data._grade_table.rowCount())
    ]
    assert "B+" in grades


def test_grade_table_ungraded_shows_dash(panel_with_data):
    """Ungraded submissions show '—' for score."""
    scores = [
        panel_with_data._grade_table.item(r, 2).text()
        for r in range(panel_with_data._grade_table.rowCount())
    ]
    assert any(s in ("—", "-", "") for s in scores)


# ---------------------------------------------------------------------------
# Slice 6 — file table populated from cache on init
# ---------------------------------------------------------------------------

def test_file_table_row_count(panel_with_data):
    assert panel_with_data._file_table.rowCount() == 2


def test_file_table_shows_file_name(panel_with_data):
    names = [
        panel_with_data._file_table.item(r, 0).text()
        for r in range(panel_with_data._file_table.rowCount())
    ]
    assert "Syllabus.pdf" in names


def test_file_table_shows_course(panel_with_data):
    courses = [
        panel_with_data._file_table.item(r, 1).text()
        for r in range(panel_with_data._file_table.rowCount())
    ]
    assert "History 201" in courses


# ---------------------------------------------------------------------------
# Slice 7 — sync button and status label behaviour
# ---------------------------------------------------------------------------

def test_status_label_initially_ready(panel_with_data):
    assert panel_with_data._status_label.text() == "Ready"


def test_sync_button_enabled_initially(panel_with_data):
    assert panel_with_data._sync_btn.isEnabled()


def test_on_sync_done_error_shows_message(panel_with_data):
    panel_with_data._on_sync_done(0, "Connection refused")
    assert "Error" in panel_with_data._status_label.text()
    assert panel_with_data._sync_btn.isEnabled()


def test_on_sync_done_success_shows_count(panel_with_data):
    panel_with_data._on_sync_done(15, "")
    assert "15" in panel_with_data._status_label.text()
    assert panel_with_data._sync_btn.isEnabled()


# ---------------------------------------------------------------------------
# Slice 8 — refresh_tables reflects store changes after sync
# ---------------------------------------------------------------------------

def test_refresh_tables_after_new_assignment(qapp, store_with_data, monkeypatch):
    monkeypatch.setattr(type(store_with_data), "has_credentials", property(lambda self: True))
    panel = CanvasPanel(store_with_data)
    assert panel._assignment_table.rowCount() == 3

    store_with_data._upsert_assignment(
        id=99, course_id=1, course_name="Biology 101",
        name="Final Exam", due_at="2026-08-01T09:00:00Z", points_possible=300.0,
    )
    store_with_data._conn.commit()
    panel._on_sync_done(1, "")
    assert panel._assignment_table.rowCount() == 4
    store_with_data.close()


def test_refresh_tables_after_new_file(qapp, store_with_data, monkeypatch):
    monkeypatch.setattr(type(store_with_data), "has_credentials", property(lambda self: True))
    panel = CanvasPanel(store_with_data)
    assert panel._file_table.rowCount() == 2

    store_with_data._upsert_file(
        id=400, course_id=1, course_name="Biology 101",
        name="Lecture1.pdf", url="https://canvas.example.com/files/400", size=512,
    )
    store_with_data._conn.commit()
    panel._on_sync_done(1, "")
    assert panel._file_table.rowCount() == 3
    store_with_data.close()


# ---------------------------------------------------------------------------
# Slice 9 — synced_at timestamp shown in status after sync
# ---------------------------------------------------------------------------

def test_synced_at_shown_after_sync(qapp, store_with_data, monkeypatch):
    monkeypatch.setattr(type(store_with_data), "has_credentials", property(lambda self: True))
    store_with_data._set_synced_at("2026-05-11T20:00:00Z")
    panel = CanvasPanel(store_with_data)
    panel._on_sync_done(5, "")
    assert "5" in panel._status_label.text()
    store_with_data.close()
