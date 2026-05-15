"""
EmailPanel — dockable panel for IMAP email + task extraction.

Layout (credentials present):
  QTabWidget
    Tab 0: Action Items — Task list populated after each sync (AI or rule-based)
    Tab 1: Inbox — search / list / reader / sync UI (unchanged behaviour)

When credentials are missing, shows a setup prompt instead.
"""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cbosa.ai.service import AIService, NullAIService
from cbosa.core.task import Task
from cbosa.core.task_extractor import TaskExtractor
from cbosa.modules.email_store import EmailStore
from cbosa.ui.panels import BasePanel

_ROLE_EMAIL_ID = Qt.ItemDataRole.UserRole


class EmailPanel(BasePanel):
    """Email inbox panel — Action Items and Inbox tabs."""

    def __init__(
        self,
        store: EmailStore,
        title: str = "Email",
        parent=None,
        ai_service: AIService | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._extractor = TaskExtractor()
        self._ai = ai_service or NullAIService()
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
            self._build_tabbed_ui(root_layout)

        self.setWidget(root)

    def _build_no_credentials_ui(self, layout: QVBoxLayout) -> None:
        """Show a setup prompt when credentials are missing."""
        layout.addStretch()
        prompt = QLabel(
            "Configure IMAP credentials in ~/.cbosa/secrets.toml\n\n"
            "Add a section like:\n\n"
            "  [imap]\n"
            "  host     = \"imap.example.com\"\n"
            "  port     = 993\n"
            "  username = \"you@example.com\"\n"
            "  password = \"yourpassword\""
        )
        prompt.setObjectName("no_credentials_label")
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)
        layout.addStretch()

    def _build_tabbed_ui(self, layout: QVBoxLayout) -> None:
        """Build the QTabWidget with Action Items (0) and Inbox (1) tabs."""
        self._tabs = QTabWidget()
        self._tabs.setObjectName("email_tabs")
        self._tabs.addTab(self._build_action_items_tab(), "Action Items")
        self._tabs.addTab(self._build_inbox_tab(), "Inbox")
        layout.addWidget(self._tabs)

    def _build_action_items_tab(self) -> QWidget:
        widget = QWidget()
        vbox = QVBoxLayout(widget)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)
        self._action_items_list = QListWidget()
        self._action_items_list.setObjectName("action_items_list")
        vbox.addWidget(self._action_items_list)
        return widget

    def _build_inbox_tab(self) -> QWidget:
        """Build the Inbox tab — existing search/list/reader/sync UI, unchanged."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ---- Search bar ----
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("search_edit")
        self._search_edit.setPlaceholderText("keyword, sender, or date (YYYY-MM-DD)…")
        self._search_btn = QPushButton("Search")
        self._search_btn.setObjectName("search_btn")
        self._search_btn.clicked.connect(self._on_search)
        self._search_edit.returnPressed.connect(self._on_search)
        search_bar.addWidget(self._search_edit)
        search_bar.addWidget(self._search_btn)
        layout.addLayout(search_bar)

        # ---- Main splitter: inbox list | message reader ----
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._inbox_list = QListWidget()
        self._inbox_list.setObjectName("inbox_list")
        self._inbox_list.currentItemChanged.connect(self._on_email_selected)
        main_splitter.addWidget(self._inbox_list)

        self._message_reader = QTextEdit()
        self._message_reader.setObjectName("message_reader")
        self._message_reader.setReadOnly(True)
        main_splitter.addWidget(self._message_reader)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        layout.addWidget(main_splitter)

        # ---- Bottom bar: sync + clear + status ----
        bottom_bar = QHBoxLayout()
        self._sync_btn = QPushButton("Sync")
        self._sync_btn.setObjectName("sync_btn")
        self._sync_btn.clicked.connect(self._on_sync)
        self._clear_btn = QPushButton("Clear Inbox")
        self._clear_btn.setObjectName("clear_btn")
        self._clear_btn.clicked.connect(self._on_clear)
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("status_label")
        bottom_bar.addWidget(self._sync_btn)
        bottom_bar.addWidget(self._clear_btn)
        bottom_bar.addWidget(self._status_label)
        bottom_bar.addStretch()
        layout.addLayout(bottom_bar)

        self._refresh_inbox()
        return widget

    # ------------------------------------------------------------------
    # Data / refresh — inbox
    # ------------------------------------------------------------------

    def _refresh_inbox(
        self,
        *,
        keyword: str | None = None,
        sender: str | None = None,
        date: str | None = None,
    ) -> None:
        """Reload the inbox list from the cache with optional filters."""
        self._inbox_list.clear()
        emails = self._store.list_emails(keyword=keyword, sender=sender, date=date)
        for em in emails:
            item = QListWidgetItem()
            item.setText(f"{em['subject']}\n{em['sender']}  {em['date']}")
            item.setData(_ROLE_EMAIL_ID, em["id"])
            self._inbox_list.addItem(item)

    # ------------------------------------------------------------------
    # Data / refresh — action items
    # ------------------------------------------------------------------

    def _extract_tasks_for_email(self, em: dict) -> list[Task]:
        """Return Task instances extracted from a single email dict.

        Uses AIService if it returns results; otherwise falls back to
        the rule-based TaskExtractor. Both paths produce Tasks with
        source="email" and source_id set to the email's row id.
        """
        text = em["subject"] + "\n" + em["body"]
        source_id = str(em["id"])

        raw = self._ai.extract_tasks(text)
        if not raw:
            raw = self._extractor.extract_tasks(text)

        return [
            Task(text=t, source="email", source_id=source_id, priority=None)
            for t in raw
        ]

    def _refresh_action_items(self) -> None:
        """Start background extraction of tasks from all stored emails."""
        self._action_item_worker = _ActionItemWorker(
            self._store, self._extractor, self._ai
        )
        self._action_item_worker.finished.connect(
            self._populate_action_items, Qt.ConnectionType.QueuedConnection
        )
        self._action_item_worker.start()

    def _populate_action_items(self, tasks: list[Task]) -> None:
        """Sort tasks by priority descending (None last) and fill the list.

        Each row: task text on line 1, subject | sender [| Due: …] on line 2.
        """
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (t.priority is None, -(t.priority or 0)),
        )

        self._action_items_list.clear()
        for task in sorted_tasks:
            em = self._store.get_email(int(task.source_id))
            if em:
                due_part = f" | Due: {task.due_date}" if task.due_date else ""
                line2 = f"{em['subject']} | {em['sender']}{due_part}"
            else:
                due_part = f"Due: {task.due_date}" if task.due_date else ""
                line2 = due_part
            self._action_items_list.addItem(
                QListWidgetItem(f"{task.text}\n{line2}")
            )

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_email_selected(
        self, current: QListWidgetItem | None, _previous
    ) -> None:
        if current is None:
            self._message_reader.clear()
            return
        email_id = current.data(_ROLE_EMAIL_ID)
        em = self._store.get_email(email_id)
        if em is None:
            return
        self._message_reader.setPlainText(
            f"Subject: {em['subject']}\n"
            f"From:    {em['sender']}\n"
            f"Date:    {em['date']}\n"
            f"\n{em['body']}"
        )

    def _on_search(self) -> None:
        query = self._search_edit.text().strip()
        if not query:
            self._refresh_inbox()
            return
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", query):
            self._refresh_inbox(date=query)
        elif "@" in query or re.search(r"\.(com|org|net|edu|io)\b", query, re.I):
            self._refresh_inbox(sender=query)
        else:
            self._refresh_inbox(keyword=query)

    def _on_clear(self) -> None:
        self._store.clear()
        self._message_reader.clear()
        self._refresh_inbox()
        self._refresh_action_items()
        self._status_label.setText("Inbox cleared")

    def _on_sync(self) -> None:
        self._sync_btn.setEnabled(False)
        self._status_label.setText("Syncing\u2026")
        self._store.sync(self._on_sync_done)

    def _on_sync_done(self, count: int, error: str) -> None:
        self._sync_btn.setEnabled(True)
        if error:
            self._status_label.setText(f"Error: {error}")
        else:
            self._status_label.setText(f"Synced {count} new email(s) — extracting tasks…")
            self._refresh_inbox()
            self._refresh_action_items()


# ---------------------------------------------------------------------------
# Background worker — task extraction
# ---------------------------------------------------------------------------

class _ActionItemWorker(QThread):
    """Extracts tasks from all stored emails in a background thread.

    Emits finished(list[Task]) when done; connect with QueuedConnection
    so _populate_action_items runs on the main thread.
    """

    finished = pyqtSignal(list)

    def __init__(self, store, extractor, ai_service, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._extractor = extractor
        self._ai = ai_service

    def run(self) -> None:
        all_tasks: list[Task] = []
        for em in self._store.list_emails():
            text = em["subject"] + "\n" + em["body"]
            source_id = str(em["id"])
            raw = self._ai.extract_tasks(text)
            if not raw:
                raw = self._extractor.extract_tasks(text)
            for t in raw:
                all_tasks.append(
                    Task(text=t, source="email", source_id=source_id, priority=None)
                )
        self.finished.emit(all_tasks)
