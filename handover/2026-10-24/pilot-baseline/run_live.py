"""#999 M4/M5/M6: Live-Mitschnitt der Pilot-Entscheidungen ueber den
recording-Hook von scripts/pilot_decision_report.py (request/answer/pilot_s),
eigene Reduktion danach. Aufruf: run_live.py <out_dir> <pod_von> <pod_bis>"""
import json, sys
from pathlib import Path
ROOT = Path('/home/hatch/workspace/github/wt-999')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import benchmark_xmage_full_games as bench
from precon_pod_sweep import plan_pods
from pilot_decision_report import recording
from commander_lab.engine.rules.full_game import XmageFullGameRunner

JAR = '/home/hatch/workspace/tmp/999/bridge_v13.jar'
out = Path(sys.argv[1]); pod_from, pod_to = int(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
PRE, PROXY = ROOT / 'data/decks/precons', ROOT / 'data/decks/precon_variants'
proxy_stems = {p.stem for p in PROXY.glob('*.json')}
deck_files = {}
for p in sorted(PRE.glob('*.json')):
    if p.stem not in proxy_stems: deck_files[p.stem] = p
for p in sorted(PROXY.glob('*.json')): deck_files[p.stem] = p
pods = plan_pods(sorted(deck_files), 4, 1)
cmd = ('java', '-XX:+UseSerialGC', '-jar', JAR, 'full-game')
for i, decks in enumerate(pods):
    if not (pod_from <= i < pod_to): continue
    target = out / f'live_pod-{i:03d}.json'
    if target.exists(): print(f'pod-{i:03d} existiert, uebersprungen', flush=True); continue
    scenario, decks_t, pilots = bench._setup(tuple(deck_files[n].relative_to(ROOT) for n in decks))
    scenario = scenario.model_copy(update={'seed': 1})
    runner = XmageFullGameRunner(cmd, private_card_repository=True)
    records = []
    try:
        with recording(records):
            result = runner.run(scenario=scenario, decks=decks_t, pilots=pilots)
        status, sem = 'ok', result.semantic_transcript_sha256
    except Exception as exc:
        status, sem = f'failed: {type(exc).__name__}: {exc}'[:200], None
    target.write_text(json.dumps({'pod': f'pod-{i:03d}', 'seed': 1, 'status': status,
                                  'semantic': sem, 'records': records}))
    print(f'pod-{i:03d}: {status}, {len(records)} Entscheidungen', flush=True)
print('LIVE FERTIG', flush=True)
