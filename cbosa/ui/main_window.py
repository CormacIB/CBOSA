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

from PyQt6.QtWidgets import QLabel, QMainWindow
from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6Ads import CDockManager, DockWidgetArea

from cbosa.ui.panels import PanelRegistry, default_registry
from cbosa.ui.command_palette import CommandPalette


_DEFAULT_LAYOUT_PATH = Path.home() / ".cbosa" / "layout.json"


class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: PanelRegistry | None = None,
        layout_path: Path | str | None = None,
        ai_available: bool = True,
    ) -> None:
        super().__init__()
        self._registry = registry or default_registry
        self._layout_path = Path(layout_path) if layout_path else _DEFAULT_LAYOUT_PATH
        self._open_panels: list[str] = []
        self._panel_instances: dict[str, object] = {}

        self.setWindowTitle("CBOSA")
        self.resize(1280, 800)

        self._dock_manager = CDockManager(self)
        self.setCentralWidget(self._dock_manager)

        if not ai_available:
            label = QLabel("AI unavailable — Ollama not reachable")
            self.statusBar().addPermanentWidget(label)

        shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        shortcut.activated.connect(self.open_command_palette)

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

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._save_layout()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Private
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
            graph = self._panel_instances.get("Graph View")
            if graph is not None:
                panel.note_saved.connect(lambda _: graph.refresh())
        if name == "Graph View":
            panel.node_clicked.connect(self._on_note_selected)
            editor = self._panel_instances.get("Note Editor")
            if editor is not None:
                editor.note_saved.connect(lambda _: panel.refresh())

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
            return
        try:
            data = json.loads(self._layout_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
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
