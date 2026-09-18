#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, unicodedata
from pathlib import Path

EXPECTED_CARDS=[
'Ishai, Ojutai Dragonspeaker','Rograkh, Son of Rohgahh','Esior, Wardwing Familiar','Kediss, Emberclaw Familiar','Veyran, Voice of Duality','Harmonic Prodigy','Narset, Parter of Veils','Jeska, Thrice Reborn','Magma Opus','Wash Away','Wear // Tear','Dig Through Time','Flare of Duplication','Vandalblast','Finale of Revelation','Psychosis Crawler','Kaervek the Merciless','Shriekmaw','Butcher of Malakir','Syphon Mind','Gratuitous Violence','Bolt Bend','Makeshift Mannequin','Warstorm Surge','Basilisk Collar','Burn Down the House','Path of Ancestry','Find // Finality','Boseiju Reaches Skyward // Branch of Boseiju']
FIELDS=['requested_face_name','current_gatherer_card_name','mana_cost','colors','color_indicator','type_line','oracle_text','power_toughness','loyalty','defense','official_rulings']

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,obj): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def norm_space(v): return ' '.join((v or '').split())
def norm_name(v):
    v=unicodedata.normalize('NFKD',v or '')
    v=''.join(ch for ch in v if not unicodedata.combining(ch)).casefold().replace('’',"'")
    return norm_space(v)
def canon_rulings(x):
    if not x: return []
    return sorted([{'date':norm_space(str(r.get('date',''))),'text':norm_space(str(r.get('text','')))} for r in x],key=lambda r:(r['date'],r['text']))
def canon_face(f):
    out={}
    for k in FIELDS:
        v=f.get(k)
        if k=='colors': out[k]=sorted(v or [])
        elif k=='official_rulings': out[k]=canon_rulings(v)
        else: out[k]=norm_space(v) if isinstance(v,str) or v is None else v
    return out
def face_key(f): return norm_name(f.get('requested_face_name') or f.get('current_gatherer_card_name'))
def canon_identity(rec):
    faces={face_key(f):canon_face(f) for f in rec.get('faces',[]) if face_key(f)}
    return {'project_card_identity':rec.get('project_card_identity'),'faces':faces}
def digest(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def records(obj):
    if isinstance(obj,dict):
        for key in ('records','cards','identities'):
            if isinstance(obj.get(key),list): return obj[key]
    if isinstance(obj,list): return obj
    raise SystemExit('AUTHORITY_DEFECT:BASELINE_OR_FRESH_RECORDS_NOT_FOUND')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--fresh',required=True); ap.add_argument('--baseline',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    fresh=load(a.fresh); base=load(a.baseline)
    fr=records(fresh); br=records(base)
    fmap={r.get('project_card_identity'):r for r in fr}; bmap={r.get('project_card_identity'):r for r in br}
    defects=[]; comparisons=[]
    if [r.get('project_card_identity') for r in fr] != EXPECTED_CARDS:
        defects.append({'code':'FRESH_EXACT_29_IDENTITY_ORDER_DRIFT','expected':EXPECTED_CARDS,'actual':[r.get('project_card_identity') for r in fr]})
    for name in EXPECTED_CARDS:
        f=fmap.get(name); b=bmap.get(name)
        if f is None: defects.append({'code':'FRESH_CARD_MISSING','card_identity':name}); continue
        if b is None: defects.append({'code':'WS31_BASELINE_CARD_MISSING','card_identity':name}); continue
        if f.get('acquisition_status')!='PASS': defects.append({'code':'FRESH_CARD_NOT_PASS','card_identity':name,'status':f.get('acquisition_status'),'failure_reason':f.get('failure_reason')})
        cf,cb=canon_identity(f),canon_identity(b)
        same=cf==cb
        row={'card_identity':name,'fresh_semantic_digest':digest(cf),'baseline_semantic_digest':digest(cb),'semantic_match':same,'fresh_face_keys':sorted(cf['faces']),'baseline_face_keys':sorted(cb['faces'])}
        if not same:
            diffs=[]
            for fk in sorted(set(cf['faces'])|set(cb['faces'])):
                if cf['faces'].get(fk)!=cb['faces'].get(fk):
                    diffs.append({'face':fk,'fresh':cf['faces'].get(fk),'baseline':cb['faces'].get(fk)})
            row['differences']=diffs
            defects.append({'code':'CURRENT_ORACLE_OR_RULINGS_DRIFT_FROM_CURATED_BASELINE','card_identity':name,'differences':diffs})
        comparisons.append(row)
    out=dict(fresh)
    out['ws37_baseline_comparison']={'status':'PASS' if not defects else 'FAIL_CLOSED','baseline':'WS31 KNOWN_ACTUAL_CARD_ORACLE_1385 @ 1bee87b9a0c4db90ecbf1f5374fae0732d6dd16e','exact_identity_count':29,'comparison_count':len(comparisons),'semantic_match_count':sum(r['semantic_match'] for r in comparisons),'records':comparisons,'defects':defects}
    dump(a.output,out)
    print(json.dumps({'status':out['ws37_baseline_comparison']['status'],'comparison_count':len(comparisons),'semantic_match_count':sum(r['semantic_match'] for r in comparisons),'defect_count':len(defects)},sort_keys=True))
    return 0 if not defects else 4
if __name__=='__main__': raise SystemExit(main())
