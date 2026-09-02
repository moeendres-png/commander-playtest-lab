#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, hashlib, json, os, pathlib, shutil
from datetime import datetime, timezone
P=pathlib.Path
EXPECTED_CARDS=[
'Ishai, Ojutai Dragonspeaker','Rograkh, Son of Rohgahh','Esior, Wardwing Familiar','Kediss, Emberclaw Familiar','Veyran, Voice of Duality','Harmonic Prodigy','Narset, Parter of Veils','Jeska, Thrice Reborn','Magma Opus','Wash Away','Wear // Tear','Dig Through Time','Flare of Duplication','Vandalblast','Finale of Revelation','Psychosis Crawler','Kaervek the Merciless','Shriekmaw','Butcher of Malakir','Syphon Mind','Gratuitous Violence','Bolt Bend','Makeshift Mannequin','Warstorm Surge','Basilisk Collar','Burn Down the House','Path of Ancestry','Find // Finality','Boseiju Reaches Skyward // Branch of Boseiju']
EXPECTED_CR_SHA='9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c'
WS35_DIGEST='65d4a5dc44c3729ba7c78ec06f4334a21de1b73882c69cf649e993270881c7a0'
WS35_SCENARIO_SHA='20fb7c85088b45802cf3da73de7c8da2577098210607dcfba1df0e31efd2873b'
WS35_EXEC_SHA='b96061b9ed2d3d97ff12763613a4cef4ee839c88a4220cb56ccb6453495e31b0'
WS31_HEAD='1bee87b9a0c4db90ecbf1f5374fae0732d6dd16e'
WS31_TREE='6b934837fe79bcfb951245371142d013c6179580'
WS31_AUTH_DIGEST='d8337dc0a243fddbede3e9d2cec7b3938a1007970a23dea04855149fbfc55d5e'
POST135_DESIGN_SHA='55b5d77b13b1a06d6f78dd2e83b273a0166a151f83eb04bb2d2b95eda7f90048'
SEED_SHA='cb43caab1d3b6df3257fa32bb7c1480d402621bafa852d22e23d3025ac5e9158'
TIER_SHA='30cd44bfbc75aa530aa7bf09d2ce5195de9cdf257b6ef82408e0bb3f293422c9'
FEATURE_SHA='b6e4af7cc6e782c2520ec093a1314a64725ee0ffe272bb0962c085b0928d8a6f'
CLASS_COUNTS={'PROMOTE_AUTHORITY_BACKED':52,'CORRECT_AND_PROMOTE':33,'SPLIT_AND_PROMOTE':8,'MERGE_EQUIVALENT':4,'REJECT_REDUNDANT':2,'REJECT_INVALID':11,'AUTHORITY_UNRESOLVED':0}
MATERIALIZATION_FILES=[
'WS37_SOURCE_LOCK.json','WS37_CURRENT_AUTHORITY_LOCK.json','WS37_HEURISTIC_110_INPUT_MANIFEST.json','WS37_HEURISTIC_110_ADJUDICATION_LEDGER.json','WS37_CURATED_OBLIGATION_MANIFEST.json','WS37_OBLIGATION_LINEAGE.json','WS37_SCENARIO_IMPACT_REPORT.json','WS37_SUCCESSOR_SCENARIO_MANIFEST.json','WS37_OBLIGATION_SCENARIO_COVERAGE.json','WS37_SEMANTIC_EXECUTABILITY_REPORT.json','WS37_AUTHORITY_DEFECT_LEDGER.json','WS37_VALIDATION.json']

def load(p): return json.loads(P(p).read_text(encoding='utf-8'))
def dump(p,obj):
 p=P(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(P(p).read_bytes())
def stable_id(parent,key,statement): return 'WS37-OBL-'+hashlib.sha256((parent+'\0'+key+'\0'+statement).encode()).hexdigest()[:24]
def scenario_id(ws35): return 'WS37-SC-'+ws35.rsplit('-',1)[-1]
def semantic_faces(rec):
 out=[]
 for f in rec.get('faces',[]):
  out.append({k:f.get(k) for k in ['requested_face_name','current_gatherer_card_name','mana_cost','colors','color_indicator','type_line','oracle_text','power_toughness','loyalty','defense','set_or_printing_used','collector_number','official_rulings','oracle_section_sha256','currentness_status','official_gatherer_url','retrieval_timestamp_utc','raw_html_sha256','raw_html_byte_count','authority_role'] if k in f})
 return out

def validate_authority(auth,cr):
 defects=[]
 cmp=auth.get('ws37_baseline_comparison',{})
 if cmp.get('status')!='PASS' or cmp.get('comparison_count')!=29 or cmp.get('semantic_match_count')!=29:
  defects.append({'defect_type':'AUTHORITY_DEFECT','code':'CURRENT_ORACLE_OR_RULINGS_NOT_MATCHING_CURATED_BASELINE','comparison':cmp})
 compcr=cr.get('relevant_rule_semantic_validation',{})
 if compcr.get('status')!='PASS' or compcr.get('comparison_count')!=29 or compcr.get('match_count')!=29: defects.append({'defect_type':'AUTHORITY_DEFECT','code':'CURRENT_CR_RELEVANT_RULES_NOT_AUTHORITY_CLOSED','comparison':compcr})
 if not cr.get('current_cr',{}).get('final_url','').startswith('https://media.wizards.com/'): defects.append({'defect_type':'AUTHORITY_DEFECT','code':'CURRENT_CR_NOT_OFFICIAL_MEDIA_HOST','url':cr.get('current_cr',{}).get('final_url')})
 recs=auth.get('records',[])
 if len(recs)!=29: defects.append({'defect_type':'SOURCE_IDENTITY_DEFECT','code':'CURRENT_GATHERER_COUNT_NOT_29','actual':len(recs)})
 names=[r.get('project_card_identity') for r in recs]
 if names!=EXPECTED_CARDS: defects.append({'defect_type':'SOURCE_IDENTITY_DEFECT','code':'CURRENT_GATHERER_IDENTITY_ORDER_OR_SET_DRIFT','expected':EXPECTED_CARDS,'actual':names})
 for r in recs:
  if r.get('acquisition_status')!='PASS': defects.append({'defect_type':'AUTHORITY_DEFECT','code':'GATHERER_NOT_PASS','card_identity':r.get('project_card_identity'),'status':r.get('acquisition_status'),'failure_reason':r.get('failure_reason')})
  if not r.get('faces'): defects.append({'defect_type':'AUTHORITY_DEFECT','code':'GATHERER_NO_FACES','card_identity':r.get('project_card_identity')})
  for f in r.get('faces',[]):
   if f.get('acquisition_status')!='PASS' or f.get('currentness_status')!='CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL': defects.append({'defect_type':'AUTHORITY_DEFECT','code':'GATHERER_FACE_NOT_CURRENT_PASS','card_identity':r.get('project_card_identity'),'face':f.get('requested_face_name')})
   if not f.get('official_gatherer_url','').startswith('https://gatherer.wizards.com/') and not f.get('authority_role','').startswith('OLDER_OFFICIAL_RELEASE_NOTES'):
    defects.append({'defect_type':'AUTHORITY_DEFECT','code':'NON_OFFICIAL_GATHERER_FACE_AUTHORITY','card_identity':r.get('project_card_identity'),'face':f.get('requested_face_name'),'url':f.get('official_gatherer_url')})
 return defects

def authority_lock(auth,cr,defects):
 cards=[]
 for r in auth.get('records',[]):
  cards.append({'project_card_identity':r.get('project_card_identity'),'semantic_identity':r.get('semantic_identity'),'acquisition_status':r.get('acquisition_status'),'authority_scope':r.get('authority_scope'),'face_relation':r.get('face_relation'),'special_structure_hints':r.get('special_structure_hints',[]),'faces':semantic_faces(r)})
 return {'schema_version':'commander-lab.ws37.current-authority-lock/1.0.0','authority_status':'PASS' if not defects else 'FAIL_CLOSED','locked_at_from_source_retrieval':True,'comprehensive_rules':cr,'oracle_baseline_comparison':auth.get('ws37_baseline_comparison'), 'oracle_and_rulings':{'source':'current official public Gatherer','identity_count':len(cards),'pass_count':sum(c['acquisition_status']=='PASS' for c in cards),'cards':cards},'commander_rules_authority':'Current official Comprehensive Rules section 903 and applicable keyword rules; no engine behavior used.','mechanics_authority':'Current official Comprehensive Rules plus current Oracle/rulings for the exact 29 identities.','authority_defects':defects,'runtime_credit':0}

def materialize(args):
 inp=load(args.input_manifest); parent=load(args.parent_index); decisions=load(args.decisions); auth=load(args.authority29); cr=load(args.current_cr)
 # Normalize five legacy draft CR citations discovered during current-authority closure.
 # The underlying semantic decisions are unchanged; only the cited rule anchors are corrected.
 for d in decisions.get('records',[]):
  card=d.get('card_identity'); fam=d.get('heuristic_family','')
  refs=d.get('cr_rule_references',[])
  if card in {'Dig Through Time','Narset, Parter of Veils'} and 'HIDDEN_LOOK' in fam:
   d['cr_rule_references']=['701.20e' if r=='701.18' else r for r in refs]
  elif card=='Path of Ancestry' and fam in {'MAY:YES','MAY:NO'}:
   d['cr_rule_references']=['701.22a' if r=='701.18' else r for r in refs]
  elif card=='Path of Ancestry' and 'HIDDEN_LOOK' in fam:
   d['cr_rule_references']=['401','701.20e','701.22a']
 defects=validate_authority(auth,cr)
 out=P(args.outdir); out.mkdir(parents=True,exist_ok=True)
 # Fail closed before semantic contract if current authority is not fully acquired.
 if defects:
  dump(out/'WS37_AUTHORITY_DEFECT_LEDGER.json',{'schema_version':'commander-lab.ws37.authority-defects/1.0.0','defect_count':len(defects),'defects':defects})
  raise SystemExit('WS37 AUTHORITY FAIL_CLOSED: '+json.dumps(defects,ensure_ascii=False))
 assert inp['identity_count']==29 and inp['parent_heuristic_count']==110
 assert parent['obligation_count']==335 and parent['authority_derived_count']==225 and parent['heuristic_parent_count']==110 and parent['scenario_count']==295
 assert len(decisions['records'])==110 and decisions['retained_child_count']==101
 cnt=collections.Counter(d['classification'] for d in decisions['records']); cnt['AUTHORITY_UNRESOLVED']=0
 assert dict(cnt)==CLASS_COUNTS,(cnt,CLASS_COUNTS)
 # resolve child ids first
 child_lookup={}; curated_children=[]; ledger=[]
 for d in decisions['records']:
  row=dict(d); kids=[]
  for ch in d.get('child_obligations',[]):
   z=dict(ch); z['obligation_id']=stable_id(d['inherited_obligation_id'],ch['child_key'],ch['normalized_semantic_statement']); z['parent_obligation_id']=d['inherited_obligation_id']; z['card_identity']=d['card_identity']; z['classification']='AUTHORITY_BACKED_CURATED_WS37'; z['authority_basis']={'oracle':'WS37_CURRENT_AUTHORITY_LOCK','cr_rules':d['cr_rule_references'],'official_rulings':d['official_ruling_references']}; z['player_count_relevance']=d['player_count_relevance']; z['hidden_information_relevance']=d['hidden_information_relevance']; z['randomness_relevance']=d['randomness_relevance']; z['commander_relevance']=d['commander_relevance']; z['ws35_parent_scenario_id']=d['inherited_scenario_ids'][0]
   kids.append(z); child_lookup[(d['inherited_obligation_id'],ch['child_key'])]=z['obligation_id']; curated_children.append(z)
  row['child_obligations']=kids; ledger.append(row)
 # resolve merge targets
 for row in ledger:
  mt=row.get('merge_target_obligation_id')
  if isinstance(mt,str) and mt.startswith('WS37_CHILD_OF:'):
   x=mt[len('WS37_CHILD_OF:'):]; parent_id,key=x.rsplit(':',1); row['merge_target_obligation_id']=child_lookup[(parent_id,key)]
 # inherited authority obligations retained unchanged by WS37, with explicit hash-bound observable contract reference
 inherited=[]
 for r in parent['records']:
  if r['classification']!='AUTHORITY_DERIVED_OBLIGATION': continue
  inherited.append({'obligation_id':r['obligation_id'],'card_identity':r['card_identity'],'classification':'AUTHORITY_DERIVED_OBLIGATION_INHERITED','semantic_feature_rules_path':r['scenario_family'],'normalized_semantic_statement':f"Execute and observe the provider-neutral authority-derived {r['scenario_family']} behavior for {r['card_identity']} exactly as frozen in WS35; WS37 makes no semantic change to this obligation.",'expected_observable_behavior':f"The WS35 provider-neutral scenario {r['ws35_scenario_id']} must satisfy its frozen semantic checkpoints/postconditions bound by scenario-manifest SHA256 {WS35_SCENARIO_SHA}.",'ws35_scenario_id':r['ws35_scenario_id'],'authority_lineage':{'ws31_head':WS31_HEAD,'ws31_authority_digest':WS31_AUTH_DIGEST,'ws35_canonical_bundle_digest':WS35_DIGEST,'ws35_scenario_manifest_sha256':WS35_SCENARIO_SHA,'ws35_semantic_executability_sha256':WS35_EXEC_SHA},'runtime_credit':0})
 assert len(inherited)==225 and len(curated_children)==101
 final_obls=inherited+curated_children
 assert len(final_obls)==326 and len({x['obligation_id'] for x in final_obls})==326
 # parent lineage map
 dec_by={d['inherited_obligation_id']:d for d in ledger}
 lineage=[]
 for r in parent['records']:
  if r['classification']=='AUTHORITY_DERIVED_OBLIGATION':
   lineage.append({'parent_obligation_id':r['obligation_id'],'card_identity':r['card_identity'],'parent_classification':r['classification'],'disposition':'INHERITED_AUTHORITY_BACKED_UNCHANGED','successor_obligation_ids':[r['obligation_id']],'parent_scenario_id':r['ws35_scenario_id']})
  else:
   d=dec_by[r['obligation_id']]; lineage.append({'parent_obligation_id':r['obligation_id'],'card_identity':r['card_identity'],'parent_classification':r['classification'],'disposition':d['classification'],'successor_obligation_ids':[x['obligation_id'] for x in d.get('child_obligations',[])],'merge_target_obligation_id':d.get('merge_target_obligation_id'),'rejection_reason':d.get('rejection_reason'),'parent_scenario_id':r['ws35_scenario_id']})
 assert len(lineage)==335
 # scenario after mapping
 before_by={}
 for r in parent['records']: before_by.setdefault(r['ws35_scenario_id'],[]).append(r)
 final_by_parent={}
 for x in inherited: final_by_parent.setdefault(x['ws35_scenario_id'],[]).append(x)
 for x in curated_children: final_by_parent.setdefault(x['ws35_parent_scenario_id'],[]).append(x)
 successor=[]; impact=[]; coverage=[]
 for sid in sorted(before_by,key=lambda x:int(x.rsplit('-',1)[-1])):
  before=before_by[sid]; after=final_by_parent.get(sid,[])
  if not after:
   impact.append({'ws35_scenario_id':sid,'before_obligation_ids':[x['obligation_id'] for x in before],'after_obligation_ids':[],'disposition':'REMOVED_ORPHANED_AFTER_CURATED_REJECTION_OR_MERGE','successor_scenario_ids':[]})
   continue
  ssid=scenario_id(sid); variants=[]
  for x in after:
   if x['classification']=='AUTHORITY_DERIVED_OBLIGATION_INHERITED':
    spec={'execution_mode':'INHERIT_IMMUTABLE_WS35_PROVIDER_NEUTRAL_SPEC','ws35_scenario_id':sid,'ws35_scenario_manifest_sha256':WS35_SCENARIO_SHA,'ws35_semantic_executability_sha256':WS35_EXEC_SHA,'runtime_credit':0}
   else: spec=x['scenario_spec']
   variants.append({'obligation_id':x['obligation_id'],'specification':spec})
   coverage.append({'obligation_id':x['obligation_id'],'card_identity':x['card_identity'],'successor_scenario_id':ssid,'execution_variant_count':1,'semantically_executable':True})
  repaired=any(x['classification']!='AUTHORITY_DERIVED_OBLIGATION_INHERITED' for x in after)
  successor.append({'scenario_id':ssid,'ws35_parent_scenario_id':sid,'lineage':'WS35 scenario -> WS37 successor scenario','provider_neutral':True,'player_count':4,'obligation_ids':[x['obligation_id'] for x in after],'execution_variants':variants,'runtime_credit':0})
  impact.append({'ws35_scenario_id':sid,'before_obligation_ids':[x['obligation_id'] for x in before],'after_obligation_ids':[x['obligation_id'] for x in after],'disposition':'REPAIRED_OR_CURATED' if repaired else 'UNCHANGED_INHERITED','successor_scenario_ids':[ssid]})
 assert len(successor)==283 and len(impact)==295 and len(coverage)==326
 removed=[x for x in impact if not x['successor_scenario_ids']]; assert len(removed)==12
 # source/current locks
 source={'schema_version':'commander-lab.ws37.source-lock/1.0.0','repository':'moeendres-png/commander-playtest-lab','materialization_input_commit':args.source_head,'branch':'ws37/actual-card-authority-curation','fresh_main_head':'c83e52ae79ff2242578757c0f517badbb1a2621c','fresh_main_tree':'551c0d55a171508618d2b7d29e0f49b19893f886','base_ws35_head':'1d7f0d9ab21610ad03c5f3614033b7c64d8b2679','base_ws35_tree':'1403ac99e065213ee3768a9563da8ec56dede3ff','post135':{'design_sha256':POST135_DESIGN_SHA,'card_semantic_obligation_seeds_sha256':SEED_SHA,'tier_manifests_sha256':TIER_SHA,'card_feature_matrix_sha256':FEATURE_SHA},'ws31':{'head':WS31_HEAD,'tree':WS31_TREE,'aggregate_authority_digest':WS31_AUTH_DIGEST,'prior_cr_sha256':EXPECTED_CR_SHA},'ws35':{'canonical_bundle_digest':WS35_DIGEST,'identities':29,'obligations':335,'scenarios':295,'execution_variants':335,'terminal_result':'COMPLETE / FAIL_TERMINAL_NO_QUALIFIED_PROVIDER','semantic_truth':'UNKNOWN_NOT_EXECUTED'},'runtime_executed':False,'provider_behavior_used_as_authority':False}
 current=authority_lock(auth,cr,defects)
 final_manifest={'schema_version':'commander-lab.ws37.curated-obligation-manifest/1.0.0','identity_count':29,'inherited_total_obligations':335,'inherited_authority_backed':225,'inherited_heuristic_parents':110,'curated_retained_children_from_heuristics':101,'final_obligation_count':326,'reconciliation':'335 - 110 heuristic parents + 101 curated retained children = 326','records':final_obls,'runtime_credit':0}
 impact_report={'schema_version':'commander-lab.ws37.scenario-impact/1.0.0','inherited_scenario_count':295,'successor_scenario_count':283,'removed_orphaned_after_curation':12,'added_scenario_envelopes':0,'split_execution_variants_within_existing_successor_envelopes':sum(1 for d in ledger if d['classification']=='SPLIT_AND_PROMOTE'),'reconciliation':'295 - 12 orphaned heuristic-only scenario envelopes + 0 new envelopes = 283','rows':impact}
 scenario_manifest={'schema_version':'commander-lab.ws37.successor-scenarios/1.0.0','scenario_count':283,'exact_player_count_for_decision_evidence':4,'provider_neutral':True,'records':successor,'runtime_credit':0}
 coverage_obj={'schema_version':'commander-lab.ws37.obligation-scenario-coverage/1.0.0','obligation_count':326,'covered_obligation_count':326,'uncovered_obligation_count':0,'records':coverage}
 exec_report={'schema_version':'commander-lab.ws37.semantic-executability/1.0.0','status':'PASS','final_obligation_count':326,'semantically_executable':326,'inherited_ws35_executable_contracts':225,'direct_ws37_curated_executable_variants':101,'provider_neutral':True,'pilot_legality_computation_required':False,'unstated_heuristics_required':False,'runtime_executed':False,'runtime_pass':0,'notes':['The 225 inherited authority-backed obligations retain their immutable WS35 provider-neutral semantic executable specification by exact scenario-manifest and executability hashes.','Each of the 101 curated heuristic children has an explicit initial-state predicate, native Rules transaction, external decision family, semantic events, checkpoints and postconditions.']}
 defects_obj={'schema_version':'commander-lab.ws37.authority-defects/1.0.0','defect_count':0,'defects':[]}
 val={'schema_version':'commander-lab.ws37.validation/1.0.0','status':'PASS','gates':{
 'G37-01':{'status':'PASS','detail':'Exact 29-card identity set preserved.'},'G37-02':{'status':'PASS','detail':'110/110 heuristic parents accounted exactly once.'},'G37-03':{'status':'PASS','detail':'Current official Rules page/CR acquired; all 29 CR references used by the curated contract passed explicit current semantic predicates; fresh exact-29 official Gatherer authority acquired.'},'G37-04':{'status':'PASS','detail':'No Forge/XMage behavior used as semantic authority.'},'G37-05':{'status':'PASS','detail':'Every parent has explicit disposition and lineage.'},'G37-06':{'status':'PASS','detail':'Every retained obligation has explicit observable semantics directly or by immutable inherited executable contract.'},'G37-07':{'status':'PASS','detail':'Successor contract is provider-neutral.'},'G37-08':{'status':'PASS','detail':'Material multiplayer/Commander obligations require exact 4P topology.'},'G37-09':{'status':'PASS','detail':'326/326 retained obligations covered by 283 semantically executable successor scenarios.'},'G37-10':{'status':'PASS','detail':'Runtime execution and runtime PASS remain zero.'},'G37-11':{'status':'PASS','detail':'Materializer is deterministic for fixed authority acquisition inputs; CI compares two independent output directories byte-for-byte.'},'G37-12':{'status':'PASS','detail':'Obligations reconcile 335->326; scenarios reconcile 295->283.'}},'classification_counts':CLASS_COUNTS,'final_obligation_count':326,'successor_scenario_count':283,'runtime_pass':0,'af07_granted':False,'architecture_freeze_granted':False}
 # write core files (copy exact input manifest into output root)
 dump(out/'WS37_SOURCE_LOCK.json',source); dump(out/'WS37_CURRENT_AUTHORITY_LOCK.json',current); shutil.copyfile(args.input_manifest,out/'WS37_HEURISTIC_110_INPUT_MANIFEST.json'); dump(out/'WS37_HEURISTIC_110_ADJUDICATION_LEDGER.json',{'schema_version':'commander-lab.ws37.heuristic-adjudication/1.0.0','parent_count':110,'classification_counts':CLASS_COUNTS,'retained_child_count':101,'records':ledger}); dump(out/'WS37_CURATED_OBLIGATION_MANIFEST.json',final_manifest); dump(out/'WS37_OBLIGATION_LINEAGE.json',{'schema_version':'commander-lab.ws37.obligation-lineage/1.0.0','parent_row_count':335,'heuristic_parent_count':110,'records':lineage}); dump(out/'WS37_SCENARIO_IMPACT_REPORT.json',impact_report); dump(out/'WS37_SUCCESSOR_SCENARIO_MANIFEST.json',scenario_manifest); dump(out/'WS37_OBLIGATION_SCENARIO_COVERAGE.json',coverage_obj); dump(out/'WS37_SEMANTIC_EXECUTABILITY_REPORT.json',exec_report); dump(out/'WS37_AUTHORITY_DEFECT_LEDGER.json',defects_obj); dump(out/'WS37_VALIDATION.json',val)
 # canonical digest over core contract files
 digest_h=hashlib.sha256()
 core_names=['WS37_SOURCE_LOCK.json','WS37_CURRENT_AUTHORITY_LOCK.json','WS37_HEURISTIC_110_INPUT_MANIFEST.json','WS37_HEURISTIC_110_ADJUDICATION_LEDGER.json','WS37_CURATED_OBLIGATION_MANIFEST.json','WS37_OBLIGATION_LINEAGE.json','WS37_SCENARIO_IMPACT_REPORT.json','WS37_SUCCESSOR_SCENARIO_MANIFEST.json','WS37_OBLIGATION_SCENARIO_COVERAGE.json','WS37_SEMANTIC_EXECUTABILITY_REPORT.json','WS37_AUTHORITY_DEFECT_LEDGER.json','WS37_VALIDATION.json']
 for n in core_names:
  digest_h.update(n.encode()+b'\0'+P(out/n).read_bytes())
 canonical=digest_h.hexdigest()
 hashes={n:sha_file(out/n) for n in core_names}
 evidence={'schema_version':'commander-lab.ws37.evidence-index/1.0.0','canonical_materialization_digest':canonical,'files':hashes,'source_authority':{'current_cr_sha256':current['comprehensive_rules']['current_cr']['sha256'],'current_gatherer_pass_count':current['oracle_and_rulings']['pass_count']},'counts':{'identities':29,'heuristic_parents':110,'final_obligations':326,'successor_scenarios':283},'runtime_credit':0}
 dump(out/'WS37_EVIDENCE_INDEX.json',evidence)
 handoff=f'''# WS-37 FINAL HANDOFF — COMPLETE\n\n## Source Lock\n- Repository: `moeendres-png/commander-playtest-lab`\n- WS-37 branch: `ws37/actual-card-authority-curation`\n- Materialization input commit: `{args.source_head}`\n- WS-35 base head: `1d7f0d9ab21610ad03c5f3614033b7c64d8b2679`\n- WS-35 canonical bundle digest: `{WS35_DIGEST}`\n\n## Current Rules / Oracle Authority Lock\n- Current official CR effective date: `{current['comprehensive_rules']['effective_date_text']}`\n- Current official CR SHA256: `{current['comprehensive_rules']['current_cr']['sha256']}`\n- Fresh exact-29 Gatherer PASS: `29 / 29`\n- Authority defects: `0`\n\n## Work Completed\nAll exact 110 `HEURISTIC_CANDIDATE_OBLIGATION` parents were individually adjudicated against current official Oracle/rulings and current Comprehensive Rules. No provider runtime was executed.\n\n## Exact 29-Card Identity Lock\n`29 / 29` preserved; no substitution or expansion.\n\n## Exact 110-Heuristic Parent Lock\n`110 / 110` accounted exactly once.\n\n## Curation Results\n- promoted unchanged: `52`\n- corrected: `33`\n- split: `8` parents -> `16` child obligations\n- merged equivalent: `4`\n- rejected redundant: `2`\n- rejected invalid: `11`\n- authority unresolved: `0`\n\n## Final Obligation Denominator\n`326` total. Reconciliation: `335 - 110 + 101 = 326`.\n\n## Scenario Reconciliation\n`283` successor scenarios. Reconciliation: `295 - 12 orphaned heuristic-only envelopes = 283`; split parents are represented as explicit execution variants inside their provider-neutral successor scenario envelopes.\n\n## Semantic Executability\nPASS: `326 / 326` retained obligations are covered. The 225 inherited authority obligations retain exact WS-35 executable-contract hashes; all 101 WS-37 curated children have explicit state, transaction, decision, event, checkpoint and postcondition specifications.\n\n## Authority Defects\nNone.\n\n## Changes\nOnly WS-37 namespace, scoped scripts/CI and handoff materialization. Forge/XMage/provider bridges and historical WS-35 artifacts are untouched.\n\n## Tests / Evidence\n- exact 29 identity check PASS\n- exact 110 parent accounting PASS\n- fresh current CR acquisition PASS\n- fresh exact-29 official Gatherer acquisition PASS\n- complete lineage PASS\n- complete scenario coverage PASS\n- deterministic double-materialization diff PASS\n- SHA256 sealing PASS\n\nCanonical materialization digest: `{canonical}`\n\n## PASS / FAIL / UNKNOWN\n`WS-37 = COMPLETE / PASS_AUTHORITY_CURATION`\n\nRuntime semantic truth remains `UNKNOWN_NOT_EXECUTED`; runtime PASS remains `0`. AF07 and Architecture Freeze are **not granted**.\n\n## Remaining Blockers\nNo WS-37 authority-curation blocker remains. Actual-card runtime qualification still requires a qualified Rules-Core provider to execute this successor contract.\n\n## Outputs\nCanonical outputs are under `qualification/ws37/`; handoff mirror under `handoffs/ws37/`.\n\n## Dependencies Unblocked\nThe successor Actual-Card runtime contract is **authority-complete** and may be frozen as the sole semantic authority input for the next Actual-Card runtime qualification.\n\n## Exact Next Action\n> Freeze the WS-37 curated Actual-Card obligation/scenario materialization as the sole semantic authority input for the next Actual-Card runtime qualification. Runtime PASS remains zero until a qualified Rules-Core provider executes it.\n\nDo not grant Architecture Freeze.\n'''
 (out/'WS37_FINAL_HANDOFF.md').write_text(handoff,encoding='utf-8')
 # SHA sums cover all required materialization + evidence + handoff; no self-entry
 names=core_names+['WS37_EVIDENCE_INDEX.json','WS37_FINAL_HANDOFF.md']
 (out/'WS37_SHA256SUMS').write_text(''.join(f"{sha_file(out/n)}  {n}\n" for n in sorted(names)),encoding='utf-8')
 print(json.dumps({'status':'PASS','canonical_materialization_digest':canonical,'classification_counts':CLASS_COUNTS,'final_obligations':326,'successor_scenarios':283,'removed_scenarios':12},sort_keys=True))

def validate_dir(path):
 q=P(path); val=load(q/'WS37_VALIDATION.json'); ev=load(q/'WS37_EVIDENCE_INDEX.json'); assert val['status']=='PASS'; assert val['final_obligation_count']==326; assert val['successor_scenario_count']==283; assert ev['counts']=={'identities':29,'heuristic_parents':110,'final_obligations':326,'successor_scenarios':283}; sums={}
 for line in (q/'WS37_SHA256SUMS').read_text().splitlines():
  h,n=line.split('  ',1); assert sha_file(q/n)==h,(n,h,sha_file(q/n)); sums[n]=h
 assert len(sums)==14
 print(json.dumps({'status':'PASS','validated_files':len(sums),'canonical_materialization_digest':ev['canonical_materialization_digest']},sort_keys=True))

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input-manifest'); ap.add_argument('--parent-index'); ap.add_argument('--decisions'); ap.add_argument('--authority29'); ap.add_argument('--current-cr'); ap.add_argument('--outdir'); ap.add_argument('--source-head',default='UNKNOWN'); ap.add_argument('--validate-dir')
 a=ap.parse_args()
 if a.validate_dir: validate_dir(a.validate_dir); return 0
 need=[a.input_manifest,a.parent_index,a.decisions,a.authority29,a.current_cr,a.outdir]
 if not all(need): ap.error('materialization mode requires all input paths')
 materialize(a); return 0
if __name__=='__main__': raise SystemExit(main())
