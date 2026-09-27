#!/usr/bin/env python3
"""WS79 deterministic package validator (stdlib only).

Validates qualification/ws79-h01-authority-remediation/ as a pure
authority/evidence package. Fails closed on any item below. Grants no
behavior credit and executes no engine.

Usage: python3 validate_ws79_h01.py [--root <package-dir>]
Exit 0: VALIDATION_PASS. Exit 1: VALIDATION_FAIL with reasons on stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_FILES = [
    "SOURCE_LOCK.md",
    "H01_RULES_ADJUDICATION.md",
    "H01_CORRECTED_CASES.json",
    "H01_IMPACT_LEDGER.json",
    "H01_AUTHORITY_PROVENANCE.json",
    "validate_ws79_h01.py",
    "WORKSTREAM_STATE.yaml",
]

EXPECTED_CASES = ["HUMILITY_FIRST", "CLONE_FIRST", "NO_HUMILITY"]

DISPOSITIONS = {
    "INVALIDATED_BY_ORACLE_CHANGE",
    "REQUALIFICATION_REQUIRED",
    "HISTORICAL_PROVENANCE_ONLY",
    "UNAFFECTED",
    "UNKNOWN",
}

PROVENANCE_REQUIRED_TOP = [
    "schema",
    "historical_provenance",
    "external_rules_sources",
    "coordinator_adjudication",
    "supersession_record",
    "behavior_credit",
    "current_standings",
    "evidence_classifications_used",
    "artifact_provenance",
]

HIST_PROV_REQUIRED = [
    "historical_terminal_head",
    "historical_terminal_tree",
    "audit_base_sha",
    "audit_base_tree",
    "file_blobs",
    "modification_statement",
]


def fail(reasons: list[str], detail: dict) -> int:
    detail["verdict"] = "VALIDATION_FAIL"
    detail["reasons"] = reasons
    print(json.dumps(detail, indent=2, sort_keys=True))
    return 1


def main() -> int:
    reasons: list[str] = []
    detail: dict = {"validator": "validate_ws79_h01.py", "schema": "ws79.validation.v1"}
    root = (
        Path(sys.argv[sys.argv.index("--root") + 1])
        if "--root" in sys.argv
        else Path(__file__).resolve().parent
    )
    detail["package_root"] = str(root)

    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            reasons.append(f"missing required file: {name}")

    cases_path = root / "H01_CORRECTED_CASES.json"
    cases_doc = None
    if cases_path.is_file():
        try:
            cases_doc = json.loads(cases_path.read_text())
        except json.JSONDecodeError as exc:
            reasons.append(f"H01_CORRECTED_CASES.json is not valid JSON: {exc}")
    if cases_doc is not None:
        cases = cases_doc.get("cases", [])
        ids = [c.get("case_id") for c in cases]
        for expected in EXPECTED_CASES:
            if ids.count(expected) == 0:
                reasons.append(f"required case absent: {expected}")
            elif ids.count(expected) > 1:
                reasons.append(f"required case duplicated: {expected}")
        extras = [i for i in ids if i not in EXPECTED_CASES]
        if extras:
            reasons.append(f"unexpected fourth case(s) present: {sorted(set(extras))}")
        if len(cases) != 3:
            reasons.append(f"case family must contain exactly three cases, found {len(cases)}")
        by_id = {c.get("case_id"): c for c in cases}
        # HUMILITY_FIRST must claim NO copy choice.
        hum = by_id.get("HUMILITY_FIRST", {})
        dec = hum.get("decision_occurrence", {})
        if dec.get("copy_choice_offered") is not False or dec.get("copy_choice_taken") is not False:
            reasons.append(
                "HUMILITY_FIRST claims a copy choice (must be offered=false, taken=false)"
            )
        if hum.get("copied_identity") is not None:
            reasons.append("HUMILITY_FIRST claims a copied identity (must be null)")
        # CLONE_FIRST must preserve copied identity.
        clf = by_id.get("CLONE_FIRST", {})
        cdec = clf.get("decision_occurrence", {})
        if cdec.get("copy_choice_offered") is not True or cdec.get("copy_choice_taken") is not True:
            reasons.append(
                "CLONE_FIRST fails to record the copy decision (must be offered=true, taken=true)"
            )
        if not clf.get("copied_identity"):
            reasons.append(
                "CLONE_FIRST fails to preserve copied identity (must name the Bear copy)"
            )
        post = str(clf.get("post_humility_discriminating_state", "")).lower()
        if "2/2" not in post and "bear" not in post:
            reasons.append("CLONE_FIRST lacks the 2/2-Bear post-Humility discriminator")
        # NO_HUMILITY must not suppress the copy decision.
        noh = by_id.get("NO_HUMILITY", {})
        ndec = noh.get("decision_occurrence", {})
        if ndec.get("copy_choice_offered") is not True or ndec.get("copy_choice_taken") is not True:
            reasons.append(
                "NO_HUMILITY suppresses the copy decision (must be offered=true, taken=true)"
            )
        # Each case needs discriminating + falsifying content.
        for cid in EXPECTED_CASES:
            c = by_id.get(cid, {})
            if not str(c.get("post_humility_discriminating_state", "")).strip():
                reasons.append(f"{cid} lacks a post-Humility discriminating state")
            if not str(c.get("falsifying_expectation", "")).strip():
                reasons.append(f"{cid} lacks a falsifying expectation")
            if not c.get("rules_authority_refs"):
                reasons.append(f"{cid} lacks rules authority references")
            if not str(c.get("initial_ordering", "")).strip():
                reasons.append(f"{cid} lacks an initial ordering")

    # Behavior credit must be zero everywhere in the package.
    prov_path = root / "H01_AUTHORITY_PROVENANCE.json"
    prov = None
    if prov_path.is_file():
        try:
            prov = json.loads(prov_path.read_text())
        except json.JSONDecodeError as exc:
            reasons.append(f"H01_AUTHORITY_PROVENANCE.json is not valid JSON: {exc}")
    if prov is not None:
        for key in PROVENANCE_REQUIRED_TOP:
            if key not in prov:
                reasons.append(f"mandatory authority provenance field absent: {key}")
        hist = (
            prov.get("historical_provenance", {})
            if isinstance(prov.get("historical_provenance"), dict)
            else {}
        )
        for key in HIST_PROV_REQUIRED:
            if key not in hist:
                reasons.append(f"mandatory historical provenance field absent: {key}")
        credit = (
            prov.get("behavior_credit", {}) if isinstance(prov.get("behavior_credit"), dict) else {}
        )
        if credit.get("behavior_credit_change") != 0:
            reasons.append("package claims behavior credit (behavior_credit_change must be 0)")
        if credit.get("full107_behavior") != "NOT_RUN":
            reasons.append("package implies Full107 behavior ran (must be NOT_RUN)")
        if str(credit.get("full107_behavior_credit", "")) != "0/107":
            reasons.append("package misstates Full107 behavior credit (must be 0/107)")
        if prov.get("supersession_record", {}).get("old_oracle_status") != "SUPERSEDED":
            reasons.append("old oracle status is not SUPERSEDED")
        standings = (
            prov.get("current_standings", {})
            if isinstance(prov.get("current_standings"), dict)
            else {}
        )
        if standings.get("first_wave_current_ranking") == "VALID":
            reasons.append("historical aggregates rewritten as current VALID ranking")
        if standings.get("first_wave_current_ranking") != "INVALID_PENDING_REQUALIFICATION":
            reasons.append("first_wave_current_ranking must be INVALID_PENDING_REQUALIFICATION")
        if standings.get("architecture_freeze") != "NOT_CLAIMED":
            reasons.append("architecture_freeze must be NOT_CLAIMED")
        if standings.get("production_provider") != "NOT_SELECTED":
            reasons.append("production_provider must be NOT_SELECTED")

    # Impact ledger: every entry needs a disposition from the vocabulary.
    ledger_path = root / "H01_IMPACT_LEDGER.json"
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_text())
        except json.JSONDecodeError as exc:
            ledger = None
            reasons.append(f"H01_IMPACT_LEDGER.json is not valid JSON: {exc}")
        if ledger is not None:
            entries = ledger.get("entries", [])
            if not entries:
                reasons.append("impact ledger has no entries")
            for i, entry in enumerate(entries):
                disp = entry.get("disposition")
                if not disp:
                    reasons.append(
                        f"impacted evidence entry lacks a disposition: {entry.get('id', f'index {i}')}"
                    )
                elif disp not in DISPOSITIONS:
                    reasons.append(
                        f"unknown disposition '{disp}' on entry {entry.get('id', f'index {i}')}"
                    )
                if not str(entry.get("requalification_requirement", "")).strip():
                    reasons.append(
                        f"entry lacks a requalification requirement: {entry.get('id', f'index {i}')}"
                    )
            pol = str(ledger.get("policy", ""))
            if "14/15" not in pol or "9/15" not in pol:
                reasons.append(
                    "ledger policy must name the preserved historical aggregates (14/15, 9/15)"
                )

    # Cross-file: no file in the package may claim a behavior PASS for a candidate.
    for name in [
        "H01_CORRECTED_CASES.json",
        "H01_IMPACT_LEDGER.json",
        "H01_AUTHORITY_PROVENANCE.json",
    ]:
        p = root / name
        if p.is_file():
            text = p.read_text()
            low = text.lower()
            if 'behavior_credit_change": 1' in text.replace(" ", ""):
                reasons.append(f"{name} claims behavior credit")
            if "candidate_behavior_status" in low and '"pass"' in low:
                reasons.append(f"{name} claims candidate behavior PASS")

    # Old-oracle rejection must be explicit in the adjudication record.
    adj = root / "H01_RULES_ADJUDICATION.md"
    if adj.is_file():
        atext = adj.read_text()
        if "SUPERSEDED" not in atext:
            reasons.append("adjudication record does not mark the old oracle SUPERSEDED")
        if "614.12" not in atext:
            reasons.append("adjudication record does not cite CR 614.12")

    if reasons:
        return fail(reasons, detail)
    detail["verdict"] = "VALIDATION_PASS"
    detail["reasons"] = []
    detail["checks"] = (
        "required files; exactly three cases; decision-occurrence semantics per case; discriminators+falsifiers; zero behavior credit; provenance fields; ledger dispositions; no current ranking; oracle supersession explicit"
    )
    print(json.dumps(detail, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
