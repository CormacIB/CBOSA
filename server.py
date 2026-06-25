"""CBOSA FastAPI server — wraps the Python core as a local REST API."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

from cbosa import config
from cbosa.ai.ollama_service import OllamaAIService
from cbosa.ai.service import NullAIService
from cbosa.core.daily_note import DailyNoteService
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import DuplicateNoteError, NoteNotFoundError, NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.core.timer_store import TimerStore, TimerStoreError

app = FastAPI(title="CBOSA API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Bootstrap ────────────────────────────────────────────────────────────────

config.load()
data_dir = config.resolve("data_dir", "data")
notes_dir = data_dir / "notes"
daily_dir = data_dir / "daily"
captures_dir = data_dir / "captures"

note_store = NoteStore(notes_dir)
daily_store = NoteStore(daily_dir)
capture_store = NoteStore(captures_dir)

link_index = LinkIndex(note_store)
tag_index = TagIndex(note_store)
search_index = SearchIndex(note_store)
daily_service = DailyNoteService(daily_store)
timer_store = TimerStore(data_dir / "timer.db")

link_index.rebuild()
tag_index.rebuild()
search_index.rebuild()

ai_cfg = config.get("ai", {})
if ai_cfg.get("backend") == "ollama":
    ai_service = OllamaAIService(
        endpoint=ai_cfg.get("endpoint", "http://localhost:11434"),
        model=ai_cfg.get("model", "hermes3"),
        search_index=search_index,
        num_ctx=ai_cfg.get("num_ctx", 8192),
    )
else:
    ai_service = NullAIService()


# ── Pydantic models ──────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    name: str
    content: str = ""
    frontmatter: dict = {}

class NoteUpdate(BaseModel):
    content: str
    frontmatter: Optional[dict] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context_notes: list[str] = []

class TimerSessionRequest(BaseModel):
    category_id: int
    start_time: str
    end_time: str

class GroupRequest(BaseModel):
    name: str

class CategoryRequest(BaseModel):
    name: str

class CaptureRequest(BaseModel):
    content: str


# ── Notes ────────────────────────────────────────────────────────────────────

@app.get("/api/notes")
def list_notes():
    return {"notes": note_store.all_names()}

@app.get("/api/notes/{name:path}/backlinks")
def get_backlinks(name: str):
    return {"backlinks": link_index.links_to(name)}

@app.get("/api/notes/{name:path}")
def get_note(name: str):
    try:
        note = note_store.read(name)
        return {"name": note.name, "content": note.content, "frontmatter": note.frontmatter}
    except NoteNotFoundError:
        raise HTTPException(404, f"Note not found: {name}")

@app.post("/api/notes")
def create_note(body: NoteCreate):
    try:
        note = note_store.create(body.name, body.content, body.frontmatter or None)
        _rebuild_indexes()
        return {"name": note.name}
    except DuplicateNoteError:
        raise HTTPException(409, f"Note already exists: {body.name}")

@app.put("/api/notes/{name:path}")
def update_note(name: str, body: NoteUpdate):
    try:
        note_store.update(name, body.content, body.frontmatter)
        _rebuild_indexes()
        return {"ok": True}
    except NoteNotFoundError:
        raise HTTPException(404, f"Note not found: {name}")

@app.delete("/api/notes/{name:path}")
def delete_note(name: str):
    try:
        note_store.delete(name)
        _rebuild_indexes()
        return {"ok": True}
    except NoteNotFoundError:
        raise HTTPException(404, f"Note not found: {name}")


# ── Search ───────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search(q: str = Query(...)):
    try:
        results = search_index.search_snippets(q, limit=20)
        return {"results": [{"name": r[0], "snippet": r[1]} for r in results]}
    except Exception:
        return {"results": []}


# ── Tags ─────────────────────────────────────────────────────────────────────

@app.get("/api/tags")
def list_tags():
    return {"tags": list(tag_index._map.keys())}


# ── Daily note ───────────────────────────────────────────────────────────────

@app.get("/api/daily")
def get_daily():
    note = daily_service.ensure_today()
    return {"name": note.name, "content": note.content, "frontmatter": note.frontmatter}

@app.put("/api/daily/{name:path}")
def update_daily(name: str, body: NoteUpdate):
    try:
        daily_store.update(name, body.content, body.frontmatter)
        return {"ok": True}
    except NoteNotFoundError:
        raise HTTPException(404, f"Daily note not found: {name}")


# ── Capture ──────────────────────────────────────────────────────────────────

@app.post("/api/capture")
def capture(body: CaptureRequest):
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"capture-{ts}"
    capture_store.create(name, body.content.strip())
    return {"name": name}


# ── AI chat ──────────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(body: ChatRequest):
    context: list[str] = []
    for note_name in body.context_notes:
        try:
            note = note_store.read(note_name)
            context.append(f"[{note_name}]\n{note.content}")
        except NoteNotFoundError:
            pass
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    response = ai_service.chat(messages, context)
    return {"response": response}

@app.get("/api/ai/info")
def ai_info():
    return ai_service.context_info()


# ── Timer ────────────────────────────────────────────────────────────────────

@app.get("/api/timer/groups")
def list_groups():
    return {"groups": timer_store.list_groups()}

@app.post("/api/timer/groups")
def add_group(body: GroupRequest):
    try:
        gid = timer_store.add_group(body.name)
        return {"id": gid}
    except TimerStoreError as e:
        raise HTTPException(400, str(e))

@app.get("/api/timer/groups/{group_id}/categories")
def list_categories(group_id: int):
    return {"categories": timer_store.list_categories(group_id)}

@app.post("/api/timer/groups/{group_id}/categories")
def add_category(group_id: int, body: CategoryRequest):
    try:
        cid = timer_store.add_category(group_id, body.name)
        return {"id": cid}
    except TimerStoreError as e:
        raise HTTPException(400, str(e))

@app.post("/api/timer/sessions")
def log_session(body: TimerSessionRequest):
    try:
        sid = timer_store.log_session(body.category_id, body.start_time, body.end_time)
        return {"id": sid}
    except TimerStoreError as e:
        raise HTTPException(400, str(e))

@app.get("/api/timer/sessions")
def list_sessions(start_date: Optional[str] = None, end_date: Optional[str] = None):
    return {"sessions": timer_store.list_sessions(start_date, end_date)}

@app.get("/api/timer/totals")
def category_totals(start_date: Optional[str] = None, end_date: Optional[str] = None):
    return {"totals": timer_store.category_totals(start_date, end_date)}


# ── Config ───────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    return {
        "ai": config.get("ai", {}),
        "data_dir": str(data_dir),
    }

@app.get("/api/health")
def health():
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rebuild_indexes() -> None:
    search_index.rebuild()
    link_index.rebuild()
    tag_index.rebuild()


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CBOSA API server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
