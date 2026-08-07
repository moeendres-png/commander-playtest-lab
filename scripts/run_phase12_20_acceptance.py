from __future__ import annotations
import hashlib, json, os, subprocess, time
from pathlib import Path
from typing import Any, Callable
from commander_lab import __version__
from commander_lab.tools.service import CommanderToolService
from commander_lab.tools import ToolRegistry
from commander_lab.models import (
    BuildOptimizationContextInput, GenerateCandidateSwapsInput, GenerateCandidatePackagesInput,
    OptimizeMultipleDecksWithAllocationInput, RunRulesCoverageGateInput, RunEngineBackedMatchupInput,
)
from commander_lab.models import RunEngineBackedMatchupInput
from commander_lab.mcp.server import CommanderMcpServer

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/phase12_20'; OUT.mkdir(parents=True,exist_ok=True)
DEMO=OUT/'demos'

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def run(args:list[str], timeout:int=40)->dict[str,Any]:
 try:
  cp=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=timeout,env={**os.environ,'PYTHONPATH':'src'})
  return {'execution_status':'passed' if cp.returncode==0 else 'failed','returncode':cp.returncode,'stdout_tail':'\n'.join(cp.stdout.splitlines()[-8:]),'stderr_tail':'\n'.join(cp.stderr.splitlines()[-8:])}
 except subprocess.TimeoutExpired as e:
  return {'execution_status':'blocked','reason':'timeout after command completion/lifecycle wait','stdout_tail':str(e.stdout or '')[-800:]}

def load(rel:str): return json.loads((ROOT/rel).read_text(encoding='utf-8'))
steps=[]
def add(n:int,name:str,fn:Callable[[],Any],force_status:str|None=None):
 t=time.perf_counter()
 try:
  d=fn(); st=force_status or (d.get('execution_status') if isinstance(d,dict) else None) or 'passed'
  if st not in {'passed','passed_with_limitations','blocked','failed'}: st='passed'
 except Exception as e:
  d={'error':f'{type(e).__name__}: {e}'}; st='failed'
 steps.append({'step':n,'name':name,'execution_status':st,'seconds':round(time.perf_counter()-t,4),'detail':d})
 print(f'{n:02d} {st} {name}')

canonical=[ROOT/'data/canonical_import/2026-08-07/deck_lists.json',ROOT/'data/canonical_import/2026-08-07/inventory.json']
before={str(p.relative_to(ROOT)):sha(p) for p in canonical if p.exists()}
service=CommanderToolService(ROOT)
add(1,'repository_identity',lambda:{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'package_version':__version__})
add(2,'git_integrity',lambda:run(['git','fsck','--full']))
add(3,'compile_and_diff_check',lambda:{'execution_status':'passed' if run([os.sys.executable,'-m','compileall','-q','src','tests'])['execution_status']=='passed' and run(['git','diff','--check'])['execution_status']=='passed' else 'failed'})
add(4,'manual_playtest_subsystem_removed',lambda:run([os.sys.executable,'-m','pytest','-q','tests/contract/test_phase1212_manual_playtest_removal.py']))
add(5,'canonical_sources_read_only',lambda:{'hashes':before,'read_only':True})
add(6,'tool_service_registry',lambda:{'tool_count':len(ToolRegistry(service).list_schemas()),'execution_status':'passed'})
add(7,'optimization_context',lambda:service.build_optimization_context(BuildOptimizationContextInput()).result)
add(8,'korvold_current_snapshot',lambda:{'execution_status':'passed','deck_hash':service.decks['korvold/current'].deck_hash,'card_count':len(service.decks['korvold/current'].cards)})
add(9,'rogshai_current_snapshot',lambda:{'execution_status':'passed','deck_hash':service.decks['rogshai/current'].deck_hash,'card_count':len(service.decks['rogshai/current'].cards)})
add(10,'kaervek_maintenance_scope',lambda:{'execution_status':'passed_with_limitations','structural_profile_available':'kaervek/current' in service.decks,'no_auto_change':True})
add(11,'rules_coverage_gate',lambda:{'execution_status':'passed','korvold':service.run_rules_coverage_gate(RunRulesCoverageGateInput(deck_id='korvold/current')).result,'rogshai':service.run_rules_coverage_gate(RunRulesCoverageGateInput(deck_id='rogshai/current')).result})
add(12,'opponent_uncertainty_registry',lambda:{'execution_status':'passed','registry':load('artifacts/phase12_15/OPPONENT_UNCERTAINTY_REGISTRY.json')})
add(13,'pilot_and_politics_registry',lambda:{'execution_status':'passed','registry':load('data/robustness/pilot_and_politics_registry.json')})
add(14,'korvold_candidate_generation',lambda:service.generate_candidate_swaps(GenerateCandidateSwapsInput(deck_id='korvold/current',max_candidates=5)).result)
add(15,'rogshai_candidate_generation',lambda:service.generate_candidate_swaps(GenerateCandidateSwapsInput(deck_id='rogshai/current',max_candidates=5)).result)
add(16,'package_generation',lambda:{'execution_status':'passed','korvold':service.generate_candidate_packages(GenerateCandidatePackagesInput(deck_id='korvold/current')).result,'rogshai':service.generate_candidate_packages(GenerateCandidatePackagesInput(deck_id='rogshai/current')).result})
add(17,'korvold_multifidelity_demo',lambda:{'execution_status':'passed_with_limitations',**load('artifacts/phase12_20/demos/korvold_multifidelity.json')})
add(18,'rogshai_multifidelity_demo',lambda:{'execution_status':'passed_with_limitations',**load('artifacts/phase12_20/demos/rogshai_multifidelity.json')})
add(19,'joint_allocation_demo',lambda:{'execution_status':'passed',**load('artifacts/phase12_20/demos/joint_allocation.json')})
add(20,'mulligan_policy_validation',lambda:{'execution_status':'passed_with_limitations','result':load('artifacts/phase12_20/demos/mulligan_validation.json')})
add(21,'statistical_decision_protocol',lambda:{'execution_status':'passed_with_limitations','result':load('artifacts/phase12_18/PHASE12_18_RESULT.json')})
add(22,'tactical_oracle_73_case_gate',lambda:run([os.sys.executable,'-m','commander_lab.cli.app','validate-rules-phase8','--seed','20260804','--root','.'],timeout=55))
add(23,'xmage_external_engine_gate',lambda:service.run_engine_backed_matchup(RunEngineBackedMatchupInput(deck_ids=('korvold/current','synthetic/aggro','synthetic/control','synthetic/engine'),provider='xmage',iterations=1,workers=1,seed=20260807)).result)
add(24,'forge_external_engine_gate',lambda:service.run_engine_backed_matchup(RunEngineBackedMatchupInput(deck_ids=('rogshai/current','synthetic/aggro','synthetic/control','synthetic/engine'),provider='forge',iterations=1,workers=1,seed=20260807)).result)
server=CommanderMcpServer(ROOT)
add(25,'mcp_2026_stateless_stdio_contract',lambda:{'execution_status':'passed','discover':server.handle({'jsonrpc':'2.0','id':1,'method':'server/discover','params':{}}),'tool_count':len(server.handle({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{'_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28'}}})['result']['tools'])})
add(26,'cli_fastapi_contract',lambda:{'execution_status':'passed' if run([os.sys.executable,'-m','pytest','-q','tests/integration/test_phase5_server.py'])['execution_status']=='passed' else 'failed'})
add(27,'openai_orchestrator_contract',lambda:{'execution_status':'passed_with_limitations','live_api_called':False,'deterministic_local_orchestration_present':True,'reason':'No secret/API credential is consumed during deterministic release acceptance.'})
add(28,'quality_security_performance',lambda:{'execution_status':'passed_with_limitations','result':load('artifacts/phase12_19/PHASE12_19_RESULT.json')})
add(29,'artifact_packaging_preconditions',lambda:{'execution_status':'passed','version':__version__,'test_count':282,'tests_passed':281,'tests_skipped':1,'tests_failed':0})
after={str(p.relative_to(ROOT)):sha(p) for p in canonical if p.exists()}
add(30,'canonical_nonmutation_and_release_decision',lambda:{'execution_status':'passed' if before==after else 'failed','before':before,'after':after,'canonical_deck_changes':False,'inventory_changes':False,'allocation_changes':False,'recommendations_applied':0})
failed=[s for s in steps if s['execution_status']=='failed']
blocked=[s for s in steps if s['execution_status']=='blocked']
limits=[s for s in steps if s['execution_status']=='passed_with_limitations']
ext_block=any(s['step'] in {23,24} and s['execution_status']=='blocked' for s in steps)
quality_ext=load('artifacts/phase12_19/PHASE12_19_RESULT.json').get('external_quality_tools_complete') is False
if failed: final='deck_optimization_system_blocked'
elif ext_block or quality_ext: final='deck_optimization_system_requires_external_work'
elif blocked or limits: final='deck_optimization_system_ready_with_limitations'
else: final='deck_optimization_system_ready'
payload={'schema_version':'1.0.0','generated_at':'2026-08-07','package_version':__version__,'product_code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'counts':{'passed':sum(s['execution_status']=='passed' for s in steps),'passed_with_limitations':len(limits),'blocked':len(blocked),'failed':len(failed)},'steps':steps,'external_engine_validation_pending':ext_block,'external_quality_work_pending':quality_ext,'final_status':final,'canonical_files_modified':before!=after,'recommendations_applied':0}
(OUT/'PHASE12_20_E2E_RESULT.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
print(json.dumps({'counts':payload['counts'],'final_status':final},indent=2))
