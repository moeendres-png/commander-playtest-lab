#!/usr/bin/env bash
# Real-engine smoke through the Studio series path (compare-decks, paired series) at 7 and 8 seats (#1672).
set -u
S=<scratchpad>/s78gate
cd /home/user/s78; export PYTHONPATH=/home/user/s78/src PYTHONHASHSEED=0
J=$S/after2/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Xmx3g -jar $J full-game"
P=data/decks/precons
OPP="$P/2026_lorehold_spirit.json $P/2024_animated_army.json $P/2022_token_triumph.json $P/2023_veloci_ramp_tor.json $P/2023_blood_rites.json $P/2023_divine_convocation.json $P/2025_temur_roar.json"
for N in 7 8; do
  args=""; i=0; for f in $OPP; do i=$((i+1)); [ $i -le $((N-1)) ] && args="$args --opponent $f"; done
  python3 -m commander_lab.studio --data $S/smoke78_data compare-decks --base-deck $P/2023_eldrazi_unbound.json --variant-deck $P/2024_eldrazi_incursion.json $args --pairs 2 --look-every 2 --base-seed 1 --series-id smk78-$N --out $S/smoke78-$N.json > $S/smoke78-$N.log 2>&1
  echo "seats $N rc=$?"
done
