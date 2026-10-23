#!/bin/bash
# M4 Schritt 4 (Nachtrag-1-Fassung): Buendel-Laeufe Seeds 1-50, stop-when-decided
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
OPP="--opponent data/decks/precons/2026_doom_prevails.json --opponent data/decks/precons/2021_elven_empire.json --opponent data/decks/precons/2022_painbow.json"
PROG=~/workspace/tmp/m4/progress4b.txt
B=~/workspace/tmp/m4/bundles
run() {
  local name=$1; local base=$2; shift 2
  local vars=(); for v in "$@"; do vars+=(--variant "$v"); done
  echo "$(date +%H:%M:%S) START $name" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline "$base" "${vars[@]}" $OPP --seeds 1-50 --games-per-jvm 6 --workers 2 --stop-when-decided --look-every 5 --out ~/workspace/tmp/m4/step4b_$name > ~/workspace/tmp/m4/step4b_${name}.log 2>&1
  echo "$(date +%H:%M:%S) ENDE $name rc=$? spiele=$(ls ~/workspace/tmp/m4/step4b_$name/games 2>/dev/null | wc -l)" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline "$base" "${vars[@]}" $OPP --seeds 1-50 --games-per-jvm 6 --workers 1 --retry-failed --out ~/workspace/tmp/m4/step4b_$name > ~/workspace/tmp/m4/step4b_${name}_retry.log 2>&1
  echo "$(date +%H:%M:%S) RETRY-ENDE $name rc=$? spiele=$(ls ~/workspace/tmp/m4/step4b_$name/games 2>/dev/null | wc -l) failed=$(grep -l '"status": "failed"' ~/workspace/tmp/m4/step4b_$name/games/*.json 2>/dev/null | wc -l)" >> $PROG
}
run rogshai ~/workspace/tmp/m4/rogshai.json $B/rogshai_RA.json $B/rogshai_RB.json $B/rogshai_RC.json
run chulane ~/workspace/tmp/m4/chulane.json $B/chulane_CA.json $B/chulane_CB.json $B/chulane_CC.json
echo "$(date +%H:%M:%S) BUENDEL-LAEUFE-FERTIG" >> $PROG
