import json, sys
from pathlib import Path
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
from commander_lab.qualification.current_boundary import midgame_rows
from commander_lab.qualification.current_boundary.materialization import load_effective_materialization  # noqa
fixtures = tuple(sys.argv[2:])
recs = {r["fixture_id"]: r for r in load_effective_materialization(Path(".")).denominator_records()}
out = Path(sys.argv[1])
doc = midgame_rows.execute_and_persist(workspace=Path("engine-bridge").resolve(), records=recs,
    candidate_commit="b479fe74fd1eaf899ff16c6a9203e74a91c0f339", runner_digest="local-dev",
    out_dir=out, fixtures=fixtures)
print(json.dumps(doc, indent=1, sort_keys=True))
