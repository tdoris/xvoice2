# XVoice2

**[Homepage and downloads →](https://tdoris.github.io/xvoice2/)**

**Offline voice dictation for Linux and macOS.** Speak, and your words are typed
into whatever application has focus: a terminal, an editor, a browser, or a
remote desktop session. Runs a system-tray app with a friendly settings window,
or a headless CLI. All transcription happens locally; nothing is sent to the
cloud by default.

XVoice2 grew out of a tool for people who can't easily type. It keeps that
spirit: **fully hands-free**. The microphone is always on and dictation is gated
behind a spoken **wake word**, so there is no key to press.

## Highlights

- **Always-on mic with a configurable wake word.** Say your wake phrase to
  start, your sleep phrase to pause. No hotkey.
- **Works over remote desktop (RDP/VNC),** because there's no global hotkey to
  be swallowed by the client, and text is injected into the focused window.
- **NVIDIA Parakeet transcription** (local, via ONNX Runtime): accurate,
  punctuated, capitalized text, and no "thank you"-style hallucinations on
  silence. whisper.cpp and the OpenAI Whisper API are also supported.
- **System-tray GUI** with a settings window (engine, microphone, wake phrases,
  responsiveness), plus a full CLI.
- **Single-file AppImage:** a double-click install for non-technical users, with
  a first-run model-download screen.
- **Private by default.** Local inference; the only optional cloud paths (OpenAI
  Whisper / LLM cleanup) are off unless you enable them.

## Quick start

### Option A: AppImage (recommended for most users)

A self-contained, double-click app. Build it once (see
[packaging/README.md](packaging/README.md)):

```bash
pip install -e .[gui,parakeet] pyinstaller
bash packaging/build_appimage.sh
# -> packaging/XVoice2-x86_64.AppImage
```

Then just run it; it lives in your system tray. On first launch it downloads the
speech model (~2.4 GB, one time) with a progress dialog.

> Linux note: the Qt tray needs `libxcb-cursor0`
> (`sudo apt install libxcb-cursor0`), and text injection needs `wtype`
> (Wayland) or `xdotool` (X11).

### Option B: from source

```bash
git clone https://github.com/tdoris/xvoice2.git
cd xvoice2

# System deps (Debian/Ubuntu): PortAudio + a text-injection tool
sudo apt-get install portaudio19-dev python3-dev wtype xdotool libxcb-cursor0

# Install XVoice2 with the Parakeet engine and the tray GUI
pip install -e .[gui,parakeet]

# Run the tray app...
xvoice2-gui
# ...or the CLI
xvoice2 --engine parakeet
```

On macOS, install PortAudio with `brew install portaudio`, and grant
**Accessibility** permission (System Settings → Privacy & Security →
Accessibility) so text injection works.

## Transcription engines

Select with `--engine` (CLI), the Settings window (GUI), or `TRANSCRIPTION_ENGINE`
in config.

- **`parakeet`** *(recommended):* NVIDIA Parakeet via
  [onnx-asr](https://github.com/istupakov/onnx-asr), fully local on ONNX Runtime.
  Being a transducer, it doesn't hallucinate stock phrases on silence/noise, and
  it emits punctuated, capitalized text. The model downloads on first use and is
  cached; inference is well under real-time on CPU. The AppImage ships this
  engine. Multilingual variant: `--parakeet-model nemo-parakeet-tdt-0.6b-v3`.
- **`whisper`:** local `whisper.cpp` (build separately and set `WHISPER_ROOT`),
  or the OpenAI Whisper API with `--use-whisper-api`.

```bash
pip install -e .[parakeet]     # onnx-asr + onnxruntime + huggingface_hub
xvoice2 --engine parakeet
```

## Wake-word activation

The mic is always on, but text is only typed while dictation is **armed**.
Because nothing depends on a global hotkey, this is what makes XVoice2 work over
**remote desktop**: your local mic is transcribed locally, and the text is
injected into the focused window, including an RDP/VNC client.

Two interaction models (`WAKE_MODE`, or `--wake-mode`):

- **`session`** *(default):* say the wake phrase to start typing, the sleep
  phrase to pause. Everything between is typed. Best for continuous dictation.
- **`prefix`:** say a short prefix word before each phrase you want typed. No
  persistent state.

```bash
xvoice2                       # say "start dictation" ... "stop dictation"
xvoice2 --start-armed         # begin already listening
xvoice2 --wake-mode prefix    # say "computer <your text>" each time
xvoice2 --no-wake-word        # type everything heard (no gating)
```

Wake/sleep phrases are **editable in the GUI Settings window** (or via
`WAKE_PHRASE` / `SLEEP_PHRASE` / `WAKE_PREFIX` in config).

## Desktop app (system-tray GUI)

```bash
pip install -e .[gui]
xvoice2-gui
```

A tray icon shows the state (grey = sleeping, green = listening, blue =
transcribing) with a menu to **Start/Pause dictation**, open **Settings...**, or
**Quit**. The Settings window configures:

- Transcription **engine** and model
- **Microphone** device (pick a USB mic so a Bluetooth headset can stay on hi-fi
  audio); see below
- **Wake / sleep phrases** and mode
- **End-of-speech pause** (responsiveness) and other toggles

Settings are saved to `~/.config/xvoice2/settings.json`, shared with the CLI.

### Microphone selection

Settings → **Microphone** lists your input devices. A plugged-in USB mic appears
directly; select it and it's used for dictation. This lets a Bluetooth headset
(e.g. Bose QC35) stay on high-quality A2DP output instead of switching to the
low-quality headset profile just to expose its mic.

## CLI reference

```bash
xvoice2 --engine parakeet        # choose engine (whisper | parakeet)
xvoice2 --mode email             # dictation mode (general | email | command)
xvoice2 --wake-mode prefix       # wake interaction model
xvoice2 --start-armed            # skip the initial wake phrase
xvoice2 --no-wake-word           # disable wake gating
xvoice2 --use-llm                # OpenAI LLM grammar/punctuation cleanup
xvoice2 --use-local-llm          # local Ollama cleanup instead
xvoice2 --list-models            # list installed whisper models
python -m xvoice2 --help         # full help
```

## Configuration

Defaults live in `xvoice2/config.py`. For machine-specific overrides (kept out
of git), create `xvoice2/config_local.py`:

```bash
cp xvoice2/config_local.py.example xvoice2/config_local.py
```

The GUI writes user settings to `~/.config/xvoice2/settings.json` instead, so you
rarely need to touch config files by hand. Notable settings: `TRANSCRIPTION_ENGINE`,
`PARAKEET_MODEL`, wake phrases, `SILENCE_DURATION` (end-of-speech pause),
`INPUT_DEVICE_NAME` (microphone), and the optional LLM cleanup.

## How it works

```
mic (PortAudio) → voice-activity detection → wake-word gate → transcription
   (Parakeet / whisper.cpp / API) → optional LLM cleanup → inject into focused
   window (wtype / xdotool / AppleScript)
```

The voice-activity detector rejects non-speech (keyboard clicks, silence) using
amplitude, duration, and a zero-crossing "voicing" check, so stray sounds aren't
transcribed. Whole-utterance Whisper hallucinations are filtered as a backstop.

## Development

```bash
pip install -e .[test]
pytest                             # full suite
QT_QPA_PLATFORM=offscreen pytest   # if running GUI tests headless
```

Building the distributable AppImage is documented in
[packaging/README.md](packaging/README.md).

## Project structure

```
xvoice2/
├── xvoice2/
│   ├── main.py              # app orchestration + CLI
│   ├── gui.py               # PySide6 tray app, settings, download dialog
│   ├── mic_stream.py        # microphone capture + VAD + device enumeration
│   ├── transcriber.py       # engine dispatch (whisper.cpp / API / Parakeet)
│   ├── parakeet_backend.py  # Parakeet via onnx-asr
│   ├── model_download.py    # first-run model download helpers
│   ├── wake_word.py         # wake/sleep-phrase gating
│   ├── text_injector.py     # wtype / xdotool / AppleScript injection
│   ├── formatter.py         # optional LLM cleanup (OpenAI / Ollama)
│   ├── settings_store.py    # ~/.config/xvoice2/settings.json
│   ├── notifier.py          # desktop notifications
│   ├── config.py            # defaults (+ config_local.py overrides)
│   └── tests/               # unit + integration tests
├── packaging/               # PyInstaller spec + AppImage build
├── setup.py / pyproject.toml
└── README.md
```

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for platform-specific issues. On
Linux, remember the runtime bits: `libxcb-cursor0` (Qt tray) and `wtype` /
`xdotool` (text injection).

## License

MIT
