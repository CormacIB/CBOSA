"""
NoteEditorPanel — dockable Markdown editor with Edit / Preview / Split modes.

Default mode is Preview: the note is rendered as styled HTML in a QTextEdit.
Clicking Edit switches to the raw QPlainTextEdit. Split shows both side-by-side.

[[wikilinks]] in the editor are styled via WikilinkHighlighter (Obsidian-style
live preview: brackets invisible when cursor is away, visible when cursor is inside).
"""
from __future__ import annotations

import functools
import re
from urllib.parse import quote

import mistune
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QKeySequence,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cbosa.ai.service import AIService, NullAIService
from cbosa.ai.worker import AIWorker
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteNotFoundError, NoteStore
from cbosa.ui.panels import BasePanel

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_MATH_DISPLAY_RE = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
_MATH_INLINE_RE  = re.compile(r'(?<!\$)\$(?!\s)(.+?)(?<!\s)\$(?!\$)')

# Matrix shorthands: \mat{a,b;c,d}  \bmat{...}  \vmat{...}
# Commas = column separators, semicolons = row separators.
_MAT_RE  = re.compile(r'\\(mat|bmat|vmat)\{([^}]*)\}')
_MAT_ENV = {"mat": "pmatrix", "bmat": "bmatrix", "vmat": "vmatrix"}

_MODE_EDIT = "edit"
_MODE_PREVIEW = "preview"
_MODE_SPLIT = "split"

_KATEX_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist"
_KATEX_RENDER_CALL = (
    "<script>renderMathInElement(document.body,{"
    "delimiters:[{left:'$$',right:'$$',display:true},"
    "{left:'$',right:'$',display:false}],"
    "throwOnError:false});</script>"
)


@functools.lru_cache(maxsize=1)
def _resolve_katex() -> tuple[str, str, str | None]:
    """
    Return (css_head, scripts_foot, base_dir_or_None).

    css_head   — <link> tag for <head>
    scripts_foot — <script> tags placed just before </body> so the DOM is
                   already complete when renderMathInElement is called; no
                   defer/onload needed, which is unreliable inside setHtml().
    base_dir_or_None — local file:// base URL when using the bundled assets.
    """
    from cbosa import config
    local = config.PROJECT_ROOT / "cbosa" / "resources" / "katex"
    if local.is_dir() and (local / "katex.min.js").exists():
        css  = '<link rel="stylesheet" href="katex.min.css">'
        foot = (
            '<script src="katex.min.js"></script>'
            '<script src="contrib/auto-render.min.js"></script>'
            + _KATEX_RENDER_CALL
        )
        return css, foot, str(local) + "/"
    css  = f'<link rel="stylesheet" href="{_KATEX_CDN}/katex.min.css">'
    foot = (
        f'<script src="{_KATEX_CDN}/katex.min.js"></script>'
        f'<script src="{_KATEX_CDN}/contrib/auto-render.min.js"></script>'
        + _KATEX_RENDER_CALL
    )
    return css, foot, None


def _extract_math(text: str) -> tuple[str, list[tuple[str, str, bool]]]:
    """Replace $$...$$ and $...$ with placeholders so mistune won't corrupt them."""
    spans: list[tuple[str, str, bool]] = []

    def sub_display(m: re.Match) -> str:
        ph = f"ZZMD{len(spans)}ZZ"
        spans.append((ph, m.group(1), True))
        return ph

    def sub_inline(m: re.Match) -> str:
        ph = f"ZZMI{len(spans)}ZZ"
        spans.append((ph, m.group(1), False))
        return ph

    text = _MATH_DISPLAY_RE.sub(sub_display, text)
    text = _MATH_INLINE_RE.sub(sub_inline, text)
    return text, spans


def _expand_matrix_shorthands(content: str) -> str:
    """Expand \mat{a,b;c,d} → \begin{pmatrix}a & b \\ c & d\end{pmatrix}."""
    def _expand(m: re.Match) -> str:
        env = _MAT_ENV[m.group(1)]
        rows = m.group(2).split(";")
        body = " \\\\ ".join(
            " & ".join(cell.strip() for cell in row.split(","))
            for row in rows
        )
        return f"\\begin{{{env}}}{body}\\end{{{env}}}"
    return _MAT_RE.sub(_expand, content)


def _restore_math(html: str, spans: list[tuple[str, str, bool]]) -> str:
    for ph, content, display in spans:
        content = _expand_matrix_shorthands(content)
        html = html.replace(ph, f'$${content}$$' if display else f'${content}$')
    return html


def _render_markdown(text: str) -> str:
    """Convert Markdown (with [[wikilinks]] and $math$) to an HTML fragment."""
    text = _WIKILINK_RE.sub(
        lambda m: f"[{m.group(1)}](note:///{quote(m.group(1))})", text
    )
    text, math_spans = _extract_math(text)
    html = mistune.html(text)
    return _restore_math(html, math_spans)


def _build_preview_html(markdown_text: str, colors: dict, fonts: dict) -> str:
    """Render markdown to a complete HTML document styled with theme colors."""
    body = _render_markdown(markdown_text)

    bg         = colors.get("background", "#1e1e2e")
    surface    = colors.get("surface",    "#232336")
    primary    = colors.get("primary",    "#2a2a40")
    text       = colors.get("text",       "#cdd6f4")
    text_muted = colors.get("text_muted", "#8b91b0")
    accent     = colors.get("accent",     "#cba6f7")
    link       = colors.get("link",       accent)
    heading    = colors.get("heading",    accent)
    code_bg    = colors.get("code_bg",    primary)
    border     = colors.get("border",     "#383850")

    family    = fonts.get("family",       "Inter")
    size_base = fonts.get("size_base",    13)
    size_h1   = fonts.get("size_heading", 18)
    size_h2   = size_h1 - 2
    size_h3   = size_h1 - 4

    css = f"""
body {{
    background-color: {bg};
    color: {text};
    font-family: "{family}", system-ui, sans-serif;
    font-size: {size_base}px;
    line-height: 1.6;
    padding: 14px 32px;
    margin: 0;
    max-width: 900px;
}}
h1 {{
    color: {heading};
    font-size: {size_h1}px;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin: 18px 0 8px;
}}
h2 {{
    color: {heading};
    font-size: {size_h2}px;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin: 14px 0 6px;
}}
h3, h4, h5, h6 {{
    color: {heading};
    font-size: {size_h3}px;
    font-weight: 600;
    margin: 12px 0 6px;
}}
p {{ margin: 8px 0; }}
a {{ color: {link}; text-decoration: underline; }}
code {{
    background-color: {surface};
    border: 1px solid {border};
    color: {accent};
    font-family: "JetBrains Mono", monospace;
    font-size: {size_base - 1}px;
    padding: 0 4px;
}}
pre {{
    background-color: {surface};
    border: 1px solid {border};
    border-left: 2px solid {accent};
    padding: 8px 12px;
    overflow-x: auto;
    margin: 8px 0;
}}
pre code {{
    background-color: transparent;
    border: none;
    padding: 0;
    color: {text};
}}
blockquote {{
    border-left: 2px solid {accent};
    color: {text_muted};
    padding: 4px 0 4px 12px;
    margin: 8px 0;
}}
hr {{
    border: none;
    border-top: 1px dashed {border};
    margin: 10px 0;
}}
ul {{ margin: 6px 0; padding-left: 22px; }}
ol {{ margin: 6px 0; padding-left: 22px; }}
li {{ margin: 3px 0; }}
table {{
    border-collapse: collapse;
    width: 100%;
    font-size: {size_base}px;
}}
th, td {{
    border: 1px solid {border};
    padding: 4px 8px;
    text-align: left;
}}
th {{ background-color: {surface}; color: {text_muted}; }}
"""
    katex_css, katex_foot, _ = _resolve_katex()
    return (
        f"<!DOCTYPE html><html><head><style>{css}</style>{katex_css}</head>"
        f"<body>{body}{katex_foot}</body></html>"
    )


class _NotePage(QWebEnginePage):
    """QWebEnginePage that intercepts note:/// navigation and blocks external URLs."""

    note_link_clicked = pyqtSignal(str)

    def acceptNavigationRequest(
        self,
        url: QUrl,
        nav_type: "QWebEnginePage.NavigationType",
        is_main_frame: bool,
    ) -> bool:
        if url.scheme() == "note":
            self.note_link_clicked.emit(url.path().lstrip("/"))
            return False
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            return False
        return True


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

        self._bracket_hidden_fmt = QTextCharFormat()
        self._bracket_hidden_fmt.setForeground(QColor(bg_color))

        self._bracket_active_fmt = QTextCharFormat()
        self._bracket_active_fmt.setForeground(QColor(bracket_active_color))

    def update_colors(
        self,
        bg_color: str,
        link_color: str,
        bracket_active_color: str,
    ) -> None:
        """Update highlight colors and re-run highlighting (called on theme change)."""
        self._bracket_hidden_fmt.setForeground(QColor(bg_color))
        self._link_fmt.setForeground(QColor(link_color))
        self._bracket_active_fmt.setForeground(QColor(bracket_active_color))
        self.rehighlight()

    def set_cursor_position(self, block_number: int, pos_in_block: int) -> None:
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
            self.setFormat(m.start(), 2, bracket_fmt)
            self.setFormat(m.start(1), len(m.group(1)), self._link_fmt)
            self.setFormat(m.end(1), 2, bracket_fmt)


class _WikiEditor(QPlainTextEdit):
    """QPlainTextEdit that intercepts left-clicks on [[wikilinks]]."""

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
    note_saved = pyqtSignal(str)
    ask_ai_requested = pyqtSignal(str, str)  # (note_title, note_content)

    def __init__(
        self,
        store: NoteStore,
        link_index: LinkIndex,
        title: str = "Note Editor",
        parent=None,
        daily_store: NoteStore | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._store = store
        self._link_index = link_index
        self._daily_store = daily_store
        self._ai = ai_service or NullAIService()
        self._current_note: str | None = None
        self._worker: AIWorker | None = None
        self._mode = _MODE_PREVIEW
        self._theme_colors: dict = {}
        self._theme_fonts: dict = {}

        self._load_current_theme()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(6, 3, 6, 3)
        top_bar_layout.setSpacing(4)

        self._edit_btn    = QPushButton("edit")
        self._preview_btn = QPushButton("preview")
        self._split_btn   = QPushButton("split")
        for btn in (self._edit_btn, self._preview_btn, self._split_btn):
            btn.setCheckable(True)
            btn.setProperty("role", "toggle")
            btn.setFlat(True)

        top_bar_layout.addWidget(self._edit_btn)
        top_bar_layout.addWidget(self._preview_btn)
        top_bar_layout.addWidget(self._split_btn)
        top_bar_layout.addSpacing(12)

        self._summarize_btn   = QPushButton("Summarize")
        self._connections_btn = QPushButton("Find Connections")
        self._ask_ai_btn      = QPushButton("Ask AI")
        self._latex_btn       = QPushButton("→ LaTeX")
        self._summarize_btn.setEnabled(False)
        self._connections_btn.setEnabled(False)
        self._ask_ai_btn.setEnabled(False)
        self._latex_btn.setEnabled(False)
        self._latex_btn.setToolTip("Convert selected spoken/informal text to LaTeX")
        top_bar_layout.addWidget(self._summarize_btn)
        top_bar_layout.addWidget(self._connections_btn)
        top_bar_layout.addWidget(self._ask_ai_btn)
        top_bar_layout.addWidget(self._latex_btn)
        top_bar_layout.addStretch()
        layout.addWidget(top_bar)

        # ── Editor + Preview splitter ─────────────────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._editor = _WikiEditor()
        self._editor.setPlaceholderText("Open a note to edit…")
        self._editor.link_clicked.connect(self.note_link_activated)
        self._splitter.addWidget(self._editor)

        self._preview_page = _NotePage(self)
        self._preview_page.note_link_clicked.connect(self.note_link_activated)
        self._preview = QWebEngineView()
        self._preview.setPage(self._preview_page)
        self._splitter.addWidget(self._preview)

        layout.addWidget(self._splitter, stretch=1)

        # ── AI output area ───────────────────────────────────────────────
        self._label_row = QWidget()
        label_row_layout = QHBoxLayout(self._label_row)
        label_row_layout.setContentsMargins(4, 2, 4, 2)
        self._call_type_label = QLabel("")
        self._dismiss_btn = QPushButton("×")
        label_row_layout.addWidget(self._call_type_label)
        label_row_layout.addStretch()
        label_row_layout.addWidget(self._dismiss_btn)
        self._label_row.setVisible(False)
        layout.addWidget(self._label_row)

        self._output_pane = QTextEdit()
        self._output_pane.setReadOnly(True)
        self._output_pane.setVisible(False)
        layout.addWidget(self._output_pane)

        self.setWidget(container)

        # ── Syntax highlighter ───────────────────────────────────────────
        self._highlighter = WikilinkHighlighter(
            self._editor.document(),
            bg_color=self._theme_colors.get("background", "#1e1e2e"),
            link_color=self._theme_colors.get(
                "link", self._theme_colors.get("accent", "#89b4fa")
            ),
            bracket_active_color=self._theme_colors.get("text_muted", "#6c7086"),
        )
        self._editor.cursorPositionChanged.connect(self._on_cursor_position_changed)

        # ── Debounce timer for live preview ──────────────────────────────
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(200)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._editor.textChanged.connect(self._preview_timer.start)

        # ── Shortcuts ────────────────────────────────────────────────────
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self._on_summarize)

        # ── Button wiring ────────────────────────────────────────────────
        self._edit_btn.clicked.connect(lambda: self._set_mode(_MODE_EDIT))
        self._preview_btn.clicked.connect(lambda: self._set_mode(_MODE_PREVIEW))
        self._split_btn.clicked.connect(lambda: self._set_mode(_MODE_SPLIT))
        self._summarize_btn.clicked.connect(self._on_summarize)
        self._connections_btn.clicked.connect(self._on_find_connections)
        self._ask_ai_btn.clicked.connect(self._on_ask_ai)
        self._latex_btn.clicked.connect(self._on_latex_convert)
        self._dismiss_btn.clicked.connect(self._dismiss_output)

        self._set_mode(_MODE_PREVIEW)

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
        self._summarize_btn.setEnabled(True)
        self._connections_btn.setEnabled(True)
        self._ask_ai_btn.setEnabled(True)
        self._latex_btn.setEnabled(True)
        self._dismiss_output()
        self._refresh_preview()

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
            self._preview.setHtml("")

    def update_theme(self, theme_path: str) -> None:
        """Called by MainWindow when the user switches themes."""
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            self._theme_colors, self._theme_fonts = (
                ThemeEngine().get_colors_and_fonts(theme_path)
            )
        except ThemeLoadError:
            return
        self._highlighter.update_colors(
            bg_color=self._theme_colors.get("background", "#1e1e2e"),
            link_color=self._theme_colors.get(
                "link", self._theme_colors.get("accent", "#89b4fa")
            ),
            bracket_active_color=self._theme_colors.get("text_muted", "#6c7086"),
        )
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_current_theme(self) -> None:
        from cbosa import config
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        theme_path = str(config.resolve("theme", "themes/obsidian_dark.toml"))
        try:
            self._theme_colors, self._theme_fonts = (
                ThemeEngine().get_colors_and_fonts(theme_path)
            )
        except ThemeLoadError:
            self._theme_colors = {}
            self._theme_fonts = {}

    def _resolve(self, name: str) -> tuple[NoteStore, str]:
        if name.startswith("daily/") and self._daily_store is not None:
            return self._daily_store, name[len("daily/"):]
        # If the name has no "/" and no matching file, try bare-name resolution
        # (wikilinks emit bare names; the note may live in a subdirectory)
        from pathlib import Path as _Path
        from cbosa.core.note_store import NoteNotFoundError as _NNF
        if "/" not in name:
            path = self._store._root / f"{name}.md"
            if not path.exists():
                try:
                    full = self._store.resolve_name(name)
                    return self._store, full
                except _NNF:
                    pass
        return self._store, name

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._edit_btn.setChecked(mode == _MODE_EDIT)
        self._preview_btn.setChecked(mode == _MODE_PREVIEW)
        self._split_btn.setChecked(mode == _MODE_SPLIT)

        if mode == _MODE_EDIT:
            self._splitter.setSizes([1, 0])
        elif mode == _MODE_PREVIEW:
            self._splitter.setSizes([0, 1])
            self._refresh_preview()
        elif mode == _MODE_SPLIT:
            half = max(self._splitter.width() // 2, 200)
            self._splitter.setSizes([half, half])
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self._mode == _MODE_EDIT:
            return
        html = _build_preview_html(
            self._editor.toPlainText(), self._theme_colors, self._theme_fonts
        )
        _, _2, base_path = _resolve_katex()
        base_url = QUrl.fromLocalFile(base_path) if base_path else QUrl()
        self._preview.setHtml(html, base_url)

    def _on_cursor_position_changed(self) -> None:
        cursor = self._editor.textCursor()
        self._highlighter.set_cursor_position(
            cursor.blockNumber(), cursor.positionInBlock()
        )

    # ------------------------------------------------------------------
    # AI toolbar actions
    # ------------------------------------------------------------------

    def _on_summarize(self) -> None:
        if self._current_note is None:
            return
        store, bare_name = self._resolve(self._current_note)
        try:
            note = store.read(bare_name)
        except NoteNotFoundError:
            return
        self._show_output("Summary")
        self._start_worker(lambda: self._ai.summarize(note.content))

    def _on_ask_ai(self) -> None:
        if self._current_note is None:
            return
        store, bare_name = self._resolve(self._current_note)
        try:
            note = store.read(bare_name)
        except NoteNotFoundError:
            return
        self.ask_ai_requested.emit(self._current_note, note.content)

    def _on_latex_convert(self) -> None:
        cursor = self._editor.textCursor()
        selected = cursor.selectedText().strip()
        if not selected:
            return
        prompt = (
            "Convert the following spoken or informal mathematical expression to LaTeX. "
            "Return ONLY the LaTeX notation, nothing else. "
            "Use $...$ for inline math or $$...$$ for display math as appropriate.\n\n"
            f"{selected}"
        )
        self._latex_btn.setEnabled(False)
        worker = AIWorker(lambda: self._ai.chat([{"role": "user", "content": prompt}]))
        worker.result_ready.connect(lambda latex: self._replace_selection(cursor, latex))
        worker.finished.connect(lambda: self._latex_btn.setEnabled(True))
        worker.start()
        self._worker = worker

    def _replace_selection(self, cursor: QTextCursor, latex: str) -> None:
        latex = latex.strip()
        if latex:
            cursor.insertText(latex)

    def _on_find_connections(self) -> None:
        if self._current_note is None:
            return
        note_name = self._current_note
        all_notes = []
        for name in self._store.all_names():
            try:
                note = self._store.read(name)
                snippet = " ".join(note.content.split()[:75])
            except Exception:
                snippet = ""
            all_notes.append((name, snippet))
        self._show_output("Connections")
        self._start_worker(
            lambda: "\n".join(self._ai.find_connections(note_name, all_notes))
        )

    def _show_output(self, call_type: str) -> None:
        self._call_type_label.setText(call_type)
        self._output_pane.setPlainText("Thinking…")
        self._label_row.setVisible(True)
        self._output_pane.setVisible(True)

    def _dismiss_output(self) -> None:
        self._label_row.setVisible(False)
        self._output_pane.setVisible(False)

    def _start_worker(self, fn) -> None:
        self._worker = AIWorker(fn)
        self._worker.result_ready.connect(self._output_pane.setPlainText)
        self._worker.error.connect(
            lambda msg: self._output_pane.setPlainText(f"Error: {msg}")
        )
        self._worker.start()
