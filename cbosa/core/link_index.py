"""
LinkIndex — bidirectional wikilink map across all notes.

Public interface:
    LinkIndex(store: NoteStore)
    LinkIndex.rebuild() -> None
    LinkIndex.links_from(name) -> list[str]
    LinkIndex.links_to(name) -> list[str]
"""
from __future__ import annotations

import re
from collections import defaultdict

from cbosa.core.note_store import NoteStore

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class LinkIndex:
    def __init__(self, store: NoteStore) -> None:
        self._store = store
        self._forward: dict[str, list[str]] = defaultdict(list)
        self._backward: dict[str, list[str]] = defaultdict(list)

    def rebuild(self) -> None:
        self._forward = defaultdict(list)
        self._backward = defaultdict(list)
        for name in self._store.all_names():
            note = self._store.read(name)
            for target in _WIKILINK_RE.findall(note.content):
                self._forward[name].append(target)
                self._backward[target].append(name)

    def links_from(self, name: str) -> list[str]:
        return list(self._forward.get(name, []))

    def links_to(self, name: str) -> list[str]:
        return list(self._backward.get(name, []))
