#!/usr/bin/env bash
# usage: run_oracle.sh VARIANT SEEDS
S=/tmp/claude-0/-home-user/539e0cc6-b24b-52bf-b082-9d8e56b102aa/scratchpad
v=$1; seeds=$2; tag=${3:-s$(echo $seeds | tr ',' '_')}
cd /home/user/commander-playtest-lab
PYTHONPATH="$PWD/src" $S/venv/bin/python scripts/benchmark_xmage_full_games.py run --jar $S/jars/$v.jar --out $S/res/${v}_${tag}.json --seeds $seeds --workers 2 --private-card-repository > $S/res/${v}_${tag}.log 2>&1
