"""
Tests for Issue #11 — CaptureEngine.

All network I/O is intercepted via injected http clients or fake functions.
No real network, yt-dlp, or pypdf calls are made.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cbosa.modules.capture_engine import (
    CaptureEngine,
    CaptureResult,
    CaptureFetchError,
)
from cbosa.core.note_store import NoteStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html(title: str, body_text: str) -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body><p>{body_text}</p></body></html>"
    )


class _MockTransport(httpx.BaseTransport):
    """Static route table: url_substring → (status_code, response_text)."""

    def __init__(self, routes: dict) -> None:
        self._routes = routes

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for fragment, (status, body) in self._routes.items():
            if fragment in url:
                if isinstance(body, str):
                    return httpx.Response(status, text=body)
                return httpx.Response(status, json=body)
        return httpx.Response(404, text="not found")


def _make_engine(routes: dict) -> CaptureEngine:
    transport = _MockTransport(routes)
    http = httpx.Client(transport=transport)
    return CaptureEngine(http_client=http)


_FAKE_YDL = lambda url: {  # noqa: E731
    "title": "My Video Title",
    "description": "A great video description.",
    "transcript": "Hello and welcome.",
}

_FAKE_PDF = lambda path: "Page one content.\n\nPage two content."  # noqa: E731


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: capture_url returns a CaptureResult
# ---------------------------------------------------------------------------

def test_capture_url_returns_capture_result():
    engine = _make_engine({"example.com": (200, _html("Title", "Content"))})
    result = engine.capture_url("http://example.com/article")
    assert isinstance(result, CaptureResult)


# ---------------------------------------------------------------------------
# Slice 2 — article source is the URL
# ---------------------------------------------------------------------------

def test_capture_url_sets_source():
    engine = _make_engine({"example.com": (200, _html("Title", "Content"))})
    result = engine.capture_url("http://example.com/article")
    assert result.source == "http://example.com/article"


# ---------------------------------------------------------------------------
# Slice 3 — article title extracted from HTML
# ---------------------------------------------------------------------------

def test_capture_url_extracts_title():
    engine = _make_engine({"example.com": (200, _html("My Interesting Article", "Some content"))})
    result = engine.capture_url("http://example.com/article")
    assert result.title == "My Interesting Article"


# ---------------------------------------------------------------------------
# Slice 4 — article content extracted from HTML body
# ---------------------------------------------------------------------------

def test_capture_url_extracts_content():
    engine = _make_engine({"example.com": (200, _html("Title", "Hello World content here"))})
    result = engine.capture_url("http://example.com/article")
    assert "Hello World content here" in result.content


# ---------------------------------------------------------------------------
# Slice 5 — article capture_type and capture_date
# ---------------------------------------------------------------------------

def test_capture_url_article_type():
    engine = _make_engine({"example.com": (200, _html("Title", "Content"))})
    result = engine.capture_url("http://example.com/article")
    assert result.capture_type == "article"


def test_capture_url_article_has_capture_date():
    engine = _make_engine({"example.com": (200, _html("Title", "Content"))})
    result = engine.capture_url("http://example.com/article")
    # YYYY-MM-DD format
    assert len(result.capture_date) == 10
    assert result.capture_date[4] == "-"
    assert result.capture_date[7] == "-"


# ---------------------------------------------------------------------------
# Slice 6 — YouTube URL detection
# ---------------------------------------------------------------------------

def test_is_youtube_url_youtube_com():
    assert CaptureEngine.is_youtube_url("https://www.youtube.com/watch?v=abc123")


def test_is_youtube_url_youtu_be():
    assert CaptureEngine.is_youtube_url("https://youtu.be/abc123")


def test_is_youtube_url_false_for_article():
    assert not CaptureEngine.is_youtube_url("https://example.com/article")


def test_is_youtube_url_false_for_file():
    assert not CaptureEngine.is_youtube_url("file:///home/user/doc.pdf")


# ---------------------------------------------------------------------------
# Slice 7 — YouTube capture returns CaptureResult
# ---------------------------------------------------------------------------

def test_capture_youtube_returns_capture_result():
    engine = CaptureEngine(ydl_extract_fn=_FAKE_YDL)
    result = engine.capture_url("https://www.youtube.com/watch?v=abc123")
    assert isinstance(result, CaptureResult)


def test_capture_youtube_type_is_youtube():
    engine = CaptureEngine(ydl_extract_fn=_FAKE_YDL)
    result = engine.capture_url("https://www.youtube.com/watch?v=abc123")
    assert result.capture_type == "youtube"


def test_capture_youtube_title_from_ydl():
    engine = CaptureEngine(ydl_extract_fn=_FAKE_YDL)
    result = engine.capture_url("https://www.youtube.com/watch?v=abc123")
    assert result.title == "My Video Title"


def test_capture_youtube_source_is_url():
    engine = CaptureEngine(ydl_extract_fn=_FAKE_YDL)
    url = "https://www.youtube.com/watch?v=abc123"
    result = engine.capture_url(url)
    assert result.source == url


def test_capture_youtube_content_includes_description():
    engine = CaptureEngine(ydl_extract_fn=_FAKE_YDL)
    result = engine.capture_url("https://www.youtube.com/watch?v=abc123")
    assert "A great video description." in result.content


def test_capture_youtube_content_includes_transcript():
    engine = CaptureEngine(ydl_extract_fn=_FAKE_YDL)
    result = engine.capture_url("https://www.youtube.com/watch?v=abc123")
    assert "Hello and welcome." in result.content


def test_capture_youtube_without_transcript():
    """YouTube result without transcript only shows description."""
    def no_transcript_ydl(url):
        return {"title": "Video", "description": "Desc only", "transcript": ""}
    engine = CaptureEngine(ydl_extract_fn=no_transcript_ydl)
    result = engine.capture_url("https://www.youtube.com/watch?v=abc")
    assert result.content == "Desc only"


# ---------------------------------------------------------------------------
# Slice 8 — PDF capture returns CaptureResult
# ---------------------------------------------------------------------------

def test_capture_pdf_returns_capture_result():
    engine = CaptureEngine(pdf_text_fn=_FAKE_PDF)
    result = engine.capture_pdf(Path("/fake/document.pdf"))
    assert isinstance(result, CaptureResult)


def test_capture_pdf_type_is_pdf():
    engine = CaptureEngine(pdf_text_fn=_FAKE_PDF)
    result = engine.capture_pdf(Path("/fake/document.pdf"))
    assert result.capture_type == "pdf"


def test_capture_pdf_content_has_extracted_text():
    engine = CaptureEngine(pdf_text_fn=_FAKE_PDF)
    result = engine.capture_pdf(Path("/fake/document.pdf"))
    assert "Page one content." in result.content


def test_capture_pdf_title_is_filename_stem():
    engine = CaptureEngine(pdf_text_fn=_FAKE_PDF)
    result = engine.capture_pdf(Path("/fake/research_paper.pdf"))
    assert result.title == "research_paper"


def test_capture_pdf_source_is_path_string():
    engine = CaptureEngine(pdf_text_fn=_FAKE_PDF)
    path = Path("/fake/document.pdf")
    result = engine.capture_pdf(path)
    assert str(path) in result.source


# ---------------------------------------------------------------------------
# Slice 9 — errors raise CaptureFetchError (no partial note created)
# ---------------------------------------------------------------------------

def test_http_404_raises_capture_fetch_error():
    engine = _make_engine({"example.com/missing": (404, "not found")})
    with pytest.raises(CaptureFetchError):
        engine.capture_url("http://example.com/missing")


def test_http_500_raises_capture_fetch_error():
    engine = _make_engine({"example.com": (500, "server error")})
    with pytest.raises(CaptureFetchError):
        engine.capture_url("http://example.com/article")


def test_ydl_error_raises_capture_fetch_error():
    def failing_ydl(url):
        raise RuntimeError("yt-dlp failed to extract")
    engine = CaptureEngine(ydl_extract_fn=failing_ydl)
    with pytest.raises(CaptureFetchError):
        engine.capture_url("https://www.youtube.com/watch?v=bad")


def test_pdf_error_raises_capture_fetch_error():
    def failing_pdf(path):
        raise OSError("file not readable")
    engine = CaptureEngine(pdf_text_fn=failing_pdf)
    with pytest.raises(CaptureFetchError):
        engine.capture_pdf(Path("/nonexistent.pdf"))


# ---------------------------------------------------------------------------
# Slice 10 — save creates note in store with correct frontmatter
# ---------------------------------------------------------------------------

def test_save_creates_note_in_store(tmp_path):
    store = NoteStore(tmp_path)
    engine = CaptureEngine()
    result = CaptureResult(
        source="http://example.com/article",
        title="Test Article",
        content="Some content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, store)
    assert note_name in store.all_names()


def test_save_note_has_source_frontmatter(tmp_path):
    store = NoteStore(tmp_path)
    engine = CaptureEngine()
    result = CaptureResult(
        source="http://example.com/article",
        title="Test Article",
        content="Some content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, store)
    note = store.read(note_name)
    assert note.frontmatter["source"] == "http://example.com/article"


def test_save_note_has_capture_date_frontmatter(tmp_path):
    store = NoteStore(tmp_path)
    engine = CaptureEngine()
    result = CaptureResult(
        source="http://example.com",
        title="Test Article",
        content="Content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, store)
    note = store.read(note_name)
    assert note.frontmatter["capture_date"] == "2026-05-11"


def test_save_note_has_capture_type_frontmatter(tmp_path):
    store = NoteStore(tmp_path)
    engine = CaptureEngine()
    result = CaptureResult(
        source="http://example.com",
        title="Test Article",
        content="Content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, store)
    note = store.read(note_name)
    assert note.frontmatter["capture_type"] == "article"


def test_save_note_has_summary_placeholder(tmp_path):
    store = NoteStore(tmp_path)
    engine = CaptureEngine()
    result = CaptureResult(
        source="http://example.com",
        title="Test Article",
        content="Content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, store)
    note = store.read(note_name)
    assert "summary" in note.frontmatter


def test_save_note_content_matches(tmp_path):
    store = NoteStore(tmp_path)
    engine = CaptureEngine()
    result = CaptureResult(
        source="http://example.com",
        title="Test Article",
        content="The captured body content.",
        capture_type="article",
        capture_date="2026-05-11",
    )
    note_name = engine.save(result, store)
    note = store.read(note_name)
    assert "The captured body content." in note.content


# ---------------------------------------------------------------------------
# Slice 11 — find_related returns matching note names
# ---------------------------------------------------------------------------

def test_find_related_empty_when_no_matches(tmp_path):
    store = NoteStore(tmp_path)
    store.create("Biology Notes", "Cell division content")
    engine = CaptureEngine()
    related = engine.find_related("A story about mountains and rivers", store)
    assert related == []


def test_find_related_finds_matching_note(tmp_path):
    store = NoteStore(tmp_path)
    store.create("Biology Notes", "Cell division content")
    engine = CaptureEngine()
    related = engine.find_related(
        "This article discusses Biology Notes in great depth", store
    )
    assert "Biology Notes" in related


def test_find_related_case_insensitive(tmp_path):
    store = NoteStore(tmp_path)
    store.create("Climate Change", "Global warming content")
    engine = CaptureEngine()
    related = engine.find_related("An article about climate change and its effects", store)
    assert "Climate Change" in related


def test_find_related_does_not_include_unrelated(tmp_path):
    store = NoteStore(tmp_path)
    store.create("Python Programming", "Code and algorithms")
    store.create("History of Rome", "Ancient empire")
    engine = CaptureEngine()
    related = engine.find_related("Python Programming is very popular today", store)
    assert "History of Rome" not in related


def test_find_related_returns_multiple_matches(tmp_path):
    store = NoteStore(tmp_path)
    store.create("Machine Learning", "ML algorithms")
    store.create("Neural Networks", "Deep learning")
    engine = CaptureEngine()
    related = engine.find_related(
        "Machine Learning and Neural Networks are related topics", store
    )
    assert "Machine Learning" in related
    assert "Neural Networks" in related
