"""
DailyNoteService — creates today's daily note on app launch.

Public interface:
    DailyNoteService(store: NoteStore)
    DailyNoteService.ensure_today(date: datetime.date | None = None) -> Note

The note is created at <store_root>/YYYY-MM-DD.md with minimal frontmatter
(title, date). If the note already exists it is left untouched.
"""
from __future__ import annotations

import datetime

from cbosa.core.note_store import Note, NoteStore


class DailyNoteService:
    def __init__(self, store: NoteStore) -> None:
        self._store = store

    def ensure_today(self, date: datetime.date | None = None) -> Note:
        """Create today's daily note if it doesn't exist. Returns the Note."""
        if date is None:
            date = datetime.date.today()
        name = date.isoformat()  # "YYYY-MM-DD"
        if name in self._store.all_names():
            return self._store.read(name)
        return self._store.create(
            name,
            "",
            frontmatter={"title": name, "date": name},
        )
