"""Generate FULL107 successor contract 1.0.23 from 1.0.22: the bounded-secondary 6P record.

Coordinator erratum (Lab issue #441, 2026-10-07; parent #255), modelled exactly
on the PR #583 / 1.0.22 precedent (deterministic generator, contract + schema,
authority pointer, errata-ledger entry, manifests via the repository tool).

The recorded AF04 gap (adjudication #599 finding 4) is that the bounded-secondary
6P lifecycle runs record-less: the runner passes ``record=by_id.get(
"PLAYER_COUNT_6P")``, which is None because PLAYER_COUNT_6P is not a FULL107
denominator row, so the run declares no starting seat. XMage's create channel
requires one, Forge offers a STARTING_PLAYER decision, and the Lab never chooses
(#572/#574), so 6P fails DecisionUnsatisfied and decision_boundary.py turns that
gap into AF04 UNKNOWN.

This successor adds exactly one authoritative bounded-secondary, non-denominator
record, modelled on the existing PLAYER_COUNT_5P record:

* the same deck shape per seat (Rograkh commander plus the 99-Mountain library
  template, opening hand 7, one seeded ``library_shuffle:Pn`` channel per seat);
* an explicit integer ``rules_seed`` (424242, the PLAYER_COUNT_5P value);
* the same NATURAL_GAME_START pregame plan with one round-1 keep per seat;
* a starting-seat declaration exactly in the form the 2P-5P model records use,
  consumed by ``starting_player.record_starting_seat``: the pre-first-turn
  ``temporal_state.active_player`` (P1, turn 0). The record declares the
  pre-first-turn active player; it adds no separate scripted
  ``starting_player`` step, so its declaration channel is identical to the
  PLAYER_COUNT_5P record's.

The record is authoritative only as the ``record`` argument of the 6P
``run_cardinality`` call. It never becomes a FULL107 row, never changes the
107-row denominator and never affects AF06; there is no ``cardinality_row`` for
it. If the record is absent the lifecycle keeps its record-less, fail-closed
behaviour (``run_cardinality(record=None)``).

Everything else in 1.0.22 is carried over byte for byte: every record successor,
the change accounting, the evidence policy, the rules authority block and the
schema shape. Only the contract id, the effective materialization version, the
predecessor binding, the schema note and the new bounded-secondary section
change, plus the authority pointer and the errata ledger entry.

Idempotent: always regenerated from the 1.0.22 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_22.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_23.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.22-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_23.json"
DECISIONS = (
    "#441 Coordinator erratum 2026-10-07 (contract 1.0.23): add the "
    "bounded-secondary PLAYER_COUNT_6P record to close the recorded AF04 gap"
)
FIXTURE = "PLAYER_COUNT_6P"
MODEL_FIXTURE = "PLAYER_COUNT_5P"
NEW_VERSION = "1.0.23"
NEW_MINOR = "23"

raw = src.read_bytes()
contract = json.loads(raw)
authority = json.loads((REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json").read_text())
base = {
    record["fixture_id"]: record
    for record in json.loads(
        (REPO / authority["full107"]["historical_base_materialization"]).read_text()
    )["records"]
}
model = copy.deepcopy(base[MODEL_FIXTURE])
assert model["fixture_id"] == MODEL_FIXTURE
assert model["rules_randomness"]["rules_seed"] == 424242
assert model["temporal_state"] == {
    "active_player": "P1",
    "extra_turn_queue": [],
    "phase": "pregame",
    "priority_player": "P1",
    "step": "game_start",
    "turn_number": 0,
}, model["temporal_state"]


# --- the bounded-secondary 6P record ---------------------------------------- #


def _sixp() -> dict:
    record = copy.deepcopy(model)
    record["fixture_id"] = FIXTURE

    # Same deck shape per seat, one more seat.
    record["players"].append({**copy.deepcopy(record["players"][-1]), "player_id": "P6", "seat": 6})
    record["commander_state"]["commanders"].append(
        {
            **copy.deepcopy(record["commander_state"]["commanders"][-1]),
            "commander_id": "cmd:P6-A",
            "owner": "P6",
        }
    )
    record["semantic_objects"].append(
        {
            **copy.deepcopy(record["semantic_objects"][-1]),
            "card_lineage_id": "line:obj:P6-commander",
            "commander_id": "cmd:P6-A",
            "controller": "P6",
            "owner": "P6",
            "semantic_id": "obj:P6-commander",
        }
    )
    record["deck_state"].append(
        {
            **copy.deepcopy(record["deck_state"][-1]),
            "commander_ids": ["cmd:P6-A"],
            "player_id": "P6",
            "shuffle_channel": "library_shuffle:P6",
        }
    )
    record["knowledge_state"]["viewer_states"].append(
        {**copy.deepcopy(record["knowledge_state"]["viewer_states"][-1]), "viewer": "P6"}
    )
    record["rules_randomness"] = {
        **copy.deepcopy(record["rules_randomness"]),
        "channels": [f"library_shuffle:P{i}" for i in range(1, 7)],
    }
    record["pregame_decision_plan"].append({"decision": "KEEP", "player_id": "P6", "round": 1})

    # No separate scripted starting_player step: the 6P record declares the seat
    # through the same channel as its PLAYER_COUNT_5P model (and 2P-4P), the
    # pre-first-turn temporal_state.active_player consumed by
    # starting_player.record_starting_seat. Only the six keeps are scripted.
    keeps = copy.deepcopy(record["decision_script"])
    assert [step["actor"] for step in keeps] == [f"P{i}" for i in range(1, 6)]
    keeps.append({**copy.deepcopy(keeps[-1]), "actor": "P6", "causal_step_id": "keep-P6"})
    record["decision_script"] = keeps
    for index, step in enumerate(record["decision_script"], start=1):
        assert step["decision_family"] == "mulligan" and step["actor"] == f"P{index}"

    procedure = copy.deepcopy(record["native_procedure"])
    create, shuffle, draw, *keeps_and_start = procedure
    assert create["operation"] == "CREATE_COMMANDER_GAME"
    assert shuffle["operation"] == "NATIVE_SEEDED_INITIAL_SHUFFLE"
    assert draw["operation"] == "NATIVE_OPENING_HAND_DRAW"
    start = keeps_and_start.pop()
    assert start["operation"] == "NATIVE_START_FIRST_TURN"
    create["details"] = {**create["details"], "player_count": 6}
    shuffle["details"] = {
        **shuffle["details"],
        "channels": [f"library_shuffle:P{i}" for i in range(1, 7)],
    }
    keeps_and_start.append(
        {
            "actor": "P6",
            "details": {"round": 1},
            "operation": "NATIVE_MULLIGAN_PROMPT",
            "step_id": "keep-P6",
        }
    )
    record["native_procedure"] = [create, shuffle, draw, *keeps_and_start, start]

    record["terminal_postconditions"] = [
        "exactly 6 live real players exist" if text == "exactly 5 live real players exist" else text
        for text in record["terminal_postconditions"]
    ]
    assert record["terminal_postconditions"][0] == "exactly 6 live real players exist"

    # The historical WS41 manifest bindings of the 5P model do not exist for a
    # 6P record and are never fabricated. Its authority is this successor
    # contract plus its own generator-computed digests.
    record["authority_provenance"] = {
        "bounded_secondary_record": True,
        "historical_materialization_provenance": "NONE_NO_WS41_MANIFEST_ROW_FOR_6P",
        "rsp": "commander-lab.rules-service/1.1.0",
        "successor_contract": SUCCESSOR_PATH,
    }
    record["frozen_contract_binding"] = {
        "af_mapping": "INHERIT_BY_REFERENCE_NO_REDEFINITION",
        "binding": "SUCCESSOR_CONTRACT_1_0_23_BOUNDED_SECONDARY_RECORD",
        "manifest_fixture_id": FIXTURE,
        "manifest_sha256": "NONE_NO_HISTORICAL_MANIFEST_ROW",
    }
    record["materialization_status"] = "BOUNDED_SECONDARY_NON_DENOMINATOR"
    record["materialization_version"] = (
        f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
    )
    record["repair_provenance"] = {
        "correction_class": "BOUNDED_SECONDARY_STARTING_SEAT_ERRATUM",
        "historical_record_preserved": False,
        "model_record": MODEL_FIXTURE,
        "predecessor_requested_state_digest": None,
        "provider_semantics_used": False,
        "source": DECISIONS,
    }
    record.pop("supersedes_record_digest", None)
    record["scenario_notes"] = [
        *record["scenario_notes"],
        (
            "Bounded-secondary 6P record of contract 1.0.23: modelled on "
            "PLAYER_COUNT_5P; used only as the record argument of the 6P cardinality "
            "lifecycle and never as a FULL107 denominator row."
        ),
    ]
    record["requested_state_digest"] = resolver.requested_state_digest(record)
    record["obligation_digest"] = resolver.obligation_digest(record)
    record["materialization_digest"] = resolver.materialization_digest(record)
    return record


sixp = _sixp()
assert resolver.requested_state_digest(sixp) == sixp["requested_state_digest"]
assert resolver.obligation_digest(sixp) == sixp["obligation_digest"]
assert resolver.materialization_digest(sixp) == sixp["materialization_digest"]
# The 107-row denominator is untouched by construction.
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert len(denominator) == 107
assert FIXTURE not in denominator

# --- assemble the 1.0.23 contract ------------------------------------------- #

contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.23 carries every "
    "1.0.22 record successor and every other 1.0.22 field byte for byte, and adds exactly "
    "one bounded-secondary, non-denominator record section: PLAYER_COUNT_6P, used only as "
    "the record argument of the 6P cardinality lifecycle (AF04). It is not a FULL107 row, "
    "the denominator stays exactly 107 and AF06 is unaffected. Per #441 Coordinator "
    "erratum 2026-10-07."
)
contract["bounded_secondary_records"] = {
    "authority": DECISIONS,
    "denominator_effect": "NONE",
    "af06_effect": "NONE",
    "policy": (
        "A bounded-secondary record is authoritative only as the record argument of its "
        "lifecycle run. It never becomes a FULL107 denominator row, produces no "
        "cardinality_row, and changes neither the 107-row denominator nor AF06. If the "
        "successor contract carries no such record, the lifecycle runs record-less and "
        "fails closed (the Lab supplies no default starting seat or seed)."
    ),
    "records": [sixp],
}
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_22.json",
    "record_count": len(json.loads(raw)["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.22 overlay to the same 1.0.5 historical base byte for byte and adds exactly "
        "one bounded-secondary, non-denominator 6P record"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.23 ----------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_22_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.22", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.22", NEW_VERSION)
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

# --- authority pointer -------------------------------------------------------- #

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = SUCCESSOR_PATH
full["effective_materialization_schema"] = (
    f"qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_{NEW_MINOR}_SUCCESSOR.json"
)
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- errata ledger entry ------------------------------------------------------ #

lpath = REPO / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
ledger = json.loads(lpath.read_text(encoding="utf-8"))
# Idempotent: a prior run's entry is replaced, never duplicated.
ledger["records"] = [record for record in ledger["records"] if record["fixture_id"] != FIXTURE]
entry = {
    "correction_class": "BOUNDED_SECONDARY_NON_DENOMINATOR_RECORD_ADDITION",
    "denominator_effect": "NONE",
    "effective_obligation_digest": sixp["obligation_digest"],
    "effective_requested_state_digest": sixp["requested_state_digest"],
    "evidence_survival": "NO_RUNTIME_CREDIT_UNTIL_PB03_AND_A_SEALED_EPOCH",
    "fixture_id": FIXTURE,
    "model_record": MODEL_FIXTURE,
    "notes": (
        "bounded-secondary, non-denominator record added by successor contract 1.0.23 to "
        "close the recorded AF04 6P starting-seat gap: it is used only as the record "
        "argument of the 6P cardinality lifecycle, never as a FULL107 row; the 107-row "
        "denominator and AF06 are unchanged"
    ),
    "successor_contract": SUCCESSOR_PATH,
}
ledger["records"] = [
    *ledger["records"],
    dict(sorted(entry.items())),
]
lpath.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

print("wrote", dst.name, "predecessor sha256", contract["predecessor"]["sha256"])
print(FIXTURE, sixp["requested_state_digest"], sixp["obligation_digest"])
