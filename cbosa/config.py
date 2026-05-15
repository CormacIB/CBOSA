"""
Config loader — reads cbosa.toml from the project root and provides
typed access to app settings.
"""
import toml
from pathlib import Path

# Project root is two levels up from this file (cbosa/config.py → project root).
PROJECT_ROOT = Path(__file__).parent.parent

_DEFAULT_CONFIG = {
    "theme": "themes/obsidian_dark.toml",
    "data_dir": "data",
    "ai": {
        "backend": "null",
        "endpoint": "http://localhost:11434",
        "model": "",
    },
}

_config: dict = {}


def load(config_path: "Path | str | None" = None) -> None:
    """Load the app config file. Falls back to defaults if not found."""
    global _config
    if config_path is None:
        config_path = PROJECT_ROOT / "cbosa.toml"
    _config = dict(_DEFAULT_CONFIG)
    if Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = toml.load(f)
        _config.update(user_config)


def get(key: str, default=None):
    """Return a config value by key."""
    return _config.get(key, default)


def resolve(key: str, default: "str | None" = None) -> Path:
    """Return a config value as an absolute Path, resolved against PROJECT_ROOT."""
    value = _config.get(key, default)
    if value is None:
        raise KeyError(key)
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p


def save_theme(path: str) -> None:
    """Persist the active theme path to cbosa.toml and update the in-memory config."""
    global _config
    _config["theme"] = path
    config_path = PROJECT_ROOT / "cbosa.toml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = toml.load(f)
    else:
        data = {}
    data["theme"] = path
    with open(config_path, "w", encoding="utf-8") as f:
        toml.dump(data, f)


def save_finance_budget(monthly_budget: float) -> None:
    """Persist monthly budget to cbosa.toml under [finance] and update in-memory config."""
    global _config
    if "finance" not in _config:
        _config["finance"] = {}
    _config["finance"]["monthly_budget"] = monthly_budget
    config_path = PROJECT_ROOT / "cbosa.toml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = toml.load(f)
    else:
        data = {}
    if "finance" not in data:
        data["finance"] = {}
    data["finance"]["monthly_budget"] = monthly_budget
    with open(config_path, "w", encoding="utf-8") as f:
        toml.dump(data, f)


# Load defaults immediately on import so callers never get an empty config.
load()
