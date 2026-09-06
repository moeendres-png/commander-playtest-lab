#!/usr/bin/env python3
"""WS-44 positive/negative regression tests for the v1.0.4 referential-integrity model."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from ws44_build_successor import reference_audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("materialization", type=Path)
    args = ap.parse_args()
    bundle = json.loads(args.materialization.read_text(encoding="utf-8"))

    inventory, audit = reference_audit(bundle)
    assert audit["terminal_status"] == "PASS", audit["defect_count"]
    assert audit["defect_count"] == 0
    by_id = {r["fixture_id"]: r for r in bundle["records"]}
    for fid in ("MICRO_PRIORITY", "MICRO_STACK"):
        assert by_id[fid]["stack_state"][0]["targets"] == ["obj:micro-target"]

    negative = copy.deepcopy(bundle)
    neg = {r["fixture_id"]: r for r in negative["records"]}["MICRO_PRIORITY"]
    neg["stack_state"][0]["targets"][0] = "obj:P2-bears"
    _, neg_audit = reference_audit(negative)
    assert neg_audit["terminal_status"] == "FAIL"
    assert neg_audit["defect_count"] > 0
    assert any(
        e.get("value") == "obj:P2-bears" and e.get("match_count") == 0
        for row in neg_audit["records"] for e in row["errors"]
    )

    case_negative = copy.deepcopy(bundle)
    case = {r["fixture_id"]: r for r in case_negative["records"]}["MICRO_STACK"]
    case["stack_state"][0]["targets"][0] = "obj:MICRO-TARGET"
    _, case_audit = reference_audit(case_negative)
    assert case_audit["terminal_status"] == "FAIL"

    ambiguous = copy.deepcopy(bundle)
    amb = {r["fixture_id"]: r for r in ambiguous["records"]}["MICRO_PRIORITY"]
    amb["semantic_objects"].append(copy.deepcopy(next(o for o in amb["semantic_objects"] if o["semantic_id"] == "obj:micro-target")))
    _, amb_audit = reference_audit(ambiguous)
    assert amb_audit["terminal_status"] == "FAIL"
    assert any(
        e.get("reason") == "duplicate semantic object declaration"
        for row in amb_audit["records"] for e in row["errors"]
    )

    alias_negative = copy.deepcopy(bundle)
    alias_record = {r["fixture_id"]: r for r in alias_negative["records"]}["MICRO_PRIORITY"]
    alias_record["semantic_objects"][0]["aliases"] = ["obj:P2-bears"]
    _, alias_audit = reference_audit(alias_negative)
    assert alias_audit["terminal_status"] == "FAIL"

    print(json.dumps({
        "positive_repaired_bundle": "PASS",
        "historical_obj_P2_bears_negative": "PASS",
        "case_sensitive_negative": "PASS",
        "ambiguous_duplicate_negative": "PASS",
        "undeclared_alias_negative": "PASS",
        "inventory_namespace_count": len(inventory["typed_namespaces"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
