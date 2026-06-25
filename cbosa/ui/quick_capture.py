"""
QuickCaptureWindow — minimal floating dialog for fast note capture.

Triggered by a global hotkey (Cmd+Ctrl+N on macOS).
Saves the text as a timestamped note in data/notes/Inbox/ and dismisses,
then restores focus to whichever app was frontmost before capture.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from cbosa.core.note_store import NoteStore


class QuickCaptureWindow(QDialog):
    """Floating capture window — type a thought, hit Cmd+Enter to save."""

    def __init__(self, notes_dir: Path, parent=None) -> None:
        super().__init__(parent)
        # Save into notes/Inbox so the note browser picks them up
        self._store = NoteStore(notes_dir / "Inbox")
        self._prev_app = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Quick Capture")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumWidth(480)
        self.setMaximumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        hint = QLabel("Capture a thought  ·  ⌘^N to open  ·  ⌘↩ to save  ·  Esc to cancel")
        hint.setObjectName("captureHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self._editor = QPlainTextEdit()
        self._editor.setObjectName("captureEditor")
        self._editor.setPlaceholderText("What's on your mind?")
        self._editor.setMinimumHeight(120)
        layout.addWidget(self._editor)

        save_btn = QPushButton("Save  ⌘↩")
        save_btn.setObjectName("captureSave")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._save)
        QShortcut(QKeySequence("Meta+Return"), self).activated.connect(self._save)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._record_frontmost_app()
        self._editor.clear()
        self._editor.setFocus()
        self._center_on_screen()

    def _record_frontmost_app(self) -> None:
        try:
            from AppKit import NSWorkspace
            self._prev_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            self._prev_app = None

    def _restore_focus(self) -> None:
        try:
            if self._prev_app:
                from AppKit import NSApplicationActivateIgnoringOtherApps
                self._prev_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        except Exception:
            pass

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.left() + 24, geo.top() + 24)

    def _save(self) -> None:
        text = self._editor.toPlainText().strip()
        self.hide()
        if text:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self._store.create(
                f"capture-{timestamp}",
                text,
                frontmatter={"captured": datetime.now().isoformat(), "source": "quick-capture"},
            )
        self._restore_focus()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self._restore_focus()
        else:
            super().keyPressEvent(event)
