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
from cbosa.core.timer_store import TimerStore
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
from cbosa.ui.main_window import MainWindow
from cbosa.modules.capture_engine import CaptureEngine
from cbosa.core.task_store import TaskStore
from cbosa.ui.panels import default_registry
from cbosa.ui.panels.chat_panel import ChatPanel
from cbosa.ui.panels.capture_panel import CapturePanel
from cbosa.ui.panels.finance_panel import FinancePanel
from cbosa.ui.panels.graph_view import GraphViewPanel
from cbosa.ui.panels.note_browser import NoteBrowserPanel
from cbosa.ui.panels.note_editor import NoteEditorPanel
from cbosa.ui.panels.task_panel import TaskPanel
from cbosa.ui.panels.timer_data_panel import TimerDataPanel
from cbosa.ui.hotkey_service import GlobalHotkeyService
from cbosa.ui.quick_capture import QuickCaptureWindow
from cbosa.ui.tray import TrayService


def _register_panels(registry=None, timer_store: TimerStore | None = None) -> bool:
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
    task_store = TaskStore(base_data_dir / "tasks.db")
    registry.register(
        "Tasks",
        lambda title, parent: TaskPanel(task_store, title, parent),
    )
    if timer_store is None:
        timer_store = TimerStore(base_data_dir / "timer.db")
    registry.register(
        "Time Tracker",
        lambda title, parent: TimerDataPanel(timer_store, title, parent),
    )
    capture_engine = CaptureEngine(ai_service=ai_service)
    registry.register(
        "Capture",
        lambda title, parent: CapturePanel(
            capture_engine, store, all_notes_store=store, title=title, parent=parent
        ),
    )
    registry.register(
        "Chat",
        lambda title, parent: ChatPanel(ai_service, search_index, store, title, parent),
    )

    return ai_available


def create_app(argv=None) -> QApplication:
    """Create and configure the QApplication instance."""
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    app.setApplicationName("CBOSA")
    app.setOrganizationName("CBOSA")
    app.setQuitOnLastWindowClosed(False)
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
    base_data_dir = config.resolve("data_dir", "data")
    timer_store = TimerStore(base_data_dir / "timer.db")
    ai_available = _register_panels(timer_store=timer_store)
    window = MainWindow(ai_available=ai_available, timer_store=timer_store)
    window.show()

    capture_window = QuickCaptureWindow(base_data_dir / "notes")

    tray = TrayService(window, capture_window, parent=app)
    tray.show()

    hotkey_service = GlobalHotkeyService(parent=app)
    hotkey_service.triggered.connect(capture_window.show)
    hotkey_service.start()

    exit_code = app.exec()
    hotkey_service.stop()
    return exit_code
