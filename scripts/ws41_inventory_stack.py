#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'qualification/ws32/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_2.json'
b=json.loads(p.read_text())
rows=[]
for r in b['records']:
    objs={o['semantic_id']:o for o in r.get('semantic_objects',[])}
    for s in r.get('stack_state',[]):
        sid=s.get('source_semantic_id')
        obj=objs.get(sid,{})
        rows.append({
            'fixture_id':r['fixture_id'],
            'source_semantic_id':sid,
            'card_identity':obj.get('card_identity'),
            'cast_complete':s.get('cast_complete'),
            'costs_paid':s.get('costs_paid'),
            'targets':s.get('targets'),
            'modes':s.get('modes'),
            'stack_row':s,
            'decisions':[{'family':d.get('decision_family'),'semantic_value':d.get('selection',{}).get('semantic_value'),'causal_step_id':d.get('causal_step_id')} for d in r.get('decision_script',[])],
        })
print(json.dumps({'count':len(rows),'rows':rows},ensure_ascii=False,sort_keys=True,indent=2))
