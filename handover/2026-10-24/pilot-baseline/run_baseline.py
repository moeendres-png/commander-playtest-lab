"""#999 M1/M7 Baseline-Treiber: Precon-Pod-Plan (Seed 1) wie precon_pod_sweep
(186 Originale + 9 SYNTHETIC-Proxies = 195 Decks, 49 Pods) + Real-Pod.
Spiele ueber XmageFullGameBatchRunner (Transkript-Records, Resume-faehig).
Aufruf: run_baseline.py <out_dir> <pod_von> <pod_bis> <seeds,kommasep> [--real]"""
import sys
from pathlib import Path
ROOT = Path('/home/hatch/workspace/github/wt-999')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import benchmark_xmage_full_games as bench
from precon_pod_sweep import plan_pods
from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase, XmageFullGameBatchRunner, command_with_games_per_jvm)

JAR = '/home/hatch/workspace/tmp/999/bridge_v13.jar'
out_dir, pod_from, pod_to = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
seeds = [int(s) for s in sys.argv[4].split(',')]
with_real = '--real' in sys.argv

PRE, PROXY = ROOT / 'data/decks/precons', ROOT / 'data/decks/precon_variants'
proxy_stems = {p.stem for p in PROXY.glob('*.json')}
deck_files = {}
for p in sorted(PRE.glob('*.json')):
    if p.stem not in proxy_stems:
        deck_files[p.stem] = p
for p in sorted(PROXY.glob('*.json')):
    deck_files[p.stem] = p
pods = plan_pods(sorted(deck_files), 4, 1)
print(f'Pool: {len(deck_files)} Decks, Pods gesamt: {len(pods)}', flush=True)

jobs = []  # (pod_name, setup, seed)
for i, decks in enumerate(pods):
    if pod_from <= i < pod_to:
        setup = bench._setup(tuple(deck_files[n].relative_to(ROOT) for n in decks))
        for s in seeds:
            jobs.append((f'pod-{i:03d}', setup, s))
if with_real:
    setup = bench._setup(tuple(bench.smoke.REAL_DECK_PATHS))
    for s in seeds:
        jobs.append(('real', setup, s))
print(f'Jobs in diesem Lauf: {len(jobs)}', flush=True)

cases = []
for pod, (scenario, decks, pilots), seed in jobs:
    cases.append(FullGameBatchCase(
        case_id=f'{pod}|seed={seed}',
        scenario=scenario.model_copy(update={'seed': seed}),
        decks=decks, pilots=pilots))
base_cmd = ('java', '-XX:+UseSerialGC', '-jar', JAR, 'full-game')
cmd = command_with_games_per_jvm(base_cmd, 4)
runner = XmageFullGameBatchRunner(
    XmageFullGameRunner(cmd, private_card_repository=True), out_dir, games_per_jvm=4)
report = runner.run(tuple(cases), workers=2, parallelism='thread')
print(f'FERTIG: {report.completed_cases} ok, {report.failed_cases} fehlgeschlagen, {report.resumed_cases} uebernommen', flush=True)
