#!/usr/bin/env bash
# Determinism measurement at 5 and 6 seats (Studio play-batch, single JVM vs up/down 8 games/JVM), N=8 seeds each. NOT a qualification.
set -u
S=/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad
cd $S/meas1715; export PYTHONPATH=$PWD/src PYTHONHASHSEED=0
J=$S/jarbuild/out/xmage-engine-bridge.jar; O=$S/det56_out; G=$S/jarbuild/gate1715
{ git rev-parse HEAD; sha256sum $J; } > $O/IDENTITY.txt
FAST="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar $J full-game"
FAST8="java -Dcommanderlab.fullGame.gamesPerJvm=8 ${FAST#java }"
P=data/decks/precons
D5="$P/2023_eldrazi_unbound.json $P/2026_lorehold_spirit.json $P/2024_animated_army.json $P/2022_token_triumph.json $P/2023_veloci_ramp_tor.json"
D6="$D5 $P/2022_heads_i_win__tails_you_lose.json"
deckargs() { for f in $1; do printf -- '--deck %s ' "$f"; done; }
for N in 5 6; do
  if [ $N = 5 ]; then DK="$D5"; else DK="$D6"; fi
  echo "=== seats $N $(date -u +%H:%M:%S)" >> $O/run.log
  for s in $(seq 1 8); do
    COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST" python -m commander_lab.studio --data "$O/s${N}_single" play-batch $(deckargs "$DK") --game "$s:g56-s${N}-$s" >> $O/s${N}_single.log 2>&1; done
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST8" python -m commander_lab.studio --data "$O/s${N}_up" play-batch $(deckargs "$DK") $(for s in $(seq 1 8); do printf -- '--game %s:g56-s%s-%s ' $s $N $s; done) >> $O/s${N}_up.log 2>&1
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST8" python -m commander_lab.studio --data "$O/s${N}_down" play-batch $(deckargs "$DK") $(for s in $(seq 8 -1 1); do printf -- '--game %s:g56-s%s-%s ' $s $N $s; done) >> $O/s${N}_down.log 2>&1
  for o in up down; do python "$G/cmp_studio.py" "$O/s${N}_single/games" "$O/s${N}_$o/games" "g56-s${N}-*.jsonl.gz" --out "$O/cmp-s${N}-single-$o.json" >> $O/cmp.log 2>&1; done
  echo "=== seats $N done $(date -u +%H:%M:%S)" >> $O/run.log
done
find $O -type f \( -name '*.json' -o -name '*.gz' -o -name '*.log' \) ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > $O/SHA256SUMS
echo done >> $O/run.log
