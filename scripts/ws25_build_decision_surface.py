#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED = {
    "EXTERNALLY_IMPLEMENTED",
    "AUTOMATIC_NONDISCRETIONARY",
    "PROVEN_UNREACHABLE",
    "FAIL_CLOSED_UNSUPPORTED",
}

# WS-23 implemented these callbacks only for deliberately bounded semantic subsets.
# A callback is not globally EXTERNALLY_IMPLEMENTED until every production-reachable
# discretionary path through that callback is externally representable and Forge-revalidated.
PARTIAL_CALLBACKS: dict[str, list[str]] = {
    "chooseTargetsFor": ["exactly one visible Forge-valid target"],
    "chooseModeForAbility": ["min=1,num=1,allowRepeat=false"],
    "getCostDecisionMaker": ["CostPartMana deferred to controller; all other cost visitors fail closed"],
    "applyManaToCost": ["Forge-filtered already-floating mana only"],
    "declareAttackers": ["at most one possible attacker; Forge-valid defender selection"],
    "declareBlockers": ["at most one attacker and one blocker"],
    "assignCombatDamage": ["unique single-blocker non-trample assignment"],
    "orderSimultaneousSa": ["exactly two simultaneous Soul Warden triggers in Gate-D"],
    "orderAndPlaySimultaneousSa": ["bounded native trigger pair orchestration"],
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_classification(value: str) -> str:
    if value == "RULES_AUTOMATIC_NONDISCRETIONARY":
        return "AUTOMATIC_NONDISCRETIONARY"
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2-mapping", type=Path, required=True)
    ap.add_argument("--broad-mapping", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    v2 = load(args.v2_mapping)
    broad = load(args.broad_mapping)
    if v2.get("abstract_method_count") != 109 or broad.get("abstract_method_count") != 109:
        raise AssertionError("pinned Forge PlayerController abstract surface drifted from 109 callbacks")

    broad_by_signature = {row["signature"]: row for row in broad["callbacks"]}
    rows: list[dict[str, Any]] = []
    for item in v2["callbacks"]:
        signature = item["signature"]
        name = item["name"]
        broad_item = broad_by_signature.get(signature)
        v2_class = normalize_classification(item["classification"])
        broad_class = (
            normalize_classification(broad_item["classification"])
            if broad_item is not None
            else "FAIL_CLOSED_UNSUPPORTED"
        )

        implemented_subsets = list(PARTIAL_CALLBACKS.get(name, []))
        if name in PARTIAL_CALLBACKS:
            classification = "FAIL_CLOSED_UNSUPPORTED"
            reason = (
                "At least one production-reachable semantic path is intentionally unsupported; "
                "bounded qualified subsets are recorded separately."
            )
        else:
            candidates = {v2_class, broad_class}
            if "EXTERNALLY_IMPLEMENTED" in candidates:
                classification = "EXTERNALLY_IMPLEMENTED"
                reason = "WS-23 provider routes this callback through explicit external choice or native Forge execution."
            elif "AUTOMATIC_NONDISCRETIONARY" in candidates:
                classification = "AUTOMATIC_NONDISCRETIONARY"
                reason = "Callback is treated as non-discretionary in the qualified provider path."
            elif "PROVEN_UNREACHABLE" in candidates:
                classification = "PROVEN_UNREACHABLE"
                reason = "Reachability proof inherited from generated provider mapping."
            else:
                classification = "FAIL_CLOSED_UNSUPPORTED"
                reason = "No complete production-reachable external implementation exists; generated controller throws fail closed."

        if classification not in ALLOWED:
            raise AssertionError(f"illegal WS-25 callback classification: {classification}")
        rows.append(
            {
                "name": name,
                "signature": signature,
                "classification": classification,
                "implemented_subsets": implemented_subsets,
                "v2_ws23_classification": v2_class,
                "broad_ws23_classification": broad_class,
                "reason": reason,
            }
        )

    if len(rows) != 109 or len({row["signature"] for row in rows}) != 109:
        raise AssertionError("decision-surface rows must contain each abstract signature exactly once")

    counts = {key: sum(row["classification"] == key for row in rows) for key in sorted(ALLOWED)}
    output = {
        "schema_version": "ws25-player-controller-decision-surface/1.0.0",
        "forge_player_controller_abstract_method_count": 109,
        "allowed_classifications": sorted(ALLOWED),
        "classification_counts": counts,
        "complete_external_surface": counts["FAIL_CLOSED_UNSUPPORTED"] == 0,
        "callbacks": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"classification_counts": counts, "complete": output["complete_external_surface"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
