from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from PyQt6Ads import CDockWidget


class BasePanel(CDockWidget):
    """Shared base for all dockable panels.

    Uses CDockWidget (PyQt6Ads) instead of QDockWidget, enabling 2-D tiling,
    tab groups, and floating windows via CDockManager (wired in Issue #17).
    The ``closed`` signal is inherited directly from CDockWidget.
    """

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(title, parent)
        self.setWidget(QWidget())


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
