"""
NoteBrowserPanel — dockable panel showing the notes folder tree with tag filtering.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
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
_FOLDER_PATH_KEY = Qt.ItemDataRole.UserRole + 1  # stores the rel folder path on folder items


class _MoveToDlg(QDialog):
    """Simple folder-picker dialog for 'Move To…'."""

    def __init__(self, folders: list[str], current_folder: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Move To…")
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select destination folder:"))
        self._list = QListWidget()
        for f in folders:
            label = f if f else "(root)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, f)
            self._list.addItem(item)
            if f == current_folder:
                self._list.setCurrentItem(item)
        layout.addWidget(self._list)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self._list.itemDoubleClicked.connect(lambda _: self.accept())

    def selected_folder(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


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
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree)

        btn_row = QHBoxLayout()
        new_note_btn = QPushButton("New Note")
        new_note_btn.clicked.connect(self._prompt_create_note)
        btn_row.addWidget(new_note_btn)
        new_folder_btn = QPushButton("New Folder")
        new_folder_btn.clicked.connect(self._prompt_create_folder_at_root)
        btn_row.addWidget(new_folder_btn)
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
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
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
        """Rename a note and propagate [[wikilinks]] using bare stems."""
        self._store.rename(old_name, new_name)
        if self._link_index is not None:
            old_bare = Path(old_name).name
            new_bare = Path(new_name).name
            if old_bare != new_bare:
                self._link_index.rename_note(old_bare, new_bare)
        self.refresh()
        self.note_renamed.emit(old_name, new_name)

    def move_note(self, name: str, dest_folder: str) -> None:
        """Move note to dest_folder (no wikilink change — links use bare names)."""
        self._store.move_note(name, dest_folder)
        self.refresh()

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
        all_names = set(self._store.all_names())
        archived = set(self._tag_index.notes_for_tag("archived")) & all_names
        regular = all_names - archived

        # Build filesystem tree from regular notes
        self._add_fs_tree(sorted(regular))

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
                self._add_leaf(arch_folder, Path(name).name, name)
            self._tree.addTopLevelItem(arch_folder)
            arch_folder.setExpanded(False)

    def _add_fs_tree(self, names: list[str]) -> None:
        """Build a tree of QTreeWidgetItems mirroring the filesystem hierarchy."""
        folder_items: dict[str, QTreeWidgetItem] = {}

        def get_folder_item(rel_folder: str) -> QTreeWidgetItem:
            if rel_folder in folder_items:
                return folder_items[rel_folder]
            parts = Path(rel_folder).parts
            if len(parts) == 1:
                item = self._make_folder(rel_folder)
                item.setData(0, _FOLDER_PATH_KEY, rel_folder)
                self._tree.addTopLevelItem(item)
                item.setExpanded(True)
            else:
                parent_path = str(Path(rel_folder).parent)
                parent_item = get_folder_item(parent_path)
                item = self._make_folder(parts[-1])
                item.setData(0, _FOLDER_PATH_KEY, rel_folder)
                parent_item.addChild(item)
                item.setExpanded(True)
            folder_items[rel_folder] = item
            return item

        # Sort: folders before root-level notes, then alphabetically
        root_notes = [n for n in names if "/" not in n]
        nested_notes = [n for n in names if "/" in n]

        # Ensure all parent folders exist for nested notes
        all_folders: set[str] = set()
        for name in nested_notes:
            parts = Path(name).parts
            for i in range(1, len(parts)):
                all_folders.add(str(Path(*parts[:i])))
        for folder in sorted(all_folders):
            get_folder_item(folder)

        # Add nested notes under their folder items
        for name in nested_notes:
            folder_path = str(Path(name).parent)
            folder_item = get_folder_item(folder_path)
            self._add_leaf(folder_item, Path(name).name, name)

        # Add root-level notes directly as top-level items
        for name in root_notes:
            leaf = QTreeWidgetItem([name])
            leaf.setData(0, _NOTE_KEY, name)
            self._tree.addTopLevelItem(leaf)

    def _populate_filtered(self) -> None:
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
            self._add_leaf(results_folder, Path(name).name, name)
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
        def _search(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if item.data(0, _NOTE_KEY) == key:
                return item
            for i in range(item.childCount()):
                found = _search(item.child(i))
                if found:
                    return found
            return None

        for i in range(self._tree.topLevelItemCount()):
            found = _search(self._tree.topLevelItem(i))
            if found:
                return found
        return None

    def _current_note_key(self) -> str | None:
        item = self._tree.currentItem()
        return item.data(0, _NOTE_KEY) if item else None

    def _item_folder_path(self, item: QTreeWidgetItem) -> str | None:
        """Return the folder rel-path for a folder item, or None if it's a note/special."""
        return item.data(0, _FOLDER_PATH_KEY)

    # ------------------------------------------------------------------
    # Private — context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            # Right-click on empty space
            menu.addAction("New Note", self._prompt_create_note)
            menu.addAction("New Folder", lambda: self._prompt_create_folder(""))
        else:
            note_key = item.data(0, _NOTE_KEY)
            folder_path = item.data(0, _FOLDER_PATH_KEY)

            if note_key and not note_key.startswith("daily/"):
                # Note item
                menu.addAction("Rename", self._prompt_rename_note)
                menu.addAction("Move To…", lambda: self._prompt_move_note(note_key))
                menu.addSeparator()
                menu.addAction("Delete", self._delete_selected_note)
            elif folder_path is not None:
                # Filesystem folder item
                menu.addAction("New Note Here",
                               lambda fp=folder_path: self._prompt_create_note_in(fp))
                menu.addAction("New Subfolder",
                               lambda fp=folder_path: self._prompt_create_folder(fp))
                menu.addSeparator()
                menu.addAction("Rename Folder",
                               lambda fp=folder_path: self._prompt_rename_folder(fp))
                menu.addAction("Delete Folder",
                               lambda fp=folder_path: self._prompt_delete_folder(fp))
            else:
                # Special (Daily / Archived / Results) — offer nothing
                return

        menu.exec(self._tree.viewport().mapToGlobal(pos))

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
        if key:
            self.note_selected.emit(key)

    def _on_selection_changed(self, current: QTreeWidgetItem | None, _previous) -> None:
        pass  # no buttons to enable/disable; actions are in the context menu

    # ------------------------------------------------------------------
    # Private — actions
    # ------------------------------------------------------------------

    def _prompt_create_note(self) -> None:
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if ok and name.strip():
            self.create_note(name.strip())

    def _prompt_create_note_in(self, folder: str) -> None:
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if ok and name.strip():
            full_name = f"{folder}/{name.strip()}" if folder else name.strip()
            self.create_note(full_name)

    def _prompt_create_folder_at_root(self) -> None:
        self._prompt_create_folder("")

    def _prompt_create_folder(self, parent_folder: str) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        rel = f"{parent_folder}/{name.strip()}" if parent_folder else name.strip()
        self._store.create_folder(rel)
        self.refresh()

    def _prompt_rename_folder(self, folder_path: str) -> None:
        old_name = Path(folder_path).name
        new_name, ok = QInputDialog.getText(
            self, "Rename Folder", "New name:", text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        import shutil
        old_full = self._store._root / folder_path
        new_rel = str(Path(folder_path).parent / new_name.strip()) \
            if Path(folder_path).parent != Path(".") else new_name.strip()
        new_full = self._store._root / new_rel
        if new_full.exists():
            QMessageBox.critical(self, "Rename Failed",
                                 f"A folder named '{new_name.strip()}' already exists.")
            return
        shutil.move(str(old_full), str(new_full))
        self.refresh()

    def _prompt_delete_folder(self, folder_path: str) -> None:
        full = self._store._root / folder_path
        if any(full.rglob("*.md")):
            QMessageBox.warning(self, "Delete Folder",
                                "Remove or move all notes in this folder first.")
            return
        reply = QMessageBox.question(
            self, "Delete Folder",
            f"Delete empty folder '{folder_path}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            import shutil
            shutil.rmtree(str(full))
            self.refresh()

    def _prompt_rename_note(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        old_name = item.data(0, _NOTE_KEY)
        if not old_name or old_name.startswith("daily/"):
            return
        old_bare = Path(old_name).name
        new_bare, ok = QInputDialog.getText(
            self, "Rename Note", "New name:", text=old_bare
        )
        if not ok or not new_bare.strip() or new_bare.strip() == old_bare:
            return
        folder = str(Path(old_name).parent) if "/" in old_name else ""
        new_name = f"{folder}/{new_bare.strip()}" if folder else new_bare.strip()
        try:
            self.rename_note(old_name, new_name)
        except DuplicateNoteError:
            QMessageBox.critical(
                self, "Rename Failed",
                f"A note named '{new_bare.strip()}' already exists.",
            )

    def _prompt_move_note(self, note_key: str) -> None:
        folders = self._store.all_folders()
        current_folder = str(Path(note_key).parent) if "/" in note_key else ""
        dlg = _MoveToDlg(folders, current_folder, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dest = dlg.selected_folder()
        if dest is None or dest == current_folder:
            return
        try:
            self.move_note(note_key, dest)
        except DuplicateNoteError:
            QMessageBox.critical(self, "Move Failed",
                                 "A note with that name already exists in the destination.")

    def _delete_selected_note(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        key = item.data(0, _NOTE_KEY)
        if not key or key.startswith("daily/"):
            return
        reply = QMessageBox.question(
            self, "Delete Note",
            f"Delete '{Path(key).name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_note(key)
