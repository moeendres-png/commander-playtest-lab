#!/usr/bin/env bash
# M2 import proofs: one measure_precon_imports.py run per proof copy.
# Sequential (CPU rule). Shared warm workdir; only statuses are evidence.
set -u
source ~/workspace/tools/env.sh
cd ~/workspace/github/wt-m1-sweep
mkdir -p ~/workspace/tmp/m2/import_nachweis ~/workspace/tmp/m2/proofs_workdir
PY=~/workspace/venvs/commander-lab/bin/python
JAR=~/workspace/tmp/m1/bridge.jar
WD=~/workspace/tmp/m2/proofs_workdir
for dir in ~/workspace/tmp/m2/copies/*/; do
  name=$(basename "$dir")
  out=~/workspace/tmp/m2/import_nachweis/${name}.json
  if [ -f "$out" ]; then echo "SKIP $name (exists)"; continue; fi
  $PY scripts/measure_precon_imports.py --jar "$JAR" --workdir "$WD" \
      --deck-dir "$dir" --out "$out" > ~/workspace/tmp/m2/import_nachweis/${name}.log 2>&1
  echo "$name exit=$?"
done
echo "PROOFS-DONE"
