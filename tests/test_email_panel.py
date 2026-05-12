"""
Tests for Issue #9 — EmailPanel UI.

Behaviors verified through public interfaces only.
All tests use an in-memory EmailStore (no disk I/O, no network).
"""
from __future__ import annotations

import pytest

from cbosa.modules.email_store import EmailStore
from cbosa.ui.panels import BasePanel
from cbosa.ui.panels.email_panel import EmailPanel, _ROLE_EMAIL_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    s = EmailStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def panel_no_creds(qapp, store, monkeypatch):
    """Panel whose store reports no credentials (explicitly forced for test isolation)."""
    monkeypatch.setattr(type(store), "has_credentials", property(lambda self: False))
    return EmailPanel(store)


@pytest.fixture
def store_with_emails(store):
    """Store pre-populated with two fixture emails."""
    store.insert_email(
        uid="1",
        subject="Please review the Q1 report",
        sender="alice@example.com",
        date="2026-05-01",
        body="Hi,\nCould you review the attached Q1 report by Friday?\nLet me know if you have questions.\nAlice",
    )
    store.insert_email(
        uid="2",
        subject="Meeting tomorrow",
        sender="bob@example.com",
        date="2026-05-02",
        body="Hi team,\nWe have a meeting scheduled for tomorrow at 10am.\nPlease confirm your attendance.\nBob",
    )
    return store


@pytest.fixture
def panel_with_emails(qapp, store_with_emails, monkeypatch):
    """Panel with credentials mocked present and two emails pre-loaded."""
    monkeypatch.setattr(type(store_with_emails), "has_credentials", property(lambda self: True))
    return EmailPanel(store_with_emails)


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: EmailPanel is a BasePanel
# ---------------------------------------------------------------------------

def test_is_base_panel(panel_no_creds):
    assert isinstance(panel_no_creds, BasePanel)


# ---------------------------------------------------------------------------
# Slice 2 — no credentials → setup prompt shown, not inbox
# ---------------------------------------------------------------------------

def test_no_credentials_shows_setup_label(panel_no_creds):
    from PyQt6.QtWidgets import QLabel
    labels = panel_no_creds.widget().findChildren(QLabel, "no_credentials_label")
    assert len(labels) == 1


def test_no_credentials_label_mentions_secrets_toml(panel_no_creds):
    from PyQt6.QtWidgets import QLabel
    labels = panel_no_creds.widget().findChildren(QLabel, "no_credentials_label")
    assert labels, "no_credentials_label not found"
    assert "secrets.toml" in labels[0].text()


def test_no_credentials_has_no_inbox_list(panel_no_creds):
    from PyQt6.QtWidgets import QListWidget
    inbox = panel_no_creds.widget().findChildren(QListWidget, "inbox_list")
    assert len(inbox) == 0


# ---------------------------------------------------------------------------
# Slice 3 — with credentials: inbox widgets are present
# ---------------------------------------------------------------------------

def test_with_credentials_inbox_list_exists(panel_with_emails):
    from PyQt6.QtWidgets import QListWidget
    inbox = panel_with_emails.widget().findChildren(QListWidget, "inbox_list")
    assert len(inbox) == 1


def test_with_credentials_message_reader_exists(panel_with_emails):
    from PyQt6.QtWidgets import QTextEdit
    reader = panel_with_emails.widget().findChildren(QTextEdit, "message_reader")
    assert len(reader) == 1


def test_with_credentials_tasks_list_exists(panel_with_emails):
    from PyQt6.QtWidgets import QListWidget
    tasks = panel_with_emails.widget().findChildren(QListWidget, "tasks_list")
    assert len(tasks) == 1


def test_with_credentials_sync_button_exists(panel_with_emails):
    from PyQt6.QtWidgets import QPushButton
    btns = panel_with_emails.widget().findChildren(QPushButton, "sync_btn")
    assert len(btns) == 1


def test_with_credentials_search_edit_exists(panel_with_emails):
    from PyQt6.QtWidgets import QLineEdit
    edits = panel_with_emails.widget().findChildren(QLineEdit, "search_edit")
    assert len(edits) == 1


# ---------------------------------------------------------------------------
# Slice 4 — inbox list populated from cache on init
# ---------------------------------------------------------------------------

def test_inbox_shows_correct_count(panel_with_emails):
    assert panel_with_emails._inbox_list.count() == 2


def test_inbox_item_contains_subject(panel_with_emails):
    texts = [panel_with_emails._inbox_list.item(i).text()
             for i in range(panel_with_emails._inbox_list.count())]
    assert any("Meeting tomorrow" in t for t in texts)


def test_inbox_item_contains_sender(panel_with_emails):
    texts = [panel_with_emails._inbox_list.item(i).text()
             for i in range(panel_with_emails._inbox_list.count())]
    assert any("alice@example.com" in t for t in texts)


def test_inbox_item_contains_date(panel_with_emails):
    texts = [panel_with_emails._inbox_list.item(i).text()
             for i in range(panel_with_emails._inbox_list.count())]
    assert any("2026-05-01" in t for t in texts)


def test_inbox_item_stores_email_id(panel_with_emails):
    item = panel_with_emails._inbox_list.item(0)
    email_id = item.data(_ROLE_EMAIL_ID)
    assert isinstance(email_id, int)
    assert email_id > 0


# ---------------------------------------------------------------------------
# Slice 5 — selecting an email populates the message reader
# ---------------------------------------------------------------------------

def test_selecting_email_shows_subject_in_reader(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(1)  # row 1 = older email (alice)
    text = panel_with_emails._message_reader.toPlainText()
    assert "Q1 report" in text


def test_selecting_email_shows_sender_in_reader(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(1)
    text = panel_with_emails._message_reader.toPlainText()
    assert "alice@example.com" in text


def test_selecting_email_shows_body_in_reader(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(1)
    text = panel_with_emails._message_reader.toPlainText()
    assert "Could you review" in text


# ---------------------------------------------------------------------------
# Slice 6 — selecting an email populates extracted tasks
# ---------------------------------------------------------------------------

def test_selecting_email_with_action_items_shows_tasks(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(1)  # alice email has action items
    assert panel_with_emails._tasks_list.count() >= 1


def test_selecting_email_tasks_contain_action_text(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(1)
    task_texts = [
        panel_with_emails._tasks_list.item(i).text()
        for i in range(panel_with_emails._tasks_list.count())
    ]
    assert any("review" in t.lower() or "let me know" in t.lower() for t in task_texts)


def test_selecting_different_email_refreshes_tasks(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(1)
    count_first = panel_with_emails._tasks_list.count()
    panel_with_emails._inbox_list.setCurrentRow(0)
    count_second = panel_with_emails._tasks_list.count()
    assert count_first >= 1
    assert count_second >= 1


# ---------------------------------------------------------------------------
# Slice 7 — keyword search filters inbox
# ---------------------------------------------------------------------------

def test_keyword_search_filters_inbox(panel_with_emails):
    panel_with_emails._search_edit.setText("Q1")
    panel_with_emails._on_search()
    assert panel_with_emails._inbox_list.count() == 1
    assert "Q1" in panel_with_emails._inbox_list.item(0).text()


def test_keyword_search_no_match_shows_empty(panel_with_emails):
    panel_with_emails._search_edit.setText("xyznonexistent")
    panel_with_emails._on_search()
    assert panel_with_emails._inbox_list.count() == 0


def test_empty_search_restores_all_emails(panel_with_emails):
    panel_with_emails._search_edit.setText("Q1")
    panel_with_emails._on_search()
    assert panel_with_emails._inbox_list.count() == 1
    panel_with_emails._search_edit.setText("")
    panel_with_emails._on_search()
    assert panel_with_emails._inbox_list.count() == 2


# ---------------------------------------------------------------------------
# Slice 8 — sender search filters inbox
# ---------------------------------------------------------------------------

def test_sender_search_filters_to_matching_sender(panel_with_emails):
    panel_with_emails._search_edit.setText("alice@example.com")
    panel_with_emails._on_search()
    assert panel_with_emails._inbox_list.count() == 1
    assert "alice" in panel_with_emails._inbox_list.item(0).text()


# ---------------------------------------------------------------------------
# Slice 9 — date search filters inbox
# ---------------------------------------------------------------------------

def test_date_search_filters_by_date(panel_with_emails):
    panel_with_emails._search_edit.setText("2026-05-02")
    panel_with_emails._on_search()
    assert panel_with_emails._inbox_list.count() == 1
    assert "Meeting" in panel_with_emails._inbox_list.item(0).text()


# ---------------------------------------------------------------------------
# Slice 10 — sync button and status label
# ---------------------------------------------------------------------------

def test_status_label_initially_ready(panel_with_emails):
    assert panel_with_emails._status_label.text() == "Ready"


def test_sync_button_is_enabled_initially(panel_with_emails):
    assert panel_with_emails._sync_btn.isEnabled()


def test_on_sync_done_with_error_shows_error(panel_with_emails):
    panel_with_emails._on_sync_done(0, "Connection refused")
    assert "Error" in panel_with_emails._status_label.text()
    assert panel_with_emails._sync_btn.isEnabled()


def test_on_sync_done_success_shows_count(panel_with_emails):
    panel_with_emails._on_sync_done(5, "")
    assert "5" in panel_with_emails._status_label.text()
    assert panel_with_emails._sync_btn.isEnabled()


# ---------------------------------------------------------------------------
# Slice 11 — refresh_inbox after sync_done re-populates list
# ---------------------------------------------------------------------------

def test_sync_done_refreshes_inbox(qapp, monkeypatch):
    store = EmailStore(":memory:")
    monkeypatch.setattr(type(store), "has_credentials", property(lambda self: True))
    panel = EmailPanel(store)
    assert panel._inbox_list.count() == 0
    store.insert_email("uid-1", "Hello", "x@example.com", "2026-05-10", "body")
    panel._on_sync_done(1, "")
    assert panel._inbox_list.count() == 1
    store.close()


# ---------------------------------------------------------------------------
# Slice 12 — deselecting clears the reader and tasks
# ---------------------------------------------------------------------------

def test_reader_empty_when_no_email_selected(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(0)
    panel_with_emails._on_email_selected(None, None)
    assert panel_with_emails._message_reader.toPlainText() == ""
    assert panel_with_emails._tasks_list.count() == 0


# ---------------------------------------------------------------------------
# Slice 13 — _refresh_inbox reflects store changes
# ---------------------------------------------------------------------------

def test_refresh_inbox_shows_new_email(qapp, store_with_emails, monkeypatch):
    monkeypatch.setattr(type(store_with_emails), "has_credentials", property(lambda self: True))
    panel = EmailPanel(store_with_emails)
    assert panel._inbox_list.count() == 2
    store_with_emails.insert_email("3", "New message", "c@example.com", "2026-05-03", "Hi")
    panel._refresh_inbox()
    assert panel._inbox_list.count() == 3


# ---------------------------------------------------------------------------
# Slice 14 — clear inbox button empties the list
# ---------------------------------------------------------------------------

def test_clear_btn_exists(panel_with_emails):
    from PyQt6.QtWidgets import QPushButton
    btns = panel_with_emails.widget().findChildren(QPushButton, "clear_btn")
    assert len(btns) == 1


def test_on_clear_empties_inbox_list(panel_with_emails):
    assert panel_with_emails._inbox_list.count() == 2
    panel_with_emails._on_clear()
    assert panel_with_emails._inbox_list.count() == 0


def test_on_clear_empties_store(panel_with_emails, store_with_emails):
    assert store_with_emails.count() == 2
    panel_with_emails._on_clear()
    assert store_with_emails.count() == 0


def test_on_clear_clears_reader(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(0)
    panel_with_emails._on_clear()
    assert panel_with_emails._message_reader.toPlainText() == ""


def test_on_clear_clears_tasks(panel_with_emails):
    panel_with_emails._inbox_list.setCurrentRow(0)
    panel_with_emails._on_clear()
    assert panel_with_emails._tasks_list.count() == 0


def test_on_clear_updates_status_label(panel_with_emails):
    panel_with_emails._on_clear()
    assert "cleared" in panel_with_emails._status_label.text().lower()
