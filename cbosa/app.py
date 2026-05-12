"""
CBOSA application bootstrap.
Creates the QApplication, loads the theme, and launches the main window.
"""
import sys
from PyQt6.QtWidgets import QApplication

from cbosa import config
from cbosa.core.daily_note import DailyNoteService
from cbosa.core.ledger import Ledger
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
from cbosa.ui.main_window import MainWindow
from cbosa.modules.email_store import EmailStore
from cbosa.ui.panels import default_registry, BasePanel
from cbosa.ui.panels.email_panel import EmailPanel
from cbosa.ui.panels.finance_panel import FinancePanel
from cbosa.ui.panels.graph_view import GraphViewPanel
from cbosa.ui.panels.note_browser import NoteBrowserPanel
from cbosa.ui.panels.note_editor import NoteEditorPanel


def _register_panels(registry=None) -> None:
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
            store, link_index, title, parent, daily_store=daily_store
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
        lambda title, parent: FinancePanel(ledger, title, parent),
    )
    email_db_path = base_data_dir / "email.db"
    email_store = EmailStore(email_db_path)
    registry.register(
        "Email",
        lambda title, parent: EmailPanel(email_store, title, parent),
    )
    registry.register("Canvas", BasePanel)


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
    _register_panels()
    window = MainWindow()
    window.show()
    return app.exec()
