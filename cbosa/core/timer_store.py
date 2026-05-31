"""
TimerStore — time-tracking module.

Stores groups, categories, and timed sessions in a local SQLite database.
All datetimes use ISO-8601 string format: YYYY-MM-DDTHH:MM:SS.
Session duration is always derived from end_time - start_time; no planned
duration is stored.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class TimerStoreError(Exception):
    """Base class for TimerStore errors."""


class GroupNotFoundError(TimerStoreError):
    pass


class CategoryNotFoundError(TimerStoreError):
    pass


class DuplicateGroupError(TimerStoreError):
    pass


class TimerStore:
    """
    Time-tracking store backed by SQLite.

    Manages user-defined groups, their child categories, and timed work
    sessions (start_time, end_time, category). Provides per-category
    duration summaries with optional date-range filtering.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS categories (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                name     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                start_time  TEXT    NOT NULL,
                end_time    TEXT    NOT NULL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def add_group(self, name: str) -> int:
        """Add a new group. Returns the new group id."""
        name = name.strip()
        if not name:
            raise TimerStoreError("Group name must not be empty.")
        try:
            cur = self._conn.execute(
                "INSERT INTO groups (name) VALUES (?)", (name,)
            )
            self._conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise DuplicateGroupError(f"Group already exists: {name!r}")

    def list_groups(self) -> list[dict]:
        """Return all groups as [{'id': int, 'name': str}, ...]."""
        rows = self._conn.execute(
            "SELECT id, name FROM groups ORDER BY name"
        ).fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    def delete_group(self, group_id: int) -> None:
        """Delete a group and all its categories/sessions (cascade)."""
        cur = self._conn.execute(
            "DELETE FROM groups WHERE id = ?", (group_id,)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise GroupNotFoundError(f"No group with id {group_id}")

    def rename_group(self, group_id: int, name: str) -> None:
        """Rename an existing group."""
        name = name.strip()
        if not name:
            raise TimerStoreError("Group name must not be empty.")
        cur = self._conn.execute(
            "UPDATE groups SET name = ? WHERE id = ?", (name, group_id)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise GroupNotFoundError(f"No group with id {group_id}")

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def add_category(self, group_id: int, name: str) -> int:
        """Add a category under a group. Returns the new category id."""
        name = name.strip()
        if not name:
            raise TimerStoreError("Category name must not be empty.")
        row = self._conn.execute(
            "SELECT id FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
        if row is None:
            raise GroupNotFoundError(f"No group with id {group_id}")
        cur = self._conn.execute(
            "INSERT INTO categories (group_id, name) VALUES (?, ?)",
            (group_id, name),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_categories(self, group_id: int) -> list[dict]:
        """Return all categories for a group as [{'id', 'group_id', 'name'}, ...]."""
        rows = self._conn.execute(
            "SELECT id, group_id, name FROM categories WHERE group_id = ? ORDER BY name",
            (group_id,),
        ).fetchall()
        return [{"id": r["id"], "group_id": r["group_id"], "name": r["name"]} for r in rows]

    def delete_category(self, category_id: int) -> None:
        """Delete a category and its sessions (cascade)."""
        cur = self._conn.execute(
            "DELETE FROM categories WHERE id = ?", (category_id,)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise CategoryNotFoundError(f"No category with id {category_id}")

    def rename_category(self, category_id: int, name: str) -> None:
        """Rename an existing category."""
        name = name.strip()
        if not name:
            raise TimerStoreError("Category name must not be empty.")
        cur = self._conn.execute(
            "UPDATE categories SET name = ? WHERE id = ?", (name, category_id)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise CategoryNotFoundError(f"No category with id {category_id}")

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def log_session(self, category_id: int, start_time: str, end_time: str) -> int:
        """
        Log a completed work session. Returns the new session id.

        start_time / end_time  ISO-8601 datetime strings (YYYY-MM-DDTHH:MM:SS)
        Duration is always derived as end_time - start_time.
        """
        _validate_datetime(start_time)
        _validate_datetime(end_time)
        if end_time <= start_time:
            raise TimerStoreError("end_time must be after start_time")
        row = self._conn.execute(
            "SELECT id FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise CategoryNotFoundError(f"No category with id {category_id}")
        cur = self._conn.execute(
            "INSERT INTO sessions (category_id, start_time, end_time) VALUES (?, ?, ?)",
            (category_id, start_time, end_time),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_sessions(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Return sessions ordered by start_time DESC, enriched with group/category names.

        start_date  inclusive lower bound (YYYY-MM-DD)
        end_date    inclusive upper bound (YYYY-MM-DD)
        """
        sql = """
            SELECT s.id, s.start_time, s.end_time,
                   c.id AS category_id, c.name AS category_name,
                   g.id AS group_id,   g.name AS group_name
            FROM sessions s
            JOIN categories c ON c.id = s.category_id
            JOIN groups     g ON g.id = c.group_id
            WHERE 1=1
        """
        params: list = []
        if start_date:
            sql += " AND date(s.start_time) >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date(s.start_time) <= ?"
            params.append(end_date)
        sql += " ORDER BY s.start_time DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [_session_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def category_totals(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Return per-category total seconds, enriched with group info, ordered
        by total_seconds DESC.

        Returns [{'group_id', 'group_name', 'category_id', 'category_name',
                  'total_seconds'}, ...]
        """
        sql = """
            SELECT g.id AS group_id, g.name AS group_name,
                   c.id AS category_id, c.name AS category_name,
                   SUM(
                       CAST(ROUND((julianday(s.end_time) - julianday(s.start_time)) * 86400) AS INTEGER)
                   ) AS total_seconds
            FROM sessions s
            JOIN categories c ON c.id = s.category_id
            JOIN groups     g ON g.id = c.group_id
            WHERE 1=1
        """
        params: list = []
        if start_date:
            sql += " AND date(s.start_time) >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date(s.start_time) <= ?"
            params.append(end_date)
        sql += " GROUP BY c.id ORDER BY total_seconds DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "group_id": r["group_id"],
                "group_name": r["group_name"],
                "category_id": r["category_id"],
                "category_name": r["category_name"],
                "total_seconds": r["total_seconds"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_datetime(dt: str) -> None:
    try:
        datetime.fromisoformat(dt)
    except ValueError:
        raise TimerStoreError(f"Invalid datetime format (expected YYYY-MM-DDTHH:MM:SS): {dt!r}")


def _session_dict(row: sqlite3.Row) -> dict:
    start = row["start_time"]
    end = row["end_time"]
    duration = int(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    )
    return {
        "id": row["id"],
        "start_time": start,
        "end_time": end,
        "duration_seconds": duration,
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "group_id": row["group_id"],
        "group_name": row["group_name"],
    }
