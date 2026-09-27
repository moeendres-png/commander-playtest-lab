#!/usr/bin/env python3
"""WS90 deterministic validator (stdlib only). Fails closed unless all hard gates hold.

Usage: python3 qualification/ws90-rqc3-corrected-first-wave-reissue/verify.py
Exit 0: VALIDATION_PASS. Exit 1: VALIDATION_FAIL with reasons.
Grants zero behavior credit; executes no candidate.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "qualification" / "ws90-rqc3-corrected-first-wave-reissue"

EXPECTED_IDS = sorted(
    [
        "RQ-C3-A03",
        "RQ-C3-A04",
        "RQ-C3-B01",
        "RQ-C3-C01",
        "RQ-C3-C03",
        "RQ-C3-D06",
        "RQ-C3-E01",
        "RQ-C3-E02",
        "RQ-C3-F01",
        "RQ-C3-G02",
        "RQ-C3-G03",
        "RQ-C3-G04",
        "RQ-C3-H01",
        "RQ-C3-I01",
        "RQ-C3-J02",
    ]
)
EXPECTED_SHORT = "A03,A04,B01,C01,C03,D06,E01,E02,F01,G02,G03,G04,H01,I01,J02"
XMAGE_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c"
HIST_REV = "897d72f0b57bb8febe045870acaa3d2dba4bde56"
HIST_PACK_BLOB = "0db015ffee9dfcaabd2338da92c711d865059d81"
HIST_DECREQ_BLOB = "3707d8965e27ff823bea02b81b80ab13be396ed4"

FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(
        ("PASS " if cond else "FAIL ") + name + ((" :: " + detail) if detail and not cond else "")
    )
    if not cond:
        FAIL.append(name)


def load(name: str):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def git_show(rev: str, path: str) -> str:
    r = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        check(f"git show {path}", False, r.stderr[:300])
        return ""
    return r.stdout


def main() -> int:
    # Required files present
    for f in [
        "SOURCE_LOCK.md",
        "AUTHORITY_ADJUDICATION.md",
        "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json",
        "FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json",
        "NON_H01_EQUIVALENCE.json",
        "H01_BINDING.json",
        "WS60_HARNESS_IMPACT.json",
        "XMAGE_EXECUTION_READINESS.md",
        "FORGE_EXECUTION_READINESS.md",
        "VALIDATION.json",
        "FINAL_REPORT.md",
        "verify.py",
    ]:
        check(f"required file {f}", (PKG / f).is_file())

    try:
        pack = load("FIRST_WAVE_EXECUTION_PACK_CORRECTED.json")
    except Exception as e:
        check("pack valid JSON", False, str(e))
        pack = {}
    try:
        decreq = load("FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json")
    except Exception as e:
        check("decreq valid JSON", False, str(e))
        decreq = {}
    try:
        equiv = load("NON_H01_EQUIVALENCE.json")
    except Exception as e:
        check("equivalence valid JSON", False, str(e))
        equiv = {}
    try:
        binding = load("H01_BINDING.json")
    except Exception as e:
        check("h01 binding valid JSON", False, str(e))
        binding = {}
    try:
        impact = load("WS60_HARNESS_IMPACT.json")
    except Exception as e:
        check("ws60 impact valid JSON", False, str(e))
        impact = {}

    # Denominator gates
    check("exact denominator 15", pack.get("count") == 15, str(pack.get("count")))
    scen_ids = sorted([s.get("rqc3_scenario_id") for s in pack.get("scenarios", [])])
    check("exact ids 15", scen_ids == EXPECTED_IDS, str(scen_ids))
    short = ",".join([s.split("-")[-1] for s in scen_ids])
    check("exact short ids", short == EXPECTED_SHORT, short)
    check("H01 slot count 1", pack.get("h01_slot_count") == 1, str(pack.get("h01_slot_count")))
    # No extra slots, no REMAINING92/107 concepts
    blob = json.dumps(pack)
    check("no REMAINING92 concept", "REMAINING92" not in blob and "REMAINING_92" not in blob)
    check("no 107 denominator", pack.get("count") == 15 and '"count": 107' not in blob)

    # H01 family gates via pack h01_decision_occurrence + subcases
    h01_list = [s for s in pack.get("scenarios", []) if s.get("rqc3_scenario_id") == "RQ-C3-H01"]
    check("H01 single slot object", len(h01_list) == 1, str(len(h01_list)))
    h01 = h01_list[0] if h01_list else {}
    occ = h01.get("h01_decision_occurrence", {})
    hum = occ.get("HUMILITY_FIRST", {})
    check("HUMILITY_FIRST.offered false", hum.get("copy_choice_offered") is False, str(hum))
    check("HUMILITY_FIRST.taken false", hum.get("copy_choice_taken") is False, str(hum))
    check("HUMILITY_FIRST.identity null", hum.get("copied_identity") is None, str(hum))
    clf = occ.get("CLONE_FIRST", {})
    check("CLONE_FIRST.offered true", clf.get("copy_choice_offered") is True, str(clf))
    check("CLONE_FIRST.taken true", clf.get("copy_choice_taken") is True, str(clf))
    check("CLONE_FIRST Bear identity", clf.get("copied_identity") == "Runeclaw Bear", str(clf))
    noh = occ.get("NO_HUMILITY", {})
    check("NO_HUMILITY.offered true", noh.get("copy_choice_offered") is True, str(noh))
    check("NO_HUMILITY.taken true", noh.get("copy_choice_taken") is True, str(noh))
    check("NO_HUMILITY Bear identity", "Bear" in str(noh.get("copied_identity")), str(noh))

    # Post-Humility discriminators present
    h01_text = json.dumps(h01)
    h01_text_low = h01_text.lower()
    check(
        "HUMILITY_FIRST post-Humility 0/0 SBA death",
        "0/0" in h01_text
        and ("dies to" in h01_text_low or "sba" in h01_text_low or "704.5f" in h01_text),
        "missing 0/0 SBA discriminator",
    )
    check(
        "HUMILITY_FIRST NOT Bear",
        "NOT a 2/2 Bear" in h01_text or "NOT a 2/2" in h01_text,
        "missing NOT Bear guard",
    )
    check(
        "CLONE_FIRST post-Humility 2/2",
        "2/2" in h01_text and "Bear" in h01_text,
        "missing 2/2 Bear",
    )
    check(
        "NO_HUMILITY normal copy Bear",
        "NO_HUMILITY" in h01_text and "Bear" in h01_text and "copy" in h01_text_low,
        "missing NO_HUMILITY copy",
    )
    # 614.12 present, old semantics not silently retained
    check("H01 cites 614.12", "614.12" in h01_text, "missing 614.12")
    check(
        "old H01 COPY_CHOICE under Humility not retained",
        "CAST Clone; COPY_CHOICE: enter as Runeclaw Bear" not in h01_text,
        "old sequence retained",
    )
    check(
        "old semantic objective not retained verbatim",
        "Prove copy-before-Humility layering: Clone entering as a Bear under Humility must end as an ability-less 1/1."
        not in h01_text,
        "old objective retained",
    )
    check(
        "under-Humility 1/1 alone insufficient stated",
        "non-discriminating" in h01_text_low and "insufficient" in h01_text_low,
        "missing non-discriminating guard",
    )
    # Binding file mirrors
    check(
        "binding slot count 1",
        binding.get("h01_slot_count") == 1,
        str(binding.get("h01_slot_count")),
    )
    by_case = {c.get("case_id"): c for c in binding.get("cases", [])}
    check(
        "binding 3 cases",
        sorted(by_case.keys()) == ["CLONE_FIRST", "HUMILITY_FIRST", "NO_HUMILITY"],
        str(sorted(by_case.keys())),
    )
    bh = by_case.get("HUMILITY_FIRST", {}).get("decision_occurrence", {})
    check(
        "binding HUMILITY_FIRST false/false/null",
        bh.get("copy_choice_offered") is False
        and bh.get("copy_choice_taken") is False
        and by_case.get("HUMILITY_FIRST", {}).get("copied_identity") is None,
        str(bh),
    )
    check(
        "binding old oracle SUPERSEDED",
        binding.get("historical_oracle_status") == "SUPERSEDED",
        str(binding.get("historical_oracle_status")),
    )
    check(
        "binding pass criteria 1/1 insufficient",
        "alone" in str(binding.get("pass_criteria", "")).lower()
        or "insufficient" in str(binding.get("pass_criteria", "")).lower(),
        "missing guard",
    )

    # Other 14 fingerprints unchanged + drift 0
    check(
        "NON_H01_SEMANTIC_DRIFT 0",
        equiv.get("non_h01_semantic_drift") == 0,
        str(equiv.get("non_h01_semantic_drift")),
    )
    # Recompute independently from historical pack
    hist_pack_text = git_show(
        HIST_REV,
        "research/candidate-qualification/common/rq-c3/RQ_C3_FIRST_WAVE_EXECUTION_PACK.json",
    )
    try:
        hist_pack = json.loads(hist_pack_text)
    except Exception as e:
        check("historical pack loads", False, str(e))
        hist_pack = {"scenarios": []}
    hist_by = {s["rqc3_scenario_id"]: s for s in hist_pack.get("scenarios", [])}
    new_by = {s["rqc3_scenario_id"]: s for s in pack.get("scenarios", [])}
    sem_fields = equiv.get("semantic_fields", [])
    check("semantic fields cover required", len(sem_fields) >= 9, str(sem_fields))
    for sid in EXPECTED_IDS:
        if sid == "RQ-C3-H01":
            continue
        h = hist_by.get(sid, {})
        n = new_by.get(sid, {})

        # fingerprint over semantic subset
        def subset(s):
            d = {"scenario_id": s.get("rqc3_scenario_id")}
            for f in sem_fields:
                if f == "scenario_id":
                    continue
                d[f] = s.get(f)
            return d

        hf = hashlib.sha256(
            (json.dumps(subset(h), sort_keys=True, indent=2) + "\n").encode()
        ).hexdigest()
        nf = hashlib.sha256(
            (json.dumps(subset(n), sort_keys=True, indent=2) + "\n").encode()
        ).hexdigest()
        check(f"{sid} fingerprint match", hf == nf, f"{hf[:12]} vs {nf[:12]}")
        check(
            f"{sid} byte-equivalent",
            json.dumps(h, sort_keys=True, indent=2) + "\n"
            == json.dumps(n, sort_keys=True, indent=2) + "\n",
            "not byte-equivalent",
        )
    # Equivalence file matches recomputation
    for row in equiv.get("results", []):
        sid = row.get("rqc3_scenario_id")
        if sid == "RQ-C3-H01":
            check("equivalence excludes H01", False, "H01 in non-H01 file")
        check(f"equiv {sid} match true", row.get("match") is True, str(row))

    # Decision union mechanically derived
    per = decreq.get("per_scenario", {})
    check("decreq count 15", decreq.get("count") == 15, str(decreq.get("count")))
    check(
        "decreq per_scenario 15 keys", sorted(per.keys()) == EXPECTED_IDS, str(sorted(per.keys()))
    )
    recomputed: dict[str, list[str]] = {}
    for sid, kinds in per.items():
        for k in kinds:
            recomputed.setdefault(k, []).append(sid)
    for k in recomputed:
        recomputed[k] = sorted(recomputed[k])
    check(
        "union mechanically derived",
        dict(sorted(recomputed.items())) == dict(sorted(decreq.get("union", {}).items())),
        "union mismatch",
    )
    recomp_counts = {k: len(v) for k, v in recomputed.items()}
    check("union_counts derived", recomp_counts == decreq.get("union_counts"), "counts mismatch")
    check(
        "union has 20 kinds", len(decreq.get("union", {})) == 20, str(len(decreq.get("union", {})))
    )
    check(
        "copy choices in union", "copy choices" in decreq.get("union", {}), "missing copy choices"
    )
    check(
        "copy choices sole carrier H01",
        decreq.get("union", {}).get("copy choices") == ["RQ-C3-H01"],
        str(decreq.get("union", {}).get("copy choices")),
    )
    # No generic ordering categories beyond allowed
    union_keys = set(decreq.get("union", {}).keys())
    check("no generic ordering", "ordering" not in union_keys, str(union_keys))
    check("no may kind", "may" not in [k.lower() for k in union_keys], str(union_keys))
    # H01 subcase distinction
    sub = decreq.get("h01_subcase_kinds", {})
    check(
        "H01-A lacks copy",
        "copy choices" not in sub.get("RQ-C3-H01-HUMILITY_FIRST", []),
        str(sub.get("RQ-C3-H01-HUMILITY_FIRST")),
    )
    check(
        "H01-B has copy",
        "copy choices" in sub.get("RQ-C3-H01-CLONE_FIRST", []),
        str(sub.get("RQ-C3-H01-CLONE_FIRST")),
    )
    check(
        "H01-C has copy",
        "copy choices" in sub.get("RQ-C3-H01-NO_HUMILITY", []),
        str(sub.get("RQ-C3-H01-NO_HUMILITY")),
    )
    check(
        "must-not-occur copy for A",
        decreq.get("must_not_occur", {}).get("RQ-C3-H01-HUMILITY_FIRST") == ["copy choices"],
        str(decreq.get("must_not_occur")),
    )

    # Historical files untouched: worktree diff must not touch forbidden surfaces
    r = subprocess.run(
        ["git", "status", "--porcelain=v1"], capture_output=True, text=True, cwd=str(ROOT)
    )
    changed = [line[3:].split(" -> ")[-1] for line in r.stdout.splitlines() if line.strip()]
    # git diff --name-only HEAD for committed changes? status shows worktree; also check diff HEAD
    r2 = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, cwd=str(ROOT)
    )
    diff_files = [line.strip() for line in r2.stdout.splitlines() if line.strip()]
    all_touched = set(changed) | set(diff_files)
    # staged? git diff --cached
    r3 = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, cwd=str(ROOT)
    )
    all_touched |= {line.strip() for line in r3.stdout.splitlines() if line.strip()}
    forbidden_prefixes = [
        "qualification/ws79-h01-authority-remediation/",
        "candidate-qualification/ws60-xmage-rqc3-first-wave/",
        "engine-bridge/src/main/java/",
        "config/rules_engines.json",
    ]
    for f in all_touched:
        # allow only ws90 package + manifests + generator cleanup? generator is in ws90 package (allowed as new file, will be removed or kept? must not be extra?)
        # For historical-files-untouched gate, only check forbidden prefixes
        for pref in forbidden_prefixes:
            if f.startswith(pref):
                check(f"historical untouched {pref}", False, f"touched {f}")
    check(
        "historical files untouched (no forbidden touch)",
        all([not f.startswith(tuple(forbidden_prefixes)) for f in all_touched]),
        str(sorted(all_touched)[:5]),
    )
    # Also verify historical blobs still resolvable
    for blob_name, (rev_path, expect) in {
        "pack blob": (
            "research/candidate-qualification/common/rq-c3/RQ_C3_FIRST_WAVE_EXECUTION_PACK.json",
            HIST_PACK_BLOB,
        ),
        "decreq blob": (
            "research/candidate-qualification/common/rq-c3/RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json",
            HIST_DECREQ_BLOB,
        ),
    }.items():
        rr = subprocess.run(
            ["git", "rev-parse", f"{HIST_REV}:{rev_path}"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        # rev-parse gives blob sha? Actually need git ls-tree or hash-object? Use git rev-parse for blob id
        blob_id = rr.stdout.strip()
        check(f"historical {blob_name} resolvable", blob_id == expect, f"{blob_id} vs {expect}")

    # Current XMage pin
    try:
        engines = json.loads((ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    except Exception as e:
        check("rules_engines loads", False, str(e))
        engines = {}
    check(
        "current XMage pin cfc36f",
        engines.get("primary_engine", {}).get("commit") == XMAGE_PIN,
        str(engines.get("primary_engine", {}).get("commit")),
    )
    check(
        "pack xmage pin matches",
        pack.get("reissue_provenance", {}).get("current_xmage_pin") == XMAGE_PIN,
        str(pack.get("reissue_provenance", {}).get("current_xmage_pin")),
    )
    check(
        "provider selection false",
        engines.get("current_runtime", {}).get("provider_selected") is False,
        str(engines.get("current_runtime", {})),
    )
    check(
        "production_provider null",
        engines.get("current_runtime", {}).get("production_provider") is None,
        str(engines.get("current_runtime", {})),
    )
    check(
        "provider_decision NO_PROVIDER_READY",
        engines.get("provider_decision") == "NO_PROVIDER_READY",
        str(engines.get("provider_decision")),
    )

    # WS60 production edits accounted
    deltas = impact.get("production_deltas", [])
    check("5 production deltas accounted", len(deltas) == 5, str(len(deltas)))
    for d in deltas:
        check(
            f"delta {d.get('delta_id')} STILL_REQUIRED",
            d.get("classification") == "STILL_REQUIRED_FOR_EXECUTION",
            str(d.get("classification")),
        )
    check(
        "WS60 production edits imported 0",
        impact.get("ws60_production_edits_imported") == 0,
        str(impact.get("ws60_production_edits_imported")),
    )
    check(
        "behavior credit imported 0",
        impact.get("behavior_credit_imported") == 0,
        str(impact.get("behavior_credit_imported")),
    )
    harness = impact.get("test_harness_files", [])
    check("13 harness files classified", len(harness) == 13, str(len(harness)))
    allowed_classes = {
        "REUSABLE_AS_TEST_INFRASTRUCTURE",
        "REQUIRES_REWRITE",
        "BOUND_TO_OLD_BRIDGE",
        "BOUND_TO_OLD_ORACLE",
        "UNSAFE_SECOND_RULES_LOGIC",
        "OBSOLETE",
        "UNKNOWN",
    }
    for h in harness:
        check(
            f"harness {h.get('file')} class valid",
            h.get("classification") in allowed_classes,
            str(h.get("classification")),
        )
    check(
        "no UNSAFE harness without evidence",
        all([h.get("classification") != "UNSAFE_SECOND_RULES_LOGIC" for h in harness]),
        "unsafe found",
    )
    pilot = impact.get("pilot_audit", {}).get("items", [])
    check("pilot 10 behaviors audited", len(pilot) == 10, str(len(pilot)))
    for item in pilot:
        check(f"pilot {item.get('behavior')} absent", item.get("present") is False, str(item))

    # Zero behavior credit, NOT_RUN, Freeze/Provider
    check(
        "pack behavior 0",
        pack.get("behavior_credit_change") == 0,
        str(pack.get("behavior_credit_change")),
    )
    check(
        "pack candidate NOT_RUN",
        pack.get("candidate_behavior_status") == "NOT_RUN",
        str(pack.get("candidate_behavior_status")),
    )
    check(
        "pack Full107 NOT_RUN",
        pack.get("full107") == "NOT_RUN" and pack.get("full107_behavior") == "NOT_RUN",
        str(pack.get("full107")),
    )
    check(
        "pack Freeze NOT_CLAIMED",
        pack.get("architecture_freeze") == "NOT_CLAIMED",
        str(pack.get("architecture_freeze")),
    )
    check(
        "pack Provider NOT_SELECTED",
        pack.get("production_provider") == "NOT_SELECTED",
        str(pack.get("production_provider")),
    )
    check(
        "pack ranking INVALID",
        pack.get("first_wave_current_ranking") == "INVALID_PENDING_REQUALIFICATION",
        str(pack.get("first_wave_current_ranking")),
    )
    for s in pack.get("scenarios", []):
        check(
            f"{s.get('rqc3_scenario_id')} NOT_RUN",
            s.get("candidate_behavior_status") == "NOT_RUN",
            str(s.get("candidate_behavior_status")),
        )
        check(
            f"{s.get('rqc3_scenario_id')} credit 0",
            s.get("behavior_credit") == 0,
            str(s.get("behavior_credit")),
        )
    check(
        "decreq NOT_RUN",
        decreq.get("candidate_behavior_status") == "NOT_RUN",
        str(decreq.get("candidate_behavior_status")),
    )

    # Deterministic JSON rebuild for our 4 JSONs
    for name in [
        "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json",
        "FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json",
        "NON_H01_EQUIVALENCE.json",
        "H01_BINDING.json",
        "WS60_HARNESS_IMPACT.json",
    ]:
        p = PKG / name
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            canon = json.dumps(obj, indent=2, sort_keys=True) + "\n"
            check(
                f"deterministic {name}", p.read_text(encoding="utf-8") == canon, "nondeterministic"
            )
        except Exception as e:
            check(f"deterministic {name}", False, str(e))

    print()
    if FAIL:
        print(f"VALIDATION_FAIL: {len(FAIL)} check(s): {FAIL}")
        return 1
    print("VALIDATION_PASS: all WS90 hard gates green (zero behavior credit, no execution).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
