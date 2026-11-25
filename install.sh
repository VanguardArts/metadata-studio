#!/usr/bin/env bash
# Portable install for Metadata Studio (no root — installs to $PREFIX).
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"
APPS="$PREFIX/share/applications"
ICONS="$PREFIX/share/icons/hicolor"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIBDIR="$PREFIX/lib/metadata-studio"

AUTOSTART=0
for arg in "$@"; do
    case "$arg" in
        --autostart|-a) AUTOSTART=1 ;;
    esac
done

mkdir -p "$BIN" "$APPS" "$ICONS/scalable/apps" "$LIBDIR"

rm -rf "$LIBDIR/metadata_studio"
cp -r "$SRC_DIR/src/metadata_studio" "$LIBDIR/metadata_studio"
cp "$SRC_DIR/packaging/cli_main.py" "$SRC_DIR/packaging/gui_main.py" "$LIBDIR/"

printf '#!/bin/sh\nexec python3 "%s/cli_main.py" "$@"\n' "$LIBDIR" > "$BIN/metadata-studio"
printf '#!/bin/sh\nexec python3 "%s/gui_main.py" "$@"\n' "$LIBDIR" > "$BIN/metadata-studio-gui"
chmod 755 "$BIN/metadata-studio" "$BIN/metadata-studio-gui"

install -m 644 "$SRC_DIR/packaging/metadata-studio.desktop" "$APPS/metadata-studio.desktop"
install -m 644 "$SRC_DIR/packaging/metadata-studio.svg" "$ICONS/scalable/apps/metadata-studio.svg"
for sz in 16 24 32 48 64 96 128 256 512; do
    install -Dm 644 "$SRC_DIR/packaging/icons/hicolor/${sz}x${sz}/apps/metadata-studio.png" \
        "$ICONS/${sz}x${sz}/apps/metadata-studio.png"
done

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true

if [ "$AUTOSTART" = "1" ]; then
    bash "$SRC_DIR/scripts/enable-autostart.sh"
fi

echo "✔ Metadata Studio installed to $PREFIX"
echo "  CLI:  metadata-studio"
echo "  GUI:  metadata-studio-gui"
