from __future__ import annotations
import hashlib, importlib.util, json, os, re, subprocess, sys, tempfile, unittest, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
Q=ROOT/'qualification/ws31'; I=Q/'input'; G=Q/'generated'
KNOWN_SHA='8dcc2bd8460f23f42a86b8db9c2b96a880f76219fad6ba194d1f1009acf09bbe'
CR_SHA='9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c'
def loadmod(name,path):
 s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
class TestWS31Static(unittest.TestCase):
 def test_source_lock(self):
  d=json.loads((Q/'WS31_SOURCE_LOCK.json').read_text()); self.assertEqual(d['base_commit'],'362d9351f749b6f49d67cd1ef4eed298b8922b68'); self.assertEqual(d['base_tree'],'e510af2fd8a05f7db874781e3182a6bf3c062fc4'); self.assertEqual(d['known_actual_card_universe']['count'],1385); self.assertEqual(d['known_actual_card_universe']['name_set_sha256'],KNOWN_SHA); self.assertEqual(d['physical_inventory']['identity_count'],1338); self.assertEqual(d['rogshai_current']['unique_identities'],87); self.assertEqual(d['kaervek_current']['unique_identities'],77); self.assertEqual(d['unknown_real_opponent_slots'],142); self.assertEqual(d['current_cr_pdf_sha256'],CR_SHA)
 def test_exact_inputs(self):
  raw=zlib.decompress((I/'KNOWN_ACTUAL_CARD_IDENTITY_MANIFEST_1385.txt.zlib').read_bytes()); self.assertEqual(hashlib.sha256(raw).hexdigest(),KNOWN_SHA); self.assertEqual(len(raw.decode().splitlines()),1385); self.assertEqual(len((I/'OPPONENT_ONLY_47.txt').read_text().splitlines()),47); self.assertEqual(len((I/'MORCANT_HARD_KNOWN_54.txt').read_text().splitlines()),54); self.assertEqual(len((I/'COSMIC_HARD_KNOWN_4.txt').read_text().splitlines()),4)
 def test_taxonomy(self):
  d=json.loads((I/'WS04_RULES_PATH_TAXONOMY.json').read_text()); self.assertEqual(d['category_count'],15); self.assertEqual(d['path_count'],110); self.assertEqual(sum(len(c['paths']) for c in d['categories']),110)
 def test_ws29_baseline(self):
  d=json.loads(zlib.decompress((I/'WS29_REGRESSION_BASELINE.json.zlib').read_bytes())); self.assertEqual(d['record_count'],29); self.assertEqual([r['fixture_id'] for r in d['records']],[f'CARD_{i:02d}' for i in range(1,30)]); self.assertTrue(all(r['authority_status']=='FULL_CURRENT_ORACLE_LOCK' for r in d['records'])); self.assertTrue(all(r['discriminator_authority']=='PASS' for r in d['records']))
 def test_parser_preserves_mana_and_fields(self):
  m=loadmod('a',ROOT/'scripts/ws31_acquire_gatherer.py'); html=b'<img alt="{2}"><img alt="{W}"> Printed Oracle Card Name Test Mana Cost {2}{W} Type Creature - Human Rarity Rare rules Text Flying Artist A P/T 2 / 2 Set TST Number 1 Language English'; txt=m.visible_text(html); self.assertIn('{2}',txt); f=m.parse_section(txt,'Test'); self.assertTrue(f['parse_complete']); self.assertEqual(f['mana_cost'],'{2}{W}'); self.assertEqual(f['colors'],['W']); self.assertEqual(f['oracle_text'],'Flying')
 def test_incidence_separates_authority_and_heuristic(self):
  m=loadmod('mat',ROOT/'scripts/ws31_materialize.py'); r={'project_card_identity':'Test','semantic_identity':'x','faces':[{'oracle_text':'When this creature dies, shuffle your library.','type_line':'Creature','mana_cost':'{1}{G}'}]}; e=m.derive_incidence(r); self.assertTrue(any(x['path']=='normal triggers' and x['classification']=='AUTHORITY_DERIVED' for x in e)); self.assertTrue(any(x['path']=='shuffle' and x['classification']=='AUTHORITY_DERIVED' for x in e)); self.assertTrue(any(x['path']=='zone-change semantics' and x['classification']=='HEURISTIC_DISCOVERY_ONLY' for x in e))
 def test_builder_exact_manifest(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'m.json'; subprocess.run([sys.executable,str(ROOT/'scripts/ws31_build_identity_manifest.py'),'--output',str(out)],cwd=ROOT,check=True,capture_output=True,text=True); d=json.loads(out.read_text()); self.assertEqual(d['record_count'],1385); self.assertEqual(d['semantic_identity_unique_count'],1385); self.assertEqual(d['name_set_sha256'],KNOWN_SHA)
class TestWS31Generated(unittest.TestCase):
 def setUp(self):
  if not (G/'WS31_RESULT.json').exists(): self.skipTest('generated authority artifacts not present')
 def test_terminal_denominator(self):
  d=json.loads((G/'KNOWN_ACTUAL_CARD_ORACLE_1385.json').read_text()); self.assertEqual(d['record_count'],1385); self.assertEqual(len(d['records']),1385); self.assertEqual(len({r['semantic_identity'] for r in d['records']}),1385); self.assertTrue(all(r['acquisition_status'] in {'PASS','UNKNOWN','FAIL_CLOSED'} for r in d['records']))
 def test_subsets(self):
  for fn,n in [('PHYSICAL_CARD_ORACLE_1338.json',1338),('CURRENT_ROGSHAI_ORACLE.json',87),('CURRENT_KAERVEK_ORACLE.json',77)]: self.assertEqual(json.loads((G/fn).read_text())['record_count'],n)
 def test_cr_and_runtime_credit(self):
  c=json.loads((G/'CURRENT_CR_LOCK.json').read_text()); self.assertEqual(c['status'],'PASS'); self.assertEqual(c['observed_sha256'],CR_SHA); cov=json.loads((G/'COVERAGE.json').read_text()); self.assertEqual(cov['runtime_functionality_credit'],0)
 def test_ws29_regression(self): self.assertEqual(json.loads((G/'WS29_REGRESSION.json').read_text())['status'],'PASS')
 def test_close_gate(self):
  r=json.loads((G/'WS31_RESULT.json').read_text()); self.assertIn(r['workstream_status'],{'PASS_CLOSED','UNKNOWN_CLOSED','OPEN'}); self.assertEqual(r['coverage']['terminal_acquisition_records'],1385)
  if os.environ.get('WS31_REQUIRE_CLOSE')=='1': self.assertIn(r['workstream_status'],{'PASS_CLOSED','UNKNOWN_CLOSED'}); self.assertEqual(r['coverage']['workstream_close_gate'],'PASS')
 def test_optional_full_pass(self):
  if os.environ.get('WS31_REQUIRE_FULL_PASS')!='1': self.skipTest('optional full PASS gate disabled')
  self.assertEqual(json.loads((G/'WS31_RESULT.json').read_text())['workstream_status'],'PASS_CLOSED')
if __name__=='__main__': unittest.main()
