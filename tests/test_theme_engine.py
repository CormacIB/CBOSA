"""
Tests for ThemeEngine — behaviors tested through the public interface only.
No rendering required: we assert on the QSS string content, not visual output.
"""
import pytest
from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError


VALID_TOML = """\
[colors]
background = "#1a1a2e"
surface = "#16213e"
primary = "#0f3460"
accent = "#e94560"
text = "#eaeaea"
text_muted = "#888888"
border = "#2a2a4a"

[fonts]
family = "JetBrains Mono"
size_base = 13
size_small = 11
size_heading = 16
"""


@pytest.fixture
def theme_file(tmp_path):
    f = tmp_path / "theme.toml"
    f.write_text(VALID_TOML, encoding="utf-8")
    return str(f)


# --- Tracer bullet ---

def test_load_valid_theme_contains_background_color(theme_file):
    """QSS output includes the background color from the theme file."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "#1a1a2e" in qss


# --- Remaining behaviors ---

def test_load_valid_theme_contains_accent_color(theme_file):
    """QSS output includes the accent color from the theme file."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "#e94560" in qss


def test_load_valid_theme_contains_font_family(theme_file):
    """QSS output includes the font family from the theme file."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "JetBrains Mono" in qss


def test_load_missing_file_raises_theme_load_error():
    """A missing theme file raises ThemeLoadError, not a raw FileNotFoundError."""
    engine = ThemeEngine()
    with pytest.raises(ThemeLoadError, match="not found"):
        engine.load("/nonexistent/path/theme.toml")


def test_load_theme_file_with_utf8_bom(tmp_path):
    """Theme files saved with a UTF-8 BOM (e.g. by Windows editors) load correctly."""
    bom_file = tmp_path / "bom.toml"
    bom_file.write_bytes(b"\xef\xbb\xbf" + VALID_TOML.encode("utf-8"))
    engine = ThemeEngine()
    qss = engine.load(str(bom_file))
    assert "#1a1a2e" in qss


def test_load_malformed_toml_raises_theme_load_error(tmp_path):
    """A malformed TOML file raises ThemeLoadError, not a raw parse error."""
    bad_file = tmp_path / "bad.toml"
    bad_file.write_text("this is not [ valid toml ~~~", encoding="utf-8")
    engine = ThemeEngine()
    with pytest.raises(ThemeLoadError, match="parse"):
        engine.load(str(bad_file))


# ---------------------------------------------------------------------------
# PyQtAds chrome — Issue #19
# ---------------------------------------------------------------------------

def test_qss_contains_ads_title_bar_selector(theme_file):
    """QSS output includes the PyQtAds CDockWidgetTitleBar selector (tracer bullet)."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "ads--CDockWidgetTitleBar" in qss


def test_title_bar_uses_surface_background(theme_file):
    """CDockWidgetTitleBar block uses the surface color as its background."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    title_bar_idx = qss.index("ads--CDockWidgetTitleBar")
    block_end = qss.index("}", title_bar_idx)
    title_bar_block = qss[title_bar_idx:block_end]
    assert "#16213e" in title_bar_block  # surface from VALID_TOML


def test_title_bar_uses_text_foreground(theme_file):
    """CDockWidgetTitleBar block uses the text color as its foreground."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    title_bar_idx = qss.index("ads--CDockWidgetTitleBar")
    block_end = qss.index("}", title_bar_idx)
    title_bar_block = qss[title_bar_idx:block_end]
    assert "#eaeaea" in title_bar_block  # text from VALID_TOML


def test_active_tab_uses_accent_color(theme_file):
    """Active tab selector uses accent color to be visually distinct."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    active_tab_selector = 'ads--CDockWidgetTab[activeTab="true"]'
    assert active_tab_selector in qss
    active_tab_idx = qss.index(active_tab_selector)
    block_end = qss.index("}", active_tab_idx)
    active_tab_block = qss[active_tab_idx:block_end]
    assert "#e94560" in active_tab_block  # accent from VALID_TOML


def test_tab_bar_uses_surface_background(theme_file):
    """CDockAreaTabBar uses the surface color as its background."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "ads--CDockAreaTabBar" in qss
    tab_bar_idx = qss.index("ads--CDockAreaTabBar")
    block_end = qss.index("}", tab_bar_idx)
    tab_bar_block = qss[tab_bar_idx:block_end]
    assert "#16213e" in tab_bar_block  # surface from VALID_TOML


def test_title_bar_buttons_use_text_color(theme_file):
    """CTitleBarButton is styled with the text color so buttons are visible."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "CTitleBarButton" in qss
    btn_idx = qss.index("CTitleBarButton")
    block_end = qss.index("}", btn_idx)
    btn_block = qss[btn_idx:block_end]
    assert "#eaeaea" in btn_block  # text from VALID_TOML


def test_splitter_handle_uses_border_color(theme_file):
    """CDockSplitter handle is styled with the border color so it's visible."""
    engine = ThemeEngine()
    qss = engine.load(theme_file)
    assert "ads--CDockSplitter" in qss
    splitter_idx = qss.index("ads--CDockSplitter")
    block_end = qss.index("}", splitter_idx)
    splitter_block = qss[splitter_idx:block_end]
    assert "#2a2a4a" in splitter_block  # border from VALID_TOML


def test_dark_default_theme_has_ads_chrome():
    """Loading dark_default.toml produces PyQtAds chrome selectors."""
    import pathlib
    themes_dir = pathlib.Path(__file__).parent.parent / "themes"
    engine = ThemeEngine()
    qss = engine.load(str(themes_dir / "dark_default.toml"))
    assert "ads--CDockWidgetTitleBar" in qss
    assert "ads--CDockWidgetTab" in qss
    assert "ads--CDockSplitter" in qss


def test_light_theme_has_ads_chrome():
    """Loading light.toml produces PyQtAds chrome selectors."""
    import pathlib
    themes_dir = pathlib.Path(__file__).parent.parent / "themes"
    engine = ThemeEngine()
    qss = engine.load(str(themes_dir / "light.toml"))
    assert "ads--CDockWidgetTitleBar" in qss
    assert "ads--CDockWidgetTab" in qss
    assert "ads--CDockSplitter" in qss
