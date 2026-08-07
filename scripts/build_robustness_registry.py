#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from commander_lab.robustness import build_registry, run_policy_tournament

p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--output',default='artifacts/phase12_15')
a=p.parse_args(); root=Path(a.root).resolve(); out=root/a.output; out.mkdir(parents=True,exist_ok=True)
registry=build_registry(root)
tournament=run_policy_tournament(registry['opponent_variants'])
(out/'PILOT_AND_POLITICS_REGISTRY.json').write_text(json.dumps(registry,indent=2)+"\n")
(out/'OPPONENT_UNCERTAINTY_REGISTRY.json').write_text(json.dumps({'schema_version':1,'variants':registry['opponent_variants']},indent=2)+"\n")
(out/'POLICY_TOURNAMENT_RESULT.json').write_text(json.dumps(tournament,indent=2)+"\n")
(root/'data/robustness/pilot_and_politics_registry.json').write_text(json.dumps(registry,indent=2)+"\n")
(root/'data/robustness/policy_tournament_result.json').write_text(json.dumps(tournament,indent=2)+"\n")
print(json.dumps({'pilots':len(registry['pilot_profiles']),'politics':len(registry['politics_regimes']),'opponent_variants':len(registry['opponent_variants']),'top_robust':tournament['rankings'][:3]},indent=2))
