# CBOSA — Known Issues

Issues discovered during development that are not yet resolved. Each entry notes the affected area, the consequence, and the planned fix.

---

## KI-1: No filesystem watcher on note indexes

**Area:** Issue #3 — Note Engine (`LinkIndex`, `TagIndex`, `SearchIndex`)
**Status:** Open

`LinkIndex`, `TagIndex`, and `SearchIndex` all expose a `rebuild()` method but nothing watches the filesystem for changes. If a `.md` file is edited outside the app (another editor, sync tool), the indexes are stale until the next restart.

In-app edits via the Note Editor (Issue #4) will call `rebuild()` explicitly after each save, so this only affects external edits.

**Planned fix:** Wire a `QFileSystemWatcher` into `NoteStore` to trigger index rebuilds on file-change events. Target: follow-up to Issue #4.

---

## KI-2: Command palette requires double-click or Enter — no visible confirm button

**Area:** Issue #2 — `cbosa/ui/command_palette.py`
**Status:** Open / low priority

Single-clicking a panel type in the palette does nothing visible. Users must double-click or press Enter to open a panel. The affordance is not obvious.

**Planned fix:** Add an "Add Panel" button to the dialog, or add a hint label. Target: Issue #4 or a small polish pass.

---

## KI-3: Registered panel types are placeholder `BasePanel` instances until Issue #4

**Area:** Issue #2 — `cbosa/app.py` `_register_panels()`
**Status:** Expected / by design

Ctrl+P lists Notes, Finance, Email, and Canvas, but all open an empty `BasePanel` dock with no content. Real implementations arrive in Issue #4 (Notes) and subsequent issues.

**Planned fix:** Replace each `BasePanel` entry in `_register_panels()` with the concrete class as each issue is completed.

---

## KI-4: Theme and config paths are relative to the working directory -- YIIIKEEES

**Area:** Issue #1 — `cbosa/config.py`, `cbosa/app.py`
**Status:** Fixed

`config.py` now defines `PROJECT_ROOT = Path(__file__).parent.parent` and defaults the config file lookup to `PROJECT_ROOT / "cbosa.toml"`. A new `config.resolve()` helper returns any config path as an absolute `Path` anchored to `PROJECT_ROOT`. `app.py` uses `config.resolve()` for both `theme` and `data_dir`.
