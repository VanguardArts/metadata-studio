#!/usr/bin/env bash
# Enable Metadata Studio to start automatically at login (XDG autostart).
set -euo pipefail

BIN="$(command -v metadata-studio-gui 2>/dev/null || true)"
if [ -z "$BIN" ]; then
    BIN="$HOME/.local/bin/metadata-studio-gui"
fi
if [ ! -x "$BIN" ]; then
    echo "error: metadata-studio-gui not found (run ./install.sh first)" >&2
    exit 1
fi

AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$AUTOSTART"

cat > "$AUTOSTART/metadata-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Metadata Studio
Comment=Inspect and strip metadata from images, audio and documents
Exec=$BIN
Icon=metadata-studio
Terminal=false
Categories=Utility;AudioVideo;Audio;Graphics;
X-GNOME-Autostart-enabled=true
EOF

echo "✔ Metadata Studio will start automatically at login"
echo "  wrote: $AUTOSTART/metadata-studio.desktop"
