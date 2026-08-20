#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
NAME="soloPAW-public-source"
mkdir -p "$DIST"
rm -f "$DIST/$NAME.zip" "$DIST/$NAME.tar.gz" "$DIST/SHA256SUMS.txt"
cd "$ROOT/.."
BASE="$(basename "$ROOT")"
zip -qr "$DIST/$NAME.zip" "$BASE" -x "$BASE/.git/*" "$BASE/dist/*" "$BASE/**/__pycache__/*" "$BASE/**/*.pyc"
tar --exclude='.git' --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' -czf "$DIST/$NAME.tar.gz" "$BASE"
cd "$DIST"
sha256sum "$NAME.zip" "$NAME.tar.gz" > SHA256SUMS.txt
cat SHA256SUMS.txt
