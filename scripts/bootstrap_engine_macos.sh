#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v java >/dev/null || ! command -v javac >/dev/null; then
  echo "ERROR: install Temurin/OpenJDK 21, then rerun" >&2; exit 3
fi
exec "$ROOT/scripts/bootstrap_engine_linux.sh" "$@"
