#!/usr/bin/env python3
"""Adjudicate the narrow WS40 v1.0.3 observer identity projection.

Input is the already source-locked corpuswide identity-normalization audit.
No requested state is supplied to the runtime observer. The proposed projection
is a representation rule over frozen provider-neutral identity metadata only:

  * player IDs remain player IDs;
  * for a uniquely bound Card target, preserve current semantic_id by default;
  * only when card_lineage_id carries a complete object-domain identity
    (`line:obj:...`) use that suffix as the normalized card identity;
  * never case-fold, match card names, infer owner/controller, or resolve an
    otherwise unresolved target.

This program grants no runtime credit. It only proves whether the proposed
projection is lossless for every already-resolved frozen stack target in the
exact WS41 107-record denominator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_SOURCE = {
    "commit": "24152acf36b5a560c23ccacfed3f31d3039537eb",
    "tree": "428bbe58b2ea7b869200521092a8768108029b47",
    "materialization_sha256": "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5",
    "denominator_count": 107,
}
RESOLVED_CARD = {"EXACT_SEMANTIC_ID", "UNIQUE_LINEAGE_SUFFIX"}


def projected(row: dict) -> str | None:
    status = row["resolution_status"]
    if status == "PLAYER_ID":
        return row["requested_target"]
    if status not in RESOLVED_CARD:
        return None
    sid = row.get("resolved_semantic_id")
    suffix = row.get("resolved_lineage_suffix")
    if isinstance(suffix, str) and suffix.startswith("obj:"):
        return suffix
    return sid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audit", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    audit = json.loads(args.audit.read_text())
    for k, v in EXPECTED_SOURCE.items():
        if audit.get("source_lock", {}).get(k) != v:
            raise SystemExit(f"source-lock mismatch for {k}")
    if audit.get("record_count") != 107:
        raise SystemExit("audit denominator is not 107")
    if audit.get("historical_runtime_credit_imported") != 0:
        raise SystemExit("historical runtime credit is nonzero")

    rows = audit.get("stack_target_rows") or []
    checked = []
    breaks = []
    unresolved = []
    ambiguous = []
    changed_projection_rows = []
    for row in rows:
        status = row["resolution_status"]
        p = projected(row)
        out = {
            "fixture_id": row["fixture_id"],
            "denominator_index": row["denominator_index"],
            "source_semantic_id": row.get("source_semantic_id"),
            "requested_target": row["requested_target"],
            "resolution_status": status,
            "resolved_semantic_id": row.get("resolved_semantic_id"),
            "resolved_lineage_suffix": row.get("resolved_lineage_suffix"),
            "refined_projected_identity": p,
            "projection_equals_requested": p == row["requested_target"] if p is not None else False,
        }
        checked.append(out)
        if status.startswith("AMBIGUOUS"):
            ambiguous.append(out)
        elif status == "UNRESOLVED":
            unresolved.append(out)
        elif p != row["requested_target"]:
            breaks.append(out)
        if status in RESOLVED_CARD and p != row.get("resolved_semantic_id"):
            changed_projection_rows.append(out)

    resolved_or_player = [r for r in checked if r["resolution_status"] in RESOLVED_CARD | {"PLAYER_ID"}]
    safe = (
        len(breaks) == 0
        and len(ambiguous) == 0
        and audit.get("duplicate_lineage_suffix_group_count") == 0
        and all(r["projection_equals_requested"] for r in resolved_or_player)
    )
    report = {
        "schema_version": "commander-lab.ws40-v1.0.3-identity-normalization-adjudication/1.0.0",
        "source_audit_schema": audit.get("schema_version"),
        "source_lock": audit["source_lock"],
        "historical_runtime_credit_imported": 0,
        "candidate_rule": {
            "player_identity": "PRESERVE",
            "card_default": "PRESERVE_CURRENT_SEMANTIC_ID",
            "card_lineage_override": "ONLY_IF_CARD_LINEAGE_ID_SUFFIX_STARTS_WITH_obj:",
            "runtime_requested_target_dependency": False,
            "case_folding": False,
            "card_name_matching": False,
            "owner_controller_guessing": False,
            "unresolved_target_inference": False,
        },
        "stack_target_reference_count": len(checked),
        "resolved_or_player_target_count": len(resolved_or_player),
        "projection_break_count": len(breaks),
        "ambiguous_target_count": len(ambiguous),
        "unresolved_target_count": len(unresolved),
        "duplicate_lineage_suffix_group_count": audit.get("duplicate_lineage_suffix_group_count"),
        "changed_projection_row_count": len(changed_projection_rows),
        "safe_for_observer_stack_card_identity_projection": safe,
        "qualification_credit_granted": False,
        "checked_rows": checked,
        "projection_breaks": breaks,
        "ambiguous_targets": ambiguous,
        "unresolved_targets": unresolved,
        "changed_projection_rows": changed_projection_rows,
        "scope_limit": "STACK_CARD_TARGET_NORMALIZATION_ONLY; does not authorize attachment/combat/global semanticOf changes",
        "next_gate": "If safe=true, implement stack-observer-only projection and rerun construction 0->107. Unresolved targets remain fail-closed."
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "safe": safe,
        "targets": len(checked),
        "resolved_or_player": len(resolved_or_player),
        "breaks": len(breaks),
        "ambiguous": len(ambiguous),
        "unresolved": len(unresolved),
        "changed": len(changed_projection_rows),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
