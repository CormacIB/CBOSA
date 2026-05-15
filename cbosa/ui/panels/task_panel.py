"""
TaskPanel — dockable panel for the persistent task list.

Layout:
  ┌─────────────────────────────────────┐
  │  [ ] Task text              [src]   │  ← list of open tasks
  │  [ ] Another task           [src]   │
  │  ...                                │
  ├─────────────────────────────────────┤
  │  [New task text input field ] [Add] │
  │  [Delete Selected]  [Show Done]     │
  └─────────────────────────────────────┘
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.task_store import StoredTask, TaskStore
from cbosa.ui.panels import BasePanel

_SOURCE_BADGE = {
    "manual": "",
    "email":  "[email]",
    "canvas": "[canvas]",
    "note":   "[note]",
}


class TaskPanel(BasePanel):
    """Persistent task list panel backed by TaskStore."""

    def __init__(self, task_store: TaskStore, title: str = "Tasks", parent=None) -> None:
        super().__init__(title, parent)
        self._store = task_store
        self._show_done = False
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        # Task list
        self._list = QListWidget()
        self._list.setObjectName("task_list")
        self._list.setSpacing(2)
        self._list.itemChanged.connect(self._on_item_changed)
        root_layout.addWidget(self._list)

        # Add-task row
        add_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setObjectName("task_input")
        self._input.setPlaceholderText("New task…")
        self._input.returnPressed.connect(self._on_add)
        add_row.addWidget(self._input)

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
        self._list.blockSignals(True)
        self._list.clear()
        tasks = self._store.list_tasks(include_completed=self._show_done)
        for task in tasks:
            self._list.addItem(self._make_item(task))
        self._list.blockSignals(False)

    def _make_item(self, task: StoredTask) -> QListWidgetItem:
        badge = _SOURCE_BADGE.get(task.source, f"[{task.source}]")
        display = f"{task.text}  {badge}".strip()
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, task.id)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if task.completed else Qt.CheckState.Unchecked
        )
        return item

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._store.add_task(text, source="manual")
        self._input.clear()
        self._refresh()

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        self._store.delete_task(task_id)
        self._refresh()

    def _on_toggle_done(self, checked: bool) -> None:
        self._show_done = checked
        self._toggle_btn.setText("Hide Done" if checked else "Show Done")
        self._refresh()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id is None:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._store.complete_task(task_id)
        else:
            self._store.uncomplete_task(task_id)
        if not self._show_done:
            self._refresh()
