import json, sys, time
from pathlib import Path
ROOT = Path(sys.argv[1]); jar = Path(sys.argv[2]); seed = int(sys.argv[3]); decks = sys.argv[4:]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
from benchmark_xmage_full_games import _play, _setup, bridge_command
setup = _setup(tuple(Path("data/decks/precons") / f"{d}.json" for d in decks))
t = time.monotonic()
row = _play(bridge_command(jar, []), "pod:" + "+".join(decks), setup, seed, True)
row["total_wall_s"] = round(time.monotonic() - t, 1)
print(json.dumps(row)[:600])
