"""
EmailPanel — dockable panel for IMAP email + task extraction.

Layout when credentials are present:
  ┌──────────────────────────────────────────────────┐
  │  Search: [_________________________] [Search]    │
  ├────────────────────┬─────────────────────────────┤
  │  Inbox list        │  Message reader              │
  │  (QListWidget)     │  (QTextEdit, read-only)      │
  │  Subject           │                              │
  │  From / Date       ├─────────────────────────────┤
  │                    │  Extracted Tasks             │
  │                    │  (QListWidget)               │
  ├────────────────────┴─────────────────────────────┤
  │  [Sync]   Status: Ready                          │
  └──────────────────────────────────────────────────┘

When credentials are missing, shows a setup prompt instead.
"""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.task_extractor import TaskExtractor
from cbosa.modules.email_store import EmailStore
from cbosa.ui.panels import BasePanel

_ROLE_EMAIL_ID = Qt.ItemDataRole.UserRole


class EmailPanel(BasePanel):
    """Email inbox panel — list, reader, and extracted task sidebar."""

    def __init__(
        self,
        store: EmailStore,
        title: str = "Email",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._extractor = TaskExtractor()
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
            self._build_inbox_ui(root_layout)

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

    def _build_inbox_ui(self, layout: QVBoxLayout) -> None:
        """Build the full inbox / reader / tasks UI."""
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

        # ---- Main splitter: inbox | reader+tasks ----
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._inbox_list = QListWidget()
        self._inbox_list.setObjectName("inbox_list")
        self._inbox_list.currentItemChanged.connect(self._on_email_selected)
        main_splitter.addWidget(self._inbox_list)

        # Right pane: reader on top, tasks on bottom
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self._message_reader = QTextEdit()
        self._message_reader.setObjectName("message_reader")
        self._message_reader.setReadOnly(True)
        right_splitter.addWidget(self._message_reader)

        tasks_widget = QWidget()
        tasks_layout = QVBoxLayout(tasks_widget)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        tasks_layout.addWidget(QLabel("<b>Extracted Tasks</b>"))
        self._tasks_list = QListWidget()
        self._tasks_list.setObjectName("tasks_list")
        tasks_layout.addWidget(self._tasks_list)
        right_splitter.addWidget(tasks_widget)

        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)
        right_layout.addWidget(right_splitter)
        main_splitter.addWidget(right_pane)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        layout.addWidget(main_splitter)

        # ---- Bottom bar: sync + clear buttons + status ----
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

        # Load from cache on open
        self._refresh_inbox()

    # ------------------------------------------------------------------
    # Data / refresh
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
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_email_selected(
        self, current: QListWidgetItem | None, _previous
    ) -> None:
        if current is None:
            self._message_reader.clear()
            self._tasks_list.clear()
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
        tasks = self._extractor.extract_tasks(em["subject"] + "\n" + em["body"])
        self._tasks_list.clear()
        for task in tasks:
            self._tasks_list.addItem(QListWidgetItem(task))

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
        self._tasks_list.clear()
        self._refresh_inbox()
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
            self._status_label.setText(f"Synced {count} new email(s)")
            self._refresh_inbox()
