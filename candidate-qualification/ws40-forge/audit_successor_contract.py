#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

EXPECTED_FILE_SHA = '0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261'
EXPECTED_CANONICAL = 'ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23'


def nonempty(v):
    return v not in (None, '', [], {})


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--materialization',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    raw=args.materialization.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==EXPECTED_FILE_SHA
    doc=json.loads(raw)
    assert doc['schema_version']=='commander-lab.semantic-fixture-materialization/1.0.2'
    assert doc['canonical_bundle_digest']==EXPECTED_CANONICAL
    records=[r for r in doc['records'] if r.get('fixture_family')!='actual_card' or r.get('fixture_id')=='CARD_02']
    assert len(records)==107

    entry=collections.Counter(r['execution_entry_mode'] for r in records)
    families=collections.Counter(r['fixture_family'] for r in records)
    decisions=collections.Counter()
    surfaces=collections.Counter()
    zones=collections.Counter()
    commander_prior=collections.Counter()
    player_counts=collections.Counter(len(r.get('players') or []) for r in records)
    special=[]
    for r in records:
        for d in r.get('decision_script') or []:
            decisions[d.get('decision_family','<missing>')]+=1
        for key in (
            'deck_state','commander_state','semantic_objects','temporal_state','knowledge_state','rules_randomness',
            'combat_state','stack_state','continuous_rules_effects','extra_turn_creation','elimination_trigger',
            'zone_move_event','setup_validation'):
            if nonempty(r.get(key)): surfaces[key]+=1
        for o in r.get('semantic_objects') or []:
            zones[o.get('zone','<missing>')]+=1
        for c in (r.get('commander_state') or {}).get('commanders') or []:
            commander_prior[int(c.get('prior_command_zone_cast_count',0))]+=1
        flags=[]
        cs=r.get('combat_state') or {}
        if nonempty(cs): flags.append('combat')
        if nonempty(r.get('stack_state')): flags.append('stack')
        if nonempty(r.get('continuous_rules_effects')): flags.append('continuous')
        if nonempty(r.get('extra_turn_creation')): flags.append('extra_turn')
        if nonempty(r.get('elimination_trigger')): flags.append('elimination')
        if nonempty(r.get('zone_move_event')): flags.append('zone_move')
        if nonempty(r.get('knowledge_state')): flags.append('knowledge')
        if flags:
            special.append({'fixture_id':r['fixture_id'],'fixture_family':r['fixture_family'],'flags':flags,'decision_families':sorted({d.get('decision_family') for d in r.get('decision_script') or [] if d.get('decision_family')})})
    result={
        'schema_version':'ws40-successor-contract-surface-audit/1.0.0',
        'denominator':len(records),
        'entry_modes':dict(sorted(entry.items())),
        'fixture_families':dict(sorted(families.items())),
        'player_counts':dict(sorted(player_counts.items())),
        'decision_families':dict(sorted(decisions.items())),
        'nonempty_state_surfaces':dict(sorted(surfaces.items())),
        'semantic_object_zones':dict(sorted(zones.items())),
        'commander_prior_cast_counts':dict(sorted(commander_prior.items())),
        'special_records':special,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='special_records'},indent=2,sort_keys=True))
    print('SPECIAL_RECORD_COUNT',len(special))
    for row in special:
        print(json.dumps(row,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
