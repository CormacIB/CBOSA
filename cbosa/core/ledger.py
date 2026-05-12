"""
Ledger — personal finance module.

Stores transactions and categories in a local SQLite database.
All dates use ISO-8601 string format: YYYY-MM-DD.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path


class LedgerError(Exception):
    """Base class for Ledger errors."""


class CategoryNotFoundError(LedgerError):
    pass


class TransactionNotFoundError(LedgerError):
    pass


class DuplicateCategoryError(LedgerError):
    pass


class Ledger:
    """
    Personal finance ledger backed by SQLite.

    Manages user-defined categories and manually-logged transactions
    (date, amount, description, category). Provides per-category
    spending summaries with optional date-range filtering.
    """

    def __init__(self, db_path: "str | Path") -> None:
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
            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                amount      REAL    NOT NULL,
                description TEXT    NOT NULL DEFAULT '',
                category    TEXT    NOT NULL DEFAULT ''
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def add_category(self, name: str) -> int:
        """Add a new category. Returns the new category id."""
        name = name.strip()
        if not name:
            raise LedgerError("Category name must not be empty.")
        try:
            cur = self._conn.execute(
                "INSERT INTO categories (name) VALUES (?)", (name,)
            )
            self._conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise DuplicateCategoryError(f"Category already exists: {name!r}")

    def delete_category(self, category_id: int) -> None:
        """Delete a category by id."""
        cur = self._conn.execute(
            "DELETE FROM categories WHERE id = ?", (category_id,)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise CategoryNotFoundError(f"No category with id {category_id}")

    def list_categories(self) -> list[dict]:
        """Return all categories as [{'id': int, 'name': str}, ...]."""
        rows = self._conn.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def add_transaction(
        self,
        date: str,
        amount: float,
        description: str,
        category: str,
    ) -> int:
        """
        Add a transaction. Returns the new transaction id.

        date        ISO-8601 string (YYYY-MM-DD)
        amount      positive (income) or negative (expense)
        description free-text label
        category    category name (free-text — not FK-constrained so
                    categories can be renamed without orphaning rows)
        """
        _validate_date(date)
        cur = self._conn.execute(
            "INSERT INTO transactions (date, amount, description, category) "
            "VALUES (?, ?, ?, ?)",
            (date, float(amount), description, category),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_transaction(self, tx_id: int) -> dict:
        """Return a single transaction dict or raise TransactionNotFoundError."""
        row = self._conn.execute(
            "SELECT id, date, amount, description, category "
            "FROM transactions WHERE id = ?",
            (tx_id,),
        ).fetchone()
        if row is None:
            raise TransactionNotFoundError(f"No transaction with id {tx_id}")
        return _tx_dict(row)

    def edit_transaction(
        self,
        tx_id: int,
        *,
        date: str,
        amount: float,
        description: str,
        category: str,
    ) -> None:
        """Replace all fields of an existing transaction."""
        _validate_date(date)
        cur = self._conn.execute(
            "UPDATE transactions "
            "SET date=?, amount=?, description=?, category=? "
            "WHERE id=?",
            (date, float(amount), description, category, tx_id),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise TransactionNotFoundError(f"No transaction with id {tx_id}")

    def delete_transaction(self, tx_id: int) -> None:
        """Delete a transaction by id."""
        cur = self._conn.execute(
            "DELETE FROM transactions WHERE id = ?", (tx_id,)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise TransactionNotFoundError(f"No transaction with id {tx_id}")

    def list_transactions(
        self,
        start_date: "str | None" = None,
        end_date: "str | None" = None,
        category: "str | None" = None,
    ) -> list[dict]:
        """
        Return transactions ordered by date DESC, id DESC.

        start_date  inclusive lower bound (YYYY-MM-DD)
        end_date    inclusive upper bound (YYYY-MM-DD)
        category    exact category name filter
        """
        sql = (
            "SELECT id, date, amount, description, category "
            "FROM transactions WHERE 1=1"
        )
        params: list = []
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY date DESC, id DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [_tx_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def category_totals(
        self,
        start_date: "str | None" = None,
        end_date: "str | None" = None,
    ) -> dict[str, float]:
        """
        Return {category_name: total_amount} for transactions in range.

        Positive amounts represent income; negative amounts are expenses.
        """
        sql = (
            "SELECT category, SUM(amount) AS total "
            "FROM transactions WHERE 1=1"
        )
        params: list = []
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " GROUP BY category ORDER BY category"
        rows = self._conn.execute(sql, params).fetchall()
        return {r["category"]: round(r["total"], 2) for r in rows}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_date(date: str) -> None:
    """Raise LedgerError if date is not a valid YYYY-MM-DD string."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise LedgerError(f"Invalid date format (expected YYYY-MM-DD): {date!r}")
    parts = date.split("-")
    month, day = int(parts[1]), int(parts[2])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise LedgerError(f"Date out of range: {date!r}")


def _tx_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "date": row["date"],
        "amount": row["amount"],
        "description": row["description"],
        "category": row["category"],
    }
