"""
ThemeEngine — loads a TOML theme file and produces a QSS stylesheet string.

Public interface:
    ThemeEngine().load(path: str) -> str
    ThemeEngine().apply(app: QApplication, path: str) -> None
    ThemeLoadError — raised for missing or malformed theme files
"""
import toml


class ThemeLoadError(Exception):
    """Raised when a theme file cannot be loaded or parsed."""


class ThemeEngine:
    def load(self, theme_path: str) -> str:
        """
        Read a TOML theme file and return a complete QSS string.

        Raises:
            ThemeLoadError: if the file does not exist or cannot be parsed.
        """
        colors, fonts = self._parse_theme(theme_path)
        return self._build_qss(colors, fonts)

    def apply(self, app, theme_path: str) -> None:
        """Load a theme and apply style + stylesheet + palette to the QApplication.

        Three layers are set in order:
        1. Base style → "Windows" (flat, no Fusion gradients) so that PyQt6Ads
           widgets which paint themselves via drawPrimitive/drawControl get a
           solid-fill from the palette instead of Fusion's lighter→darker gradient.
           CDockAreaTitleBar has WA_StyledBackground=False so QSS background-color
           is ignored for it; it falls back to palette + base style painting.
        2. QSS stylesheet → full control over all standard Qt widgets.
        3. QPalette → colour roles used by palette-painting widgets (PyQt6Ads chrome).
        """
        from PyQt6.QtWidgets import QStyleFactory
        app.setStyle(QStyleFactory.create("Windows"))
        colors, fonts = self._parse_theme(theme_path)
        app.setStyleSheet(self._build_qss(colors, fonts))
        app.setPalette(self._build_palette(colors))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _parse_theme(self, theme_path: str) -> tuple:
        """Read and parse a TOML theme file. Returns (colors, fonts) dicts."""
        try:
            with open(theme_path, "r", encoding="utf-8-sig") as f:
                raw = f.read()
        except FileNotFoundError:
            raise ThemeLoadError(f"Theme file not found: {theme_path}")

        try:
            data = toml.loads(raw)
        except toml.TomlDecodeError as exc:
            raise ThemeLoadError(f"Failed to parse theme file: {exc}")

        return data.get("colors", {}), data.get("fonts", {})

    def _build_palette(self, colors: dict):
        """Build a QPalette from theme colors so palette-based widgets are dark-themed."""
        from PyQt6.QtGui import QPalette, QColor

        bg      = QColor(colors.get("background", "#000000"))
        surface = QColor(colors.get("surface",    "#111111"))
        text    = QColor(colors.get("text",        "#ffffff"))
        muted   = QColor(colors.get("text_muted",  "#888888"))
        accent  = QColor(colors.get("accent",      "#ffffff"))
        border  = QColor(colors.get("border",      "#333333"))

        p = QPalette()
        p.setColor(QPalette.ColorRole.Window,          surface)
        p.setColor(QPalette.ColorRole.WindowText,      text)
        p.setColor(QPalette.ColorRole.Base,            bg)
        p.setColor(QPalette.ColorRole.AlternateBase,   surface)
        p.setColor(QPalette.ColorRole.Text,            text)
        p.setColor(QPalette.ColorRole.BrightText,      text)
        p.setColor(QPalette.ColorRole.Button,          surface)
        p.setColor(QPalette.ColorRole.ButtonText,      text)
        p.setColor(QPalette.ColorRole.Highlight,       accent)
        p.setColor(QPalette.ColorRole.HighlightedText, text)
        p.setColor(QPalette.ColorRole.PlaceholderText, muted)
        p.setColor(QPalette.ColorRole.Mid,             border)
        p.setColor(QPalette.ColorRole.Dark,            bg)
        p.setColor(QPalette.ColorRole.Shadow,          bg)
        # PyQt6Ads' built-in stylesheet uses:
        #   background: qlineargradient(stop:0 palette(window), stop:1 palette(light))
        # for the active tab.  Setting Light = Midlight = surface collapses both
        # gradient stops to the same colour, producing a flat solid fill.
        p.setColor(QPalette.ColorRole.Light,           surface)
        p.setColor(QPalette.ColorRole.Midlight,        surface)
        return p

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_qss(self, colors: dict, fonts: dict) -> str:
        bg = colors.get("background", "#000000")
        surface = colors.get("surface", "#111111")
        primary = colors.get("primary", "#222222")
        accent = colors.get("accent", "#d40b0b")
        text = colors.get("text", "#ffffff")
        text_muted = colors.get("text_muted", "#888888")
        border = colors.get("border", "#333333")

        family = fonts.get("family", "sans-serif")
        size_base = fonts.get("size_base", 13)
        size_small = fonts.get("size_small", 11)
        size_heading = fonts.get("size_heading", 16)

        return f"""
/* CBOSA Theme — generated by ThemeEngine */

QWidget {{
    background-color: {bg};
    color: {text};
    font-family: "{family}";
    font-size: {size_base}px;
    border: none;
}}

QMainWindow, QDialog {{
    background-color: {bg};
}}

QDockWidget {{
    background-color: {surface};
    color: {text};
    font-size: {size_base}px;
}}

QDockWidget::title {{
    background-color: {primary};
    color: {text};
    padding: 4px 8px;
    font-size: {size_small}px;
}}

QPushButton {{
    background-color: {primary};
    color: {text};
    border: 1px solid {border};
    padding: 4px 12px;
    font-size: {size_base}px;
}}

QPushButton:hover {{
    background-color: {accent};
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    font-family: "{family}";
    font-size: {size_base}px;
    padding: 2px 4px;
}}

QTreeView, QListView, QTableView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    alternate-background-color: {bg};
}}

QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{
    background-color: {accent};
    color: {text};
}}

QMenuBar {{
    background-color: {surface};
    color: {text};
}}

QMenuBar::item:selected {{
    background-color: {primary};
}}

QMenu {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
}}

QMenu::item:selected {{
    background-color: {accent};
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background-color: {surface};
    border: none;
    width: 8px;
    height: 8px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background-color: {border};
    border-radius: 4px;
}}

QLabel {{
    color: {text};
    font-size: {size_base}px;
}}

QLabel[heading="true"] {{
    font-size: {size_heading}px;
    color: {text};
}}

QLabel[muted="true"] {{
    color: {text_muted};
    font-size: {size_small}px;
}}

QSplitter::handle {{
    background-color: {border};
}}

QTabWidget::pane {{
    background-color: {bg};
    border: 1px solid {border};
}}

QTabBar {{
    background-color: {surface};
}}

QTabBar::tab {{
    background-color: {surface};
    color: {text};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 4px 12px;
    font-size: {size_small}px;
}}

QTabBar::tab:selected {{
    background-color: {surface};
    color: {text};
    border-bottom: 2px solid {accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: {surface};
    color: {text};
}}

QHeaderView {{
    background-color: {surface};
    color: {text};
    border: none;
}}

QHeaderView::section {{
    background-color: {surface};
    color: {text};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: 4px 6px;
    font-size: {size_small}px;
}}

QComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    padding: 2px 6px;
    font-size: {size_base}px;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    selection-background-color: {accent};
}}

QStatusBar {{
    background-color: {surface};
    color: {text_muted};
    font-size: {size_small}px;
}}

/* ------------------------------------------------------------------ */
/* PyQtAds chrome — Issue #19                                          */
/* ------------------------------------------------------------------ */

ads--CDockManager {{
    background-color: {bg};
}}

ads--CDockWidget {{
    background-color: {surface};
}}

ads--CDockWidgetTitleBar {{
    background-color: {surface};
    color: {text};
    border-bottom: 1px solid {border};
    padding: 0px 4px;
}}

CTitleBarButton {{
    color: {text};
    background-color: transparent;
    border: none;
    padding: 2px 4px;
}}

CTitleBarButton:hover {{
    background-color: {primary};
    color: {text};
}}

ads--CDockAreaWidget {{
    background-color: {bg};
}}

ads--CDockAreaTitleBar {{
    background-color: {surface};
    border-bottom: 1px solid {border};
    padding: 0px;
}}

ads--CDockAreaTabBar {{
    background-color: {surface};
    border-bottom: 1px solid {border};
}}

ads--CDockWidgetTab {{
    background-color: {surface};
    color: {text};
    border-top: 2px solid transparent;
    padding: 4px 8px;
    font-family: "{family}";
    font-size: {size_small}px;
}}

ads--CDockWidgetTab QLabel {{
    background-color: transparent;
    color: {text};
}}

ads--CDockWidgetTab[activeTab="true"] {{
    background-color: {surface};
    color: {text};
    border-top: 2px solid {accent};
}}

ads--CDockWidgetTab[activeTab="true"] QLabel {{
    background-color: transparent;
    color: {text};
}}

ads--CDockSplitter::handle {{
    background-color: {border};
}}
""".strip()
