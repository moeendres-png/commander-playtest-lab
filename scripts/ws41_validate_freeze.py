#!/usr/bin/env python3
"""Independent fail-closed validation for a generated WS-41 freeze directory."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

VERSION="commander-lab.semantic-fixture-materialization/1.0.3"
PILOT_NEW="ef1df9ac28c80dc6c13d1d8922967a9078c52a9085aa9f03a219931be2944108"
PILOT_OBLIGATION="4c6ab40eb9b2ffc2e47d1ba3858d136cf76bddb356558d6a87b1d0601e9a2baa"
WS32_COMMIT="038d0f38635eecee4e331c99af41f148de267a26"
WS32_TREE="0d160128119f2bad30b220a17c43419b50b7edbe"
REQUIRED={
"WS41_SOURCE_LOCK.json","WS41_WS39_CONTRADICTION_REPRODUCTION.json","WS41_PILOT_CHOICE_SUPERSESSION_PROOF.json",
"WS41_TARGETED_STACK_STATE_AUDIT_135.json","WS41_SEMANTIC_LINTER_RULES.json","SEMANTIC_FIXTURE_SCHEMA_v1_0_3.json",
"SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json","WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json","WS41_PROVIDER_DENOMINATOR_107.json",
"WS41_DIGEST_LINEAGE.json","SUPERSEDES_v1_0_2.json","WS41_VALIDATION.json","WS41_EVIDENCE_INDEX.json","WS41_BUNDLE_MANIFEST_v1_0_3.json",
"WS41_REMAINING_DEFECTS_2.json","WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json","WS41_SHA256SUMS","WS41_FINAL_HANDOFF.md"}

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path):return json.loads(p.read_text(encoding="utf-8"))
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("directory",type=Path);a=ap.parse_args();d=a.directory
 missing=sorted(REQUIRED-{p.name for p in d.iterdir() if p.is_file()})
 if missing: raise SystemExit(f"missing required outputs: {missing}")
 checks={}
 for line in (d/"WS41_SHA256SUMS").read_text().splitlines():
  if not line.strip():continue
  expected,name=line.split(None,1);name=name.strip();actual=sha(d/name);checks[name]=(expected==actual)
 if not checks or not all(checks.values()):raise SystemExit(f"checksum failure: {[k for k,v in checks.items() if not v]}")
 if set(checks)!=(REQUIRED-{"WS41_SHA256SUMS"}):raise SystemExit(f"checksum coverage failure: expected={sorted(REQUIRED-{'WS41_SHA256SUMS'})} actual={sorted(checks)}")
 mat=load(d/"SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json")
 if mat.get("schema_version")!=VERSION or mat.get("record_count")!=135 or len(mat.get("records",[]))!=135:raise SystemExit("materialization accounting/version failure")
 if len({r["fixture_id"] for r in mat["records"]})!=135:raise SystemExit("duplicate fixture ID")
 pilot=next(r for r in mat["records"] if r["fixture_id"]=="PILOT_CHOICE")
 if pilot["requested_state_digest"]!=PILOT_NEW or pilot["obligation_digest"]!=PILOT_OBLIGATION:raise SystemExit("PILOT_CHOICE digest failure")
 objects={o["semantic_id"]:o for o in pilot["semantic_objects"]}
 if objects["obj:forest"]["card_identity"]!="Forest":raise SystemExit("PILOT_CHOICE target object is not Forest")
 stack=next(s for s in pilot["stack_state"] if s["source_semantic_id"]=="obj:utopia")
 if stack.get("cast_complete") is not True or stack.get("costs_paid") is not True or stack.get("targets")!=["obj:forest"]:raise SystemExit("PILOT_CHOICE stack repair failure")
 report=load(d/"WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json")
 if report.get("terminal_status")!="PASS" or report.get("semantic_executable_count")!=135 or report.get("contract_defect_count")!=0 or report.get("global_errors") not in ([],None):raise SystemExit("135 semantic executability failure")
 audit=load(d/"WS41_TARGETED_STACK_STATE_AUDIT_135.json")
 if audit.get("terminal_status")!="PASS" or audit.get("contract_defect_count_after_repair")!=0 or audit.get("stack_state_row_count")!=31:raise SystemExit("targeted stack audit failure")
 denom=load(d/"WS41_PROVIDER_DENOMINATOR_107.json")
 if denom.get("provider_denominator_count")!=107 or not denom.get("pilot_choice_included") or "PILOT_CHOICE" not in denom.get("fixture_ids",[]):raise SystemExit("provider denominator failure")
 lineage=load(d/"WS41_DIGEST_LINEAGE.json")
 if lineage.get("requested_state_changed_fixture_ids")!=["PILOT_CHOICE"] or lineage.get("obligation_changed_count")!=0:raise SystemExit("digest lineage failure")
 defects=load(d/"WS41_REMAINING_DEFECTS_2.json")
 if defects.get("historical_defect_count")!=2 or defects.get("terminal_status")!="PASS":raise SystemExit("remaining-defects accounting failure")
 rows=defects.get("defects",[])
 if [r.get("fixture_id") for r in rows]!=["CARD_13","CARD_22"]:raise SystemExit("remaining-defects fixture identity failure")
 if any(r.get("classification")!="LINTER_FALSE_POSITIVE" or r.get("obligation_changing") is not False or r.get("materialization_record_changed_for_this_adjudication") is not False or r.get("post_fix_linter_status")!="PASS" for r in rows):raise SystemExit("remaining-defects adjudication failure")
 if defects.get("obligation_contradiction_count")!=0 or defects.get("authority_unresolved_count")!=0 or defects.get("post_fix_contract_defect_count")!=0 or defects.get("post_fix_global_errors")!=[]:raise SystemExit("remaining-defects terminal closure failure")
 integrity=load(d/"WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json")
 base=integrity.get("baseline",{})
 if base.get("freeze_commit")!=WS32_COMMIT or base.get("freeze_tree")!=WS32_TREE or integrity.get("status")!="PASS":raise SystemExit("WS32 integrity source-lock failure")
 if not integrity.get("path_set_identical") or not integrity.get("all_files_byte_identical") or not integrity.get("all_git_blob_ids_identical") or integrity.get("namespace_git_diff_exit_code")!=0:raise SystemExit("WS32 content integrity failure")
 if integrity.get("file_count")!=len(integrity.get("rows",[])) or any(not r.get("byte_identical") or r.get("frozen_git_blob_sha")!=r.get("current_git_blob_sha") or r.get("frozen_sha256")!=r.get("current_sha256") for r in integrity.get("rows",[])):raise SystemExit("WS32 content integrity row failure")
 val=load(d/"WS41_VALIDATION.json")
 if val.get("classification")!="COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_3_FREEZE" or val.get("successor_contract_frozen") is not True or val.get("architecture_freeze") is not False:raise SystemExit("freeze classification failure")
 if val.get("provider_runtime_executed") is not False or val.get("provider_pass_imported") is not False or val.get("af07_granted") is not False:raise SystemExit("out-of-scope credit imported")
 if val.get("historical_remaining_linter_defect_count")!=2 or val.get("historical_remaining_linter_defects_adjudicated")!=2 or val.get("linter_false_positive_count")!=2 or val.get("obligation_contradiction_count")!=0 or val.get("authority_unresolved_count")!=0 or val.get("post_fix_contract_defect_count")!=0 or val.get("post_fix_global_errors")!=[] or val.get("ws32_content_integrity_comparison")!="PASS":raise SystemExit("continuation validation fields failure")
 gates=val.get("gates",{})
 if set(gates)!={f"G41-{i:02d}" for i in range(1,15)} or any(v!="PASS" for v in gates.values()):raise SystemExit("hard gate failure")
 source=load(d/"WS41_SOURCE_LOCK.json")
 if source["predecessor"].get("sha256s_all_pass") is not True:raise SystemExit("predecessor preservation failure")
 sup=load(d/"SUPERSEDES_v1_0_2.json")
 if not sup.get("immutable_predecessor_verified_byte_for_byte") or not sup.get("frozen_obligation_projection_preserved_135_of_135"):raise SystemExit("supersession proof failure")
 index=load(d/"WS41_EVIDENCE_INDEX.json")
 if set(index.get("required_in_repo_outputs",[]))!=REQUIRED:raise SystemExit("evidence-index required-output coverage failure")
 print(json.dumps({"status":"PASS","required_outputs":len(REQUIRED),"checksum_rows":len(checks),"records":135,"provider_denominator":107,"historical_linter_defects":2,"post_fix_contract_defects":0,"ws32_integrity_files":integrity["file_count"],"pilot_choice_requested_state_digest":PILOT_NEW},sort_keys=True))
 return 0
if __name__=="__main__":raise SystemExit(main())
