"""
GraphViewPanel — interactive force-directed note graph.

Nodes are notes; edges are [[wikilinks]].  Initial layout uses
networkx.spring_layout.  Live force-directed physics (charge repulsion,
spring attraction, centre gravity, velocity damping) runs via QTimer so
the graph settles naturally and responds to node drags.

Interaction:
  Left-drag on node  — move node; physics resumes on release
  Left-drag on empty — pan the view
  Middle-drag        — pan the view
  Scroll wheel       — zoom (anchored under cursor)
  Left-click on node — open that note (node_clicked signal)
"""
from __future__ import annotations

import math

import networkx as nx
import numpy as np
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from cbosa import config
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.ui.panels import BasePanel

# ── Physics constants ────────────────────────────────────────────────────────
_K_REPEL   = 8_000.0  # charge-repulsion strength
_K_SPRING  = 0.04     # spring attraction (connected nodes)
_REST_LEN  = 160.0    # spring rest length in scene px
_K_GRAVITY = 0.002    # pull toward origin — prevents drift
_DAMPING   = 0.80     # velocity decay per tick
_MAX_VEL   = 60.0     # clamp velocity to prevent explosions
_STEP_MS   = 30       # physics timer interval (~33 fps)
_SCALE     = 500.0    # spring_layout [-1,1] → scene px
_NODE_R    = 9.0      # base node radius
_EDGE_W    = 1.8      # edge line width
_SETTLE_V  = 0.4      # below this max-velocity the simulation is "at rest"


class _NodeItem(QGraphicsEllipseItem):
    """Draggable, hoverable node circle."""

    def __init__(self, pen: QPen, brush: QBrush, hover_brush: QBrush, radius: float):
        r = radius
        super().__init__(-r, -r, 2 * r, 2 * r)
        self._default_brush = brush
        self._hover_brush = hover_brush
        self._radius = r
        self.setPen(pen)
        self.setBrush(brush)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.pinned: bool = False

    def mousePressEvent(self, ev) -> None:
        self.pinned = True
        self.vx = 0.0
        self.vy = 0.0
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        self.pinned = False
        super().mouseReleaseEvent(ev)

    def hoverEnterEvent(self, ev) -> None:
        self.setBrush(self._hover_brush)
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev) -> None:
        self.setBrush(self._default_brush)
        super().hoverLeaveEvent(ev)

    def apply_colors(self, pen: QPen, brush: QBrush, hover: QBrush) -> None:
        self._default_brush = brush
        self._hover_brush = hover
        self.setPen(pen)
        self.setBrush(brush)


class _EdgeItem(QGraphicsLineItem):
    """Line connecting two node items; syncs its endpoints with their positions."""

    def __init__(self, a: _NodeItem, b: _NodeItem, pen: QPen):
        super().__init__()
        self.a = a
        self.b = b
        self.setPen(pen)
        self.setZValue(0)
        self.sync()

    def sync(self) -> None:
        pa, pb = self.a.pos(), self.b.pos()
        self.setLine(pa.x(), pa.y(), pb.x(), pb.y())


class _GraphScene(QGraphicsScene):
    """QGraphicsScene with a force-directed physics simulation."""

    node_name_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: list[_NodeItem] = []
        self._edges: list[_EdgeItem] = []
        self._labels: list[QGraphicsSimpleTextItem] = []
        self._names: list[str] = []
        self._adj_list: list[tuple[int, int]] = []

        # Theme colors — updated by apply_colors()
        self._node_brush  = QBrush(QColor("#89b4fa"))
        self._hover_brush = QBrush(QColor("#cba6f7"))
        self._node_pen    = QPen(QColor("#45475a"), 1.5)
        self._edge_pen    = QPen(QColor("#6c7086"), _EDGE_W)
        self._edge_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._label_color = QColor("#cdd6f4")

        self._timer = QTimer(self)
        self._timer.setInterval(_STEP_MS)
        self._timer.timeout.connect(self._physics_step)

    # ------------------------------------------------------------------
    # Public

    def populate(
        self,
        names: list[str],
        positions: np.ndarray,
        adj: list[tuple[int, int]],
        degrees: list[int],
    ) -> None:
        self._timer.stop()
        self.clear()
        self._nodes = []
        self._edges = []
        self._labels = []
        self._names = list(names)
        self._adj_list = list(adj)

        if not names:
            return

        label_font = QFont()
        label_font.setPointSize(9)

        for i, name in enumerate(names):
            r = _NODE_R + min(degrees[i] * 2.0, 14.0)
            node = _NodeItem(
                QPen(self._node_pen),
                QBrush(self._node_brush),
                QBrush(self._hover_brush),
                r,
            )
            node.setPos(positions[i, 0], positions[i, 1])
            node.setToolTip(name)
            self.addItem(node)
            self._nodes.append(node)

            lbl = QGraphicsSimpleTextItem(name)
            lbl.setFont(label_font)
            lbl.setBrush(QBrush(self._label_color))
            lbl.setZValue(1)
            lbl.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            lw = lbl.boundingRect().width()
            lbl.setPos(positions[i, 0] - lw / 2, positions[i, 1] + r + 3)
            self.addItem(lbl)
            self._labels.append(lbl)

        for u, v in adj:
            edge = _EdgeItem(self._nodes[u], self._nodes[v], QPen(self._edge_pen))
            self.addItem(edge)
            self._edges.append(edge)

        self._timer.start()

    def name_at(self, node: _NodeItem) -> str | None:
        try:
            return self._names[self._nodes.index(node)]
        except ValueError:
            return None

    def apply_colors(
        self,
        node_color: str,
        node_border: str,
        edge_color: str,
        label_color: str,
        hover_color: str,
    ) -> None:
        self._node_brush  = QBrush(QColor(node_color))
        self._hover_brush = QBrush(QColor(hover_color))
        self._node_pen    = QPen(QColor(node_border), 1.5)
        self._edge_pen    = QPen(QColor(edge_color), _EDGE_W)
        self._edge_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._label_color = QColor(label_color)
        for nd in self._nodes:
            nd.apply_colors(
                QPen(QColor(node_border), 1.5),
                QBrush(QColor(node_color)),
                QBrush(QColor(hover_color)),
            )
        for ed in self._edges:
            ed.setPen(QPen(self._edge_pen))
        for lbl in self._labels:
            lbl.setBrush(QBrush(self._label_color))

    # ------------------------------------------------------------------
    # Physics

    def _physics_step(self) -> None:
        n = len(self._nodes)
        if n < 2:
            return

        px = np.array([nd.pos().x() for nd in self._nodes])
        py = np.array([nd.pos().y() for nd in self._nodes])
        vx = np.array([nd.vx for nd in self._nodes])
        vy = np.array([nd.vy for nd in self._nodes])

        # Skip update when the system has settled and no node is being dragged
        if not any(nd.pinned for nd in self._nodes):
            if np.max(np.sqrt(vx ** 2 + vy ** 2)) < _SETTLE_V:
                return

        # Charge repulsion — all pairs (vectorised)
        dx = px[:, None] - px[None, :]   # (n, n): dx[i,j] = px[i] - px[j]
        dy = py[:, None] - py[None, :]
        dist2 = dx ** 2 + dy ** 2
        np.fill_diagonal(dist2, 1.0)     # avoid self-division
        dist = np.sqrt(dist2)
        force = _K_REPEL / dist2
        fx = np.sum(force * dx / dist, axis=1)
        fy = np.sum(force * dy / dist, axis=1)

        # Spring attraction — connected pairs
        for u, v in self._adj_list:
            ddx = px[v] - px[u]
            ddy = py[v] - py[u]
            d = math.sqrt(ddx * ddx + ddy * ddy) or 1.0
            s = _K_SPRING * (d - _REST_LEN) / d
            fx[u] += s * ddx
            fy[u] += s * ddy
            fx[v] -= s * ddx
            fy[v] -= s * ddy

        # Centre gravity
        fx -= _K_GRAVITY * px
        fy -= _K_GRAVITY * py

        # Integrate
        vx = (vx + fx) * _DAMPING
        vy = (vy + fy) * _DAMPING
        np.clip(vx, -_MAX_VEL, _MAX_VEL, out=vx)
        np.clip(vy, -_MAX_VEL, _MAX_VEL, out=vy)

        for i, nd in enumerate(self._nodes):
            if nd.pinned:
                nd.vx = 0.0
                nd.vy = 0.0
            else:
                nd.vx = float(vx[i])
                nd.vy = float(vy[i])
                nd.setPos(px[i] + nd.vx, py[i] + nd.vy)
                lbl = self._labels[i]
                lw = lbl.boundingRect().width()
                lbl.setPos(nd.pos().x() - lw / 2, nd.pos().y() + nd._radius + 3)

        for ed in self._edges:
            ed.sync()


class _GraphView(QGraphicsView):
    """Zoomable, pannable view for _GraphScene."""

    def __init__(self, scene: _GraphScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor("#1e1e2e")))
        self.setFrameShape(self.Shape.NoFrame)
        self._panning = False
        self._press_pos = QPointF()

    def wheelEvent(self, ev) -> None:
        factor = 1.15 if ev.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, ev) -> None:
        is_middle = ev.button() == Qt.MouseButton.MiddleButton
        is_left_empty = (
            ev.button() == Qt.MouseButton.LeftButton
            and self.itemAt(ev.pos()) is None
        )
        if is_middle or is_left_empty:
            self._panning = True
            self._press_pos = ev.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            ev.accept()
        else:
            self._press_pos = ev.position()
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:
        if self._panning:
            delta = ev.position() - self._press_pos
            self._press_pos = ev.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        if self._panning and ev.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        ):
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            ev.accept()
        else:
            if ev.button() == Qt.MouseButton.LeftButton:
                item = self.itemAt(ev.pos())
                if isinstance(item, _NodeItem):
                    moved = (ev.position() - self._press_pos).manhattanLength()
                    if moved < 6:
                        scene: _GraphScene = self.scene()  # type: ignore[assignment]
                        name = scene.name_at(item)
                        if name:
                            scene.node_name_clicked.emit(name)
            super().mouseReleaseEvent(ev)


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

        # These three attributes are kept for test compatibility
        self._names: list[str] = []
        self._adj: np.ndarray = np.empty((0, 2), dtype=int)
        self._pos: np.ndarray = np.empty((0, 2), dtype=float)

        self._scene = _GraphScene()
        self._scene.node_name_clicked.connect(self.node_clicked)
        self._view = _GraphView(self._scene)

        self.setWidget(self._view)
        self._apply_plot_theme()
        self.refresh()

    # ------------------------------------------------------------------
    # Public

    def refresh(self) -> None:
        """Rebuild the graph from the current store + link_index state."""
        self._names = list(self._store.all_names())

        if not self._names:
            self._adj = np.empty((0, 2), dtype=int)
            self._pos = np.empty((0, 2), dtype=float)
            self._scene.populate([], np.empty((0, 2), dtype=float), [], [])
            return

        G = nx.Graph()
        G.add_nodes_from(self._names)
        name_set = set(self._names)
        name_to_idx = {n: i for i, n in enumerate(self._names)}

        seen: set[frozenset] = set()
        edge_list: list[list[int]] = []
        for name in self._names:
            for target in self._link_index.links_from(name):
                if target not in name_set:
                    continue
                key = frozenset((name, target))
                if key not in seen:
                    seen.add(key)
                    edge_list.append([name_to_idx[name], name_to_idx[target]])
                    G.add_edge(name, target)

        pos_map = nx.spring_layout(G, seed=42, k=1.5)
        pos = np.array([pos_map[n] for n in self._names], dtype=float) * _SCALE

        self._pos = pos
        self._adj = (
            np.array(edge_list, dtype=int)
            if edge_list
            else np.empty((0, 2), dtype=int)
        )

        degrees = [G.degree(n) for n in self._names]
        self._scene.populate(
            self._names,
            pos,
            [(e[0], e[1]) for e in edge_list],
            degrees,
        )

    def update_theme(self, theme_path: str) -> None:
        self._apply_colors(self._load_theme_colors(theme_path))
        bg = self._load_theme_colors(theme_path).get("background", "#1e1e2e")
        self._view.setBackgroundBrush(QBrush(QColor(bg)))

    # ------------------------------------------------------------------
    # Backward-compat (test_graph_view.py calls this directly)

    def _on_node_clicked(self, _plot_item, spots, _ev) -> None:
        if not spots:
            return
        p = spots[0].pos()
        clicked = np.array([p.x(), p.y()])
        if self._pos.shape[0] == 0:
            return
        dists = np.linalg.norm(self._pos - clicked, axis=1)
        self.node_clicked.emit(self._names[int(np.argmin(dists))])

    # ------------------------------------------------------------------
    # Theme

    def _apply_plot_theme(self) -> None:
        try:
            theme_path = str(config.resolve("theme", "themes/dark_default.toml"))
        except KeyError:
            return
        colors = self._load_theme_colors(theme_path)
        self._apply_colors(colors)
        bg = colors.get("background", "#1e1e2e")
        self._view.setBackgroundBrush(QBrush(QColor(bg)))

    def _load_theme_colors(self, theme_path: str) -> dict:
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
            return colors
        except ThemeLoadError:
            return {}

    def _apply_colors(self, colors: dict) -> None:
        self._scene.apply_colors(
            node_color=colors.get("accent",     "#89b4fa"),
            node_border=colors.get("border",    "#45475a"),
            edge_color=colors.get("text_muted", "#6c7086"),
            label_color=colors.get("text",      "#cdd6f4"),
            hover_color=colors.get("primary",   "#cba6f7"),
        )
