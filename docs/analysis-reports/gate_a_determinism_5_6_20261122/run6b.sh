#!/usr/bin/env bash
set -u
S=/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad
cd $S/meas1715; export PYTHONPATH=$PWD/src PYTHONHASHSEED=0
J=$S/jarbuild/out/xmage-engine-bridge.jar; O=$S/det56_out; G=$S/jarbuild/gate1715
FAST="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar $J full-game"
P=data/decks/precons
D6="--deck $P/2023_eldrazi_unbound.json --deck $P/2026_lorehold_spirit.json --deck $P/2024_animated_army.json --deck $P/2022_token_triumph.json --deck $P/2023_veloci_ramp_tor.json --deck $P/2022_heads_i_win__tails_you_lose.json"
echo "=== seed4 repeat single x3 $(date -u +%H:%M:%S)" >> $O/run.log
for r in a b c; do
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST" python -m commander_lab.studio --data "$O/s6_rep_$r" play-batch $D6 --game "4:g56-s6-4" >> $O/s6_rep.log 2>&1
done
for r in a b c; do python "$G/cmp_studio.py" "$O/s6_single/games" "$O/s6_rep_$r/games" "g56-s6-4*.jsonl.gz" --out "$O/cmp-s6-rep-$r.json" >> $O/cmp_rep.log 2>&1; done
echo "=== seed4 repeat done $(date -u +%H:%M:%S)" >> $O/run.log
