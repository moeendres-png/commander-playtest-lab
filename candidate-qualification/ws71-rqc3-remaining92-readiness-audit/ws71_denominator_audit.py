#!/usr/bin/env python3
"""WS71 Phase A — exact denominator mechanical audit.

Derives the Full107 / First-Wave / Remaining denominator SOLELY from the
exact pinned RQ-C3 authority commit, via `git show <sha>:<path>` reads.
No working-tree files, no network, no behavior execution.

Exit codes:
  0 = audit executed AND hard gate PASS (107 = 15 + 92 mechanically holds)
  2 = audit executed AND hard gate FAIL (STOP condition; manifest written)
  1 = audit execution error (source unreadable, hash mismatch, ...)

Outputs (byte-deterministic; no timestamps):
  WS71_REMAINING92_DENOMINATOR.json  (canonical JSON: sort_keys, indent 2)

Usage:
  python3 ws71_denominator_audit.py [--out DIR] [--repo DIR]
  Defaults: --out = directory containing this script, --repo = cwd.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Pins (from the WS71 workstream contract; fail-closed on mismatch)
# --------------------------------------------------------------------------
RQC3_AUTHORITY_SHA = "897d72f0b57bb8febe045870acaa3d2dba4bde56"
RQC3_AUTHORITY_TREE = "1b8c8a46f1b81277f73a0ec808055dde25fadbe5"

CPL_SOURCE_SHA = "7796619e69b0434cd232de8335ff5cab3c5d08e5"
CPL_SOURCE_TREE = "48ec3eafcca668f3fa165e3977af5836b3add059"

XMAGE_FIRST_WAVE_SHA = "731891ec5ed8e7611fc9a636bab5fc3c400108eb"
FORGE_FIRST_WAVE_SHA = "7796619e69b0434cd232de8335ff5cab3c5d08e5"

# Contract Phase-A First-Wave suffix set (bare suffixes; full IDs RQ-C3-<sfx>)
CONTRACT_FIRST_WAVE_SUFFIXES = [
    "A03", "A04", "B01", "C01", "C03", "D06", "E01", "E02",
    "F01", "G02", "G03", "G04", "H01", "I01", "J02",
]

# Authority paths inside the RQ-C3 commit
P_RQC3_MANIFEST = "research/candidate-qualification/common/rq-c3/RQ_C3_CORRECTED_SCENARIO_MANIFEST.json"
P_RQC3_FW_PACK = "research/candidate-qualification/common/rq-c3/RQ_C3_FIRST_WAVE_EXECUTION_PACK.json"
P_RQC3_FINAL_REPORT = "research/candidate-qualification/common/rq-c3/RQ_C3_FINAL_REPORT.md"
P_RQC1_MANIFEST = "research/candidate-qualification/common/rq-c1/RQ_C1_SCENARIO_MANIFEST.json"
P_RQC1_FULL107_REL = "research/candidate-qualification/common/rq-c1/RQ_C1_FULL107_RELATION.md"
P_RQC2_ASSERT_REVIEW = "research/candidate-qualification/common/rq-c2/RQ_C2_EXPECTED_ASSERTION_REVIEW.json"

SCHEMA = "ws71.remaining92-denominator.v1"


def run_git(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()[:400]}")
    return p.stdout


def git_show_bytes(repo: Path, sha: str, path: str) -> bytes:
    p = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=str(repo),
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git show {sha}:{path} failed: {p.stderr.decode()[:400]}")
    return p.stdout


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def suffix_of(full_id: str) -> str:
    # "RQ-C3-A03" -> "A03"; "RQ-C1-A03" -> "A03"
    return full_id.rsplit("-", 1)[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    out_dir = Path(args.out)
    repo = Path(args.repo)

    errors: list[str] = []
    provenance: dict = {}
    try:
        # --- 1. Pin verification (fail-closed) ---------------------------
        got_commit = run_git(repo, "rev-parse", f"{RQC3_AUTHORITY_SHA}^{{commit}}").strip()
        got_tree = run_git(repo, "rev-parse", f"{RQC3_AUTHORITY_SHA}^{{tree}}").strip()
        provenance["rqc3_authority_commit_resolved"] = got_commit
        provenance["rqc3_authority_tree_resolved"] = got_tree
        if got_commit != RQC3_AUTHORITY_SHA:
            raise RuntimeError("RQ-C3 authority commit mismatch")
        if got_tree != RQC3_AUTHORITY_TREE:
            raise RuntimeError("RQ-C3 authority tree mismatch")

        # --- 2. RQ-C3 corrected manifest (18 scenarios) -------------------
        raw_c3 = git_show_bytes(repo, RQC3_AUTHORITY_SHA, P_RQC3_MANIFEST)
        provenance["rqc3_manifest_sha256"] = sha256_hex(raw_c3)
        m_c3 = json.loads(raw_c3.decode("utf-8"))
        c3_ids = sorted(e["rqc3_scenario_id"] for e in m_c3["scenarios"])
        c3_fw_ids = sorted(
            e["rqc3_scenario_id"] for e in m_c3["scenarios"] if e.get("first_wave") is True
        )
        c3_nonfw_ids = sorted(
            e["rqc3_scenario_id"] for e in m_c3["scenarios"] if e.get("first_wave") is not True
        )

        # --- 3. RQ-C3 First-Wave execution pack (denominator string) ------
        raw_pack = git_show_bytes(repo, RQC3_AUTHORITY_SHA, P_RQC3_FW_PACK)
        provenance["rqc3_fw_pack_sha256"] = sha256_hex(raw_pack)
        pack = json.loads(raw_pack.decode("utf-8"))
        pack_count = pack.get("count")
        pack_full107 = pack.get("full107")

        # --- 4. RQ-C1 parent manifest (40 families) -----------------------
        raw_c1 = git_show_bytes(repo, RQC3_AUTHORITY_SHA, P_RQC1_MANIFEST)
        provenance["rqc1_manifest_sha256"] = sha256_hex(raw_c1)
        m_c1 = json.loads(raw_c1.decode("utf-8"))
        c1_ids = sorted(s["scenario_id"] for s in m_c1["scenarios"])
        c1_fw_ids = sorted(
            s["scenario_id"] for s in m_c1["scenarios"] if s.get("first_wave") is True
        )
        c1_nonfw_ids = sorted(
            s["scenario_id"] for s in m_c1["scenarios"] if s.get("first_wave") is not True
        )

        # --- 5. Full107 relation note + RQ-C2 assertion review ------------
        raw_rel = git_show_bytes(repo, RQC3_AUTHORITY_SHA, P_RQC1_FULL107_REL)
        provenance["rqc1_full107_relation_sha256"] = sha256_hex(raw_rel)
        rel_text = raw_rel.decode("utf-8")
        rel_states_full107_not_run = "FULL107 = NOT_RUN" in rel_text
        rel_states_separate_contract = "SEPARATE evidence contract" in rel_text

        raw_ar = git_show_bytes(repo, RQC3_AUTHORITY_SHA, P_RQC2_ASSERT_REVIEW)
        provenance["rqc2_assertion_review_sha256"] = sha256_hex(raw_ar)
        ar = json.loads(raw_ar.decode("utf-8"))
        ar_counting = ar.get("counting", "")

        # --- 6. Full107 ID-set search ------------------------------------
        # A Full107 ID set would be a machine-readable list of exactly 107
        # scenario IDs inside the authority. Candidate carriers enumerated:
        full107_candidates = {
            "rqc3_corrected_manifest": len(c3_ids),
            "rqc1_parent_manifest": len(c1_ids),
            "rqc3_fw_pack_count": pack_count,
        }
        full107_id_set: list[str] = []
        full107_source: str = "NONE_FOUND_IN_AUTHORITY"

        # --- 7. Gate checks ----------------------------------------------
        contract_fw_full = sorted(f"RQ-C3-{s}" for s in CONTRACT_FIRST_WAVE_SUFFIXES)
        checks = {
            "rqc3_manifest_total_is_18": len(c3_ids) == 18,
            "rqc3_manifest_fw_is_15": len(c3_fw_ids) == 15,
            "rqc3_fw_matches_contract_set": c3_fw_ids == contract_fw_full,
            "rqc3_fw_pack_count_is_15": pack_count == 15,
            "rqc1_manifest_total_is_40": len(c1_ids) == 40,
            "rqc1_fw_suffixes_match_contract": sorted(
                suffix_of(i) for i in c1_fw_ids
            ) == sorted(CONTRACT_FIRST_WAVE_SUFFIXES),
            "c3_ids_unique": len(set(c3_ids)) == len(c3_ids),
            "c1_ids_unique": len(set(c1_ids)) == len(c1_ids),
            "full107_count_is_107": len(full107_id_set) == 107,
            "first_wave_count_is_15": len(c3_fw_ids) == 15,
            "remaining_count_is_92": (len(full107_id_set) - len(c3_fw_ids)) == 92,
            "remaining_exact_set_difference": False,  # computable only if FULL107 exists
        }
        gate_pass = all(checks.values())

        remaining_ids: list[str] = []
        if gate_pass:
            remaining_ids = sorted(set(full107_id_set) - set(c3_fw_ids))
            checks["remaining_exact_set_difference"] = (
                len(remaining_ids) == 92
                and set(remaining_ids) | set(c3_fw_ids) == set(full107_id_set)
                and not (set(remaining_ids) & set(c3_fw_ids))
            )
            gate_pass = all(checks.values())

        manifest = {
            "schema": SCHEMA,
            "source_lock": {
                "cpl_source_sha": CPL_SOURCE_SHA,
                "cpl_source_tree": CPL_SOURCE_TREE,
                "rqc3_authority_sha": RQC3_AUTHORITY_SHA,
                "rqc3_authority_tree": RQC3_AUTHORITY_TREE,
                "xmage_first_wave_sha": XMAGE_FIRST_WAVE_SHA,
                "forge_first_wave_sha": FORGE_FIRST_WAVE_SHA,
            },
            "derivation_method": (
                "git show <rqc3-authority-sha>:<path> reads of "
                "RQ_C3_CORRECTED_SCENARIO_MANIFEST.json, "
                "RQ_C3_FIRST_WAVE_EXECUTION_PACK.json, "
                "RQ_C1_SCENARIO_MANIFEST.json, RQ_C1_FULL107_RELATION.md, "
                "RQ_C2_EXPECTED_ASSERTION_REVIEW.json; no working-tree reads, "
                "no network, no behavior execution."
            ),
            "contract_first_wave_suffixes": sorted(CONTRACT_FIRST_WAVE_SUFFIXES),
            "derived_sets": {
                "rqc3_corrected_ids": c3_ids,
                "rqc3_first_wave_ids": c3_fw_ids,
                "rqc3_nonfw_ids": c3_nonfw_ids,
                "rqc1_parent_ids": c1_ids,
                "rqc1_first_wave_ids": c1_fw_ids,
                "rqc1_nonfw_ids": c1_nonfw_ids,
                "full107_ids": full107_id_set,
                "remaining_ids": remaining_ids,
            },
            "counts": {
                "FULL107_COUNT": len(full107_id_set),
                "FIRST_WAVE_COUNT": len(c3_fw_ids),
                "REMAINING_COUNT": len(remaining_ids),
                "RQC3_CORRECTED_COUNT": len(c3_ids),
                "RQC1_PARENT_COUNT": len(c1_ids),
                "RQC1_NONFW_COUNT": len(c1_nonfw_ids),
            },
            "full107_search": {
                "candidate_carriers": full107_candidates,
                "full107_source": full107_source,
                "rqc1_relation_states_full107_not_run": rel_states_full107_not_run,
                "rqc1_relation_states_separate_contract": rel_states_separate_contract,
                "rqc2_assertion_review_counting": ar_counting,
                "rqc3_fw_pack_full107_field": pack_full107,
            },
            "gate_checks": checks,
            "gate_verdict": "PASS" if gate_pass else "FAIL",
            "stop_rationale": (
                None
                if gate_pass
                else (
                    "HARD GATE FAIL: the exact RQ-C3 authority contains no "
                    "machine-readable 107-scenario ID population "
                    "(RQC3 corrected = 18 = 15 FW + F02/H02/K02; "
                    "RQ-C1 parent = 40 families = 15 FW + 25 non-FW; "
                    "First-Wave pack full107 field = NOT_RUN; "
                    "RQ-C1 FULL107 relation = SEPARATE evidence contract, NOT_RUN). "
                    "FULL107_COUNT=0, FIRST_WAVE_COUNT=15, REMAINING_COUNT=0: "
                    "107 = 15 + 92 does not mechanically hold. "
                    "Per contract: STOP with evidence; no 92 denominator manufactured; "
                    "Phases B-G not executed."
                )
            ),
            "provenance": provenance,
            "evidence_class": "DIRECTLY_VERIFIED",
            "behavior_credit": "0/107",
        }
    except Exception as exc:  # audit execution error -> exit 1, still write stub
        errors.append(f"{type(exc).__name__}: {exc}")
        manifest = {
            "schema": SCHEMA,
            "source_lock": {
                "cpl_source_sha": CPL_SOURCE_SHA,
                "cpl_source_tree": CPL_SOURCE_TREE,
                "rqc3_authority_sha": RQC3_AUTHORITY_SHA,
                "rqc3_authority_tree": RQC3_AUTHORITY_TREE,
                "xmage_first_wave_sha": XMAGE_FIRST_WAVE_SHA,
                "forge_first_wave_sha": FORGE_FIRST_WAVE_SHA,
            },
            "gate_verdict": "ERROR",
            "errors": errors,
            "provenance": provenance,
            "evidence_class": "UNKNOWN",
            "behavior_credit": "0/107",
        }
        out_path = out_dir / "WS71_REMAINING92_DENOMINATOR.json"
        out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"verdict": "ERROR", "errors": errors}, indent=2))
        return 1

    out_path = out_dir / "WS71_REMAINING92_DENOMINATOR.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "verdict": manifest["gate_verdict"],
                "FULL107_COUNT": manifest["counts"]["FULL107_COUNT"],
                "FIRST_WAVE_COUNT": manifest["counts"]["FIRST_WAVE_COUNT"],
                "REMAINING_COUNT": manifest["counts"]["REMAINING_COUNT"],
                "out": str(out_path),
            },
            indent=2,
        )
    )
    return 0 if manifest["gate_verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
