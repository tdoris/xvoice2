# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the XVoice2 tray GUI (Parakeet engine)."""

import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(SPECPATH)  # repo root (spec lives in packaging/)

datas = []
binaries = []
hiddenimports = ["pyaudio"]

# Collect packages that ship data/plugins or import lazily.
for pkg in ("onnx_asr", "onnxruntime", "huggingface_hub", "xvoice2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Never ship the developer's machine-specific config_local.py (it hardcodes
# local paths); the frozen app defaults to Parakeet on its own.
datas = [(src, dest) for (src, dest) in datas
         if os.path.basename(src) != "config_local.py"]

# Bundle system shared libraries that PyInstaller won't pick up on its own.
for lib in (
    "/usr/lib/x86_64-linux-gnu/libportaudio.so.2",
    "/lib/x86_64-linux-gnu/libportaudio.so.2",
    "/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0",
):
    if os.path.exists(lib):
        binaries.append((lib, "."))

a = Analysis(
    [os.path.join(ROOT, "xvoice2", "gui.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Exclude heavy, unused packages (torch/CUDA from earlier experiments,
    # plotting, tk) to keep the bundle small.
    excludes=[
        "torch", "triton", "numba", "llvmlite", "matplotlib", "tkinter",
        "scipy", "pandas", "IPython", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="xvoice2",
    debug=False,
    strip=False,
    upx=False,
    console=True,  # keep a console during bring-up so errors are visible
    icon=os.path.join(ROOT, "packaging", "xvoice2.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="xvoice2",
)
