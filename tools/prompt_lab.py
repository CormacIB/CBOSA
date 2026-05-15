"""
prompt_lab.py — interactive prompt tester for OllamaAIService.

Run from the project root:
    python tools/prompt_lab.py

Loads a real note, fires each AIService method, and prints raw output so you
can judge quality and iterate on the prompts in cbosa/ai/ollama_service.py.

Config is read from cbosa.toml (same as the app). Hermes must be running.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from cbosa.config import load, get, resolve          # noqa: E402
from cbosa.ai.ollama_service import OllamaAIService  # noqa: E402
from cbosa.core.note_store import NoteStore          # noqa: E402

load()

# ── Config ────────────────────────────────────────────────────────────────────
AI_CFG      = get("ai", {})
ENDPOINT    = AI_CFG.get("endpoint", "http://localhost:11434")
MODEL       = AI_CFG.get("model", "")
DATA_DIR    = resolve("data_dir", "data")
NOTES_DIR   = DATA_DIR / "notes"

# ── Helpers ───────────────────────────────────────────────────────────────────
DIVIDER = "-" * 70

def header(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)

def show(label: str, value) -> None:
    print(f"\n[{label}]")
    if isinstance(value, list):
        if not value:
            print("  (empty list)")
        for item in value:
            print(f"  • {item}")
    else:
        if not value:
            print("  (empty string)")
        else:
            for line in textwrap.wrap(value, width=68):
                print(f"  {line}")

# ── Setup ─────────────────────────────────────────────────────────────────────
if not MODEL:
    print("ERROR: [ai] model is not set in cbosa.toml")
    print("Add:  model = \"hermes3\"  (or whatever your Ollama model name is)")
    sys.exit(1)

print(f"Endpoint : {ENDPOINT}")
print(f"Model    : {MODEL}")
print(f"Notes dir: {NOTES_DIR}")

store = NoteStore(NOTES_DIR)
all_names = store.all_names()

if not all_names:
    print("\nNo notes found. Add some notes to data/notes/ first.")
    sys.exit(1)

print(f"\nAvailable notes: {', '.join(all_names)}")

# Accept note name as CLI arg, e.g.: python tools/prompt_lab.py "future app ideas"
if len(sys.argv) > 1:
    choice = " ".join(sys.argv[1:])
    note_name = choice if choice in all_names else all_names[0]
    print(f"Using: '{note_name}'")
else:
    note_name = all_names[0]
    print(f"No arg given — defaulting to: '{note_name}'")
note = store.read(note_name)
note_text = note.content

print(f"\nLoaded: '{note_name}' ({len(note_text.split())} words)")

ai = OllamaAIService(endpoint=ENDPOINT, model=MODEL)

# ── Tests ─────────────────────────────────────────────────────────────────────
header(f"1. summarize  ->  '{note_name}'")
show("output", ai.summarize(note_text))

header(f"2. key_points  ->  '{note_name}'")
show("output", ai.key_points(note_text))

header(f"3. extract_tasks  ->  '{note_name}'")
show("output", ai.extract_tasks(note_text))

header(f"4. find_connections  ->  '{note_name}'")
all_notes_with_snippets = []
for name in all_names:
    try:
        n = store.read(name)
        words = n.content.split()
        snippet = " ".join(words[:50])
    except Exception:
        snippet = ""
    all_notes_with_snippets.append((name, snippet))
show("output", ai.find_connections(note_name, all_notes_with_snippets))

header(f"5. answer  ->  freeform Q&A against '{note_name}'")
question = "What are the main ideas in this note?"
print(f"Question: {question}")
show("output", ai.answer(question, [note_text]))

print(f"\n{DIVIDER}")
print("Done. Edit prompts in cbosa/ai/ollama_service.py then re-run.")
print(DIVIDER)
