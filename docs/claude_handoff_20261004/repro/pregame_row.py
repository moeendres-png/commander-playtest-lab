import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from commander_lab.qualification.current_boundary import bridge_launcher as bl, full107
from commander_lab.qualification.current_boundary.materialization import load_effective_materialization
recs = {r["fixture_id"]: r for r in load_effective_materialization(Path(".")).denominator_records()}
cand = sys.argv[1]
plan = bl.build_launch_plan(cand, lane="compat", xmage_workspace=Path("/home/user/wt-mull/engine-bridge"), forge_workspace=Path("/home/user/forge-20e3"))
proc = bl.launch(plan, timeout_s=300.0)
r = full107.scripted_pregame_row(recs["PILOT_MULLIGAN"], proc, candidate=cand, runtime_identity={})
print(cand, r.outcome, r.reason)
print(" asked", r.evidence.get("observed_pregame_decisions"), "unmet", r.evidence.get("unmet_required_events"))
