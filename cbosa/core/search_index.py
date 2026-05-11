"""
SearchIndex — full-text search over note content via SQLite FTS5.

Public interface:
    SearchIndex(store: NoteStore, db_path=":memory:")
    SearchIndex.rebuild() -> None
    SearchIndex.search(query) -> list[str]   # note names matching query
"""
from __future__ import annotations

import sqlite3

from cbosa.core.note_store import NoteStore


class SearchIndex:
    def __init__(self, store: NoteStore, db_path: str = ":memory:") -> None:
        self._store = store
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts "
            "USING fts5(name UNINDEXED, content)"
        )
        self._conn.commit()

    def rebuild(self) -> None:
        self._conn.execute("DELETE FROM notes_fts")
        rows = [
            (name, self._store.read(name).content)
            for name in self._store.all_names()
        ]
        self._conn.executemany("INSERT INTO notes_fts(name, content) VALUES (?, ?)", rows)
        self._conn.commit()

    def search(self, query: str) -> list[str]:
        cur = self._conn.execute(
            "SELECT name FROM notes_fts WHERE notes_fts MATCH ? ORDER BY rank",
            (query,),
        )
        return [row[0] for row in cur.fetchall()]
