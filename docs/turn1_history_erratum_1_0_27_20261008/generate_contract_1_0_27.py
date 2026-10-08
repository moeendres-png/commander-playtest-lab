"""Generate FULL107 successor contract 1.0.27 from 1.0.26: the turn-1 arrival
pre-checkpoint history erratum for WS05-MP-TURN-5, WS05-MP-BLOCK-4 and
MICRO_REPLACEMENT.

Coordinator ruling (Lab issue #626, 2026-10-08; refs #592), following the
1.0.26 precedent (``docs/turn1_history_erratum_1_0_26_20261008/``): the
midgame arrival path ``drive_to_precombat_main`` still kept opening hands and
passed priority without a record script for these three turn-1 rows. Those are
Lab choices made for players (CR 103.5 for the keep, CR 117 for the passes).

The ruling is that each record declares its whole turn-1 arrival history in
``decision_script`` and the Lab only transports it:

* pregame: one ``mulligan`` KEEP step per seat P1-P4 (the 6P / START-2 shape;
  CR 103.5);
* ``priority_pass_through``: actor ALL, scope from turn 1's beginning to the
  row's own declared checkpoint (CR 117.3d, 305.1). Every priority decision in
  scope is answered PASS, declaring that no player plays a land, casts or
  activates anything; any non-priority decision in scope that is not
  separately scripted fails closed.

No other decision is declared: these records' pre-checkpoint history needs no
attackers, discards or targets before their declared checkpoint. Every other
field is the 1.0.26 one byte for byte: the superseded patch is kept as lineage
(``superseded_successor_patch``). The obligation is unchanged key for key and
the 107-row denominator is untouched (``denominator_effect: NONE``). No runtime
credit is claimed.

Idempotent: always regenerated from the 1.0.26 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_26.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_27.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.26-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_27.json"
NEW_VERSION = "1.0.27"
NEW_MINOR = "27"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_TURN1_ARRIVAL_HISTORY_DECLARATIONS"
FIXTURES = ("WS05-MP-TURN-5", "WS05-MP-BLOCK-4", "MICRO_REPLACEMENT")
DECISIONS = (
    "#626 Coordinator ruling 2026-10-08 (contract 1.0.27): the three turn-1 "
    "arrival records declare their whole pre-checkpoint history explicitly in "
    "decision_script and the Lab only transports it -- one pregame keep per seat "
    "(CR 103.5) and a declared priority pass-through scope from turn 1's beginning "
    "to the row's own checkpoint (CR 117.3d/305.1); no Lab default, first-option or "
    "positional choice answers an engine frame"
)
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
    "NO_RUNTIME_CREDIT_CLAIMED_BY_THIS_MATERIALIZATION: the turn-1 arrival history is "
    "now declared (pregame keeps and the scoped priority pass-through) so the Lab "
    "transports each frame instead of answering it with a default. The row still "
    "requires exact-head runtime requalification after the Lab transport follows these "
    "declarations; this erratum only removes the Lab-chosen answers the #625 review "
    "reproduced"
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": (
        "fixture-contract successor rule: #626 turn-1 arrival pre-checkpoint history "
        "declarations erratum"
    ),
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_OBLIGATION_KEYS_UNTOUCHED",
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
assert contract["contract_id"] == PRIOR_CONTRACT
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert len(denominator) == 107
for fixture_id in FIXTURES:
    assert fixture_id in denominator
    assert fixture_id in existing


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


def priority_step(fixture_id: str, temporal: dict) -> dict:
    until = {
        "turn": temporal["turn_number"],
        "phase": str(temporal["phase"]).strip().lower(),
        "step": str(temporal["step"]).strip().lower(),
    }
    return {
        "actor": "ALL",
        "causal_step_id": f"priority-pass-r1-to-{fixture_id.lower()}-checkpoint",
        "decision_family": "priority_pass_through",
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": (
            f"CR 117.3d, 305.1: from turn 1's beginning to {fixture_id}'s declared "
            "checkpoint no player plays a land, casts or activates anything, so every "
            "priority decision in that scope is the record's declared pass-through and "
            "the Lab answers it PASS. A non-priority decision in scope that is not "
            "separately scripted fails closed; the record never lets the Lab answer for "
            "a player. The selector is the arrival transport's own semantic "
            "pass-priority shape (midgame_rows/probe) and the scope key carries the "
            "ruled temporal window"
        ),
        # The scope the transport's ``_scripted_priority_pass_through`` authorizes:
        # this is the step's declared temporal window, not a second selection shape.
        "scope": {
            "from": {"turn": 1, "phase": "beginning"},
            "until": until,
        },
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": "pass_priority",
        },
    }


patches: dict[str, dict] = {}
for fixture_id in FIXTURES:
    prior = existing[fixture_id]
    prior_record = resolver.effective_record(fixture_id)
    prior_replace = copy.deepcopy(prior["replace"])
    prior_script = prior_replace.get("decision_script") or []
    assert isinstance(prior_script, list)
    # The 1.0.27 declarations are prepended; the record's own existing steps stay
    # byte for byte and in order.
    temporal = {
        **copy.deepcopy(base[fixture_id].get("temporal_state") or {}),
        **copy.deepcopy(prior_replace.get("temporal_state") or {}),
    }
    assert isinstance(temporal.get("turn_number"), int), fixture_id
    new_script = [
        *(mulligan_step(seat) for seat in ("P1", "P2", "P3", "P4")),
        priority_step(fixture_id, temporal),
        *copy.deepcopy(prior_script),
    ]
    merged_replace = {**prior_replace, "decision_script": new_script}
    record = copy.deepcopy(base[fixture_id])
    for key, value in merged_replace.items():
        record[key] = copy.deepcopy(value)
    record["knowledge_state"]["channel_policy"] = prior["knowledge_state_channel_policy"]

    # The obligation is the base one, key for key: nothing it projects is touched.
    assert resolver.obligation_digest(record) == resolver.obligation_digest(base[fixture_id])
    assert resolver.obligation_digest(record) == base[fixture_id]["obligation_digest"]
    for untouched in ("expected_events", "terminal_postconditions", "negative_fallback_probe"):
        assert record.get(untouched) == base[fixture_id].get(untouched), untouched
    for untouched in ("temporal_state", "stack_state", "deck_state"):
        assert record.get(untouched) == prior_record.get(untouched), untouched

    field_changes = [
        {
            "change": "decision_script +4 pregame mulligan keep steps (P1-P4)",
            "comprehensive_rules": "103.5",
            "reason": (
                "the pregame keep is each seat's own choice (CR 103.5). The 1.0.26 "
                "record declared no mulligan step, so the turn-1 arrival answered the "
                "engine's keep with a Lab default. The record now scripts one keep per "
                "seat in the 6P / START-2 shape; an unscripted mulligan frame fails "
                "closed"
            ),
        },
        {
            "change": (
                "decision_script +1 priority_pass_through scope (actor ALL) from "
                "turn 1's beginning to the declared checkpoint"
            ),
            "comprehensive_rules": "117.3d, 305.1",
            "reason": (
                "from turn 1's beginning to the record's own checkpoint no player "
                "plays a land, casts or activates anything, so every priority decision "
                "in scope is the record's declared PASS. The 1.0.26 arrival passed "
                "priority by Lab default; now only the declared scope authorizes it and "
                "a frame outside it fails closed"
            ),
        },
    ]
    erratum = {
        "actor": None,
        "details": {
            "authority": DECISIONS,
            "comprehensive_rules": "103.5, 117.3d, 305.1",
            "erratum_class": CORRECTION_CLASS,
            "field_changes": copy.deepcopy(field_changes),
            "obligation_changed": False,
            "provider_semantics_used": False,
            "reason": (
                "the #625 review found the row's turn-1 arrival depended on Lab answers "
                "for players: pregame keeps were answered with a default and priority "
                "was passed without a record script. The record now declares its whole "
                "turn-1 pre-checkpoint history in decision_script -- four pregame keeps "
                "(CR 103.5) and the scoped priority pass-through (CR 117.3d/305.1) -- so "
                "the Lab only transports what the record declares. No other decision is "
                "needed before the declared checkpoint. Obligation keys are untouched, "
                "the denominator is untouched and no runtime credit is claimed"
            ),
            "supersedes_erratum_step": prior["append_native_procedure"][-1]["step_id"],
        },
        "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
        "source_object": None,
        "step_id": f"erratum-turn1-arrival-history-{fixture_id.lower()}",
    }
    patch = {
        **copy.deepcopy(prior),
        "append_native_procedure": [
            *copy.deepcopy(prior["append_native_procedure"]),
            erratum,
        ],
        "authority_overlay": dict(OVERLAY),
        "correction_class": CORRECTION_CLASS,
        "digest_migration": {
            **DIGEST_MIGRATION,
            "reason": (
                "the declared decision script changes; the requested state and the "
                "obligation keys are byte for byte the predecessor's, so both digests are "
                "unchanged and the historical materialization digest is preserved under "
                "historical_digests"
            ),
        },
        "predecessor_invalidity": {
            "predecessor_values": {
                "decision_script": copy.deepcopy(prior_script),
            },
            "reason": (
                "the 1.0.26 record left the turn-1 arrival history undeclared: no "
                "pregame mulligan step and no priority pass-through scope, so the "
                "arrival answered those frames with Lab defaults (#625 review)"
            ),
        },
        "replace": merged_replace,
        "successor_requested_state_digest": resolver.requested_state_digest(record),
        "superseded_successor_patch": {
            "contract": PRIOR_CONTRACT,
            "correction_class": prior["correction_class"],
            "patch_sha256": hashlib.sha256(
                resolver.canonical_json(prior).encode("utf-8")
            ).hexdigest(),
            "successor_requested_state_digest": prior["successor_requested_state_digest"],
            "append_native_procedure": copy.deepcopy(prior["append_native_procedure"]),
            "lineage": (
                "its replace is kept and extended; its erratum steps are preserved here "
                "as history and are not active procedure"
            ),
        },
    }
    assert resolver.requested_state_digest(record) == patch["successor_requested_state_digest"]
    # The requested state is untouched: this is a decision-script-only erratum.
    assert prior["successor_requested_state_digest"] == patch["successor_requested_state_digest"]
    patches[fixture_id] = patch

# --- assemble the 1.0.27 contract --------------------------------------------- #

replaced = [patches.get(p["fixture_id"], p) for p in contract["record_successors"]]
assert [p["fixture_id"] for p in replaced] == [
    p["fixture_id"] for p in contract["record_successors"]
]
contract["record_successors"] = replaced
accounting = contract["change_accounting"]
for fixture_id in FIXTURES:
    assert fixture_id in accounting["changed_fixture_ids"]
    accounting["per_fixture_correction_class"][fixture_id] = CORRECTION_CLASS
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
accounting["unchanged_provider_denominator_rows"] = sum(
    1 for fixture_id in denominator if fixture_id not in accounting["changed_fixture_ids"]
)
contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.27 carries "
    "every 1.0.26 record successor and the bounded-secondary PLAYER_COUNT_6P section "
    "byte for byte, and supersedes in place exactly three records: WS05-MP-TURN-5, "
    "WS05-MP-BLOCK-4 and MICRO_REPLACEMENT now declare their whole turn-1 "
    "pre-checkpoint arrival history (four pregame mulligan keeps and the scoped "
    "priority pass-through), so the Lab transports each frame instead of answering it "
    "with a default. The obligation keys and the 107-row denominator are untouched and "
    "no runtime credit is claimed. Per #626 Coordinator ruling 2026-10-08."
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_26.json",
    "record_count": len(contract["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.26 overlay to the same 1.0.5 historical base, supersedes in place exactly "
        "three turn-1 arrival records (WS05-MP-TURN-5, WS05-MP-BLOCK-4, "
        "MICRO_REPLACEMENT) and keeps each 1.0.26 patch (or its lineage) as history, "
        "with the obligation keys unchanged"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.27 ------------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_26_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.26", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.26", NEW_VERSION)
# The 1.0.27 declarations reuse the 1.0.26 declared shapes exactly: the mulligan
# keep step, the ALL-actor priority pass-through with its scope, and the same
# fail-closed selections. No new record shape is introduced.
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
for fixture_id in FIXTURES:
    assert fixture_id in full["changed_fixture_ids"]
    full["evidence_survival"][fixture_id] = "REQUALIFICATION_REQUIRED_" + CORRECTION_CLASS
full["unchanged_fixture_count"] = sum(
    1 for fixture_id in denominator if fixture_id not in full["changed_fixture_ids"]
)
assert len(full["changed_fixture_ids"]) == len(set(full["changed_fixture_ids"]))
assert full["denominator_count"] == 107
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- errata ledger entries ----------------------------------------------------- #

lpath = REPO / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
ledger = json.loads(lpath.read_text(encoding="utf-8"))
ledger["records"] = [r for r in ledger["records"] if r["fixture_id"] not in FIXTURES]
new_entries = []
for fixture_id in FIXTURES:
    patch = patches[fixture_id]
    new_entries.append(
        dict(
            sorted(
                {
                    "correction_class": CORRECTION_CLASS,
                    "denominator_effect": "NONE",
                    "effective_obligation_digest": base[fixture_id]["obligation_digest"],
                    "effective_requested_state_digest": patch["successor_requested_state_digest"],
                    "evidence_survival": "REQUALIFICATION_REQUIRED",
                    "field_changes": copy.deepcopy(
                        patch["append_native_procedure"][-1]["details"]["field_changes"]
                    ),
                    "fixture_id": fixture_id,
                    "known_runtime_blocker": KNOWN_RUNTIME_BLOCKER,
                    "notes": (
                        "#625 review: the turn-1 arrival kept hands and passed priority "
                        "without a record script. The record now declares its whole "
                        "turn-1 pre-checkpoint history in decision_script (four pregame "
                        "keeps, CR 103.5; a priority pass-through scope from turn 1's "
                        "beginning to the row's checkpoint, CR 117.3d/305.1) and the Lab "
                        "transports each frame; unscripted frames fail closed. The "
                        "obligation digest is unchanged, the 107-row denominator is "
                        "untouched and no runtime credit is claimed"
                    ),
                    "predecessor_requested_state_digest": existing[fixture_id][
                        "successor_requested_state_digest"
                    ],
                    "successor_contract": SUCCESSOR_PATH,
                }.items()
            )
        )
    )
ledger["records"] = [*ledger["records"], *new_entries]
lpath.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

print("wrote", dst.name, "predecessor sha256", contract["predecessor"]["sha256"])
for fixture_id in FIXTURES:
    print(
        fixture_id,
        patches[fixture_id]["successor_requested_state_digest"],
        base[fixture_id]["obligation_digest"],
    )
