"""
Tests for Issue #12 — AIService interface + NullAIService.

Verifies:
  - NullAIService returns correct empty types for all five methods
  - NullAIService satisfies the AIService ABC
  - CaptureEngine uses ai_service.summarize to populate the summary field
"""
from __future__ import annotations

import pytest

from cbosa.ai.service import AIService, NullAIService


# ---------------------------------------------------------------------------
# NullAIService — correct return types
# ---------------------------------------------------------------------------

class TestNullAIService:
    def setup_method(self):
        self.ai = NullAIService()

    def test_summarize_returns_empty_string(self):
        result = self.ai.summarize("some long text here")
        assert result == ""

    def test_embed_returns_empty_list(self):
        result = self.ai.embed("some text")
        assert result == []

    def test_find_connections_returns_empty_list(self):
        result = self.ai.find_connections("note-id", ["note1", "note2"])
        assert result == []

    def test_extract_tasks_returns_empty_list(self):
        result = self.ai.extract_tasks("Please send me the report by Friday")
        assert result == []

    def test_answer_returns_empty_string(self):
        result = self.ai.answer("What did I spend on food?", ["tx1", "tx2"])
        assert result == ""

    def test_is_instance_of_ai_service(self):
        assert isinstance(self.ai, AIService)


# ---------------------------------------------------------------------------
# CaptureEngine uses ai_service.summarize
# ---------------------------------------------------------------------------

class _SpyAIService(NullAIService):
    """Records calls to summarize so tests can verify integration."""

    def __init__(self):
        super().__init__()
        self.summarize_calls: list[str] = []

    def summarize(self, text: str) -> str:
        self.summarize_calls.append(text)
        return "AI summary"


class TestCaptureEngineAIIntegration:
    """CaptureEngine.save populates the summary frontmatter via ai_service."""

    def _make_engine(self, spy):
        from cbosa.modules.capture_engine import CaptureEngine
        return CaptureEngine(ai_service=spy)

    def test_save_calls_summarize_and_stores_result(self, tmp_path):
        from cbosa.modules.capture_engine import CaptureResult
        from cbosa.core.note_store import NoteStore

        spy = _SpyAIService()
        engine = self._make_engine(spy)
        store = NoteStore(tmp_path)

        result = CaptureResult(
            source="https://example.com",
            title="Test Article",
            content="Long article content here.",
            capture_type="article",
            capture_date="2026-05-11",
        )
        note_name = engine.save(result, store)

        # summarize should have been called with the article content
        assert len(spy.summarize_calls) == 1
        assert spy.summarize_calls[0] == "Long article content here."

        # the saved note's frontmatter should contain the AI summary
        note = store.read(note_name)
        assert note.frontmatter.get("summary") == "AI summary"

    def test_save_with_null_ai_service_leaves_summary_empty(self, tmp_path):
        from cbosa.modules.capture_engine import CaptureResult
        from cbosa.core.note_store import NoteStore

        engine = self._make_engine(NullAIService())
        store = NoteStore(tmp_path)

        result = CaptureResult(
            source="https://example.com",
            title="Test Article",
            content="content",
            capture_type="article",
            capture_date="2026-05-11",
        )
        note_name = engine.save(result, store)
        note = store.read(note_name)
        assert note.frontmatter.get("summary") == ""
