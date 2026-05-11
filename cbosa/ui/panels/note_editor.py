"""
NoteEditorPanel — dockable raw Markdown editor panel.
"""
from __future__ import annotations

import re
from urllib.parse import quote

import mistune
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteNotFoundError, NoteStore
from cbosa.ui.panels import BasePanel

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _render_markdown(text: str) -> str:
    """Convert Markdown (with [[wikilinks]]) to HTML."""
    text = _WIKILINK_RE.sub(
        lambda m: f"[{m.group(1)}](note:///{quote(m.group(1))})", text
    )
    return mistune.html(text)


class NoteEditorPanel(BasePanel):
    def __init__(
        self,
        store: NoteStore,
        link_index: LinkIndex,
        title: str = "Note Editor",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._link_index = link_index
        self._current_note: str | None = None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("Open a note to edit…")
        layout.addWidget(self._editor)

        self.setWidget(container)

        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def current_note(self) -> str | None:
        return self._current_note

    def open_note(self, name: str) -> None:
        try:
            note = self._store.read(name)
        except NoteNotFoundError:
            note = self._store.create(name, "")
        self._current_note = name
        self._editor.blockSignals(True)
        self._editor.setPlainText(note.content)
        self._editor.blockSignals(False)

    def save(self) -> None:
        if self._current_note is None:
            return
        self._store.update(self._current_note, self._editor.toPlainText())

    def clear_if_current(self, name: str) -> None:
        if self._current_note == name:
            self._current_note = None
            self._editor.clear()
