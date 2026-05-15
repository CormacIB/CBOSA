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

    def get_colors_and_fonts(self, theme_path: str) -> tuple[dict, dict]:
        """Return (colors, fonts) dicts for a theme file without applying it."""
        return self._parse_theme(theme_path)

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
        from PyQt6.QtGui import QFont
        app.setStyle(QStyleFactory.create("Windows"))
        colors, fonts = self._parse_theme(theme_path)
        family    = fonts.get("family",    "Segoe UI")
        size_base = fonts.get("size_base", 13)
        # QSS is applied first — it controls per-widget font sizes (e.g. menus
        # at size_small).  app.setFont() then sets the application-level
        # default for any widget not explicitly covered by a QSS rule.
        # Do NOT call widget.setFont() on individual widgets: that marks the
        # font as "explicitly set" on each widget, which takes precedence over
        # QSS font-size rules and causes menus to grow on successive switches.
        app.setStyleSheet(self._build_qss(colors, fonts))
        app.setPalette(self._build_palette(colors))
        app.setFont(QFont(family, size_base))
        # PyQtAds custom widgets (CDockWidgetTab etc.) do not always repaint
        # when the application stylesheet changes.  Force an unpolish/polish
        # cycle on every widget so QSS rules are re-evaluated without marking
        # any property as "explicitly set".
        style = app.style()
        for widget in app.allWidgets():
            style.unpolish(widget)
            style.polish(widget)
            widget.update()

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
        bg         = colors.get("background", "#000000")
        surface    = colors.get("surface",    "#111111")
        primary    = colors.get("primary",    "#222222")
        accent     = colors.get("accent",     "#cba6f7")
        text       = colors.get("text",       "#ffffff")
        text_muted = colors.get("text_muted", "#888888")
        text_faint = colors.get("text_faint", text_muted)
        border     = colors.get("border",     "#333333")
        link       = colors.get("link",       accent)

        family       = fonts.get("family",       "sans-serif")
        size_base    = fonts.get("size_base",    13)
        size_small   = fonts.get("size_small",   11)
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

/* ── Base ─────────────────────────────────────────────────────────── */

QMainWindow, QDialog {{
    background-color: {bg};
}}

/* ── Menu bar ─────────────────────────────────────────────────────── */

QMenuBar {{
    background-color: {bg};
    color: {text_muted};
    border-bottom: 1px solid {border};
    font-size: {size_small}px;
    padding: 0 2px;
}}

QMenuBar::item {{
    padding: 2px 8px;
    background: transparent;
    color: {text_muted};
}}

QMenuBar::item:selected, QMenuBar::item:pressed {{
    background-color: {surface};
    color: {text};
}}

QMenu {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    font-size: {size_small}px;
}}

QMenu::item {{
    padding: 4px 20px 4px 12px;
}}

QMenu::item:selected {{
    background-color: {primary};
    color: {accent};
}}

QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 2px 0;
}}

/* ── Buttons ──────────────────────────────────────────────────────── */

QPushButton {{
    background-color: {surface};
    color: {text_muted};
    border: 1px solid {border};
    padding: 3px 10px;
    font-size: {size_small}px;
}}

QPushButton:hover {{
    border-color: {text_muted};
    color: {text};
    background-color: {surface};
}}

QPushButton:pressed {{
    background-color: {primary};
}}

/* Toggle buttons (Edit / Preview / Split) */
QPushButton[role="toggle"] {{
    background-color: transparent;
    border: none;
    border-bottom: 1px solid transparent;
    color: {text_muted};
    padding: 2px 8px;
    font-size: {size_small}px;
    font-family: "{family}";
}}

QPushButton[role="toggle"]:hover {{
    color: {text};
    background-color: transparent;
    border-bottom: 1px solid transparent;
}}

QPushButton[role="toggle"]:checked {{
    color: {accent};
    background-color: transparent;
    border-bottom: 1px solid {accent};
}}

/* ── Inputs ───────────────────────────────────────────────────────── */

QLineEdit {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    font-family: "{family}";
    font-size: {size_base}px;
    padding: 3px 6px;
    selection-background-color: {primary};
    selection-color: {accent};
}}

QLineEdit:focus {{
    border-color: {text_muted};
    background-color: {primary};
}}

QLineEdit::placeholder {{
    color: {text_faint};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {bg};
    color: {text};
    border: none;
    font-family: "{family}";
    font-size: {size_base}px;
    padding: 2px 4px;
    selection-background-color: {primary};
    selection-color: {text};
}}

/* ── Lists / Trees ────────────────────────────────────────────────── */

QTreeView, QListView, QTableView {{
    background-color: {bg};
    color: {text};
    border: none;
    alternate-background-color: {bg};
    outline: none;
}}

QTreeView::item, QListView::item {{
    padding: 2px 4px;
    color: {text};
    border: none;
}}

QTreeView::item:hover, QListView::item:hover {{
    background-color: {surface};
    color: {text};
}}

QTreeView::item:selected, QListView::item:selected {{
    background-color: {surface};
    color: {accent};
}}

QTreeView::branch {{
    background: {bg};
    color: {text_muted};
}}

QHeaderView {{
    background-color: {surface};
    color: {text_muted};
    border: none;
    font-size: {size_small}px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QHeaderView::section {{
    background-color: {surface};
    color: {text_muted};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: 3px 6px;
    font-size: {size_small}px;
}}

/* ── Scroll bars ──────────────────────────────────────────────────── */

QScrollBar:vertical {{
    background-color: transparent;
    border: none;
    width: 8px;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    border: none;
    height: 8px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background-color: {text_faint};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background-color: {text_muted};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
    height: 0;
    width: 0;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* ── Labels ───────────────────────────────────────────────────────── */

QLabel {{
    color: {text};
    font-size: {size_base}px;
    background: transparent;
}}

QLabel[muted="true"] {{
    color: {text_muted};
    font-size: {size_small}px;
}}

/* ── Splitter ─────────────────────────────────────────────────────── */

QSplitter::handle {{
    background-color: {border};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── Tabs ─────────────────────────────────────────────────────────── */

QTabWidget::pane {{
    background-color: {bg};
    border: 1px solid {border};
}}

QTabBar {{
    background-color: {surface};
}}

QTabBar::tab {{
    background-color: {surface};
    color: {text_muted};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 3px 12px;
    font-size: {size_small}px;
}}

QTabBar::tab:selected {{
    color: {text};
    border-bottom: 2px solid {accent};
}}

QTabBar::tab:hover:!selected {{
    color: {text};
}}

/* ── ComboBox ─────────────────────────────────────────────────────── */

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
    selection-background-color: {primary};
    selection-color: {accent};
}}

/* ── Status bar ───────────────────────────────────────────────────── */

QStatusBar {{
    background-color: {surface};
    color: {text_muted};
    border-top: 1px solid {border};
    font-size: {size_small}px;
    padding: 0 8px;
}}

QStatusBar QLabel {{
    color: {text_muted};
    font-size: {size_small}px;
    background: transparent;
    padding: 0 4px;
}}

/* ── Dock widgets ─────────────────────────────────────────────────── */

QDockWidget {{
    background-color: {surface};
    color: {text};
    font-size: {size_base}px;
}}

QDockWidget::title {{
    background-color: {surface};
    color: {text_muted};
    padding: 3px 8px;
    font-size: {size_small}px;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid {border};
}}

/* ── PyQtAds chrome ───────────────────────────────────────────────── */

ads--CDockManager {{
    background-color: {bg};
}}

ads--CDockWidget {{
    background-color: {bg};
}}

ads--CDockWidgetTitleBar {{
    background-color: {surface};
    color: {text_muted};
    border-bottom: 1px solid {border};
    padding: 0 4px;
}}

CTitleBarButton {{
    color: {text_muted};
    background-color: transparent;
    border: none;
    padding: 2px 4px;
    font-size: {size_small}px;
}}

CTitleBarButton:hover {{
    color: {text};
    background-color: {primary};
}}

ads--CDockAreaWidget {{
    background-color: {bg};
}}

ads--CDockAreaTitleBar {{
    background-color: {surface};
    border-bottom: 1px solid {border};
    padding: 0;
    min-height: 24px;
}}

ads--CDockAreaTabBar {{
    background-color: {surface};
    border-bottom: 1px solid {border};
}}

ads--CDockWidgetTab {{
    background-color: {surface};
    color: {text_muted};
    border-top: 2px solid transparent;
    padding: 3px 10px;
    font-family: "{family}";
    font-size: {size_small}px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

ads--CDockWidgetTab QLabel {{
    background-color: transparent;
    color: {text_muted};
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: {size_small}px;
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

/* ── Banner ───────────────────────────────────────────────────────── */

QWidget#banner_widget {{
    background-color: {surface};
    border-bottom: 1px solid {border};
}}

QLabel#banner_art {{
    color: {accent};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9px;
    background: transparent;
    padding: 2px 0;
}}

QLabel#banner_meta, QLabel#banner_clock {{
    color: {text_muted};
    font-family: "{family}";
    font-size: {size_small}px;
    background: transparent;
}}
""".strip()
