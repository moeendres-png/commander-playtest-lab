import json, sys, collections
from pathlib import Path
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
import run_current_boundary_qualification as rq
from commander_lab.qualification.current_boundary import forge_scenario_lane as fl
from commander_lab.qualification.current_boundary.materialization import load_effective_materialization
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_forge_authority
forge = rq.resolve_forge_workspace(sys.argv[1])
recs = {r["fixture_id"]: r for r in load_effective_materialization(Path(".")).denominator_records()}
doc = fl.execute_and_persist(forge_workspace=Path(forge["workspace"]), records=recs,
    candidate_commit=canonical_forge_authority()["rules_core_commit"], runner_digest="local-dev",
    out_dir=Path(sys.argv[2]), lab_root=Path(".").resolve())
json.dump(doc, open(sys.argv[3], "w"), indent=1, sort_keys=True)
print(json.dumps({k: v for k, v in doc.items() if k != "rows"}, sort_keys=True)[:1500])
