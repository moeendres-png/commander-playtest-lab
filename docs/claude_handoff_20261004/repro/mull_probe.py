import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from commander_lab.qualification.current_boundary import bridge_launcher as bl, game_driver as gd
cand = sys.argv[1]
plan = bl.build_launch_plan(cand, lane="compat", xmage_workspace=Path("/home/user/wt-mull/engine-bridge"),
                            forge_workspace=Path("/home/user/forge-20e3"))
proc = bl.launch(plan, timeout_s=300.0)
try:
    r = gd.drive_commander_game(proc, candidate=cand, player_count=4, seed=424242, drive_to="priority",
        max_steps=80, mulligan_plan=(("p1", False), ("p2", True), ("p3", True), ("p4", True), ("p1", True)))
    print("failure", r.failure)
    for e in r.decision_tape: print(" ", e.step, e.kind, e.actor, e.policy, e.chosen_option_id, e.note)
    print(json.dumps(r.terminal_facts.get("post_pregame_zone_counts"), indent=1))
finally:
    proc.close() if hasattr(proc, "close") else None
