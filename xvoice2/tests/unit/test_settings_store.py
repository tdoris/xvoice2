"""
Unit tests for settings_store (JSON-backed GUI settings).
"""

import json
import os

import pytest

from xvoice2 import config, settings_store


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Point the settings dir at a temp location."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def restore_config():
    """Restore config attributes mutated by apply_to_config tests."""
    saved = {attr: getattr(config, attr, None)
             for attr in settings_store.SETTING_TO_CONFIG.values()}
    yield
    for attr, val in saved.items():
        setattr(config, attr, val)


class TestSettingsStore:
    def test_defaults_when_no_file(self, tmp_config):
        d = settings_store.load_settings()
        assert set(d) == set(settings_store.SETTING_TO_CONFIG)
        assert d["wake_phrase"] == config.WAKE_PHRASE

    def test_save_and_load_roundtrip(self, tmp_config):
        s = settings_store.load_settings()
        s["wake_phrase"] = "hello there"
        s["transcription_engine"] = "parakeet"
        settings_store.save_settings(s)
        assert os.path.exists(settings_store.settings_path())
        loaded = settings_store.load_settings()
        assert loaded["wake_phrase"] == "hello there"
        assert loaded["transcription_engine"] == "parakeet"

    def test_corrupt_file_falls_back_to_defaults(self, tmp_config):
        os.makedirs(settings_store.settings_dir(), exist_ok=True)
        with open(settings_store.settings_path(), "w") as f:
            f.write("{ this is not json")
        d = settings_store.load_settings()
        assert d["wake_phrase"] == config.WAKE_PHRASE

    def test_unknown_keys_not_persisted(self, tmp_config):
        s = settings_store.load_settings()
        s["evil"] = "x"
        settings_store.save_settings(s)
        with open(settings_store.settings_path()) as f:
            raw = json.load(f)
        assert "evil" not in raw

    def test_unknown_keys_ignored_on_load(self, tmp_config):
        os.makedirs(settings_store.settings_dir(), exist_ok=True)
        with open(settings_store.settings_path(), "w") as f:
            json.dump({"wake_phrase": "x", "bogus": 1}, f)
        d = settings_store.load_settings()
        assert d["wake_phrase"] == "x"
        assert "bogus" not in d

    def test_apply_to_config(self, tmp_config):
        settings_store.apply_to_config({
            "wake_phrase": "abracadabra",
            "transcription_engine": "parakeet",
        })
        assert config.WAKE_PHRASE == "abracadabra"
        assert config.TRANSCRIPTION_ENGINE == "parakeet"

    def test_apply_ignores_none_values(self, tmp_config):
        original = config.WAKE_PHRASE
        settings_store.apply_to_config({"wake_phrase": None})
        assert config.WAKE_PHRASE == original
