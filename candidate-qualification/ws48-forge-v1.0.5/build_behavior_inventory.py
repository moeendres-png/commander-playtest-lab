#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, hashlib, json
from pathlib import Path
from typing import Any

WS47_SHA="0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"

def canon(v:Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(v:Any)->str: return hashlib.sha256(canon(v).encode()).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--materialization',type=Path,required=True); ap.add_argument('--denominator',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    raw=a.materialization.read_bytes(); assert hashlib.sha256(raw).hexdigest()==WS47_SHA
    doc=json.loads(raw); ids=list(json.loads(a.denominator.read_text())['fixture_ids']); assert len(ids)==107 and len(set(ids))==107
    by={r['fixture_id']:r for r in doc['records']}; assert all(fid in by for fid in ids)
    rows=[]; families=collections.Counter(); selectors=collections.Counter(); steps=collections.Counter(); events=collections.Counter(); modes=collections.Counter(); decision_count=0
    for idx,fid in enumerate(ids,1):
        r=by[fid]; ds=list(r.get('decision_script') or []); np=list(r.get('native_procedure') or []); ee=r.get('expected_events') or {}
        drows=[]
        for d in ds:
            decision_count+=1; families[d['decision_family']]+=1; selectors[d['selection']['selector_kind']]+=1
            drows.append({'decision_family':d['decision_family'],'actor':d['actor'],'selector_kind':d['selection']['selector_kind'],'semantic_value':d['selection']['semantic_value'],'causal_step_id':d['causal_step_id'],'forbidden_fallbacks':d['forbidden_fallbacks']})
        prows=[]
        for p in np:
            st=p.get('step') or p.get('operation') or p.get('action') or p.get('kind') or p.get('step_id') or '<UNNAMED>'
            steps[str(st)]+=1; prows.append(p)
        for ev in ee.get('required_events') or []: events[str(ev).split(':',1)[0]]+=1
        modes[r['execution_entry_mode']]+=1
        rows.append({'index':idx,'fixture_id':fid,'fixture_family':r['fixture_family'],'execution_entry_mode':r['execution_entry_mode'],'decision_script':drows,'native_procedure':prows,'expected_events':ee,'terminal_postconditions':r.get('terminal_postconditions') or [],'negative_fallback_probe':r.get('negative_fallback_probe'),'priority_script':r.get('priority_script') or [],'action_cost_state':r.get('action_cost_state') or [],'record_obligation_digest':r['obligation_digest']})
    out={'schema_version':'commander-lab.ws48-behavior-contract-inventory/1.0.0','status':'PASS','denominator':107,'fixture_ids':ids,'execution_entry_mode_counts':dict(sorted(modes.items())),'decision_count':decision_count,'decision_family_counts':dict(sorted(families.items())),'selector_kind_counts':dict(sorted(selectors.items())),'native_step_counts':dict(sorted(steps.items())),'required_event_prefix_counts':dict(sorted(events.items())),'rows':rows}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps({k:v for k,v in out.items() if k not in {'rows','fixture_ids'}},indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
