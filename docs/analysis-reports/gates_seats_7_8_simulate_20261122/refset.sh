#!/usr/bin/env bash
# Studio bridge gate NEUTRAL (#1672): reference set seeds 1-36, real pod, BEFORE (main 3037a425) vs AFTER (branch).
set -u
cd /home/user/s78; export PYTHONPATH=/home/user/s78/src PYTHONHASHSEED=0
B=<scratchpad>/s78gate/before/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
A=<scratchpad>/s78gate/after/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
echo "start $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py run --jar $B --out <scratchpad>/s78gate/before.json --seeds 1-36 --workers 4 --games-per-jvm 9 --fast > <scratchpad>/s78gate/run-before.log 2>&1; echo "before rc=$? $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py run --jar $A --out <scratchpad>/s78gate/after.json --seeds 1-36 --workers 4 --games-per-jvm 9 --fast > <scratchpad>/s78gate/run-after.log 2>&1; echo "after rc=$? $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py compare <scratchpad>/s78gate/before.json <scratchpad>/s78gate/after.json --expect-games 36 --require-different-jars > <scratchpad>/s78gate/cmp-36.txt 2>&1; echo "cmp36 rc=$?"
python3 scripts/benchmark_xmage_full_games.py run --jar $A --out <scratchpad>/s78gate/after-gpj1.json --seeds 1-6 --workers 4 --games-per-jvm 1 --fast > <scratchpad>/s78gate/run-after-gpj1.log 2>&1; echo "gpj1 rc=$? $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py compare <scratchpad>/s78gate/before.json <scratchpad>/s78gate/after-gpj1.json --require-different-jars > <scratchpad>/s78gate/cmp-gpj1.txt 2>&1; echo "cmpgpj1 rc=$?"
echo done
