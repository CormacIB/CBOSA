"""
CaptureEngine — fetches and extracts content from URLs and PDFs,
assembling the result into a Markdown note under data/captures/.

External dependencies (all optional / injectable for testing):
  httpx          — HTTP client for article fetching
  beautifulsoup4 — HTML parsing
  yt-dlp         — YouTube metadata + transcript extraction
  pypdf          — PDF text extraction

Injectable callables for testing:
  http_client    — httpx.Client instance
  ydl_extract_fn — callable(url: str) -> dict{title, description, transcript}
  pdf_text_fn    — callable(path: Path) -> str
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cbosa.ai.service import AIService, NullAIService
from cbosa.core.note_store import NoteStore


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class CaptureResult:
    """Content extracted from a URL or PDF, ready to be saved as a note."""
    source: str
    title: str
    content: str
    capture_type: str   # "article" | "youtube" | "pdf"
    capture_date: str   # YYYY-MM-DD


class CaptureFetchError(Exception):
    """Raised when content cannot be fetched or extracted."""


# ---------------------------------------------------------------------------
# Default extraction helpers (use real libraries when available)
# ---------------------------------------------------------------------------

def _default_ydl_extract(url: str) -> dict:
    try:
        import yt_dlp  # type: ignore[import]
    except ImportError as exc:
        raise CaptureFetchError("yt-dlp is required for YouTube capture") from exc
    ydl_opts = {"quiet": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
            return {
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "transcript": "",
            }
    except Exception as exc:
        raise CaptureFetchError(f"yt-dlp extraction failed: {exc}") from exc


def _default_pdf_text(path) -> str:
    try:
        import pypdf  # type: ignore[import]
    except ImportError as exc:
        raise CaptureFetchError("pypdf is required for PDF capture") from exc
    try:
        reader = pypdf.PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except Exception as exc:
        raise CaptureFetchError(f"PDF extraction failed: {exc}") from exc


def _parse_article_html(html: str) -> tuple[str, str]:
    """Extract (title, body_text) from raw HTML via BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import]
    except ImportError as exc:
        raise CaptureFetchError("beautifulsoup4 is required for article capture") from exc

    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    body = soup.body or soup
    text = body.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title, text


# ---------------------------------------------------------------------------
# CaptureEngine
# ---------------------------------------------------------------------------

class CaptureEngine:
    """
    Fetches content from article URLs, YouTube URLs, or PDF files and
    assembles a CaptureResult ready to be saved as a Markdown note.

    All external I/O is injectable for testing:
      engine = CaptureEngine(
          http_client=httpx.Client(transport=MockTransport(...)),
          ydl_extract_fn=lambda url: {...},
          pdf_text_fn=lambda path: "text",
      )
    """

    def __init__(
        self,
        http_client=None,
        ydl_extract_fn=None,
        pdf_text_fn=None,
        ai_service: AIService | None = None,
    ) -> None:
        self._http = http_client
        self._ydl_extract = ydl_extract_fn or _default_ydl_extract
        self._pdf_text = pdf_text_fn or _default_pdf_text
        self._ai = ai_service or NullAIService()

    # ------------------------------------------------------------------
    # URL type detection
    # ------------------------------------------------------------------

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url

    # ------------------------------------------------------------------
    # Capture methods
    # ------------------------------------------------------------------

    def capture_url(self, url: str) -> CaptureResult:
        """
        Fetch and extract content from a URL.

        Dispatches to YouTube or article extraction based on URL.
        Raises CaptureFetchError on any failure.
        """
        if self.is_youtube_url(url):
            return self._capture_youtube(url)
        return self._capture_article(url)

    def capture_pdf(self, path: Path) -> CaptureResult:
        """
        Extract text from a PDF file.

        Raises CaptureFetchError on any failure.
        """
        path = Path(path)
        try:
            text = self._pdf_text(path)
        except CaptureFetchError:
            raise
        except Exception as exc:
            raise CaptureFetchError(f"PDF extraction failed: {exc}") from exc
        return CaptureResult(
            source=str(path),
            title=path.stem,
            content=text,
            capture_type="pdf",
            capture_date=date.today().isoformat(),
        )

    # ------------------------------------------------------------------
    # Save and relate
    # ------------------------------------------------------------------

    def save(self, result: CaptureResult, store: NoteStore) -> str:
        """
        Save a CaptureResult as a .md note in the given NoteStore.

        Returns the note name (without extension).
        """
        safe_title = re.sub(r"[^\w\s-]", "", result.title).strip()
        safe_title = re.sub(r"\s+", "_", safe_title)
        note_name = (
            f"{result.capture_date}_{safe_title}"
            if safe_title
            else f"capture_{result.capture_date}"
        )
        frontmatter = {
            "title": result.title,
            "source": result.source,
            "capture_date": result.capture_date,
            "capture_type": result.capture_type,
            "summary": self._ai.summarize(result.content),
        }
        store.create(note_name, result.content, frontmatter)
        return note_name

    def find_related(self, content: str, note_store: NoteStore) -> list[str]:
        """
        Return names of notes whose title appears as a keyword in content.

        Case-insensitive. Underscores in note names are treated as spaces.
        Used to suggest wikilinks after capture.
        """
        content_lower = content.lower()
        related: list[str] = []
        for name in note_store.all_names():
            name_lower = name.lower().replace("_", " ")
            if name_lower in content_lower:
                related.append(name)
        return related

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _capture_article(self, url: str) -> CaptureResult:
        try:
            import httpx as _httpx  # type: ignore[import]
        except ImportError as exc:
            raise CaptureFetchError("httpx is required for article capture") from exc

        http = self._http or _httpx.Client()
        try:
            response = http.get(url)
        except Exception as exc:
            raise CaptureFetchError(f"Network error fetching {url}: {exc}") from exc

        if response.status_code >= 400:
            raise CaptureFetchError(f"HTTP {response.status_code} fetching {url}")

        title, content = _parse_article_html(response.text)
        return CaptureResult(
            source=url,
            title=title,
            content=content,
            capture_type="article",
            capture_date=date.today().isoformat(),
        )

    def _capture_youtube(self, url: str) -> CaptureResult:
        try:
            data = self._ydl_extract(url)
        except CaptureFetchError:
            raise
        except Exception as exc:
            raise CaptureFetchError(f"YouTube extraction failed: {exc}") from exc

        title = data.get("title", "")
        description = data.get("description", "")
        transcript = data.get("transcript", "")
        content = (
            f"{description}\n\n## Transcript\n\n{transcript}"
            if transcript
            else description
        )
        return CaptureResult(
            source=url,
            title=title,
            content=content,
            capture_type="youtube",
            capture_date=date.today().isoformat(),
        )
