"""
CBOSA application bootstrap.
Creates the QApplication, loads the theme, and launches the main window.
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from cbosa import config
from cbosa.core.link_index import LinkIndex
from cbosa.core.note_store import NoteStore
from cbosa.core.search_index import SearchIndex
from cbosa.core.tag_index import TagIndex
from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
from cbosa.ui.main_window import MainWindow
from cbosa.ui.panels import default_registry, BasePanel
from cbosa.ui.panels.note_browser import NoteBrowserPanel
from cbosa.ui.panels.note_editor import NoteEditorPanel


def _register_panels(registry=None) -> None:
    if registry is None:
        registry = default_registry

    data_dir = Path(config.get("data_dir", "data")) / "notes"
    store = NoteStore(data_dir)
    tag_index = TagIndex(store)
    tag_index.rebuild()
    link_index = LinkIndex(store)
    link_index.rebuild()
    search_index = SearchIndex(store)
    search_index.rebuild()

    registry.register(
        "Note Browser",
        lambda title, parent: NoteBrowserPanel(store, tag_index, search_index, title, parent),
    )
    registry.register(
        "Note Editor",
        lambda title, parent: NoteEditorPanel(store, link_index, title, parent),
    )
    registry.register("Finance", BasePanel)
    registry.register("Email", BasePanel)
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
    theme_path = config.get("theme", "themes/dark_default.toml")
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
