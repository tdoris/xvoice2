#!/usr/bin/env bash
# Build the XVoice2 AppImage from the PyInstaller bundle.
#
# Prereqs: run inside the project venv with build deps installed:
#   pip install -e .[gui,parakeet] pyinstaller
# Produces: packaging/XVoice2-x86_64.AppImage
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
DIST="$HERE/dist/xvoice2"
APPDIR="$HERE/AppDir"
OUT="$HERE/XVoice2-x86_64.AppImage"

# 1. PyInstaller bundle (build if missing).
if [ ! -x "$DIST/xvoice2" ]; then
  echo ">> Building PyInstaller bundle..."
  ( cd "$ROOT" && pyinstaller --clean --noconfirm \
      --distpath "$HERE/dist" --workpath "$HERE/build" "$HERE/xvoice2.spec" )
fi

# 2. Assemble the AppDir.
echo ">> Assembling AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -a "$DIST/." "$APPDIR/usr/bin/"
install -m 0755 "$HERE/AppRun" "$APPDIR/AppRun"
cp "$HERE/xvoice2.desktop" "$APPDIR/xvoice2.desktop"
cp "$HERE/xvoice2.png" "$APPDIR/xvoice2.png"
cp "$HERE/xvoice2.png" "$APPDIR/.DirIcon"

# 3. Fetch appimagetool if needed.
TOOL="$HERE/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
  echo ">> Downloading appimagetool..."
  curl -fL -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi

# 4. Build the AppImage. APPIMAGE_EXTRACT_AND_RUN avoids needing FUSE for the
#    tool itself.
echo ">> Building AppImage..."
rm -f "$OUT"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
echo ">> Built: $OUT"
ls -lh "$OUT"
