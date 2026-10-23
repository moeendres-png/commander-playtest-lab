#!/bin/bash
# M4 Schritt 4, Restlaeufe in Seed-Scheiben (Speichergrenze des Runners umgehen).
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
OPP="--opponent data/decks/precons/2026_doom_prevails.json --opponent data/decks/precons/2021_elven_empire.json --opponent data/decks/precons/2022_painbow.json"
B=~/workspace/tmp/m4/bundles
PROG=~/workspace/tmp/m4/progress_slices.txt
run_slice() { # name base variants... -- seeds
  local name=$1 base=$2 seeds=$3; shift 3
  local vars=(); for v in "$@"; do vars+=(--variant "$v"); done
  echo "$(date +%H:%M:%S) START $name seeds=$seeds" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline "$base" "${vars[@]}" $OPP --seeds "$seeds" --games-per-jvm 3 --workers 1 --out ~/workspace/tmp/m4/step4b_$name > ~/workspace/tmp/m4/slice_${name}_${seeds}.log 2>&1
  echo "$(date +%H:%M:%S) ENDE $name seeds=$seeds spiele=$(ls ~/workspace/tmp/m4/step4b_$name/games 2>/dev/null | wc -l)" >> $PROG
}
# RogShai: fehlende Seeds 33-50 in zwei Scheiben, danach Retry der Timeout-Faelle (Seeds 32-50)
run_slice rogshai ~/workspace/tmp/m4/rogshai.json 33-41 $B/rogshai_RA.json $B/rogshai_RB.json $B/rogshai_RC.json
run_slice rogshai ~/workspace/tmp/m4/rogshai.json 42-50 $B/rogshai_RA.json $B/rogshai_RB.json $B/rogshai_RC.json
echo "$(date +%H:%M:%S) START rogshai RETRY seeds=32-50" >> $PROG
$PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/rogshai.json --variant $B/rogshai_RA.json --variant $B/rogshai_RB.json --variant $B/rogshai_RC.json $OPP --seeds 32-50 --games-per-jvm 3 --workers 1 --retry-failed --out ~/workspace/tmp/m4/step4b_rogshai > ~/workspace/tmp/m4/slice_rogshai_retry.log 2>&1
echo "$(date +%H:%M:%S) ENDE rogshai RETRY spiele=$(ls ~/workspace/tmp/m4/step4b_rogshai/games | wc -l)" >> $PROG
# Chulane: fehlende Seeds in Scheiben (16-20 zuerst: dort fehlen 4 Spiele aus Seed 16)
run_slice chulane ~/workspace/tmp/m4/chulane.json 16-20 $B/chulane_CA.json $B/chulane_CB.json $B/chulane_CC.json
run_slice chulane ~/workspace/tmp/m4/chulane.json 21-30 $B/chulane_CA.json $B/chulane_CB.json $B/chulane_CC.json
run_slice chulane ~/workspace/tmp/m4/chulane.json 31-40 $B/chulane_CA.json $B/chulane_CB.json $B/chulane_CC.json
run_slice chulane ~/workspace/tmp/m4/chulane.json 41-50 $B/chulane_CA.json $B/chulane_CB.json $B/chulane_CC.json
echo "$(date +%H:%M:%S) SCHEIBEN-FERTIG" >> $PROG
