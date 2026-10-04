import json, sys
from pathlib import Path
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
from commander_lab.qualification.current_boundary import midgame_rows
from commander_lab.qualification.current_boundary.materialization import load_effective_materialization
recs = {r["fixture_id"]: r for r in load_effective_materialization(Path(".")).denominator_records()}
doc = midgame_rows.execute_and_persist(workspace=Path("engine-bridge").resolve(), records=recs,
    candidate_commit="b479fe74fd1eaf899ff16c6a9203e74a91c0f339", runner_digest="local-dev",
    out_dir=Path(sys.argv[1]))
json.dump(doc, open(sys.argv[2], "w"), indent=1, sort_keys=True)
print(doc["rows_declared"], doc["rows_verified"])
for k, r in sorted(doc["rows"].items()):
    if not r["verified"]: print("NOT VERIFIED", k, r["detail"][:200])
