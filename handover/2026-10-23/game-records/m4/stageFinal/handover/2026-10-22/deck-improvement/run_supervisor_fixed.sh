#!/bin/bash
# M4 Schritt 4 — korrigierter Supervisor (ersetzt run_step4b.sh / run_slices*.sh).
# Fixes gegenueber den Nacht-Skripten:
#  1. Exit-Codes werden DIREKT nach dem Kommando gelesen ($? auf eigener Zeile),
#     niemals nach einer Command-Substitution im selben echo (alte "ENDE rc=0"-
#     Zeilen waren dadurch wertlos). Zusaetzlich `set -o pipefail`.
#  2. Seed-Scheiben statt eines 800-Spiele-Prozesses: der Vergleichsprozess haelt
#     alle Records im RAM (~5 GB bei 800 Spielen auf dieser 7-GB-Box) und wurde
#     wiederholt gekillt. Scheiben von 9-12 Seeds mit eigenem Prozess bleiben
#     klein; Resume pro Scheibe uebernimmt Fertiges (gleiche Spec = gleicher run_key).
#  3. workers=1, games-per-jvm=3 (Batching durch PR #974 qualifiziert).
set -o pipefail
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
PROG=~/workspace/tmp/m4/progress_fixed.txt
slice() { # name base seeds variants...
  local name=$1 base=$2 seeds=$3; shift 3
  local vars=(); for v in "$@"; do vars+=(--variant "$v"); done
  echo "$(date +%H:%M:%S) START $name seeds=$seeds" >> "$PROG"
  $PY scripts/run_full_game_deck_comparison.py --baseline "$base" "${vars[@]}" \
    --opponent data/decks/precons/2026_doom_prevails.json \
    --opponent data/decks/precons/2021_elven_empire.json \
    --opponent data/decks/precons/2022_painbow.json \
    --seeds "$seeds" --games-per-jvm 3 --workers 1 \
    --out ~/workspace/tmp/m4/step4b_$name > ~/workspace/tmp/m4/fixed_${name}_${seeds}.log 2>&1
  rc=$?
  echo "$(date +%H:%M:%S) ENDE $name seeds=$seeds rc=$rc" >> "$PROG"
}
