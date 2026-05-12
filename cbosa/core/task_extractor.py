"""
TaskExtractor — regex-based action item extraction from email text.

Scans subject/body text for action items using heuristics:
- Deadline keywords: due, deadline, by [date]
- Request patterns: please, can you, could you, would you, need you to, I need
- Follow-up patterns: follow up, follow-up, get back to, let me know, RSVP
- Action verbs at line start: send, review, complete, submit, confirm, update, check
- Calendar keywords: meeting, call, appointment, schedule
"""
from __future__ import annotations

import re

# Patterns that identify action-item sentences
_TASK_PATTERNS: list[re.Pattern] = [
    # Deadline keywords
    re.compile(r"\b(due|deadline|due date)\b", re.IGNORECASE),
    re.compile(r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
               r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}[/-]\d{1,2})", re.IGNORECASE),
    # Request patterns
    re.compile(r"\b(please|can you|could you|would you|need you to|i need)\b", re.IGNORECASE),
    # Follow-up patterns
    re.compile(r"\b(follow[- ]?up|get back to|let me know|rsvp)\b", re.IGNORECASE),
    # Action verbs at the start of a sentence/line
    re.compile(r"(?:^|\.\s+|\n)\s*(send|review|complete|submit|confirm|update|check)\b", re.IGNORECASE),
    # Calendar keywords
    re.compile(r"\b(meeting|call|appointment|schedule)\b", re.IGNORECASE),
]


class TaskExtractor:
    """Extracts action items from email subject and body text."""

    def extract_tasks(self, text: str) -> list[str]:
        """
        Return a list of sentences/lines from *text* that look like action items.

        Each returned string is the original sentence preserved verbatim.
        Duplicates are removed (case-insensitive) and order is preserved.
        """
        if not text or not text.strip():
            return []

        sentences = _split_sentences(text)
        seen: set[str] = set()
        results: list[str] = []
        for sentence in sentences:
            stripped = sentence.strip()
            if not stripped:
                continue
            if _is_action_item(stripped):
                key = stripped.lower()
                if key not in seen:
                    seen.add(key)
                    results.append(stripped)
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """Split text into candidate sentences by line breaks and sentence-ending punctuation."""
    lines = text.splitlines()
    sentences: list[str] = []
    for line in lines:
        parts = re.split(r"\.\s+", line)
        sentences.extend(parts)
    return sentences


def _is_action_item(sentence: str) -> bool:
    """Return True if the sentence matches any action-item pattern."""
    return any(p.search(sentence) for p in _TASK_PATTERNS)
