# CBOSA — Honest Audit
*Produced via grilling session, 2026-06-26*

---

## What CBOSA Actually Is (vs. What It Was Supposed To Be)

**Intended:** A unified personal OS — notes, finance, email, Canvas LMS, AI, all talking to each other in one local-first dashboard.

**Actual:** A fast local scratchpad for work thinking, with an offline AI chat panel that's occasionally useful on planes.

That gap is the document.

---

## Failure Analysis

### 1. Finance Panel — Dead on Arrival
**Why it failed:** The data already existed elsewhere (bank and credit card statements) with zero extra effort. CBOSA required manual re-entry of every transaction to produce a graph that the bank's app already provides. The value proposition was negative: more work for an inferior output.

**Root cause:** Built around the *idea* of owning your financial data, not around a real friction point in how you access it. Manual ledger entry is a habit that has to be cultivated — it wasn't.

**Status:** Unused. The panel code exists; the ledger is empty.

---

### 2. Canvas & Email Panels — Never Configured
**Why they failed:** Credentials were never set up. The existing tools (Canvas web app, Gmail) are instantaneous and feature-complete. CBOSA's versions would have required setup work to access a degraded version of the same information.

**Root cause:** Same pattern as finance — CBOSA tried to mirror data that lives comfortably elsewhere. Aggregation only adds value when the aggregation itself saves time or reveals connections that don't exist in the source tools. Neither was true here.

**Status:** Code exists, credentials never configured, panels are decorative.

---

### 3. Graph View — Technically Working, Behaviorally Unused
**Why it failed:** The graph assumes a deliberate wikilink practice. Making a backlink is a conscious extra step that competes with the actual goal (getting a thought written down). Without that practice, the graph is a visualization of ~12 loosely connected nodes. It's aesthetically interesting; it's not a navigation tool.

**Root cause:** Designed for a Zettelkasten-style knowledge management workflow that doesn't match how you actually write notes (fast, casual, topic-focused bullet lists).

**Status:** Works correctly. Not useful.

---

### 4. Folder Structure — Manual Friction
**Why it failed:** Folder organization requires a decision every time a new note is created. When the goal is "throw an idea down fast," any required decision is friction. Most notes end up in a flat structure by default because filing them correctly takes more effort than the note is worth in the moment.

**Root cause:** Hierarchical organization suits archival; it fights quick capture.

**Status:** Partially used. Adds maintenance burden.

---

### 5. Search — Unused Despite Being Implemented
**Why it's unused:** Not entirely clear — possibly because the note collection is small enough to navigate visually, possibly because FTS5 search isn't prominent enough in the UI, possibly because the folder structure (however loose) still orients navigation. Likely all three.

**Status:** Implemented and functional. Not part of daily flow.

---

### 6. Form Factor — Wrong for the Core Need
**The tension:** You want CBOSA to be *instantly accessible* (hit a key from anywhere and write) AND a *persistent workspace* (leave it running, glance at it). Currently it's neither — it's just a window you alt-tab into like any other application. There's no global capture shortcut, no menu bar presence, no way to capture a thought from outside the app.

**Root cause:** Designed as a feature-complete desktop application, not as an always-available tool. The two modes (quick capture + persistent workspace) were never separated in the UX.

---

### 7. AI Chat — Actually Working, Narrow Use Case
**What it does:** Offline LLM reference (Ollama running locally) for looking up technical topics when internet access is limited. Used on planes, in low-connectivity situations.

**What it doesn't do:** Reason over your notes, surface connections, answer questions about your personal context. It's a local ChatGPT tab, not a personal AI.

**Status:** Legitimate use case. Appropriately scoped. Don't cut it.

---

## What's Actually Working

- **Note editor:** The core reason the app is open. Local ownership, no cloud clutter, always running.
- **Daily notes:** Auto-created on startup — passive habit that works because it requires nothing from you.
- **Offline AI chat:** Real value in specific situations (travel, low wifi).
- **Theming:** You care about the aesthetic, you've invested in it, it's working.
- **The Pomodoro timer:** Actively used (evidenced by multiple recent aesthetic commits).

---

## Improvement Points (without redesign)

These are changes that could be made to the current PyQt6 codebase:

1. **Global capture hotkey:** Register a system-wide shortcut (e.g. `Cmd+Shift+N`) that instantly opens a minimal capture window — a single text field that creates a note and dismisses. No folder selection, no frontmatter, just the text. File it under `data/captures/` with a timestamp as filename.

2. **Menu bar / system tray presence:** Give CBOSA a tray icon so it's always one click away even when buried behind other windows. The icon could show the Pomodoro timer state.

3. **Remove the folder requirement from new notes:** Default all new notes to a flat inbox (`data/inbox/`). Let organization happen lazily or not at all.

4. **Surface search more aggressively:** Put a persistent search bar at the top of the note browser, not buried. The FTS5 implementation is good — it just needs to be findable.

5. **Deprecate or hide dead panels:** Finance, Canvas, Email panels add visual clutter and cognitive weight to the command palette. Either remove them or move them behind a "configure first" gate that keeps the palette clean.

6. **Wikilinks on opt-in, not default:** Don't deprecate them — but don't design the UX around them. They're there if you want them; the app shouldn't push the workflow.

---

## Redesign Decision — Electron Rewrite

**Decision (2026-06-26): Rewrite the frontend in Electron + React. Keep the Python backend.**

The PyQt6 frontend will be replaced. The Python backend (note engine, search, AI service, ledger) becomes a local API server running on localhost. An Electron shell wraps a React frontend that talks to it. Data stays entirely local — no domain, no hosting, no cloud.

**What this buys:**
- Real editor (CodeMirror or ProseMirror) instead of `QPlainTextEdit` — the "locked into writing the same way" feeling goes away
- CSS instead of QSS — full theming flexibility, no workarounds
- Global hotkeys and tray icon are straightforward in Electron
- React/JSX aligns with the prospective designs already sketched in `Prospective designs/`

**What stays in Python:**
- `NoteStore`, `LinkIndex`, `TagIndex`, `SearchIndex` — the entire note engine
- `Ledger` and `TaskStore`
- `AIService` / `OllamaAIService` — the Ollama integration
- All file I/O and SQLite access

**What gets replaced:**
- Everything under `cbosa/ui/` — all PyQt6 panels, theme engine, main window
- `app.py` bootstrap becomes a Flask/FastAPI server entry point

**Scope note:** This is a frontend rewrite, not a ground-up rebuild. The data layer is solid and stays untouched.

---

## Core Design Principle (for any redesign)

**CBOSA should be the fastest possible place to write something down that you own.**

Everything else is secondary. The graph is secondary. The finance ledger is secondary. Canvas sync is secondary. The AI is a bonus. If a feature makes the core act of writing slower or requires a decision before you can start typing, it's working against the app.

The personal ownership angle is real and worth preserving. That's not a feature — it's the point.

---

## Summary Table

| Feature | Status | Verdict |
|---------|--------|---------|
| Note editor | Used daily | Keep, improve capture speed |
| Daily notes | Passive, working | Keep |
| Pomodoro timer | Actively used | Keep |
| Offline AI chat | Occasionally useful | Keep, narrow scope |
| Graph view | Technically works, behaviorally unused | Deprioritize |
| Search | Implemented, not in flow | Improve discoverability |
| Finance panel | Unused | Remove or archive |
| Canvas panel | Never configured | Remove or archive |
| Email panel | Never configured | Remove or archive |
| Folder structure | Friction | Flatten to inbox model |
| Global capture hotkey | Missing | High priority addition |
| Tray/menu bar presence | Missing | High priority addition |
