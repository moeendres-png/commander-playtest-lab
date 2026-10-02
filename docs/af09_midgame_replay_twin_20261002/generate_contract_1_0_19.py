"""Generate FULL107 successor contract 1.0.19 from 1.0.18: the REPLAY/RNG lossless errata.

The five replay/RNG records name seven of P1's library cards but declare no
complete library, so under SLOT-04 L7 their partial library request fails closed
on every candidate. Each gets the LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04
CARD_12 and CARD_29 received: complete checkpoint hands (P1: the named Burn Down
the House plus the opening seven and the turn-1 draw; the others: the opening
seven) and P1's complete library (the seven named cards on top in record order,
then the 91 remaining template cards). The obligation keys are untouched.

Idempotent: always regenerated from the 1.0.18 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_18.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_19.json"
ROWS = [
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_STATE_HASHES",
    "RNG_RULES_TAPE",
]

raw = src.read_bytes()
contract = json.loads(raw)
(template,) = [p for p in contract["record_successors"] if p["fixture_id"] == "CARD_12"]
authority = json.loads((REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json").read_text())
base = {
    r["fixture_id"]: r
    for r in json.loads(
        (REPO / authority["full107"]["historical_base_materialization"]).read_text()
    )["records"]
}
assert not any(p["fixture_id"] in ROWS for p in contract["record_successors"])

for fixture in ROWS:
    old = base[fixture]
    assert old.get("deck_state") is None, fixture
    library = [o for o in old["semantic_objects"] if o["owner"] == "P1" and o["zone"] == "library"]
    assert [o["semantic_id"] for o in library] == [f"obj:replay-lib-{i}" for i in range(7)], fixture
    hand = [
        o["semantic_id"]
        for o in old["semantic_objects"]
        if o["owner"] == "P1" and o["zone"] == "hand"
    ]
    assert hand == ["obj:replay-burn"], (fixture, hand)
    deck_state = copy.deepcopy(template["replace"]["deck_state"])
    (p1,) = [d for d in deck_state if d["player_id"] == "P1"]
    p1["checkpoint_hand"] = {
        "completeness": "COMPLETE",
        "template_card_identity": "Mountain",
        "template_count": 8,
    }
    p1["checkpoint_library"] = {
        "completeness": "COMPLETE_TOP_TO_BOTTOM",
        "runs": [{"semantic_id": o["semantic_id"]} for o in library]
        + [{"card_identity": "Mountain", "count": 91}],
    }
    for deck in deck_state:
        if deck["player_id"] != "P1":
            assert "checkpoint_library" not in deck
            assert deck["checkpoint_hand"]["template_count"] == 7
    details = {
        "authority": template["append_native_procedure"][0]["details"]["authority"],
        "complete_checkpoint_hands": {
            "P1": "obj:replay-burn plus 8 template cards",
            "P2": "7 template cards",
            "P3": "7 template cards",
            "P4": "7 template cards",
        },
        "complete_checkpoint_libraries": {
            "P1": ", ".join(o["semantic_id"] for o in library)
            + " on top in that order, then the 91 remaining template cards"
        },
        "erratum_class": "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04",
        "first_turn_draw": template["append_native_procedure"][0]["details"]["first_turn_draw"],
        "obligation_changed": False,
        "provider_semantics_used": False,
        "rules_rng_procedure": (
            "the record's native step 'rules-shuffle' (NATIVE_RULES_RNG_SHUFFLE_DECLARED_LIBRARY) "
            "names a shuffle of the declared library after the cast resolves, but nothing in the "
            "scenario causes one, and a shuffle ordered by the harness would be state the Rules "
            "Core never caused. The step is realized by the engine's own start-of-game shuffle of "
            "P1's library (CR 103.2): the record's NATIVE_LIBRARY_SHUFFLE channel and its required "
            "event rules_rng:library_shuffle:P1. Its result is taped as the permutation digest "
            "the engine reports (get_rules_rng_tape), which the clean replay must reproduce and "
            "a different seed must change. The complete library declared here is the library AT "
            "the checkpoint, applied through the native game-load seam after that shuffle"
        ),
        "native_procedure_step_realized_by": {
            "rules-shuffle": "ENGINE_START_OF_GAME_LIBRARY_SHUFFLE_CR_103_2"
        },
        "scaffolding_template": template["append_native_procedure"][0]["details"][
            "scaffolding_template"
        ],
    }
    patch = {
        "append_native_procedure": [
            {
                "actor": None,
                "details": details,
                "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
                "source_object": None,
                "step_id": f"erratum-lossless-{fixture.lower()}",
            }
        ],
        "authority_overlay": copy.deepcopy(template["authority_overlay"]),
        "correction_class": "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04",
        "digest_migration": {
            **copy.deepcopy(template["digest_migration"]),
            "reason": (
                "Only deck_state changes (complete checkpoint hands and P1's complete library), "
                "so the requested-state and materialization digests change; the obligation keys "
                "are untouched, so the recomputed obligation digest equals the predecessor's"
            ),
        },
        "evidence_survival": "REQUALIFICATION_REQUIRED",
        "fixture_id": fixture,
        "knowledge_state_channel_policy": template["knowledge_state_channel_policy"],
        "predecessor_invalidity": {
            "predecessor_values": {"deck_state": None},
            "reason": (
                "the record names seven of P1's library cards but declares no complete library "
                "or hand; under SLOT-04 L7 a partial library request fails closed on every "
                "candidate (UNSUPPORTED_ZONE on the XMage midgame lane)"
            ),
        },
        "predecessor_requested_state_digest": old["requested_state_digest"],
        "replace": {"deck_state": deck_state},
    }
    record = copy.deepcopy(old)
    record["deck_state"] = copy.deepcopy(deck_state)
    patch["successor_requested_state_digest"] = resolver.requested_state_digest(record)
    assert resolver.obligation_digest(record) == old["obligation_digest"]
    contract["record_successors"].append(patch)

accounting = contract["change_accounting"]
for fixture in ROWS:
    accounting["changed_fixture_ids"].append(fixture)
    accounting["per_fixture_correction_class"][fixture] = (
        "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04"
    )
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
accounting["unchanged_provider_denominator_rows"] = accounting[
    "unchanged_provider_denominator_rows"
] - len(ROWS)
contract["contract_id"] = "commander-lab.full107/1.0.19-successor"
contract["effective_materialization_version"] = (
    "commander-lab.semantic-fixture-materialization/1.0.19-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.19 adds the SLOT-04 "
    "lossless library errata of the five replay/RNG rows (REPLAY_CLEAN_PROCESS, "
    "REPLAY_DECISION_TAPE, REPLAY_EVENT_TAPE, REPLAY_STATE_HASHES, RNG_RULES_TAPE) while "
    "preserving every 1.0.18 overlay byte-semantically"
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_18.json",
    "record_count": len(json.loads(raw)["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every current "
        "overlay to the same 1.0.5 historical base and adds the replay/RNG lossless errata"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_18_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.18", "1.0.19")
schema["$id"] = schema["$id"].replace("1.0.18", "1.0.19")
enum = schema["$defs"]["record"]["properties"]["materialization_version"]["enum"]
enum.append("commander-lab.semantic-fixture-materialization/1.0.19-successor")
schema["properties"]["contract_id"]["const"] = "commander-lab.full107/1.0.19-successor"
schema["properties"]["schema_version"]["const"] = (
    "commander-lab.semantic-fixture-materialization/1.0.19-successor"
)
indent = 2 if schema_text.startswith('{\n  "') else 1
(PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_19_SUCCESSOR.json").write_text(
    json.dumps(schema, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
)

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = (
    "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_19.json"
)
full["effective_materialization_schema"] = (
    "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_19_SUCCESSOR.json"
)
for fixture in ROWS:
    if fixture not in full["changed_fixture_ids"]:
        full["changed_fixture_ids"].append(fixture)
        full["unchanged_fixture_count"] -= 1
    full["evidence_survival"][fixture] = "REQUALIFICATION_REQUIRED_LOSSLESS_LIBRARY_ERRATUM_SLOT04"
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", dst.name, "records", len(contract["record_successors"]))
