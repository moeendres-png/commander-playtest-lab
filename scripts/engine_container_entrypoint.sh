#!/usr/bin/env bash
set -euo pipefail
[[ -n "${ENGINE_START_COMMAND:-}" ]] || { echo "ENGINE_START_COMMAND is required" >&2; exit 64; }
exec bash -lc "$ENGINE_START_COMMAND"
