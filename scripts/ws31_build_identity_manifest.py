#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re,unicodedata,zlib
from pathlib import Path
BASE='362d9351f749b6f49d67cd1ef4eed298b8922b68'
KNOWN_SHA='8dcc2bd8460f23f42a86b8db9c2b96a880f76219fad6ba194d1f1009acf09bbe'
ROG_BLOB='4db4174011e6ea0b07196e68165aa4549cff1971'; KAE_BLOB='beebc3cf50e32b29db5c1e594821f754da69249d'
def canon(s): return re.sub(r'\s+',' ',re.sub(r'\s*//\s*',' // ',unicodedata.normalize('NFC',s.strip())))
def norm(s): return unicodedata.normalize('NFKC',canon(s)).casefold()
def read(p): return [canon(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x.strip()]
def gitblob(p):
 b=Path(p).read_bytes(); return hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
def deck(p,want):
 if gitblob(p)!=want: raise SystemExit(f'deck blob drift: {p}')
 ns=[]
 for line in Path(p).read_text(encoding='utf-8').splitlines():
  m=re.match(r'^\d+\s+(.+)$',line.strip())
  if m: ns.append(canon(m.group(1)))
 return ns
def sid(s): return 'mtg:oracle-semantic:'+hashlib.sha256(('mtg-oracle-identity/v1\0'+norm(s)).encode()).hexdigest()
def main():
 a=argparse.ArgumentParser(); a.add_argument('--input-dir',default='qualification/ws31/input'); a.add_argument('--output',required=True); x=a.parse_args(); d=Path(x.input_dir)
 kp=d/'KNOWN_ACTUAL_CARD_IDENTITY_MANIFEST_1385.txt.zlib'; kb=zlib.decompress(kp.read_bytes())
 if hashlib.sha256(kb).hexdigest()!=KNOWN_SHA: raise SystemExit('1,385 identity manifest hash drift')
 known=[canon(x) for x in kb.decode('utf-8').splitlines() if x.strip()]
 opp=read(d/'OPPONENT_ONLY_47.txt'); mor=read(d/'MORCANT_HARD_KNOWN_54.txt'); cos=read(d/'COSMIC_HARD_KNOWN_4.txt')
 rog=deck('data/decks/rogshai_current.txt',ROG_BLOB); kae=deck('data/decks/opponents/kaervek/current/decklist.txt',KAE_BLOB)
 sets={k:{norm(n) for n in v} for k,v in {'known':known,'opp':opp,'morcant':mor,'cosmic':cos,'rog':rog,'kae':kae}.items()}
 for k,n in {'known':1385,'opp':47,'morcant':54,'cosmic':4,'rog':87,'kae':77}.items():
  if len(sets[k])!=n: raise SystemExit(f'{k} denominator drift {len(sets[k])}!={n}')
 if any(sets[k]-sets['known'] for k in ('opp','morcant','cosmic','rog','kae')): raise SystemExit('subset outside known universe')
 physical=sets['known']-sets['opp']
 if len(physical)!=1338: raise SystemExit('physical denominator drift')
 by={norm(n):n for n in known}; recs=[]
 for k in sorted(by):
  mem={'physical':k in physical,'current_rogshai':k in sets['rog'],'current_kaervek':k in sets['kae'],'morcant_hard_known':k in sets['morcant'],'cosmic_hard_known':k in sets['cosmic']}
  prov=[p for flag,p in [('physical','PHYSICAL_CANONICAL_INVENTORY_2026-08-20'),('morcant_hard_known','WS04_VIA_WS11_MORCANT_HARD_KNOWN'),('cosmic_hard_known','WS04_VIA_WS11_COSMIC_HARD_KNOWN'),('current_rogshai','REPO_ROGSHAI_CURRENT_AT_WS29_HEAD'),('current_kaervek','REPO_KAERVEK_CURRENT_AT_WS29_HEAD')] if mem[flag]]
  recs.append({'project_card_identity':by[k],'semantic_identity':sid(by[k]),'memberships':mem,'identity_provenance':prov})
 out={'schema_version':'commander-lab.ws31.actual-card-identity-manifest/1.0.0','source_lock_commit':BASE,'record_count':1385,'name_set_sha256':KNOWN_SHA,'semantic_identity_unique_count':len({r['semantic_identity'] for r in recs}),'unknown_real_opponent_slots_excluded':142,'records':recs}
 p=Path(x.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'record_count':len(recs),'name_set_sha256':KNOWN_SHA,'semantic_identity_unique_count':out['semantic_identity_unique_count']},sort_keys=True))
if __name__=='__main__': raise SystemExit(main())
