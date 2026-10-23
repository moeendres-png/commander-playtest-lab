#!/bin/bash
# M4 Schritt 2: Baselines RogShai + Chulane, Seeds 1-25 in 5er-Bloecken, resume-faehig
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m4 || exit 1
export PYTHONPATH=$PWD/src
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar /home/hatch/workspace/tmp/m3/bridge_v11.jar full-game"
PY=~/workspace/venvs/commander-lab/bin/python
OPP="--opponent data/decks/precons/2026_doom_prevails.json --opponent data/decks/precons/2021_elven_empire.json --opponent data/decks/precons/2022_painbow.json"
PROG=~/workspace/tmp/m4/progress.txt
for deck in rogshai chulane; do
  for block in "1-5" "6-10" "11-15" "16-20" "21-25"; do
    echo "$(date +%H:%M:%S) START $deck seeds $block" >> $PROG
    $PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/$deck.json --variant ~/workspace/tmp/m4/$deck.json $OPP --seeds $block --games-per-jvm 6 --workers 2 --out ~/workspace/tmp/m4/baseline_$deck > ~/workspace/tmp/m4/baseline_${deck}_${block}.log 2>&1
    echo "$(date +%H:%M:%S) ENDE $deck seeds $block rc=$? spiele=$(ls ~/workspace/tmp/m4/baseline_$deck/games 2>/dev/null | wc -l)" >> $PROG
  done
  echo "$(date +%H:%M:%S) RETRY $deck" >> $PROG
  $PY scripts/run_full_game_deck_comparison.py --baseline ~/workspace/tmp/m4/$deck.json --variant ~/workspace/tmp/m4/$deck.json $OPP --seeds 1-25 --games-per-jvm 6 --workers 1 --retry-failed --out ~/workspace/tmp/m4/baseline_$deck > ~/workspace/tmp/m4/baseline_${deck}_retry.log 2>&1
  echo "$(date +%H:%M:%S) FERTIG $deck rc=$? spiele=$(ls ~/workspace/tmp/m4/baseline_$deck/games 2>/dev/null | wc -l)" >> $PROG
done
echo "$(date +%H:%M:%S) ALLE-BASELINES-FERTIG" >> $PROG
