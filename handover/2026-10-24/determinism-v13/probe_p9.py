"""P9-Fall im Probe-Format spielen (pdr.recording + rows_of), fuer State-Diff-Beleg (a)."""
import sys, subprocess, json
from pathlib import Path
ROOT = Path('/home/hatch/workspace/github/wt-1001')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from run_full_game_deck_comparison import load_deck, distinct_contenders
from commander_lab.engine.rules.full_game_comparison import DeckComparisonSpec, plan_comparison_cases
import benchmark_xmage_full_games as bench
import pilot_decision_report as pdr
from determinism_probe import rows_of, write_dump
from commander_lab.engine.rules.full_game import XmageFullGameRunner

JAR = Path('/home/hatch/workspace/tmp/1001/bridge_v13.jar')
OUT = Path('/home/hatch/workspace/tmp/1001/probe_p9')
OUT.mkdir(parents=True, exist_ok=True)
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
c = [x for x in plan_comparison_cases(spec) if x.case_id == 'custom/rogshai#variant1|seed=3|seat=3'][0]
for name in ('a', 'b'):
    target = OUT / f'{name}.jsonl.gz'
    if target.exists():
        print(f'{name}: existiert, uebersprungen', flush=True); continue
    cmd = ('java', '-XX:+UseSerialGC', '-jar', str(JAR), 'full-game')
    runner = XmageFullGameRunner(cmd, private_card_repository=True)
    sink: list = []
    with pdr.recording(sink):
        result = runner.run(scenario=c.scenario, decks=c.decks, pilots=c.pilots)
    rows = rows_of(sink)
    write_dump(target, rows)
    print(f'{name}: semantic {result.semantic_transcript_sha256[:16]} decisions {len(rows)} -> {target}', flush=True)
print('PROBE P9 FERTIG', flush=True)
