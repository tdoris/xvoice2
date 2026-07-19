"""
User settings persistence for the XVoice2 GUI.

Settings live in a JSON file under the user's config directory
(``~/.config/xvoice2/settings.json``) so the GUI and the app share one source of
truth instead of hand-editing ``config_local.py``. Loaded values are applied
over the ``config`` module at startup, the same override mechanism
``config_local`` uses.
"""

import json
import os
from typing import Any, Dict

from xvoice2 import config
from xvoice2.logging_util import debug_log

# Map user-facing setting keys to config module attribute names. These are the
# settings the GUI exposes and persists.
SETTING_TO_CONFIG = {
    "transcription_engine": "TRANSCRIPTION_ENGINE",
    "parakeet_model": "PARAKEET_MODEL",
    "whisper_model": "WHISPER_MODEL",
    "mode": "DEFAULT_MODE",
    "wake_word_enabled": "WAKE_WORD_ENABLED",
    "wake_mode": "WAKE_MODE",
    "wake_phrase": "WAKE_PHRASE",
    "sleep_phrase": "SLEEP_PHRASE",
    "wake_prefix": "WAKE_PREFIX",
    "start_armed": "START_ARMED",
    "wake_notifications": "WAKE_NOTIFICATIONS",
    "append_trailing_space": "APPEND_TRAILING_SPACE",
    "silence_duration": "SILENCE_DURATION",
}


def settings_dir() -> str:
    """Directory holding the settings file (respects XDG_CONFIG_HOME)."""
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "xvoice2")


def settings_path() -> str:
    """Full path to the settings JSON file."""
    return os.path.join(settings_dir(), "settings.json")


def defaults() -> Dict[str, Any]:
    """Default settings derived from the config module's current values."""
    return {key: getattr(config, attr, None) for key, attr in SETTING_TO_CONFIG.items()}


def load_settings() -> Dict[str, Any]:
    """Load settings merged over defaults.

    A missing or corrupt file yields the defaults, so the GUI always has a
    complete, valid settings dict to work with.
    """
    result = defaults()
    path = settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                for key in SETTING_TO_CONFIG:
                    if key in stored:
                        result[key] = stored[key]
        except (OSError, json.JSONDecodeError) as e:
            debug_log(f"Could not read settings ({e}); using defaults")
    return result


def save_settings(settings: Dict[str, Any]) -> None:
    """Persist the known settings keys to the JSON file (creating the dir)."""
    os.makedirs(settings_dir(), exist_ok=True)
    filtered = {k: settings[k] for k in SETTING_TO_CONFIG if k in settings}
    with open(settings_path(), "w", encoding="utf-8") as fh:
        json.dump(filtered, fh, indent=2)


def apply_to_config(settings: Dict[str, Any]) -> None:
    """Apply settings onto the config module (like config_local overrides)."""
    for key, attr in SETTING_TO_CONFIG.items():
        if key in settings and settings[key] is not None:
            setattr(config, attr, settings[key])
