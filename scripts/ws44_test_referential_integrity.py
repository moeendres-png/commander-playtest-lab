#!/usr/bin/env python3
"""WS-44 positive/negative regression tests for v1.0.4 referential integrity."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from ws44_build_successor_v2 import reference_audit


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
    assert any(o["semantic_id"] == "obj:micro-zero" for o in by_id["MICRO_STATE_BASED_ACTIONS"]["semantic_objects"])
    assert all(o["semantic_id"] != "obj:sba-memnite" for o in by_id["MICRO_STATE_BASED_ACTIONS"]["semantic_objects"])
    assert any(o["semantic_id"] == "obj:card01-ishai" for o in by_id["CARD_01"]["semantic_objects"])
    assert by_id["WS05-MP-TRIG-3"]["native_procedure"][2]["source_objects"] == ["obj:soulwarden-1", "obj:soulwarden-2", "obj:soulwarden-3"]
    assert "source_object" not in by_id["WS05-MP-TRIG-3"]["native_procedure"][2]
    assert by_id["HIDDEN_07"]["knowledge_state"]["viewer_states"][0]["temporary_permissions"][0]["viewer"] == "ALL_PLAYERS"

    # Permanent regression: original case-mismatched dangling MICRO target must fail.
    negative = copy.deepcopy(bundle)
    {r["fixture_id"]: r for r in negative["records"]}["MICRO_PRIORITY"]["stack_state"][0]["targets"][0] = "obj:P2-bears"
    _, neg_audit = reference_audit(negative)
    assert neg_audit["terminal_status"] == "FAIL"
    assert any(e.get("value") == "obj:P2-bears" and e.get("match_count") == 0 for row in neg_audit["records"] for e in row["errors"])

    case_negative = copy.deepcopy(bundle)
    {r["fixture_id"]: r for r in case_negative["records"]}["MICRO_STACK"]["stack_state"][0]["targets"][0] = "obj:MICRO-TARGET"
    assert reference_audit(case_negative)[1]["terminal_status"] == "FAIL"

    ambiguous = copy.deepcopy(bundle)
    amb = {r["fixture_id"]: r for r in ambiguous["records"]}["MICRO_PRIORITY"]
    amb["semantic_objects"].append(copy.deepcopy(next(o for o in amb["semantic_objects"] if o["semantic_id"] == "obj:micro-target")))
    _, amb_audit = reference_audit(ambiguous)
    assert amb_audit["terminal_status"] == "FAIL"
    assert any(e.get("reason") == "duplicate declaration" for row in amb_audit["records"] for e in row["errors"])

    alias_negative = copy.deepcopy(bundle)
    {r["fixture_id"]: r for r in alias_negative["records"]}["MICRO_PRIORITY"]["semantic_objects"][0]["aliases"] = ["obj:P2-bears"]
    assert reference_audit(alias_negative)[1]["terminal_status"] == "FAIL"

    # Event syntax must parse exact IDs, not consume the '-' from '->' or sentence '.'.
    assert by_id["PILOT_DECLARE_ATTACKER"]["expected_events"]["required_events"][1].startswith("attacker_declared:obj:p1-bears->")
    assert by_id["WS05-MP-ELIM-OWNED-3"]["terminal_postconditions"][0].find("obj:leave-owned.") >= 0

    print(json.dumps({
        "positive_repaired_bundle": "PASS",
        "historical_obj_P2_bears_negative": "PASS",
        "case_sensitive_negative": "PASS",
        "ambiguous_duplicate_negative": "PASS",
        "undeclared_alias_negative": "PASS",
        "sba_identity_rename": "PASS",
        "card01_identity_rename": "PASS",
        "multi_source_exact_vector": "PASS",
        "audience_scope_sentinel": "PASS",
        "embedded_delimiter_grammar": "PASS",
        "inventory_namespace_count": len(inventory["typed_namespaces"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
