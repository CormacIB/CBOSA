"""
TaskStore — persistent SQLite-backed task list with categories.

Each task has a text label, an optional source tag ("manual", "email",
"canvas"), a completion flag, an optional priority integer, and an optional
category_id foreign-key to the categories table.
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
    category_id: int | None


@dataclass
class Category:
    id: int
    name: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'manual',
    completed   INTEGER NOT NULL DEFAULT 0,
    priority    INTEGER,
    category_id INTEGER REFERENCES categories(id)
);
"""

_MIGRATE_CATEGORY_COL = """
ALTER TABLE tasks ADD COLUMN category_id INTEGER REFERENCES categories(id);
"""


class CategoryNotEmptyError(Exception):
    """Raised when deleting a category that still has tasks."""


class TaskStore:
    """Persistent task list backed by a SQLite database."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._maybe_migrate()

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def _maybe_migrate(self) -> None:
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(tasks)")}
        if "category_id" not in cols:
            self._conn.execute(_MIGRATE_CATEGORY_COL)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Category CRUD
    # ------------------------------------------------------------------

    def list_categories(self) -> list[Category]:
        rows = self._conn.execute(
            "SELECT * FROM categories ORDER BY name"
        ).fetchall()
        return [Category(id=r["id"], name=r["name"]) for r in rows]

    def add_category(self, name: str) -> Category:
        name = name.strip()
        if not name:
            raise ValueError("Category name must not be empty.")
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM categories WHERE name = ?", (name,)
        ).fetchone()
        return Category(id=row["id"], name=row["name"])

    def rename_category(self, category_id: int, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Category name must not be empty.")
        self._conn.execute(
            "UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id)
        )
        self._conn.commit()

    def delete_category(self, category_id: int) -> None:
        """Delete a category. Raises CategoryNotEmptyError if tasks exist in it."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE category_id = ? AND completed = 0",
            (category_id,),
        ).fetchone()[0]
        if count > 0:
            raise CategoryNotEmptyError(
                f"Category still has {count} open task(s). Move or complete them first."
            )
        self._conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Task queries
    # ------------------------------------------------------------------

    def list_tasks(self, include_completed: bool = False) -> list[StoredTask]:
        if include_completed:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY completed ASC, id DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE completed = 0 ORDER BY id DESC"
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def list_tasks_by_category(
        self, include_completed: bool = False
    ) -> dict[str, list[StoredTask]]:
        """Return {category_name: [tasks]}.

        Uncategorized tasks appear under the key '' (empty string).
        """
        tasks = self.list_tasks(include_completed)
        cats = {c.id: c.name for c in self.list_categories()}
        result: dict[str, list[StoredTask]] = {}
        for task in tasks:
            key = cats.get(task.category_id, "") if task.category_id is not None else ""
            result.setdefault(key, []).append(task)
        return result

    # ------------------------------------------------------------------
    # Task mutations
    # ------------------------------------------------------------------

    def add_task(
        self,
        text: str,
        source: str = "manual",
        priority: int | None = None,
        category_id: int | None = None,
    ) -> StoredTask:
        text = text.strip()
        if not text:
            raise ValueError("Task text must not be empty.")
        cur = self._conn.execute(
            "INSERT INTO tasks (text, source, priority, category_id) VALUES (?, ?, ?, ?)",
            (text, source, priority, category_id),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return self._row_to_task(row)

    def complete_task(self, task_id: int) -> None:
        self._conn.execute(
            "UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,)
        )
        self._conn.commit()

    def uncomplete_task(self, task_id: int) -> None:
        self._conn.execute(
            "UPDATE tasks SET completed = 0 WHERE id = ?", (task_id,)
        )
        self._conn.commit()

    def delete_task(self, task_id: int) -> None:
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def import_tasks(self, texts: list[str], source: str) -> int:
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
            category_id=row["category_id"],
        )
