#!/usr/bin/env bash
set -u
S=<scratchpad>/s78gate
cd /home/user/s78; export PYTHONPATH=/home/user/s78/src PYTHONHASHSEED=0
HEAD=$(git rev-parse HEAD)
rm -rf $S/after2 && mkdir -p $S/after2 && git archive $HEAD engine-bridge | tar -x -C $S/after2
(cd $S/after2/engine-bridge && mvn -o -q -B package -DskipTests > $S/build-after2b.log 2>&1); echo "build rc=$? $(date -u +%T)"
A=$S/after2/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
B=$S/before/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar
{ echo "lab_head $HEAD"; git status --short src engine-bridge | sed 's/^/dirty /'; sha256sum $B $A; python3 -c 'import commander_lab; print("commander_lab", commander_lab.__file__)'; java -version 2>&1 | grep -v JAVA_TOOL; } > $S/IDENTITY.txt
rm -rf $S/after2_test && cp -r $S/after2 $S/after2_test
(cd $S/after2_test/engine-bridge && mvn -o -B test -Dtest='XmageSeatsFiveSixF5ScenarioTest,XmageFullGamePlayerCountTest,XmageFullGameContractTruthTest' -Dsurefire.failIfNoSpecifiedTests=false > $S/java-after2.log 2>&1); echo "java rc=$? $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py run --jar $A --out $S/after.json --seeds 1-36 --workers 4 --games-per-jvm 9 --fast > $S/run-after.log 2>&1; echo "after rc=$? $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py compare $S/before.json $S/after.json --expect-games 36 --require-different-jars > $S/cmp-36.txt 2>&1; echo "cmp36 rc=$?"
python3 scripts/benchmark_xmage_full_games.py run --jar $A --out $S/after-gpj1.json --seeds 1-6 --workers 4 --games-per-jvm 1 --fast > $S/run-after-gpj1.log 2>&1; echo "gpj1 rc=$? $(date -u +%T)"
python3 scripts/benchmark_xmage_full_games.py compare $S/before.json $S/after-gpj1.json --require-different-jars > $S/cmp-gpj1.txt 2>&1; echo "cmpgpj1 rc=$?"
( $S/det78/run.sh 7 ) & ( $S/det78/run.sh 8 ) & wait; echo "det78 done $(date -u +%T)"
$S/smoke78.sh > $S/smoke78.out 2>&1; echo "smoke done $(date -u +%T)"
