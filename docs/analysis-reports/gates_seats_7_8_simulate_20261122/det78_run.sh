#!/usr/bin/env bash
# Determinism at 7 and 8 seats (#1672, gate (a)): Studio play-batch, single JVM per game vs up/down
# 8 games per JVM, seeds 1-8, normalized frames. Same method as gate_a_determinism_5_6_20261122.
# SIMULATED_RESULT, not a qualification. Usage: run.sh N   (N = 7 or 8)
set -u
N=$1
S=<scratchpad>/s78gate
O=$S/det78; G=<scratchpad>/jarbuild/gate1715
cd /home/user/s78; export PYTHONPATH=/home/user/s78/src PYTHONHASHSEED=0
J=$S/after2/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
FAST="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar $J full-game"
FAST8="java -Dcommanderlab.fullGame.gamesPerJvm=8 ${FAST#java }"
P=data/decks/precons
D7="$P/2023_eldrazi_unbound.json $P/2026_lorehold_spirit.json $P/2024_animated_army.json $P/2022_token_triumph.json $P/2023_veloci_ramp_tor.json $P/2023_blood_rites.json $P/2023_divine_convocation.json"
D8="$D7 $P/2025_temur_roar.json"
if [ "$N" = 7 ]; then DK="$D7"; else DK="$D8"; fi
deckargs() { for f in $1; do printf -- '--deck %s ' "$f"; done; }
measure() { python3 -c 'import json,resource,subprocess,sys,time
t=time.monotonic(); rc=subprocess.run(sys.argv[2:]).returncode; r=resource.getrusage(resource.RUSAGE_CHILDREN)
json.dump({"rc":rc,"wall_s":round(time.monotonic()-t,2),"cpu_s":round(r.ru_utime+r.ru_stime,2),"maxrss_kib":r.ru_maxrss},open(sys.argv[1],"w"))' "$@"; }
echo "=== seats $N $(date -u +%H:%M:%S)" >> $O/run.log
for s in $(seq 1 8); do
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST" measure "$O/m-s${N}-single-$s.json" python3 -m commander_lab.studio --data "$O/s${N}_single" play-batch $(deckargs "$DK") --game "$s:g78-s${N}-$s" >> $O/s${N}_single.log 2>&1
done
COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST8" measure "$O/m-s${N}-up.json" python3 -m commander_lab.studio --data "$O/s${N}_up" play-batch $(deckargs "$DK") $(for s in $(seq 1 8); do printf -- '--game %s:g78-s%s-%s ' $s $N $s; done) >> $O/s${N}_up.log 2>&1
COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST8" measure "$O/m-s${N}-down.json" python3 -m commander_lab.studio --data "$O/s${N}_down" play-batch $(deckargs "$DK") $(for s in $(seq 8 -1 1); do printf -- '--game %s:g78-s%s-%s ' $s $N $s; done) >> $O/s${N}_down.log 2>&1
for o in up down; do python3 "$G/cmp_studio.py" "$O/s${N}_single/games" "$O/s${N}_$o/games" "g78-s${N}-*.jsonl.gz" --out "$O/cmp-s${N}-single-$o.json" >> $O/cmp.log 2>&1; done
echo "=== seats $N done $(date -u +%H:%M:%S)" >> $O/run.log
