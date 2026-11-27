#!/usr/bin/env bash
# Enable Metascrub to start automatically at login (XDG autostart).
set -euo pipefail

BIN="$(command -v metascrub-gui 2>/dev/null || true)"
if [ -z "$BIN" ]; then
    BIN="$HOME/.local/bin/metascrub-gui"
fi
if [ ! -x "$BIN" ]; then
    echo "error: metascrub-gui not found (run ./install.sh first)" >&2
    exit 1
fi

AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$AUTOSTART"

cat > "$AUTOSTART/metascrub.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Metascrub
Comment=Inspect and strip metadata from images, audio and documents
Exec=$BIN
Icon=metascrub
Terminal=false
Categories=Utility;AudioVideo;Audio;Graphics;
X-GNOME-Autostart-enabled=true
EOF

echo "✔ Metascrub will start automatically at login"
echo "  wrote: $AUTOSTART/metascrub.desktop"
