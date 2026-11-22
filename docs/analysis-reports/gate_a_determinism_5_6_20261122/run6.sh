#!/usr/bin/env bash
set -u
S=/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad
cd $S/meas1715; export PYTHONPATH=$PWD/src PYTHONHASHSEED=0
J=$S/jarbuild/out/xmage-engine-bridge.jar; O=$S/det56_out; G=$S/jarbuild/gate1715
FAST="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar $J full-game"
FAST8="java -Dcommanderlab.fullGame.gamesPerJvm=8 ${FAST#java }"
P=data/decks/precons
D6="$P/2023_eldrazi_unbound.json $P/2026_lorehold_spirit.json $P/2024_animated_army.json $P/2022_token_triumph.json $P/2023_veloci_ramp_tor.json $P/2022_heads_i_win__tails_you_lose.json"
deckargs() { for f in $1; do printf -- '--deck %s ' "$f"; done; }
echo "=== seats 6 restart up/down $(date -u +%H:%M:%S)" >> $O/run.log
rm -rf $O/s6_up $O/s6_down
COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST8" python -m commander_lab.studio --data "$O/s6_up" play-batch $(deckargs "$D6") $(for s in $(seq 1 8); do printf -- '--game %s:g56-s6-%s ' $s $s; done) >> $O/s6_up.log 2>&1
COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST8" python -m commander_lab.studio --data "$O/s6_down" play-batch $(deckargs "$D6") $(for s in $(seq 8 -1 1); do printf -- '--game %s:g56-s6-%s ' $s $s; done) >> $O/s6_down.log 2>&1
for o in up down; do python "$G/cmp_studio.py" "$O/s6_single/games" "$O/s6_$o/games" "g56-s6-*.jsonl.gz" --out "$O/cmp-s6-single-$o.json" >> $O/cmp.log 2>&1; done
find $O -type f \( -name '*.json' -o -name '*.gz' -o -name '*.log' \) ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > $O/SHA256SUMS
echo "=== seats 6 done $(date -u +%H:%M:%S)" >> $O/run.log
