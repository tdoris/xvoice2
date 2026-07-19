# Packaging XVoice2 as an AppImage

Builds a single, double-click `XVoice2-x86_64.AppImage` (Parakeet engine, tray
GUI) for non-technical Linux users.

## Build

From the project root, inside the venv with build deps installed:

```bash
pip install -e .[gui,parakeet]
pip install pyinstaller
bash packaging/build_appimage.sh
```

Output: `packaging/XVoice2-x86_64.AppImage`.

The script:
1. Freezes the app with PyInstaller (`xvoice2.spec`) → `packaging/dist/xvoice2/`.
2. Assembles an `AppDir` (bundle + `AppRun` + `.desktop` + icon).
3. Downloads `appimagetool` (cached) and builds the AppImage.

## What's bundled / not bundled

- **Bundled:** Python, PySide6 (Qt), onnxruntime, onnx-asr, PortAudio, and the
  `libxcb-cursor` Qt dependency. `torch`/CUDA are explicitly excluded.
- **Not bundled:** the Parakeet model (~600 MB) — it downloads on first run to
  `~/.cache/huggingface` (needs internet once, offline thereafter), and the
  developer's `config_local.py` (the frozen app ignores it and defaults to
  Parakeet).

## Runtime requirements on the target machine

- A **system tray** (most desktops; GNOME needs an AppIndicator extension).
- For **text injection**: `wtype` (Wayland) or `xdotool` (X11) — invoked via
  subprocess, not bundled. The app warns if missing.
- Internet access on first launch to fetch the model.

## Notes

- `console=True` in the spec keeps a terminal for troubleshooting during
  bring-up. Flip to `False` for a windowless release build.
- The AppImage is built and tested on Ubuntu; other glibc versions may vary.
