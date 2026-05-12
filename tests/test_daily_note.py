"""
Tests for Issue #5 — Daily Note Auto-Creation.

All tests verify behavior through the DailyNoteService public interface.
NoteStore uses a temporary directory; no Qt required.
"""
from __future__ import annotations

import datetime

import pytest

from cbosa.core.daily_note import DailyNoteService
from cbosa.core.note_store import NoteStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def daily_store(tmp_path):
    return NoteStore(tmp_path / "daily")


@pytest.fixture
def service(daily_store):
    return DailyNoteService(daily_store)


_DATE = datetime.date(2026, 5, 11)


# ---------------------------------------------------------------------------
# Tracer bullet: note is created
# ---------------------------------------------------------------------------


def test_ensure_today_creates_note_when_missing(service, daily_store):
    """Calling ensure_today creates a .md note in the store when none exists."""
    service.ensure_today(_DATE)
    assert "2026-05-11" in daily_store.all_names()


# ---------------------------------------------------------------------------
# Idempotency: existing note is not overwritten
# ---------------------------------------------------------------------------


def test_ensure_today_does_not_overwrite_existing(service, daily_store):
    """If today's note already exists, ensure_today leaves its content unchanged."""
    daily_store.create("2026-05-11", "my existing content")
    service.ensure_today(_DATE)
    note = daily_store.read("2026-05-11")
    assert note.content == "my existing content"


# ---------------------------------------------------------------------------
# Frontmatter: title is populated
# ---------------------------------------------------------------------------


def test_daily_note_has_title_frontmatter(service, daily_store):
    """The created daily note has frontmatter['title'] set to the date string."""
    service.ensure_today(_DATE)
    note = daily_store.read("2026-05-11")
    assert note.frontmatter.get("title") == "2026-05-11"


# ---------------------------------------------------------------------------
# Frontmatter: date is populated
# ---------------------------------------------------------------------------


def test_daily_note_has_date_frontmatter(service, daily_store):
    """The created daily note has frontmatter['date'] set to the date string."""
    service.ensure_today(_DATE)
    note = daily_store.read("2026-05-11")
    assert note.frontmatter.get("date") == "2026-05-11"


# ---------------------------------------------------------------------------
# Default argument: uses today's real date
# ---------------------------------------------------------------------------


def test_ensure_today_uses_actual_date_by_default(service, daily_store):
    """ensure_today() with no argument creates a note named after today's date."""
    service.ensure_today()
    today_str = datetime.date.today().isoformat()
    assert today_str in daily_store.all_names()


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------


def test_ensure_today_returns_note_object(service):
    """ensure_today returns a Note whose name matches the date string."""
    note = service.ensure_today(_DATE)
    assert note.name == "2026-05-11"
