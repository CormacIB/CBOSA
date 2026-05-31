"""
TimerPanel — self-contained dockable countdown timer.

Layout:
  - Circular arc showing time remaining (primary colour → accent when over)
  - Group chips → expands to category chips below the arc
  - Duration spinner (global default, editable before start)
  - Start / Stop controls
  - "Edit Categories" button → modal dialog

All colours come from the active theme via _load_theme_colors().
"""
from __future__ import annotations

import math
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from cbosa import config
from cbosa.core.timer_store import (
    DuplicateGroupError,
    TimerStore,
    TimerStoreError,
)
from cbosa.ui.panels import BasePanel

_DEFAULT_DURATION_SECONDS = 25 * 60


def _load_theme_colors() -> dict:
    from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
    try:
        theme_path = str(config.resolve("theme", "themes/dark_default.toml"))
        colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
        return colors
    except (ThemeLoadError, KeyError):
        return {}


# ---------------------------------------------------------------------------
# Arc widget
# ---------------------------------------------------------------------------

class _ArcWidget(QWidget):
    """Circular countdown arc drawn with QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._total: int = _DEFAULT_DURATION_SECONDS
        self._elapsed: int = 0
        self._running: bool = False
        self._colors: dict = {}
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_state(self, total: int, elapsed: int, running: bool) -> None:
        self._total = max(total, 1)
        self._elapsed = elapsed
        self._running = running
        self.update()

    def set_colors(self, colors: dict) -> None:
        self._colors = colors
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        size = min(W, H) - 20
        x = (W - size) // 2
        y = (H - size) // 2

        bg     = self._colors.get("background", "#1e1e2e")
        surface = self._colors.get("surface",   "#313244")
        primary = self._colors.get("primary",   "#cba6f7")
        accent  = self._colors.get("accent",    "#89b4fa")
        text    = self._colors.get("text",      "#cdd6f4")

        p.fillRect(0, 0, W, H, QColor(bg))

        # Track ring (background arc)
        pen = QPen(QColor(surface), 12)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(x, y, size, size, 0, 360 * 16)

        # Foreground arc
        over = self._elapsed > self._total
        arc_color = QColor(accent if over else primary)
        pen2 = QPen(arc_color, 12)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)

        if over:
            # Pulse the accent ring: full circle when over
            p.drawArc(x, y, size, size, 90 * 16, -360 * 16)
        else:
            remaining = self._total - self._elapsed
            span = int((remaining / self._total) * 360 * 16)
            p.drawArc(x, y, size, size, 90 * 16, span)

        # Centre text
        remaining_s = max(self._total - self._elapsed, 0) if not over else self._elapsed - self._total
        if over:
            label = f"+{remaining_s // 60:02d}:{remaining_s % 60:02d}"
            colour = QColor(accent)
        else:
            label = f"{remaining_s // 60:02d}:{remaining_s % 60:02d}"
            colour = QColor(text)

        font = QFont("Helvetica Neue", 28 if size > 160 else 20)
        font.setBold(True)
        p.setFont(font)
        p.setPen(colour)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(label)
        p.drawText(W // 2 - tw // 2, H // 2 + fm.ascent() // 2, label)

        p.end()


# ---------------------------------------------------------------------------
# TimerPanel
# ---------------------------------------------------------------------------

class TimerPanel(BasePanel):
    """Self-contained dockable countdown timer with group/category chips."""

    def __init__(self, timer_store: TimerStore, title: str = "Timer", parent=None) -> None:
        super().__init__(title, parent)
        self._store = timer_store
        self._colors: dict = {}

        self._total_seconds: int = _DEFAULT_DURATION_SECONDS
        self._elapsed_seconds: int = 0
        self._start_time: datetime | None = None
        self._selected_group_id: int | None = None
        self._selected_category_id: int | None = None

        self._tick_timer = QTimer()
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._apply_theme()
        self._refresh_groups()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Arc
        self._arc = _ArcWidget()
        layout.addWidget(self._arc, stretch=1)

        # Duration row
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (min):"))
        self._duration_spin = QSpinBox()
        self._duration_spin.setObjectName("timer_duration_spin")
        self._duration_spin.setRange(1, 480)
        self._duration_spin.setValue(_DEFAULT_DURATION_SECONDS // 60)
        self._duration_spin.valueChanged.connect(self._on_duration_changed)
        dur_row.addWidget(self._duration_spin)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        # Group chips
        self._group_scroll = QScrollArea()
        self._group_scroll.setWidgetResizable(True)
        self._group_scroll.setFixedHeight(44)
        self._group_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._group_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._group_chip_container = QWidget()
        self._group_chip_layout = QHBoxLayout(self._group_chip_container)
        self._group_chip_layout.setContentsMargins(0, 0, 0, 0)
        self._group_chip_layout.setSpacing(4)
        self._group_chip_layout.addStretch()
        self._group_scroll.setWidget(self._group_chip_container)
        layout.addWidget(self._group_scroll)

        # Category chips
        self._cat_scroll = QScrollArea()
        self._cat_scroll.setWidgetResizable(True)
        self._cat_scroll.setFixedHeight(44)
        self._cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cat_chip_container = QWidget()
        self._cat_chip_layout = QHBoxLayout(self._cat_chip_container)
        self._cat_chip_layout.setContentsMargins(0, 0, 0, 0)
        self._cat_chip_layout.setSpacing(4)
        self._cat_chip_layout.addStretch()
        self._cat_scroll.setWidget(self._cat_chip_container)
        layout.addWidget(self._cat_scroll)

        # Controls row
        ctrl_row = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("timer_start_btn")
        self._start_btn.clicked.connect(self._on_start_stop)
        ctrl_row.addWidget(self._start_btn)

        edit_btn = QPushButton("Edit Categories")
        edit_btn.setObjectName("timer_edit_btn")
        edit_btn.clicked.connect(self._on_edit_categories)
        ctrl_row.addWidget(edit_btn)
        layout.addLayout(ctrl_row)

        self.setWidget(root)

    # ------------------------------------------------------------------
    # Chip management
    # ------------------------------------------------------------------

    def _clear_layout(self, layout: QHBoxLayout) -> None:
        while layout.count() > 1:  # keep trailing stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_groups(self) -> None:
        self._clear_layout(self._group_chip_layout)
        groups = self._store.list_groups()
        for g in groups:
            btn = QPushButton(g["name"])
            btn.setObjectName("timer_group_chip")
            btn.setCheckable(True)
            btn.setProperty("group_id", g["id"])
            btn.clicked.connect(lambda checked, gid=g["id"], b=btn: self._on_group_chip(gid, b))
            self._group_chip_layout.insertWidget(self._group_chip_layout.count() - 1, btn)

        # Restore last selection if still valid
        if self._selected_group_id is not None:
            gid = self._selected_group_id
            if any(g["id"] == gid for g in groups):
                self._select_group_chip(gid)
            else:
                self._selected_group_id = None
                self._selected_category_id = None
                self._refresh_categories()

    def _on_group_chip(self, group_id: int, btn: QPushButton) -> None:
        # Uncheck all other group chips
        for i in range(self._group_chip_layout.count()):
            w = self._group_chip_layout.itemAt(i).widget()
            if isinstance(w, QPushButton) and w is not btn:
                w.setChecked(False)
        self._selected_group_id = group_id
        self._selected_category_id = None
        self._refresh_categories()

    def _select_group_chip(self, group_id: int) -> None:
        for i in range(self._group_chip_layout.count()):
            w = self._group_chip_layout.itemAt(i).widget()
            if isinstance(w, QPushButton):
                w.setChecked(w.property("group_id") == group_id)
        self._refresh_categories()

    def _refresh_categories(self) -> None:
        self._clear_layout(self._cat_chip_layout)
        if self._selected_group_id is None:
            return
        cats = self._store.list_categories(self._selected_group_id)
        for c in cats:
            btn = QPushButton(c["name"])
            btn.setObjectName("timer_cat_chip")
            btn.setCheckable(True)
            btn.setProperty("category_id", c["id"])
            btn.clicked.connect(lambda checked, cid=c["id"], b=btn: self._on_cat_chip(cid, b))
            self._cat_chip_layout.insertWidget(self._cat_chip_layout.count() - 1, btn)

        if self._selected_category_id is not None:
            cid = self._selected_category_id
            if any(c["id"] == cid for c in cats):
                for i in range(self._cat_chip_layout.count()):
                    w = self._cat_chip_layout.itemAt(i).widget()
                    if isinstance(w, QPushButton) and w.property("category_id") == cid:
                        w.setChecked(True)
            else:
                self._selected_category_id = None

    def _on_cat_chip(self, category_id: int, btn: QPushButton) -> None:
        for i in range(self._cat_chip_layout.count()):
            w = self._cat_chip_layout.itemAt(i).widget()
            if isinstance(w, QPushButton) and w is not btn:
                w.setChecked(False)
        self._selected_category_id = category_id

    # ------------------------------------------------------------------
    # Timer logic
    # ------------------------------------------------------------------

    def _on_duration_changed(self, minutes: int) -> None:
        if not self._tick_timer.isActive():
            self._total_seconds = minutes * 60
            self._elapsed_seconds = 0
            self._arc.set_state(self._total_seconds, 0, False)

    def _on_start_stop(self) -> None:
        if self._tick_timer.isActive():
            self._stop_timer()
        else:
            self._start_timer()

    def _start_timer(self) -> None:
        if self._selected_category_id is None:
            return
        self._total_seconds = self._duration_spin.value() * 60
        self._elapsed_seconds = 0
        self._start_time = datetime.now()
        self._tick_timer.start()
        self._start_btn.setText("Stop")
        self._duration_spin.setEnabled(False)
        self._arc.set_state(self._total_seconds, 0, True)

    def _stop_timer(self) -> None:
        self._tick_timer.stop()
        end_time = datetime.now()
        self._start_btn.setText("Start")
        self._duration_spin.setEnabled(True)

        if self._start_time and self._selected_category_id is not None:
            start_str = self._start_time.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")
            try:
                self._store.log_session(
                    self._selected_category_id, start_str, end_str
                )
            except TimerStoreError:
                pass  # session too short or invalid — discard silently

        self._start_time = None
        self._elapsed_seconds = 0
        self._arc.set_state(self._total_seconds, 0, False)

    def _on_tick(self) -> None:
        self._elapsed_seconds += 1
        self._arc.set_state(self._total_seconds, self._elapsed_seconds, True)

    # ------------------------------------------------------------------
    # Edit categories dialog
    # ------------------------------------------------------------------

    def _on_edit_categories(self) -> None:
        dlg = _EditCategoriesDialog(self._store, parent=self)
        dlg.exec()
        self._refresh_groups()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        self._colors = _load_theme_colors()
        self._arc.set_colors(self._colors)

    def update_theme(self, theme_path: str) -> None:
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
            self._colors = colors
            self._arc.set_colors(colors)
        except ThemeLoadError:
            pass


# ---------------------------------------------------------------------------
# Edit Categories dialog
# ---------------------------------------------------------------------------

class _EditCategoriesDialog(QDialog):
    """Modal dialog for managing groups and their child categories."""

    def __init__(self, store: TimerStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Categories")
        self.setMinimumSize(500, 380)
        self._store = store
        self._selected_group_id: int | None = None
        self._build_ui()
        self._refresh_groups()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        # Left: groups
        left = QVBoxLayout()
        left.addWidget(QLabel("Groups"))
        self._group_list = QListWidget()
        self._group_list.currentRowChanged.connect(self._on_group_selected)
        left.addWidget(self._group_list)

        grp_btns = QHBoxLayout()
        add_g = QPushButton("Add")
        add_g.clicked.connect(self._on_add_group)
        ren_g = QPushButton("Rename")
        ren_g.clicked.connect(self._on_rename_group)
        del_g = QPushButton("Delete")
        del_g.clicked.connect(self._on_delete_group)
        grp_btns.addWidget(add_g)
        grp_btns.addWidget(ren_g)
        grp_btns.addWidget(del_g)
        left.addLayout(grp_btns)

        # Right: categories
        right = QVBoxLayout()
        right.addWidget(QLabel("Categories"))
        self._cat_list = QListWidget()
        right.addWidget(self._cat_list)

        cat_btns = QHBoxLayout()
        add_c = QPushButton("Add")
        add_c.clicked.connect(self._on_add_category)
        ren_c = QPushButton("Rename")
        ren_c.clicked.connect(self._on_rename_category)
        del_c = QPushButton("Delete")
        del_c.clicked.connect(self._on_delete_category)
        cat_btns.addWidget(add_c)
        cat_btns.addWidget(ren_c)
        cat_btns.addWidget(del_c)
        right.addLayout(cat_btns)

        layout.addLayout(left)
        layout.addLayout(right)

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)

        outer = QVBoxLayout()
        outer.addLayout(layout)
        outer.addWidget(close_btn)
        self.setLayout(outer)

    # -- Groups --

    def _refresh_groups(self) -> None:
        self._group_list.clear()
        for g in self._store.list_groups():
            item = QListWidgetItem(g["name"])
            item.setData(Qt.ItemDataRole.UserRole, g["id"])
            self._group_list.addItem(item)

    def _on_group_selected(self, row: int) -> None:
        item = self._group_list.item(row)
        if item:
            self._selected_group_id = item.data(Qt.ItemDataRole.UserRole)
            self._refresh_categories()
        else:
            self._selected_group_id = None
            self._cat_list.clear()

    def _on_add_group(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Group", "Group name:")
        if ok and name.strip():
            try:
                self._store.add_group(name.strip())
                self._refresh_groups()
            except DuplicateGroupError:
                pass

    def _on_rename_group(self) -> None:
        item = self._group_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        name, ok = QInputDialog.getText(self, "Rename Group", "New name:", text=item.text())
        if ok and name.strip():
            try:
                self._store.rename_group(gid, name.strip())
                self._refresh_groups()
            except TimerStoreError:
                pass

    def _on_delete_group(self) -> None:
        item = self._group_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        try:
            self._store.delete_group(gid)
            self._refresh_groups()
            self._cat_list.clear()
        except TimerStoreError:
            pass

    # -- Categories --

    def _refresh_categories(self) -> None:
        self._cat_list.clear()
        if self._selected_group_id is None:
            return
        for c in self._store.list_categories(self._selected_group_id):
            item = QListWidgetItem(c["name"])
            item.setData(Qt.ItemDataRole.UserRole, c["id"])
            self._cat_list.addItem(item)

    def _on_add_category(self) -> None:
        if self._selected_group_id is None:
            return
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name.strip():
            try:
                self._store.add_category(self._selected_group_id, name.strip())
                self._refresh_categories()
            except TimerStoreError:
                pass

    def _on_rename_category(self) -> None:
        item = self._cat_list.currentItem()
        if not item:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=item.text())
        if ok and name.strip():
            try:
                self._store.rename_category(cid, name.strip())
                self._refresh_categories()
            except TimerStoreError:
                pass

    def _on_delete_category(self) -> None:
        item = self._cat_list.currentItem()
        if not item:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        try:
            self._store.delete_category(cid)
            self._refresh_categories()
        except TimerStoreError:
            pass
