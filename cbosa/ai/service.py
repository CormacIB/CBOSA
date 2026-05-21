"""
AIService — abstract interface for AI capabilities.
NullAIService — no-op stub; all methods return empty/default values.

Swap implementations by passing a different AIService subclass at startup.
No panel or module imports a concrete AI backend directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIService(ABC):
    """Abstract interface for all AI operations used in CBOSA."""

    @abstractmethod
    def summarize(self, text: str) -> str:
        """Return a short summary of *text*, or '' if unavailable."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a vector embedding of *text*, or [] if unavailable."""

    @abstractmethod
    def find_connections(self, note_id: str, all_notes: list) -> list[str]:
        """Return note IDs/names likely related to *note_id*, or []."""

    @abstractmethod
    def extract_tasks(self, text: str) -> list[str]:
        """Return a list of action-item strings extracted from *text*, or []."""

    @abstractmethod
    def key_points(self, text: str) -> list[str]:
        """Return a list of key takeaway strings extracted from *text*, or []."""

    @abstractmethod
    def answer(self, query: str, context: list[str]) -> str:
        """Answer *query* given *context* snippets, or '' if unavailable."""

    @abstractmethod
    def chat(self, messages: list[dict], context: list[str] = []) -> str:
        """Multi-turn chat. messages is list of {role, content} dicts.
        context snippets are injected into the final user turn."""

    def context_info(self) -> dict:
        """Return display info about the backend: model name and context window size.
        Returns {} if the backend doesn't expose this (e.g. NullAIService)."""
        return {}


class NullAIService(AIService):
    """No-op stub — returns empty values for every method.

    Used as the default backend until a real AI implementation is configured.
    Panels and modules that depend on AIService will degrade gracefully.
    """

    def summarize(self, text: str) -> str:
        return ""

    def embed(self, text: str) -> list[float]:
        return []

    def find_connections(self, note_id: str, all_notes: list) -> list[str]:
        return []

    def extract_tasks(self, text: str) -> list[str]:
        return []

    def key_points(self, text: str) -> list[str]:
        return []

    def answer(self, query: str, context: list[str]) -> str:
        return ""

    def chat(self, messages: list[dict], context: list[str] = []) -> str:
        return ""
