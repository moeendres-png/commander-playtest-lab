#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-3.9.16}"
DEST="$ROOT/.tools/apache-maven-$VERSION"
[[ -x "$DEST/bin/mvn" ]] && { "$DEST/bin/mvn" -version; exit 0; }
command -v curl >/dev/null || { echo "ERROR: curl is required to download Maven" >&2; exit 2; }
ARCHIVE="apache-maven-$VERSION-bin.tar.gz"
BASE="https://archive.apache.org/dist/maven/maven-3/$VERSION/binaries"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl --fail --location --retry 3 "$BASE/$ARCHIVE" -o "$TMP/$ARCHIVE"
curl --fail --location --retry 3 "$BASE/$ARCHIVE.sha512" -o "$TMP/$ARCHIVE.sha512"
EXPECTED="$(awk '{print $1}' "$TMP/$ARCHIVE.sha512")"
ACTUAL="$(sha512sum "$TMP/$ARCHIVE" | awk '{print $1}')"
[[ "$EXPECTED" == "$ACTUAL" ]] || { echo "ERROR: Maven SHA-512 mismatch" >&2; exit 3; }
tar -xzf "$TMP/$ARCHIVE" -C "$ROOT/.tools"
"$DEST/bin/mvn" -version
