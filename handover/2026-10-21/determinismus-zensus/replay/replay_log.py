# Wegwerfskript (nicht committen): spielt EINEN Pod des Sweeps allein nach und schreibt jede beantwortete Entscheidung als JSON-Zeile.
# Aufruf (im Lab-Worktree): PYTHONPATH=src python3 replay_log.py SWEEP.json BRIDGE.jar POD_ID GAME_SEED OUT.jsonl
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import commander_lab.engine.rules.full_game as fg
import benchmark_xmage_full_games as bench
LOG = []
cls = [v for v in vars(fg).values() if isinstance(v, type) and hasattr(v, "request") and hasattr(v, "_prepare_private_directory")][0]
orig = cls.request
def spy(self, message_type, payload=None):
    res = orig(self, message_type, payload)
    LOG.append((message_type, payload, res))
    return res
cls.request = spy
ROOT = Path.cwd()
sweep = json.load(open(sys.argv[1]))
jar, pod, gseed, out = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
row = next(r for r in sweep["rows"] if r["pod"] == pod)
deck_dir = ROOT / "data/decks/precons"
setup = bench._setup(tuple((deck_dir / f"{n}.json").relative_to(ROOT) for n in row["decks"]))
res = bench._play(bench.bridge_command(Path(jar), []), pod, setup, gseed, True)
print(json.dumps({k: res.get(k) for k in ("status", "semantic", "decisions", "error")}))
cur = None
with open(out, "w") as f:
    for mt, pl, r in LOG:
        if mt == "submit_full_game_decision" and cur and cur["decision_id"] == pl["response"]["decision_id"]:
            lab = {o["option_id"]: o["label"] for o in cur["legal_options"]}
            f.write(json.dumps({"cls": cur["decision_class"], "seat": cur.get("seat"),
                                "src": (cur.get("source_object") or {}).get("source_name"),
                                "prompt": cur.get("prompt", "")[:120],
                                "opts": [o["label"] for o in cur["legal_options"]],
                                "sel": [lab.get(x, x) for x in pl["response"]["selected_option_ids"]]}) + "\n")
        if isinstance(r, dict) and r.get("decision"):
            cur = r["decision"]
