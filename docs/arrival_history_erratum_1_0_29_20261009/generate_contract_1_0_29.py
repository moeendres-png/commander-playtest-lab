"""Generate FULL107 successor contract 1.0.29 from 1.0.28: the arrival-history
declarations erratum for every remaining arrival-using lane record.

PB-03 run 37860773242 on the #637 head (contract 1.0.28) gave XMage 80 PASS; the
remaining arrival-side failures are the 25 records other lanes execute through
the same strict arrival that 1.0.28 did not cover:

* the 20 knowledge-projection rows (``knowledge_projection.ROWS``:
  HIDDEN_01 .. HIDDEN_19 and HIDDEN_HONEYCARD_SENTINEL), executed by
  KNOWLEDGE_PROJECTION_EXECUTIONS, which failed closed at
  ``the record scripts no mulligan keep for P1``;
* the 5 midgame replay/RNG twin rows (``midgame_replay_twin.ROWS``:
  REPLAY_CLEAN_PROCESS, REPLAY_DECISION_TAPE, REPLAY_EVENT_TAPE,
  REPLAY_STATE_HASHES, RNG_RULES_TAPE), executed by
  MIDGAME_REPLAY_TWIN_EXECUTIONS, for the same reason.

The ruling (Lab issues #634 / #592, following the 1.0.26 / 1.0.27 / 1.0.28
precedents) is that EVERY record any arrival-using lane executes declares its
game-start arrival history in ``decision_script`` and the Lab only transports
it, in exactly the 1.0.28 step shapes:

* pregame: one ``mulligan`` KEEP step per seat present in the record (CR 103.5;
  the record's constructed hands are placed at the checkpoint, so the keep is a
  declaration, not a Lab choice);
* ``priority_pass_through``: actor ALL, scope from turn 1's beginning to the
  record's own declared arrival checkpoint, ``until`` exclusive (CR 117.3d).
  Every priority decision in scope is answered PASS, declaring that no player
  plays a land, casts or activates anything; any non-priority decision in scope
  that is not separately scripted fails closed.

Each record's seat set and checkpoint are derived mechanically from the record
itself (its ``players`` list and its own ``temporal_state``); no other decision
is invented. Every one of the 25 records has its checkpoint at turn 1
precombat main and its own script steps at or after that checkpoint, so all 25
are patchable. A record whose arrival would need any other pre-checkpoint
decision (attackers, discards, targets) or whose checkpoint cannot be derived
would not be patched and would be listed with its reason -- none remains.

The 1.0.29 diff against 1.0.28 is exactly: per record, ``decision_script``
arrival-history keeps/pass-through inserted before the record's own existing
steps (the 1.0.28 steps are carried byte for byte), the per-record 1.0.28 patch
preserved as lineage (``superseded_successor_patch``), the version/accounting
fields, the schema version, the authority pointer and the errata ledger.

The obligation keys are untouched key for key, the 107-row denominator is
untouched (``denominator_effect: NONE``) and no runtime credit is claimed.

Idempotent: always regenerated from the 1.0.28 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_28.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_29.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.28-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_29.json"
NEW_VERSION = "1.0.29"
NEW_MINOR = "29"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_ARRIVAL_HISTORY_DECLARATIONS"
# The arrival-using lane registry order for the records 1.0.28 did not cover:
# the 20 knowledge_projection.ROWS rows then the 5 midgame_replay_twin.ROWS
# rows. The coverage test enumerates the registries themselves and asserts this
# set is exactly the records they execute.
FIXTURES = (
    "HIDDEN_01",
    "HIDDEN_02",
    "HIDDEN_03",
    "HIDDEN_04",
    "HIDDEN_05",
    "HIDDEN_06",
    "HIDDEN_07",
    "HIDDEN_08",
    "HIDDEN_09",
    "HIDDEN_10",
    "HIDDEN_11",
    "HIDDEN_12",
    "HIDDEN_13",
    "HIDDEN_14",
    "HIDDEN_15",
    "HIDDEN_16",
    "HIDDEN_17",
    "HIDDEN_18",
    "HIDDEN_19",
    "HIDDEN_HONEYCARD_SENTINEL",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_STATE_HASHES",
    "RNG_RULES_TAPE",
)
DECISIONS = (
    "#634 / #592 Coordinator ruling 2026-10-09 (contract 1.0.29): every record "
    "an arrival-using qualification lane executes -- the midgame RowSpec "
    "registry, the knowledge-projection registry and the midgame replay-twin "
    "registry -- declares its game-start arrival history explicitly and the Lab "
    "only transports it: one pregame keep per seat present in the record "
    "(CR 103.5) and a declared priority pass-through scope from game start to "
    "the record's own checkpoint (CR 117.3d), until exclusive; no Lab default, "
    "first-option or positional choice answers an engine frame"
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
    "NO_RUNTIME_CREDIT_CLAIMED_BY_THIS_MATERIALIZATION: the game-start arrival history "
    "is now declared (pregame keeps per seat and the scoped priority pass-through) so "
    "the Lab transports each frame instead of answering it with a default. The row "
    "still requires exact-head runtime requalification after the Lab transport follows "
    "these declarations; this erratum only removes the Lab-chosen answers the #637 "
    "PB-03 run 37860773242 reproduced for the knowledge-projection and replay-twin lanes"
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": (
        "fixture-contract successor rule: #634 arrival-history declarations for "
        "every arrival-using lane registry (knowledge projection and replay twin)"
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
# The arrival transport's own checkpoint vocabulary (the probe's
# ``_ENGINE_STEP_BY_POINT``), reproduced so a record whose temporal point the
# transport cannot address is refused here instead of silently mis-scoped.
ENGINE_STEP_BY_POINT = {
    ("beginning", "upkeep"): "UPKEEP",
    ("beginning", "draw"): "DRAW",
    ("precombat_main", "main"): "PRECOMBAT_MAIN",
    ("combat", "declare_attackers"): "DECLARE_ATTACKERS",
    ("combat", "declare_blockers"): "DECLARE_BLOCKERS",
    ("combat", "combat_damage"): "COMBAT_DAMAGE",
    ("postcombat_main", "main"): "POSTCOMBAT_MAIN",
}
_TURN_STEP_ORDER = (
    "UNTAP",
    "UPKEEP",
    "DRAW",
    "PRECOMBAT_MAIN",
    "BEGIN_COMBAT",
    "DECLARE_ATTACKERS",
    "DECLARE_BLOCKERS",
    "FIRST_COMBAT_DAMAGE",
    "COMBAT_DAMAGE",
    "END_COMBAT",
    "POSTCOMBAT_MAIN",
    "END_TURN",
    "CLEANUP",
)
# The record's own pre-checkpoint transport steps; every other family is the
# caller's obligation and must not appear before the checkpoint.
_ARRIVAL_PREFIX_FAMILIES = ("mulligan", "priority_pass_through")

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
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert contract["contract_id"] == PRIOR_CONTRACT
assert len(denominator) == 107
assert len(FIXTURES) == len(set(FIXTURES))
for fixture_id in FIXTURES:
    assert fixture_id in denominator, fixture_id
    assert fixture_id in base, fixture_id


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
            f"CR 117.3d, 305.1: from game start to {fixture_id}'s declared checkpoint "
            "no player plays a land, casts or activates anything, so every priority "
            "decision in that scope is the record's declared pass-through and the Lab "
            "answers it PASS. A non-priority decision in scope that is not separately "
            "scripted fails closed; the record never lets the Lab answer for a player. "
            "The selector is the arrival transport's own semantic pass-priority shape "
            "(midgame_rows/probe) and the scope key carries the ruled temporal window"
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


def effective_like(fixture_id: str) -> dict:
    """The 1.0.28 effective record, rebuilt from the base and the 1.0.28 patch."""
    record = copy.deepcopy(base[fixture_id])
    prior = existing.get(fixture_id)
    if prior is not None:
        for key, value in prior["replace"].items():
            record[key] = copy.deepcopy(value)
        record["knowledge_state"]["channel_policy"] = prior["knowledge_state_channel_policy"]
    return record


def is_keep_step(step: object, seat: str) -> bool:
    return (
        isinstance(step, dict)
        and step.get("decision_family") == "mulligan"
        and step.get("actor") == seat
        and (step.get("selection") or {}).get("selector_kind") == "semantic_action"
        and (step.get("selection") or {}).get("semantic_value") == "keep_opening_hand"
    )


def step_position(step: dict) -> tuple[int, int] | None:
    """The (turn, engine step index) a scripted step declares, or None."""
    turn = step.get("turn")
    if not isinstance(turn, int) or isinstance(turn, bool):
        return None
    phase = str(step.get("phase") or "").strip().lower()
    step_token = str(step.get("step") or phase).strip().upper()
    if step_token not in _TURN_STEP_ORDER:
        return None
    return turn, _TURN_STEP_ORDER.index(step_token)


patches: dict[str, dict] = {}
keeps_added: dict[str, list[str]] = {}
pass_added: dict[str, bool] = {}
obligation_digests: dict[str, str] = {}
for fixture_id in FIXTURES:
    prior = existing.get(fixture_id)
    prior_replace = copy.deepcopy(prior["replace"]) if prior is not None else {}
    record = effective_like(fixture_id)
    # The record's own 1.0.28 script: the base record's script overlaid with
    # the prior patch's, so a record whose script comes from the base (not the
    # patch) keeps it. Never only the patch's own value.
    prior_script = copy.deepcopy(record.get("decision_script") or [])
    assert isinstance(prior_script, list), fixture_id

    # --- derive the seat set and the checkpoint from the record itself --------- #
    seats = [str(p["player_id"]) for p in record["players"]]
    assert seats == [f"P{index + 1}" for index in range(len(seats))], (fixture_id, seats)
    temporal = dict(record.get("temporal_state") or {})
    assert isinstance(temporal.get("turn_number"), int), fixture_id
    point = (
        str(temporal["phase"]).strip().lower(),
        str(temporal["step"]).strip().lower(),
    )
    if point not in ENGINE_STEP_BY_POINT:
        raise SystemExit(f"unpatchable: {fixture_id}: checkpoint {point} cannot be derived")
    checkpoint = step_position(
        {
            "turn": temporal["turn_number"],
            "phase": point[0],
            "step": ENGINE_STEP_BY_POINT[point],
        }
    )
    assert checkpoint is not None

    # --- the record's own leading arrival-history prefix ----------------------- #
    prefix_end = 0
    while prefix_end < len(prior_script) and (
        str(prior_script[prefix_end].get("decision_family")) in _ARRIVAL_PREFIX_FAMILIES
    ):
        prefix_end += 1
    prefix = prior_script[:prefix_end]
    tail = prior_script[prefix_end:]

    # A record whose arrival needs any other decision before its checkpoint is
    # not patchable by this erratum: the two declarations would not reach it.
    for step in tail:
        position = step_position(step)
        if position is not None and position < checkpoint:
            raise SystemExit(
                f"unpatchable: {fixture_id}: {step.get('decision_family')} at "
                f"turn {position[0]} precedes the checkpoint"
            )

    # --- the declared history: a keep per seat, then the scoped pass-through --- #
    new_keeps: list[dict] = []
    added_seats: list[str] = []
    for seat in seats:
        declared = next((step for step in prefix if is_keep_step(step, seat)), None)
        if declared is None:
            added_seats.append(seat)
            new_keeps.append(mulligan_step(seat))
        else:
            new_keeps.append(copy.deepcopy(declared))
    declared_pass = next(
        (
            step
            for step in prefix
            if isinstance(step, dict) and step.get("decision_family") == "priority_pass_through"
        ),
        None,
    )
    if declared_pass is None:
        new_pass = priority_step(fixture_id, temporal)
        pass_added[fixture_id] = True
    else:
        new_pass = copy.deepcopy(declared_pass)
        pass_added[fixture_id] = False
    keeps_added[fixture_id] = added_seats
    assert added_seats or pass_added[fixture_id], fixture_id

    new_script = [*new_keeps, new_pass, *copy.deepcopy(tail)]
    merged_replace = {**prior_replace, "decision_script": new_script}
    corrected = copy.deepcopy(base[fixture_id])
    if prior is not None:
        for key, value in prior["replace"].items():
            corrected[key] = copy.deepcopy(value)
    for key, value in merged_replace.items():
        corrected[key] = copy.deepcopy(value)
    corrected["knowledge_state"]["channel_policy"] = (
        prior["knowledge_state_channel_policy"]
        if prior is not None
        else base[fixture_id]["knowledge_state"]["channel_policy"]
    )

    # The obligation is the 1.0.28 one, key for key: nothing it projects is touched.
    assert resolver.obligation_digest(corrected) == resolver.obligation_digest(record)
    obligation_digests[fixture_id] = resolver.obligation_digest(corrected)
    for untouched in ("expected_events", "terminal_postconditions", "negative_fallback_probe"):
        assert corrected.get(untouched) == record.get(untouched), untouched
    assert resolver.obligation_digest(corrected) == resolver.obligation_digest(record)
    for untouched in ("temporal_state", "stack_state", "deck_state"):
        assert corrected.get(untouched) == record.get(untouched), untouched
    prior_digest = (
        prior["successor_requested_state_digest"]
        if prior is not None
        else base[fixture_id]["requested_state_digest"]
    )
    successor_digest = resolver.requested_state_digest(corrected)

    field_changes = []
    if added_seats:
        field_changes.append(
            {
                "change": (
                    f"decision_script +{len(added_seats)} pregame mulligan keep step(s) "
                    f"({', '.join(added_seats)})"
                ),
                "comprehensive_rules": "103.5",
                "reason": (
                    "the pregame keep is each seat's own choice (CR 103.5). The 1.0.28 "
                    "predecessor declared no keep for "
                    + ", ".join(added_seats)
                    + ", so the arrival answered the engine's keep with a Lab default "
                    "(#637 PB-03 run 37860773242, knowledge-projection / replay-twin "
                    "lanes). The record now scripts one keep per seat in the 6P / START-2 "
                    "shape; an unscripted mulligan frame fails closed. The record's "
                    "constructed hands are placed at the checkpoint, so this is a "
                    "declaration, not a Lab choice"
                ),
            }
        )
    if pass_added[fixture_id]:
        field_changes.append(
            {
                "change": (
                    "decision_script +1 priority_pass_through scope (actor ALL) from "
                    "turn 1's beginning to the declared checkpoint"
                ),
                "comprehensive_rules": "117.3d, 305.1",
                "reason": (
                    "from game start to the record's own checkpoint no player plays a "
                    "land, casts or activates anything, so every priority decision in "
                    "scope is the record's declared PASS. The predecessor arrival passed "
                    "priority by Lab default (#637 PB-03 run 37860773242, "
                    "knowledge-projection / replay-twin lanes); now only the declared "
                    "scope authorizes it and a frame outside it fails closed"
                ),
            }
        )
    erratum = {
        "actor": None,
        "details": {
            "authority": DECISIONS,
            "comprehensive_rules": "103.5, 117.3d",
            "erratum_class": CORRECTION_CLASS,
            "field_changes": copy.deepcopy(field_changes),
            "obligation_changed": False,
            "provider_semantics_used": False,
            "reason": (
                "PB-03 run 37860773242 found the knowledge-projection and replay-twin "
                "arrivals depended on Lab answers for players: pregame keeps were "
                "answered with a default and priority was passed without a record "
                "script. This record now declares its "
                "game-start arrival history in decision_script -- "
                + (f"keeps for {', '.join(added_seats)}" if added_seats else "no missing keep")
                + (", " if added_seats and pass_added[fixture_id] else "")
                + (
                    "the scoped priority pass-through to its own checkpoint"
                    if pass_added[fixture_id]
                    else "the pass-through is carried"
                )
                + " -- so the Lab only transports what the record declares. No other "
                "decision is needed before the declared checkpoint. Obligation keys are "
                "untouched, the denominator is untouched and no runtime credit is claimed"
            ),
        },
        "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
        "source_object": None,
        "step_id": f"erratum-arrival-history-{fixture_id.lower()}",
    }
    if prior is not None:
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
                    "obligation keys are byte for byte the predecessor's, so both digests "
                    "are unchanged and the historical materialization digest is preserved "
                    "under historical_digests"
                ),
            },
            "predecessor_invalidity": {
                "predecessor_values": {
                    "decision_script": copy.deepcopy(prior_script),
                },
                "reason": (
                    "the 1.0.28 predecessor left its game-start arrival history "
                    "undeclared for this record (no keep for "
                    + (", ".join(added_seats) or "any seat")
                    if added_seats
                    else "the 1.0.28 predecessor left its game-start arrival history incomplete"
                )
                + (" and no priority pass-through scope" if pass_added[fixture_id] else "")
                + ", so the arrival answered those frames with Lab defaults "
                "(#637 PB-03 run 37860773242)",
            },
            "replace": merged_replace,
            "successor_requested_state_digest": successor_digest,
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
    else:
        patch = {
            "append_native_procedure": [erratum],
            "authority_overlay": dict(OVERLAY),
            "correction_class": CORRECTION_CLASS,
            "digest_migration": {
                **DIGEST_MIGRATION,
                "reason": (
                    "the declared decision script gains the arrival history; the requested "
                    "state and the obligation keys are byte for byte the base record's, so "
                    "both digests are unchanged and the historical materialization digest "
                    "is preserved under historical_digests"
                ),
            },
            "evidence_survival": "REQUALIFICATION_REQUIRED",
            "fixture_id": fixture_id,
            "knowledge_state_channel_policy": base[fixture_id]["knowledge_state"]["channel_policy"],
            "predecessor_invalidity": {
                "predecessor_values": {"decision_script": copy.deepcopy(prior_script)},
                "reason": (
                    "the base record left its game-start arrival history undeclared: no "
                    "pregame keep and no priority pass-through scope, so the arrival "
                    "answered those frames with Lab defaults (#637 PB-03 run 37860773242)"
                ),
            },
            "predecessor_requested_state_digest": base[fixture_id]["requested_state_digest"],
            "replace": merged_replace,
            "successor_requested_state_digest": successor_digest,
        }
    assert resolver.requested_state_digest(corrected) == patch["successor_requested_state_digest"]
    # The requested state is untouched: this is a decision-script-only erratum.
    assert prior_digest == patch["successor_requested_state_digest"], fixture_id
    patches[fixture_id] = patch

# --- assemble the 1.0.29 contract --------------------------------------------- #

replaced = [patches.get(p["fixture_id"], p) for p in contract["record_successors"]]
assert [p["fixture_id"] for p in replaced] == [
    p["fixture_id"] for p in contract["record_successors"]
]
new_patches = [patches[fixture_id] for fixture_id in FIXTURES if fixture_id not in existing]
assert len(new_patches) == sum(1 for fixture_id in FIXTURES if fixture_id not in existing)
contract["record_successors"] = [*replaced, *new_patches]

accounting = contract["change_accounting"]
for fixture_id in FIXTURES:
    if fixture_id not in accounting["changed_fixture_ids"]:
        accounting["changed_fixture_ids"].append(fixture_id)
    accounting["per_fixture_correction_class"][fixture_id] = CORRECTION_CLASS
accounting["change_class"] = "MIXED_FIXTURE_CONTRACT_ERRATA_AND_RULES_AUTHORITY_CORRECTION"
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
accounting["unchanged_provider_denominator_rows"] = sum(
    1 for fixture_id in denominator if fixture_id not in accounting["changed_fixture_ids"]
)
contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.29 carries "
    "every 1.0.28 record successor and the bounded-secondary PLAYER_COUNT_6P section "
    "byte for byte, and adds the game-start arrival-history declarations to every "
    "remaining arrival-using lane record that lacked them -- the 20 "
    "knowledge_projection.ROWS rows and the 5 midgame_replay_twin.ROWS rows: one "
    "pregame mulligan keep per seat present in the record (CR 103.5) and a priority "
    "pass-through scope (actor ALL) from game start to the record's own checkpoint, "
    "until exclusive (CR 117.3d). The obligation keys and the 107-row denominator are "
    "untouched and no runtime credit is claimed. Per #634 / #592 Coordinator ruling "
    "2026-10-09."
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_28.json",
    "record_count": len(contract["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.28 overlay to the same 1.0.5 historical base and adds the game-start "
        "arrival-history declarations to every remaining arrival-using lane record "
        "(knowledge projection and replay twin) that lacked them, with the obligation "
        "keys unchanged"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.29 ------------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_28_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.28", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.28", NEW_VERSION)
# The 1.0.29 declarations reuse the 1.0.28 declared shapes exactly: the mulligan
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
    if fixture_id not in full["changed_fixture_ids"]:
        full["changed_fixture_ids"].append(fixture_id)
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
    prior = existing.get(fixture_id)
    new_entries.append(
        dict(
            sorted(
                {
                    "correction_class": CORRECTION_CLASS,
                    "denominator_effect": "NONE",
                    "effective_obligation_digest": obligation_digests[fixture_id],
                    "effective_requested_state_digest": patch["successor_requested_state_digest"],
                    "evidence_survival": "REQUALIFICATION_REQUIRED",
                    "field_changes": copy.deepcopy(
                        patch["append_native_procedure"][-1]["details"]["field_changes"]
                    ),
                    "fixture_id": fixture_id,
                    "known_runtime_blocker": KNOWN_RUNTIME_BLOCKER,
                    "notes": (
                        "#634 / #592 Coordinator ruling 2026-10-09: the "
                        "arrival-using lane's game-start history was undeclared, so the "
                        "Lab answered pregame keeps and priority with defaults. The "
                        "record now declares one pregame keep per seat (CR 103.5; "
                        + (", ".join(keeps_added[fixture_id]) or "no missing seat")
                        + ") and "
                        + (
                            "a priority pass-through scope from game start to the row's "
                            "checkpoint (CR 117.3d)"
                            if pass_added[fixture_id]
                            else "its existing priority pass-through scope is carried"
                        )
                        + "; the Lab transports each frame and unscripted frames fail "
                        "closed. The obligation digest is unchanged, the 107-row "
                        "denominator is untouched and no runtime credit is claimed"
                    ),
                    "predecessor_requested_state_digest": (
                        prior["successor_requested_state_digest"]
                        if prior is not None
                        else base[fixture_id]["requested_state_digest"]
                    ),
                    "successor_contract": SUCCESSOR_PATH,
                }.items()
            )
        )
    )
ledger["records"] = [*ledger["records"], *new_entries]
lpath.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

print("wrote", dst.name, "predecessor sha256", contract["predecessor"]["sha256"])
print("patched", len(FIXTURES), "records;", len(new_patches), "new patch entries")
for fixture_id in FIXTURES:
    print(
        fixture_id,
        "keeps+",
        keeps_added[fixture_id] or "none",
        "pass" if pass_added[fixture_id] else "carried",
        patches[fixture_id]["successor_requested_state_digest"],
    )
