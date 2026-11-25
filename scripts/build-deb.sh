#!/usr/bin/env bash
# Build a Debian/Ubuntu .deb package for Metadata Studio.
#
# This is a pure-Python package, so we vendor the source tree at
# /usr/lib/metadata-studio and install thin launcher shell scripts, exactly
# like metascrub. Output: build/deb/metadata-studio_<version>_all.deb
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.1.0"
PKG="metadata-studio"
STAGE="$ROOT/build/deb/${PKG}_${VERSION}_all"
DEBIAN="$STAGE/DEBIAN"

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "error: dpkg-deb not found (install 'dpkg' / 'dpkg-dev')" >&2
    exit 1
}

rm -rf "$STAGE"
mkdir -p \
    "$STAGE/usr/bin" \
    "$STAGE/usr/lib/$PKG" \
    "$STAGE/usr/share/applications" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps" \
    "$STAGE/usr/share/doc/$PKG" \
    "$DEBIAN"

# vendor the Python package
cp -r "$ROOT/src/metadata_studio" "$STAGE/usr/lib/$PKG/metadata_studio"
cp "$ROOT/packaging/cli_main.py" "$ROOT/packaging/gui_main.py" "$STAGE/usr/lib/$PKG/"

# launcher scripts
printf '#!/bin/sh\nexec python3 /usr/lib/%s/cli_main.py "$@"\n' "$PKG" > "$STAGE/usr/bin/$PKG"
printf '#!/bin/sh\nexec python3 /usr/lib/%s/gui_main.py "$@"\n' "$PKG" > "$STAGE/usr/bin/$PKG-gui"
chmod 755 "$STAGE/usr/bin/$PKG" "$STAGE/usr/bin/$PKG-gui"

install -m 0644 "$ROOT/packaging/$PKG.desktop" "$STAGE/usr/share/applications/$PKG.desktop"
install -m 0644 "$ROOT/packaging/$PKG.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/$PKG.svg"
for sz in 16 24 32 48 64 96 128 256 512; do
    install -Dm 0644 "$ROOT/packaging/icons/hicolor/${sz}x${sz}/apps/$PKG.png" \
        "$STAGE/usr/share/icons/hicolor/${sz}x${sz}/apps/$PKG.png"
done

# package metadata
sed "s/__VERSION__/$VERSION/g" "$ROOT/packaging/debian/control" > "$DEBIAN/control"
install -m 0755 "$ROOT/packaging/debian/postinst" "$DEBIAN/postinst"

cat > "$STAGE/usr/share/doc/$PKG/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: metadata-studio
Source: https://github.com/VanguardArts/metadata-studio

Files: *
Copyright: 2026 Vanguard Arts SRL
License: MIT
 See /usr/share/doc/$PKG/ for the full MIT license text.
EOF

cat > "$STAGE/usr/share/doc/$PKG/changelog.gz.tmp" <<EOF
$PKG ($VERSION) unstable; urgency=medium

  * Initial release.

 -- Vanguard Arts SRL <https://vanguardarts.vip/>  $(date -R)
EOF
gzip -c "$STAGE/usr/share/doc/$PKG/changelog.gz.tmp" > "$STAGE/usr/share/doc/$PKG/changelog.gz"
rm -f "$STAGE/usr/share/doc/$PKG/changelog.gz.tmp"

mkdir -p "$ROOT/build/deb"
DEB_FILE="$ROOT/build/deb/${PKG}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB_FILE" >/dev/null

echo "✔ Built $DEB_FILE"
ls -l "$DEB_FILE"
