"""
NoteStore — reads and writes .md files with YAML frontmatter.

Public interface:
    NoteStore(root: Path)
    NoteStore.create(name, content, frontmatter=None) -> Note
    NoteStore.read(name) -> Note
    NoteStore.update(name, content, frontmatter=None)
    NoteStore.delete(name)

    Note — dataclass with fields: name, content, frontmatter (dict)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Note:
    name: str
    content: str
    frontmatter: dict[str, Any] = field(default_factory=dict)


class NoteNotFoundError(FileNotFoundError):
    """Raised when a requested note does not exist."""


class NoteStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, name: str, content: str, frontmatter: dict | None = None) -> Note:
        path = self._path(name)
        fm = frontmatter or {}
        path.write_text(self._serialize(content, fm), encoding="utf-8")
        return Note(name=name, content=content, frontmatter=fm)

    def read(self, name: str) -> Note:
        path = self._path(name)
        if not path.exists():
            raise NoteNotFoundError(f"Note not found: {name}")
        raw = path.read_text(encoding="utf-8")
        content, fm = self._parse(raw)
        return Note(name=name, content=content, frontmatter=fm)

    def update(self, name: str, content: str, frontmatter: dict | None = None) -> None:
        path = self._path(name)
        if not path.exists():
            raise NoteNotFoundError(f"Note not found: {name}")
        existing = self.read(name)
        fm = frontmatter if frontmatter is not None else existing.frontmatter
        path.write_text(self._serialize(content, fm), encoding="utf-8")

    def delete(self, name: str) -> None:
        path = self._path(name)
        if not path.exists():
            raise NoteNotFoundError(f"Note not found: {name}")
        path.unlink()

    def all_names(self) -> list[str]:
        return [p.stem for p in self._root.glob("*.md")]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _path(self, name: str) -> Path:
        return self._root / f"{name}.md"

    @staticmethod
    def _serialize(content: str, frontmatter: dict) -> str:
        if frontmatter:
            fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
            return f"---\n{fm_str}---\n\n{content}"
        return content

    _FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

    @classmethod
    def _parse(cls, raw: str) -> tuple[str, dict]:
        m = cls._FRONTMATTER_RE.match(raw)
        if m:
            fm = yaml.safe_load(m.group(1)) or {}
            content = raw[m.end():]
            if content.startswith("\n"):
                content = content[1:]
            return content, fm
        return raw, {}
