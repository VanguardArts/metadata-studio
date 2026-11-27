#!/usr/bin/env bash
# Build an AppImage for Metascrub.
#
# A PySide6 app is non-trivial to bundle (Python + full Qt stack), so we build
# on top of python-appimage to get a relocatable CPython, install our deps into
# it, then wrap the result with appimagetool. Best run in CI.
#
# Output: build/appimage/metascrub-<arch>.AppImage
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="metascrub"
OUT="$ROOT/build/appimage"
APPDIR="$OUT/AppDir"

ARCH=$(uname -m)
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"

mkdir -p "$APPDIR"

PYAPPIMAGE="python3.12.3-cp312-cp312-manylinux2014_${ARCH}.AppImage"
if [ ! -x "$OUT/$PYAPPIMAGE" ]; then
    curl -fsSL "https://github.com/niess/python-appimage/releases/download/python3.12/$PYAPPIMAGE" \
        -o "$OUT/$PYAPPIMAGE"
    chmod +x "$OUT/$PYAPPIMAGE"
    (cd "$OUT" && ./"$PYAPPIMAGE" --appimage-extract >/dev/null)
fi

"$OUT/squashfs-root/AppRun" -m pip install --quiet pillow mutagen pypdf pyside6

cp -a "$OUT/squashfs-root/." "$APPDIR/"

# vendor the package directly (simpler than a pip egg inside AppImage)
install -d "$APPDIR/usr/lib/$PKG"
cp -r "$ROOT/src/metascrub" "$APPDIR/usr/lib/$PKG/metascrub"
cp "$ROOT/packaging/cli_main.py" "$ROOT/packaging/gui_main.py" "$APPDIR/usr/lib/$PKG/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/python3.12" "$HERE/usr/lib/metascrub/gui_main.py" "$@"
EOF
chmod +x "$APPDIR/AppRun"

install -Dm644 "$ROOT/packaging/metascrub.desktop" "$APPDIR/metascrub.desktop"
install -Dm644 "$ROOT/packaging/icons/hicolor/256x256/apps/metascrub.png" \
    "$APPDIR/metascrub.png"

if [ ! -x "$OUT/appimagetool" ]; then
    curl -fsSL "$APPIMAGETOOL_URL" -o "$OUT/appimagetool"
    chmod +x "$OUT/appimagetool"
fi

"$OUT/appimagetool" "$APPDIR" "$OUT/$PKG-${ARCH}.AppImage"

echo "✔ AppImage built: $OUT/$PKG-${ARCH}.AppImage"
