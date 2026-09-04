#!/usr/bin/env python3
"""WS-41 fail-closed semantic linter for successor materialization v1.0.3."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import ws32_lint_semantic_v1_0_2 as base

VERSION = "commander-lab.semantic-fixture-materialization/1.0.3"
REPORT_VERSION = "commander-lab.semantic-executability-report/1.0.3"
DIGEST_SPEC = base.DIGEST_SPEC
STATE_KEYS = base.STATE_KEYS
OBLIGATION_KEYS = base.OBLIGATION_KEYS
CAST_TIME_FAMILIES = {"target", "choose_mode", "announce_x", "mana_payment", "multi_amount", "target_amount"}

# Current-authority classification for every card identity that occurs as a
# completed spell in the frozen 135-record v1.0.2 corpus. New identities must
# be classified explicitly before a future completed-stack record can pass.
STACK_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "Raven's Crime": {"targets": 1, "modes": 0, "authority": ["ORACLE:Ravens Crime"]},
    "Utopia Sprawl": {"targets": 1, "modes": 0, "aura": True, "authority": ["CR303.4a", "CR115.1b", "CR601.2c", "ORACLE:Enchant Forest"]},
    "Fact or Fiction": {"targets": 0, "modes": 0, "authority": ["CURRENT_ORACLE:An opponent separates (not target opponent)"]},
    "Lightning Bolt": {"targets": 1, "modes": 0, "authority": ["ORACLE:target"]},
    "Unsummon": {"targets": 1, "modes": 0, "authority": ["ORACLE:target"]},
    "Opt": {"targets": 0, "modes": 0, "authority": ["ORACLE:no targets"]},
    "Syphon Mind": {"targets": 0, "modes": 0, "authority": ["ORACLE:no targets"]},
    "Flare of Duplication": {"targets": 1, "modes": 0, "authority": ["ORACLE:target instant or sorcery spell"]},
    "Stitch in Time": {"targets": 0, "modes": 0, "authority": ["ORACLE:no targets"]},
    "Divination": {"targets": 0, "modes": 0, "authority": ["ORACLE:no targets"]},
    "Rograkh, Son of Rohgahh": {"targets": 0, "modes": 0, "authority": ["ORACLE:no targets"]},
    "Doom Blade": {"targets": 1, "modes": 0, "authority": ["ORACLE:target"]},
    "Swords to Plowshares": {"targets": 1, "modes": 0, "authority": ["ORACLE:target"]},
    "Bant Charm": {"targets": 1, "modes": 1, "authority": ["ORACLE:choose one; selected mode targets"]},
    # Additional known targeted identities covered by predecessor validation;
    # including them makes future recurrence fail on cardinality rather than on
    # an unclassified card when they move into a completed stack state.
    "Wash Away": {"targets": 1, "modes": 0, "authority": ["ORACLE:target spell"]},
    "Bolt Bend": {"targets": 1, "modes": 0, "authority": ["ORACLE:target spell or ability"]},
    "Makeshift Mannequin": {"targets": 1, "modes": 0, "authority": ["ORACLE:target creature card"]},
}
X_ANNOUNCEMENT_REQUIRED = {"Finale of Revelation"}


def canonical_bytes(value: Any) -> bytes:
    return base.canonical_bytes(value)


def requested_state_digest(record: dict[str, Any]) -> str:
    return base.requested_state_digest(record)


def obligation_digest(record: dict[str, Any]) -> str:
    return base.obligation_digest(record)


def obligation_projection(record: dict[str, Any]) -> dict[str, Any]:
    return base.obligation_projection(record)


def _objects(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {o["semantic_id"]: o for o in record.get("semantic_objects", [])}


def _procedures(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s.get("step_id"): s for s in record.get("native_procedure", []) if s.get("step_id")}


def _completed_stack(record: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    objs = _objects(record)
    result = []
    for row in record.get("stack_state", []):
        sid = row.get("source_semantic_id")
        obj = objs.get(sid)
        if obj and row.get("cast_complete") is True:
            result.append((obj, row))
    return result


def _cast_source_by_cause(record: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for dec in record.get("decision_script", []):
        if dec.get("decision_family") != "priority":
            continue
        value = dec.get("selection", {}).get("semantic_value")
        if not isinstance(value, dict):
            continue
        action = str(value.get("action", ""))
        sid = value.get("object")
        cause = dec.get("causal_step_id")
        if sid and cause and (action.startswith("cast") or action == "announce_cast"):
            result[cause] = sid
    return result


def _cast_action_semantically_complete(record: dict[str, Any], value: Any) -> bool:
    """Return True only when a scripted cast action already fixes its cast-time choices.

    This distinguishes a later rules-procedure target choice (for example, a
    new target for a Flare copy or Bolt Bend retarget) from an illegally
    deferred cast-time target. Unknown card identities fail closed.
    """
    if not isinstance(value, dict):
        return False
    action = str(value.get("action", ""))
    if not (action.startswith("cast") or action == "announce_cast"):
        return False
    sid = value.get("object")
    obj = _objects(record).get(sid)
    if not obj:
        return False
    card = str(obj.get("card_identity"))
    req = STACK_REQUIREMENTS.get(card)
    if req is None:
        return False
    if req.get("targets", 0) > 0:
        target_keys = ("target", "target_spell", "targets", "target_object", "target_player")
        if not any(k in value and value.get(k) not in (None, [], "") for k in target_keys):
            return False
    if req.get("modes", 0) > 0:
        mode_value = value.get("modes", value.get("mode"))
        if mode_value in (None, [], ""):
            return False
    if card in X_ANNOUNCEMENT_REQUIRED and value.get("announced_x", value.get("x")) is None:
        return False
    if action == "cast_alt_cost":
        alt_keys = ("sacrifice", "alternative_cost", "alt_cost_choice", "cost_choice")
        if not any(k in value and value.get(k) not in (None, [], "") for k in alt_keys):
            return False
    return True


def _has_prior_complete_cast(record: dict[str, Any], decision_index: int) -> bool:
    for prior in record.get("decision_script", [])[:decision_index]:
        if prior.get("decision_family") != "priority":
            continue
        value = prior.get("selection", {}).get("semantic_value")
        if _cast_action_semantically_complete(record, value):
            return True
    return False


def _ws32_core_errors(record: dict[str, Any], predecessor: dict[str, Any] | None) -> list[dict[str, Any]]:
    # Reuse all predecessor hardening while intentionally shimming only the
    # version discriminator. Requested-state and obligation projections exclude
    # that discriminator, so this cannot hide state or obligation drift.
    shim = copy.deepcopy(record)
    shim["materialization_version"] = base.VERSION
    pred = copy.deepcopy(predecessor) if predecessor else None
    errors = base.lint_record(shim, pred)
    return [{"code": e["code"], "reason": e["message"], "authority": ["WS32_V1_0_2_HARD_GATE"]} for e in errors]


def lint_record(record: dict[str, Any], predecessor: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    fid = record.get("fixture_id", "<missing>")
    errors: list[dict[str, Any]] = _ws32_core_errors(record, predecessor)

    def err(code: str, reason: str, *, sid: str | None = None, card: str | None = None, authority: list[str] | None = None) -> None:
        errors.append({
            "code": code,
            "fixture_id": fid,
            "semantic_object_id": sid,
            "card_identity": card,
            "reason": reason,
            "authority": authority or [],
        })

    if record.get("materialization_version") != VERSION:
        err("VERSION", f"materialization_version must be {VERSION}")

    procedures = _procedures(record)
    cast_sources = _cast_source_by_cause(record)
    completed_sids = {row.get("source_semantic_id") for row in record.get("stack_state", []) if row.get("cast_complete") is True}

    for obj, row in _completed_stack(record):
        sid = obj["semantic_id"]
        card = obj.get("card_identity")
        req = STACK_REQUIREMENTS.get(str(card))
        if req is None:
            err("UNCLASSIFIED_COMPLETED_STACK_CARD", "Completed stack card has no current-authority cast-completion classification; fail closed until classified.", sid=sid, card=card, authority=["FAIL_CLOSED_AUTHORITY_CLASSIFICATION"])
            continue
        targets = row.get("targets")
        modes = row.get("modes")
        if not isinstance(targets, list):
            err("FULLY_CAST_TARGET_GROUPS_COMPLETE", "Completed spell must serialize complete target groups as a list.", sid=sid, card=card, authority=req["authority"])
        elif len(targets) != req["targets"]:
            code = "AURA_TARGET_CARDINALITY" if req.get("aura") else "TARGET_CARDINALITY"
            err(code, f"Completed {card} requires exactly {req['targets']} target(s); serialized target count is {len(targets)}.", sid=sid, card=card, authority=req["authority"])
            if req["targets"] > 0 and not targets:
                err("TARGET_REQUIRED_STACK_NONEMPTY", "A target-required completed spell cannot have empty target state.", sid=sid, card=card, authority=req["authority"])
        if not isinstance(modes, list):
            err("MODAL_CAST_COMPLETE_MODE_STATE", "Completed spell must serialize mode state as a list.", sid=sid, card=card, authority=req["authority"])
        elif len(modes) != req["modes"]:
            err("MODAL_CAST_COMPLETE_MODE_STATE", f"Completed {card} requires exactly {req['modes']} selected mode(s); serialized count is {len(modes)}.", sid=sid, card=card, authority=req["authority"])
        if card in X_ANNOUNCEMENT_REQUIRED and "announced_x" not in row:
            err("X_ANNOUNCEMENT_CAST_COMPLETE", "Completed X spell lacks announced_x.", sid=sid, card=card, authority=["CR601.2b", "CR601.2c"])
        if row.get("costs_paid") is not True:
            err("ADDITIONAL_ALTERNATIVE_COST_COMPLETION", "Completed stack spell must serialize costs_paid=true; cost-dependent choices must be fixed before completion.", sid=sid, card=card, authority=["CR601.2b", "CR601.2f", "CR601.2h"])

    for i, dec in enumerate(record.get("decision_script", [])):
        family = dec.get("decision_family")
        cause = dec.get("causal_step_id")
        if family in CAST_TIME_FAMILIES and cause not in cast_sources:
            step = procedures.get(cause, {})
            op = str(step.get("operation", ""))
            # A cast-time decision may still be legal when the native procedure
            # explicitly begins/continues a cast rather than using a preceding
            # priority selection.
            if any(token in op for token in ("BEGIN_CAST", "CONTINUE_CAST", "CAST_TO_", "BEGIN_OR_CONTINUE_CAST")):
                continue
            # "target" is also used by the frozen contract for later
            # rules-generated targeting decisions. Accept that shape only when
            # a prior cast action has already fixed every authority-classified
            # cast-time choice for the spell, and the current causal step is the
            # provider-neutral rules-procedure target-decision boundary. This
            # is the exact CARD_13 (Flare copy new target) / CARD_22 (Bolt Bend
            # retarget) shape proven by WS41 causality diagnostics; it does not
            # permit a missing cast target to be deferred.
            if (
                family == "target"
                and "RULES_PROCEDURE_TO_TARGET_DECISION" in op
                and _has_prior_complete_cast(record, i)
            ):
                continue
            if completed_sids:
                err("NO_CAST_TIME_DECISION_AFTER_CAST_COMPLETE", f"Decision {i} ({family}) is not tied to a native in-progress cast and is not a proven later rules-procedure choice; cast-time choices cannot be deferred.", authority=["CR601.2b", "CR601.2c", "CR601.2h"])

    if fid == "PILOT_CHOICE":
        choices = [d for d in record.get("decision_script", []) if d.get("decision_family") == "choice"]
        if len(choices) != 1 or choices[0].get("selection", {}).get("semantic_value") != "RED":
            err("PILOT_CHOICE_OBLIGATION_SHAPE", "PILOT_CHOICE must preserve the sole external discretionary color choice RED.", authority=["FROZEN_OBLIGATION"])
        else:
            step = procedures.get(choices[0].get("causal_step_id"), {})
            op = str(step.get("operation", ""))
            if "UTOPIA_SPRAW" not in op or "COLOR_CHOICE" not in op:
                err("LATER_DECISION_RULE_CAUSALITY", "The later color choice must be generated by Utopia Sprawl's distinct as-enters instruction, not by a delayed casting target choice.", sid="obj:utopia", card="Utopia Sprawl", authority=["ORACLE:As Utopia Sprawl enters choose a color"])

    if predecessor is not None and obligation_projection(record) != obligation_projection(predecessor):
        err("OBLIGATION_DRIFT", "Frozen obligation projection changed from immutable v1.0.2.", authority=["WS32_IMMUTABLE_PROVENANCE"])
    return errors


def serialization_sensitivity(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Prove Rules-relevant stack choices are inside requested-state serialization."""
    problems = []
    original = requested_state_digest(record)
    for obj, row in _completed_stack(record):
        sid = obj["semantic_id"]
        for field, value in (("targets", ["__ws41_mutation_target__"]), ("modes", ["__ws41_mutation_mode__"])):
            mutated = copy.deepcopy(record)
            for candidate in mutated.get("stack_state", []):
                if candidate.get("source_semantic_id") == sid:
                    candidate[field] = value
                    break
            if requested_state_digest(mutated) == original:
                problems.append({"fixture_id": record["fixture_id"], "semantic_object_id": sid, "field": field, "reason": "Rules-relevant stack choice mutation did not change requested-state digest."})
        if "announced_x" in row:
            mutated = copy.deepcopy(record)
            for candidate in mutated.get("stack_state", []):
                if candidate.get("source_semantic_id") == sid:
                    candidate["announced_x"] = int(candidate["announced_x"]) + 1
                    break
            if requested_state_digest(mutated) == original:
                problems.append({"fixture_id": record["fixture_id"], "semantic_object_id": sid, "field": "announced_x", "reason": "X mutation did not change requested-state digest."})
    return problems


def lint_bundle(bundle: dict[str, Any], predecessor_bundle: dict[str, Any]) -> dict[str, Any]:
    records = bundle.get("records", [])
    predecessor_by_id = {r["fixture_id"]: r for r in predecessor_bundle.get("records", [])}
    rows = []
    sensitivity = []
    seen: set[str] = set()
    for record in records:
        fid = record.get("fixture_id", "<missing>")
        errs = lint_record(record, predecessor_by_id.get(fid))
        sensitivity.extend(serialization_sensitivity(record))
        rows.append({"fixture_id": fid, "status": "PASS" if not errs else "CONTRACT_DEFECT", "errors": errs})
        seen.add(fid)
    pred_ids = set(predecessor_by_id)
    global_errors = []
    if bundle.get("schema_version") != VERSION:
        global_errors.append({"code": "SCHEMA_VERSION", "reason": f"schema_version must be {VERSION}"})
    if len(records) != 135 or bundle.get("record_count") != 135:
        global_errors.append({"code": "COMPLETE_ACCOUNTING", "reason": f"expected 135 records; declared={bundle.get('record_count')} actual={len(records)}"})
    if len(seen) != len(records):
        global_errors.append({"code": "DUPLICATE_FIXTURE_ID", "reason": "fixture IDs are not unique"})
    if seen != pred_ids:
        global_errors.append({"code": "IMMUTABLE_ID_SET", "reason": "v1.0.3 fixture ID set differs from immutable v1.0.2"})
    if sensitivity:
        global_errors.append({"code": "REQUESTED_STATE_SERIALIZATION_SENSITIVITY", "reason": "Rules-relevant stack mutation failed digest sensitivity", "details": sensitivity})
    passed = sum(r["status"] == "PASS" for r in rows)
    return {
        "report_version": REPORT_VERSION,
        "materialization_version": VERSION,
        "record_count": len(rows),
        "semantic_executable_count": passed,
        "contract_defect_count": len(rows) - passed,
        "serialization_sensitivity_check_count": sum(2 + int("announced_x" in s) for r in records for _, s in _completed_stack(r)),
        "serialization_sensitivity_failures": sensitivity,
        "global_errors": global_errors,
        "records": rows,
        "terminal_status": "PASS" if passed == 135 and not global_errors else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("materialization", type=Path)
    ap.add_argument("--predecessor", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    bundle = json.loads(args.materialization.read_text(encoding="utf-8"))
    predecessor = json.loads(args.predecessor.read_text(encoding="utf-8"))
    report = lint_bundle(bundle, predecessor)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["terminal_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
