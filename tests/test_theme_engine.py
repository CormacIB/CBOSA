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
