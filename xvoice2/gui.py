"""
System-tray GUI for XVoice2 (PySide6).

Runs the dictation core (main.VoiceDictationApp) in a background daemon thread
and surfaces it as a tray icon plus a settings window, so a non-technical user
never touches the terminal. The core stays Qt-free: it exposes plain callbacks
(on_state_change / on_status / on_transcription) which this module bridges to Qt
signals, safely marshalling them from the worker thread to the GUI thread.

Tray states:
    grey  = sleeping (armed off)      green = armed (listening for dictation)
    blue  = transcribing              (transient)
"""

import sys
import threading
from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSystemTrayIcon,
    QMenu, QVBoxLayout,
)

from xvoice2 import config
from xvoice2 import model_download
from xvoice2 import settings_store
from xvoice2.main import VoiceDictationApp

# Tray icon colours per state.
_COLORS = {
    "sleeping": "#8a8a8a",
    "armed": "#2ecc71",
    "transcribing": "#3498db",
    "stopped": "#c0392b",
}

ENGINES = ["parakeet", "whisper"]
PARAKEET_MODELS = ["nemo-parakeet-tdt-0.6b-v2", "nemo-parakeet-tdt-0.6b-v3"]
WAKE_MODES = ["session", "prefix"]
DICTATION_MODES = ["general", "email", "command"]


def _make_icon(state: str) -> QIcon:
    """Render a simple coloured-dot tray icon for the given state."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(_COLORS.get(state, _COLORS["sleeping"])))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(8, 8, 48, 48)
    painter.end()
    return QIcon(pixmap)


class _Bridge(QObject):
    """Marshals core callbacks (worker thread) onto Qt signals (GUI thread)."""

    state_changed = Signal(bool)   # armed
    status_changed = Signal(str)   # "listening" | "transcribing" | "stopped"
    transcribed = Signal(str)      # injected text


class DictationController:
    """Owns the VoiceDictationApp and runs it in a daemon thread."""

    def __init__(self, bridge: _Bridge):
        self.bridge = bridge
        self.app: Optional[VoiceDictationApp] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Build the app, wire callbacks to signals, and start the loop."""
        self.app = VoiceDictationApp(mode=getattr(config, "DEFAULT_MODE", "general"))
        self.app.on_state_change = lambda armed: self.bridge.state_changed.emit(bool(armed))
        self.app.on_status = lambda status: self.bridge.status_changed.emit(str(status))
        self.app.on_transcription = lambda text: self.bridge.transcribed.emit(str(text))

        def run():
            try:
                self.app.run()
            finally:
                # run() returning means the loop ended (e.g. failed dependency
                # check); reflect that in the tray.
                self.bridge.status_changed.emit("stopped")

        self._thread = threading.Thread(target=run, daemon=True, name="xvoice2-dictation")
        self._thread.start()

    def set_armed(self, armed: bool) -> None:
        if self.app is not None:
            self.app.set_armed(armed)

    def is_armed(self) -> bool:
        return bool(self.app and self.app.wake and self.app.wake.armed)

    def apply_settings(self) -> None:
        """Re-read config into the running app's wake controller."""
        if self.app is not None:
            self.app.reload_wake_controller()

    def stop(self) -> None:
        if self.app is not None:
            self.app.running = False


class SettingsDialog(QDialog):
    """Editable settings, including the wake/sleep phrases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("XVoice2 Settings")
        self._settings = settings_store.load_settings()

        form = QFormLayout()

        self.engine = QComboBox()
        self.engine.addItems(ENGINES)
        self.engine.setCurrentText(self._settings.get("transcription_engine", "parakeet"))
        form.addRow("Transcription engine", self.engine)

        self.parakeet_model = QComboBox()
        self.parakeet_model.setEditable(True)
        self.parakeet_model.addItems(PARAKEET_MODELS)
        self.parakeet_model.setCurrentText(
            self._settings.get("parakeet_model", PARAKEET_MODELS[0]))
        form.addRow("Parakeet model", self.parakeet_model)

        self.mode = QComboBox()
        self.mode.addItems(DICTATION_MODES)
        self.mode.setCurrentText(self._settings.get("mode", "general"))
        form.addRow("Dictation mode", self.mode)

        self.wake_enabled = QCheckBox("Require a wake word before typing")
        self.wake_enabled.setChecked(bool(self._settings.get("wake_word_enabled", True)))
        form.addRow(self.wake_enabled)

        self.wake_mode = QComboBox()
        self.wake_mode.addItems(WAKE_MODES)
        self.wake_mode.setCurrentText(self._settings.get("wake_mode", "session"))
        form.addRow("Wake mode", self.wake_mode)

        self.wake_phrase = QLineEdit(self._settings.get("wake_phrase", "start dictation"))
        form.addRow("Wake phrase (start)", self.wake_phrase)

        self.sleep_phrase = QLineEdit(self._settings.get("sleep_phrase", "stop dictation"))
        form.addRow("Sleep phrase (stop)", self.sleep_phrase)

        self.wake_prefix = QLineEdit(self._settings.get("wake_prefix", "computer"))
        form.addRow("Prefix word (prefix mode)", self.wake_prefix)

        self.start_armed = QCheckBox("Start already listening")
        self.start_armed.setChecked(bool(self._settings.get("start_armed", False)))
        form.addRow(self.start_armed)

        self.notifications = QCheckBox("Desktop notification on state change")
        self.notifications.setChecked(bool(self._settings.get("wake_notifications", True)))
        form.addRow(self.notifications)

        self.trailing_space = QCheckBox("Add a space after each sentence")
        self.trailing_space.setChecked(bool(self._settings.get("append_trailing_space", True)))
        form.addRow(self.trailing_space)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        note = QLabel("Engine and model changes take effect after restarting XVoice2.")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def collect(self) -> dict:
        """Gather the form values into a settings dict."""
        return {
            "transcription_engine": self.engine.currentText(),
            "parakeet_model": self.parakeet_model.currentText().strip(),
            "mode": self.mode.currentText(),
            "wake_word_enabled": self.wake_enabled.isChecked(),
            "wake_mode": self.wake_mode.currentText(),
            "wake_phrase": self.wake_phrase.text().strip(),
            "sleep_phrase": self.sleep_phrase.text().strip(),
            "wake_prefix": self.wake_prefix.text().strip(),
            "start_armed": self.start_armed.isChecked(),
            "wake_notifications": self.notifications.isChecked(),
            "append_trailing_space": self.trailing_space.isChecked(),
        }


class ModelDownloadDialog(QDialog):
    """First-run modal that downloads the Parakeet model with progress.

    The download runs in a daemon thread; a timer polls the growing cache to
    update the bar. Falls back to an indeterminate bar if the total size can't
    be fetched (e.g. brief offline metadata failure).
    """

    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("XVoice2 — First-time setup")
        self.setModal(True)
        self.model_name = model_name
        self._total = model_download.model_total_bytes(model_name)
        self._error = None
        self._done = False

        layout = QVBoxLayout(self)
        size_txt = f"~{self._total / 1024**3:.1f} GB" if self._total else "~2.4 GB"
        info = QLabel(
            f"XVoice2 needs to download the speech recognition model "
            f"(Parakeet, {size_txt}).\nThis is a one-time download and may take "
            f"a few minutes depending on your connection.")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100) if self._total else self.bar.setRange(0, 0)
        layout.addWidget(self.bar)

        self.status = QLabel("Starting download…")
        layout.addWidget(self.status)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

        self._thread = threading.Thread(
            target=self._run, daemon=True, name="xvoice2-model-download")
        self._thread.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

    def _run(self) -> None:
        try:
            model_download.download_model(self.model_name)
        except Exception as e:  # noqa: BLE001 - surfaced to the user in _tick
            self._error = e
        finally:
            self._done = True

    def _tick(self) -> None:
        if self._done:
            self._timer.stop()
            if self._error is not None:
                QMessageBox.critical(
                    self, "Download failed",
                    f"Could not download the speech model:\n{self._error}\n\n"
                    f"Check your internet connection and try again.")
                self.reject()
            else:
                self.bar.setRange(0, 100)
                self.bar.setValue(100)
                self.accept()
            return
        got = model_download.cache_bytes_on_disk(self.model_name)
        mb = got // (1024 * 1024)
        if self._total:
            self.bar.setValue(min(99, int(got / self._total * 100)))
            self.status.setText(f"Downloaded {mb} / {self._total // (1024 * 1024)} MB")
        else:
            self.status.setText(f"Downloaded {mb} MB…")


class TrayApp:
    """The tray icon, its menu, and the wiring to the dictation controller."""

    def __init__(self, app: QApplication):
        self.qapp = app
        self.bridge = _Bridge()
        self.controller = DictationController(self.bridge)
        self._armed = False

        self.tray = QSystemTrayIcon(_make_icon("sleeping"))
        self.tray.setToolTip("XVoice2 — sleeping")

        # Keep references (and parent the actions to the menu) so PySide6 does
        # not garbage-collect them out of the menu.
        self.menu = QMenu()
        self.toggle_action = QAction("Start dictation", self.menu)
        self.toggle_action.triggered.connect(self._toggle)
        self.menu.addAction(self.toggle_action)
        self.menu.addSeparator()
        self.settings_action = QAction("Settings…", self.menu)
        self.settings_action.triggered.connect(self._open_settings)
        self.menu.addAction(self.settings_action)
        self.quit_action = QAction("Quit", self.menu)
        self.quit_action.triggered.connect(self._quit)
        self.menu.addAction(self.quit_action)
        self.tray.setContextMenu(self.menu)

        self.bridge.state_changed.connect(self._on_state)
        self.bridge.status_changed.connect(self._on_status)

    def start(self) -> None:
        self.tray.show()
        self.controller.start()

    def _toggle(self) -> None:
        self.controller.set_armed(not self._armed)

    def _on_state(self, armed: bool) -> None:
        self._armed = armed
        self.tray.setIcon(_make_icon("armed" if armed else "sleeping"))
        self.tray.setToolTip("XVoice2 — " + ("listening" if armed else "sleeping"))
        self.toggle_action.setText("Pause dictation" if armed else "Start dictation")

    def _on_status(self, status: str) -> None:
        if status == "transcribing":
            self.tray.setIcon(_make_icon("transcribing"))
            self.tray.setToolTip("XVoice2 — transcribing…")
        elif status == "stopped":
            self.tray.setIcon(_make_icon("stopped"))
            self.tray.setToolTip("XVoice2 — stopped (check settings/dependencies)")
        else:  # listening/idle -> reflect current armed state
            self._on_state(self._armed)

    def _open_settings(self) -> None:
        dialog = SettingsDialog()
        if dialog.exec() == QDialog.Accepted:
            new = dialog.collect()
            settings_store.save_settings(new)
            settings_store.apply_to_config(new)
            self.controller.apply_settings()

    def _quit(self) -> None:
        self.controller.stop()
        self.tray.hide()
        self.qapp.quit()


def main() -> int:
    """Entry point for the ``xvoice2-gui`` console script."""
    # Make logs visible when stdout is redirected (e.g. the packaged app), so
    # troubleshooting output isn't stuck in a buffer.
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None:
                stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            pass

    # Load persisted settings before constructing the core.
    settings = settings_store.load_settings()
    # The packaged (frozen) app bundles only the Parakeet engine, so default to
    # it regardless of any inherited config.
    if getattr(sys, "frozen", False):
        settings["transcription_engine"] = "parakeet"
    settings_store.apply_to_config(settings)

    app = QApplication(sys.argv)
    app.setApplicationName("XVoice2")
    app.setQuitOnLastWindowClosed(False)  # live in the tray, not a window

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "XVoice2",
                             "No system tray is available on this desktop.")
        return 1

    # First run: make sure the Parakeet model is downloaded before starting,
    # with a visible progress dialog instead of a silent multi-minute stall.
    engine = getattr(config, "TRANSCRIPTION_ENGINE", "parakeet")
    if engine == "parakeet":
        model = getattr(config, "PARAKEET_MODEL", "nemo-parakeet-tdt-0.6b-v2")
        if not model_download.is_model_cached(model):
            if ModelDownloadDialog(model).exec() != QDialog.Accepted:
                return 1  # download cancelled or failed

    tray = TrayApp(app)
    tray.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
