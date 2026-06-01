"""
MainWindow — the top-level application window.
Hosts the panel system via CDockManager (Issue #17).

Panels are CDockWidget instances (BasePanel subclasses) managed entirely by
CDockManager, which is set as the central widget.  This gives 2-D tiling,
tab groups, and floating windows out of the box.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import QByteArray, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PyQt6Ads import CDockManager, DockWidgetArea

from cbosa import config
from cbosa.ui.banner import BannerWidget
from cbosa.ui.panels import PanelRegistry, default_registry
from cbosa.ui.command_palette import CommandPalette
from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError


_DEFAULT_LAYOUT_PATH = Path.home() / ".cbosa" / "layout.json"

_THEMES = [
    ("Obsidian Dark", "themes/obsidian_dark.toml"),
    ("Terminal",      "themes/terminal.toml"),
    ("Light",         "themes/light.toml"),
]


class MainWindow(QMainWindow):
    theme_changed = pyqtSignal(str)  # emits absolute theme path

    def __init__(
        self,
        registry: PanelRegistry | None = None,
        layout_path: Path | str | None = None,
        ai_available: bool = True,
        timer_store=None,
    ) -> None:
        super().__init__()
        self._registry = registry or default_registry
        self._layout_path = Path(layout_path) if layout_path else _DEFAULT_LAYOUT_PATH
        self._open_panels: list[str] = []
        self._panel_instances: dict[str, object] = {}
        self._current_theme_rel: str = config.get("theme", "themes/obsidian_dark.toml")

        self.setWindowTitle("CBOSA")
        self.resize(1280, 800)

        # Container: banner on top, dock manager below
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self._banner = BannerWidget(container, timer_store=timer_store)
        container_layout.addWidget(self._banner)

        self._dock_manager = CDockManager(container)
        container_layout.addWidget(self._dock_manager)

        self.setCentralWidget(container)

        self._setup_menu_bar()
        self._setup_status_bar(ai_available)

        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(
            self.open_command_palette
        )
        QShortcut(QKeySequence("Ctrl+Shift+T"), self).activated.connect(
            self._cycle_theme
        )

        self._restore_layout()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def open_command_palette(self) -> None:
        palette = CommandPalette(self._registry, self)
        palette.panel_selected.connect(self.add_panel)
        palette.exec()

    def add_panel(self, name: str) -> None:
        if name in self._panel_instances:
            return
        cls = self._registry.get(name)
        if cls is None:
            return
        panel = cls(name, self)
        self._panel_instances[name] = panel
        self._wire_panels(name, panel)
        self._dock_manager.addDockWidget(DockWidgetArea.RightDockWidgetArea, panel)
        self._open_panels.append(name)
        panel.closed.connect(lambda n=name: self._remove_panel(n))

    def _create_panel(self, name: str):
        """Create, register, and wire a panel without docking it. Returns the panel or None."""
        if name in self._panel_instances:
            return self._panel_instances[name]
        cls = self._registry.get(name)
        if cls is None:
            return None
        panel = cls(name, self)
        self._panel_instances[name] = panel
        self._wire_panels(name, panel)
        self._open_panels.append(name)
        panel.closed.connect(lambda n=name: self._remove_panel(n))
        return panel

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._save_layout()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Private — setup
    # ------------------------------------------------------------------

    def _setup_menu_bar(self) -> None:
        theme_menu = self.menuBar().addMenu("Theme")
        group = QActionGroup(self)
        group.setExclusive(True)
        current_abs = str(config.resolve("theme", "themes/obsidian_dark.toml"))

        for label, rel_path in _THEMES:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(rel_path)
            action.setChecked(
                str(config.PROJECT_ROOT / rel_path) == current_abs
            )
            action.triggered.connect(
                lambda checked, p=rel_path: self._switch_theme(p)
            )
            group.addAction(action)
            theme_menu.addAction(action)

        self._theme_action_group = group

    def _setup_status_bar(self, ai_available: bool) -> None:
        self._ai_status_label = QLabel()
        self._set_ai_status(ai_available)
        self.statusBar().addWidget(self._ai_status_label)

    def _set_ai_status(self, available: bool) -> None:
        if available:
            self._ai_status_label.setText("● AI: connected")
            self._ai_status_label.setStyleSheet("color: #a6e3a1;")
        else:
            self._ai_status_label.setText("● AI: offline")
            self._ai_status_label.setStyleSheet("color: #f38ba8;")

    # ------------------------------------------------------------------
    # Private — theme switching
    # ------------------------------------------------------------------

    def _switch_theme(self, rel_path: str) -> None:
        full_path = str(config.PROJECT_ROOT / rel_path)
        try:
            ThemeEngine().apply(QApplication.instance(), full_path)
        except ThemeLoadError as exc:
            print(f"[CBOSA] Theme load error: {exc}")
            return
        config.save_theme(rel_path)
        self._current_theme_rel = rel_path
        for action in self._theme_action_group.actions():
            action.setChecked(action.data() == rel_path)
        self._banner.update_theme_name(rel_path)
        self.theme_changed.emit(full_path)

    def _cycle_theme(self) -> None:
        paths = [rel for _, rel in _THEMES]
        try:
            idx = paths.index(self._current_theme_rel)
        except ValueError:
            idx = -1
        self._switch_theme(paths[(idx + 1) % len(paths)])

    # ------------------------------------------------------------------
    # Private — panels
    # ------------------------------------------------------------------

    def _remove_panel(self, name: str) -> None:
        panel = self._panel_instances.pop(name, None)
        if panel is not None:
            self._dock_manager.removeDockWidget(panel)
        if name in self._open_panels:
            self._open_panels.remove(name)

    def _wire_panels(self, name: str, panel) -> None:
        if name == "Note Browser":
            panel.note_selected.connect(self._on_note_selected)
            editor = self._panel_instances.get("Note Editor")
            if editor is not None:
                panel.note_deleted.connect(editor.clear_if_current)
        if name == "Note Editor":
            panel.note_link_activated.connect(self._on_note_selected)
            panel.ask_ai_requested.connect(self._on_ask_ai)
            self.theme_changed.connect(panel.update_theme)
            graph = self._panel_instances.get("Graph View")
            if graph is not None:
                panel.note_saved.connect(lambda _: graph.refresh())
        if name == "Chat":
            editor = self._panel_instances.get("Note Editor")
            if editor is not None:
                editor.ask_ai_requested.connect(panel.set_note_context)
            self.theme_changed.connect(panel.update_theme)
        if name == "Graph View":
            panel.node_clicked.connect(self._on_note_selected)
            editor = self._panel_instances.get("Note Editor")
            if editor is not None:
                editor.note_saved.connect(lambda _: panel.refresh())
        if name == "Finance Summary":
            self.theme_changed.connect(panel.update_theme)

    def _on_ask_ai(self, title: str, content: str) -> None:
        if "Chat" not in self._panel_instances:
            self.add_panel("Chat")
        chat = self._panel_instances.get("Chat")
        if chat is not None:
            chat.set_note_context(title, content)

    def _on_note_selected(self, note_name: str) -> None:
        if "Note Editor" not in self._panel_instances:
            self.add_panel("Note Editor")
        editor = self._panel_instances.get("Note Editor")
        if editor is not None:
            editor.open_note(note_name)
        browser = self._panel_instances.get("Note Browser")
        if browser is not None:
            browser.select_note(note_name)

    def _save_layout(self) -> None:
        self._layout_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "panels": list(self._open_panels),
            "dock_state": self._dock_manager.saveState().toBase64().data().decode(),
        }
        self._layout_path.write_text(json.dumps(data), encoding="utf-8")

    def _restore_layout(self) -> None:
        if not self._layout_path.exists():
            self._create_default_layout()
            return
        try:
            data = json.loads(self._layout_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._create_default_layout()
            return
        for name in data.get("panels", []):
            self.add_panel(name)
        dock_state = data.get("dock_state")
        if dock_state:
            try:
                self._dock_manager.restoreState(
                    QByteArray.fromBase64(dock_state.encode())
                )
            except Exception:
                pass  # corrupted state — panel positions reset, not a crash

    def _create_default_layout(self) -> None:
        """Pre-dock Note Browser (left), Note Editor (center), Tasks + Finance Summary (right)."""
        # Left: Note Browser
        browser = self._create_panel("Note Browser")
        if browser:
            self._dock_manager.addDockWidget(DockWidgetArea.LeftDockWidgetArea, browser)

        # Center: Note Editor
        editor = self._create_panel("Note Editor")
        if editor:
            self._dock_manager.addDockWidget(DockWidgetArea.CenterDockWidgetArea, editor)

        # Right column: Tasks on top
        tasks = self._create_panel("Tasks")
        if tasks:
            self._dock_manager.addDockWidget(DockWidgetArea.RightDockWidgetArea, tasks)

        # Right column: Finance Summary below Tasks
        summary = self._create_panel("Finance Summary")
        if summary and tasks:
            tasks_area = tasks.dockAreaWidget()
            if tasks_area is not None:
                self._dock_manager.addDockWidget(
                    DockWidgetArea.BottomDockWidgetArea, summary, tasks_area
                )
            else:
                self._dock_manager.addDockWidget(DockWidgetArea.RightDockWidgetArea, summary)
