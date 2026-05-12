"""
Tests for Issue #4 — Note Browser + Note Editor panels.

Each class covers one slice of behavior, verified through public interfaces.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QPlainTextEdit

from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore, DuplicateNoteError
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.panels import BasePanel
from cbosa.ui.panels.note_browser import NoteBrowserPanel
from cbosa.ui.panels.note_editor import NoteEditorPanel, _render_markdown


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return NoteStore(tmp_path)


@pytest.fixture
def tag_index(store):
    return TagIndex(store)


@pytest.fixture
def link_index(store):
    return LinkIndex(store)


@pytest.fixture
def search_index(store):
    return SearchIndex(store)


# ---------------------------------------------------------------------------
# NoteBrowserPanel — slice 1: exists and lists notes
# ---------------------------------------------------------------------------


class TestNoteBrowserPanel:
    def test_is_base_panel(self, qapp, store, tag_index, search_index):
        panel = NoteBrowserPanel(store, tag_index, search_index)
        assert isinstance(panel, BasePanel)

    def test_shows_all_notes_on_init(self, qapp, store, tag_index, search_index):
        store.create("alpha", "content a")
        store.create("beta", "content b")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "alpha" in items
        assert "beta" in items

    # --- slice 2: tag filtering ---

    def test_tag_filter_narrows_list(self, qapp, store, tag_index, search_index):
        store.create("python-note", "#python is great")
        store.create("other-note", "no tags here")
        tag_index.rebuild()
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.set_tag_filter("python")
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "python-note" in items
        assert "other-note" not in items

    def test_clear_tag_filter_shows_all(self, qapp, store, tag_index, search_index):
        store.create("python-note", "#python content")
        store.create("other-note", "no tags")
        tag_index.rebuild()
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.set_tag_filter("python")
        panel.clear_tag_filter()
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert len(items) == 2

    # --- slice 3: note_selected signal ---

    def test_note_selected_signal_fires_on_click(self, qapp, store, tag_index, search_index):
        store.create("my-note", "content")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        received = []
        panel.note_selected.connect(received.append)
        panel._on_item_clicked(panel._list.item(0))
        assert received == ["my-note"]

    # --- slice 4: create new note ---

    def test_create_note_creates_file_on_disk(self, qapp, store, tag_index, search_index):
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.create_note("new-note")
        assert "new-note" in store.all_names()

    def test_create_note_emits_signal(self, qapp, store, tag_index, search_index):
        panel = NoteBrowserPanel(store, tag_index, search_index)
        received = []
        panel.note_created.connect(received.append)
        panel.create_note("new-note")
        assert received == ["new-note"]

    def test_create_note_refreshes_list(self, qapp, store, tag_index, search_index):
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.create_note("brand-new")
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "brand-new" in items

    # --- slice FTS: full-text search ---

    def test_search_query_shows_matching_notes(self, qapp, store, tag_index, search_index):
        store.create("alpha", "quantum computing concepts")
        store.create("beta", "classical music theory")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.set_search_query("quantum")
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "alpha" in items
        assert "beta" not in items

    def test_clearing_search_shows_all_notes(self, qapp, store, tag_index, search_index):
        store.create("alpha", "quantum computing")
        store.create("beta", "classical music")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.set_search_query("quantum")
        panel.set_search_query("")
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert len(items) == 2

    # --- delete slice ---

    def test_delete_note_removes_file(self, qapp, store, tag_index, search_index):
        store.create("to-delete", "content")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.delete_note("to-delete")
        assert "to-delete" not in store.all_names()

    def test_delete_note_emits_signal(self, qapp, store, tag_index, search_index):
        store.create("to-delete", "content")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        received = []
        panel.note_deleted.connect(received.append)
        panel.delete_note("to-delete")
        assert received == ["to-delete"]

    def test_delete_note_refreshes_list(self, qapp, store, tag_index, search_index):
        store.create("to-delete", "content")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.delete_note("to-delete")
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "to-delete" not in items

    def test_search_and_tag_filter_intersect(self, qapp, store, tag_index, search_index):
        store.create("match-both", "#python quantum computing")
        store.create("tag-only", "#python classical music")
        store.create("search-only", "quantum physics no tag")
        panel = NoteBrowserPanel(store, tag_index, search_index)
        panel.set_tag_filter("python")
        panel.set_search_query("quantum")
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert items == ["match-both"]


# ---------------------------------------------------------------------------
# _render_markdown — slice 7/9: markdown + wikilink rendering (pure logic)
# ---------------------------------------------------------------------------


class TestRenderMarkdown:
    def test_renders_heading(self):
        html = _render_markdown("# Hello")
        assert "<h1" in html
        assert "Hello" in html

    def test_renders_paragraph(self):
        html = _render_markdown("plain text")
        assert "plain text" in html

    def test_wikilinks_become_anchor_tags(self):
        html = _render_markdown("[[NoteA]]")
        assert "href=" in html
        assert "NoteA" in html

    def test_wikilink_uses_note_scheme(self):
        html = _render_markdown("[[NoteA]]")
        assert "note://" in html

    def test_wikilink_with_spaces(self):
        html = _render_markdown("[[My Note]]")
        assert "My Note" in html
        assert "note://" in html


# ---------------------------------------------------------------------------
# NoteEditorPanel — slices 5–10
# ---------------------------------------------------------------------------


class TestNoteEditorPanel:
    # slice 5: widget exists
    def test_is_base_panel(self, qapp, store, link_index):
        panel = NoteEditorPanel(store, link_index)
        assert isinstance(panel, BasePanel)

    def test_has_plain_text_editor(self, qapp, store, link_index):
        panel = NoteEditorPanel(store, link_index)
        assert isinstance(panel._editor, QPlainTextEdit)

    # slice 6: open_note loads content
    def test_open_note_loads_content_into_editor(self, qapp, store, link_index):
        store.create("my-note", "# Hello World")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        assert panel._editor.toPlainText() == "# Hello World"

    def test_open_note_sets_current_note(self, qapp, store, link_index):
        store.create("my-note", "content")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        assert panel.current_note == "my-note"

    def test_current_note_is_none_before_open(self, qapp, store, link_index):
        panel = NoteEditorPanel(store, link_index)
        assert panel.current_note is None

    # slice 10: save
    def test_save_persists_content_to_store(self, qapp, store, link_index):
        store.create("my-note", "original")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        panel._editor.setPlainText("updated content")
        panel.save()
        assert store.read("my-note").content == "updated content"

    def test_save_without_open_note_does_not_raise(self, qapp, store, link_index):
        panel = NoteEditorPanel(store, link_index)
        panel.save()  # must not raise

    # missing wikilink target creates the note
    def test_open_missing_note_creates_it(self, qapp, store, link_index):
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("does-not-exist")
        assert "does-not-exist" in store.all_names()
        assert panel.current_note == "does-not-exist"

    def test_clear_if_current_clears_editor(self, qapp, store, link_index):
        store.create("my-note", "some content")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        panel.clear_if_current("my-note")
        assert panel.current_note is None
        assert panel._editor.toPlainText() == ""

    def test_clear_if_current_ignores_other_notes(self, qapp, store, link_index):
        store.create("my-note", "content")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        panel.clear_if_current("other-note")
        assert panel.current_note == "my-note"


# ---------------------------------------------------------------------------
# Issue #5 — Daily note UI tests
# ---------------------------------------------------------------------------


class TestNoteBrowserPanelDailyNotes:
    """Verify the Note Browser shows daily notes with a 'daily/' prefix."""

    @pytest.fixture
    def daily_store(self, tmp_path):
        return NoteStore(tmp_path / "daily")

    @pytest.fixture
    def notes_store(self, tmp_path):
        return NoteStore(tmp_path / "notes")

    def test_browser_shows_daily_notes_with_prefix(
        self, qapp, notes_store, daily_store, tmp_path
    ):
        """A daily note in daily_store appears in the list as 'daily/YYYY-MM-DD'."""
        daily_store.create("2026-05-11", "")
        tag_index = TagIndex(notes_store)
        search_index = SearchIndex(notes_store)
        panel = NoteBrowserPanel(
            notes_store, tag_index, search_index, daily_store=daily_store
        )
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "daily/2026-05-11" in items

    def test_browser_without_daily_store_shows_no_prefix(
        self, qapp, notes_store, tmp_path
    ):
        """Without a daily_store, no 'daily/' items appear in the list."""
        notes_store.create("regular-note", "content")
        tag_index = TagIndex(notes_store)
        search_index = SearchIndex(notes_store)
        panel = NoteBrowserPanel(notes_store, tag_index, search_index)
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert not any(item.startswith("daily/") for item in items)

    def test_browser_daily_note_selected_signal(
        self, qapp, notes_store, daily_store, tmp_path
    ):
        """Clicking a daily note item fires note_selected with the 'daily/' prefixed name."""
        daily_store.create("2026-05-11", "")
        tag_index = TagIndex(notes_store)
        search_index = SearchIndex(notes_store)
        panel = NoteBrowserPanel(
            notes_store, tag_index, search_index, daily_store=daily_store
        )
        received = []
        panel.note_selected.connect(received.append)
        daily_items = [
            panel._list.item(i)
            for i in range(panel._list.count())
            if panel._list.item(i).text() == "daily/2026-05-11"
        ]
        assert daily_items, "daily/2026-05-11 not found in list"
        panel._on_item_clicked(daily_items[0])
        assert received == ["daily/2026-05-11"]


class TestNoteEditorPanelDailyNotes:
    """Verify the Note Editor opens daily notes from the daily_store."""

    @pytest.fixture
    def daily_store(self, tmp_path):
        return NoteStore(tmp_path / "daily")

    @pytest.fixture
    def notes_store(self, tmp_path):
        return NoteStore(tmp_path / "notes")

    def test_editor_opens_daily_note_from_daily_store(
        self, qapp, notes_store, daily_store, tmp_path
    ):
        """open_note('daily/2026-05-11') loads content from daily_store, not notes_store."""
        daily_store.create("2026-05-11", "daily body content")
        link_index = LinkIndex(notes_store)
        panel = NoteEditorPanel(notes_store, link_index, daily_store=daily_store)
        panel.open_note("daily/2026-05-11")
        assert panel._editor.toPlainText() == "daily body content"
        assert panel.current_note == "daily/2026-05-11"


# ---------------------------------------------------------------------------
# Issue #6 — Wikilink Rename Propagation UI tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Issue #6 (addendum) — Inline wikilink navigation in NoteEditorPanel
# ---------------------------------------------------------------------------


class TestNoteEditorWikilinkNavigation:
    """Wikilinks in the editor are visually styled and clickable."""

    def test_editor_has_note_link_activated_signal(self, qapp, store, link_index):
        """NoteEditorPanel exposes a note_link_activated(str) signal."""
        panel = NoteEditorPanel(store, link_index)
        # signal exists and is connectable
        received = []
        panel.note_link_activated.connect(received.append)
        assert received == []  # nothing fired yet

    def test_extract_wikilink_at_cursor_finds_target(self, qapp, store, link_index):
        """_extract_wikilink_at_cursor returns the target name when cursor is inside [[name]]."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        # position cursor inside [[target-note]]
        cursor = panel._editor.textCursor()
        cursor.setPosition(7)  # inside "[[target-note]]"
        assert panel._extract_wikilink_at_cursor(cursor) == "target-note"

    def test_extract_wikilink_at_cursor_returns_none_outside_link(self, qapp, store, link_index):
        """_extract_wikilink_at_cursor returns None when cursor is on plain text."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        cursor = panel._editor.textCursor()
        cursor.setPosition(0)  # "S" — outside any wikilink
        assert panel._extract_wikilink_at_cursor(cursor) is None

    def test_activate_wikilink_emits_signal(self, qapp, store, link_index):
        """_activate_wikilink_at_cursor emits note_link_activated with the target name."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        received = []
        panel.note_link_activated.connect(received.append)
        cursor = panel._editor.textCursor()
        cursor.setPosition(7)  # inside [[target-note]]
        panel._activate_wikilink_at_cursor(cursor)
        assert received == ["target-note"]

    def test_activate_wikilink_does_nothing_outside_link(self, qapp, store, link_index):
        """_activate_wikilink_at_cursor emits nothing when cursor is on plain text."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        received = []
        panel.note_link_activated.connect(received.append)
        cursor = panel._editor.textCursor()
        cursor.setPosition(0)
        panel._activate_wikilink_at_cursor(cursor)
        assert received == []

    def test_wikilink_highlighter_is_attached(self, qapp, store, link_index):
        """A WikilinkHighlighter is installed on the editor's document."""
        from cbosa.ui.panels.note_editor import WikilinkHighlighter
        panel = NoteEditorPanel(store, link_index)
        assert panel._highlighter is not None
        assert isinstance(panel._highlighter, WikilinkHighlighter)

    def test_cursor_move_updates_highlighter_position(self, qapp, store, link_index):
        """Moving the editor cursor updates the highlighter's tracked position."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        cursor = panel._editor.textCursor()
        cursor.setPosition(7)  # inside [[target-note]]
        panel._editor.setTextCursor(cursor)
        assert panel._highlighter._cursor_block_number == 0
        assert panel._highlighter._cursor_pos_in_block == 7

    def test_same_wikilink_span_true_when_both_inside(self, qapp, store, link_index):
        """_same_wikilink_span returns True when both cursors are in the same [[link]]."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        c1 = panel._editor.textCursor()
        c1.setPosition(6)   # inside [[target-note]]
        c2 = panel._editor.textCursor()
        c2.setPosition(10)  # also inside [[target-note]]
        assert panel._same_wikilink_span(c1, c2) is True

    def test_same_wikilink_span_false_when_outside(self, qapp, store, link_index):
        """_same_wikilink_span returns False when one cursor is outside the link."""
        store.create("my-note", "See [[target-note]] here")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        c1 = panel._editor.textCursor()
        c1.setPosition(0)   # "S" — outside wikilink
        c2 = panel._editor.textCursor()
        c2.setPosition(10)  # inside [[target-note]]
        assert panel._same_wikilink_span(c1, c2) is False

    def test_same_wikilink_span_false_across_blocks(self, qapp, store, link_index):
        """_same_wikilink_span returns False for cursors in different blocks."""
        store.create("my-note", "[[alpha]]\n[[alpha]]")
        panel = NoteEditorPanel(store, link_index)
        panel.open_note("my-note")
        c1 = panel._editor.textCursor()
        c1.setPosition(3)   # inside first [[alpha]] on line 0
        c2 = panel._editor.textCursor()
        c2.setPosition(13)  # inside second [[alpha]] on line 1
        assert panel._same_wikilink_span(c1, c2) is False


class TestNoteBrowserPanelRename:
    """Verify rename_note on NoteBrowserPanel renames files, propagates links, updates UI."""

    @pytest.fixture
    def link_index(self, store):
        return LinkIndex(store)

    @pytest.fixture
    def panel(self, qapp, store, tag_index, search_index, link_index):
        return NoteBrowserPanel(store, tag_index, search_index, link_index=link_index)

    def test_rename_note_renames_file_on_disk(self, panel, store):
        """rename_note moves the file so the new name exists and old name is gone."""
        store.create("alpha", "content")
        panel.rename_note("alpha", "beta")
        assert "beta" in store.all_names()
        assert "alpha" not in store.all_names()

    def test_rename_note_refreshes_list(self, panel, store):
        """After rename, the list widget shows new name and not old name."""
        store.create("alpha", "content")
        panel.rename_note("alpha", "beta")
        panel.refresh()
        items = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert "beta" in items
        assert "alpha" not in items

    def test_rename_note_emits_signal(self, panel, store):
        """rename_note emits note_renamed(old_name, new_name)."""
        store.create("alpha", "content")
        received = []
        panel.note_renamed.connect(lambda old, new: received.append((old, new)))
        panel.rename_note("alpha", "beta")
        assert received == [("alpha", "beta")]

    def test_rename_note_propagates_wikilinks(self, panel, store, link_index):
        """[[alpha]] in other notes is rewritten to [[beta]] after rename."""
        store.create("alpha", "Target note")
        store.create("other", "See [[alpha]] for info")
        link_index.rebuild()
        panel.rename_note("alpha", "beta")
        content = store.read("other").content
        assert "[[beta]]" in content
        assert "[[alpha]]" not in content

    def test_rename_note_raises_on_duplicate(self, panel, store):
        """Renaming to an existing note name raises DuplicateNoteError."""
        store.create("alpha", "content a")
        store.create("beta", "content b")
        with pytest.raises(DuplicateNoteError):
            panel.rename_note("alpha", "beta")

    def test_rename_note_leaves_unlinked_notes_unchanged(self, panel, store, link_index):
        """Notes with no [[alpha]] links are not modified."""
        store.create("alpha", "Target")
        store.create("unrelated", "just text here")
        link_index.rebuild()
        panel.rename_note("alpha", "beta")
        assert store.read("unrelated").content == "just text here"
