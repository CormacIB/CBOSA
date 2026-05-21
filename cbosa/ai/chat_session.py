"""ChatSession — lightweight message history for a single conversation thread."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatSession:
    messages: list[dict] = field(default_factory=list)

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def reset(self) -> None:
        self.messages.clear()
