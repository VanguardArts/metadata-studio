#!/usr/bin/env bash
# Uninstall Metadata Studio (portable install only — matches install.sh).
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"

rm -rf "$PREFIX/lib/metadata-studio"
rm -f \
  "$PREFIX/bin/metadata-studio" \
  "$PREFIX/bin/metadata-studio-gui" \
  "$PREFIX/share/applications/metadata-studio.desktop" \
  "$PREFIX/share/icons/hicolor/scalable/apps/metadata-studio.svg"

for sz in 16 24 32 48 64 96 128 256 512; do
    rm -f "$PREFIX/share/icons/hicolor/${sz}x${sz}/apps/metadata-studio.png"
done

# remove the autostart entry if present
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/metadata-studio.desktop"

command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true

echo "✔ Metadata Studio uninstalled from $PREFIX"
