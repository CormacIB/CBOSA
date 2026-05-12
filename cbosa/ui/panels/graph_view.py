"""
GraphViewPanel — interactive force-directed note graph.

Nodes are notes; edges are [[wikilinks]].  Layout is computed with the
Fruchterman-Reingold algorithm (networkx.spring_layout).  The user can
zoom and pan via pyqtgraph's built-in ViewBox, and click any node to open
that note in the Note Editor.

Design decision: pyqtgraph (PlotWidget + GraphItem) is used for rendering
because its ViewBox provides zoom/pan for free and ScatterPlotItem provides
node-click detection.  A custom QPainter renderer was considered but rejected —
pyqtgraph covers zoom, pan, and hit-testing at lower implementation cost.

The graph refreshes on save (note_saved signal from NoteEditorPanel), wired
through MainWindow._wire_panels() following the established inter-panel pattern.
Layout is computed on the main thread (sufficient for personal-scale note
counts; a QThread worker can be added here if performance becomes an issue).
"""
from __future__ import annotations

import numpy as np
import networkx as nx
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal

from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.ui.panels import BasePanel


class GraphViewPanel(BasePanel):
    """Force-directed graph panel: notes as nodes, wikilinks as edges."""

    node_clicked = pyqtSignal(str)

    def __init__(
        self,
        store: NoteStore,
        link_index: LinkIndex,
        title: str = "Graph View",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._link_index = link_index
        self._names: list[str] = []
        self._adj: np.ndarray = np.empty((0, 2), dtype=int)
        self._pos: np.ndarray = np.empty((0, 2), dtype=float)
        self._labels: list[pg.TextItem] = []

        # --- pyqtgraph setup ---
        pg.setConfigOption("background", "#1e1e2e")
        pg.setConfigOption("foreground", "#cdd6f4")
        self._plot = pg.PlotWidget()
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._plot.setMenuEnabled(False)

        self._graph_item = pg.GraphItem()
        self._plot.addItem(self._graph_item)
        # GraphItem's internal ScatterPlotItem provides per-node click events.
        # The data field is overwritten by GraphItem with {'index': array},
        # so we look up the name via self._names[spot.data()['index']].
        self._graph_item.scatter.sigClicked.connect(self._on_node_clicked)

        self.setWidget(self._plot)
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the graph from the current store + link_index state."""
        # Clear old labels
        for label in self._labels:
            self._plot.removeItem(label)
        self._labels = []

        self._names = list(self._store.all_names())

        if not self._names:
            self._adj = np.empty((0, 2), dtype=int)
            self._pos = np.empty((0, 2), dtype=float)
            self._graph_item.setData(pos=np.empty((0, 2)))
            return

        # Build networkx graph for Fruchterman-Reingold layout
        G = nx.Graph()
        G.add_nodes_from(self._names)
        name_set = set(self._names)
        name_to_idx = {n: i for i, n in enumerate(self._names)}

        seen_edges: set[frozenset] = set()
        edge_list: list[list[int]] = []
        for name in self._names:
            for target in self._link_index.links_from(name):
                if target not in name_set:
                    continue
                key = frozenset((name, target))
                if key not in seen_edges:
                    seen_edges.add(key)
                    edge_list.append([name_to_idx[name], name_to_idx[target]])
                    G.add_edge(name, target)

        pos_map = nx.spring_layout(G, seed=42)
        pos = np.array([pos_map[n] for n in self._names], dtype=float)
        self._pos = pos

        self._adj = (
            np.array(edge_list, dtype=int)
            if edge_list
            else np.empty((0, 2), dtype=int)
        )

        self._graph_item.setData(
            pos=pos,
            adj=self._adj,
            size=14,
            symbol="o",
            pxMode=True,
            pen=pg.mkPen("#45475a", width=1),
            brush=pg.mkBrush("#89b4fa"),
        )

        # Add a TextItem label above each node
        for i, name in enumerate(self._names):
            label = pg.TextItem(name, anchor=(0.5, 1.5), color="#cdd6f4")
            label.setPos(pos[i, 0], pos[i, 1])
            self._plot.addItem(label)
            self._labels.append(label)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_node_clicked(self, plot_item, spots, ev) -> None:
        """Handle a click on a graph node and emit node_clicked(name).

        pyqtgraph 0.14 does not populate spot.data() reliably via GraphItem,
        so we match the clicked spot's position against self._pos instead.
        """
        if not spots:
            return
        p = spots[0].pos()
        clicked = np.array([p.x(), p.y()])
        if self._pos.shape[0] == 0:
            return
        dists = np.linalg.norm(self._pos - clicked, axis=1)
        idx = int(np.argmin(dists))
        self.node_clicked.emit(self._names[idx])
