#!/usr/bin/env bash
# Disable Metascrub autostart-at-login.
set -euo pipefail

AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
rm -f "$AUTOSTART/metascrub.desktop"
echo "✔ Autostart disabled"
