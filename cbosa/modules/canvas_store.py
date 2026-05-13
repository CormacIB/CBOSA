"""
CanvasStore — SQLite-backed cache for Canvas LMS data.

Credentials are read from ~/.cbosa/secrets.toml under [canvas]:
    base_url = "https://your-institution.instructure.com"
    token    = "your-personal-access-token"

All Canvas network I/O runs in a QThread worker (CanvasSyncWorker).
CanvasStore itself is thread-safe for reads; writes from the worker
are protected by SQLite WAL journal mode.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

try:
    import httpx as _httpx
except ImportError:
    _httpx = None  # type: ignore[assignment]

try:
    import toml
except ImportError:
    toml = None  # type: ignore[assignment]

from PyQt6.QtCore import QThread, pyqtSignal

_SECRETS_PATH = Path.home() / ".cbosa" / "secrets.toml"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CanvasStoreError(Exception):
    """Base error for Canvas integration."""


class CredentialsMissingError(CanvasStoreError):
    """Raised when ~/.cbosa/secrets.toml is missing or has no [canvas] section."""


class CanvasApiError(CanvasStoreError):
    """Raised when the Canvas API returns a non-2xx response."""


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class CanvasApiClient:
    """
    Thin wrapper around the Canvas REST API.

    Can be constructed with an explicit httpx.Client (for testing)
    or built from credentials via from_credentials().

    Usage (production):
        creds = {"base_url": "https://...", "token": "..."}
        client = CanvasApiClient.from_credentials(creds)

    Usage (tests):
        http = httpx.Client(transport=MockTransport(...))
        client = CanvasApiClient(http_client=http)
    """

    def __init__(self, http_client) -> None:
        self._http = http_client

    @classmethod
    def from_credentials(cls, creds: dict) -> "CanvasApiClient":
        if _httpx is None:
            raise CanvasStoreError("httpx is required for Canvas sync")
        base_url = creds["base_url"].rstrip("/")
        token = creds["token"]
        http = _httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        return cls(http_client=http)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def list_courses(self) -> list[dict]:
        """Return list of active enrolled courses. Each dict has id and name."""
        data = self._get("/api/v1/courses", params={"enrollment_state": "active", "per_page": 100})
        return [{"id": c["id"], "name": c.get("name", "")} for c in data]

    def list_assignments(self, course_id: int) -> list[dict]:
        """Return assignments for a course. Each dict has id, name, due_at, points_possible."""
        data = self._get(
            f"/api/v1/courses/{course_id}/assignments",
            params={"per_page": 100, "order_by": "due_at"},
        )
        result = []
        for a in data:
            result.append({
                "id": a["id"],
                "name": a.get("name", ""),
                "due_at": a.get("due_at") or "",
                "points_possible": a.get("points_possible") or 0.0,
            })
        return result

    def list_submissions(self, course_id: int) -> list[dict]:
        """Return student submissions for a course. Each dict has assignment_id, score, grade."""
        data = self._get(
            f"/api/v1/courses/{course_id}/students/submissions",
            params={"per_page": 100, "student_ids[]": "self"},
        )
        result = []
        for s in data:
            result.append({
                "assignment_id": s.get("assignment_id"),
                "score": s.get("score"),  # may be None if not graded
                "grade": s.get("grade") or "",
            })
        return result

    def list_files(self, course_id: int) -> list[dict]:
        """Return course files. Each dict has id, name, url, size."""
        data = self._get(
            f"/api/v1/courses/{course_id}/files",
            params={"per_page": 100},
        )
        result = []
        for f in data:
            result.append({
                "id": f["id"],
                "name": f.get("display_name") or f.get("filename", ""),
                "url": f.get("url", ""),
                "size": f.get("size", 0),
            })
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> list:
        response = self._http.get(path, params=params or {})
        if response.status_code >= 400:
            raise CanvasApiError(
                f"{response.status_code} error from Canvas API: {path}"
            )
        return response.json()


# ---------------------------------------------------------------------------
# CanvasStore — SQLite cache
# ---------------------------------------------------------------------------

class CanvasStore:
    """
    Local SQLite cache for Canvas LMS data.

    Usage:
        store = CanvasStore(":memory:")              # for tests
        store = CanvasStore(Path("data/canvas.db"))  # for production

    Check store.has_credentials before syncing.
    Call store.sync(on_done) to fetch data in a background thread.
    """

    def __init__(self, db_path: "str | Path") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._worker: CanvasSyncWorker | None = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS assignments (
                id              INTEGER PRIMARY KEY,
                course_id       INTEGER NOT NULL,
                course_name     TEXT    NOT NULL DEFAULT '',
                name            TEXT    NOT NULL DEFAULT '',
                due_at          TEXT    NOT NULL DEFAULT '',
                points_possible REAL    NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id       INTEGER NOT NULL,
                course_name     TEXT    NOT NULL DEFAULT '',
                assignment_id   INTEGER NOT NULL,
                assignment_name TEXT    NOT NULL DEFAULT '',
                score           REAL,
                grade           TEXT    NOT NULL DEFAULT '',
                UNIQUE(course_id, assignment_id)
            );
            CREATE TABLE IF NOT EXISTS files (
                id          INTEGER PRIMARY KEY,
                course_id   INTEGER NOT NULL,
                course_name TEXT    NOT NULL DEFAULT '',
                name        TEXT    NOT NULL DEFAULT '',
                url         TEXT    NOT NULL DEFAULT '',
                size        INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    @property
    def has_credentials(self) -> bool:
        """Return True if ~/.cbosa/secrets.toml exists and has a valid [canvas] section."""
        try:
            creds = self._load_credentials()
            return bool(creds.get("base_url") and creds.get("token"))
        except CredentialsMissingError:
            return False

    def _load_credentials(self) -> dict:
        if toml is None:
            raise CredentialsMissingError("toml package not available")
        if not _SECRETS_PATH.exists():
            raise CredentialsMissingError(
                f"secrets.toml not found at {_SECRETS_PATH}"
            )
        try:
            data = toml.load(str(_SECRETS_PATH))
        except Exception as exc:
            raise CredentialsMissingError(f"Could not parse secrets.toml: {exc}") from exc
        if "canvas" not in data:
            raise CredentialsMissingError("secrets.toml has no [canvas] section")
        return data["canvas"]

    # ------------------------------------------------------------------
    # Read queries
    # ------------------------------------------------------------------

    def list_assignments(self) -> list[dict]:
        """Return all cached assignments sorted by due_at (undated last)."""
        rows = self._conn.execute(
            """SELECT id, course_id, course_name, name, due_at, points_possible
               FROM assignments
               ORDER BY CASE WHEN due_at = '' THEN 1 ELSE 0 END, due_at"""
        ).fetchall()
        return [dict(r) for r in rows]

    def list_submissions(self) -> list[dict]:
        """Return all cached submissions (grade data)."""
        rows = self._conn.execute(
            """SELECT id, course_id, course_name, assignment_id, assignment_name,
                      score, grade
               FROM submissions
               ORDER BY course_name, assignment_name"""
        ).fetchall()
        return [dict(r) for r in rows]

    def list_files(self) -> list[dict]:
        """Return all cached course files."""
        rows = self._conn.execute(
            """SELECT id, course_id, course_name, name, url, size
               FROM files
               ORDER BY course_name, name"""
        ).fetchall()
        return [dict(r) for r in rows]

    def synced_at(self) -> str:
        """Return the ISO timestamp of the last successful sync, or ''."""
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'synced_at'"
        ).fetchone()
        return row["value"] if row else ""

    def count_assignments(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]

    def count_files(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    # ------------------------------------------------------------------
    # Write operations (called by CanvasSyncWorker)
    # ------------------------------------------------------------------

    def _upsert_assignment(
        self,
        id: int,
        course_id: int,
        course_name: str,
        name: str,
        due_at: str,
        points_possible: float,
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO assignments
               (id, course_id, course_name, name, due_at, points_possible)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id, course_id, course_name, name, due_at, points_possible),
        )

    def _upsert_submission(
        self,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        score,
        grade: str,
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO submissions
               (course_id, course_name, assignment_id, assignment_name, score, grade)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (course_id, course_name, assignment_id, assignment_name, score, grade),
        )

    def _upsert_file(
        self,
        id: int,
        course_id: int,
        course_name: str,
        name: str,
        url: str,
        size: int,
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO files
               (id, course_id, course_name, name, url, size)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id, course_id, course_name, name, url, size),
        )

    def _set_synced_at(self, timestamp: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('synced_at', ?)",
            (timestamp,),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Delete all cached Canvas data."""
        self._conn.executescript(
            "DELETE FROM assignments; DELETE FROM submissions; DELETE FROM files;"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Background sync
    # ------------------------------------------------------------------

    def sync(self, on_done: "Callable[[int, str], None]") -> None:
        """
        Fetch Canvas data from the API in a background QThread.

        on_done(count, error_message) is called when done.
        count is the total number of items synced; error_message is '' on success.
        """
        try:
            creds = self._load_credentials()
        except CredentialsMissingError as exc:
            on_done(0, str(exc))
            return

        self._worker = CanvasSyncWorker(self, creds)
        self._worker.finished.connect(on_done)
        self._worker.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Background sync worker
# ---------------------------------------------------------------------------

class CanvasSyncWorker(QThread):
    """Fetches Canvas data in a background thread."""

    finished = pyqtSignal(int, str)

    def __init__(self, store: CanvasStore, creds: dict, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._creds = creds

    def run(self) -> None:
        try:
            count = _do_sync(self._store, self._creds)
            self.finished.emit(count, "")
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(0, str(exc))


def _do_sync(store: CanvasStore, creds: dict) -> int:
    """Fetch all Canvas data and populate the store. Returns total item count."""
    from datetime import datetime, timezone

    client = CanvasApiClient.from_credentials(creds)
    courses = client.list_courses()
    total = 0

    for course in courses:
        cid = course["id"]
        cname = course["name"]

        # Assignments + submissions
        try:
            assignments = client.list_assignments(cid)
            for a in assignments:
                store._upsert_assignment(
                    id=a["id"],
                    course_id=cid,
                    course_name=cname,
                    name=a["name"],
                    due_at=a["due_at"],
                    points_possible=a["points_possible"],
                )
                total += 1

            try:
                subs = client.list_submissions(cid)
                aname_map = {a["id"]: a["name"] for a in assignments}
                for s in subs:
                    aid = s["assignment_id"]
                    store._upsert_submission(
                        course_id=cid,
                        course_name=cname,
                        assignment_id=aid,
                        assignment_name=aname_map.get(aid, ""),
                        score=s["score"],
                        grade=s["grade"],
                    )
                    total += 1
            except CanvasApiError:
                pass  # submissions may not be accessible; non-fatal

        except CanvasApiError:
            pass  # individual course errors are non-fatal

        # Files
        try:
            files = client.list_files(cid)
            for f in files:
                store._upsert_file(
                    id=f["id"],
                    course_id=cid,
                    course_name=cname,
                    name=f["name"],
                    url=f["url"],
                    size=f["size"],
                )
                total += 1
        except CanvasApiError:
            pass  # file access may be restricted; non-fatal

    store._conn.commit()
    store._set_synced_at(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return total
