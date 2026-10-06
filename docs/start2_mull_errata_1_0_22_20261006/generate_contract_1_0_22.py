"""Generate FULL107 successor contract 1.0.22 from 1.0.21: the START-2 and MULL errata.

Coordinator ruling on Lab issue #441 (comment 6007651998), under the #560
delegation (AGENTS.md section 8). Each erratum is versioned, digest-bound and
lineage-preserving; changed fixture bytes are a new evidence identity and no
historical PASS transfers (every changed row is REQUALIFICATION_REQUIRED).

* WS05-CMD-START-2, erratum (b), natural-start record. The 1.0.6 successor
  constructs the state at turn-1 precombat main (NATIVE_STATE_LOAD) and then
  asks the provider to advance through turn 1's beginning phase, which a state
  already past that phase cannot do. The frozen obligation is the two-player
  starting player and first draw (CR 103.8a); Rograkh and the Grizzly Bears are
  filler. The successor is a natural game start: per-seat Rograkh plus a
  99-Mountain library template, seeded per-seat library shuffles, pregame
  mulligan checkpoint at turn 0 with P1 active and holding priority, the two
  command-zone commanders only. The starting player (P1) and both round-1 keeps
  are scripted decisions (the Lab never chooses for a player). expected_events
  and terminal_postconditions are the 1.0.21 values, unchanged; the 1.0.6
  skip-proof step stays active.
* WS05-CMD-MULL-2 / MULL-4, rules-randomness erratum (obligation unchanged).
  Their rules_randomness names the channel INITIAL_LIBRARY_SHUFFLE and the
  seed binding SCENARIO_SEED but no rules_seed, so the construction proof
  reports rules_seed MISMATCH (None against the acknowledged seed) and the
  channel UNSUPPORTED, and the lane filled the gap with a default. The
  successor uses the PILOT_MULLIGAN shape: rules_seed 424242 and the per-seat
  channels library_shuffle:P1..Pn.

All three patches supersede their 1.0.21 overlays in place and extend them
(the RNG_RULES_TAPE precedent of 1.0.21); the superseded patch is kept under
superseded_successor_patch as lineage.

Idempotent: always regenerated from the 1.0.21 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_21.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_22.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.21-successor"
DECISIONS = (
    "#441 comment 6007651998 (Coordinator ruling under the #560 delegation, AGENTS.md section 8)"
)
RULES_SEED = 424242
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": "fixture-contract successor rule: #441 START-2/MULL errata",
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_FROM_THE_1_0_21_SUCCESSOR_OBLIGATION_KEYS_UNTOUCHED",
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


def _apply(old: dict, patch: dict) -> dict:
    """The record a patch yields on its historical base (the resolver's overlay)."""
    record = copy.deepcopy(old)
    for key, value in patch["replace"].items():
        record[key] = copy.deepcopy(value)
    record["knowledge_state"]["channel_policy"] = patch["knowledge_state_channel_policy"]
    record.setdefault("native_procedure", []).extend(
        copy.deepcopy(patch["append_native_procedure"])
    )
    return record


def _erratum_step(fixture: str, slug: str, details: dict) -> dict:
    return {
        "actor": None,
        "details": {
            "authority": DECISIONS,
            "obligation_changed": False,
            "provider_semantics_used": False,
            **details,
        },
        "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
        "source_object": None,
        "step_id": f"erratum-{slug}-{fixture.lower()}",
    }


def _players(record: dict) -> list[str]:
    return [player["player_id"] for player in record["players"]]


def _pregame_deck(player: str) -> dict:
    return {
        "commander_ids": [f"cmd:{player}-A"],
        "library_template": {"card_identity": "Mountain", "count": 99},
        "opening_hand_size": 7,
        "player_id": player,
        "shuffle_channel": f"library_shuffle:{player}",
    }


FORBIDDEN = [
    "first_option",
    "random_option",
    "default_yes_no",
    "internal_ai",
    "gui_default",
    "silent_skip",
    "parent_class_fallback",
]


def _step(
    actor: str, step_id: str, family: str, selector: str, value: object, notes: str = ""
) -> dict:
    """One decision-script entry in the shape every successor record uses."""
    return {
        "actor": actor,
        "causal_step_id": step_id,
        "decision_family": family,
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": notes,
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": selector,
            "semantic_value": value,
        },
    }


def _randomness(players: list[str]) -> dict:
    """The PILOT_MULLIGAN rules-randomness shape for these seats."""
    return {
        "channels": [f"library_shuffle:{player}" for player in players],
        "pilot_randomness_prohibited": True,
        "predetermined_semantic_draws": [],
        "rules_seed": RULES_SEED,
    }


patches: list[dict] = []


def supersede(
    fixture: str,
    correction_class: str,
    replace: dict,
    keep_steps: list[dict],
    errata: list[dict],
    invalidity: dict,
    reason: str,
    overlay: dict,
) -> None:
    """Supersede the 1.0.21 overlay of ``fixture`` in place and extend it.

    The prior replace is kept and extended; ``keep_steps`` are the prior steps
    that stay active procedure (they are still true), and the whole prior patch
    is kept as lineage under superseded_successor_patch.
    """
    old = base[fixture]
    prior = existing[fixture]
    prior_record = _apply(old, prior)
    merged_replace = copy.deepcopy(prior["replace"])
    merged_replace.update(copy.deepcopy(replace))
    patch = {
        "append_native_procedure": [*copy.deepcopy(keep_steps), *errata],
        "authority_overlay": dict(overlay),
        "correction_class": correction_class,
        "digest_migration": {**DIGEST_MIGRATION, "reason": reason},
        "evidence_survival": "REQUALIFICATION_REQUIRED",
        "fixture_id": fixture,
        "knowledge_state_channel_policy": prior["knowledge_state_channel_policy"],
        "predecessor_invalidity": invalidity,
        "predecessor_requested_state_digest": old["requested_state_digest"],
        "replace": merged_replace,
    }
    record = _apply(old, patch)
    patch["successor_requested_state_digest"] = resolver.requested_state_digest(record)
    patch["superseded_successor_patch"] = {
        "contract": PRIOR_CONTRACT,
        "correction_class": prior["correction_class"],
        "patch_sha256": hashlib.sha256(resolver.canonical_json(prior).encode("utf-8")).hexdigest(),
        "successor_requested_state_digest": prior["successor_requested_state_digest"],
        "append_native_procedure": copy.deepcopy(prior["append_native_procedure"]),
        "lineage": (
            "its replace is kept and extended; its erratum steps are preserved here as "
            "history, and only the steps this successor carries in its own "
            "append_native_procedure are active procedure"
        ),
    }
    # The obligation is the 1.0.21 one, key for key (#441 6007651998).
    assert resolver.obligation_digest(record) == resolver.obligation_digest(prior_record), fixture
    assert record["expected_events"] == prior_record["expected_events"], fixture
    assert record["terminal_postconditions"] == prior_record["terminal_postconditions"], fixture
    assert patch["successor_requested_state_digest"] != prior["successor_requested_state_digest"]
    assert patch["successor_requested_state_digest"] != old["requested_state_digest"], fixture
    patches.append(patch)


# --- WS05-CMD-START-2: erratum (b), natural-start record ------------------- #

FIXTURE = "WS05-CMD-START-2"
old = base[FIXTURE]
prior = existing[FIXTURE]
prior_record = _apply(old, prior)
assert prior["correction_class"] == "OFFICIAL_RULES_AUTHORITY_CORRECTION"
assert prior_record["execution_entry_mode"] == "NATIVE_STATE_LOAD"
assert (
    prior_record["temporal_state"]["phase"],
    prior_record["temporal_state"]["turn_number"],
) == ("precombat_main", 1)
players = _players(old)
assert players == ["P1", "P2"], players
(skip_proof,) = prior["append_native_procedure"]
assert skip_proof["step_id"] == "start2-cr1038a-skip-proof"
commanders = [o for o in old["semantic_objects"] if o["zone"] == "command"]
dropped = [o for o in old["semantic_objects"] if o["zone"] != "command"]
assert [o["semantic_id"] for o in commanders] == ["obj:P1-commander", "obj:P2-commander"]
assert [(o["semantic_id"], o["card_identity"]) for o in dropped] == [
    ("obj:P1-bears", "Grizzly Bears"),
    ("obj:P2-bears", "Grizzly Bears"),
]
assert [c["commander_id"] for c in old["commander_state"]["commanders"]] == [
    "cmd:P1-A",
    "cmd:P2-A",
]
natural_procedure = [
    {
        "details": {"player_count": len(players), "starting_life": 40},
        "operation": "CREATE_COMMANDER_GAME",
        "step_id": "create",
    },
    {
        "details": {"channels": [f"library_shuffle:{p}" for p in players]},
        "operation": "NATIVE_SEEDED_INITIAL_SHUFFLE",
        "step_id": "shuffle",
    },
    {
        "details": {"cards_each": 7},
        "operation": "NATIVE_OPENING_HAND_DRAW",
        "step_id": "draw",
    },
    *(
        {
            "actor": p,
            "details": {"round": 1},
            "operation": "NATIVE_MULLIGAN_PROMPT",
            "step_id": f"mull-r1-{p}",
        }
        for p in players
    ),
]
# The Lab never chooses for a player (#441, Coordinator extension of 6007651998):
# the starter and every keep are the record's own scripted decisions.
assert old["decision_script"] == [] and old.get("pregame_decision_plan") is None
start2_script = [
    _step(
        "P1",
        "start-P1",
        "starting_player",
        "semantic_player",
        "P1",
        notes=(
            "CR 103.1: the starting player is a player's choice; P1 is the record's "
            "starting player (temporal_state.active_player), scripted, never a lane default"
        ),
    ),
    *(
        _step(p, f"mull-r1-{p}", "mulligan", "semantic_action", "keep_opening_hand")
        for p in players
    ),
]
start2_plan = [{"decision": "KEEP", "player_id": p, "round": 1} for p in players]
supersede(
    FIXTURE,
    "NATURAL_START_SCENARIO_ERRATUM",
    {
        "execution_entry_mode": "NATURAL_GAME_START",
        "deck_state": [_pregame_deck(p) for p in players],
        "semantic_objects": copy.deepcopy(commanders),
        "temporal_state": {
            "active_player": "P1",
            "extra_turn_queue": [],
            "phase": "pregame",
            "priority_player": "P1",
            "step": "mulligan",
            "turn_number": 0,
        },
        "rules_randomness": _randomness(players),
        "native_procedure": natural_procedure,
        "decision_script": start2_script,
        "pregame_decision_plan": start2_plan,
    },
    [skip_proof],
    [
        _erratum_step(
            FIXTURE,
            "natural-start",
            {
                "erratum_class": "NATURAL_START_SCENARIO_ERRATUM",
                "comprehensive_rules": "103.8a",
                "reason": (
                    "The 1.0.6 successor constructs the requested state at turn-1 precombat "
                    "main (NATIVE_STATE_LOAD) and then requires the provider to advance "
                    "through turn 1's beginning phase and verify that the draw step was "
                    "skipped. A state constructed after the beginning phase cannot advance "
                    "through it, so the record is self-contradictory. The CR 103.8a "
                    "observation (a turn-1 upkeep baseline, no draw step, then precombat "
                    "main) exists only on a natural game start, which is the record this "
                    "successor states"
                ),
                "obligation_scope": (
                    "the frozen obligation is the two-player starting player and first "
                    "draw (CR 103.8a). Rograkh and the Grizzly Bears were filler: "
                    "multiplayer turn-1 draws (CR 103.8c) belong to START-3 and "
                    "commander-specific behaviour to the PARTNER rows, so dropping the "
                    "Bears and constructing nothing mid-game loses no obligation"
                ),
                "deck_shape": (
                    "each seat is its Rograkh commander plus the 99-Mountain library "
                    "template, opening hand 7, shuffled on its own library_shuffle:Pn "
                    "channel (the PILOT_MULLIGAN shape)"
                ),
                "construction_point": (
                    "the generic lane reads the constructed state at the first mulligan "
                    "decision before it is answered: pregame, step mulligan, turn 0, with "
                    "P1 the starting player holding the game's first priority (CR 103.1)"
                ),
                "rules_seed_binding": (
                    "the seed and the per-seat shuffle channels are record values; the "
                    "lane takes the seed from the record and the construction proof "
                    "compares it with the seed the engine acknowledged, never with a lane "
                    "default"
                ),
                "starting_player_evidence": (
                    "starting-player credit comes only from the first_priority_seat the "
                    "construction proof compares, never from the first actor on the "
                    "decision tape"
                ),
                "skip_proof_step": "start2-cr1038a-skip-proof stays active procedure",
                "scripted_decisions": (
                    "the starting player (P1, decision family starting_player) and both "
                    "round-1 keeps (the PILOT_MULLIGAN plan shape) are the record's own "
                    "decisions; the Lab chooses neither, and a record without them is refused"
                ),
                "route": "PROTOCOL2_START2 on an orchestration-keyed launch with the record's decks",
            },
        )
    ],
    {
        "reason": (
            "construct-then-advance contradiction: the predecessor requests a constructed "
            "state at turn-1 precombat main (NATIVE_STATE_LOAD) and then asks the provider "
            "to advance through turn 1's beginning phase and verify the skipped draw step, "
            "which a state already past the beginning phase cannot do. It also names "
            "Grizzly Bears on the battlefield, which no natural game start holds, and a "
            "native state load, which the generic construction proof never marks EQUAL"
        ),
        "predecessor_values": {
            "execution_entry_mode": prior_record["execution_entry_mode"],
            "temporal_state": prior_record["temporal_state"],
            "rules_randomness": prior_record["rules_randomness"],
            "dropped_semantic_objects": [o["semantic_id"] for o in dropped],
            "decision_script": prior_record["decision_script"],
            "native_procedure_operations": [
                step["operation"] for step in old.get("native_procedure") or ()
            ],
        },
    },
    (
        "The entry mode, decks, objects, checkpoint, Rules randomness and native "
        "procedure change; expected_events and terminal_postconditions are the 1.0.21 values."
    ),
    prior["authority_overlay"],
)

# --- WS05-CMD-MULL-2 / MULL-4: rules-randomness erratum --------------------- #

for fixture, count in (("WS05-CMD-MULL-2", 2), ("WS05-CMD-MULL-4", 4)):
    old = base[fixture]
    prior = existing[fixture]
    prior_record = _apply(old, prior)
    players = _players(old)
    assert len(players) == count and players == [f"P{i}" for i in range(1, count + 1)], players
    assert prior_record["rules_randomness"] == {
        "channels": ["INITIAL_LIBRARY_SHUFFLE"],
        "pilot_randomness_prohibited": True,
        "seed_binding": "SCENARIO_SEED",
    }, fixture
    assert [d["shuffle_channel"] for d in prior_record["deck_state"]] == [
        f"library_shuffle:{p}" for p in players
    ]
    supersede(
        fixture,
        "FIXTURE_SCRIPT_CONTRACT_AND_RULES_RANDOMNESS_ERRATUM",
        {"rules_randomness": _randomness(players)},
        prior["append_native_procedure"],
        [
            _erratum_step(
                fixture,
                "rules-randomness",
                {
                    "erratum_class": "RULES_RANDOMNESS_ERRATUM",
                    "reason": (
                        "The predecessor's rules_randomness names the channel "
                        "INITIAL_LIBRARY_SHUFFLE and the seed binding SCENARIO_SEED but no "
                        "rules_seed. The construction proof therefore compares no record "
                        "seed (rules_seed MISMATCH: None against the acknowledged seed) and "
                        "cannot construct the channel (UNSUPPORTED), and the lane supplied "
                        "the missing seed from its own default, which is not a record value. "
                        "The successor states the seed SCENARIO_SEED meant (424242, the "
                        "manifest value) and one library-shuffle channel per seat, in the "
                        "PILOT_MULLIGAN shape"
                    ),
                    "native_procedure_binding": (
                        "the native 'initial-shuffle' step (INITIAL_LIBRARY_SHUFFLE) is the "
                        "per-seat Rules-RNG library shuffles these channels name; the step "
                        "itself is unchanged"
                    ),
                    "obligation_scope": "the pregame decisions, decks and script are the 1.0.21 values",
                    "route": "PROTOCOL2_SCRIPTED_PREGAME (the PILOT_MULLIGAN precedent)",
                },
            )
        ],
        {
            "predecessor_values": {"rules_randomness": prior_record["rules_randomness"]},
            "reason": (
                "no rules_seed and a channel no provider constructs; a lane default filled the seed"
            ),
        },
        "Only the Rules randomness changes.",
        OVERLAY,
    )

# --- assemble --------------------------------------------------------------- #

# Each superseding patch takes its predecessor's place, so every other overlay
# keeps its order and its bytes.
by_fixture = {patch["fixture_id"]: patch for patch in patches}
contract["record_successors"] = [
    by_fixture.get(p["fixture_id"], p) for p in contract["record_successors"]
]
accounting = contract["change_accounting"]
for patch in patches:
    fixture = patch["fixture_id"]
    assert fixture in accounting["changed_fixture_ids"], fixture
    accounting["per_fixture_correction_class"][fixture] = patch["correction_class"]
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
contract["contract_id"] = "commander-lab.full107/1.0.22-successor"
contract["effective_materialization_version"] = (
    "commander-lab.semantic-fixture-materialization/1.0.22-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.22 supersedes the "
    "1.0.21 overlays of WS05-CMD-START-2 (natural-start record) and WS05-CMD-MULL-2/4 "
    "(Rules-randomness seed and channels) in place, per #441 comment 6007651998, while "
    "preserving every other 1.0.21 overlay byte for byte"
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_21.json",
    "record_count": len(json.loads(raw)["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every current "
        "overlay to the same 1.0.5 historical base and supersedes three 1.0.21 overlays in "
        "place, extending (never dropping) each and keeping it as lineage"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_21_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.21", "1.0.22")
schema["$id"] = schema["$id"].replace("1.0.21", "1.0.22")
enum = schema["$defs"]["record"]["properties"]["materialization_version"]["enum"]
if "commander-lab.semantic-fixture-materialization/1.0.22-successor" not in enum:
    enum.append("commander-lab.semantic-fixture-materialization/1.0.22-successor")
schema["properties"]["contract_id"]["const"] = "commander-lab.full107/1.0.22-successor"
schema["properties"]["schema_version"]["const"] = (
    "commander-lab.semantic-fixture-materialization/1.0.22-successor"
)
indent = 2 if schema_text.startswith('{\n  "') else 1
(PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_22_SUCCESSOR.json").write_text(
    json.dumps(schema, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
)

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = (
    "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_22.json"
)
full["effective_materialization_schema"] = (
    "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_22_SUCCESSOR.json"
)
for patch in patches:
    fixture = patch["fixture_id"]
    assert fixture in full["changed_fixture_ids"], fixture
    full["evidence_survival"][fixture] = "REQUALIFICATION_REQUIRED_" + patch["correction_class"]
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# The stale START-2 runtime PASS entries of the 1.0.7 errata ledger are history:
# the record they ran no longer exists, so they move under historical, never deleted.
lpath = REPO / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
ledger = json.loads(lpath.read_text(encoding="utf-8"))
(entry,) = [r for r in ledger["records"] if r["fixture_id"] == FIXTURE]
if "runtime_verdicts" in entry:
    entry["historical_runtime_verdicts"] = entry.pop("runtime_verdicts")
entry["historical_runtime_verdicts_status"] = (
    "HISTORICAL_PROVENANCE_ONLY: these verdicts ran the 1.0.7 START-2 record; contract "
    "1.0.22 supersedes it (natural-start record, #441 comment 6007651998), the changed "
    "fixture bytes are a new evidence identity and no historical PASS transfers"
)
(start2,) = [p for p in patches if p["fixture_id"] == FIXTURE]
entry["superseded_by"] = {
    "contract": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_22.json",
    "correction_class": start2["correction_class"],
    "successor_requested_state_digest": start2["successor_requested_state_digest"],
    "evidence_survival": "REQUALIFICATION_REQUIRED",
    "current_runtime_credit": "NONE_UNTIL_PB03_AND_A_SEALED_EPOCH",
}
# The ledger keeps its records' keys in sorted order.
ledger["records"] = [
    dict(sorted(r.items())) if r["fixture_id"] == FIXTURE else r for r in ledger["records"]
]
lpath.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", dst.name, "records", len(contract["record_successors"]))
for patch in patches:
    print(patch["fixture_id"], patch["successor_requested_state_digest"])
