"""
NoteBrowserPanel — dockable panel showing the notes folder tree with tag filtering.
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.note_store import NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.panels import BasePanel


class NoteBrowserPanel(BasePanel):
    note_selected = pyqtSignal(str)
    note_created = pyqtSignal(str)
    note_deleted = pyqtSignal(str)

    def __init__(
        self,
        store: NoteStore,
        tag_index: TagIndex,
        search_index: SearchIndex,
        title: str = "Note Browser",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._tag_index = tag_index
        self._search_index = search_index
        self._tag_filter: str | None = None
        self._search_query: str = ""

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search notes…")
        self._search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_box)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Tag:"))
        self._tag_combo = QComboBox()
        self._tag_combo.addItem("")
        self._tag_combo.currentTextChanged.connect(self._on_tag_changed)
        filter_row.addWidget(self._tag_combo, stretch=1)
        layout.addLayout(filter_row)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New Note")
        new_btn.clicked.connect(self._prompt_create_note)
        btn_row.addWidget(new_btn)

        self._delete_btn = QPushButton("Delete Note")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected_note)
        btn_row.addWidget(self._delete_btn)

        layout.addLayout(btn_row)

        self.setWidget(container)
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._tag_index.rebuild()
        self._search_index.rebuild()
        self._refresh_tag_combo()
        self._list.clear()
        for name in self._visible_names():
            self._list.addItem(QListWidgetItem(name))

    def set_tag_filter(self, tag: str) -> None:
        self._tag_filter = tag or None
        self.refresh()

    def clear_tag_filter(self) -> None:
        self._tag_filter = None
        self.refresh()

    def set_search_query(self, query: str) -> None:
        self._search_query = query.strip()
        self.refresh()

    def create_note(self, name: str) -> None:
        self._store.create(name, "")
        self.refresh()
        self.note_created.emit(name)

    def delete_note(self, name: str) -> None:
        self._store.delete(name)
        self.refresh()
        self.note_deleted.emit(name)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _visible_names(self) -> list[str]:
        if self._search_query:
            search_hits: set[str] | None = set(self._search_index.search(self._search_query))
        else:
            search_hits = None

        if self._tag_filter:
            tag_hits: set[str] | None = set(self._tag_index.notes_for_tag(self._tag_filter))
        else:
            tag_hits = None

        if search_hits is not None and tag_hits is not None:
            names = search_hits & tag_hits
        elif search_hits is not None:
            names = search_hits
        elif tag_hits is not None:
            names = tag_hits
        else:
            names = set(self._store.all_names())

        return sorted(names)

    def _refresh_tag_combo(self) -> None:
        current = self._tag_combo.currentText()
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        self._tag_combo.addItem("")
        for tag in sorted(self._tag_index.all_tags()):
            self._tag_combo.addItem(tag)
        idx = self._tag_combo.findText(current)
        self._tag_combo.setCurrentIndex(max(0, idx))
        self._tag_combo.blockSignals(False)

    def _on_search_changed(self, text: str) -> None:
        self.set_search_query(text)

    def _on_tag_changed(self, tag: str) -> None:
        self.set_tag_filter(tag)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self.note_selected.emit(item.text())

    def _on_selection_changed(self, current, _previous) -> None:
        self._delete_btn.setEnabled(current is not None)

    def _prompt_create_note(self) -> None:
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if ok and name.strip():
            self.create_note(name.strip())

    def _delete_selected_note(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        name = item.text()
        reply = QMessageBox.question(
            self,
            "Delete Note",
            f"Delete '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_note(name)
