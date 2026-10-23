#!/bin/bash
# M4 Schritt 4: Paarvergleiche mit stop-when-decided; resume-faehig ueber --out
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
OPP="--opponent data/decks/precons/2026_doom_prevails.json --opponent data/decks/precons/2021_elven_empire.json --opponent data/decks/precons/2022_painbow.json"
PROG=~/workspace/tmp/m4/progress4.txt
V=~/workspace/tmp/m4/variants
run() { # name baseline varianten...
  local name=$1; local base=$2; shift 2
  local vars=(); for v in "$@"; do vars+=(--variant "$v"); done
  echo "$(date +%H:%M:%S) START $name" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline "$base" "${vars[@]}" $OPP --seeds 1-25 --games-per-jvm 6 --workers 2 --stop-when-decided --look-every 5 --out ~/workspace/tmp/m4/step4_$name > ~/workspace/tmp/m4/step4_${name}.log 2>&1
  echo "$(date +%H:%M:%S) ENDE $name rc=$? spiele=$(ls ~/workspace/tmp/m4/step4_$name/games 2>/dev/null | wc -l)" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline "$base" "${vars[@]}" $OPP --seeds 1-25 --games-per-jvm 6 --workers 1 --retry-failed --out ~/workspace/tmp/m4/step4_$name > ~/workspace/tmp/m4/step4_${name}_retry.log 2>&1
  echo "$(date +%H:%M:%S) RETRY-ENDE $name rc=$? spiele=$(ls ~/workspace/tmp/m4/step4_$name/games 2>/dev/null | wc -l) failed=$(grep -l '"status": "failed"' ~/workspace/tmp/m4/step4_$name/games/*.json 2>/dev/null | wc -l)" >> $PROG
}
run rogshai ~/workspace/tmp/m4/rogshai.json $V/rogshai_R1.json $V/rogshai_R2.json $V/rogshai_R3.json $V/rogshai_R4.json $V/rogshai_R5.json $V/rogshai_R6.json
run chulaneA ~/workspace/tmp/m4/chulane.json $V/chulane_C1.json $V/chulane_C2.json $V/chulane_C3.json $V/chulane_C4.json $V/chulane_C5.json $V/chulane_C6.json
run chulaneB ~/workspace/tmp/m4/chulane.json $V/chulane_C7.json $V/chulane_C8.json
echo "$(date +%H:%M:%S) SCHRITT4-RUNDEN-FERTIG" >> $PROG
