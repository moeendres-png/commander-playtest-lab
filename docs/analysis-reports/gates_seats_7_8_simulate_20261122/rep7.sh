#!/usr/bin/env bash
# Review of #1762: seed 7 at 8 seats three more times SINGLE (own JVM each, same config as det78/run.sh),
# compared with the existing single base. SIMULATED_RESULT.
set -u
S=<scratchpad>/s78gate
O=$S/det78; G=<scratchpad>/jarbuild/gate1715
cd /home/user/s78; export PYTHONPATH=/home/user/s78/src PYTHONHASHSEED=0
J=$S/after2/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
FAST="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar $J full-game"
P=data/decks/precons
D8="$P/2023_eldrazi_unbound.json $P/2026_lorehold_spirit.json $P/2024_animated_army.json $P/2022_token_triumph.json $P/2023_veloci_ramp_tor.json $P/2023_blood_rites.json $P/2023_divine_convocation.json $P/2025_temur_roar.json"
args=""; for f in $D8; do args="$args --deck $f"; done
for r in 1 2 3; do
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST" python3 -m commander_lab.studio --data "$O/s8_rep$r" play-batch $args --game "7:g78-s8-7" >> $O/s8_rep.log 2>&1
  python3 "$G/cmp_studio.py" "$O/s8_single/games" "$O/s8_rep$r/games" "g78-s8-7.jsonl.gz" --out "$O/cmp-s8-seed7-single-rep$r.json" >> $O/cmp_rep.log 2>&1
done
python3 "$G/cmp_studio.py" "$O/s8_up/games" "$O/s8_down/games" "g78-s8-*.jsonl.gz" --out "$O/cmp-s8-up-down.json" >> $O/cmp_rep.log 2>&1
echo done >> $O/cmp_rep.log
