"""
TaskPanel — dockable panel for the persistent task list, organised by category.

Layout:
  ┌─────────────────────────────────────────────────┐
  │ ▼ CBOSA                                         │  ← collapsible category
  │    [ ] Fix graph view              [manual]     │
  │    [ ] Write tests                 [manual]     │
  │ ▼ Personal                                      │
  │    [ ] Buy groceries               [manual]     │
  │ ▼ Uncategorized                                 │
  │    [ ] Old task without category   [email]      │
  ├─────────────────────────────────────────────────┤
  │  [New task…]       [Category ▾]  [Add]          │
  │  [Delete Selected] [Show Done]                  │
  └─────────────────────────────────────────────────┘
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.task_store import CategoryNotEmptyError, StoredTask, TaskStore
from cbosa.ui.panels import BasePanel

_TASK_ID_ROLE = Qt.ItemDataRole.UserRole
_CAT_ID_ROLE  = Qt.ItemDataRole.UserRole + 1

_SOURCE_BADGE = {
    "manual": "",
    "email":  "[email]",
    "canvas": "[canvas]",
    "note":   "[note]",
}

_UNCATEGORIZED = "Uncategorized"
_NEW_CAT_SENTINEL = "__new_category__"


class TaskPanel(BasePanel):
    """Persistent task list panel with collapsible category sections."""

    def __init__(self, task_store: TaskStore, title: str = "Tasks", parent=None) -> None:
        super().__init__(title, parent)
        self._store = task_store
        self._show_done = False
        self._build_ui()
        self._refresh_cat_combo()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        # Task tree (collapsible category sections)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setObjectName("task_tree")
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        root_layout.addWidget(self._tree)

        # Add-task row
        add_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setObjectName("task_input")
        self._input.setPlaceholderText("New task…")
        self._input.returnPressed.connect(self._on_add)
        add_row.addWidget(self._input, stretch=1)

        self._cat_combo = QComboBox()
        self._cat_combo.setObjectName("task_cat_combo")
        self._cat_combo.setMinimumWidth(100)
        self._cat_combo.activated.connect(self._on_cat_combo_activated)
        add_row.addWidget(self._cat_combo)

        add_btn = QPushButton("Add")
        add_btn.setObjectName("task_add_btn")
        add_btn.clicked.connect(self._on_add)
        add_row.addWidget(add_btn)
        root_layout.addLayout(add_row)

        # Bottom button row
        btn_row = QHBoxLayout()
        del_btn = QPushButton("Delete Selected")
        del_btn.setObjectName("task_delete_btn")
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(del_btn)

        self._toggle_btn = QPushButton("Show Done")
        self._toggle_btn.setObjectName("task_toggle_btn")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._on_toggle_done)
        btn_row.addWidget(self._toggle_btn)

        btn_row.addStretch()
        root_layout.addLayout(btn_row)

        self.setWidget(root)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        # Preserve which category sections are currently expanded
        expanded: set[str] = set()
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.isExpanded():
                expanded.add(item.text(0).rsplit(" (", 1)[0])

        self._tree.blockSignals(True)
        self._tree.clear()
        by_cat = self._store.list_tasks_by_category(include_completed=self._show_done)

        # Named categories first (sorted), then Uncategorized at bottom
        named_keys = sorted(k for k in by_cat if k != "")
        all_keys = named_keys + ([""] if "" in by_cat else [])

        for cat_name_key in all_keys:
            tasks = by_cat[cat_name_key]
            label = cat_name_key if cat_name_key else _UNCATEGORIZED
            header = self._make_cat_header(f"{label} ({len(tasks)})")
            cat_id = next(
                (c.id for c in self._store.list_categories() if c.name == cat_name_key),
                None,
            )
            header.setData(0, _CAT_ID_ROLE, cat_id)
            for task in tasks:
                header.addChild(self._make_task_item(task))
            self._tree.addTopLevelItem(header)
            # First load: expand all. Subsequent refreshes: restore saved state.
            header.setExpanded((label in expanded) if expanded else True)

        self._tree.blockSignals(False)

    def _refresh_cat_combo(self) -> None:
        self._cat_combo.blockSignals(True)
        current_id = self._cat_combo.currentData()
        self._cat_combo.clear()
        self._cat_combo.addItem("(no category)", None)
        for cat in self._store.list_categories():
            self._cat_combo.addItem(cat.name, cat.id)
        self._cat_combo.addItem("New category…", _NEW_CAT_SENTINEL)
        # Restore previous selection
        idx = self._cat_combo.findData(current_id)
        self._cat_combo.setCurrentIndex(max(0, idx))
        self._cat_combo.blockSignals(False)

    @staticmethod
    def _make_cat_header(label: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = item.font(0)
        font.setWeight(QFont.Weight.Bold)
        item.setFont(0, font)
        return item

    def _make_task_item(self, task: StoredTask) -> QTreeWidgetItem:
        badge = _SOURCE_BADGE.get(task.source, f"[{task.source}]")
        display = f"{task.text}  {badge}".strip()
        item = QTreeWidgetItem([display])
        item.setData(0, _TASK_ID_ROLE, task.id)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            0,
            Qt.CheckState.Checked if task.completed else Qt.CheckState.Unchecked,
        )
        return item

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        category_id = self._cat_combo.currentData()
        if category_id == _NEW_CAT_SENTINEL:
            category_id = None
        self._store.add_task(text, source="manual", category_id=category_id)
        self._input.clear()
        self._refresh()

    def _on_delete(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        task_id = item.data(0, _TASK_ID_ROLE)
        if task_id is None:
            return
        self._store.delete_task(task_id)
        self._refresh()

    def _on_toggle_done(self, checked: bool) -> None:
        self._show_done = checked
        self._toggle_btn.setText("Hide Done" if checked else "Show Done")
        self._refresh()

    def _on_item_changed(self, item: QTreeWidgetItem) -> None:
        task_id = item.data(0, _TASK_ID_ROLE)
        if task_id is None:
            return
        if item.checkState(0) == Qt.CheckState.Checked:
            self._store.complete_task(task_id)
        else:
            self._store.uncomplete_task(task_id)
        if not self._show_done:
            self._refresh()

    def _on_cat_combo_activated(self, index: int) -> None:
        if self._cat_combo.itemData(index) == _NEW_CAT_SENTINEL:
            name, ok = QInputDialog.getText(self, "New Category", "Category name:")
            if ok and name.strip():
                cat = self._store.add_category(name.strip())
                self._refresh_cat_combo()
                idx = self._cat_combo.findData(cat.id)
                if idx >= 0:
                    self._cat_combo.setCurrentIndex(idx)
            else:
                self._cat_combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        task_id = item.data(0, _TASK_ID_ROLE)
        cat_id = item.data(0, _CAT_ID_ROLE)

        menu = QMenu(self)
        if task_id is not None:
            menu.addAction("Delete Task", lambda: self._delete_task(task_id))
        elif cat_id is not None:
            menu.addAction("Rename Category",
                           lambda: self._prompt_rename_category(cat_id, item))
            menu.addAction("Delete Category",
                           lambda: self._prompt_delete_category(cat_id))
        else:
            return
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _delete_task(self, task_id: int) -> None:
        self._store.delete_task(task_id)
        self._refresh()

    def _prompt_rename_category(self, cat_id: int, header_item: QTreeWidgetItem) -> None:
        cats = {c.id: c.name for c in self._store.list_categories()}
        old_name = cats.get(cat_id, "")
        new_name, ok = QInputDialog.getText(
            self, "Rename Category", "New name:", text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        self._store.rename_category(cat_id, new_name.strip())
        self._refresh_cat_combo()
        self._refresh()

    def _prompt_delete_category(self, cat_id: int) -> None:
        try:
            self._store.delete_category(cat_id)
        except CategoryNotEmptyError as exc:
            QMessageBox.warning(self, "Delete Category", str(exc))
            return
        self._refresh_cat_combo()
        self._refresh()
