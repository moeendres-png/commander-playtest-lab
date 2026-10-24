"""#999 P9: Die 147 v11-instabilen Szenario-Keys auf Pin v13 zweimal spielen
und die semantischen Hashes vergleichen. Aufruf: p9_replay.py <out_dir>"""
import json, sys
from pathlib import Path
ROOT = Path('/home/hatch/workspace/github/wt-999')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from run_full_game_deck_comparison import load_deck, distinct_contenders
from commander_lab.engine.rules.full_game_comparison import DeckComparisonSpec, plan_comparison_cases
from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import XmageFullGameBatchRunner, command_with_games_per_jvm

PIN = '90f5c4d3f8'  # wird unten durch vollen Hash ersetzt
import subprocess
PIN = subprocess.check_output(['git', '-C', '/home/hatch/workspace/github/wt-mage-v13', 'rev-parse', 'HEAD']).decode().strip()
JAR = '/home/hatch/workspace/tmp/999/bridge_v13.jar'
M4 = Path('/home/hatch/workspace/tmp/m4')
keys = json.load(open('/home/hatch/workspace/tmp/999/p9_keys.json'))
want = {f"{k['candidate_id']}|seed={k['seed']}|seat={k['seat']}" for k in keys}
OPP = [ROOT / 'data/decks/precons/2026_doom_prevails.json',
       ROOT / 'data/decks/precons/2021_elven_empire.json',
       ROOT / 'data/decks/precons/2022_painbow.json']
cases = []
for name, base, bundles in (
    ('chulane', M4 / 'chulane.json', ['chulane_CA.json', 'chulane_CB.json', 'chulane_CC.json']),
    ('rogshai', M4 / 'rogshai.json', ['rogshai_RA.json', 'rogshai_RB.json', 'rogshai_RC.json'])):
    seeds = sorted({k['seed'] for k in keys if k['candidate_id'].startswith(f'custom/{name}')})
    spec = DeckComparisonSpec(
        comparison_id=f'custom/{name}',
        contenders=distinct_contenders([load_deck(base)] + [load_deck(M4 / "bundles" / b) for b in bundles]),
        opponents=tuple(load_deck(p) for p in OPP),
        seeds=tuple(seeds), rotate_seats=True, xmage_commit=PIN)
    mine = [c for c in plan_comparison_cases(spec) if c.case_id in want]
    print(f'{name}: {len(mine)} der Keys als Cases gefunden', flush=True)
    cases.extend(mine)
print(f'Cases gesamt: {len(cases)} von {len(want)} Keys', flush=True)
missing = want - {c.case_id for c in cases}
if missing: print('FEHLENDE Keys:', sorted(missing)[:5], flush=True)
base_cmd = ('java', '-XX:+UseSerialGC', '-jar', JAR, 'full-game')
cmd = command_with_games_per_jvm(base_cmd, 6)
runner = XmageFullGameBatchRunner(
    XmageFullGameRunner(cmd, private_card_repository=True), sys.argv[1], games_per_jvm=6)
report = runner.run(tuple(cases), workers=2, parallelism='thread')
print(f'P9-Lauf fertig: {report.completed_cases} ok, {report.failed_cases} fehlgeschlagen, {report.resumed_cases} uebernommen', flush=True)
