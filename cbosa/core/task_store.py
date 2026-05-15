"""
TaskStore — persistent SQLite-backed task list.

Each task has a text label, an optional source tag ("manual", "email",
"canvas"), a completion flag, and an optional priority integer.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoredTask:
    id: int
    text: str
    source: str          # "manual" | "email" | "canvas"
    completed: bool
    priority: int | None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    text      TEXT    NOT NULL,
    source    TEXT    NOT NULL DEFAULT 'manual',
    completed INTEGER NOT NULL DEFAULT 0,
    priority  INTEGER
);
"""


class TaskStore:
    """Persistent task list backed by a SQLite database."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_tasks(self, include_completed: bool = False) -> list[StoredTask]:
        """Return all tasks, newest first.  By default excludes completed."""
        if include_completed:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY completed ASC, id DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE completed = 0 ORDER BY id DESC"
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_task(self, text: str, source: str = "manual", priority: int | None = None) -> StoredTask:
        """Insert a new task and return it."""
        text = text.strip()
        if not text:
            raise ValueError("Task text must not be empty.")
        cur = self._conn.execute(
            "INSERT INTO tasks (text, source, priority) VALUES (?, ?, ?)",
            (text, source, priority),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return self._row_to_task(row)

    def complete_task(self, task_id: int) -> None:
        """Mark a task as completed."""
        self._conn.execute(
            "UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,)
        )
        self._conn.commit()

    def uncomplete_task(self, task_id: int) -> None:
        """Mark a completed task as open again."""
        self._conn.execute(
            "UPDATE tasks SET completed = 0 WHERE id = ?", (task_id,)
        )
        self._conn.commit()

    def delete_task(self, task_id: int) -> None:
        """Permanently delete a task."""
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def import_tasks(self, texts: list[str], source: str) -> int:
        """Bulk-import tasks from a source. Returns the count added."""
        added = 0
        for text in texts:
            text = text.strip()
            if not text:
                continue
            exists = self._conn.execute(
                "SELECT 1 FROM tasks WHERE text = ? AND source = ? AND completed = 0",
                (text, source),
            ).fetchone()
            if not exists:
                self._conn.execute(
                    "INSERT INTO tasks (text, source) VALUES (?, ?)", (text, source)
                )
                added += 1
        self._conn.commit()
        return added

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _row_to_task(self, row: sqlite3.Row) -> StoredTask:
        return StoredTask(
            id=row["id"],
            text=row["text"],
            source=row["source"],
            completed=bool(row["completed"]),
            priority=row["priority"],
        )
