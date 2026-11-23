#!/usr/bin/env bash
# A1-Forensik: alle Auswertungen in fester Reihenfolge. Aufruf: bash run_all.sh
# Eingaben (siehe ../README.md): Repo-Checkout ($A1_REPO, Standard: dieser Checkout), usage_holdout.jsonl
# ($A1_USAGE, lokal, nicht im Repo), Decklisten-Korpus ($A1_CORPUS, lokaler Checkout, nur Gegenprobe),
# Original-F1-Chargenprompts ($A1_F1RAW, nicht im Repo). Ausgaben: $A1_OUT (Standard ./work_a1).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export A1_REPO=${A1_REPO:-$(cd "$HERE/../../../../.." && pwd)}
export A1_OUT=${A1_OUT:-$PWD/work_a1}
: "${A1_USAGE:?A1_USAGE (usage_holdout.jsonl) setzen}"
: "${A1_CORPUS:?A1_CORPUS (Korpus-Ordner chulane_corpus) setzen}"
: "${A1_F1RAW:?A1_F1RAW (Ordner mit F1_b*.md) setzen}"
mkdir -p "$A1_OUT"
export PYTHONPATH=$A1_REPO/src
python3 "$HERE/a1_parity.py" --f1-batches "$A1_F1RAW" > "$A1_OUT/parity_stdout.txt"
python3 "$HERE/a1_decomp.py" > "$A1_OUT/decomp_stdout.txt"
python3 "$HERE/a1_struct.py" > "$A1_OUT/struct_stdout.txt"
python3 "$HERE/a1_external.py" --usage "$A1_USAGE" --corpus "$A1_CORPUS" > "$A1_OUT/external_stdout.txt"
python3 "$HERE/a1_extra.py" --usage "$A1_USAGE" > "$A1_OUT/extra_stdout.txt"
python3 "$HERE/a1_top30.py" > "$A1_OUT/top30_stdout.txt"
cd "$A1_OUT" && sha256sum parity.json decomp.json pairs.jsonl struct.json external.json extra.json top30.json
