"""
Tests for Issue #7 — Graph View Panel.

Behaviors verified through public interfaces only.
QGraphicsView is used for rendering; we test state, not pixels.
"""
from __future__ import annotations

import numpy as np
import pytest

from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.ui.panels import BasePanel
from cbosa.ui.panels.graph_view import GraphViewPanel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return NoteStore(tmp_path)


@pytest.fixture
def link_index(store):
    idx = LinkIndex(store)
    idx.rebuild()
    return idx


@pytest.fixture
def panel(qapp, store, link_index):
    return GraphViewPanel(store, link_index)


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: GraphViewPanel is a BasePanel
# ---------------------------------------------------------------------------


def test_is_base_panel(panel):
    assert isinstance(panel, BasePanel)


# ---------------------------------------------------------------------------
# Slice 2 — has a QGraphicsView
# ---------------------------------------------------------------------------


def test_has_graphics_view(panel):
    from PyQt6.QtWidgets import QGraphicsView
    assert isinstance(panel._view, QGraphicsView)


# ---------------------------------------------------------------------------
# Slice 3 — refresh() on empty store does not crash
# ---------------------------------------------------------------------------


def test_refresh_empty_store_no_crash(qapp, store, link_index):
    p = GraphViewPanel(store, link_index)
    p.refresh()  # must not raise
    assert p._names == []


# ---------------------------------------------------------------------------
# Slice 4 — refresh() tracks one entry per note
# ---------------------------------------------------------------------------


def test_refresh_names_match_all_notes(qapp, store, link_index):
    store.create("alpha", "content")
    store.create("beta", "content")
    store.create("gamma", "content")
    link_index.rebuild()
    p = GraphViewPanel(store, link_index)
    assert set(p._names) == {"alpha", "beta", "gamma"}


# ---------------------------------------------------------------------------
# Slice 5 — refresh() builds edges for wikilinks
# ---------------------------------------------------------------------------


def test_refresh_builds_edge_for_wikilink(qapp, store, link_index):
    store.create("alpha", "See [[beta]]")
    store.create("beta", "content")
    link_index.rebuild()
    p = GraphViewPanel(store, link_index)
    assert p._adj.shape[0] == 1          # exactly one edge
    assert p._adj.shape[1] == 2          # (u, v) pairs


def test_refresh_no_edges_when_no_links(qapp, store, link_index):
    store.create("alpha", "content")
    store.create("beta", "content")
    link_index.rebuild()
    p = GraphViewPanel(store, link_index)
    assert p._adj.shape[0] == 0


# ---------------------------------------------------------------------------
# Slice 6 — isolated notes still appear as nodes
# ---------------------------------------------------------------------------


def test_isolated_notes_appear_as_nodes(qapp, store, link_index):
    store.create("linked-a", "See [[linked-b]]")
    store.create("linked-b", "content")
    store.create("isolated", "no links here")
    link_index.rebuild()
    p = GraphViewPanel(store, link_index)
    assert "isolated" in p._names


# ---------------------------------------------------------------------------
# Slice 7 — node_clicked signal exists and is connectable
# ---------------------------------------------------------------------------


def test_node_clicked_signal_connectable(panel):
    received = []
    panel.node_clicked.connect(received.append)
    assert received == []


# ---------------------------------------------------------------------------
# Slice 8 — _on_node_clicked emits node_clicked with the correct note name
# ---------------------------------------------------------------------------


class _FakeSpot:
    """Mimics the spot object pyqtgraph passes to sigClicked handlers.

    Uses pos() matching — the same path taken by the real handler —
    since GraphItem in pyqtgraph 0.14 does not populate spot.data().
    """
    def __init__(self, x: float, y: float):
        from PyQt6.QtCore import QPointF
        self._pos = QPointF(x, y)

    def pos(self):
        return self._pos


def test_on_node_clicked_emits_correct_name(qapp, store, link_index):
    store.create("alpha", "content")
    store.create("beta", "content")
    link_index.rebuild()
    p = GraphViewPanel(store, link_index)
    received = []
    p.node_clicked.connect(received.append)
    # Click exactly on node 0's stored position
    x, y = float(p._pos[0, 0]), float(p._pos[0, 1])
    p._on_node_clicked(None, [_FakeSpot(x, y)], None)
    assert received == [p._names[0]]


def test_on_node_clicked_with_no_spots_does_nothing(panel):
    received = []
    panel.node_clicked.connect(received.append)
    panel._on_node_clicked(None, [], None)
    assert received == []


# ---------------------------------------------------------------------------
# Slice 9 — refresh() after link added reflects new edge
# ---------------------------------------------------------------------------


def test_refresh_after_link_added_shows_new_edge(qapp, store, link_index):
    store.create("alpha", "no links yet")
    store.create("beta", "content")
    link_index.rebuild()
    p = GraphViewPanel(store, link_index)
    assert p._adj.shape[0] == 0

    # Now add a link and rebuild
    store.update("alpha", "See [[beta]]")
    link_index.rebuild()
    p.refresh()
    assert p._adj.shape[0] == 1


# ---------------------------------------------------------------------------
# Slice 10 — NoteEditorPanel emits note_saved after save()
# ---------------------------------------------------------------------------


def test_note_editor_emits_note_saved_after_save(qapp, store, link_index):
    from cbosa.ui.panels.note_editor import NoteEditorPanel
    store.create("my-note", "content")
    panel = NoteEditorPanel(store, link_index)
    panel.open_note("my-note")
    received = []
    panel.note_saved.connect(received.append)
    panel.save()
    assert received == ["my-note"]


def test_note_editor_note_saved_not_emitted_without_open_note(qapp, store, link_index):
    from cbosa.ui.panels.note_editor import NoteEditorPanel
    panel = NoteEditorPanel(store, link_index)
    received = []
    panel.note_saved.connect(received.append)
    panel.save()
    assert received == []
