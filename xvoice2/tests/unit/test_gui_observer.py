"""
Tests for the GUI observer hooks on VoiceDictationApp and a guarded PySide6
smoke test of the tray/settings wiring.
"""

import os
from unittest.mock import patch

import pytest

from xvoice2.main import VoiceDictationApp


def _make_app():
    """Build an app with wake gating on and notifications off (no subprocess)."""
    with patch("xvoice2.config.WAKE_WORD_ENABLED", True), \
         patch("xvoice2.config.WAKE_NOTIFICATIONS", False):
        return VoiceDictationApp(mode="general")


class TestObserverHooks:
    def test_set_armed_fires_state_change_once_per_change(self):
        app = _make_app()
        events = []
        app.on_state_change = events.append
        app.set_armed(True)
        app.set_armed(True)   # no change -> no new event
        app.set_armed(False)
        assert events == [True, False]

    def test_reload_wake_controller_applies_new_phrase(self):
        app = _make_app()
        with patch("xvoice2.config.WAKE_PHRASE", "new wake phrase"):
            app.reload_wake_controller()
        assert app.wake.wake_phrase == "new wake phrase"

    def test_reload_can_disable_wake(self):
        app = _make_app()
        with patch("xvoice2.config.WAKE_WORD_ENABLED", False):
            app.reload_wake_controller()
        assert app.wake is None

    def test_set_armed_noop_without_wake(self):
        with patch("xvoice2.config.WAKE_WORD_ENABLED", False):
            app = VoiceDictationApp(mode="general")
        assert app.wake is None
        app.set_armed(True)  # must not raise


# --- Guarded GUI smoke test (skips if PySide6 unavailable) ---

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402
from xvoice2 import gui  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestGuiWiring:
    def test_icons_render(self, qapp):
        for state in ["sleeping", "armed", "transcribing", "stopped"]:
            assert not gui._make_icon(state).isNull()

    def test_settings_dialog_collects_wake_phrases(self, qapp, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        dlg = gui.SettingsDialog()
        dlg.wake_phrase.setText("hey xvoice")
        dlg.sleep_phrase.setText("goodnight")
        dlg.silence_duration.setValue(0.5)
        collected = dlg.collect()
        assert collected["wake_phrase"] == "hey xvoice"
        assert collected["sleep_phrase"] == "goodnight"
        assert collected["silence_duration"] == 0.5
        # Microphone defaults to automatic (empty) and is always collected.
        assert collected["input_device_name"] == ""
        assert "input_device_name" in collected

    def test_tray_state_transitions(self, qapp):
        tray = gui.TrayApp(qapp)
        tray._on_state(True)
        assert tray._armed is True
        assert tray.toggle_action.text() == "Pause dictation"
        tray._on_state(False)
        assert tray._armed is False
        assert tray.toggle_action.text() == "Start dictation"

    def test_tray_menu_has_all_actions(self, qapp):
        """Regression: Settings/Quit actions must not be GC'd out of the menu."""
        tray = gui.TrayApp(qapp)
        labels = [a.text() for a in tray.menu.actions() if not a.isSeparator()]
        assert "Settings…" in labels
        assert "Quit" in labels
        assert "Start dictation" in labels


class TestModelDownloadDialog:
    def test_completes_and_accepts(self, qapp):
        from PySide6.QtWidgets import QDialog
        with patch("xvoice2.model_download.model_total_bytes", return_value=1000), \
             patch("xvoice2.model_download.download_model") as dl, \
             patch("xvoice2.model_download.cache_bytes_on_disk", return_value=1000):
            dlg = gui.ModelDownloadDialog("nemo-parakeet-tdt-0.6b-v2")
            dlg._thread.join(timeout=3)
            dlg._tick()  # sees _done, no error -> accept
            assert dlg.result() == QDialog.Accepted
            dl.assert_called_once()

    def test_reports_error_and_rejects(self, qapp):
        from PySide6.QtWidgets import QDialog
        with patch("xvoice2.model_download.model_total_bytes", return_value=0), \
             patch("xvoice2.model_download.download_model",
                   side_effect=RuntimeError("no network")), \
             patch("xvoice2.model_download.cache_bytes_on_disk", return_value=0), \
             patch.object(gui.QMessageBox, "critical", return_value=None):
            dlg = gui.ModelDownloadDialog("nemo-parakeet-tdt-0.6b-v2")
            dlg._thread.join(timeout=3)
            dlg._tick()  # sees _done + error -> reject
            assert dlg.result() == QDialog.Rejected
