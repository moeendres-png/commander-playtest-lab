#!/usr/bin/env python3
"""WS73 deterministic validation: Full107 contract + RQ-C3 relation + credit gates.

Reads ONLY pinned commits via `git show` (no working-tree inputs for contract facts),
plus WS73 output files in this directory. Deterministic, no timestamps.
Exit 0 PASS, exit 2 FAIL with manifest written to stdout.
Checks:
  C1 exactly 135 materialized records
  C2 exactly 107 denominator IDs
  C3 every denominator ID belongs to the materialization
  C4 exact RQ-C3 population counts (RQ-C1 40/15, RQ-C3 18/15, defined 40/25)
  C5 no invented 92 (no output claims a 92-ID population; REMAINING92==NOT_APPLICABLE)
  C6 no cross-contract credit (Full107 0/107 both; RQ-C3 PASS not counted as Full107)
"""
import subprocess, json, hashlib, sys, pathlib
WS47="192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
RQC1="714ad417c1c090eb4ddf1ccd0828a2e869a80a74"
RQC3="897d72f0b57bb8febe045870acaa3d2dba4bde56"
WS60="731891ec5ed8e7611fc9a636bab5fc3c400108eb"
WS65="7796619e69b0434cd232de8335ff5cab3c5d08e5"
WS72="7a92ab471a92c3c57522044d5326276d578f69d0"
HERE=pathlib.Path(__file__).parent
def show(c,p): return subprocess.check_output(["git","show", f"{c}:{p}"])
def load_json(c,p): return json.loads(show(c,p))
def load_local(n): return json.loads((HERE/n).read_text())
checks=[]
def check(id, ok, detail=""):
    checks.append({"id": id, "pass": bool(ok), "detail": detail})
    return bool(ok)
mat=load_json(WS47,"qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")
den=load_json(WS47,"qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json")
frz=load_json(WS47,"qualification/ws47/WS47_FREEZE_RESULT.json")
rqc1m=load_json(RQC1,"research/candidate-qualification/common/rq-c1/RQ_C1_SCENARIO_MANIFEST.json")
rqc3m=load_json(RQC3,"research/candidate-qualification/common/rq-c3/RQ_C3_CORRECTED_SCENARIO_MANIFEST.json")
mat_ids=[r["fixture_id"] for r in mat["records"]]
check("C1_135_records", mat.get("record_count")==135 and len(mat["records"])==135 and len(set(mat_ids))==135, f"record_count={mat.get('record_count')} len={len(mat['records'])} uniq={len(set(mat_ids))}")
check("C1b_freeze_135_107", frz.get("record_count")==135 and frz.get("provider_denominator")==107, f"freeze={frz}")
check("C2_107_denominator", den.get("provider_denominator_count")==107 and len(den["fixture_ids"])==107 and len(den["excluded_fixture_ids"])==28, f"den={len(den['fixture_ids'])} excl={len(den['excluded_fixture_ids'])}")
check("C3_denominator_subset_materialization", set(den["fixture_ids"])<=set(mat_ids), f"missing={sorted(set(den['fixture_ids'])-set(mat_ids))[:5]}")
check("C3b_union_135", set(den["fixture_ids"])|set(den["excluded_fixture_ids"])==set(mat_ids) and len(den["fixture_ids"])+len(den["excluded_fixture_ids"])==135, "union==mat")
rqc1_ids=[s["scenario_id"] for s in rqc1m["scenarios"]]
rqc1_fw=[s["scenario_id"] for s in rqc1m["scenarios"] if s.get("first_wave")]
rqc3_ids=[s["rqc3_scenario_id"] for s in rqc3m["scenarios"]]
rqc3_fw=[s["rqc3_scenario_id"] for s in rqc3m["scenarios"] if s.get("first_wave")]
check("C4_rqc1_40_15", rqc1m.get("scenario_count")==40 and len(rqc1_ids)==40 and len(rqc1_fw)==15, f"40/{len(rqc1_ids)} 15/{len(rqc1_fw)}")
check("C4b_rqc3_18_15", rqc3m.get("count")==18 and len(rqc3_ids)==18 and rqc3m.get("first_wave_count")==15 and len(rqc3_fw)==15, f"18/{len(rqc3_ids)} 15/{len(rqc3_fw)}")
overlay={s["parent_scenario_id"]:s["rqc3_scenario_id"] for s in rqc3m["scenarios"]}
defined40=sorted([overlay.get(pid,pid) for pid in rqc1_ids])
defined25=sorted([overlay.get(pid,pid) for pid in rqc1_ids if pid not in set(rqc1_fw)])
check("C4c_defined_40_25", len(defined40)==40 and len(defined25)==25, f"40/{len(defined40)} 25/{len(defined25)}")
check("C4d_namespaces_disjoint", set(den["fixture_ids"])&set(rqc1_ids)==set() and set(den["fixture_ids"])&set(rqc3_ids)==set(), "disjoint")
# C5 no invented 92: scan WS73 outputs for 92-ID claims
import re
bad92=[]
for fn in ["FULL107_CONTRACT_IDENTITY.json","RQC3_FULL107_RELATION.json","BEHAVIOR_CREDIT_RECONCILIATION.json","FULL107_HISTORICAL_IMPACT_MATRIX.json","FULL107_CURRENT_READINESS.json","WS72_IMPACT_ADJUDICATION.json"]:
    t=(HERE/fn).read_text()
    # allow mentions of 92 as rejected/NOT_APPLICABLE, forbid claims of a 92 population like "92/92" or '"remaining92": 92' or 92 IDs listed
    if re.search(r"92/92|REMAINING92\s*=\s*92|remaining.*92.*PASS|92 scenarios.*defined", t, re.I):
        # permit if accompanied by NOT_APPLICABLE or SUPERSEDED/FAIL context? strict: fail only if claims 92 as valid denominator
        if "NOT_APPLICABLE" not in t and "not a 92" not in t.lower() and "no 92" not in t.lower():
            bad92.append(fn)
check("C5_no_invented_92", len(bad92)==0, f"bad={bad92}")
# explicit REMAINING92 gate
try:
    adj=load_local("WS72_IMPACT_ADJUDICATION.json")
    check("C5b_remaining92_not_applicable", adj.get("required_classifications",{}).get("REMAINING92")=="NOT_APPLICABLE", f"{adj.get('required_classifications',{}).get('REMAINING92')}")
except Exception as e:
    check("C5b_remaining92_not_applicable", False, str(e))
# C6 no cross-contract credit
try:
    rec=load_local("BEHAVIOR_CREDIT_RECONCILIATION.json")
    cur=rec.get("adjudication",{}).get("current_creditable",{})
    check("C6_full107_zero_both", cur.get("xmage_full107_current_credit")=="0/107" and cur.get("forge_full107_current_credit")=="0/107", f"{cur}")
    check("C6b_change_zero", rec.get("adjudication",{}).get("behavior_credit_change_by_this_audit")==0, "change==0")
    check("C6c_superseded_labels", rec.get("adjudication",{}).get("xmage_14_107_classification")=="SUPERSEDED_CROSS_CONTRACT_ACCOUNTING" and rec.get("adjudication",{}).get("forge_9_107_classification")=="SUPERSEDED_CROSS_CONTRACT_ACCOUNTING", "labels")
    check("C6d_rqc3_preserved", cur.get("xmage_rqc3_first_wave")=="14/15" and cur.get("forge_rqc3_first_wave")=="9/15", f"{cur}")
except Exception as e:
    check("C6_full107_zero_both", False, str(e))
    check("C6b_change_zero", False, str(e))
    check("C6c_superseded_labels", False, str(e))
    check("C6d_rqc3_preserved", False, str(e))
# identity file consistency
try:
    ident=load_local("FULL107_CONTRACT_IDENTITY.json")
    check("C7_identity_135_107", ident.get("FULL107_MATERIALIZATION_RECORD_COUNT")==135 and ident.get("FULL107_PROVIDER_DENOMINATOR_COUNT")==107, "identity counts")
    check("C7b_identity_verdict", ident.get("class_adjudication",{}).get("verdict")=="PROVIDER_QUALIFICATION_FIXTURES", "verdict")
    rel=load_local("RQC3_FULL107_RELATION.json")
    check("C7c_relation_separate", rel.get("classification")=="SEPARATE_CONTRACT", f"{rel.get('classification')}")
    rd=load_local("FULL107_CURRENT_READINESS.json")
    check("C7d_ready_zero", rd.get("summary",{}).get("forge",{}).get("ready_fraction")=="0/107" and rd.get("summary",{}).get("xmage",{}).get("ready_fraction")=="0/107", f"{rd.get('summary')}")
    ws72a=load_local("WS72_IMPACT_ADJUDICATION.json").get("required_classifications",{})
    check("C7e_ws72_labels", ws72a.get("WS72_RQC3_CARD_PREFLIGHT")=="PASS" and ws72a.get("WS72_FULL107_CARD_PREFLIGHT")=="NOT_RUN", f"{ws72a}")
except Exception as e:
    check("C7_identity_135_107", False, str(e))
overall=all(c["pass"] for c in checks)
manifest={"schema": "ws73.validation.v1", "verdict": "PASS" if overall else "FAIL", "checks": checks, "passed": sum(1 for c in checks if c["pass"]), "total": len(checks)}
print(json.dumps(manifest, indent=2, sort_keys=True))
sys.exit(0 if overall else 2)
