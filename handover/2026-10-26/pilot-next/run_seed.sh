#!/bin/bash
# Einen Dump-Seed aufnehmen (ein Seed = eine Datei, resume-fähig).
# Verwendung: run_seed.sh <worktree> <jar> <tag> <seed>
#   tag: pre | main ; out: ~/workspace/tmp/1029/dump-<tag>-seed<seed>.jsonl.gz
# Unbuffered (-u), damit der Fortschritt auch bei Kill sichtbar bleibt.
# Vor jedem Start: ps prüfen (max. 2 JVMs gesamt), stale Locks nur bei 0
# eigenen Spiel-JVMs löschen. NICHT parallel zu anderen Spiel-JVMs starten.
set -u
WORKTREE="$1"; JAR="$2"; TAG="$3"; SEED="$4"
OUT=~/workspace/tmp/1029/dump-${TAG}-seed${SEED}.jsonl.gz
if [ -f "$OUT" ]; then echo "schon da: $OUT"; exit 0; fi
cd "$WORKTREE" || exit 1
source ~/workspace/tools/env.sh
source ~/workspace/venvs/commander-lab/bin/activate
PYTHONPATH=src python -u scripts/pilot_request_corpus.py record --all \
  --jar "$JAR" --seeds "$SEED" --out "$OUT"
echo "exit: $? seed $SEED tag $TAG"
