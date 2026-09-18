#!/usr/bin/env python3
"""Extract a compact, exact WS-41 v1.0.3 provider surface for WS-42 remediation.

This does not reinterpret records and grants no runtime credit. It exists so
provider work can consume the immutable materialization through a small
auditable artifact while CI remains pinned to the WS-41 source lock.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

KEEP_TOP = (
    "fixture_id", "fixture_family", "materialization_digest", "requested_state_digest",
    "execution_entry_mode", "players", "deck_state", "commander_state", "semantic_objects",
    "temporal_state", "knowledge_state", "rules_randomness", "combat_state", "stack_state",
    "continuous_rules_effects", "extra_turn_creation", "elimination_trigger", "zone_move_event",
    "native_procedure", "decision_script", "setup_validation", "expected_events", "terminal_postconditions",
    "normalization", "execution_transaction_policy", "negative_fallback_probe",
)

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); doc=json.loads(a.input.read_text())
    rows=[]
    for r in doc['records']:
        if r.get('fixture_family')=='actual_card' and r.get('fixture_id')!='CARD_02':
            continue
        rows.append({k:r[k] for k in KEEP_TOP if k in r})
    if len(rows)!=107 or len({r['fixture_id'] for r in rows})!=107: raise SystemExit('DENOMINATOR_MISMATCH')
    out={
      'artifact_version':'commander-lab.ws42-contract-surface/1.0.1',
      'source_contract':doc['schema_version'],
      'canonical_bundle_digest':doc['canonical_bundle_digest'],
      'record_count':len(rows),
      'runtime_credit_granted':False,
      'records':rows,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'record_count':len(rows),'fixture_ids':[r['fixture_id'] for r in rows]},sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
