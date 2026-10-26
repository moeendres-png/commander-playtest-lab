#!/bin/bash
# #1029-Kette: pre-Seeds 2-6 (wt-1029-pre1010, Pre-#1010-Pilot), dann
# main-Seeds 2-24 (wt-1029, Main-Pilot). Strikt sequenziell, eine JVM pro
# Lauf. Resume-fähig: run_seed.sh überspringt bereits vorhandene Dumps.
# Jeder Seed loggt separat nach ~/workspace/tmp/1029/seed-<tag>-<n>.log,
# Fortschritt in ~/workspace/tmp/1029/chain-1029.log.
# JAR für alle Seeds identisch (Merge verlangt gleiche jar_sha256):
#   wt-1029/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
#   sha256 eca822d295a3f3340db1e9dc0c1acbd9d45accad6f6468325fa1285e178948fa
set -u
JAR=~/workspace/github/wt-1029/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
LOG=~/workspace/tmp/1029/chain-1029.log
echo "$(date -u +%FT%TZ) Kette gestartet (pre 2-6, dann main 2-24)" >> "$LOG"
run_one() {
  local wt="$1" tag="$2" seed="$3"
  local out=~/workspace/tmp/1029/dump-${tag}-seed${seed}.jsonl.gz
  echo "$(date -u +%FT%TZ) $tag seed $seed Start" >> "$LOG"
  bash ~/workspace/tmp/1029/run_seed.sh "$wt" "$JAR" "$tag" "$seed" \
    > ~/workspace/tmp/1029/seed-${tag}-${seed}.log 2>&1
  if [ -f "$out" ] && gzip -t "$out" 2>/dev/null; then
    echo "$(date -u +%FT%TZ) $tag seed $seed OK $(zcat "$out" | wc -l) Zeilen" >> "$LOG"
  else
    echo "$(date -u +%FT%TZ) $tag seed $seed FEHLT/KORRUPT (siehe seed-${tag}-${seed}.log)" >> "$LOG"
  fi
}
for s in 2 3 4 5 6; do
  run_one ~/workspace/github/wt-1029-pre1010 pre "$s"
done
for s in $(seq 2 24); do
  run_one ~/workspace/github/wt-1029 main "$s"
done
echo "$(date -u +%FT%TZ) Kette fertig" >> "$LOG"
