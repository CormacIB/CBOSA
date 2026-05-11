from __future__ import annotations

from PyQt6.QtWidgets import QDockWidget, QWidget
from PyQt6.QtCore import Qt, pyqtSignal


class BasePanel(QDockWidget):
    """Shared base for all dockable panels."""

    closed = pyqtSignal()

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(title, parent)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setWidget(QWidget())

    def closeEvent(self, event) -> None:
        self.closed.emit()
        event.accept()


class PanelRegistry:
    """Maps panel type names to their BasePanel subclasses."""

    def __init__(self) -> None:
        self._panels: dict[str, type[BasePanel]] = {}

    def register(self, name: str, panel_cls: type[BasePanel]) -> None:
        self._panels[name] = panel_cls

    def get(self, name: str) -> type[BasePanel] | None:
        return self._panels.get(name)

    def all_names(self) -> list[str]:
        return list(self._panels.keys())


default_registry = PanelRegistry()
