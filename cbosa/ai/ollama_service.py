"""
OllamaAIService — AIService implementation backed by a locally-running Ollama instance.

Communicates via httpx blocking HTTP calls (POST /api/generate).
All methods return empty defaults on any network error or non-200 response
without raising. find_connections() pre-filters candidates via SearchIndex FTS5
(top 15 results) when a search_index is supplied.
"""
from __future__ import annotations

import sys
from typing import Optional

import httpx

from cbosa.ai.service import AIService


class OllamaAIService(AIService):
    """Concrete AIService that delegates to a locally-running Ollama instance."""

    def __init__(
        self,
        endpoint: str,
        model: str,
        search_index=None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._search_index = search_index
        self._client = client or httpx.Client()

    # ------------------------------------------------------------------
    # AIService interface
    # ------------------------------------------------------------------

    def summarize(self, text: str) -> str:
        prompt = f"Summarize the following text concisely:\n\n{text}"
        return self._generate(prompt)

    def embed(self, text: str) -> list[float]:
        return []

    def find_connections(self, note_id: str, all_notes: list) -> list[str]:
        if self._search_index is not None:
            try:
                candidates = self._search_index.search(note_id)[:15]
            except Exception:
                candidates = []
        else:
            candidates = [n for n in all_notes if n != note_id][:15]

        if not candidates:
            return []

        prompt = (
            f"Given the note '{note_id}', which of the following notes are most related?\n"
            f"Notes: {', '.join(str(c) for c in candidates)}\n"
            "Return only the names of related notes, one per line."
        )
        response = self._generate(prompt)
        if not response:
            return []
        return [line.strip() for line in response.splitlines() if line.strip()]

    def extract_tasks(self, text: str) -> list[str]:
        prompt = (
            "Extract all action items and tasks from the following text. "
            "Return one task per line:\n\n" + text
        )
        response = self._generate(prompt)
        if not response:
            return []
        return [line.strip() for line in response.splitlines() if line.strip()]

    def answer(self, query: str, context: list[str]) -> str:
        context_text = "\n\n".join(context)
        prompt = f"Context:\n{context_text}\n\nQuestion: {query}\nAnswer:"
        return self._generate(prompt)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _generate(self, prompt: str) -> str:
        """POST to Ollama /api/generate. Returns response text or '' on any error."""
        url = f"{self._endpoint}/api/generate"
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        try:
            resp = self._client.post(url, json=payload, timeout=30.0)
        except Exception as exc:
            print(f"[OllamaAIService] HTTP error: {exc}", file=sys.stderr)
            return ""
        if resp.status_code != 200:
            print(
                f"[OllamaAIService] Non-200 response: {resp.status_code}",
                file=sys.stderr,
            )
            return ""
        try:
            return resp.json().get("response", "")
        except Exception as exc:
            print(f"[OllamaAIService] JSON parse error: {exc}", file=sys.stderr)
            return ""
