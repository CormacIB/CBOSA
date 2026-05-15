"""
CBOSA application bootstrap.
Creates the QApplication, loads the theme, and launches the main window.
"""
import sys
from PyQt6.QtWidgets import QApplication

from cbosa import config
from cbosa.ai import NullAIService
from cbosa.core.daily_note import DailyNoteService
from cbosa.core.ledger import Ledger
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
from cbosa.ui.main_window import MainWindow
from cbosa.modules.canvas_store import CanvasStore
from cbosa.modules.capture_engine import CaptureEngine
from cbosa.modules.email_store import EmailStore
from cbosa.core.task_store import TaskStore
from cbosa.ui.panels import default_registry
from cbosa.ui.panels.canvas_panel import CanvasPanel
from cbosa.ui.panels.capture_panel import CapturePanel
from cbosa.ui.panels.email_panel import EmailPanel
from cbosa.ui.panels.finance_panel import FinancePanel
from cbosa.ui.panels.finance_summary_panel import FinanceSummaryPanel
from cbosa.ui.panels.graph_view import GraphViewPanel
from cbosa.ui.panels.note_browser import NoteBrowserPanel
from cbosa.ui.panels.note_editor import NoteEditorPanel
from cbosa.ui.panels.task_panel import TaskPanel


def _register_panels(registry=None) -> bool:
    """Register all panels and return True if AI backend is reachable."""
    if registry is None:
        registry = default_registry

    base_data_dir = config.resolve("data_dir", "data")
    store = NoteStore(base_data_dir / "notes")
    daily_store = NoteStore(base_data_dir / "daily")

    DailyNoteService(daily_store).ensure_today()

    tag_index = TagIndex(store)
    tag_index.rebuild()
    link_index = LinkIndex(store)
    link_index.rebuild()
    search_index = SearchIndex(store)
    search_index.rebuild()

    ai_cfg = config.get("ai", {})
    backend = ai_cfg.get("backend", "null")
    endpoint = ai_cfg.get("endpoint", "http://localhost:11434")
    model = ai_cfg.get("model", "")

    if backend == "ollama":
        import httpx
        from cbosa.ai.ollama_service import OllamaAIService
        ai_service = OllamaAIService(endpoint, model, search_index)
        try:
            resp = httpx.get(f"{endpoint}/api/tags", timeout=2.0)
            ai_available = resp.status_code == 200
        except Exception:
            ai_available = False
    else:
        ai_service = NullAIService()
        ai_available = True  # null backend is intentional — no warning needed

    registry.register(
        "Note Browser",
        lambda title, parent: NoteBrowserPanel(
            store, tag_index, search_index, title, parent,
            daily_store=daily_store, link_index=link_index,
        ),
    )
    registry.register(
        "Note Editor",
        lambda title, parent: NoteEditorPanel(
            store, link_index, title, parent, daily_store=daily_store, ai_service=ai_service
        ),
    )
    registry.register(
        "Graph View",
        lambda title, parent: GraphViewPanel(store, link_index, title, parent),
    )
    ledger_path = base_data_dir / "finance.db"
    ledger = Ledger(ledger_path)
    registry.register(
        "Finance",
        lambda title, parent: FinancePanel(ledger, title, parent, ai_service=ai_service),
    )
    registry.register(
        "Finance Summary",
        lambda title, parent: FinanceSummaryPanel(ledger, title, parent),
    )
    task_store = TaskStore(base_data_dir / "tasks.db")
    registry.register(
        "Tasks",
        lambda title, parent: TaskPanel(task_store, title, parent),
    )
    email_db_path = base_data_dir / "email.db"
    email_store = EmailStore(email_db_path)
    registry.register(
        "Email",
        lambda title, parent: EmailPanel(email_store, title, parent, ai_service=ai_service),
    )
    canvas_db_path = base_data_dir / "canvas.db"
    canvas_store = CanvasStore(canvas_db_path)
    registry.register(
        "Canvas",
        lambda title, parent: CanvasPanel(canvas_store, title, parent),
    )
    capture_engine = CaptureEngine(ai_service=ai_service)
    registry.register(
        "Capture",
        lambda title, parent: CapturePanel(
            capture_engine, store, all_notes_store=store, title=title, parent=parent
        ),
    )

    return ai_available


def create_app(argv=None) -> QApplication:
    """Create and configure the QApplication instance."""
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    app.setApplicationName("CBOSA")
    app.setOrganizationName("CBOSA")
    _apply_theme(app)
    return app


def _apply_theme(app: QApplication) -> None:
    theme_path = config.resolve("theme", "themes/dark_default.toml")
    theme_path = config.resolve("theme", "themes/dark_default.toml")
    engine = ThemeEngine()
    try:
        engine.apply(app, theme_path)
    except ThemeLoadError as exc:
        print(f"[CBOSA] Warning: could not load theme: {exc}", file=sys.stderr)


def run() -> int:
    """Entry point — create app, show window, start event loop."""
    app = create_app()
    ai_available = _register_panels()
    window = MainWindow(ai_available=ai_available)
    window.show()
    return app.exec()
