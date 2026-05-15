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


# Words per chunk for map-reduce summarisation (~3 300 tokens, safe within 8 k ctx)
_CHUNK_WORDS = 2500


class OllamaAIService(AIService):
    """Concrete AIService that delegates to a locally-running Ollama instance."""

    def __init__(
        self,
        endpoint: str,
        model: str,
        search_index=None,
        client: Optional[httpx.Client] = None,
        num_ctx: int = 8192,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._search_index = search_index
        self._client = client or httpx.Client()
        self._num_ctx = num_ctx

    # ------------------------------------------------------------------
    # AIService interface
    # ------------------------------------------------------------------

    def summarize(self, text: str) -> str:
        if len(text.split()) <= _CHUNK_WORDS:
            return self._generate(f"Summarize the following text concisely:\n\n{text}")
        # Long text: map-reduce — summarise each chunk, then combine
        chunk_summaries = []
        for chunk in self._chunk_text(text):
            s = self._generate(f"Summarize this section concisely in 2-3 sentences:\n\n{chunk}")
            if s:
                chunk_summaries.append(s)
        if not chunk_summaries:
            return ""
        combined = "\n\n".join(chunk_summaries)
        return self._generate(
            f"Combine these section summaries into one cohesive paragraph:\n\n{combined}"
        )

    def embed(self, text: str) -> list[float]:
        return []

    def find_connections(self, note_id: str, all_notes: list) -> list[str]:
        # all_notes may be list[str] (names only) or list[tuple[str, str]] (name, snippet)
        snippet_map: dict[str, str] = {}
        if all_notes and isinstance(all_notes[0], tuple):
            for item in all_notes:
                snippet_map[item[0]] = item[1]

        if self._search_index is not None:
            try:
                candidates = self._search_index.search(note_id)[:15]
            except Exception:
                candidates = []
        else:
            names = [item[0] if isinstance(item, tuple) else item for item in all_notes]
            candidates = [n for n in names if n != note_id][:15]

        if not candidates:
            return []

        if snippet_map:
            candidate_lines = []
            for name in candidates:
                snippet = snippet_map.get(str(name), "")
                # Skip notes with too little content to judge relevance
                if len(snippet.split()) < 20:
                    continue
                candidate_lines.append(f'"{name}": {snippet}')
            if not candidate_lines:
                return []
            candidates_text = "\n".join(candidate_lines)
            prompt = (
                f"You are helping find notes related to '{note_id}'.\n"
                f"Here are candidate notes with brief excerpts:\n{candidates_text}\n\n"
                "Return only the names of notes you are confident are genuinely related "
                "based on their content. If none are clearly related, return nothing. "
                "One name per line, no explanation, no punctuation."
            )
        else:
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
            "Return one task per line. "
            "Do not include any introduction, preamble, or bullet characters. "
            "Output only the tasks, nothing else:\n\n" + text
        )
        response = self._generate(prompt)
        if not response:
            return []
        tasks = []
        for line in response.splitlines():
            line = line.strip().lstrip("-*\u2022 ").strip()
            if line and not line.endswith(":"):
                tasks.append(line)
        return tasks

    def key_points(self, text: str) -> list[str]:
        # For long text, summarise first so the key-points prompt fits in context
        working_text = text
        if len(text.split()) > _CHUNK_WORDS:
            working_text = self.summarize(text) or " ".join(text.split()[:_CHUNK_WORDS])
        if not working_text:
            return []
        prompt = (
            "List the key points and main takeaways from the following text. "
            "Return one concise point per line, starting each line with '- ':\n\n"
            + working_text
        )
        response = self._generate(prompt)
        if not response:
            return []
        return [
            line.lstrip("-• ").strip()
            for line in response.splitlines()
            if line.strip() and line.strip().startswith(("-", "•"))
        ]

    def answer(self, query: str, context: list[str]) -> str:
        context_text = "\n\n".join(context)
        prompt = f"Context:\n{context_text}\n\nQuestion: {query}\nAnswer:"
        return self._generate(prompt)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, max_words: int = _CHUNK_WORDS) -> list[str]:
        words = text.split()
        return [" ".join(words[i: i + max_words]) for i in range(0, len(words), max_words)]

    def _generate(self, prompt: str) -> str:
        """POST to Ollama /api/generate. Returns response text or '' on any error."""
        url = f"{self._endpoint}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": self._num_ctx},
        }
        try:
            resp = self._client.post(url, json=payload, timeout=1000.0)
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
