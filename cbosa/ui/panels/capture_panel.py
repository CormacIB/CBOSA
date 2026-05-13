"""
CapturePanel — dockable panel for the Capture Engine.

Layout:
  ┌─────────────────────────────────────────────────┐
  │  URL: [_________________________________] [Capture] │
  │  Drop a PDF onto this panel to capture it         │
  ├─────────────────────────────────────────────────┤
  │  Status: Ready                                    │
  ├─────────────────────────────────────────────────┤
  │  Related notes:         ← hidden until capture    │
  │    Note A  [Accept] [Reject]                      │
  │    Note B  [Accept] [Reject]                      │
  └─────────────────────────────────────────────────┘
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.note_store import NoteStore
from cbosa.modules.capture_engine import CaptureEngine, CaptureResult, CaptureFetchError
from cbosa.ui.panels import BasePanel


class CapturePanel(BasePanel):
    """
    Panel for capturing content from URLs and PDFs.

    Args:
        engine:          CaptureEngine used for fetching.
        captures_store:  NoteStore where captured notes are saved.
        all_notes_store: Optional NoteStore scanned for related-note suggestions.
        title:           Dock widget title.
        parent:          Qt parent widget.
    """

    def __init__(
        self,
        engine: CaptureEngine,
        captures_store: NoteStore,
        all_notes_store: NoteStore | None = None,
        title: str = "Capture",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._engine = engine
        self._captures_store = captures_store
        self._all_notes_store = all_notes_store
        self._current_note_name: str | None = None
        self._worker: _CaptureWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setAcceptDrops(True)
        root.dragEnterEvent = self._drag_enter  # type: ignore[method-assign]
        root.dropEvent = self._drop_event       # type: ignore[method-assign]

        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ---- URL input row ----
        url_row = QHBoxLayout()
        url_label = QLabel("URL:")
        self._url_input = QLineEdit()
        self._url_input.setObjectName("url_input")
        self._url_input.setPlaceholderText("Paste URL or drop a PDF onto this panel…")
        self._url_input.returnPressed.connect(self._on_capture_clicked)
        self._capture_btn = QPushButton("Capture")
        self._capture_btn.setObjectName("capture_btn")
        self._capture_btn.clicked.connect(self._on_capture_clicked)
        url_row.addWidget(url_label)
        url_row.addWidget(self._url_input, stretch=1)
        url_row.addWidget(self._capture_btn)
        layout.addLayout(url_row)

        # ---- Status label ----
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("status_label")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # ---- Suggestions section ----
        self._suggestions_widget = QWidget()
        self._suggestions_widget.setObjectName("suggestions_widget")
        self._suggestions_layout = QVBoxLayout(self._suggestions_widget)
        self._suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self._suggestions_layout.setSpacing(4)
        _header = QLabel("Related notes:")
        _header.setObjectName("suggestions_header")
        self._suggestions_layout.addWidget(_header)
        layout.addWidget(self._suggestions_widget)
        self._suggestions_widget.hide()

        layout.addStretch()
        self.setWidget(root)

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_capture_clicked(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return
        self._start_capture_url(url)

    def _start_capture_url(self, url: str) -> None:
        self._capture_btn.setEnabled(False)
        self._status_label.setText("Capturing\u2026")
        self._clear_suggestions()
        self._worker = _CaptureWorker(self._engine, url=url)
        self._worker.succeeded.connect(self._on_capture_complete)
        self._worker.failed.connect(self._on_capture_error)
        self._worker.start()

    def _start_capture_pdf(self, path: Path) -> None:
        self._capture_btn.setEnabled(False)
        self._status_label.setText("Extracting PDF\u2026")
        self._clear_suggestions()
        self._worker = _CaptureWorker(self._engine, pdf_path=path)
        self._worker.succeeded.connect(self._on_capture_complete)
        self._worker.failed.connect(self._on_capture_error)
        self._worker.start()

    def _on_capture_complete(self, result: CaptureResult) -> None:
        note_name = self._engine.save(result, self._captures_store)
        self._capture_btn.setEnabled(True)
        self._status_label.setText(f"Captured: {result.title or note_name}")
        if self._all_notes_store is not None:
            suggestions = self._engine.find_related(result.content, self._all_notes_store)
        else:
            suggestions = []
        self._on_capture_done(note_name, suggestions)

    def _on_capture_done(self, note_name: str, suggestions: list[str]) -> None:
        """Show related-note suggestion rows. Called after a successful capture."""
        self._current_note_name = note_name
        self._clear_suggestions()
        if suggestions:
            self._suggestions_widget.show()
            for suggestion in suggestions:
                self._add_suggestion_row(suggestion)

    def _on_capture_error(self, error: str) -> None:
        self._capture_btn.setEnabled(True)
        self._status_label.setText(f"Error: {error}")

    # ------------------------------------------------------------------
    # Suggestion management
    # ------------------------------------------------------------------

    def _add_suggestion_row(self, note_name: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(note_name)
        accept_btn = QPushButton("Accept")
        accept_btn.setObjectName(f"accept_{note_name}")
        reject_btn = QPushButton("Reject")
        reject_btn.setObjectName(f"reject_{note_name}")

        def _on_accept(_checked=False, n=note_name, r=row):
            self._accept_suggestion(self._current_note_name, n)
            r.hide()

        def _on_reject(_checked=False, r=row):
            self._reject_suggestion(self._current_note_name, note_name)
            r.hide()

        accept_btn.clicked.connect(_on_accept)
        reject_btn.clicked.connect(_on_reject)

        row_layout.addWidget(label, stretch=1)
        row_layout.addWidget(accept_btn)
        row_layout.addWidget(reject_btn)
        self._suggestions_layout.addWidget(row)

    def _accept_suggestion(self, note_name: str | None, related_note: str) -> None:
        """Append [[related_note]] wikilink to the captured note's content."""
        if note_name is None:
            return
        note = self._captures_store.read(note_name)
        new_content = note.content + f"\n\n[[{related_note}]]"
        self._captures_store.update(note_name, new_content, note.frontmatter)

    def _reject_suggestion(self, note_name: str | None, related_note: str) -> None:
        """Rejection is a no-op — the note is not modified."""

    def _clear_suggestions(self) -> None:
        """Remove all suggestion rows (keep the header label) and hide the widget."""
        while self._suggestions_layout.count() > 1:
            item = self._suggestions_layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()
        self._suggestions_widget.hide()

    # ------------------------------------------------------------------
    # Drag-and-drop support for PDFs
    # ------------------------------------------------------------------

    def _drag_enter(self, event) -> None:
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_event(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self._start_capture_pdf(Path(path))
                break


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _CaptureWorker(QThread):
    """Runs a single capture operation in a background thread."""

    succeeded = pyqtSignal(object)   # CaptureResult
    failed = pyqtSignal(str)

    def __init__(
        self,
        engine: CaptureEngine,
        url: str | None = None,
        pdf_path: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._url = url
        self._pdf_path = pdf_path

    def run(self) -> None:
        try:
            if self._url is not None:
                result = self._engine.capture_url(self._url)
            else:
                result = self._engine.capture_pdf(self._pdf_path)
            self.succeeded.emit(result)
        except CaptureFetchError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
