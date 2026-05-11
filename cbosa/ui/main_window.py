"""
MainWindow — the top-level application window.
Hosts the QDockWidget panel system (Issue #2).
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QLabel
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QKeySequence, QShortcut

from cbosa.ui.panels import PanelRegistry, default_registry
from cbosa.ui.command_palette import CommandPalette

_DEFAULT_LAYOUT_PATH = Path.home() / ".cbosa" / "layout.json"


class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: PanelRegistry | None = None,
        layout_path: Path | str | None = None,
    ) -> None:
        super().__init__()
        self._registry = registry or default_registry
        self._layout_path = Path(layout_path) if layout_path else _DEFAULT_LAYOUT_PATH
        self._open_panels: list[str] = []
        self._panel_instances: dict[str, object] = {}

        self.setWindowTitle("CBOSA")
        self.resize(1280, 800)

        self._placeholder = QLabel(
            "Press Ctrl+P to add a panel",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._placeholder.setProperty("muted", "true")
        self.setCentralWidget(self._placeholder)

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
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, panel)
        self._open_panels.append(name)
        panel.closed.connect(lambda: self._remove_panel(panel, name))
        self._placeholder.setVisible(not self._open_panels)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._save_layout()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _remove_panel(self, panel: "BasePanel", name: str) -> None:
        self.removeDockWidget(panel)
        panel.setParent(None)
        if name in self._open_panels:
            self._open_panels.remove(name)
        self._panel_instances.pop(name, None)
        self._placeholder.setVisible(not self._open_panels)

    def _wire_panels(self, name: str, panel) -> None:
        if name == "Note Browser":
            panel.note_selected.connect(self._on_note_selected)
            editor = self._panel_instances.get("Note Editor")
            if editor is not None:
                panel.note_deleted.connect(editor.clear_if_current)

    def _on_note_selected(self, note_name: str) -> None:
        if "Note Editor" not in self._panel_instances:
            self.add_panel("Note Editor")
        editor = self._panel_instances.get("Note Editor")
        if editor is not None:
            editor.open_note(note_name)

    def _save_layout(self) -> None:
        self._layout_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "panels": list(self._open_panels),
            "qt_state": self.saveState().toBase64().data().decode(),
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
        qt_state = data.get("qt_state")
        if qt_state:
            try:
                self.restoreState(QByteArray.fromBase64(qt_state.encode()))
            except Exception:
                pass  # corrupted state — panel positions reset, not a crash
