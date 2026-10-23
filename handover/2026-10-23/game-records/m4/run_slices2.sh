#!/bin/bash
# M4 Schritt 4, Restscheiben v2: Chulane erst ab Seed 29 (1-28 sind abgeschlossen).
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
OPP="--opponent data/decks/precons/2026_doom_prevails.json --opponent data/decks/precons/2021_elven_empire.json --opponent data/decks/precons/2022_painbow.json"
B=~/workspace/tmp/m4/bundles
PROG=~/workspace/tmp/m4/progress_slices.txt
echo "$(date +%H:%M:%S) START rogshai RETRY v2 seeds=32-50" >> $PROG
$PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/rogshai.json --variant $B/rogshai_RA.json --variant $B/rogshai_RB.json --variant $B/rogshai_RC.json $OPP --seeds 32-50 --games-per-jvm 3 --workers 1 --retry-failed --out ~/workspace/tmp/m4/step4b_rogshai > ~/workspace/tmp/m4/slice_rogshai_retry2.log 2>&1
echo "$(date +%H:%M:%S) ENDE rogshai RETRY v2" >> $PROG
for range in 29-38 39-50; do
  echo "$(date +%H:%M:%S) START chulane seeds=$range" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/chulane.json --variant $B/chulane_CA.json --variant $B/chulane_CB.json --variant $B/chulane_CC.json $OPP --seeds $range --games-per-jvm 3 --workers 1 --out ~/workspace/tmp/m4/step4b_chulane > ~/workspace/tmp/m4/slice_chulane_${range}.log 2>&1
  echo "$(date +%H:%M:%S) ENDE chulane seeds=$range" >> $PROG
done
echo "$(date +%H:%M:%S) SCHEIBEN-V2-FERTIG" >> $PROG
