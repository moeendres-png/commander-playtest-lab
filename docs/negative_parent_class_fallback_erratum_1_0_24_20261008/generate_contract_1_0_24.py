"""Generate FULL107 successor contract 1.0.24 from 1.0.23: the NEGATIVE_PARENT_CLASS_FALLBACK cast timing and cost consistency erratum.

Coordinator erratum (Lab issue #441, 2026-10-08; parent #255), modelled exactly
on the PR #583 / #604 precedent (deterministic generator, contract + schema,
authority pointer, errata-ledger entry, manifests via the repository tool).

The recorded defect is scoped to cast timing and cost consistency: the
effective NEGATIVE_PARENT_CLASS_FALLBACK record declares a fully cast P2
Syphon Mind (a sorcery) on the stack while P1 is the active player in P1's
turn-1 precombat main, and declares ``costs_paid`` although P2 controls no mana
source. Under CR 307.1 a sorcery can be cast only during its controller's own
main phase while the stack is empty, and no flash grant exists in the record;
under CR 305.2 / 601.2g-h the declared paid cost needs declared mana sources.
The opponent-discard decision the probe exercises (actor P1, omitted handler
``choose_object``) is reachable only after the spell resolves, which requires
it to have been legally cast first. No full natural-play reachability is
claimed: the other injected permanents pre-exist and are out of scope.

The erratum corrects only the declared state needed for that consistency:

* ``temporal_state``: turn 2, active player P2, precombat main, priority P2
  (P2's own first main phase, immediately after P1's turn 1);
* ``stack_state[0]`` additionally declares the cast origin ``from_zone: hand``
  (CR 601.2a: to cast a spell is to put it on the stack from where it is; the
  cast here is from P2's hand);
* ``semantic_objects`` gains four tapped Swamps controlled by P2, the mana
  spent on {3}{B} (CR 305.2, 601.2g-h);
* ``deck_state`` declares complete empty checkpoint hands (``hand_count`` 0)
  for P3 and P4, the APNAP precondition under CR 101.4 that makes P1 the first
  actor that must discard (P1's two declared hand cards are kept byte for
  byte).

Every other record field is unchanged: the obligation semantics
(``negative_fallback_probe``, the omitted handler, the expected and forbidden
events, the expected decision actor P1) are kept byte for byte, and the
obligation digest is asserted equal to the base record's. No untapped, life or
prior-draw field depends on turn 1 / P1 active, so none is touched.

The record is NOT runnable on the current bridge: the resume route accepts only
the qualified turn-1 checkpoints (``XmageNativeStateRestoration.
isSupportedTemporalPoint``), so this turn-2 checkpoint is refused with
``UNSUPPORTED_TEMPORAL_POINT``. That is recorded as an explicit
``known_runtime_blocker`` in the errata-ledger entry; no runtime credit is
claimed.

Everything else in 1.0.23 is carried over byte for byte: every record
successor, the bounded-secondary PLAYER_COUNT_6P section, the change
accounting (which gains exactly this one corrected fixture), the evidence
policy, the rules authority block and the schema shape. Only the contract id,
the effective materialization version, the predecessor binding, the schema note,
the new record patch and the accounting entry change, plus the authority
pointer, the errata ledger entry and the schema copy.

Idempotent: always regenerated from the 1.0.23 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_23.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_24.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.23-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_24.json"
DECISIONS = (
    "#441 Coordinator erratum 2026-10-08 (contract 1.0.24): correct the "
    "NEGATIVE_PARENT_CLASS_FALLBACK temporal/stack declaration so its declared "
    "state is reachable under CR 307.1"
)
FIXTURE = "NEGATIVE_PARENT_CLASS_FALLBACK"
NEW_VERSION = "1.0.24"
NEW_MINOR = "24"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_CAST_TIMING_AND_COST_CONSISTENCY"
KNOWN_RUNTIME_BLOCKER = (
    "NOT_RUNNABLE_ON_CURRENT_BRIDGE: the native resume route accepts only the "
    "qualified turn-1 checkpoints (XmageNativeStateRestoration.isSupportedTemporalPoint), "
    "so this corrected turn-2 checkpoint is refused with UNSUPPORTED_TEMPORAL_POINT. "
    "Bridge code is out of scope; no runtime credit is claimed or possible until the "
    "bridge admits the checkpoint"
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": (
        "fixture-contract successor rule: #441 NEGATIVE_PARENT_CLASS_FALLBACK "
        "cast timing and cost consistency erratum"
    ),
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_FROM_THE_1_0_23_SUCCESSOR_OBLIGATION_KEYS_UNTOUCHED",
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

old = base[FIXTURE]

# --- the predecessor's inconsistent declaration ------------------------------ #

assert old["temporal_state"] == {
    "active_player": "P1",
    "extra_turn_queue": [],
    "phase": "precombat_main",
    "priority_player": "P1",
    "step": "main",
    "turn_number": 1,
}, old["temporal_state"]
assert old["stack_state"] == [
    {
        "cast_complete": True,
        "controller": "P2",
        "costs_paid": True,
        "modes": [],
        "source_semantic_id": "obj:negative-syphon",
        "targets": [],
    }
], old["stack_state"]
assert old["native_procedure"][1]["details"]["expected_decision_actor"] == "P1"
# The predecessor declares no deck state and no P2 mana source (only the
# injected Grizzly Bears), so its ``costs_paid`` has nothing that could have
# paid {3}{B}, and P3/P4 hold no declared hand. Both preconditions are made
# explicit below.
assert old.get("deck_state") is None
assert [
    obj["card_identity"]
    for obj in old["semantic_objects"]
    if obj.get("zone") == "battlefield" and obj["controller"] == "P2"
] == ["Grizzly Bears"]
assert [
    obj["card_identity"]
    for obj in old["semantic_objects"]
    if obj.get("zone") == "hand" and obj["controller"] == "P1"
] == ["Mountain", "Island"]

# --- the corrected declared state -------------------------------------------- #

corrected_temporal = {
    "active_player": "P2",
    "extra_turn_queue": [],
    "phase": "precombat_main",
    "priority_player": "P2",
    "step": "main",
    "turn_number": 2,
}
corrected_stack = [
    {
        **entry,
        "from_zone": "hand",
    }
    for entry in old["stack_state"]
]
# Four tapped Swamps controlled by P2: the mana spent on Syphon Mind's {3}{B}
# (CR 305.2). Declaring them makes ``costs_paid`` consistent with the declared
# battlefield (CR 601.2g-h). Nothing else about P2's board changes.
swamps = [
    {
        "card_identity": "Swamp",
        "card_lineage_id": f"line:obj:neg-swamp-{index}",
        "controller": "P2",
        "counters": {},
        "face_down": False,
        "owner": "P2",
        "semantic_id": f"obj:neg-swamp-{index}",
        "tapped": True,
        "zone": "battlefield",
    }
    for index in range(1, 5)
]
corrected_objects = [*copy.deepcopy(old["semantic_objects"]), *swamps]
# Complete empty checkpoint hands for P3 and P4: the explicit ``hand_count: 0``
# APNAP precondition (CR 101.4), so P1 is the first actor Syphon Mind asks to
# discard. P1's two declared hand cards above are kept byte for byte.
corrected_deck_state = [
    {
        "player_id": player,
        "checkpoint_hand": {
            "completeness": "COMPLETE",
            "template_card_identity": "Mountain",
            "template_count": 0,
        },
    }
    for player in ("P3", "P4")
]
corrected_scenario_notes = [
    *old["scenario_notes"],
    (
        "Corrected declared state (#441 Coordinator erratum 2026-10-08), scoped to cast "
        "timing and cost consistency: P2 is the active player holding priority in P2's "
        "turn-2 precombat main with Syphon Mind fully cast from hand; P2 controls four "
        "tapped Swamps (the {3}{B} was paid); P3 and P4 hold no cards (complete empty "
        "checkpoint hands). Not runnable on the current bridge: the resume route accepts "
        "only the qualified turn-1 checkpoints, so this turn-2 checkpoint is refused with "
        "UNSUPPORTED_TEMPORAL_POINT; no runtime credit is claimed."
    ),
]
erratum = {
    "actor": None,
    "details": {
        "authority": DECISIONS,
        "comprehensive_rules": "307.1, 305.2, 601.2g-h, 101.4, 117.3c, 601.2a",
        "erratum_class": CORRECTION_CLASS,
        "field_changes": [
            {
                "change": "temporal_state.turn_number 1 -> 2",
                "comprehensive_rules": "307.1",
                "reason": (
                    "a sorcery requires its controller's own main phase; P2's own first "
                    "main phase is turn 2, after P1's turn 1"
                ),
            },
            {
                "change": "temporal_state.active_player P1 -> P2",
                "comprehensive_rules": "307.1",
                "reason": (
                    "the main phase in which a sorcery may be cast is a phase of its "
                    "controller's turn, so the active player must be the caster P2"
                ),
            },
            {
                "change": "temporal_state.priority_player P1 -> P2",
                "comprehensive_rules": "117.3c",
                "reason": (
                    "a player who had priority and cast a spell receives priority again "
                    "after the cast (CR 117.3c); the declared point is that priority, held "
                    "by the caster P2"
                ),
            },
            {
                "change": "stack_state[0].from_zone absent -> hand",
                "comprehensive_rules": "601.2a",
                "reason": (
                    "declares the cast-from zone: to cast a spell is to put it on the "
                    "stack from where it is, and this cast is from P2's hand"
                ),
            },
            {
                "change": "semantic_objects +4 tapped Swamps controlled by P2",
                "comprehensive_rules": "305.2",
                "reason": (
                    "the record declares costs_paid for {3}{B}; the four declared tapped "
                    "Swamps are the mana sources that paid it, making the paid cast "
                    "consistent with the declared battlefield"
                ),
            },
            {
                "change": "stack_state[0].costs_paid now has declared mana sources",
                "comprehensive_rules": "601.2g-h",
                "reason": (
                    "a cost is paid with mana; declaring the tapped Swamps keeps the "
                    "declared paid cast consistent instead of asserting payment out of "
                    "an empty battlefield"
                ),
            },
            {
                "change": (
                    "deck_state absent -> complete empty checkpoint hands for P3 and P4 "
                    "(hand_count 0)"
                ),
                "comprehensive_rules": "101.4",
                "reason": (
                    "Syphon Mind makes each other player discard a card; APNAP order from "
                    "active player P2 is P3, P4, P1, so P1 is the first actor asked to "
                    "discard only if P3 and P4 hold no cards. The complete empty "
                    "checkpoint hands declare that precondition explicitly. P1's two "
                    "declared hand cards are unchanged, so the expected decision actor "
                    "stays P1"
                ),
            },
        ],
        "obligation_changed": False,
        "provider_semantics_used": False,
        "reason": (
            "the 1.0.5/1.0.23 record declares a fully cast P2 Syphon Mind on the stack "
            "while P1 is active in P1's turn-1 precombat main, with costs_paid and no P2 "
            "mana source, and with no declared hand for P3/P4. The erratum is scoped to "
            "cast timing and cost consistency: CR 307.1 permits a sorcery only in its "
            "controller's own main phase with an empty stack and no flash grant exists; "
            "CR 305.2 / 601.2g-h require the declared paid cost to have declared mana "
            "sources; CR 101.4 makes P1 the first discarding actor only when P3 and P4 "
            "hold no cards. The correction moves the declared point to P2's own first "
            "main phase (turn 2) with P2 active and holding priority (CR 117.3c), "
            "declares the cast-from zone hand (CR 601.2a), adds the four tapped Swamps "
            "that paid {3}{B}, and declares complete empty P3/P4 checkpoint hands. No "
            "full natural-play reachability is claimed (other injected permanents "
            "pre-exist and are out of scope)"
        ),
    },
    "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
    "source_object": None,
    "step_id": "erratum-cast-timing-and-cost-consistency-negative_parent_class_fallback",
}
patch = {
    "append_native_procedure": [erratum],
    "authority_overlay": dict(OVERLAY),
    "correction_class": CORRECTION_CLASS,
    "digest_migration": {
        **DIGEST_MIGRATION,
        "reason": (
            "the declared temporal/stack state, the mana sources for the paid cost and "
            "the P3/P4 hand preconditions change; the obligation keys are byte for byte "
            "the predecessor's, so the obligation digest is unchanged and the historical "
            "materialization digest is preserved under historical_digests"
        ),
    },
    "evidence_survival": "REQUALIFICATION_REQUIRED",
    "fixture_id": FIXTURE,
    "knowledge_state_channel_policy": old["knowledge_state"]["channel_policy"],
    "predecessor_invalidity": {
        "predecessor_values": {
            "semantic_objects": copy.deepcopy(old["semantic_objects"]),
            "stack_state": copy.deepcopy(old["stack_state"]),
            "temporal_state": copy.deepcopy(old["temporal_state"]),
        },
        "reason": (
            "cast timing and cost inconsistency: a P2 sorcery fully cast while P1 is "
            "active in P1's turn-1 precombat main violates CR 307.1 (its controller's own "
            "main phase, empty stack; no flash grant exists), and the declared costs_paid "
            "for {3}{B} has no declared P2 mana source under CR 305.2 / 601.2g-h"
        ),
    },
    "predecessor_requested_state_digest": old["requested_state_digest"],
    "replace": {
        "deck_state": corrected_deck_state,
        "scenario_notes": corrected_scenario_notes,
        "semantic_objects": corrected_objects,
        "stack_state": corrected_stack,
        "temporal_state": corrected_temporal,
    },
}
record = copy.deepcopy(old)
record.update(copy.deepcopy(patch["replace"]))
patch["successor_requested_state_digest"] = resolver.requested_state_digest(record)
# The obligation is the base one, key for key: nothing it projects is touched.
assert resolver.obligation_digest(record) == resolver.obligation_digest(old)
assert resolver.obligation_digest(record) == old["obligation_digest"]
assert record["expected_events"] == old["expected_events"]
assert record["terminal_postconditions"] == old["terminal_postconditions"]
assert record["negative_fallback_probe"] == old["negative_fallback_probe"]
assert record["decision_script"] == old["decision_script"] == []
assert record["native_procedure"][:2] == old["native_procedure"]
assert patch["successor_requested_state_digest"] != old["requested_state_digest"]
# The 107-row denominator is untouched by construction.
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert len(denominator) == 107
assert FIXTURE in denominator

# --- assemble the 1.0.24 contract ------------------------------------------- #

predecessor_successors = list(contract["record_successors"])
assert all(p["fixture_id"] != FIXTURE for p in predecessor_successors)
contract["record_successors"] = [*predecessor_successors, patch]
accounting = contract["change_accounting"]
assert FIXTURE not in accounting["changed_fixture_ids"]
accounting["changed_fixture_ids"] = [*accounting["changed_fixture_ids"], FIXTURE]
accounting["per_fixture_correction_class"][FIXTURE] = patch["correction_class"]
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
# Recomputed from the denominator, never hand-edited: this fixture is a 107-row
# denominator row, so one row moves from unchanged to changed; the denominator
# itself stays exactly 107.
accounting["unchanged_provider_denominator_rows"] = sum(
    1 for fixture_id in denominator if fixture_id not in accounting["changed_fixture_ids"]
)
contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.24 carries every "
    "1.0.23 record successor and the bounded-secondary PLAYER_COUNT_6P section byte for "
    "byte, and adds exactly one corrected record: NEGATIVE_PARENT_CLASS_FALLBACK's "
    "declared state is made cast-timing and cost consistent (turn 2, P2 active and "
    "holding priority under CR 117.3c in P2's precombat main, cast-from zone hand, four "
    "tapped P2 Swamps paying {3}{B}, and complete empty P3/P4 checkpoint hands under CR "
    "101.4), with the obligation keys untouched. No full natural-play reachability is "
    "claimed, and the turn-2 checkpoint is not runnable on the current bridge "
    "(UNSUPPORTED_TEMPORAL_POINT). Per #441 Coordinator erratum 2026-10-08."
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_23.json",
    "record_count": len(predecessor_successors),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.23 overlay to the same 1.0.5 historical base and adds exactly one corrected "
        "record, whose obligation keys are unchanged"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.24 ----------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_23_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.23", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.23", NEW_VERSION)
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
if FIXTURE not in full["changed_fixture_ids"]:
    full["changed_fixture_ids"] = [*full["changed_fixture_ids"], FIXTURE]
# The unchanged count is recomputed from the denominator, never hand-edited:
# this fixture is a 107-row denominator row, so correcting it moves one row from
# unchanged to changed while the denominator itself stays exactly 107.
full["unchanged_fixture_count"] = sum(
    1 for fixture_id in denominator if fixture_id not in full["changed_fixture_ids"]
)
assert len(full["changed_fixture_ids"]) == len(set(full["changed_fixture_ids"]))
assert full["denominator_count"] == 107
full["evidence_survival"][FIXTURE] = "REQUALIFICATION_REQUIRED_" + patch["correction_class"]
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- errata ledger entry ------------------------------------------------------ #

lpath = REPO / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
ledger = json.loads(lpath.read_text(encoding="utf-8"))
# Idempotent: a prior run's entry is replaced, never duplicated.
ledger["records"] = [record for record in ledger["records"] if record["fixture_id"] != FIXTURE]
entry = {
    "correction_class": patch["correction_class"],
    "denominator_effect": "NONE",
    "effective_obligation_digest": old["obligation_digest"],
    "effective_requested_state_digest": patch["successor_requested_state_digest"],
    "evidence_survival": "REQUALIFICATION_REQUIRED",
    "field_changes": copy.deepcopy(erratum["details"]["field_changes"]),
    "fixture_id": FIXTURE,
    "known_runtime_blocker": KNOWN_RUNTIME_BLOCKER,
    "notes": (
        "the effective record declared a cast-timing and cost-inconsistent state: a "
        "fully cast P2 sorcery (Syphon Mind) on the stack while P1 was active in P1's "
        "turn-1 precombat main, which CR 307.1 forbids (its controller's own main phase, "
        "empty stack; no flash grant exists), with costs_paid for {3}{B} but no declared "
        "P2 mana source (CR 305.2 / 601.2g-h) and no declared P3/P4 hands (CR 101.4 "
        "APNAP). The erratum is scoped to cast timing and cost consistency and claims no "
        "full natural-play reachability: the temporal/stack declaration, four tapped P2 "
        "Swamps paying the cost, and complete empty P3/P4 checkpoint hands change, while "
        "the negative_fallback_probe obligation, the omitted handler, the expected and "
        "forbidden events and the expected decision actor P1 are byte for byte the "
        "predecessor's, and the obligation digest is unchanged. The 107-row denominator "
        "is untouched"
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
