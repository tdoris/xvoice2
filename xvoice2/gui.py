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
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QSystemTrayIcon, QMenu, QTextEdit, QVBoxLayout,
)

from xvoice2 import config
from xvoice2 import model_download
from xvoice2 import settings_store
from xvoice2.main import VoiceDictationApp
from xvoice2.mic_stream import list_input_devices

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

        # Microphone picker. "Automatic" (empty) lets the app auto-select;
        # otherwise the chosen device name is matched at startup (e.g. a USB mic
        # so the Bose headset can stay on hi-fi A2DP).
        self.mic = QComboBox()
        self.mic.addItem("Automatic (default)", "")
        current_mic = self._settings.get("input_device_name", "") or ""
        try:
            for _idx, name in list_input_devices():
                self.mic.addItem(name, name)
        except Exception:
            pass
        if current_mic:
            pos = self.mic.findData(current_mic)
            if pos < 0:
                # Configured device not currently connected; keep it selectable.
                self.mic.addItem(f"{current_mic} (not connected)", current_mic)
                pos = self.mic.count() - 1
            self.mic.setCurrentIndex(pos)
        form.addRow("Microphone", self.mic)

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

        self.silence_duration = QDoubleSpinBox()
        self.silence_duration.setRange(0.3, 2.0)
        self.silence_duration.setSingleStep(0.1)
        self.silence_duration.setDecimals(1)
        self.silence_duration.setSuffix(" s")
        self.silence_duration.setValue(float(self._settings.get("silence_duration", 0.7)))
        self.silence_duration.setToolTip(
            "Pause length that ends an utterance. Lower = snappier response.")
        form.addRow("End-of-speech pause", self.silence_duration)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        note = QLabel("Engine, model, microphone, and end-of-speech pause changes "
                      "take effect after restarting XVoice2.")
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
            "silence_duration": round(self.silence_duration.value(), 1),
            "input_device_name": self.mic.currentData() or "",
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


class OnboardingDialog(QDialog):
    """First-run interactive tutorial that walks the user through one dictation.

    Because dictation is injected into whatever window has focus, the tutorial's
    focused text box receives the dictated words directly, so the user sees it
    work. The dialog reacts to live state/transcription signals from the running
    dictation loop to advance its steps.
    """

    def __init__(self, bridge, *, wake_mode, wake_phrase, sleep_phrase,
                 wake_prefix, wake_enabled, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to XVoice2")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._mode = wake_mode
        self._wake = wake_phrase
        self._sleep = sleep_phrase
        self._prefix = wake_prefix
        self._wake_enabled = wake_enabled

        self._steps = self._build_steps()
        self._step = 0

        layout = QVBoxLayout(self)

        self.title = QLabel()
        font = self.title.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)

        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setMinimumHeight(64)
        layout.addWidget(self.instruction)

        self.textbox = QTextEdit()
        self.textbox.setPlaceholderText("Your dictated text will appear here...")
        self.textbox.setMinimumHeight(90)
        layout.addWidget(self.textbox)

        self.status = QLabel("Status: getting ready...")
        self.status.setStyleSheet("color: gray;")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.skip_btn = QPushButton("Skip tutorial")
        self.skip_btn.clicked.connect(self.accept)
        self.finish_btn = QPushButton("Finish")
        self.finish_btn.setEnabled(False)
        self.finish_btn.clicked.connect(self.accept)
        buttons.addWidget(self.skip_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.finish_btn)
        layout.addLayout(buttons)

        bridge.state_changed.connect(self._on_state)
        bridge.transcribed.connect(self._on_transcribed)

        self._render()
        self.textbox.setFocus()

    def _build_steps(self):
        """Ordered (kind, instruction) steps for the current wake configuration."""
        steps = []
        if self._wake_enabled and self._mode == "session":
            steps.append(("arm",
                "XVoice2 types whatever you say, but only after you turn dictation "
                f"on.\n\nSay  “{self._wake}”  out loud now to start listening."))
            steps.append(("dictate",
                "You're listening. Now say a sentence, for example "
                "“this is my first dictation”, and watch it appear in the box above."))
            steps.append(("sleep",
                f"Nicely done. To pause dictation, say  “{self._sleep}”."))
        elif self._wake_enabled and self._mode == "prefix":
            steps.append(("dictate",
                "In prefix mode you say your prefix word before each phrase.\n\n"
                f"Say  “{self._prefix} this is my first dictation”  and watch it appear above."))
        else:
            steps.append(("dictate",
                "Dictation is always on. Say a sentence and watch it appear in the box above."))
        steps.append(("done",
            "That's it! XVoice2 lives in your system tray from now on. You can "
            "change your wake words, microphone, and more in Settings.\n\nHappy dictating."))
        return steps

    def _current_kind(self):
        return self._steps[self._step][0]

    def _render(self):
        _kind, text = self._steps[self._step]
        self.instruction.setText(text)
        self.title.setText(f"Welcome to XVoice2  ({self._step + 1}/{len(self._steps)})")
        if self._current_kind() == "done":
            self.finish_btn.setEnabled(True)
            self.finish_btn.setDefault(True)
            self.skip_btn.setText("Close")

    def _advance(self):
        if self._step < len(self._steps) - 1:
            self._step += 1
            self._render()
            self.textbox.setFocus()  # keep injection landing in the box

    def _on_state(self, armed):
        self.status.setText("Status: listening" if armed else "Status: paused")
        kind = self._current_kind()
        if kind == "arm" and armed:
            self._advance()
        elif kind == "sleep" and not armed:
            self._advance()

    def _on_transcribed(self, _text):
        if self._current_kind() == "dictate":
            self._advance()


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

    # First-run interactive tutorial: walk the user through one dictation.
    if not settings.get("onboarding_completed"):
        OnboardingDialog(
            tray.bridge,
            wake_mode=getattr(config, "WAKE_MODE", "session"),
            wake_phrase=getattr(config, "WAKE_PHRASE", "start dictation"),
            sleep_phrase=getattr(config, "SLEEP_PHRASE", "stop dictation"),
            wake_prefix=getattr(config, "WAKE_PREFIX", "computer"),
            wake_enabled=getattr(config, "WAKE_WORD_ENABLED", True),
        ).exec()
        settings["onboarding_completed"] = True
        settings_store.save_settings(settings)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
