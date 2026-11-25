#!/usr/bin/env bash
# Build an RPM for Metadata Studio (Fedora, RHEL, Rocky/Alma, openSUSE).
#
# Output: build/rpm/RPMS/noarch/metadata-studio-<version>-1.noarch.rpm
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.1.0"
NAME="metadata-studio"
OUT="$ROOT/build/rpm"
TARBALL="$NAME-$VERSION.tar.gz"

command -v rpmbuild >/dev/null 2>&1 || {
    echo "error: rpmbuild not found (install 'rpm-build' / 'rpm')" >&2
    exit 1
}
command -v tar >/dev/null 2>&1 || { echo "error: tar not found" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

STAGE="$(mktemp -d)/$NAME-$VERSION"
mkdir -p "$STAGE"
# copy everything the spec needs
cp -a "$ROOT/src" "$ROOT/packaging" "$ROOT/LICENSE" "$ROOT/README.md" "$STAGE/"
tar -C "$(dirname "$STAGE")" -czf "$OUT/SOURCES/$TARBALL" "$NAME-$VERSION"
rm -rf "$(dirname "$STAGE")"

rpmbuild -bb --define "_topdir $OUT" "$ROOT/packaging/rpm/metadata-studio.spec"

echo "✔ RPM built:"
find "$OUT/RPMS" -name '*.rpm' -exec ls -l {} \;
