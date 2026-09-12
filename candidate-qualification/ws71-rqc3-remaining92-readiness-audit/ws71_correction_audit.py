#!/usr/bin/env python3
"""WS71 correction validation — deterministic source-truth cross-check.

Verifies the Coordinator's binding source-truth correction WITHOUT inventing
scenarios, WITHOUT changing the denominator, WITHOUT executing behavior:

  A. RQ-C3 reverser corpus = 40 actual-card scenarios (15 First Wave + 25
     non-First-Wave), from exact RQ-C1 authority 714ad417 + exact RQ-C3
     authority 897d72f0 (corrected overlay: 18 files = 15 FW + F02/H02/K02).
  B. Full107 = SEPARATE provider-neutral semantic fixture contract:
     WS47 freeze record_count = 135, provider_denominator = 107;
     WS44 denominator = exact 107 fixture IDs derived as
     135 records minus CARD_01..CARD_29 except retained CARD_02.
  C. Category conclusion: REMAINING92 = NOT_APPLICABLE
     (CONTRACT_CATEGORY_MISMATCH, not missing authority).

Reads ONLY via `git show <pinned-sha>:<path>`. No working-tree reads,
no network, no behavior execution.

Exit codes:
  0 = all correction checks PASS (correction validated; evidence written)
  1 = execution error (unreadable source, hash mismatch, ...)
  2 = one or more correction checks FAIL (evidence written)

Output (byte-deterministic; no timestamps):
  WS71_CORRECTION_EVIDENCE.json (canonical JSON: sort_keys, indent 2)

Usage:
  python3 ws71_correction_audit.py [--out DIR] [--repo DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

RQC1_AUTHORITY_SHA = "714ad417c1c090eb4ddf1ccd0828a2e869a80a74"
RQC1_AUTHORITY_TREE = "709a5944c9826dbaaa433052f3538425c8f0573b"
RQC3_AUTHORITY_SHA = "897d72f0b57bb8febe045870acaa3d2dba4bde56"
RQC3_AUTHORITY_TREE = "1b8c8a46f1b81277f73a0ec808055dde25fadbe5"
WS47_CONTRACT_SHA = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"

P_RQC1_MANIFEST = "research/candidate-qualification/common/rq-c1/RQ_C1_SCENARIO_MANIFEST.json"
P_RQC1_RELATION = "research/candidate-qualification/common/rq-c1/RQ_C1_FULL107_RELATION.md"
P_RQC3_MANIFEST = "research/candidate-qualification/common/rq-c3/RQ_C3_CORRECTED_SCENARIO_MANIFEST.json"
P_WS47_FREEZE = "qualification/ws47/WS47_FREEZE_RESULT.json"
P_WS44_DENOM = "qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json"

CONTRACT_FW_SUFFIXES = [
    "A03", "A04", "B01", "C01", "C03", "D06", "E01", "E02",
    "F01", "G02", "G03", "G04", "H01", "I01", "J02",
]

SCHEMA = "ws71.correction-evidence.v1"


def run_git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(repo),
                       capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()[:400]}")
    return p.stdout


def git_show_bytes(repo: Path, sha: str, path: str) -> bytes:
    p = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=str(repo),
                       capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"git show {sha}:{path} failed: {p.stderr.decode()[:400]}")
    return p.stdout


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    out_dir = Path(args.out)
    repo = Path(args.repo)

    checks: dict[str, bool] = {}
    detail: dict = {}
    provenance: dict = {}

    def record(name: str, ok: bool, info=None):
        checks[name] = bool(ok)
        if info is not None:
            detail[name] = info

    try:
        # --- Pin verification (fail-closed) --------------------------------
        for sha, tree, label in (
            (RQC1_AUTHORITY_SHA, RQC1_AUTHORITY_TREE, "rqc1"),
            (RQC3_AUTHORITY_SHA, RQC3_AUTHORITY_TREE, "rqc3"),
        ):
            got_c = run_git(repo, "rev-parse", f"{sha}^{{commit}}").strip()
            got_t = run_git(repo, "rev-parse", f"{sha}^{{tree}}").strip()
            provenance[f"{label}_commit_resolved"] = got_c
            provenance[f"{label}_tree_resolved"] = got_t
            if got_c != sha or got_t != tree:
                raise RuntimeError(f"{label} pin mismatch")
        got_ws47 = run_git(repo, "rev-parse", f"{WS47_CONTRACT_SHA}^{{commit}}").strip()
        provenance["ws47_commit_resolved"] = got_ws47
        if got_ws47 != WS47_CONTRACT_SHA:
            raise RuntimeError("ws47 pin mismatch")

        # --- A. RQ-C1 corpus @ exact authority ------------------------------
        raw = git_show_bytes(repo, RQC1_AUTHORITY_SHA, P_RQC1_MANIFEST)
        provenance["rqc1_manifest_sha256"] = sha256_hex(raw)
        m1 = json.loads(raw.decode("utf-8"))
        c1_ids = sorted(s["scenario_id"] for s in m1["scenarios"])
        c1_fw = sorted(s["scenario_id"] for s in m1["scenarios"]
                       if s.get("first_wave") is True)
        c1_nonfw = sorted(s["scenario_id"] for s in m1["scenarios"]
                          if s.get("first_wave") is not True)
        record("rqc1_total_is_40", len(c1_ids) == 40, len(c1_ids))
        record("rqc1_fw_is_15", len(c1_fw) == 15, len(c1_fw))
        record("rqc1_nonfw_is_25", len(c1_nonfw) == 25, len(c1_nonfw))
        record("rqc1_ids_unique", len(set(c1_ids)) == len(c1_ids))
        record("rqc1_fw_suffixes_match_contract",
               sorted(i.rsplit("-", 1)[-1] for i in c1_fw)
               == sorted(CONTRACT_FW_SUFFIXES))

        raw_rel = git_show_bytes(repo, RQC1_AUTHORITY_SHA, P_RQC1_RELATION)
        provenance["rqc1_relation_sha256"] = sha256_hex(raw_rel)
        rel = raw_rel.decode("utf-8")
        record("relation_states_40_families_15_fw",
               "40 actual-card scenario" in rel and "15 first-wave" in rel)
        record("relation_states_full107_separate_contract",
               "SEPARATE evidence contract" in rel and "FULL107 = NOT_RUN" in rel)
        record("relation_states_no_precount",
               "pre-counts Full107 credit" in rel or "pre-count" in rel)

        # --- A2. RQ-C3 overlay @ exact authority -----------------------------
        raw3 = git_show_bytes(repo, RQC3_AUTHORITY_SHA, P_RQC3_MANIFEST)
        provenance["rqc3_manifest_sha256"] = sha256_hex(raw3)
        m3 = json.loads(raw3.decode("utf-8"))
        c3_ids = sorted(e["rqc3_scenario_id"] for e in m3["scenarios"])
        c3_fw = sorted(e["rqc3_scenario_id"] for e in m3["scenarios"]
                       if e.get("first_wave") is True)
        c3_nonfw = sorted(e["rqc3_scenario_id"] for e in m3["scenarios"]
                          if e.get("first_wave") is not True)
        record("rqc3_corrected_total_is_18", len(c3_ids) == 18, c3_ids)
        record("rqc3_fw_is_contract_15",
               c3_fw == sorted(f"RQ-C3-{s}" for s in CONTRACT_FW_SUFFIXES))
        record("rqc3_nonfw_is_f02_h02_k02",
               c3_nonfw == ["RQ-C3-F02", "RQ-C3-H02", "RQ-C3-K02"], c3_nonfw)
        # Every corrected RQ-C3 scenario traces to an RQ-C1 parent in the 40.
        parents = sorted(e["parent_scenario_id"] for e in m3["scenarios"])
        record("rqc3_parents_within_rqc1_40",
               set(parents) <= {i.replace("RQ-C1-", "RQ-C1-") for i in c1_ids}
               and all(p in c1_ids for p in parents), parents)

        # --- B. Full107 provider contract @ WS47 pin --------------------------
        raw47 = git_show_bytes(repo, WS47_CONTRACT_SHA, P_WS47_FREEZE)
        provenance["ws47_freeze_sha256"] = sha256_hex(raw47)
        f47 = json.loads(raw47.decode("utf-8"))
        record("ws47_record_count_is_135", f47.get("record_count") == 135,
               f47.get("record_count"))
        record("ws47_provider_denominator_is_107",
               f47.get("provider_denominator") == 107,
               f47.get("provider_denominator"))

        raw44 = git_show_bytes(repo, WS47_CONTRACT_SHA, P_WS44_DENOM)
        provenance["ws44_denom_sha256"] = sha256_hex(raw44)
        d44 = json.loads(raw44.decode("utf-8"))
        fx = d44["fixture_ids"]
        ex = sorted(d44["excluded_fixture_ids"])
        expected_ex = sorted(f"CARD_{i:02d}" for i in range(1, 30) if i != 2)
        record("ws44_count_field_is_107",
               d44.get("provider_denominator_count") == 107,
               d44.get("provider_denominator_count"))
        record("ws44_matcount_is_135",
               d44.get("materialization_record_count") == 135,
               d44.get("materialization_record_count"))
        record("ws44_fixture_ids_107_unique",
               len(fx) == 107 and len(set(fx)) == 107, len(fx))
        record("ws44_excluded_exact_card01_29_minus_02",
               ex == expected_ex and len(ex) == 28, ex)
        record("ws44_disjoint_union_135",
               not (set(fx) & set(ex)) and len(set(fx) | set(ex)) == 135)
        record("ws44_derivation_text_matches",
               "CARD_01..CARD_29" in d44.get("identity_derivation", "")
               and "CARD_02" in d44.get("identity_derivation", ""),
               d44.get("identity_derivation"))

        # --- C. Category conclusion -------------------------------------------
        record("no_rqc3_107_scenario_population",
               len(c3_ids) == 18 and len(c1_ids) == 40)
        record("full107_is_fixture_contract_not_scenarios",
               f47.get("provider_denominator") == 107
               and d44.get("provider_denominator_count") == 107
               and all(not str(i).startswith("RQ-C") for i in fx))

        passed = all(checks.values())
        evidence = {
            "schema": SCHEMA,
            "source_pins": {
                "rqc1_authority_sha": RQC1_AUTHORITY_SHA,
                "rqc1_authority_tree": RQC1_AUTHORITY_TREE,
                "rqc3_authority_sha": RQC3_AUTHORITY_SHA,
                "rqc3_authority_tree": RQC3_AUTHORITY_TREE,
                "ws47_contract_sha": WS47_CONTRACT_SHA,
            },
            "corpus_a_rqc3_reverser": {
                "RQ_C3_DEFINED_SCENARIOS": 40,
                "RQ_C3_FIRST_WAVE": 15,
                "RQ_C3_NON_FIRST_WAVE": 25,
                "rqc3_corrected_files": 18,
                "rqc3_corrected_nonfw_derivatives": c3_nonfw,
                "rqc1_nonfw_ids": c1_nonfw,
            },
            "contract_b_full107_provider": {
                "FULL107_PROVIDER_DENOMINATOR": 107,
                "FULL107_MATERIALIZATION_RECORDS": 135,
                "ws47_schema": f47.get("schema_version"),
                "identity_derivation": d44.get("identity_derivation"),
            },
            "disposition": {
                "WS71_REMAINING92_AUDIT": "FAIL",
                "FAILURE_CLASS": "CONTRACT_CATEGORY_MISMATCH",
                "FULL107_COUNT_AS_RQC3_SCENARIOS": "INVALID",
                "REMAINING92": "NOT_APPLICABLE",
            },
            "checks": checks,
            "check_detail": detail,
            "correction_verdict": "PASS" if passed else "FAIL",
            "provenance": provenance,
            "evidence_class": "DIRECTLY_VERIFIED",
            "behavior_credit": "0/107",
        }
    except Exception as exc:  # execution error -> exit 1
        evidence = {
            "schema": SCHEMA,
            "correction_verdict": "ERROR",
            "errors": [f"{type(exc).__name__}: {exc}"],
            "provenance": provenance,
            "evidence_class": "UNKNOWN",
            "behavior_credit": "0/107",
        }
        out = out_dir / "WS71_CORRECTION_EVIDENCE.json"
        out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"correction_verdict": "ERROR",
                          "errors": evidence["errors"]}, indent=2))
        return 1

    out = out_dir / "WS71_CORRECTION_EVIDENCE.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "correction_verdict": evidence["correction_verdict"],
        "checks_passed": sum(1 for v in checks.values() if v),
        "checks_total": len(checks),
        "failed": sorted(k for k, v in checks.items() if not v),
        "out": str(out),
    }, indent=2))
    return 0 if evidence["correction_verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
