#!/usr/bin/env bash
# Uninstall Metascrub (portable install only — matches install.sh).
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"

rm -rf "$PREFIX/lib/metascrub"
rm -f \
  "$PREFIX/bin/metascrub" \
  "$PREFIX/bin/metascrub-gui" \
  "$PREFIX/share/applications/metascrub.desktop" \
  "$PREFIX/share/icons/hicolor/scalable/apps/metascrub.svg"

for sz in 16 24 32 48 64 96 128 256 512; do
    rm -f "$PREFIX/share/icons/hicolor/${sz}x${sz}/apps/metascrub.png"
done

# remove the autostart entry if present
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/metascrub.desktop"

command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true

echo "✔ Metascrub uninstalled from $PREFIX"
