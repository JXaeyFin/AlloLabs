#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SYSTEM="$(uname -s)"
MACHINE="$(uname -m)"
case "$MACHINE" in
  arm64|aarch64) ARCH="arm64" ;;
  x86_64|amd64) ARCH="x64" ;;
  *) echo "Unsupported architecture: $MACHINE" >&2; exit 1 ;;
esac

case "$SYSTEM" in
  Darwin)
    PLATFORM="macOS"
    VERIFY_PLATFORM="macos"
    REQUIREMENTS="requirements-desktop-macos.txt"
    ;;
  Linux)
    PLATFORM="Linux"
    VERIFY_PLATFORM="linux"
    REQUIREMENTS="requirements-desktop-linux.txt"
    ;;
  *)
    echo "This script builds macOS or Linux portable releases." >&2
    exit 1
    ;;
esac

VENV="$ROOT/.desktop-build-${PLATFORM}-${ARCH}"
PYTHON="$VENV/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV"
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$REQUIREMENTS"

rm -rf "$ROOT/build" "$ROOT/dist/AlloLabs" "$ROOT/dist/AlloLabsBundle" \
  "$ROOT/dist/AlloLabs.app"
"$PYTHON" -m PyInstaller --noconfirm --clean "$ROOT/packaging/allolabs.spec"

TARGET="$ROOT/dist/AlloLabs-${PLATFORM}-${ARCH}"
rm -rf "$TARGET"
mkdir -p "$TARGET"
if [[ "$PLATFORM" == "macOS" ]]; then
  mv "$ROOT/dist/AlloLabs.app" "$TARGET/AlloLabs.app"
  rm -rf "$ROOT/dist/AlloLabsBundle"
  codesign --force --deep --sign - "$TARGET/AlloLabs.app"
else
  shopt -s dotglob
  mv "$ROOT/dist/AlloLabs/"* "$TARGET/"
  rmdir "$ROOT/dist/AlloLabs"
  chmod +x "$TARGET/AlloLabs" "$TARGET/AlloLabsWorker"
fi
cp "$ROOT/packaging/PORTABLE_README.md" "$TARGET/README.md"

"$PYTHON" "$ROOT/scripts/verify-portable.py" \
  "$TARGET" --platform "$VERIFY_PLATFORM"

if [[ "$PLATFORM" == "macOS" ]]; then
  ditto -c -k --sequesterRsrc --keepParent \
    "$TARGET" "$ROOT/dist/AlloLabs-v1.3.1-${PLATFORM}-${ARCH}.zip"
else
  tar -C "$ROOT/dist" -czf \
    "$ROOT/dist/AlloLabs-v1.3.1-${PLATFORM}-${ARCH}.tar.gz" \
    "AlloLabs-${PLATFORM}-${ARCH}"
fi

echo "Portable release created under dist/AlloLabs-${PLATFORM}-${ARCH}"
