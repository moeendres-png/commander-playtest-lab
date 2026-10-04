import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from commander_lab.qualification.current_boundary import bridge_launcher as bl, game_driver as gd
cand = sys.argv[1]
plan = bl.build_launch_plan(cand, lane="compat", xmage_workspace=Path("/home/user/wt-main/engine-bridge"),
                            forge_workspace=Path("/home/user/forge-20e3"))
proc = bl.launch(plan, timeout_s=300.0)
orig = gd.poll_decision
def spy(proc_, game_id, *, seat_count, candidate):
    f = orig(proc_, game_id, seat_count=seat_count, candidate=candidate)
    raw = f["raw"]
    keys = {k: raw.get(k) for k in ("decision_kind","actor_id","actor_seat","player_id","prompt","decision_offset") if k in raw}
    if isinstance(raw.get("decision"), dict): keys.update({"d."+k: v for k, v in raw["decision"].items() if k in ("kind","actor","seat","prompt","revision")})
    # ask every seat to see which ones get this decision
    who = []
    for s in gd._SEATS[:seat_count]:
        r = proc_.request("get_legal_actions", {"actor_id": s}, game_id=game_id, timeout_s=60.0)
        p = gd._payload(r) if gd._first_ok(r) else None
        n = gd.normalize_decision_frame(candidate, s, p) if p else None
        who.append((s, bool(n) and n["decision"]["kind"]))
    print("FRAME seat=", f["seat"], keys, "answerable_by=", who, "opts=", [a.get("action_type") or a.get("label") for a in f["actions"]][:4], flush=True)
    return f
gd.poll_decision = spy
r = gd.drive_commander_game(proc, candidate=cand, player_count=4, seed=424242, drive_to="priority", max_steps=20)
print("failure", r.failure)
