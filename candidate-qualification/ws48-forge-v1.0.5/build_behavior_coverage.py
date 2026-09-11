#!/usr/bin/env python3
"""WS48 behavior callback coverage registry (CODE_DERIVED, grants no credit).

Maps every WS47 v1.0.5 denominator record's decision_script families/selectors
to the Forge PlayerController callback(s) that must fire during native
behavior continuation, and records the callback's implementation status in the
current WS48 provider composition (as built by ws48-v105-noecho-construction).

Statuses:
  EXTERNAL_LABELED   - external choice with stable semantic labels already
  EXTERNAL_GENERIC   - external choice but labels lack semantic identity
                       (WS48 overlay required for scripted matching)
  FAIL_CLOSED        - provider throws WS23_FAIL_CLOSED_UNSUPPORTED today
                       (WS48 overlay required for any continuation)
  AUTOMATIC_SINGLETON- engine-automatic for 0/1 options; multi-option
                       requires external ordering (WS48 overlay required)
  EXPECT_FAIL_CLOSED - negative probe; harness must not answer and the
                       session must terminate with a typed failure

Output is a planning registry only. It is not behavior evidence.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

WS47_SHA = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
WS47_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.5"
WS47_BUNDLE = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"

# (decision_family, selector_kind) -> (required Forge surface, status, note)
CALLBACK_MAP: dict[tuple[str, str], tuple[str, str, str]] = {
    ("mulligan", "semantic_action"): (
        "mulliganKeepHand/chooseStartingPlayer",
        "EXTERNAL_LABELED",
        "KEEP/MULLIGAN and PLAYER:seat-N labels already stable",
    ),
    ("priority", "semantic_action"): (
        "chooseSpellAbilityToPlay",
        "EXTERNAL_GENERIC",
        "labels are PASS/FORGE_LEGAL_ACTION; overlay must add host-card semantic identity",
    ),
    ("target", "semantic_player"): (
        "chooseTargetsFor/chooseTarget",
        "FAIL_CLOSED",
        "overlay must implement engine-first candidate enumeration with seat-pid labels",
    ),
    ("target", "semantic_object"): (
        "chooseTargetsFor/chooseTarget",
        "FAIL_CLOSED",
        "overlay must implement engine-first candidate enumeration with semantic-id labels",
    ),
    ("target", "semantic_objects"): (
        "chooseTargetsFor(multi)",
        "FAIL_CLOSED",
        "multi-target loop with DONE sentinel; overlay required",
    ),
    ("target", "semantic_stack_object"): (
        "chooseTarget(stack)",
        "FAIL_CLOSED",
        "stack-object targeting; overlay required",
    ),
    ("choose_object", "semantic_object"): (
        "chooseSingleEntityForEffect/chooseCardsForEffect",
        "FAIL_CLOSED",
        "overlay must project native options to semantic ids",
    ),
    ("target_amount", "amount_assignment"): (
        "chooseAmountDistribution",
        "EXTERNAL_GENERIC",
        "exists but recipient labels lack semantic identity; overlay must add pid/semantic-id",
    ),
    ("multi_amount", "amount_assignment"): (
        "chooseAmountDistribution",
        "EXTERNAL_GENERIC",
        "as target_amount",
    ),
    ("mana_payment", "mana_payment"): (
        "applyManaToCost/payManaCost",
        "FAIL_CLOSED",
        "overlay must implement engine-native mana loop with semantic source labels",
    ),
    ("mana_payment", "semantic_stack_object"): (
        "chooseManaFromPool",
        "EXTERNAL_GENERIC",
        "generic NATIVE_OPTION labels; overlay must add mana-identity labels",
    ),
    ("announce_x", "integer"): (
        "chooseNumber",
        "FAIL_CLOSED",
        "integer range is self-identifying; overlay required",
    ),
    ("choose_use", "boolean"): (
        "arrangeForScry/confirmAction/chooseBinary",
        "FAIL_CLOSED",
        "scry arrangement needs semantic pile labels; overlay required",
    ),
    ("choice", "semantic_choice_key"): (
        "chooseColor",
        "FAIL_CLOSED",
        "color options are self-identifying; overlay required",
    ),
    ("choice", "boolean"): (
        "chooseBinary/confirmAction",
        "EXTERNAL_GENERIC",
        "boolean labels exist but question context needed; overlay should add question text",
    ),
    ("pile", "partition"): (
        "chooseCardsPile",
        "FAIL_CLOSED",
        "overlay must project both piles by semantic ids",
    ),
    ("replacement_effect", "boolean"): (
        "chooseSingleReplacementEffect/confirmReplacementEffect",
        "EXTERNAL_GENERIC",
        "single-replacement external exists generically; boolean grounding needs question labels",
    ),
    ("trigger_order", "order"): (
        "orderSimultaneousSa/orderAndPlaySimultaneousSa",
        "AUTOMATIC_SINGLETON",
        "automatic only for 0/1 triggers; 2-trigger APNAP ordering needs external overlay",
    ),
    ("choose_mode", "semantic_mode_key"): (
        "chooseModeForAbility",
        "EXTERNAL_GENERIC",
        "NATIVE_OPTION labels; overlay must render native mode params for key grounding",
    ),
    ("choose_ability", "semantic_ability_key"): (
        "chooseSpellAbilitiesForEffect/getAbilityToPlay",
        "FAIL_CLOSED",
        "overlay must project host-card + ability identity",
    ),
    ("declare_attacker", "attacker_assignment"): (
        "declareAttackers",
        "FAIL_CLOSED",
        "overlay must enumerate CombatUtil.canAttack pairs with semantic labels",
    ),
    ("declare_blocker", "blocker_assignment"): (
        "declareBlockers",
        "FAIL_CLOSED",
        "overlay must enumerate CombatUtil.canBlock pairs with semantic labels",
    ),
}


def failing_probe_status(family: str, selector: str) -> tuple[str, str, str] | None:
    if selector == "fail_closed_probe":
        return (
            "N/A(external handler unavailable)",
            "EXPECT_FAIL_CLOSED",
            f"negative {family}: harness must not answer; typed UNSUPPORTED_DISCRETIONARY_DECISION required",
        )
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    raw = a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WS47_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    doc = json.loads(raw)
    if doc["schema_version"] != WS47_SCHEMA or doc["canonical_bundle_digest"] != WS47_BUNDLE:
        raise SystemExit("immutable WS47 identity mismatch")
    ids = list(json.loads(a.denominator.read_text())["fixture_ids"])
    if len(ids) != 107 or len(set(ids)) != 107:
        raise SystemExit("WS47 denominator is not exact 107")
    by = {r["fixture_id"]: r for r in doc["records"]}

    rows: list[dict[str, Any]] = []
    status_counts: collections.Counter[str] = collections.Counter()
    blocked_fixtures: list[str] = []
    for idx, fid in enumerate(ids, 1):
        r = by[fid]
        script = list(r.get("decision_script") or [])
        needs: list[dict[str, Any]] = []
        worst = "EXTERNAL_LABELED"
        rank = {"EXTERNAL_LABELED": 0, "EXTERNAL_GENERIC": 1,
                "AUTOMATIC_SINGLETON": 2, "FAIL_CLOSED": 3,
                "EXPECT_FAIL_CLOSED": -1}
        for d in script:
            fam = d["decision_family"]
            sel = d["selection"]["selector_kind"]
            mapped = failing_probe_status(fam, sel)
            if mapped is None:
                mapped = CALLBACK_MAP.get(
                    (fam, sel),
                    ("UNKNOWN", "FAIL_CLOSED",
                     f"unmapped family/selector {fam}/{sel}; fail closed pending mapping"),
                )
            surface, status, note = mapped
            needs.append({"decision_family": fam, "selector_kind": sel,
                          "actor": d.get("actor"), "causal_step_id": d.get("causal_step_id"),
                          "forge_surface": surface, "status": status, "note": note})
            if status != "EXPECT_FAIL_CLOSED":
                status_counts[status] += 1
                if rank[status] > rank[worst]:
                    worst = status
        if worst in ("FAIL_CLOSED", "AUTOMATIC_SINGLETON", "EXTERNAL_GENERIC"):
            blocked_fixtures.append(fid)
        rows.append({"index": idx, "fixture_id": fid,
                     "fixture_family": r["fixture_family"],
                     "execution_entry_mode": r["execution_entry_mode"],
                     "decision_count": len(script), "requirements": needs,
                     "blocking_status": worst,
                     "has_priority_script": bool(r.get("priority_script")),
                     "has_action_cost_state": bool(r.get("action_cost_state"))})

    overlay_v1_covers = sorted({
        "chooseSpellAbilityToPlay", "chooseTargetsFor", "chooseTarget",
        "chooseSingleEntityForEffect", "chooseCardsForEffect",
        "chooseAmountDistribution", "applyManaToCost", "payManaCost",
        "chooseNumber", "chooseColor", "chooseCardsPile",
        "chooseSingleReplacementEffect", "confirmReplacementEffect",
        "orderSimultaneousSa", "chooseModeForAbility", "declareAttackers",
        "declareBlockers", "arrangeForScry", "chooseBinary", "confirmAction",
        "chooseManaFromPool",
    })
    out = {
        "schema_version": "commander-lab.ws48-behavior-callback-coverage/1.0.0",
        "evidence_class": "CODE_DERIVED",
        "grants_behavior_credit": False,
        "ws47": {"schema": WS47_SCHEMA, "bundle_digest": WS47_BUNDLE,
                 "materialization_sha256": WS47_SHA},
        "denominator": 107,
        "requirement_status_counts": dict(sorted(status_counts.items())),
        "fixtures_needing_overlay_before_continuation": len(blocked_fixtures),
        "blocked_fixture_ids": blocked_fixtures,
        "ws48_overlay_v1_surface": overlay_v1_covers,
        "rows": rows,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
