"""
NoteEditorPanel — dockable raw Markdown editor panel.

[[wikilinks]] in the editor are styled as clickable links via WikilinkHighlighter.
Click a wikilink to emit note_link_activated(target_name).

When the cursor is not inside a [[wikilink]], the brackets are coloured to match
the editor background — they become invisible — and only the link text is shown in
the accent colour (Obsidian-style live preview).  Moving the cursor inside the
wikilink reveals the brackets in a muted colour so the raw syntax is editable.
"""
from __future__ import annotations

import re
from urllib.parse import quote

import mistune
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QKeySequence,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
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


class WikilinkHighlighter(QSyntaxHighlighter):
    """
    Highlights [[wikilinks]] in the editor.

    For each wikilink the cursor is NOT inside:
      - ``[[`` and ``]]`` are coloured to match the editor background (invisible).
      - The inner link text is shown in the accent link colour.

    For the wikilink the cursor IS inside:
      - ``[[`` and ``]]`` are shown in a muted colour so the user can edit them.
      - The inner link text keeps the accent link colour.
    """

    def __init__(
        self,
        document,
        bg_color: str = "#1e1e2e",
        link_color: str = "#89b4fa",
        bracket_active_color: str = "#6c7086",
    ):
        super().__init__(document)
        self._cursor_block_number = -1
        self._cursor_pos_in_block = -1

        self._link_fmt = QTextCharFormat()
        self._link_fmt.setForeground(QColor(link_color))
        self._link_fmt.setFontUnderline(True)

        # Brackets when cursor is NOT in this span — matches background → invisible
        self._bracket_hidden_fmt = QTextCharFormat()
        self._bracket_hidden_fmt.setForeground(QColor(bg_color))

        # Brackets when cursor IS in this span — visible but muted
        self._bracket_active_fmt = QTextCharFormat()
        self._bracket_active_fmt.setForeground(QColor(bracket_active_color))

    def set_cursor_position(self, block_number: int, pos_in_block: int) -> None:
        """Update the cursor position and re-highlight if it changed."""
        if (
            self._cursor_block_number != block_number
            or self._cursor_pos_in_block != pos_in_block
        ):
            self._cursor_block_number = block_number
            self._cursor_pos_in_block = pos_in_block
            self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        this_block = self.currentBlock().blockNumber()
        for m in _WIKILINK_RE.finditer(text):
            cursor_in_span = (
                this_block == self._cursor_block_number
                and m.start() <= self._cursor_pos_in_block <= m.end()
            )
            bracket_fmt = (
                self._bracket_active_fmt if cursor_in_span else self._bracket_hidden_fmt
            )
            self.setFormat(m.start(), 2, bracket_fmt)                      # [[
            self.setFormat(m.start(1), len(m.group(1)), self._link_fmt)    # text
            self.setFormat(m.end(1), 2, bracket_fmt)                       # ]]


class _WikiEditor(QPlainTextEdit):
    """
    QPlainTextEdit subclass that intercepts left-clicks on [[wikilinks]].

    Monkey-patching viewport().mousePressEvent does not work in PyQt6 because
    SIP dispatches virtual methods via the class, not the instance.  Subclassing
    and overriding mousePressEvent is the only reliable way to intercept clicks.
    """

    link_clicked = pyqtSignal(str)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            block_text = cursor.block().text()
            pos = cursor.positionInBlock()
            for m in _WIKILINK_RE.finditer(block_text):
                if m.start() <= pos <= m.end():
                    self.link_clicked.emit(m.group(1))
                    return
        super().mousePressEvent(event)


class NoteEditorPanel(BasePanel):
    note_link_activated = pyqtSignal(str)
    note_saved = pyqtSignal(str)  # emits note name after a successful save

    def __init__(
        self,
        store: NoteStore,
        link_index: LinkIndex,
        title: str = "Note Editor",
        parent=None,
        daily_store: NoteStore | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._link_index = link_index
        self._daily_store = daily_store
        self._current_note: str | None = None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._editor = _WikiEditor()
        self._editor.setPlaceholderText("Open a note to edit…")
        self._editor.link_clicked.connect(self.note_link_activated)
        layout.addWidget(self._editor)

        self.setWidget(container)

        self._highlighter = WikilinkHighlighter(self._editor.document())
        self._editor.cursorPositionChanged.connect(self._on_cursor_position_changed)

        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def current_note(self) -> str | None:
        return self._current_note

    def open_note(self, name: str) -> None:
        store, bare_name = self._resolve(name)
        try:
            note = store.read(bare_name)
        except NoteNotFoundError:
            note = store.create(bare_name, "")
        self._current_note = name
        self._editor.blockSignals(True)
        self._editor.setPlainText(note.content)
        self._editor.blockSignals(False)

    def save(self) -> None:
        if self._current_note is None:
            return
        store, bare_name = self._resolve(self._current_note)
        store.update(bare_name, self._editor.toPlainText())
        self.note_saved.emit(self._current_note)

    def clear_if_current(self, name: str) -> None:
        if self._current_note == name:
            self._current_note = None
            self._editor.clear()

    def _extract_wikilink_at_cursor(self, cursor: QTextCursor) -> str | None:
        """Return the wikilink target name if the cursor sits inside [[name]], else None."""
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()
        for m in _WIKILINK_RE.finditer(block_text):
            if m.start() <= pos_in_block <= m.end():
                return m.group(1)
        return None

    def _activate_wikilink_at_cursor(self, cursor: QTextCursor) -> None:
        """Emit note_link_activated if the cursor is on a wikilink."""
        target = self._extract_wikilink_at_cursor(cursor)
        if target is not None:
            self.note_link_activated.emit(target)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _resolve(self, name: str) -> tuple[NoteStore, str]:
        """Return (store, bare_name) — routes daily/ names to the daily store."""
        if name.startswith("daily/") and self._daily_store is not None:
            return self._daily_store, name[len("daily/"):]
        return self._store, name

    def _on_cursor_position_changed(self) -> None:
        """Notify the highlighter so it can show/hide brackets around the active wikilink."""
        cursor = self._editor.textCursor()
        self._highlighter.set_cursor_position(
            cursor.blockNumber(), cursor.positionInBlock()
        )

    def _same_wikilink_span(
        self, c1: QTextCursor, c2: QTextCursor
    ) -> bool:
        """Return True if both cursors fall inside the same [[wikilink]] span."""
        if c1.block() != c2.block():
            return False
        block_text = c1.block().text()
        p1 = c1.positionInBlock()
        p2 = c2.positionInBlock()
        for m in _WIKILINK_RE.finditer(block_text):
            if m.start() <= p1 <= m.end() and m.start() <= p2 <= m.end():
                return True
        return False

