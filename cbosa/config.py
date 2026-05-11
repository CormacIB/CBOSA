"""
Config loader — reads cbosa.toml from the project root and provides
typed access to app settings.
"""
import os
import toml

_DEFAULT_CONFIG = {
    "theme": "themes/dark_default.toml",
    "data_dir": "data",
}

_config: dict = {}


def load(config_path: str = "cbosa.toml") -> None:
    """Load the app config file. Falls back to defaults if not found."""
    global _config
    _config = dict(_DEFAULT_CONFIG)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = toml.load(f)
        _config.update(user_config)


def get(key: str, default=None):
    """Return a config value by key."""
    return _config.get(key, default)


# Load defaults immediately on import so callers never get an empty config.
load()
