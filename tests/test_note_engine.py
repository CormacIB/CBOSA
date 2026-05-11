"""
Tests for the Note Engine — NoteStore, LinkIndex, TagIndex, SearchIndex.
All tests use temporary directories and in-memory SQLite.
Behavior verified through public interfaces only.
"""
import pytest
from pathlib import Path
from cbosa.core.note_store import NoteStore, Note
from cbosa.core.link_index import LinkIndex
from cbosa.core.tag_index import TagIndex
from cbosa.core.search_index import SearchIndex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return NoteStore(tmp_path)


# ---------------------------------------------------------------------------
# NoteStore — tracer bullet
# ---------------------------------------------------------------------------

def test_create_note_writes_file(store, tmp_path):
    """Creating a note persists a .md file in the notes directory."""
    store.create("my-note", "Hello world")
    assert (tmp_path / "my-note.md").exists()


# ---------------------------------------------------------------------------
# NoteStore — read
# ---------------------------------------------------------------------------

def test_read_returns_note_content(store):
    """Reading a note returns its content unchanged."""
    store.create("alpha", "Some content here")
    note = store.read("alpha")
    assert note.content == "Some content here"


# ---------------------------------------------------------------------------
# NoteStore — update
# ---------------------------------------------------------------------------

def test_update_changes_content(store):
    """Updating a note replaces its content on disk."""
    store.create("beta", "original")
    store.update("beta", "updated")
    assert store.read("beta").content == "updated"


# ---------------------------------------------------------------------------
# NoteStore — delete
# ---------------------------------------------------------------------------

def test_delete_removes_file(store, tmp_path):
    """Deleting a note removes the .md file from disk."""
    store.create("gamma", "bye")
    store.delete("gamma")
    assert not (tmp_path / "gamma.md").exists()


# ---------------------------------------------------------------------------
# NoteStore — frontmatter round-trip
# ---------------------------------------------------------------------------

def test_frontmatter_roundtrips_without_data_loss(store):
    """YAML frontmatter (title, tags, date, related) survives a write/read cycle."""
    fm = {
        "title": "My Note",
        "tags": ["python", "dev"],
        "date": "2026-05-10",
        "related": ["other-note"],
    }
    store.create("delta", "Body text.", frontmatter=fm)
    note = store.read("delta")
    assert note.frontmatter["title"] == "My Note"
    assert note.frontmatter["tags"] == ["python", "dev"]
    assert note.frontmatter["date"] == "2026-05-10"
    assert note.frontmatter["related"] == ["other-note"]
    assert note.content == "Body text."


# ---------------------------------------------------------------------------
# LinkIndex — forward link B→A
# ---------------------------------------------------------------------------

@pytest.fixture
def link_store(tmp_path):
    s = NoteStore(tmp_path)
    return s, LinkIndex(s)


def test_link_index_records_forward_link(link_store):
    """[[NoteA]] in Note B causes links_from('note-b') to include 'note-a'."""
    store, idx = link_store
    store.create("note-a", "Target note")
    store.create("note-b", "See [[note-a]] for details")
    idx.rebuild()
    assert "note-a" in idx.links_from("note-b")


# ---------------------------------------------------------------------------
# LinkIndex — bidirectional: A←B backlink
# ---------------------------------------------------------------------------

def test_link_index_records_backlink(link_store):
    """[[note-b]] in note-a causes links_to('note-b') to include 'note-a'."""
    store, idx = link_store
    store.create("note-b", "Target")
    store.create("note-a", "References [[note-b]]")
    idx.rebuild()
    assert "note-a" in idx.links_to("note-b")


# ---------------------------------------------------------------------------
# LinkIndex — missing note target handled gracefully
# ---------------------------------------------------------------------------

def test_link_index_missing_target_does_not_raise(link_store):
    """A [[wikilink]] pointing to a non-existent note is recorded without error."""
    store, idx = link_store
    store.create("note-x", "Points to [[ghost-note]] which doesn't exist")
    idx.rebuild()
    assert "ghost-note" in idx.links_from("note-x")


# ---------------------------------------------------------------------------
# TagIndex — #tag → notes
# ---------------------------------------------------------------------------

def test_tag_index_maps_tag_to_note(store):
    """A #tag in a note appears in the tag index mapping that tag to the note."""
    store.create("tagged-note", "This note has #python and #dev tags")
    idx = TagIndex(store)
    idx.rebuild()
    assert "tagged-note" in idx.notes_for_tag("python")
    assert "tagged-note" in idx.notes_for_tag("dev")


# ---------------------------------------------------------------------------
# SearchIndex — FTS5 full-text search
# ---------------------------------------------------------------------------

def test_fts_search_returns_note_by_content(store):
    """Full-text search on a note's content returns that note's name."""
    store.create("searchable", "The quick brown fox jumps over the lazy dog")
    idx = SearchIndex(store)
    idx.rebuild()
    results = idx.search("quick brown fox")
    assert "searchable" in results


def test_fts_search_no_match_returns_empty(store):
    """A query with no matching notes returns an empty list."""
    store.create("unrelated", "Nothing to see here")
    idx = SearchIndex(store)
    idx.rebuild()
    assert idx.search("xyzzy") == []
