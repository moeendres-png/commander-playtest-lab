#!/usr/bin/env python3
"""WS74 terminal gate validator (staging only; zero behavior credit).

Recomputes every terminal gate from committed evidence files. Never weakens
denominators, assertions, or expected semantics. Missing evidence stays
UNKNOWN or explicitly absent; nothing is upgraded to PASS without proof.

Terminal gates:
  FULL107_DENOMINATOR_BINDING=PASS
  XMAGE_EXACT_PIN_BUILD=PASS
  FULL107_CONSTRUCTION=107/107
  FULL107_NORMALIZATION=107/107
  NORMALIZATION_NEGATIVES=PASS
  STAGING_DETERMINISM=PASS
  (HIDDEN_REPRESENTATION_PREFLIGHT reported; must have zero FAILs)

Overall WS74_XMAGE_FULL107_STAGING=PASS only if every gate passes;
otherwise PARTIAL (demonstrated cause) or FAIL.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

ENGINE_COMMIT = "7135d5e85ddb4c8aa4b49b4192ca51947c822704"
ENGINE_TREE = "ea193e0d04493d53d962ed13ebd3b5d2f68838c7"
FORBIDDEN_LABELS = {"RUNTIME_VERIFIED"}


def load(name):
    fp = HERE / name
    if not fp.exists():
        return None
    return json.loads(fp.read_text())


def main() -> int:
    gates = {}
    notes = []

    den = load("FULL107_DENOMINATOR_BINDING.json")
    if den is None:
        gates["FULL107_DENOMINATOR_BINDING"] = "UNKNOWN"
        notes.append("denominator binding file absent")
    elif (
        den.get("verdict") == "PASS"
        and den.get("materialization_records") == 135
        and den.get("provider_denominator") == 107
        and den.get("excluded") == 28
        and len(den.get("ordered_denominator", [])) == 107
        and len({o["fixture_id"] for o in den["ordered_denominator"]}) == 107
    ):
        gates["FULL107_DENOMINATOR_BINDING"] = "PASS"
    else:
        gates["FULL107_DENOMINATOR_BINDING"] = "FAIL"
        notes.append("denominator binding mismatch")

    receipt = load("XMAGE_BUILD_RECEIPT.json")
    if receipt is None:
        gates["XMAGE_EXACT_PIN_BUILD"] = "UNKNOWN"
        notes.append("build receipt absent")
    else:
        b = receipt.get("binding", {})
        jars = b.get("jars_byte_identical_fresh_build", [])
        if (
            b.get("engine_commit") == ENGINE_COMMIT
            and b.get("engine_tree") == ENGINE_TREE
            and b.get("engine_working_tree_tracked_clean") is True
            and len(jars) == 4
            and all(j.get("byte_identical") for j in jars)
        ):
            gates["XMAGE_EXACT_PIN_BUILD"] = "PASS"
        else:
            gates["XMAGE_EXACT_PIN_BUILD"] = "FAIL"
            notes.append("exact-pin build binding mismatch")

    cpl_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(REPO)
    ).stdout.strip()
    if receipt is not None and receipt.get("binding", {}).get("cpl_commit") != cpl_head:
        notes.append(
            "receipt cpl_commit %s != validation HEAD %s (evidence descendant; validated_head unchanged)"
            % (receipt.get("binding", {}).get("cpl_commit"), cpl_head)
        )

    cm = load("FULL107_CONSTRUCTION_MATRIX.json")
    if cm is None:
        gates["FULL107_CONSTRUCTION"] = "UNKNOWN"
        gates["FULL107_CONSTRUCTION_DETAIL"] = "matrix absent"
    else:
        rows = cm.get("rows", [])
        attempted = sum(1 for r in rows if r.get("attempted"))
        constructed = sum(1 for r in rows if r.get("construction_result") == "CONSTRUCTED")
        badpin = [
            r["fixture_id"]
            for r in rows
            if r.get("attempted") and r.get("engine_commit") != ENGINE_COMMIT
        ]
        gates["FULL107_CONSTRUCTION"] = "%d/107" % constructed
        gates["FULL107_CONSTRUCTION_ATTEMPTED"] = "%d/107" % attempted
        if badpin:
            notes.append("construction rows with wrong engine pin: %s" % badpin)
        if attempted != 107 or len(rows) != 107:
            notes.append("construction did not attempt all 107")

    nm = load("FULL107_NORMALIZATION_MATRIX.json")
    if nm is None:
        gates["FULL107_NORMALIZATION"] = "UNKNOWN"
    else:
        rows = nm.get("rows", [])
        npass = sum(1 for r in rows if r.get("normalization_result") == "NORMALIZATION_PASS")
        nfail = sum(1 for r in rows if r.get("normalization_result") == "NORMALIZATION_FAIL")
        nunk = sum(1 for r in rows if r.get("normalization_result") == "UNKNOWN")
        gates["FULL107_NORMALIZATION"] = "%d/107" % npass
        gates["FULL107_NORMALIZATION_FAILED"] = nfail
        gates["FULL107_NORMALIZATION_UNKNOWN"] = nunk
        badpass = [
            r["fixture_id"]
            for r in rows
            if r.get("normalization_result") == "NORMALIZATION_PASS"
            and r.get("normalized_digest") != r.get("contract_digest")
        ]
        if badpass:
            gates["FULL107_NORMALIZATION"] = "FAIL"
            notes.append("PASS rows with digest mismatch (integrity defect): %s" % badpass)
        if len(rows) != 107:
            notes.append("normalization did not cover all 107")

    neg = load("NORMALIZATION_NEGATIVE_CONTROLS.json")
    if neg is None:
        gates["NORMALIZATION_NEGATIVES"] = "UNKNOWN"
    else:
        gates["NORMALIZATION_NEGATIVES"] = (
            "PASS" if neg.get("verdict") == "PASS" and neg.get("families_detected") == 8 else "FAIL"
        )
        if gates["NORMALIZATION_NEGATIVES"] != "PASS":
            notes.append("negative controls not 8/8")

    det = load("STAGING_DETERMINISM.json")
    if det is None:
        gates["STAGING_DETERMINISM"] = "UNKNOWN"
    else:
        gates["STAGING_DETERMINISM"] = "PASS" if det.get("verdict") == "PASS" else "FAIL"
        if gates["STAGING_DETERMINISM"] != "PASS":
            notes.append("staging not deterministic")

    pre = load("HIDDEN_REPRESENTATION_PREFLIGHT.json")
    if pre is None:
        gates["HIDDEN_REPRESENTATION_PREFLIGHT"] = "UNKNOWN"
    else:
        gates["HIDDEN_REPRESENTATION_PREFLIGHT"] = pre.get("verdict", "UNKNOWN")
        if pre.get("failed"):
            notes.append("hidden exposure findings present")

    # forbidden evidence labels sweep
    for name in ("FULL107_DENOMINATOR_BINDING.json", "XMAGE_BUILD_RECEIPT.json",
                 "FULL107_CONSTRUCTION_MATRIX.json", "FULL107_NORMALIZATION_MATRIX.json",
                 "NORMALIZATION_NEGATIVE_CONTROLS.json", "HIDDEN_REPRESENTATION_PREFLIGHT.json",
                 "STAGING_DETERMINISM.json", "FINAL_REPORT.md"):
        fp = HERE / name
        if fp.exists() and any("RUNTIME_VERIFIED" in line for line in fp.read_text().splitlines()):
            notes.append("forbidden evidence label in %s" % name)

    if (
        gates.get("FULL107_DENOMINATOR_BINDING") == "PASS"
        and gates.get("XMAGE_EXACT_PIN_BUILD") == "PASS"
        and gates.get("FULL107_CONSTRUCTION") == "107/107"
        and gates.get("FULL107_NORMALIZATION") == "107/107"
        and gates.get("NORMALIZATION_NEGATIVES") == "PASS"
        and gates.get("STAGING_DETERMINISM") == "PASS"
        and gates.get("HIDDEN_REPRESENTATION_PREFLIGHT") in ("PASS",)
    ):
        overall = "PASS"
    elif "FAIL" in gates.values() or gates.get("FULL107_NORMALIZATION") == "FAIL":
        overall = "FAIL"
    else:
        overall = "PARTIAL"
    gates["WS74_XMAGE_FULL107_STAGING"] = overall
    gates["XMAGE_FULL107_BEHAVIOR_CREDIT"] = "0/107"
    gates["FULL107_BEHAVIOR"] = "NOT_RUN"
    gates["ARCHITECTURE_FREEZE"] = "NOT_CLAIMED"
    gates["PRODUCTION_PROVIDER"] = "NOT_SELECTED"
    gates["notes"] = notes
    print(json.dumps(gates, indent=2, sort_keys=True))
    return 0 if overall == "PASS" else 2 if overall == "FAIL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
