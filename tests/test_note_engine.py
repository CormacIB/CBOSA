"""
Tests for the Note Engine — NoteStore, LinkIndex, TagIndex, SearchIndex.
All tests use temporary directories and in-memory SQLite.
Behavior verified through public interfaces only.
"""
import pytest
from pathlib import Path
from cbosa.core.note_store import NoteStore, Note, DuplicateNoteError, NoteNotFoundError
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


# ---------------------------------------------------------------------------
# Issue #6 — NoteStore.rename
# ---------------------------------------------------------------------------


def test_rename_note_moves_file(store, tmp_path):
    """Renaming a note creates the new file and removes the old one."""
    store.create("old-name", "content")
    store.rename("old-name", "new-name")
    assert (tmp_path / "new-name.md").exists()
    assert not (tmp_path / "old-name.md").exists()


def test_rename_note_preserves_content(store):
    """Content and frontmatter survive a rename."""
    store.create("old-name", "body text", frontmatter={"title": "Old"})
    store.rename("old-name", "new-name")
    note = store.read("new-name")
    assert note.content == "body text"
    assert note.frontmatter["title"] == "Old"


def test_rename_note_raises_duplicate_error(store):
    """Renaming to an already-existing note name raises DuplicateNoteError."""
    store.create("alpha", "content a")
    store.create("beta", "content b")
    with pytest.raises(DuplicateNoteError):
        store.rename("alpha", "beta")


def test_rename_note_raises_not_found_error(store):
    """Renaming a note that does not exist raises NoteNotFoundError."""
    with pytest.raises(NoteNotFoundError):
        store.rename("ghost", "new-name")


def test_rename_note_appears_in_all_names(store):
    """After rename, new name is in all_names() and old name is not."""
    store.create("old-name", "content")
    store.rename("old-name", "new-name")
    names = store.all_names()
    assert "new-name" in names
    assert "old-name" not in names


# ---------------------------------------------------------------------------
# Issue #6 — LinkIndex.rename_note (wikilink propagation)
# ---------------------------------------------------------------------------


def test_rename_note_updates_wikilinks_in_referencing_notes(link_store):
    """[[old-name]] in other notes is rewritten to [[new-name]] after rename."""
    store, idx = link_store
    store.create("old-name", "Target note")
    store.create("note-b", "See [[old-name]] for details")
    idx.rebuild()
    store.rename("old-name", "new-name")
    idx.rename_note("old-name", "new-name")
    content = store.read("note-b").content
    assert "[[new-name]]" in content
    assert "[[old-name]]" not in content


def test_rename_note_leaves_unrelated_notes_unchanged(link_store):
    """Notes with no links to old-name are not modified."""
    store, idx = link_store
    store.create("old-name", "Target")
    store.create("unrelated", "No links here, just text")
    idx.rebuild()
    store.rename("old-name", "new-name")
    idx.rename_note("old-name", "new-name")
    content = store.read("unrelated").content
    assert content == "No links here, just text"


def test_rename_note_updates_link_index(link_store):
    """After rename_note, links_to(new-name) reflects the updated references."""
    store, idx = link_store
    store.create("old-name", "Target")
    store.create("note-b", "See [[old-name]]")
    idx.rebuild()
    store.rename("old-name", "new-name")
    idx.rename_note("old-name", "new-name")
    assert "note-b" in idx.links_to("new-name")
    assert idx.links_to("old-name") == []


def test_rename_note_handles_multiple_references_in_one_note(link_store):
    """Multiple [[old-name]] occurrences in a single note are all rewritten."""
    store, idx = link_store
    store.create("old-name", "Target")
    store.create("note-b", "First [[old-name]] and second [[old-name]]")
    idx.rebuild()
    store.rename("old-name", "new-name")
    idx.rename_note("old-name", "new-name")
    content = store.read("note-b").content
    assert content.count("[[new-name]]") == 2
    assert "[[old-name]]" not in content
