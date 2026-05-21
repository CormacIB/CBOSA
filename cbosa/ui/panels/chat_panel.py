"""
ChatPanel — dockable multi-turn AI chat panel.

Context modes (toggled per session, visible at all times):
  Note  — user picks a note from the combobox; full content injected as context.
  Vault — FTS5 searches the vault on each message; top-6 snippets injected.

Context gathered for each turn is stored on the message dict and rendered
inline in the thread so the user can see exactly what was sent.
"""
from __future__ import annotations

import html

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cbosa.ai.chat_session import ChatSession
from cbosa.ai.service import AIService, NullAIService
from cbosa.ai.worker import AIWorker
from cbosa.core.note_store import NoteNotFoundError, NoteStore
from cbosa.ui.panels import BasePanel

_CTX_NOTE  = "note"
_CTX_VAULT = "vault"
_NO_NOTE   = "— pick a note —"


class ChatPanel(BasePanel):
    def __init__(
        self,
        ai_service: AIService | None = None,
        search_index=None,
        note_store: NoteStore | None = None,
        title: str = "Chat",
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._ai           = ai_service or NullAIService()
        self._search_index = search_index
        self._store        = note_store
        self._session      = ChatSession()
        self._ctx_mode     = _CTX_NOTE
        self._worker: AIWorker | None = None

        self._theme_colors: dict = {}
        self._load_current_theme()
        self._build_ui()
        self._populate_note_picker()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def set_note_context(self, title: str, content: str) -> None:
        """Called by MainWindow when note editor's Ask AI button is pressed."""
        idx = self._note_picker.findText(title)
        if idx >= 0:
            self._note_picker.setCurrentIndex(idx)
        else:
            # Note not in list yet — insert it at top and select it
            self._note_picker.insertItem(1, title)
            self._note_picker.setCurrentIndex(1)
        self._set_ctx(_CTX_NOTE)

    # ------------------------------------------------------------------
    # Private — build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Context toggle ────────────────────────────────────────────────
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(4)

        self._ctx_note_btn  = QPushButton("Note")
        self._ctx_vault_btn = QPushButton("Vault")
        for btn in (self._ctx_note_btn, self._ctx_vault_btn):
            btn.setCheckable(True)
            btn.setProperty("role", "toggle")
            btn.setFlat(True)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(48)

        toggle_layout.addWidget(self._ctx_note_btn)
        toggle_layout.addWidget(self._ctx_vault_btn)
        toggle_layout.addStretch()
        toggle_layout.addWidget(clear_btn)
        layout.addWidget(toggle_row)

        # ── Note picker (Note mode) ───────────────────────────────────────
        self._note_picker = QComboBox()
        self._note_picker.addItem(_NO_NOTE)
        layout.addWidget(self._note_picker)

        # ── Vault status (Vault mode) ─────────────────────────────────────
        self._vault_status = QLabel("Vault search ready")
        self._vault_status.setProperty("muted", "true")
        layout.addWidget(self._vault_status)

        # ── Message thread ────────────────────────────────────────────────
        self._thread = QTextEdit()
        self._thread.setReadOnly(True)
        self._thread.setPlaceholderText("Start a conversation…")
        layout.addWidget(self._thread, stretch=1)

        # ── Input row ─────────────────────────────────────────────────────
        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(4)

        self._input    = QLineEdit()
        self._input.setPlaceholderText("Ask something…")
        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedWidth(52)

        input_layout.addWidget(self._input, stretch=1)
        input_layout.addWidget(self._send_btn)
        layout.addWidget(input_row)

        # ── Context window footer ─────────────────────────────────────────
        self._ctx_footer = QLabel()
        self._ctx_footer.setProperty("muted", "true")
        layout.addWidget(self._ctx_footer)

        self.setWidget(container)

        # ── Wiring ────────────────────────────────────────────────────────
        self._ctx_note_btn.clicked.connect(lambda: self._set_ctx(_CTX_NOTE))
        self._ctx_vault_btn.clicked.connect(lambda: self._set_ctx(_CTX_VAULT))
        self._send_btn.clicked.connect(self._on_send)
        self._input.returnPressed.connect(self._on_send)
        clear_btn.clicked.connect(self._on_clear)

        self._set_ctx(_CTX_NOTE)
        self._update_ctx_footer()

    def _load_current_theme(self) -> None:
        from cbosa import config
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        theme_path = str(config.resolve("theme", "themes/dark_default.toml"))
        try:
            self._theme_colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
        except ThemeLoadError:
            self._theme_colors = {}

    def update_theme(self, theme_path: str) -> None:
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            self._theme_colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
        except ThemeLoadError:
            return
        self._refresh_thread()

    def _populate_note_picker(self) -> None:
        if self._store is None:
            return
        names = sorted(self._store.all_names())
        for name in names:
            self._note_picker.addItem(name)

    # ------------------------------------------------------------------
    # Private — interaction
    # ------------------------------------------------------------------

    def _set_ctx(self, mode: str) -> None:
        self._ctx_mode = mode
        self._ctx_note_btn.setChecked(mode == _CTX_NOTE)
        self._ctx_vault_btn.setChecked(mode == _CTX_VAULT)
        self._note_picker.setVisible(mode == _CTX_NOTE)
        self._vault_status.setVisible(mode == _CTX_VAULT)

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or (self._worker and self._worker.isRunning()):
            return
        self._input.clear()

        context, ctx_label = self._gather_context(text)

        # Store context metadata on the user message for display
        self._session.messages.append({
            "role": "user",
            "content": text,
            "context": context,
            "ctx_label": ctx_label,
        })
        self._refresh_thread()
        self._update_ctx_footer()
        self._send_btn.setEnabled(False)

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in self._session.messages
        ]

        def _run():
            return self._ai.chat(messages, context)

        self._worker = AIWorker(_run)
        self._worker.result_ready.connect(self._on_response)
        self._worker.error.connect(lambda e: self._on_response(f"Error: {e}"))
        self._worker.start()

    def _gather_context(self, query: str) -> tuple[list[str], str]:
        """Return (context_snippets, human_readable_label)."""
        if self._ctx_mode == _CTX_NOTE:
            name = self._note_picker.currentText()
            if name == _NO_NOTE or self._store is None:
                return [], "Note: none selected"
            try:
                note = self._store.read(name)
                return [f"[{name}]\n{note.content}"], f"Note: {name}"
            except NoteNotFoundError:
                return [], f"Note: {name} (not found)"

        if self._ctx_mode == _CTX_VAULT:
            if self._search_index is None:
                return [], "Vault: no index"
            try:
                results = self._search_index.search_snippets(query)
            except Exception as exc:
                self._vault_status.setText(f"Vault error: {exc}")
                return [], f"Vault: search error"
            if not results:
                self._vault_status.setText("Vault: no matches found")
                return [], "Vault: 0 matches"
            self._vault_status.setText(f"Vault: {len(results)} note(s) matched")
            snippets = [f"[{name}]\n{snippet}" for name, snippet in results]
            sources  = ", ".join(name for name, _ in results)
            return snippets, f"Vault: {len(results)} match(es) — {sources}"

        return [], ""

    def _update_ctx_footer(self) -> None:
        info = self._ai.context_info()
        model   = info.get("model", "")
        num_ctx = info.get("num_ctx", 0)

        # Rough token estimate: total chars across all messages ÷ 4
        total_chars = sum(len(m["content"]) for m in self._session.messages)
        est_tokens  = total_chars // 4

        if num_ctx:
            pct = min(100, round(est_tokens / num_ctx * 100))
            footer = f"{model}  ·  {est_tokens:,} / {num_ctx:,} tokens (~{pct}%)"
        elif model:
            footer = f"{model}  ·  ~{est_tokens:,} tokens used"
        else:
            footer = f"~{est_tokens:,} tokens used" if est_tokens else ""

        self._ctx_footer.setText(footer)

    def _on_response(self, text: str) -> None:
        self._session.add_assistant(text)
        self._refresh_thread()
        self._update_ctx_footer()
        self._send_btn.setEnabled(True)

    def _on_clear(self) -> None:
        self._session.reset()
        self._thread.clear()

    def _refresh_thread(self) -> None:
        c = self._theme_colors
        bg      = c.get("background", "#1e1e2e")
        surface = c.get("surface",    "#313244")
        text    = c.get("text",       "#cdd6f4")
        muted   = c.get("text_muted", "#6c7086")

        parts = [f"<html><body style='margin:0;padding:4px;background:{bg};color:{text}'>"]
        for msg in self._session.messages:
            escaped = html.escape(msg["content"]).replace("\n", "<br>")
            if msg["role"] == "user":
                parts.append(
                    f'<p style="text-align:right;margin:6px 0 2px 0">'
                    f'<span style="background:{surface};color:{text};padding:4px 10px;'
                    f'border-radius:6px;display:inline-block">{escaped}</span></p>'
                )
                ctx_label = msg.get("ctx_label", "")
                if ctx_label:
                    parts.append(
                        f'<p style="text-align:right;margin:0 0 4px 0">'
                        f'<span style="color:{muted};font-size:10px">'
                        f'&#8627; {html.escape(ctx_label)}</span></p>'
                    )
            elif msg["role"] == "assistant":
                parts.append(
                    f'<p style="text-align:left;margin:4px 0">'
                    f'<span style="background:{bg};color:{text};padding:4px 10px;'
                    f'border-radius:6px;display:inline-block">{escaped}</span></p>'
                )
        parts.append("</body></html>")
        self._thread.setHtml("".join(parts))
        sb = self._thread.verticalScrollBar()
        sb.setValue(sb.maximum())
