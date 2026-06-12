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


class DuplicateNoteError(FileExistsError):
    """Raised when a rename target already exists."""


class NoteStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, name: str, content: str, frontmatter: dict | None = None) -> Note:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def rename(self, old_name: str, new_name: str) -> Note:
        old_path = self._path(old_name)
        new_path = self._path(new_name)
        if not old_path.exists():
            raise NoteNotFoundError(f"Note not found: {old_name}")
        if new_path.exists():
            raise DuplicateNoteError(f"Note already exists: {new_name}")
        old_path.rename(new_path)
        return self.read(new_name)

    def all_names(self) -> list[str]:
        return [
            str(p.relative_to(self._root).with_suffix(""))
            for p in sorted(self._root.rglob("*.md"))
        ]

    def create_folder(self, rel_path: str) -> Path:
        folder = self._root / rel_path
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def all_folders(self) -> list[str]:
        """Return all subdirectory paths relative to root; '' represents the root."""
        folders: list[str] = [""]
        for p in sorted(self._root.rglob("*")):
            if p.is_dir():
                folders.append(str(p.relative_to(self._root)))
        return folders

    def move_note(self, name: str, new_folder: str) -> str:
        """Move note to new_folder. Returns the new full name (relative path)."""
        old_path = self._path(name)
        stem = Path(name).name
        new_name = f"{new_folder}/{stem}" if new_folder else stem
        new_path = self._path(new_name)
        if not old_path.exists():
            raise NoteNotFoundError(f"Note not found: {name}")
        if new_path.exists():
            raise DuplicateNoteError(f"Note already exists: {new_name}")
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        return new_name

    def resolve_name(self, bare_name: str) -> str:
        """Find a note by its bare stem, ignoring folder. Returns full name.

        Raises NoteNotFoundError if nothing matches. If multiple notes share
        the stem, returns the shallowest / alphabetically first.
        """
        matches = [
            n for n in self.all_names() if Path(n).name == bare_name
        ]
        if not matches:
            raise NoteNotFoundError(f"Note not found: {bare_name}")
        matches.sort(key=lambda n: (n.count("/"), n))
        return matches[0]

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
