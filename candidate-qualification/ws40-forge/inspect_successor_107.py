#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, json
from pathlib import Path

def shape(v):
    if isinstance(v, dict): return {k: shape(v[k]) for k in sorted(v)}
    if isinstance(v, list):
        kinds=[]
        for x in v:
            s=shape(x)
            if s not in kinds: kinds.append(s)
        return [kinds]
    return type(v).__name__

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--materialization',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); doc=json.loads(a.materialization.read_text())
    rows=[r for r in doc['records'] if r.get('fixture_family')!='actual_card' or r.get('fixture_id')=='CARD_02']
    assert len(rows)==107
    result={'denominator':107,'families':collections.Counter(),'entry_modes':collections.Counter(),'records':[]}
    for r in rows:
        result['families'][r['fixture_family']]+=1; result['entry_modes'][r['execution_entry_mode']]+=1
        rec={
          'fixture_id':r['fixture_id'],'fixture_family':r['fixture_family'],'execution_entry_mode':r['execution_entry_mode'],
          'requested_state_digest':r['requested_state_digest'],'materialization_digest':r['materialization_digest'],
          'players':r.get('players'),'deck_state':r.get('deck_state'),'commander_state':r.get('commander_state'),
          'semantic_objects':r.get('semantic_objects'),'temporal_state':r.get('temporal_state'),'knowledge_state':r.get('knowledge_state'),
          'rules_randomness':r.get('rules_randomness'),'combat_state':r.get('combat_state'),'stack_state':r.get('stack_state'),
          'continuous_rules_effects':r.get('continuous_rules_effects'),'extra_turn_creation':r.get('extra_turn_creation'),
          'elimination_trigger':r.get('elimination_trigger'),'zone_move_event':r.get('zone_move_event'),'setup_validation':r.get('setup_validation'),
          'decision_script':r.get('decision_script'),'expected_result':r.get('expected_result'),
        }
        result['records'].append(rec)
    result['families']=dict(sorted(result['families'].items())); result['entry_modes']=dict(sorted(result['entry_modes'].items()))
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'denominator':107,'families':result['families'],'entry_modes':result['entry_modes']},sort_keys=True))
    for r in result['records']:
        print('REC',json.dumps({k:r[k] for k in ('fixture_id','fixture_family','execution_entry_mode','players','temporal_state','combat_state','stack_state','continuous_rules_effects','extra_turn_creation','elimination_trigger','zone_move_event','setup_validation','decision_script','expected_result')},sort_keys=True))
if __name__=='__main__': main()
