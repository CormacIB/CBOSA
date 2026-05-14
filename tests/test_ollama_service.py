"""
Tests for OllamaAIService.

httpx is mocked by injecting a fake httpx.Client via the `client` constructor
parameter — the transport layer approach without reaching into httpx internals.
"""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

import httpx
import pytest

from cbosa.ai.ollama_service import OllamaAIService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(status: int = 200, body: dict | None = None, exc=None):
    """Return a fake httpx.Client whose .post() behaves as specified."""
    client = MagicMock()
    if exc is not None:
        client.post.side_effect = exc
    else:
        resp = Mock()
        resp.status_code = status
        resp.json.return_value = body or {}
        client.post.return_value = resp
    return client


# ---------------------------------------------------------------------------
# Cycle 1 — summarize success (tracer bullet)
# ---------------------------------------------------------------------------

def test_summarize_returns_llm_response():
    client = _mock_client(200, {"response": "a concise summary"})
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    assert svc.summarize("Some long text here") == "a concise summary"


# ---------------------------------------------------------------------------
# Cycle 2 — summarize: network error
# ---------------------------------------------------------------------------

def test_summarize_returns_empty_string_on_connect_error():
    client = _mock_client(exc=httpx.ConnectError("connection refused"))
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    assert svc.summarize("text") == ""


# ---------------------------------------------------------------------------
# Cycle 3 — summarize: non-200 response
# ---------------------------------------------------------------------------

def test_summarize_returns_empty_string_on_non_200():
    client = _mock_client(500, {})
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    assert svc.summarize("text") == ""


# ---------------------------------------------------------------------------
# Cycle 4 — embed always returns []
# ---------------------------------------------------------------------------

def test_embed_always_returns_empty_list():
    # Client should never be called — embed is unconditionally []
    client = _mock_client(200, {"embedding": [0.1, 0.2, 0.3]})
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    assert svc.embed("anything at all") == []
    client.post.assert_not_called()


# ---------------------------------------------------------------------------
# Cycle 5 — extract_tasks success
# ---------------------------------------------------------------------------

def test_extract_tasks_returns_list_from_newline_separated_response():
    client = _mock_client(200, {"response": "Buy milk\nCall Bob\nWrite report"})
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    assert svc.extract_tasks("meeting notes") == ["Buy milk", "Call Bob", "Write report"]


# ---------------------------------------------------------------------------
# Cycle 6 — extract_tasks: network error
# ---------------------------------------------------------------------------

def test_extract_tasks_returns_empty_list_on_network_error():
    client = _mock_client(exc=httpx.ConnectError("refused"))
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    assert svc.extract_tasks("text") == []


# ---------------------------------------------------------------------------
# Cycle 7 — answer success
# ---------------------------------------------------------------------------

def test_answer_returns_llm_response():
    client = _mock_client(200, {"response": "The answer is 42."})
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    result = svc.answer("What is the answer?", ["context snippet"])
    assert result == "The answer is 42."


# ---------------------------------------------------------------------------
# Cycle 8 — find_connections without search_index: error path returns []
# ---------------------------------------------------------------------------

def test_find_connections_without_search_index_returns_empty_on_error():
    client = _mock_client(exc=httpx.ConnectError("refused"))
    svc = OllamaAIService("http://localhost:11434", "llama3", client=client)
    result = svc.find_connections("my-note", ["other-note", "another-note"])
    assert result == []
