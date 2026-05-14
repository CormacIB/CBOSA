"""
Task — shared in-memory dataclass for action items extracted from any source.

This is a plain data structure with no persistence layer.
source values: "email", "canvas", "note"
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Task:
    """An action item extracted from an email, Canvas assignment, or note.

    Attributes:
        text:      The action item text.
        source:    Origin module — one of "email", "canvas", "note".
        source_id: Identifier of the originating item (e.g. email row id).
        due_date:  Optional due date. Defaults to None.
        priority:  Optional priority (higher = more urgent). Defaults to None.
    """

    text: str
    source: str
    source_id: str
    due_date: datetime | None = None
    priority: int | None = None
