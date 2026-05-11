# CBOSA — GitHub Issues (ready to publish)

All issues should be labelled `ready-for-agent`. Publish in the order listed — each issue references real issue numbers from the ones above it.

---

## Issue 1: App Bootstrap + Theming

**Labels:** `ready-for-agent`

### What to build

Bootstrap the PyQt6 application and implement the theming engine. The app launches to an empty window. A TOML theme file is loaded on startup and converted to a QSS stylesheet applied globally — every widget in the app reflects the active theme's colors and fonts. Swapping themes requires only changing one config value and restarting.

Ship two bundled themes: a dark default and a light variant.

### Acceptance criteria

- [ ] `python main.py` launches without errors on Windows
- [ ] `dark_default.toml` is loaded and QSS is applied — background, surface, accent, text, and border colors are visible throughout the window
- [ ] `light.toml` is included and the app fully re-themes when the config points to it
- [ ] No colors are hardcoded anywhere outside the theme engine
- [ ] Theme TOML schema supports `[colors]` (background, surface, primary, accent, text, text_muted, border) and `[fonts]` (family, size_base, size_small, size_heading)
- [ ] A missing or malformed theme file produces a clear error message, not a crash

### Blocked by

None — can start immediately

---

## Issue 2: Panel Docking System + Command Palette

**Labels:** `ready-for-agent`

### What to build

Implement the core workspace: a dockable, floatable, tabbable panel system using Qt's `QDockWidget`. A `PanelRegistry` knows about all available panel types. A `BasePanel` provides the shared title bar and close button. A `Ctrl+P` command palette lets the user add new panels or search. The layout (which panels are open, where they are) is saved to `~/.cbosa/layout.json` on close and restored on open.

### Acceptance criteria

- [ ] Main window starts empty with a visible prompt to add a panel
- [ ] `Ctrl+P` opens an overlay listing all available panel types
- [ ] Selecting a panel type from the palette opens it as a dock widget
- [ ] Panels can be dragged to rearrange, floated as standalone windows, and tabbed together
- [ ] Closing a panel removes it from the workspace without losing data
- [ ] Layout is saved on close and fully restored on next launch
- [ ] All panels inherit the active theme correctly

### Blocked by

Blocked by #1

---

## Issue 3: Note Engine — NoteStore, LinkIndex, TagIndex, FTS5 Search

**Labels:** `ready-for-agent`

### What to build

The core data engine for notes. `NoteStore` reads and writes `.md` files with YAML frontmatter. `LinkIndex` parses `[[wikilinks]]` across all notes and maintains a bidirectional map (which notes link to which). `TagIndex` parses `#tags` and maintains a tag-to-notes map. SQLite with FTS5 powers full-text search across note content. All indexes rebuild from the file system on startup and update on file-change events.

Tests cover `NoteStore` (CRUD + frontmatter round-trip), `LinkIndex` (bidirectional correctness, missing note handling), and `TagIndex` (tag→notes accuracy).

### Acceptance criteria

- [ ] Creating, reading, updating, and deleting a `.md` file via `NoteStore` works correctly
- [ ] YAML frontmatter (title, tags, date, related) round-trips without data loss
- [ ] `[[NoteA]]` in Note B makes the link index show B→A and A←B
- [ ] `#tag` in a note appears in the tag index mapping that tag to the note
- [ ] Full-text search on a note's content returns that note
- [ ] All three modules have passing `pytest` tests using temporary directories and in-memory SQLite
- [ ] Indexes update when a file is changed on disk (filesystem watcher)

### Blocked by

Blocked by #1

---

## Issue 4: Note Browser + Editor Panels

**Labels:** `ready-for-agent`

### What to build

Two panels that together form the primary note-taking interface. The Note Browser shows a folder tree of all notes with tag filtering. The Note Editor shows a raw Markdown editor (`QPlainTextEdit`) alongside a live rendered preview (`QWebEngineView`) that updates as you type. Both panels are wired to the note engine from Issue 3.

### Acceptance criteria

- [ ] Note Browser panel shows the `data/notes/` folder tree
- [ ] Clicking a note in the browser opens it in the editor
- [ ] Tag filter in the browser narrows the displayed notes to those with the selected tag
- [ ] Note Editor shows raw Markdown alongside rendered HTML preview
- [ ] Preview updates within ~500ms of a keystroke (debounced)
- [ ] `[[wikilinks]]` in the preview are rendered as clickable links that open the target note
- [ ] Creating a new note via the browser creates the `.md` file on disk
- [ ] Changes auto-save (or save on `Ctrl+S`)

### Blocked by

Blocked by #2, #3

---

## Issue 5: Daily Note Auto-Creation

**Labels:** `ready-for-agent`

### What to build

On every app launch, automatically create a daily note at `data/daily/YYYY-MM-DD.md` if one doesn't already exist for today. The note gets minimal frontmatter (title, date). It appears in the Note Browser and can be opened like any other note.

### Acceptance criteria

- [ ] On launch, today's daily note is created if it doesn't exist
- [ ] If the daily note already exists, it is not overwritten
- [ ] Daily notes appear under `data/daily/` in the Note Browser
- [ ] The daily note has frontmatter with `title` and `date` populated

### Blocked by

Blocked by #4

---

## Issue 6: Wikilink Rename Propagation

**Labels:** `ready-for-agent`

### What to build

When the user renames or moves a note, all `[[wikilinks]]` pointing to that note across every other note are automatically updated to reflect the new name. No broken links after a rename.

### Acceptance criteria

- [ ] Renaming Note A from the Note Browser updates all `[[Note A]]` references in other notes to `[[New Name]]`
- [ ] Moving a note to a different folder updates all references correctly
- [ ] The link index reflects the updated state immediately after the rename
- [ ] Notes with no references to the renamed note are not modified
- [ ] A rename that would create a duplicate note name is rejected with a clear error

### Blocked by

Blocked by #4

---

## Issue 7: Graph View Panel

**Labels:** `ready-for-agent`

### What to build

An interactive force-directed graph panel. Nodes are notes; edges are `[[wikilinks]]`. Node positions are computed with the Fruchterman-Reingold algorithm. The user can zoom, pan, and click any node to open that note in the editor. The graph updates in real time when links are added or removed in the editor.

### Acceptance criteria

- [ ] Graph panel shows all notes as nodes and all wikilinks as edges
- [ ] Force-directed layout separates clusters visually
- [ ] Clicking a node opens that note in the Note Editor panel
- [ ] Zoom (scroll wheel) and pan (drag) work smoothly
- [ ] Adding a `[[link]]` in the editor causes the corresponding edge to appear in the graph within ~1 second
- [ ] Isolated notes (no links) still appear as nodes

### Blocked by

Blocked by #3, #4

---

## Issue 8: Finance Ledger + Panel

**Labels:** `ready-for-agent`

### What to build

A personal finance ledger. Users manually log transactions (date, amount, description, category). Categories are user-defined. The Finance panel shows a table of all transactions, an add/edit form, and a per-category spending summary for any selected time period. All data is stored in SQLite locally. Tests cover the `Ledger` module.

### Acceptance criteria

- [ ] User can add a transaction with date (`YYYY-MM-DD`), amount (positive or negative), description, and category
- [ ] User can edit or delete any existing transaction
- [ ] User can create and delete spending categories
- [ ] Finance panel shows a sortable/filterable table of all transactions
- [ ] Category totals update immediately when a transaction is added or edited
- [ ] Time period filter (e.g., this month, last 3 months) narrows the summary
- [ ] `Ledger` module has passing `pytest` tests for CRUD and totals calculation

### Blocked by

Blocked by #2

---

## Issue 9: Email IMAP + Task Extraction + Panel

**Labels:** `ready-for-agent`

### What to build

Email integration via IMAP. Credentials are read from `~/.cbosa/secrets.toml` — never from code. On connect, recent emails are fetched and cached in SQLite. A task extractor scans email subject/body text for action items using regex heuristics (deadline keywords, requests, follow-ups). The Email panel shows the inbox list, a message reader, and a sidebar of extracted tasks. Credential errors degrade gracefully with a setup prompt. Tests cover `TaskExtractor`.

### Acceptance criteria

- [ ] App reads IMAP credentials from `~/.cbosa/secrets.toml`
- [ ] Inbox loads and displays recent email subjects, senders, and dates
- [ ] Clicking an email displays its full content in the message reader
- [ ] Email search by keyword, sender, or date filters the inbox list
- [ ] Task extractor surfaces action items from email text in the task sidebar
- [ ] Email content is cached in SQLite and viewable offline after first fetch
- [ ] Missing `secrets.toml` shows a "configure credentials" prompt instead of crashing
- [ ] `TaskExtractor` has passing `pytest` tests against fixture email bodies

### Blocked by

Blocked by #2

---

## Issue 10: Canvas LMS Sync + Panel

**Labels:** `ready-for-agent`

### What to build

Canvas LMS integration via REST API. A personal access token is read from `~/.cbosa/secrets.toml`. The sync fetches assignments (name, due date, course, points), grades (per-course and per-assignment), and course file lists. All data is cached in SQLite with a `synced_at` timestamp. The Canvas panel shows an upcoming assignment timeline, a grade table, and a file browser. Sync runs in a background thread to avoid blocking the UI. Tests cover `CanvasApiClient` with mocked HTTP responses.

### Acceptance criteria

- [ ] App reads Canvas API token from `~/.cbosa/secrets.toml`
- [ ] Canvas panel shows upcoming assignments sorted by due date
- [ ] Grade table shows current and final scores per course and per assignment
- [ ] File browser lists course files and syllabus
- [ ] Sync runs in a background thread — UI remains responsive during sync
- [ ] Cached data is shown immediately on launch; sync updates it in the background
- [ ] Missing token shows a "configure credentials" prompt instead of crashing
- [ ] `CanvasApiClient` has passing `pytest` tests against mocked HTTP responses

### Blocked by

Blocked by #2

---

## Issue 11: Capture Engine + Panel

**Labels:** `ready-for-agent`

### What to build

An information capture pipeline. The Capture panel accepts a URL or dropped PDF file. For article URLs, content is fetched and extracted via `BeautifulSoup`. For YouTube URLs, metadata and transcript are extracted via `yt-dlp`. For PDFs, text is extracted page-by-page via `pypdf`. The extracted content is assembled into a `.md` note under `data/captures/` with frontmatter (source, capture date, summary placeholder). After creation, the system scans the link index and suggests existing notes that may be related — the user accepts or rejects each suggestion before any link is created.

### Acceptance criteria

- [ ] Pasting an article URL into the Capture panel creates a note with extracted text and frontmatter
- [ ] Pasting a YouTube URL creates a note with title, description, and transcript if available
- [ ] Dropping a PDF creates a note with extracted text content
- [ ] All captured notes are filed under `data/captures/`
- [ ] After capture, related existing notes are suggested — user can accept or reject each link
- [ ] Accepting a suggestion adds a `[[wikilink]]` in the captured note; rejecting does nothing
- [ ] The capture panel shows progress feedback during fetch/extraction
- [ ] A failed fetch (404, network error) shows a clear error and does not create a partial note

### Blocked by

Blocked by #4

---

## Issue 12: AI Service Interface + NullAIService Wiring

**Labels:** `ready-for-agent`

### What to build

Define the `AIService` abstract interface and implement `NullAIService` as a no-op stub. Wire every panel and module that will eventually use AI to call through `AIService` — the note editor's connection suggester, the capture engine's summarizer, the email panel's task extractor fallback, the finance panel's natural language query hook. No visible behavior changes: all stubs return empty results. The architecture is now ready for any AI backend to be plugged in by implementing the interface and updating one config entry.

The `AIService` interface shape (from design session):

```python
class AIService(ABC):
    def summarize(self, text: str) -> str: ...
    def embed(self, text: str) -> list[float]: ...
    def find_connections(self, note_id: str, all_notes: list) -> list[str]: ...
    def extract_tasks(self, text: str) -> list[str]: ...
    def answer(self, query: str, context: list[str]) -> str: ...
```

### Acceptance criteria

- [ ] `AIService` abstract class exists with the five methods above
- [ ] `NullAIService` implements all five as no-ops returning correct empty types
- [ ] All panels that will eventually use AI call through `AIService`, not any runtime directly
- [ ] Swapping `NullAIService` for a real implementation requires only one config change
- [ ] App runs identically with `NullAIService` — no errors, no regressions
- [ ] The active `AIService` implementation is injected at startup (not imported directly by panels)

### Blocked by

Blocked by #4, #8, #9, #10, #11
