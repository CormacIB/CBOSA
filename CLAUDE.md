# CBOSA — Claude Code Guide

## What this project is

CBOSA is a local-first personal OS desktop app built with **PyQt6**. It brings notes, finance, email, and Canvas LMS data into a single customizable dashboard. All user data lives in plain `.md` files and a local SQLite database — no cloud dependency.

Run with: `python main.py` (must be invoked from the project root — see KI-4 below).

---

## Architecture

```
cbosa/
  app.py              # Bootstrap: creates QApplication, loads theme, registers panels
  config.py           # Reads cbosa.toml; falls back to defaults on import
  ui/
    main_window.py    # MainWindow (QMainWindow) — hosts CDockManager as central widget
    command_palette.py# Ctrl+P overlay for adding panels
    theme_engine.py   # Reads TOML → generates QSS → applies to QApplication
    banner.py           # App banner widget
    panels/
      __init__.py     # PanelRegistry, BasePanel
      note_browser.py # NoteBrowserPanel — folder tree + tag filter
      note_editor.py  # NoteEditorPanel — QPlainTextEdit editor + QWebEngineView preview.
                      #   Preview renders Markdown → HTML via mistune + KaTeX for math.
                      #   Math delimiters: $...$ (inline), $$...$$ (display block).
                      #   _extract_math()/_restore_math() protect delimiters from mistune
                      #   before HTML is built; KaTeX scripts placed at end of <body>.
      finance_summary_panel.py  # FinanceSummaryPanel — QPainter bar chart (category × cost)
      task_panel.py   # TaskPanel — task list view
      chat_panel.py   # ChatPanel — multi-turn AI chat; Note/Vault context toggle;
                      #   note picker combobox; inline context provenance; ctx-window footer
  core/
    note_store.py     # NoteStore — CRUD on .md files with YAML frontmatter
    link_index.py     # LinkIndex — bidirectional [[wikilink]] map
    tag_index.py      # TagIndex — #tag → notes map
    search_index.py   # SearchIndex — SQLite FTS5 full-text search.
                      #   search(query) -> list[str] (names only)
                      #   search_snippets(query, limit=6) -> list[tuple[str,str]] (name, excerpt)
    task_store.py     # TaskStore — task persistence
  ai/
    service.py        # AIService ABC + NullAIService. Methods: summarize, embed,
                      #   find_connections, extract_tasks, key_points, answer,
                      #   chat(messages, context=[]), context_info() -> dict
    ollama_service.py # OllamaAIService — POST /api/chat (NOT /api/generate).
                      #   Prepends _SYSTEM_PROMPT as system message automatically.
                      #   context_info() returns {model, num_ctx} from config.
    worker.py         # AIWorker — QThread wrapper; emits result_ready(str) / error(str)
    chat_session.py   # ChatSession dataclass — holds messages list for multi-turn chat
  modules/            # Future: Email, Canvas
  resources/
    katex/            # Bundled KaTeX assets (JS, CSS, fonts) for offline math rendering.
                      #   Populated once by: python3 tools/fetch_katex.py
                      #   If absent, _resolve_katex() falls back to jsDelivr CDN.
    banner.png        # Optional pixel art banner (48 px height, nearest-neighbor scaled)
tests/
  conftest.py
  test_note_engine.py
  test_note_panels.py
  test_panel_system.py
  test_theme_engine.py
themes/
  dark_default.toml
  light.toml
data/
  notes/              # User .md notes (source of truth)
  daily/              # Auto-created daily notes (YYYY-MM-DD.md)
  captures/           # Notes created by the capture engine
```

---

## Key conventions

- **Theming:** All colors and fonts come from a TOML theme file (`[colors]` + `[fonts]`). Never hardcode colors in Python or QSS outside the theme engine — including inside HTML strings rendered in QTextEdit widgets (read from `_theme_colors` dict instead). Swapping themes = changing `theme` in `cbosa.toml` and restarting. The macOS font fallback in `theme_engine.py` is `"Helvetica Neue"` — `"SF Pro Text"` is not exposed in Qt's font database on macOS.
- **Panels:** Every panel extends `BasePanel`. Panels are registered in `app.py::_register_panels()`. Opening a panel goes through `PanelRegistry`.
- **Note data flow:** `NoteStore` is the only writer to `.md` files. Indexes (`LinkIndex`, `TagIndex`, `SearchIndex`) are built from `NoteStore` on startup and must be explicitly `rebuild()`-ed after in-app edits (external edits are not yet watched — see KI-1).
- **Secrets:** IMAP credentials and Canvas API token go in `~/.cbosa/secrets.toml` — never in code or `cbosa.toml`. Missing secrets → graceful "configure credentials" prompt.
- **Background work:** IMAP sync and Canvas sync must run in `QThread` workers, not the main thread. All AI calls go through `AIWorker` (same pattern).
- **AI backend:** `OllamaAIService` uses `/api/chat` (not `/api/generate`). It auto-prepends a system prompt. Configure via `[ai]` in `cbosa.toml`: `backend = "ollama"`, `endpoint`, `model`, `num_ctx`. Hermes models (e.g. `hermes3`) work well. The `ChatPanel` requires `ai_service`, `search_index`, and `note_store` — all passed from `app.py::_register_panels()`.
- **Banner:** Loads pixel art from `cbosa/resources/banner.png` if present (scaled to 48px height with nearest-neighbor). Falls back to Unicode block art string if file is missing.
- **Tests:** Use `pytest`. Test behavior through public interfaces — no mocking Qt widgets. `NoteStore`/indexes use temp dirs and in-memory SQLite. `CanvasApiClient`/`TaskExtractor` mock at the `httpx` transport layer.

---

## Issue status (as of 2026-05-15)

GitHub repo: CormacIB/CBOSA

| # | Title | Status |
|---|-------|--------|
| 1 | App Bootstrap + Theming | Done |
| 2 | Panel Docking System + Command Palette | Done |
| 3 | Note Engine (NoteStore, LinkIndex, TagIndex, FTS5) | Done |
| 4 | Note Browser + Editor Panels | Done (with known issues below) |
| 5 | Daily Note Auto-Creation | Done |
| 6 | Wikilink Rename Propagation | Done |
| 7 | Graph View Panel | Done |
| 8 | Finance Ledger + Panel | Done |
| 9 | Email IMAP + Task Extraction + Panel | Done |
| 10 | Canvas LMS Sync + Panel | Done |
| 11 | Capture Engine + Panel | Done |
| 12 | AI Service Interface + NullAIService Wiring | Done |
| 16 | Add PyQtAds dependency + migrate BasePanel to CDockWidget | Done |
| 17 | Integrate CDockManager into MainWindow | Done |
| 18 | Migrate layout persistence to PyQtAds state serialization | Done |
| 19 | Theme PyQtAds panel chrome via ThemeEngine QSS | Done |
| 20 | Task dataclass (shared core) | Done |
| 21 | OllamaAIService + [ai] config + availability warning | Done |
| 22 | Note Editor AI toolbar + AIWorker | Done |
| 23 | Email panel redesign — Action Items tab + AI task extraction | Done |
| 24 | Hermes/Ollama chat integration — /api/chat migration + ChatPanel | Done |

---

## Known issues

### KI-1: No filesystem watcher on note indexes
**Area:** `core/link_index.py`, `core/tag_index.py`, `core/search_index.py`

Indexes only rebuild on startup or after an explicit in-app save. Files edited externally (another editor, sync tool) leave indexes stale until restart.

**Fix:** Wire `QFileSystemWatcher` into `NoteStore` to trigger `rebuild()` on external file changes. Planned as a follow-up to Issue #4.

---

### KI-2: Command palette requires double-click or Enter
**Area:** `cbosa/ui/command_palette.py`

Single-clicking a panel type does nothing visible — users must double-click or press Enter. The affordance is unclear.

**Fix:** Add an "Add Panel" button or a hint label to the dialog.

---

### ~~KI-3: Finance / Email / Canvas panels are empty `BasePanel` stubs~~ — PARTIALLY FIXED

Finance panel (`FinanceSummaryPanel`) is now implemented with a QPainter-based bar chart, period selector, and budget tracking. Email and Canvas panels remain stubs pending Issues #9–#10.

**Chart note:** `FinanceSummaryPanel` uses a custom `QPainter` `QWidget` — not pyqtgraph — for the bar chart. Bar width is fixed in pixels; slot width uses `min(MAX_SLOT_PX, chart_w / n)` so bars are always compact and all n bars always fit the visible panel width.

---

### ~~KI-4: Config and theme paths are relative to the working directory~~ — FIXED

`config.py` now defines `PROJECT_ROOT = Path(__file__).parent.parent` and uses it as the base for the default `cbosa.toml` lookup and for a new `config.resolve()` helper. `app.py` calls `config.resolve()` for both `theme` and `data_dir`, so paths are always absolute regardless of working directory.

---

## Config file (`cbosa.toml` — project root)

```toml
theme = "themes/light.toml"          # currently active theme (light)
data_dir = "data"                     # root for notes/, daily/, captures/

[ai]
backend  = "ollama"
endpoint = "http://localhost:11434"
model    = "hermes3"                  # or any Ollama model name
num_ctx  = 8192
```

## Theme TOML schema

```toml
[colors]
background = "#1e1e2e"
surface    = "#313244"
primary    = "#cba6f7"
accent     = "#89b4fa"
text       = "#cdd6f4"
text_muted = "#6c7086"
border     = "#45475a"

[fonts]
family       = "Segoe UI"
size_base    = 13
size_small   = 11
size_heading = 18
```

---

## Dependencies

```
PyQt6>=6.7
PyQt6Ads>=4.5.0       # Advanced Docking System — CDockManager, CDockWidget
toml
mistune>=3.0          # Markdown → HTML (note preview)
python-frontmatter    # YAML frontmatter in .md files
httpx                 # Canvas API + URL capture
beautifulsoup4        # Article text extraction (Issue #11)
yt-dlp                # YouTube capture (Issue #11)
pypdf                 # PDF capture (Issue #11)
networkx              # Graph layout (Issue #7)
pyqtgraph             # Graph rendering (Issue #7)
pytest
```

Install: `pip install -r requirements.txt`

---

## Testing

```bash
pytest                             # run all tests
pytest tests/test_note_engine.py   # run a specific file
```

Tests must not mock Qt widgets. Use temp directories for `NoteStore`. Use in-memory SQLite for `SearchIndex`. Mock HTTP at the `httpx` transport layer for `CanvasApiClient` and `TaskExtractor`.

`ThemeEngine`, `AIService/NullAIService`, and `UrlFetcher` are explicitly **not** unit-tested (deferred — see PRD.md Testing Decisions).
