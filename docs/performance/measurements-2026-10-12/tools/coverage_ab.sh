#!/bin/bash
S=/tmp/claude-0/-home-user/765903b1-9156-5d60-bb8d-0f5d4534f692/scratchpad
cd /home/user/commander-playtest-lab
D=($(ls data/coverage_decks/collection/*.json))
PODS=("0 1 2 3" "4 5 6 7" "8 9 10 11" "12 13 14 15" "16 17 0 5")
for jar in $JARS; do
  i=0
  for pod in "${PODS[@]}"; do
    paths=$(for k in $pod; do printf "%s," "${D[$k]}"; done); paths=${paths%,}
    BENCH_POD=$i BENCH_DECKS=$paths PYTHONHASHSEED=0 /home/user/venv/bin/python $S/bench4p.py ${JARPATH:-$S/jars/${JARFILE:-$jar}.jar} $S/cov_${jar}_$i.json 1 2 2>&1 | grep -v JAVA_TOOL | sed -u "s/^/$jar /"
    i=$((i+1))
  done
done
