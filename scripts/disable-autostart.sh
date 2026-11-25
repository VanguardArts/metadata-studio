#!/usr/bin/env bash
# Disable Metadata Studio autostart-at-login.
set -euo pipefail

AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
rm -f "$AUTOSTART/metadata-studio.desktop"
echo "✔ Autostart disabled"
