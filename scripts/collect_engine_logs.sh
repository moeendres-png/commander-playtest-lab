#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/artifacts/engine_setup/engine-logs-$(date -u +%Y%m%dT%H%M%SZ).tar.gz}"
mkdir -p "$(dirname "$OUT")"
tar -czf "$OUT" -C "$ROOT" artifacts/engine_setup config/rules_engines.json .env.example
echo "$OUT"
