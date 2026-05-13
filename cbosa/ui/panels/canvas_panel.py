"""
CanvasPanel — dockable panel for Canvas LMS data.

Layout when credentials are present:
  ┌──────────────────────────────────────────────────┐
  │  [Assignments] [Grades] [Files]   ← tab bar      │
  ├──────────────────────────────────────────────────┤
  │  Tab content (QTableWidget)                      │
  │                                                  │
  ├──────────────────────────────────────────────────┤
  │  [Sync]   Status: Ready                          │
  └──────────────────────────────────────────────────┘

When credentials are missing, shows a setup prompt instead.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cbosa.modules.canvas_store import CanvasStore
from cbosa.ui.panels import BasePanel


class CanvasPanel(BasePanel):
    """Canvas LMS panel — assignments timeline, grade table, file browser."""

    def __init__(
        self,
        store: CanvasStore,
        title: str = "Canvas",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        if not self._store.has_credentials:
            self._build_no_credentials_ui(root_layout)
        else:
            self._build_canvas_ui(root_layout)

        self.setWidget(root)

    def _build_no_credentials_ui(self, layout: QVBoxLayout) -> None:
        layout.addStretch()
        prompt = QLabel(
            "Configure Canvas credentials in ~/.cbosa/secrets.toml\n\n"
            "Add a section like:\n\n"
            "  [canvas]\n"
            "  base_url = \"https://your-institution.instructure.com\"\n"
            "  token    = \"your-personal-access-token\""
        )
        prompt.setObjectName("no_credentials_label")
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)
        layout.addStretch()

    def _build_canvas_ui(self, layout: QVBoxLayout) -> None:
        # ---- Tab widget ----
        tabs = QTabWidget()

        # Assignments tab
        self._assignment_table = self._make_table(
            "assignment_table",
            ["Assignment", "Course", "Due", "Points"],
        )
        tabs.addTab(self._assignment_table, "Assignments")

        # Grades tab
        self._grade_table = self._make_table(
            "grade_table",
            ["Assignment", "Course", "Score", "Grade"],
        )
        tabs.addTab(self._grade_table, "Grades")

        # Files tab
        self._file_table = self._make_table(
            "file_table",
            ["File", "Course", "Size (KB)"],
        )
        tabs.addTab(self._file_table, "Files")

        layout.addWidget(tabs)

        # ---- Bottom bar ----
        bottom = QHBoxLayout()
        self._sync_btn = QPushButton("Sync")
        self._sync_btn.setObjectName("sync_btn")
        self._sync_btn.clicked.connect(self._on_sync)
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("status_label")
        bottom.addWidget(self._sync_btn)
        bottom.addWidget(self._status_label)
        bottom.addStretch()
        layout.addLayout(bottom)

        # Load cached data on open
        self._refresh_tables()

    @staticmethod
    def _make_table(object_name: str, headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setObjectName(object_name)
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _refresh_tables(self) -> None:
        self._refresh_assignments()
        self._refresh_grades()
        self._refresh_files()

    def _refresh_assignments(self) -> None:
        assignments = self._store.list_assignments()
        t = self._assignment_table
        t.setRowCount(0)
        for row, a in enumerate(assignments):
            t.insertRow(row)
            # Strip ISO timestamp to date portion for display
            due = a["due_at"][:10] if a["due_at"] else ""
            t.setItem(row, 0, QTableWidgetItem(a["name"]))
            t.setItem(row, 1, QTableWidgetItem(a["course_name"]))
            t.setItem(row, 2, QTableWidgetItem(due))
            t.setItem(row, 3, QTableWidgetItem(str(a["points_possible"])))

    def _refresh_grades(self) -> None:
        submissions = self._store.list_submissions()
        t = self._grade_table
        t.setRowCount(0)
        for row, s in enumerate(submissions):
            t.insertRow(row)
            score_text = str(s["score"]) if s["score"] is not None else "\u2014"
            t.setItem(row, 0, QTableWidgetItem(s["assignment_name"]))
            t.setItem(row, 1, QTableWidgetItem(s["course_name"]))
            t.setItem(row, 2, QTableWidgetItem(score_text))
            t.setItem(row, 3, QTableWidgetItem(s["grade"]))

    def _refresh_files(self) -> None:
        files = self._store.list_files()
        t = self._file_table
        t.setRowCount(0)
        for row, f in enumerate(files):
            t.insertRow(row)
            size_kb = str(round(f["size"] / 1024, 1)) if f["size"] else "0"
            t.setItem(row, 0, QTableWidgetItem(f["name"]))
            t.setItem(row, 1, QTableWidgetItem(f["course_name"]))
            t.setItem(row, 2, QTableWidgetItem(size_kb))

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_sync(self) -> None:
        self._sync_btn.setEnabled(False)
        self._status_label.setText("Syncing\u2026")
        self._store.sync(self._on_sync_done)

    def _on_sync_done(self, count: int, error: str) -> None:
        self._sync_btn.setEnabled(True)
        if error:
            self._status_label.setText(f"Error: {error}")
        else:
            self._status_label.setText(f"Synced {count} item(s)")
            self._refresh_tables()
