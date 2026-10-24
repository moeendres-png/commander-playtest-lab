"""#1001 Item 1: Einen Fall N-mal mit frischer JVM spielen, Hash + Transkript speichern.
Aufruf: run_rate.py <case: pod025|p9|control> <runs>  (skips vorhandene Run-Dateien)"""
import json, sys
from pathlib import Path
ROOT = Path('/home/hatch/workspace/github/wt-1001')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import benchmark_xmage_full_games as bench
from precon_pod_sweep import plan_pods
from commander_lab.engine.rules.full_game import XmageFullGameRunner

JAR = '/home/hatch/workspace/tmp/1001/bridge_v13.jar'
case, n = sys.argv[1], int(sys.argv[2])
out = Path(f'/home/hatch/workspace/tmp/1001/rate/{case}')
out.mkdir(parents=True, exist_ok=True)
PRE, PROXY = ROOT / 'data/decks/precons', ROOT / 'data/decks/precon_variants'
proxy_stems = {p.stem for p in PROXY.glob('*.json')}
deck_files = {}
for p in sorted(PRE.glob('*.json')):
    if p.stem not in proxy_stems: deck_files[p.stem] = p
for p in sorted(PROXY.glob('*.json')): deck_files[p.stem] = p
pods = plan_pods(sorted(deck_files), 4, 1)

if case in ('pod025', 'control'):
    idx = 25 if case == 'pod025' else 0
    scenario, decks, pilots = bench._setup(tuple(deck_files[nm].relative_to(ROOT) for nm in pods[idx]))
    scenario = scenario.model_copy(update={'seed': 1})
    case_id = f'pod-{idx:03d}|seed=1'
else:
    from run_full_game_deck_comparison import load_deck, distinct_contenders
    from commander_lab.engine.rules.full_game_comparison import DeckComparisonSpec, plan_comparison_cases
    import subprocess
    PIN = subprocess.check_output(['git', '-C', '/home/hatch/workspace/github/wt-mage-v13', 'rev-parse', 'HEAD']).decode().strip()
    M4 = Path('/home/hatch/workspace/tmp/m4')
    OPP = [ROOT / 'data/decks/precons/2026_doom_prevails.json',
           ROOT / 'data/decks/precons/2021_elven_empire.json',
           ROOT / 'data/decks/precons/2022_painbow.json']
    spec = DeckComparisonSpec(
        comparison_id='custom/rogshai',
        contenders=distinct_contenders([load_deck(M4 / 'rogshai.json')] + [load_deck(M4 / 'bundles' / b) for b in ['rogshai_RA.json', 'rogshai_RB.json', 'rogshai_RC.json']]),
        opponents=tuple(load_deck(p) for p in OPP),
        seeds=(3,), rotate_seats=True, xmage_commit=PIN)
    cs = [c for c in plan_comparison_cases(spec) if c.case_id == 'custom/rogshai#variant1|seed=3|seat=3']
    assert len(cs) == 1, f'P9-Case nicht gefunden: {len(cs)}'
    c = cs[0]
    scenario, decks, pilots, case_id = c.scenario, c.decks, c.pilots, c.case_id

cmd = ('java', '-XX:+UseSerialGC', '-jar', JAR, 'full-game')
for i in range(1, n + 1):
    target = out / f'run-{i:02d}.json'
    if target.exists():
        print(f'{case} run {i}: existiert, uebersprungen', flush=True); continue
    runner = XmageFullGameRunner(cmd, private_card_repository=True)
    try:
        result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
        sem = result.semantic_transcript_sha256
        rp = getattr(result, 'result_payload', None)
        tr = rp.get('transcript') if isinstance(rp, dict) else None
        if tr is None:
            tr = getattr(result, 'transcript', None)
        rec = {'case': case_id, 'run': i, 'status': 'ok', 'semantic': sem, 'transcript': tr}
    except Exception as exc:
        rec = {'case': case_id, 'run': i, 'status': f'failed: {type(exc).__name__}: {exc}'[:200], 'semantic': None, 'transcript': None}
    target.write_text(json.dumps(rec))
    print(f"{case} run {i}: {rec['status']}, hash {(rec['semantic'] or '')[:12]}", flush=True)
print('RATE FERTIG', flush=True)
