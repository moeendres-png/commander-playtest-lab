#!/usr/bin/env bash
# Rebuilds every generated file of the rubric v2 design draft from a store COPY and a checkout.
#   run_all.sh <store-copy-dir> <checkout> [<out-dir>]    (default out-dir: the folder above scripts/;
#                                                          the docs live there, data goes to <out-dir>/data)
# data/usage_holdout.jsonl is written locally by extract_facts.py, is never checked in and never
# enters a rater prompt.
# The Studio code is read from <checkout>/src (PYTHONPATH). Nothing writes into the store or the checkout.
set -euo pipefail
STORE=$1; REPO=$2; HERE=$(cd "$(dirname "$0")" && pwd); OUT=${3:-$HERE/..}
export PYTHONPATH="$REPO/src"
mkdir -p "$OUT/data"
python3 "$HERE/extract_facts.py" --store "$STORE" --repo "$REPO" --out "$OUT/data"
python3 "$HERE/extract_patterns.py" --facts "$OUT/data/facts.jsonl" --out "$OUT/data" \
        --usage-holdout "$OUT/data/usage_holdout.jsonl" --sample 20 --seed 1118
python3 "$HERE/make_pilot_sample.py" --store "$STORE" --repo "$REPO" --facts "$OUT/data/facts.jsonl" \
        --patterns "$OUT/data/patterns.jsonl" --usage "$OUT/data/usage_holdout.jsonl" --out "$OUT/pilot_sample.json"
python3 "$HERE/build_anchors.py" --facts "$OUT/data/facts.jsonl" --pilot "$OUT/pilot_sample.json" --out "$OUT" \
        --ratings "$REPO/data/research/chulane_rubric_20261114/ratings.csv"
python3 "$HERE/render_prompt.py" --dir "$OUT" --check-leave-one-out --stats
