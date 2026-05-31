"""
NoteBrowserPanel — dockable panel showing the notes folder tree with tag filtering.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import DuplicateNoteError, NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.panels import BasePanel

_FOLDER_FLAGS = Qt.ItemFlag.ItemIsEnabled  # visible but not selectable/editable
_NOTE_KEY = Qt.ItemDataRole.UserRole       # stores the routing key on leaf items


class NoteBrowserPanel(BasePanel):
    note_selected = pyqtSignal(str)
    note_created = pyqtSignal(str)
    note_deleted = pyqtSignal(str)
    note_renamed = pyqtSignal(str, str)

    def __init__(
        self,
        store: NoteStore,
        tag_index: TagIndex,
        search_index: SearchIndex,
        title: str = "Note Browser",
        parent=None,
        daily_store: NoteStore | None = None,
        link_index: LinkIndex | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._tag_index = tag_index
        self._search_index = search_index
        self._daily_store = daily_store
        self._link_index = link_index
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

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._tree)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New Note")
        new_btn.clicked.connect(self._prompt_create_note)
        btn_row.addWidget(new_btn)

        self._rename_btn = QPushButton("Rename")
        self._rename_btn.setEnabled(False)
        self._rename_btn.clicked.connect(self._prompt_rename_note)
        btn_row.addWidget(self._rename_btn)

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
        self._populate_tree()

    def select_note(self, name: str) -> None:
        """Highlight *name* in the tree without emitting note_selected."""
        item = self._find_leaf(name)
        if item is None:
            return
        parent = item.parent()
        if parent is not None:
            parent.setExpanded(True)
        self._tree.blockSignals(True)
        self._tree.setCurrentItem(item)
        self._tree.blockSignals(False)
        self._tree.scrollToItem(item)

    def set_tag_filter(self, tag: str) -> None:
        self._tag_filter = tag or None
        self._populate_tree()

    def clear_tag_filter(self) -> None:
        self._tag_filter = None
        self._populate_tree()

    def set_search_query(self, query: str) -> None:
        self._search_query = query.strip()
        self._populate_tree()

    def create_note(self, name: str) -> None:
        self._store.create(name, "")
        self.refresh()
        self.note_created.emit(name)

    def delete_note(self, name: str) -> None:
        self._store.delete(name)
        self.refresh()
        self.note_deleted.emit(name)

    def rename_note(self, old_name: str, new_name: str) -> None:
        """Rename a note and propagate [[old_name]] wikilinks to [[new_name]]."""
        self._store.rename(old_name, new_name)
        if self._link_index is not None:
            self._link_index.rename_note(old_name, new_name)
        self.refresh()
        self.note_renamed.emit(old_name, new_name)

    # ------------------------------------------------------------------
    # Private — tree population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.clear()
        if self._search_query or self._tag_filter:
            self._populate_filtered()
        else:
            self._populate_browse()

    def _populate_browse(self) -> None:
        """Three collapsible folders: Notes / Daily / Archived."""
        all_names = set(self._store.all_names())
        archived = set(self._tag_index.notes_for_tag("archived")) & all_names
        regular = sorted(all_names - archived)

        notes_folder = self._make_folder(f"Notes ({len(regular)})")
        for name in regular:
            self._add_leaf(notes_folder, name, name)
        self._tree.addTopLevelItem(notes_folder)
        notes_folder.setExpanded(True)

        if self._daily_store is not None:
            daily_names = sorted(self._daily_store.all_names(), reverse=True)
            daily_folder = self._make_folder(f"Daily ({len(daily_names)})")
            for name in daily_names:
                self._add_leaf(daily_folder, name, f"daily/{name}")
            self._tree.addTopLevelItem(daily_folder)
            daily_folder.setExpanded(False)

        if archived:
            arch_names = sorted(archived)
            arch_folder = self._make_folder(f"Archived ({len(arch_names)})")
            for name in arch_names:
                self._add_leaf(arch_folder, name, name)
            self._tree.addTopLevelItem(arch_folder)
            arch_folder.setExpanded(False)

    def _populate_filtered(self) -> None:
        """Flat results list when a search or tag filter is active."""
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

        sorted_names = sorted(names)
        results_folder = self._make_folder(f"Results ({len(sorted_names)})")
        for name in sorted_names:
            self._add_leaf(results_folder, name, name)
        self._tree.addTopLevelItem(results_folder)
        results_folder.setExpanded(True)

    @staticmethod
    def _make_folder(label: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setFlags(_FOLDER_FLAGS)
        font = item.font(0)
        font.setWeight(QFont.Weight.Bold)
        item.setFont(0, font)
        return item

    @staticmethod
    def _add_leaf(parent: QTreeWidgetItem, display: str, key: str) -> QTreeWidgetItem:
        leaf = QTreeWidgetItem([display])
        leaf.setData(0, _NOTE_KEY, key)
        parent.addChild(leaf)
        return leaf

    def _find_leaf(self, key: str) -> QTreeWidgetItem | None:
        for i in range(self._tree.topLevelItemCount()):
            folder = self._tree.topLevelItem(i)
            for j in range(folder.childCount()):
                leaf = folder.child(j)
                if leaf.data(0, _NOTE_KEY) == key:
                    return leaf
        return None

    # ------------------------------------------------------------------
    # Private — signals and slots
    # ------------------------------------------------------------------

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

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        key = item.data(0, _NOTE_KEY)
        if key:  # None on folder headers
            self.note_selected.emit(key)

    def _on_selection_changed(self, current: QTreeWidgetItem | None, _previous) -> None:
        key = current.data(0, _NOTE_KEY) if current is not None else None
        is_editable_note = bool(key and not key.startswith("daily/"))
        self._delete_btn.setEnabled(is_editable_note)
        self._rename_btn.setEnabled(is_editable_note)

    def _prompt_create_note(self) -> None:
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if ok and name.strip():
            self.create_note(name.strip())

    def _prompt_rename_note(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        old_name = item.data(0, _NOTE_KEY)
        if not old_name or old_name.startswith("daily/"):
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Note", "New name:", text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        try:
            self.rename_note(old_name, new_name.strip())
        except DuplicateNoteError:
            QMessageBox.critical(
                self,
                "Rename Failed",
                f"A note named '{new_name.strip()}' already exists.",
            )

    def _delete_selected_note(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        key = item.data(0, _NOTE_KEY)
        if not key or key.startswith("daily/"):
            return
        reply = QMessageBox.question(
            self,
            "Delete Note",
            f"Delete '{key}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_note(key)
