"""
Tests for Issue #4 — Note Browser + Note Editor panels.

Each class covers one slice of behavior, verified through public interfaces.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QPlainTextEdit

from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
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
