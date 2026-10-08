"""Generate FULL107 successor contract 1.0.25 from 1.0.24: the NEGATIVE_PARENT_CLASS_FALLBACK turn-1 cleanup-discard reachability erratum.

Coordinator erratum (Lab issue #441, 2026-10-08; parent #255), following the
PR #583 / #604 / #608 precedent (deterministic generator, contract + schema,
authority pointer, errata-ledger entry, manifests via the repository tool).

The 1.0.24 record corrected the cast timing and cost consistency of
NEGATIVE_PARENT_CLASS_FALLBACK, but the corrected turn-2 checkpoint is only
reachable through P1's turn 1. Finding from PR #609 (real engine, open):

* In this four-player game P1 draws on turn 1 (CR 103.8c), so P1 holds eight
  cards when its own cleanup step begins and must discard one card (CR 514.1).
* Which card P1 discards is P1's own choice, so the Lab may never choose it.
  The 1.0.24 record declared neither that decision nor its resulting graveyard
  card, and the resume then reported exactly one undeclared scaffolding card in
  P1's graveyard (``P1|GRAVEYARD|Mountain`` requested 0 / observed 1).

The erratum is scoped to that reachability gap and fixes the two #608 P3 notes:

* ``decision_script`` gains one scripted ``cleanup_discard`` step for P1, in the
  same shape as the WS05-CMD-MULL-2 ``london_bottom`` steps: selector kind
  ``card_identity_multiset``, semantic value one ``Mountain`` (P1's turn-1 hand
  is the scaffolding Mountains);
* ``semantic_objects`` gains exactly one Mountain in P1's graveyard, in the
  record's existing graveyard declaration form (the CARD_29 form);
* the ``+4 tapped Swamps`` field change no longer cites CR 305.2 as support: it
  cites CR 601.2g-h and states that the Swamps are injected; not natural-play
  reachable (305.2). The same correction is applied to the ledger entry.

Every other field of the corrected record is the 1.0.24 one byte for byte: the
obligation semantics (``negative_fallback_probe``, the omitted handler, the
expected and forbidden events, the expected decision actor P1) are kept, the
obligation digest is unchanged, and the requested-state digest is recomputed
from the declared graveyard object. The 1.0.24 patch is superseded in place and
kept as lineage (``superseded_successor_patch``), exactly like the 1.0.21
RNG_RULES_TAPE supersession.

No runtime credit is claimed: the pinned bridge still refuses the turn-2
checkpoint with ``UNSUPPORTED_TEMPORAL_POINT`` until the turn-2 precombat-main
route (PR #609) lands; the erratum removes the sole mismatch that route found.

Everything else in 1.0.24 is carried over byte for byte: every other record
successor, the bounded-secondary PLAYER_COUNT_6P section, the change accounting
(which keeps this one fixture changed and only updates its correction class),
the evidence policy, the rules authority block and the schema shape. Only the
contract id, the effective materialization version, the predecessor binding, the
schema note, the superseded patch and the accounting entry change, plus the
authority pointer, the errata-ledger entry and the schema copy.

Idempotent: always regenerated from the 1.0.24 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_24.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_25.json"
PRIOR_CONTRACT = "commander-lab.full107/1.0.24-successor"
SUCCESSOR_PATH = "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_25.json"
DECISIONS = (
    "#441 Coordinator erratum 2026-10-08 (contract 1.0.25): declare the scripted "
    "P1 turn-1 cleanup discard (CR 103.8c/514.1) and its graveyard card so the "
    "corrected NEGATIVE_PARENT_CLASS_FALLBACK state is reachable through turn 1"
)
FIXTURE = "NEGATIVE_PARENT_CLASS_FALLBACK"
PRIOR_CLASS = "FIXTURE_DEFECT_CORRECTION_CAST_TIMING_AND_COST_CONSISTENCY"
NEW_VERSION = "1.0.25"
NEW_MINOR = "25"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_TURN1_CLEANUP_DISCARD_REACHABILITY"
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
    "NOT_RUNNABLE_ON_CURRENT_BRIDGE: the native resume route accepts only the "
    "qualified turn-1 checkpoints (XmageNativeStateRestoration.isSupportedTemporalPoint), "
    "so the corrected turn-2 checkpoint is refused with UNSUPPORTED_TEMPORAL_POINT until the "
    "turn-2 precombat-main route (PR #609) lands. PR #609's real-engine finding was the sole "
    "mismatch this erratum removes: P1 draws on turn 1 (CR 103.8c) and the forced cleanup "
    "discard (CR 514.1) left one undeclared P1 graveyard Mountain. No runtime credit is "
    "claimed by the materialization"
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": (
        "fixture-contract successor rule: #441 NEGATIVE_PARENT_CLASS_FALLBACK "
        "turn-1 cleanup-discard reachability erratum"
    ),
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_FROM_THE_1_0_24_SUCCESSOR_OBLIGATION_KEYS_UNTOUCHED",
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
assert old["temporal_state"]["turn_number"] == 1
assert old["native_procedure"][1]["details"]["expected_decision_actor"] == "P1"

# --- the 1.0.24 declared state, recomputed from its own patch ----------------- #

prior_replace = copy.deepcopy(prior["replace"])
assert prior_replace["temporal_state"] == {
    "active_player": "P2",
    "extra_turn_queue": [],
    "phase": "precombat_main",
    "priority_player": "P2",
    "step": "main",
    "turn_number": 2,
}
prior_objects = prior_replace["semantic_objects"]
assert [o["semantic_id"] for o in prior_objects if o["card_identity"] == "Swamp"] == [
    "obj:neg-swamp-1",
    "obj:neg-swamp-2",
    "obj:neg-swamp-3",
    "obj:neg-swamp-4",
]
assert not [o for o in prior_objects if o["zone"] == "graveyard"]
assert prior_replace["deck_state"] == [
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

# --- the 1.0.25 additions ----------------------------------------------------- #

# The scripted forced discard, in the london_bottom/WS05-CMD-MULL-2 shape: one
# card-identity multiset entry over the scaffolding hand's card identity. The Lab
# never picks the card.
cleanup_step = {
    "actor": "P1",
    "causal_step_id": "cleanup-r1-P1",
    "decision_family": "cleanup_discard",
    "forbidden_fallbacks": list(FORBIDDEN),
    "notes": (
        "CR 514.1: P1 draws on turn 1 in this four-player game (CR 103.8c), so it holds "
        "eight cards when its cleanup step begins and must discard one down to seven; "
        "which Mountain is discarded is P1's own choice, so it is scripted here and the "
        "Lab never picks"
    ),
    "selection": {
        "matches_only_provider_offered_legal_options": True,
        "on_multiple_match": "FAIL_CLOSED",
        "on_zero_match": "FAIL_CLOSED",
        "selector_kind": "card_identity_multiset",
        "semantic_value": {"Mountain": 1},
    },
}
# The declared graveyard card: one Mountain in P1's graveyard, in the record's
# existing graveyard declaration form (the CARD_29 form).
discarded_mountain = {
    "card_identity": "Mountain",
    "card_lineage_id": "line:obj:neg-graveyard-mountain",
    "controller": "P1",
    "counters": {},
    "face_down": False,
    "owner": "P1",
    "semantic_id": "obj:neg-graveyard-mountain",
    "tapped": False,
    "zone": "graveyard",
}
corrected_objects = [*copy.deepcopy(prior_objects), discarded_mountain]
corrected_scenario_notes = [
    *copy.deepcopy(prior_replace["scenario_notes"]),
    (
        "Reachability erratum (#441 Coordinator erratum 2026-10-08, contract 1.0.25): the "
        "corrected turn-2 checkpoint is reached through P1's turn 1. In this four-player "
        "game P1 draws on that turn (CR 103.8c) and must discard one card at its cleanup "
        "(CR 514.1). The discard is P1's own choice, so it is scripted as one Mountain (a "
        "scaffolding hand card); exactly that one Mountain is declared in P1's graveyard at "
        "the checkpoint. The obligation is untouched. The turn-2 checkpoint remains refused "
        "by the pinned bridge (UNSUPPORTED_TEMPORAL_POINT) until the turn-2 route lands; no "
        "runtime credit is claimed."
    ),
]
merged_replace = {
    **prior_replace,
    "decision_script": [cleanup_step],
    "scenario_notes": corrected_scenario_notes,
    "semantic_objects": corrected_objects,
}
record = copy.deepcopy(old)
for key, value in merged_replace.items():
    record[key] = copy.deepcopy(value)
record["knowledge_state"]["channel_policy"] = prior["knowledge_state_channel_policy"]

# --- the corrected errata field changes --------------------------------------- #

prior_changes = copy.deepcopy(prior["append_native_procedure"][0]["details"]["field_changes"])
swamps_change = [
    change
    for change in prior_changes
    if change["change"] == "semantic_objects +4 tapped Swamps controlled by P2"
]
assert len(swamps_change) == 1
# #608 P3: CR 305.2 governs playing a land, not paying a cost, so it is not the
# support for the declared mana; the source is CR 601.2g-h, and the Swamps are
# explicitly injected scaffolding rather than natural-play reachable.
swamps_change[0]["comprehensive_rules"] = "601.2g-h"
swamps_change[0]["reason"] = (
    "the record declares costs_paid for {3}{B}; the four declared tapped Swamps are the "
    "mana sources that paid it, making the paid cast consistent with the declared "
    "battlefield under CR 601.2g-h. They are injected; not natural-play reachable (305.2). "
    "No natural-play path is claimed"
)
new_changes = [
    {
        "change": "decision_script absent -> one scripted cleanup_discard for P1 (one Mountain)",
        "comprehensive_rules": "514.1, 103.8c",
        "reason": (
            "the corrected turn-2 checkpoint is only reachable through P1's turn 1. In this "
            "four-player game the first turn's player draws a card (CR 103.8c), so P1 holds "
            "eight cards when its cleanup step begins and must discard down to seven (CR "
            "514.1). Which card is discarded is P1's own choice, so the Lab may not choose "
            "it: the choice is scripted as a one-card card_identity_multiset of the "
            "scaffolding hand's Mountain"
        ),
    },
    {
        "change": "semantic_objects +1 Mountain in P1's graveyard",
        "comprehensive_rules": "514.1, 103.8c",
        "reason": (
            "the scripted forced discard is part of the declared history at the checkpoint: "
            "the card P1 discarded at its turn-1 cleanup is in P1's graveyard. Without the "
            "declaration the engine's checkpoint readback reported exactly one undeclared "
            "P1|GRAVEYARD|Mountain (requested 0 / observed 1), the sole mismatch of the "
            "corrected state, so the requested state declares exactly that one Mountain"
        ),
    },
]
field_changes = [*prior_changes, *new_changes]

erratum = {
    "actor": None,
    "details": {
        "authority": DECISIONS,
        "comprehensive_rules": "307.1, 601.2g-h, 101.4, 117.3c, 601.2a, 514.1, 103.8c",
        "erratum_class": CORRECTION_CLASS,
        "field_changes": field_changes,
        "obligation_changed": False,
        "provider_semantics_used": False,
        "reason": (
            "the 1.0.24 corrected state is reachable only through P1's turn 1. In this "
            "four-player game P1 draws on turn 1 (CR 103.8c) and holds eight cards at its "
            "cleanup, where CR 514.1 forces a discard. The 1.0.24 record declared neither "
            "the forced discard decision nor its resulting graveyard card, so the real "
            "engine reported one undeclared scaffolding Mountain in P1's graveyard and the "
            "checkpoint could not match. This erratum scripts the discard as one Mountain "
            "(the Lab never picks the card) and declares exactly that one Mountain in P1's "
            "graveyard. It also supersedes the 1.0.24 erratum step and fixes its #608 P3 "
            "citation: the four tapped Swamps are supported by CR 601.2g-h, not CR 305.2, "
            "and are injected, not natural-play reachable (305.2). No obligation key "
            "changes and no runtime credit is claimed"
        ),
        "supersedes_erratum_step": prior["append_native_procedure"][0]["step_id"],
    },
    "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
    "source_object": None,
    "step_id": "erratum-turn1-cleanup-discard-negative_parent_class_fallback",
}
patch = {
    "append_native_procedure": [erratum],
    "authority_overlay": dict(OVERLAY),
    "correction_class": CORRECTION_CLASS,
    "digest_migration": {
        **DIGEST_MIGRATION,
        "reason": (
            "the declared decision script and the declared graveyard object change; the "
            "obligation keys are byte for byte the 1.0.24 predecessor's, so the obligation "
            "digest is unchanged and the historical materialization digest is preserved "
            "under historical_digests"
        ),
    },
    "evidence_survival": "REQUALIFICATION_REQUIRED",
    "fixture_id": FIXTURE,
    "knowledge_state_channel_policy": prior["knowledge_state_channel_policy"],
    "predecessor_invalidity": {
        "predecessor_values": {
            "decision_script": copy.deepcopy(old["decision_script"]),
            "semantic_objects": copy.deepcopy(prior_objects),
        },
        "reason": (
            "reachability gap in the 1.0.24 corrected state: the turn-2 checkpoint is only "
            "reachable through P1's turn 1, where P1 draws (CR 103.8c) and the cleanup "
            "forces one discard (CR 514.1). The record declared neither the forced-discard "
            "decision nor its graveyard card, so the engine's checkpoint readback reported "
            "one undeclared P1|GRAVEYARD|Mountain (requested 0 / observed 1)"
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
            "its replace is kept and extended; its erratum step is preserved here as history "
            "and is not active procedure. The successor erratum restates its corrections "
            "with the #608 P3 citation fix"
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
# The requested-state projection gained exactly the declared graveyard Mountain,
# so the recomputed digest equals the digest of the 1.0.24 fields plus that one
# object; the digest is recomputed from the record, never hand-edited.
assert resolver.requested_state_digest(record) == patch["successor_requested_state_digest"]
# The 107-row denominator is untouched by construction.
denominator = json.loads(
    (REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json").read_text()
)["fixture_ids"]
assert len(denominator) == 107
assert FIXTURE in denominator

# --- assemble the 1.0.25 contract --------------------------------------------- #

predecessor_successors = list(contract["record_successors"])
assert sum(p["fixture_id"] == FIXTURE for p in predecessor_successors) == 1
assert predecessor_successors[-1]["fixture_id"] == FIXTURE
# The superseding patch takes its predecessor's place: every other overlay keeps
# its order and byte-identical value.
contract["record_successors"] = [*predecessor_successors[:-1], patch]
accounting = contract["change_accounting"]
assert FIXTURE in accounting["changed_fixture_ids"]
assert accounting["per_fixture_correction_class"][FIXTURE] == PRIOR_CLASS
accounting["per_fixture_correction_class"][FIXTURE] = CORRECTION_CLASS
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
# Recomputed from the denominator, never hand-edited: this fixture was already a
# changed denominator row, so the unchanged count stays exactly the same.
accounting["unchanged_provider_denominator_rows"] = sum(
    1 for fixture_id in denominator if fixture_id not in accounting["changed_fixture_ids"]
)
contract["contract_id"] = f"commander-lab.full107/{NEW_VERSION}-successor"
contract["effective_materialization_version"] = (
    f"commander-lab.semantic-fixture-materialization/{NEW_VERSION}-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.25 carries every "
    "1.0.24 record successor and the bounded-secondary PLAYER_COUNT_6P section byte for "
    "byte, and supersedes in place exactly one record: NEGATIVE_PARENT_CLASS_FALLBACK's "
    "1.0.24 patch is extended with the scripted P1 turn-1 cleanup discard (CR 103.8c/514.1, "
    "decision family cleanup_discard, selector card_identity_multiset of one Mountain) and "
    "with exactly that one Mountain declared in P1's graveyard, so the corrected turn-2 "
    "state is reachable through turn 1. The obligation keys are untouched and no runtime "
    "credit is claimed. The 1.0.24 erratum step is kept as lineage under "
    "superseded_successor_patch, with its #608 P3 citation corrected in the active step. "
    "Per #441 Coordinator erratum 2026-10-08."
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_24.json",
    "record_count": len(predecessor_successors),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every "
        "1.0.24 overlay to the same 1.0.5 historical base, supersedes in place exactly one "
        "corrected record (NEGATIVE_PARENT_CLASS_FALLBACK) and keeps the 1.0.24 patch as "
        "lineage, with the obligation keys unchanged"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# --- schema 1.0.25 ------------------------------------------------------------- #

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_24_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.24", NEW_VERSION)
schema["$id"] = schema["$id"].replace("1.0.24", NEW_VERSION)
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
# The fixture is already a changed denominator row from 1.0.24; superseding its
# patch in place does not add a second entry (tolerant of a rerun either side of
# the 1.0.24 pointer, which the generator overrides).
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
# Idempotent: a prior run's entry is replaced, never duplicated.
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
        "the 1.0.24 corrected state is reachable only through P1's turn 1. In this "
        "four-player game P1 draws on turn 1 (CR 103.8c), so it holds eight cards at its "
        "cleanup and CR 514.1 forces a discard. The 1.0.24 record declared neither the "
        "forced discard decision nor its resulting graveyard card; the real engine then "
        "reported one undeclared scaffolding Mountain in P1's graveyard (the sole mismatch "
        "of the corrected state). This erratum scripts the discard as one Mountain in the "
        "existing london_bottom card-selection shape (the Lab never picks the card) and "
        "declares exactly that one Mountain in P1's graveyard in the record's existing "
        "graveyard form. The obligation keys are byte for byte the predecessor's and the "
        "obligation digest is unchanged; the requested-state digest is recomputed from the "
        "declared graveyard object. The superseded 1.0.24 patch is kept as lineage. The "
        "#608 P3 note is fixed: the four tapped Swamps are supported by CR 601.2g-h, not "
        "CR 305.2, and are injected, not natural-play reachable (305.2). The 107-row "
        "denominator is untouched and no runtime credit is claimed"
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
