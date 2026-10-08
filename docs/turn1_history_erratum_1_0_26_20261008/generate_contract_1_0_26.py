"""Generate FULL107 successor contract 1.0.26 from 1.0.25: the NEGATIVE_PARENT_CLASS_FALLBACK pre-checkpoint history erratum.

Coordinator ruling (Lab issue #592, 2026-10-08; parent #255), following the
PR #583 / #604 / #608 / #611 precedent (deterministic generator, contract +
schema, authority pointer, errata-ledger entry, manifests via the repository
tool).

The independent review of PR #616 found the row's local PASS depended on Lab
choices for players: the probe held every attacker on pre-checkpoint turns and
answered pregame keeps with a default, neither of which the 1.0.25 record
declares. The Coordinator ruling is that the record declares its whole
pre-checkpoint history explicitly in ``decision_script`` and the Lab only
transports it:

* pregame: one ``mulligan`` KEEP step per seat P1-P4 (the 6P / START-2 shape;
  CR 103.5);
* ``priority_pass_through``: actor ALL, scope from turn 1's beginning to the
  declared checkpoint (turn 2, precombat main): every priority decision in
  scope is answered PASS, declaring that no player plays a land, casts or
  activates anything (CR 117.3d, 305.1). Any non-priority decision in scope
  that is not separately scripted fails closed;
* ``declare_attackers``: actor P1, turn 1, selection the empty attack set
  (CR 508.1, 508.8);
* the existing ``cleanup_discard`` step gains ``phase: CLEANUP`` and
  ``turn: 1`` and its ``on_multiple_match`` becomes
  ``SAME_NAME_OUTCOME_EQUIVALENT_LEAST_ID`` (same-name copies in a hidden hand
  are outcome-equivalent; precedent #603) -- replacing FAIL_CLOSED for this
  step only;
* the declared graveyard Mountain gains
  ``produced_by_step: cleanup-r1-P1``: it is the engine's own discard zone
  change, never a Lab top-up.

The obligation is unchanged key for key. Every other field is the 1.0.25 one
byte for byte: the 1.0.25 patch is superseded in place and kept as lineage
(``superseded_successor_patch``). No runtime credit is claimed.

Idempotent: always regenerated from the 1.0.25 bytes.
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
sys.path.insert(0, str(REPO / "scripts"))
import resolve_pre_freeze_contract as resolver  # noqa: E402

PRE = REPO / "qualification/pre-freeze-successor"
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_25.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_26.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.25-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_26.json"
DECISIONS = (
    "#592 Coordinator ruling 2026-10-08 (contract 1.0.26): the record declares its "
    "whole pre-checkpoint history explicitly in decision_script and the Lab only "
    "transports it -- four pregame keeps (CR 103.5), a declared priority "
    "pass-through scope (CR 117.3d/305.1), a declared empty attack set (CR 508.1/"
    "508.8) and the turn-1 cleanup discard (CR 514.1) with its produced graveyard "
    "card; no Lab default, first-option or positional choice answers an engine frame"
)
FIXTURE = "NEGATIVE_PARENT_CLASS_FALLBACK"
PRIOR_CLASS = "FIXTURE_DEFECT_CORRECTION_TURN1_CLEANUP_DISCARD_REACHABILITY"
NEW_VERSION = "1.0.26"
NEW_MINOR = "26"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_PRE_CHECKPOINT_HISTORY_DECLARATIONS"
FORBIDDEN = [
    "first_option",
    "random_option",
    "default_yes_no",
    "internal_ai",
    "gui_default",
    "silent_skip",
    "parent_class_fallback",
]
KNOWN_RUNTIME_BLOCKER = (
    "NO_RUNTIME_CREDIT_CLAIMED_BY_THIS_MATERIALIZATION: the pre-checkpoint history is "
    "now declared (pregame keeps, priority pass-through scope, empty attack set, turn-1 "
    "cleanup discard with produced graveyard card) so the Lab transports each frame "
    "instead of answering it with a default. The row still requires exact-head runtime "
    "requalification after the Lab transport follows these declarations; this erratum "
    "only removes the Lab-chosen answers the #616 review reproduced"
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": (
        "fixture-contract successor rule: #592 NEGATIVE_PARENT_CLASS_FALLBACK "
        "pre-checkpoint history declarations erratum"
    ),
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_FROM_THE_1_0_25_SUCCESSOR_OBLIGATION_KEYS_UNTOUCHED",
    "predecessor_non_requested_digests": "HISTORICAL_PROVENANCE_ONLY",
    "successor_non_requested_digest_policy": (
        "REMOVE_STALE_VALUES_AND_PRESERVE_UNDER_historical_digests"
    ),
}

raw = src.read_bytes()
contract = json.loads(raw)
authority = json.loads((REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json").read_text())
base = {
    r["fixture_id"]: r
    for r in json.loads(
        (REPO / authority["full107"]["historical_base_materialization"]).read_text()
    )["records"]
}
existing = {p["fixture_id"]: p for p in contract["record_successors"]}
prior = existing[FIXTURE]
assert prior["correction_class"] == PRIOR_CLASS
assert contract["contract_id"] == PRIOR_CONTRACT

old = base[FIXTURE]
assert old["decision_script"] == []

# --- the 1.0.25 declared state, recomputed from its own patch ----------------- #

prior_replace = copy.deepcopy(prior["replace"])
prior_script = prior_replace["decision_script"]
assert [step["decision_family"] for step in prior_script] == ["starting_player", "cleanup_discard"]
starting_step = copy.deepcopy(prior_script[0])
cleanup_step = copy.deepcopy(prior_script[1])
assert cleanup_step["actor"] == "P1"
assert cleanup_step["selection"]["on_multiple_match"] == "FAIL_CLOSED"
prior_objects = prior_replace["semantic_objects"]
assert [o["semantic_id"] for o in prior_objects if o["zone"] == "graveyard"] == [
    "obj:neg-graveyard-mountain"
]
graveyard_mountain = copy.deepcopy(
    next(o for o in prior_objects if o["semantic_id"] == "obj:neg-graveyard-mountain")
)
assert "produced_by_step" not in graveyard_mountain
assert prior_replace["temporal_state"] == {
    "active_player": "P2",
    "extra_turn_queue": [],
    "phase": "precombat_main",
    "priority_player": "P2",
    "step": "main",
    "turn_number": 2,
}

# --- the 1.0.26 history declarations ------------------------------------------ #


def mulligan_step(seat: str) -> dict:
    return {
        "actor": seat,
        "causal_step_id": f"mull-r1-{seat}",
        "decision_family": "mulligan",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            f"CR 103.5: {seat} keeps its opening hand; which hand is kept is the "
            "player's own choice, declared here so the Lab only transports it and never "
            "defaults to a keep"
        ),
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": "keep_opening_hand",
        },
    }


priority_step = {
    "actor": "ALL",
    "causal_step_id": "priority-pass-r1-to-r2-checkpoint",
    "decision_family": "priority_pass_through",
    "forbidden_fallbacks": list(FORBIDDEN),
    "notes": (
        "CR 117.3d, 305.1: from turn 1's beginning to the turn-2 precombat-main "
        "checkpoint no player plays a land, casts or activates anything, so every "
        "priority decision in that scope is the record's declared pass-through and the "
        "Lab answers it PASS. A non-priority decision in scope that is not separately "
        "scripted fails closed; the record never lets the Lab answer for a player"
    ),
    "selection": {
        "matches_only_provider_offered_legal_options": True,
        "on_multiple_match": "FAIL_CLOSED",
        "on_zero_match": "FAIL_CLOSED",
        "selector_kind": "pass_priority",
        "semantic_value": {
            "scope": {
                "from": {"turn": 1, "phase": "beginning"},
                "until": {"turn": 2, "phase": "precombat_main", "step": "main"},
            }
        },
    },
}
declare_step = {
    "actor": "P1",
    "causal_step_id": "declare-attackers-r1-P1",
    "decision_family": "declare_attackers",
    "forbidden_fallbacks": list(FORBIDDEN),
    "notes": (
        "CR 508.1, 508.8: P1 is active on turn 1 and its declare-attackers step runs "
        "before the turn-2 checkpoint. The record declares the empty attack set: no "
        "creature attacks. Every offered attacker frame is answered 'do not attack' "
        "from this declaration; there is no default hold and an unscripted attacker "
        "frame fails closed"
    ),
    "phase": "COMBAT",
    "turn": 1,
    "selection": {
        "matches_only_provider_offered_legal_options": True,
        "on_multiple_match": "FAIL_CLOSED",
        "on_zero_match": "FAIL_CLOSED",
        "selector_kind": "attack_set",
        "semantic_value": [],
    },
}
cleanup_step["turn"] = 1
cleanup_step["phase"] = "CLEANUP"
cleanup_step["selection"]["on_multiple_match"] = "SAME_NAME_OUTCOME_EQUIVALENT_LEAST_ID"
cleanup_step["selection"]["semantic_value"] = {"Mountain": 1}
cleanup_step["notes"] = (
    "CR 514.1: P1 draws on turn 1 in this four-player game (CR 103.8c), so it holds "
    "eight cards when its cleanup step begins and must discard one down to seven; "
    "which Mountain is discarded is P1's own choice, so it is scripted here (turn 1, "
    "CLEANUP) and the Lab never picks. Same-name copies in the hidden hand are "
    "outcome-equivalent, so among them the least option id is taken (precedent #603)"
)
graveyard_mountain["produced_by_step"] = "cleanup-r1-P1"
corrected_objects = [
    graveyard_mountain if o["semantic_id"] == "obj:neg-graveyard-mountain" else o
    for o in prior_objects
]
corrected_scenario_notes = [
    *copy.deepcopy(prior_replace["scenario_notes"]),
    (
        "Pre-checkpoint history erratum (#592 Coordinator ruling 2026-10-08, contract "
        "1.0.26): the record now declares its whole pre-checkpoint history -- four "
        "pregame keeps (CR 103.5), a priority pass-through scope (CR 117.3d/305.1), the "
        "empty attack set of P1's turn-1 declare-attackers step (CR 508.1/508.8) and "
        "the turn-1 cleanup discard (CR 514.1) whose card is marked with its producing "
        "step. The Lab transports each frame from these declarations and answers "
        "nothing by default. The obligation is untouched and no runtime credit is "
        "claimed."
    ),
]
merged_replace = {
    **prior_replace,
    "decision_script": [
        starting_step,
        *(mulligan_step(seat) for seat in ("P1", "P2", "P3", "P4")),
        priority_step,
        declare_step,
        cleanup_step,
    ],
    "scenario_notes": corrected_scenario_notes,
    "semantic_objects": corrected_objects,
}
record = copy.deepcopy(old)
for key, value in merged_replace.items():
    record[key] = copy.deepcopy(value)
record["knowledge_state"]["channel_policy"] = prior["knowledge_state_channel_policy"]

# --- the corrected errata field changes --------------------------------------- #

prior_changes = copy.deepcopy(prior["append_native_procedure"][0]["details"]["field_changes"])
new_changes = [
    {
        "change": "decision_script +4 pregame mulligan keep steps (P1-P4)",
        "comprehensive_rules": "103.5",
        "reason": (
            "the pregame keep is each seat's own choice (CR 103.5). The 1.0.25 record "
            "declared no mulligan step, so the arrival answered the engine's keep with a "
            "Lab default. The record now scripts one keep per seat in the 6P / START-2 "
            "shape; an unscripted mulligan frame fails closed"
        ),
    },
    {
        "change": "decision_script +1 priority_pass_through scope (actor ALL)",
        "comprehensive_rules": "117.3d, 305.1",
        "reason": (
            "from turn 1's beginning to the turn-2 precombat-main checkpoint no player "
            "plays a land, casts or activates anything, so every priority decision in "
            "scope is the record's declared PASS. The 1.0.25 arrival passed priority by "
            "Lab default; now only the declared scope authorizes it and a frame outside "
            "it fails closed"
        ),
    },
    {
        "change": "decision_script +1 declare_attackers step for P1 on turn 1 (empty set)",
        "comprehensive_rules": "508.1, 508.8",
        "reason": (
            "P1 is active on turn 1 and reaches its declare-attackers step before the "
            "turn-2 checkpoint. The record declares the empty attack set (no creature "
            "attacks). The 1.0.25 arrival held every offered attacker as a Lab default; "
            "now only this declaration authorizes the hold and an unscripted attacker "
            "frame fails closed"
        ),
    },
    {
        "change": "cleanup_discard step declares phase CLEANUP, turn 1; on_multiple_match SAME_NAME_OUTCOME_EQUIVALENT_LEAST_ID",
        "comprehensive_rules": "514.1, 103.8c, 603.3",
        "reason": (
            "the scripted discard is the turn-1 CLEANUP one: the frame is matched by "
            "engine class and the declared phase/turn so a later cleanup discard cannot "
            "consume it. Among same-name copies in the hidden hand the least option id "
            "is content-independent and outcome-equivalent (precedent #603), so the "
            "step's on_multiple_match changes from FAIL_CLOSED to "
            "SAME_NAME_OUTCOME_EQUIVALENT_LEAST_ID for this step only"
        ),
    },
    {
        "change": "graveyard Mountain declares produced_by_step cleanup-r1-P1",
        "comprehensive_rules": "514.1",
        "reason": (
            "the declared graveyard Mountain is the result of the engine's own scripted "
            "turn-1 cleanup discard, not a state the Lab may top up: the native "
            "restoration must require the engine's own zone change and fail closed when "
            "it is missing, instead of injecting the identity"
        ),
    },
]
field_changes = [*prior_changes, *new_changes]

erratum = {
    "actor": None,
    "details": {
        "authority": DECISIONS,
        "comprehensive_rules": "103.5, 117.3d, 305.1, 508.1, 508.8, 514.1, 103.8c",
        "erratum_class": CORRECTION_CLASS,
        "field_changes": field_changes,
        "obligation_changed": False,
        "provider_semantics_used": False,
        "reason": (
            "the independent review of PR #616 found the row's local PASS depended on "
            "Lab answers for players: pre-checkpoint attacker frames were held by a Lab "
            "default and pregame keeps answered with a default. The record now declares "
            "its whole pre-checkpoint history in decision_script -- four pregame keeps "
            "(CR 103.5), the priority pass-through scope (CR 117.3d/305.1), P1's turn-1 "
            "empty attack set (CR 508.1/508.8) and the turn-1 cleanup discard with its "
            "produced graveyard card -- so the Lab only transports what the record "
            "declares. Obligation keys are untouched and no runtime credit is claimed"
        ),
        "supersedes_erratum_step": prior["append_native_procedure"][0]["step_id"],
    },
    "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
    "source_object": None,
    "step_id": "erratum-pre-checkpoint-history-negative_parent_class_fallback",
}
patch = {
    "append_native_procedure": [erratum],
    "authority_overlay": dict(OVERLAY),
    "correction_class": CORRECTION_CLASS,
    "digest_migration": {
        **DIGEST_MIGRATION,
        "reason": (
            "the declared decision script and the declared graveyard object change; the "
            "obligation keys are byte for byte the 1.0.25 predecessor's, so the "
            "obligation digest is unchanged and the historical materialization digest is "
            "preserved under historical_digests"
        ),
    },
    "evidence_survival": "REQUALIFICATION_REQUIRED",
    "fixture_id": FIXTURE,
    "knowledge_state_channel_policy": prior["knowledge_state_channel_policy"],
    "predecessor_invalidity": {
        "predecessor_values": {
            "decision_script": copy.deepcopy(prior_replace["decision_script"]),
            "semantic_objects": copy.deepcopy(prior_objects),
        },
        "reason": (
            "the 1.0.25 record left the pre-checkpoint history undeclared: no pregame "
            "mulligan step, no priority pass-through scope and no declare_attackers "
            "step, so the arrival answered those frames with Lab defaults (review of PR "
            "#616). The scripted cleanup discard also lacked its declared phase/turn and "
            "its produced graveyard card was injectable"
        ),
    },
    "predecessor_requested_state_digest": old["requested_state_digest"],
    "replace": merged_replace,
    "successor_requested_state_digest": resolver.requested_state_digest(record),
    "superseded_successor_patch": {
        "contract": PRIOR_CONTRACT,
        "correction_class": prior["correction_class"],
        "patch_sha256": hashlib.sha256(resolver.canonical_json(prior).encode("utf-8")).hexdigest(),
        "successor_requested_state_digest": prior["successor_requested_state_digest"],
        "append_native_procedure": copy.deepcopy(prior["append_native_procedure"]),
        "lineage": (
            "its replace is kept and extended; its erratum step is preserved here as "
            "history and is not active procedure"
        ),
    },
}
# The obligation is the base one, key for key: nothing it projects is touched.
assert resolver.obligation_digest(record) == resolver.obligation_digest(old)
assert resolver.obligation_digest(record) == old["obligation_digest"]
assert record["expected_events"] == old["expected_events"]
assert record["terminal_postconditions"] == old["terminal_postconditions"]
assert record["negative_fallback_probe"] == old["negative_fallback_probe"]
assert record["native_procedure"][:2] == old["native_procedure"]
assert record["temporal_state"] == prior_replace["temporal_state"]
assert record["stack_state"] == prior_replace["stack_state"]
assert record["deck_state"] == prior_replace["deck_state"]
assert patch["successor_requested_state_digest"] != old["requested_state_digest"]
assert patch["successor_requested_state_digest"] != prior["successor_requested_state_digest"]
assert resolver.requested_state_digest(record) == patch["successor_requested_state_digest"]
# The 107-row denominator is untouched by construction.
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert len(denominator) == 107
assert FIXTURE in denominator

# --- assemble the 1.0.26 contract --------------------------------------------- #

predecessor_successors = list(contract["record_successors"])
assert sum(p["fixture_id"] == FIXTURE for p in predecessor_successors) == 1
assert predecessor_successors[-1]["fixture_id"] == FIXTURE
contract["record_successors"] = [*predecessor_successors[:-1], patch]
accounting = contract["change_accounting"]
assert FIXTURE in accounting["changed_fixture_ids"]
assert accounting["per_fixture_correction_class"][FIXTURE] == PRIOR_CLASS
accounting["per_fixture_correction_class"][FIXTURE] = CORRECTION_CLASS
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
accounting["unchanged_provider_denominator_rows"] = sum(
    1 for fixture_id in denominator if fixture_id not in accounting["changed_fixture_ids"]
)
contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.26 carries "
    "every 1.0.25 record successor and the bounded-secondary PLAYER_COUNT_6P section "
    "byte for byte, and supersedes in place exactly one record: "
    "NEGATIVE_PARENT_CLASS_FALLBACK now declares its whole pre-checkpoint history "
    "(four pregame mulligan keeps, the priority pass-through scope, P1's turn-1 empty "
    "attack set and the turn-1 cleanup discard with its produced graveyard card), so "
    "the Lab transports each frame instead of answering it with a default. The "
    "obligation keys are untouched and no runtime credit is claimed. Per #592 "
    "Coordinator ruling 2026-10-08."
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_25.json",
    "record_count": len(predecessor_successors),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.25 overlay to the same 1.0.5 historical base, supersedes in place exactly "
        "one corrected record (NEGATIVE_PARENT_CLASS_FALLBACK) and keeps the 1.0.25 "
        "patch as lineage, with the obligation keys unchanged"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.26 ------------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_25_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.25", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.25", NEW_VERSION)
enum = schema["$defs"]["record"]["properties"]["materialization_version"]["enum"]
new_materialization = f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
if new_materialization not in enum:
    enum.append(new_materialization)
schema["properties"]["contract_id"]["const"] = f"commander-lab.full107/{NEW_VERSION}-successor"
schema["properties"]["schema_version"]["const"] = new_materialization
indent = 2 if schema_text.startswith('{\n  "') else 1
(PRE / f"SEMANTIC_FIXTURE_SCHEMA_v1_0_{NEW_MINOR}_SUCCESSOR.json").write_text(
    json.dumps(schema, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
)

# --- authority pointer --------------------------------------------------------- #

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = SUCCESSOR_PATH
full["effective_materialization_schema"] = (
    f"qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_{NEW_MINOR}_SUCCESSOR.json"
)
if FIXTURE not in full["changed_fixture_ids"]:
    full["changed_fixture_ids"] = [*full["changed_fixture_ids"], FIXTURE]
full["unchanged_fixture_count"] = sum(
    1 for fixture_id in denominator if fixture_id not in full["changed_fixture_ids"]
)
assert len(full["changed_fixture_ids"]) == len(set(full["changed_fixture_ids"]))
assert full["denominator_count"] == 107
full["evidence_survival"][FIXTURE] = "REQUALIFICATION_REQUIRED_" + CORRECTION_CLASS
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- errata ledger entry ------------------------------------------------------- #

lpath = REPO / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
ledger = json.loads(lpath.read_text(encoding="utf-8"))
ledger["records"] = [r for r in ledger["records"] if r["fixture_id"] != FIXTURE]
entry = {
    "correction_class": CORRECTION_CLASS,
    "denominator_effect": "NONE",
    "effective_obligation_digest": old["obligation_digest"],
    "effective_requested_state_digest": patch["successor_requested_state_digest"],
    "evidence_survival": "REQUALIFICATION_REQUIRED",
    "field_changes": copy.deepcopy(field_changes),
    "fixture_id": FIXTURE,
    "known_runtime_blocker": KNOWN_RUNTIME_BLOCKER,
    "notes": (
        "the review of PR #616 found the row's local PASS depended on Lab answers for "
        "players: the pre-checkpoint attacker default and the default pregame keep. The "
        "record now declares its whole pre-checkpoint history in decision_script "
        "(pregame keeps, priority pass-through scope, P1's turn-1 empty attack set, the "
        "turn-1 cleanup discard with its produced graveyard card) and the Lab transports "
        "each frame; unscripted frames fail closed. The obligation digest is unchanged; "
        "the requested-state digest is recomputed from the declared script and graveyard "
        "producing step. The 107-row denominator is untouched and no runtime credit is "
        "claimed"
    ),
    "predecessor_requested_state_digest": old["requested_state_digest"],
    "successor_contract": SUCCESSOR_PATH,
}
ledger["records"] = [
    *ledger["records"],
    dict(sorted(entry.items())),
]
lpath.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

print("wrote", dst.name, "predecessor sha256", contract["predecessor"]["sha256"])
print(FIXTURE, patch["successor_requested_state_digest"], old["obligation_digest"])
