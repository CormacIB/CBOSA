"""
Tests for Issue #11 — CapturePanel UI.

Behaviors verified through public interfaces only.
All tests use temp NoteStore dirs and injected CaptureEngine fakes.
No real network, yt-dlp, or pypdf calls are made.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cbosa.modules.capture_engine import CaptureEngine, CaptureResult, CaptureFetchError
from cbosa.core.note_store import NoteStore
from cbosa.ui.panels import BasePanel
from cbosa.ui.panels.capture_panel import CapturePanel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def captures_store(tmp_path):
    return NoteStore(tmp_path / "captures")


@pytest.fixture
def all_notes_store(tmp_path):
    store = NoteStore(tmp_path / "notes")
    store.create("Python Programming", "Code and algorithms")
    store.create("Machine Learning", "ML algorithms")
    return store


@pytest.fixture
def engine():
    """CaptureEngine with no-op external dependencies."""
    return CaptureEngine(
        ydl_extract_fn=lambda url: {"title": "Fake Video", "description": "Desc", "transcript": ""},
        pdf_text_fn=lambda path: "Fake PDF text",
    )


@pytest.fixture
def panel(qapp, captures_store, engine):
    return CapturePanel(engine, captures_store)


@pytest.fixture
def panel_with_notes(qapp, captures_store, all_notes_store, engine):
    return CapturePanel(engine, captures_store, all_notes_store=all_notes_store)


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: CapturePanel is a BasePanel
# ---------------------------------------------------------------------------

def test_capture_panel_is_base_panel(panel):
    assert isinstance(panel, BasePanel)


# ---------------------------------------------------------------------------
# Slice 2 — required widgets exist
# ---------------------------------------------------------------------------

def test_url_input_exists(panel):
    from PyQt6.QtWidgets import QLineEdit
    inputs = panel.widget().findChildren(QLineEdit, "url_input")
    assert len(inputs) == 1


def test_capture_button_exists(panel):
    from PyQt6.QtWidgets import QPushButton
    btns = panel.widget().findChildren(QPushButton, "capture_btn")
    assert len(btns) == 1


def test_status_label_exists(panel):
    from PyQt6.QtWidgets import QLabel
    labels = panel.widget().findChildren(QLabel, "status_label")
    assert len(labels) == 1


# ---------------------------------------------------------------------------
# Slice 3 — initial state
# ---------------------------------------------------------------------------

def test_status_label_initially_ready(panel):
    assert panel._status_label.text() == "Ready"


def test_capture_button_enabled_initially(panel):
    assert panel._capture_btn.isEnabled()


def test_suggestions_widget_hidden_initially(panel):
    assert panel._suggestions_widget.isHidden()


# ---------------------------------------------------------------------------
# Slice 4 — error path: _on_capture_error updates status
# ---------------------------------------------------------------------------

def test_on_capture_error_shows_error_in_status(panel):
    panel._on_capture_error("Connection refused")
    assert "Error" in panel._status_label.text()
    assert "Connection refused" in panel._status_label.text()


def test_on_capture_error_re_enables_button(panel):
    panel._capture_btn.setEnabled(False)
    panel._on_capture_error("Some error")
    assert panel._capture_btn.isEnabled()


# ---------------------------------------------------------------------------
# Slice 5 — success path: _on_capture_done updates status and shows notes
# ---------------------------------------------------------------------------

def test_on_capture_done_no_suggestions_widget_stays_hidden(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="My Article",
        content="Some content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._on_capture_done(note_name, [])
    assert not panel._suggestions_widget.isVisible()


def test_on_capture_done_with_suggestions_shows_widget(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="My Article",
        content="Some content about Python Programming.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._on_capture_done(note_name, ["Python Programming"])
    assert not panel._suggestions_widget.isHidden()


# ---------------------------------------------------------------------------
# Slice 6 — suggestion rows have accept and reject buttons
# ---------------------------------------------------------------------------

def test_suggestion_rows_have_accept_button(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Content about Machine Learning techniques.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._on_capture_done(note_name, ["Machine Learning"])
    from PyQt6.QtWidgets import QPushButton
    accept_btns = panel._suggestions_widget.findChildren(
        QPushButton, "accept_Machine Learning"
    )
    assert len(accept_btns) == 1


def test_suggestion_rows_have_reject_button(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Content about Machine Learning techniques.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._on_capture_done(note_name, ["Machine Learning"])
    from PyQt6.QtWidgets import QPushButton
    reject_btns = panel._suggestions_widget.findChildren(
        QPushButton, "reject_Machine Learning"
    )
    assert len(reject_btns) == 1


# ---------------------------------------------------------------------------
# Slice 7 — accepting a suggestion adds wikilink to captured note
# ---------------------------------------------------------------------------

def test_accept_suggestion_adds_wikilink(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Some content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._accept_suggestion(note_name, "Related Note")
    note = captures_store.read(note_name)
    assert "[[Related Note]]" in note.content


def test_accept_suggestion_preserves_existing_content(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Original content here.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._accept_suggestion(note_name, "Related Note")
    note = captures_store.read(note_name)
    assert "Original content here." in note.content


def test_accept_suggestion_preserves_frontmatter(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._accept_suggestion(note_name, "Related Note")
    note = captures_store.read(note_name)
    assert note.frontmatter["source"] == "http://example.com"
    assert note.frontmatter["capture_date"] == "2026-05-11"


# ---------------------------------------------------------------------------
# Slice 8 — rejecting a suggestion does not modify the note
# ---------------------------------------------------------------------------

def test_reject_suggestion_does_not_modify_note(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Original content only.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._reject_suggestion(note_name, "Unrelated Note")
    note = captures_store.read(note_name)
    assert "[[Unrelated Note]]" not in note.content


# ---------------------------------------------------------------------------
# Slice 9 — capturing with all_notes_store finds and shows related notes
# ---------------------------------------------------------------------------

def test_panel_with_notes_finds_related_on_complete(qapp, captures_store, all_notes_store, engine):
    """When all_notes_store is provided, _on_capture_complete finds related notes."""
    panel = CapturePanel(engine, captures_store, all_notes_store=all_notes_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article about Python Programming",
        content="This article is all about Python Programming and its ecosystem.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    # Simulate the completion callback (bypasses worker thread)
    panel._on_capture_complete(result)
    assert not panel._suggestions_widget.isHidden()


# ---------------------------------------------------------------------------
# Slice 10 — multiple suggestions create multiple rows
# ---------------------------------------------------------------------------

def test_multiple_suggestions_create_multiple_rows(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._on_capture_done(note_name, ["Note A", "Note B", "Note C"])
    from PyQt6.QtWidgets import QPushButton
    accept_btns = [
        btn for btn in panel._suggestions_widget.findChildren(QPushButton)
        if btn.objectName().startswith("accept_")
    ]
    assert len(accept_btns) == 3


# ---------------------------------------------------------------------------
# Slice 11 — clearing suggestions resets the panel
# ---------------------------------------------------------------------------

def test_clear_suggestions_hides_widget(qapp, captures_store, engine):
    panel = CapturePanel(engine, captures_store)
    result = CaptureResult(
        source="http://example.com",
        title="Article",
        content="Content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, captures_store)
    panel._on_capture_done(note_name, ["Some Note"])
    assert not panel._suggestions_widget.isHidden()
    panel._clear_suggestions()
    assert panel._suggestions_widget.isHidden()
