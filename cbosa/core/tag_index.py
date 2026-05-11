"""
TagIndex — maps #tags to the notes that contain them.

Public interface:
    TagIndex(store: NoteStore)
    TagIndex.rebuild() -> None
    TagIndex.notes_for_tag(tag) -> list[str]
"""
from __future__ import annotations

import re
from collections import defaultdict

from cbosa.core.note_store import NoteStore

_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]*)")


class TagIndex:
    def __init__(self, store: NoteStore) -> None:
        self._store = store
        self._map: dict[str, list[str]] = defaultdict(list)

    def rebuild(self) -> None:
        self._map = defaultdict(list)
        for name in self._store.all_names():
            note = self._store.read(name)
            for tag in _TAG_RE.findall(note.content):
                self._map[tag].append(name)

    def notes_for_tag(self, tag: str) -> list[str]:
        return list(self._map.get(tag, []))

    def all_tags(self) -> list[str]:
        return list(self._map.keys())
