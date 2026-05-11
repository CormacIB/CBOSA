from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget
from PyQt6.QtCore import pyqtSignal

from cbosa.ui.panels import PanelRegistry


class CommandPalette(QDialog):
    """Overlay dialog that lists available panel types for the user to add."""

    panel_selected = pyqtSignal(str)

    def __init__(self, registry: PanelRegistry, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Panel")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search panels...")
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        for name in registry.all_names():
            self.list_widget.addItem(name)
        layout.addWidget(self.list_widget)

        self.search_box.textChanged.connect(self._filter)
        self.list_widget.itemDoubleClicked.connect(self._select)
        self.list_widget.itemActivated.connect(self._select)

    def _filter(self, text: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _select(self, item) -> None:
        self.panel_selected.emit(item.text())
        self.accept()
