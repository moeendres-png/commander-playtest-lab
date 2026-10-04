import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from commander_lab.qualification.current_boundary import bridge_launcher as bl, game_driver as gd
cand = sys.argv[1]
plan = bl.build_launch_plan(cand, lane="compat", xmage_workspace=Path("/home/user/wt-main/engine-bridge"), forge_workspace=Path("/home/user/forge-20e3"))
proc = bl.launch(plan, timeout_s=300.0)
for m in ("start_engine","get_provider_version","get_capabilities"): proc.request(m, {})
hs=[]
for i in range(4):
    p=gd._payload(proc.request("import_deck", {"deck": gd.build_deck(f"{cand}-wsr22-deck-{i+1}")}))
    hs.append(p["deck_handle"]["handle_id"])
sup = gd._declares_seed_support(proc)
c = proc.request("create_commander_game", gd._create_request("g1", hs, 424242, sup), game_id="g1", timeout_s=300)
print(json.dumps(gd._payload(c), indent=1)[:2500])
proc.request("start_game", {}, game_id="g1", timeout_s=300)
st = proc.request("get_game_state", {"observer_player_id": "p1"}, game_id="g1", timeout_s=60)
pl = gd._payload(st); sv = pl.get("state", pl)
print("observer", {k: pl.get(k) for k in ("observer_player_id","observer_engine_player_id","observer_seat")})
print("players", [ {k: r.get(k) for k in ("player_id","seat","is_actor","name")} for r in (sv.get("players") or [])])
la = gd._payload(proc.request("get_legal_actions", {"actor_id": "p1"}, game_id="g1", timeout_s=60))
print("legal keys", sorted(la.keys()), la.get("actor_id"), la.get("actor_seat"))
