# CBOSA — Personal OS: Product Requirements Document

## Problem Statement

Managing personal knowledge, finances, academic obligations, and communications currently requires juggling multiple disconnected tools — a note app, a spreadsheet, a student portal, an email client — none of which talk to each other. Finding a connection between a lecture note and an email thread, or between a financial decision and a Canvas deadline, requires manual effort and context-switching. There is no single place where a person's information accumulates intelligently over time, links itself together, and eventually becomes queryable by an AI that knows the full personal context.

---

## Solution

CBOSA is a local-first personal OS built as a PyQt6 desktop application. It brings notes, finances, email, and Canvas LMS data into a single customizable dashboard where every piece of information can be linked, searched, and eventually understood by a pluggable local AI model. Data lives in human-readable Markdown files and a local SQLite database — no cloud dependency, no vendor lock-in. The interface is fully themeable via TOML config files, and the panel layout is drag-and-drop configurable so the workspace adapts to what matters that day.

---

## User Stories

### Notes & Knowledge Management

1. As a user, I want to create Markdown notes in a folder hierarchy, so that I can organize my knowledge in a structure that makes sense to me.
2. As a user, I want to add `[[wikilinks]]` inside notes to link them to other notes, so that related ideas are explicitly connected.
3. As a user, I want to use `#tags` inside notes to cross-cut topics that span multiple folders, so that I can find thematically related content regardless of where it is filed.
4. As a user, I want to see a live Markdown preview as I type, so that I can see formatted output without switching modes.
5. As a user, I want to browse my notes through a folder tree with tag filtering, so that I can quickly navigate to what I need.
6. As a user, I want bidirectional links — when I link from Note A to Note B, I can see from Note B that Note A links to it, so that I can traverse the graph in any direction.
7. As a user, I want to full-text search across all my notes, so that I can find a note even when I don't remember where it is filed.
8. As a user, I want a daily note automatically created for today's date, so that I have a consistent place to capture daily thoughts without naming a file.
9. As a user, I want YAML frontmatter in my notes (title, tags, date, related), so that structured metadata is stored alongside the prose.
10. As a user, I want to rename or move a note and have all wikilinks pointing to it automatically updated, so that my link graph doesn't break.

### Graph View

11. As a user, I want an interactive force-directed graph showing my notes as nodes and wikilinks as edges, so that I can visually understand how my knowledge is connected.
12. As a user, I want to click a node in the graph to open that note in the editor, so that the graph is a navigation tool, not just a visualization.
13. As a user, I want the graph to update in real time as I add or remove links in the editor, so that it always reflects the current state of my notes.
14. As a user, I want to zoom and pan the graph, so that I can explore large note collections without losing context.

### Finance Module

15. As a user, I want to manually log financial transactions with a date, amount, description, and category, so that I have a complete personal ledger.
16. As a user, I want to define my own spending categories (e.g., Food, Rent, Books, Entertainment), so that the categorization reflects my actual life.
17. As a user, I want to see a summary of spending per category for any time period, so that I can understand where my money goes.
18. As a user, I want to edit or delete transactions after the fact, so that I can correct mistakes.
19. As a user, I want the finance data stored in SQLite locally, so that it is private and doesn't require an internet connection.

### Email (IMAP)

20. As a user, I want to connect my email account via IMAP credentials stored in a local secrets file, so that I can read emails inside CBOSA without exposing credentials in code.
21. As a user, I want to browse my inbox and read email messages inside CBOSA, so that I don't need to leave the app to check email.
22. As a user, I want to search my emails by keyword, sender, or date, so that I can find relevant correspondence quickly.
23. As a user, I want the system to automatically extract action items from emails (deadlines, requests, follow-ups), so that tasks are surfaced without manual processing.
24. As a user, I want extracted email tasks to appear as linkable items I can connect to notes, so that context around a task is preserved.
25. As a user, I want email content cached locally in SQLite so that I can browse recent emails offline, so that I'm not dependent on connectivity.

### Canvas LMS Integration

26. As a user, I want to connect my Canvas LMS account via a personal API token, so that CBOSA can pull my academic data securely.
27. As a user, I want to see all upcoming assignment due dates from Canvas in a unified timeline, so that I never miss a deadline.
28. As a user, I want to see my current grades per course and per assignment inside CBOSA, so that I have an academic overview without logging into Canvas.
29. As a user, I want to browse my Canvas course files and syllabus inside CBOSA, so that I can link course materials directly to related notes.
30. As a user, I want Canvas data to sync automatically on a configurable schedule and be cached locally, so that I have up-to-date academic info without manual refresh.

### Information Capture

31. As a user, I want to paste a URL (article, YouTube video, etc.) into a capture panel and have CBOSA automatically fetch and summarize it into a note, so that any piece of online content I find valuable is preserved and processed with zero friction.
32. As a user, I want to drop a PDF file into the capture panel and have its text extracted and summarized into a note, so that offline documents are just as easy to capture as web content.
33. As a user, I want captured content to be saved as a Markdown note with frontmatter (source URL, capture date, summary), so that it is searchable and linkable like any other note.
34. As a user, I want the system to suggest existing notes that the captured content might be related to, so that new information is automatically woven into my existing knowledge graph.
35. As a user, I want to accept or reject suggested connections before they are made, so that the link graph is always intentional, not noisy.
36. As a user, I want captured notes filed under `data/captures/` automatically, so that there is a clear distinction between authored and captured content.

### Theming & Customization

37. As a user, I want to define my color scheme, font family, and font sizes in a TOML theme file, so that the visual experience is exactly what I want.
38. As a user, I want to switch themes by changing one config value pointing to a different theme file, so that swapping the look is instant.
39. As a user, I want the entire application — all panels, text, borders, backgrounds — to reflect the active theme, so that there are no unstyled elements.
40. As a user, I want to create and share custom theme files, so that I can version-control my visual preferences alongside my notes.

### Panel Layout & Workspace

41. As a user, I want to start with an empty workspace and add panels one by one, so that my dashboard reflects what I actually use, not a pre-decided layout.
42. As a user, I want to open a command palette (`Ctrl+P`) to add new panels or search across all content, so that I can stay keyboard-driven.
43. As a user, I want to drag panels to rearrange, float, tab, or split them, so that the workspace adapts to my current focus.
44. As a user, I want my panel layout to be saved automatically when I close the app and restored when I reopen it, so that I don't reconfigure my workspace every session.
45. As a user, I want to close individual panels without losing their data, so that I can temporarily clear screen space.

### Local AI (Future-Ready)

46. As a user, I want to eventually query my notes using natural language (e.g., "what did I write about distributed systems?"), so that I can retrieve knowledge by meaning rather than exact keywords.
47. As a user, I want the AI to automatically suggest connections between newly captured content and my existing notes, so that my knowledge graph grows intelligently over time.
48. As a user, I want the AI to summarize long notes or captured content on demand, so that I can get the key points of something without reading everything.
49. As a user, I want to ask natural language questions about my finances (e.g., "how much did I spend on food last semester?"), so that my ledger is queryable like a conversation.
50. As a user, I want the AI integration to be swappable — so that I can plug in Ollama, llama.cpp, or Hugging Face Transformers without changing anything else in the app, so that I'm never locked into one runtime.

---

## Implementation Decisions

### 1. UI Framework
PyQt6 (or PySide6) is the GUI framework. Qt's `QDockWidget` system provides the dockable, floatable, tabbable panel architecture natively. This avoids building a custom panel manager from scratch while giving full QSS (Qt Style Sheets) control for theming.

### 2. Panel Architecture
The workspace uses `QDockWidget` panels registered in a `PanelRegistry`. Each panel type (Notes Browser, Note Editor, Graph, Finance, Email, Canvas, Capture) extends a `BasePanel`. The command palette (`Ctrl+P`) opens a panel selector. Layout state (which panels are open and where) is serialized to `~/.cbosa/layout.json` on close.

### 3. Data Layer — Two-tier storage
- **Notes**: Plain `.md` files on disk with YAML frontmatter. Human-readable, git-trackable. The file system is the source of truth.
- **Structured data** (finance transactions, email cache, search index, Canvas sync cache): SQLite (`cbosa.db`). SQLite's FTS5 extension powers full-text search across notes (content is indexed, not the source file).

### 4. Note Indexing
On startup and on file-change events (filesystem watcher), the system parses all `.md` files to build:
- A bidirectional wikilink index (`[[NoteTitle]]` → list of notes that reference it and are referenced by it)
- A tag index (`#tag` → list of notes)
- A full-text FTS5 index in SQLite

These indexes are in-memory during a session and can be rebuilt from scratch from the files at any time.

### 5. Markdown Rendering
The note editor uses a `QPlainTextEdit` for raw input and a `QWebEngineView` for the rendered preview. The Markdown-to-HTML conversion happens via `mistune` (fast, pure Python). The rendered HTML includes CSS derived from the active theme's colors/fonts.

### 6. Theming Engine
A `ThemeEngine` class reads a TOML file and generates a QSS string that is applied to the `QApplication`. The TOML schema has two top-level tables: `[colors]` (background, surface, primary, accent, text, text_muted, border) and `[fonts]` (family, size_base, size_small, size_heading). All QSS selectors are generated from these values — no hardcoded colors anywhere else in the codebase.

### 7. Graph View
The link graph is a `networkx.DiGraph` built from the wikilink index. Rendering uses `pyqtgraph`'s `GraphItem` for a force-directed layout. Node positions are computed with the Fruchterman-Reingold algorithm via networkx. Clicking a node emits a signal to open that note in the editor panel.

### 8. Finance Module
Transactions stored in SQLite with fields: `id` (INTEGER PRIMARY KEY), `date` (TEXT, ISO 8601 `YYYY-MM-DD`), `amount` (REAL, signed — negative for expenses), `description` (TEXT), `category` (TEXT). Categories are a user-managed list stored in a `categories` table. No external accounting library is used.

### 9. Email — IMAP Client
Uses Python's stdlib `imaplib` for IMAP connections. Credentials (host, port, username, password) are stored in `~/.cbosa/secrets.toml`, never in the main config or code. Email headers and bodies are cached in SQLite after first fetch. Task extraction uses regex heuristics on subject/body text (keywords: "please", "by [date]", "deadline", "action required") — an AI hook replaces this later.

### 10. Canvas LMS Client
Uses `httpx` for REST calls to the Canvas API. Authenticated with a personal access token stored in `~/.cbosa/secrets.toml`. Syncs: assignments (name, due_at, course_id, points_possible), grades (current_score, final_score), and course files list. All synced data is cached in SQLite with a `synced_at` timestamp.

### 11. Capture Engine
URL fetching: `httpx` fetches raw HTML; `BeautifulSoup` extracts article text. YouTube: `yt-dlp` extracts title, description, and transcript if available. PDF: `pypdf` extracts text page by page. All captured content is passed through `AIService.summarize()`. Until a real AI backend is connected, `NullAIService` returns an empty summary — the note is still created with the raw extracted content.

### 12. AI Service Interface
An abstract `AIService` class defines the contract: `summarize`, `embed`, `find_connections`, `extract_tasks`, `answer`. A `NullAIService` implements all methods as no-ops. All panels and modules call only `AIService` — never a specific runtime directly. Swapping in Ollama, llama.cpp, or Transformers requires only implementing this interface and updating one config entry.

### 13. Secrets Management
A `~/.cbosa/secrets.toml` file holds all credentials (IMAP creds, Canvas token). This file is never written by the app — the user edits it manually. It is excluded from any git tracking. A missing secrets file degrades gracefully: affected panels show a "configure credentials" prompt.

### 14. Background Workers
IMAP fetching and Canvas sync run in `QThread` workers to avoid blocking the UI. Workers emit Qt signals on completion; the main thread updates the SQLite cache and refreshes the relevant panel.

---

## Testing Decisions

**What makes a good test for CBOSA:** Tests assert on externally observable behavior — what data is stored, what is returned, what signals are emitted — not on internal implementation details like which method was called or how state is arranged internally. For UI components, test the data layer and signal contracts, not widget internals.

### Modules with tests (confirmed in scope):

| Module | Test focus |
|--------|-----------|
| `NoteStore` | CRUD on `.md` files; frontmatter round-trip; rename propagates to link index |
| `LinkIndex` | Parsing `[[wikilinks]]`; bidirectional correctness; handling renamed/missing notes |
| `TagIndex` | Parsing `#tags`; tag→notes mapping accuracy |
| `Ledger` | Transaction CRUD; category totals calculation correctness |
| `TaskExtractor` | Given email body text, returns expected extracted task strings |
| `CanvasApiClient` | Mocked HTTP responses → correct parsed assignment/grade objects |

### Modules explicitly NOT tested (deferred):

| Module | Reason |
|--------|--------|
| `ThemeEngine` | QSS output is visual; hard to assert meaningfully without rendering |
| `AIService / NullAIService` | Stub contracts are trivially correct; test when a real backend is added |
| `UrlFetcher` | Covered implicitly by capture integration tests later |

Tests use `pytest`. `NoteStore`, `LinkIndex`, `TagIndex`, and `Ledger` operate on temporary directories and in-memory SQLite — no mocking of Qt widgets. `CanvasApiClient` and `TaskExtractor` mock HTTP at the `httpx` transport layer and use fixture email/JSON bodies.

---

## Out of Scope

- **Sending email**: CBOSA is read-only for email in v1. Composing or replying is out of scope.
- **Real-time collaboration**: Single-user local tool. No sync or multi-user features.
- **Mobile / web interface**: PyQt6 desktop only. No responsive web version.
- **Cloud backup or sync**: Data lives entirely locally. Cloud sync is a user-managed file system concern.
- **CSV bank import for finance**: Manual entry only in v1.
- **Budget goals and alerts**: Finance module is ledger + categories only. Budget tracking is a future feature.
- **Canvas announcements**: Assignments, grades, and files are in scope. Announcements are not.
- **AI runtime implementation**: The `AIService` interface and `NullAIService` are in scope. Implementing Ollama/llama.cpp/Transformers backends is a future phase.
- **In-app theme editor**: Themes are configured via TOML files only. A visual theme editor is out of scope for v1.
- **Plugin system**: No third-party plugins. The panel registry is internal only.

---

## Further Notes

- **Daily note naming**: `YYYY-MM-DD.md` (e.g., `2026-05-10.md`) stored under `data/daily/`.
- **Secrets file location**: `~/.cbosa/secrets.toml` (user home directory, not project dir) so it is never accidentally committed.
- **Layout persistence**: `~/.cbosa/layout.json` stores panel layout via `QMainWindow.saveState()` / `restoreState()`.
- **Wikilink resolution**: Links use the note's filename without extension. Resolution is case-insensitive; exact match is preferred over fuzzy match.
- **Graph performance**: `pyqtgraph` handles the initial graph view. If performance degrades with 1000+ nodes, a WebGL-based renderer embedded in `QWebEngineView` is the migration path.
