#!/bin/bash
# M4 Schritt 4: finaler Retry aller Timeout-Faelle (RogShai ab Seed 31, Chulane ab 29).
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
OPP="--opponent data/decks/precons/2026_doom_prevails.json --opponent data/decks/precons/2021_elven_empire.json --opponent data/decks/precons/2022_painbow.json"
B=~/workspace/tmp/m4/bundles
PROG=~/workspace/tmp/m4/progress_slices.txt
echo "$(date +%H:%M:%S) START FINAL-RETRY rogshai seeds=31-50" >> $PROG
$PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/rogshai.json --variant $B/rogshai_RA.json --variant $B/rogshai_RB.json --variant $B/rogshai_RC.json $OPP --seeds 31-50 --games-per-jvm 3 --workers 1 --retry-failed --out ~/workspace/tmp/m4/step4b_rogshai > ~/workspace/tmp/m4/retry_final_rogshai.log 2>&1
echo "$(date +%H:%M:%S) ENDE FINAL-RETRY rogshai" >> $PROG
echo "$(date +%H:%M:%S) START FINAL-RETRY chulane seeds=29-50" >> $PROG
$PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/chulane.json --variant $B/chulane_CA.json --variant $B/chulane_CB.json --variant $B/chulane_CC.json $OPP --seeds 29-50 --games-per-jvm 3 --workers 1 --retry-failed --out ~/workspace/tmp/m4/step4b_chulane > ~/workspace/tmp/m4/retry_final_chulane.log 2>&1
echo "$(date +%H:%M:%S) ENDE FINAL-RETRY chulane" >> $PROG
