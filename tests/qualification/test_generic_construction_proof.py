"""Generic-lane construction proof (#441, Owner decision (c)).

The provider's normalized constructed state must equal the record's requested
state field by field. Each control below changes exactly one fact and must stop
the proof (wrong deck card, commander, owner, life, zone content, seed, starting
seat, capture point, cast count, entry mode); a provider that emits nothing gives
no proof at all, which keeps the decision (a) UNKNOWN.

The state is an orchestration channel: hidden zones arrive only as digests under
the launch's key, so a missing, short or foreign key never establishes equality.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import (
    bridge_launcher,
    full107,
    game_driver,
    generic_construction,
)
from commander_lab.qualification.current_boundary.game_driver import (
    CommandedGameResult,
    DecisionTapeEntry,
)
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)
from commander_lab.qualification.current_boundary.receipts import classify_seed_binding

ROGRAKH = "Rograkh, Son of Rohgahh"
KEY = bytes(range(32))


def _deck_digest(seat: str, counts: dict[str, int], key: bytes = KEY) -> str:
    return generic_construction.zone_digest(key, seat, "library_and_hand", counts)


@pytest.fixture(scope="module")
def record() -> dict:
    return load_effective_materialization().record("PLAYER_COUNT_4P")


def _state(players: int = 4) -> dict:
    return {
        "schema": generic_construction.SCHEMA,
        "observation_scope": "orchestration_keyed_digests",
        # As XMage emits it at the first mulligan decision (local real-producer
        # run): no turn has begun, its native counter already names turn 1.
        "lifecycle": "started",
        "turn_number": 1,
        "phase": None,
        "active_player": None,
        "priority_player": None,
        "stack_size": 0,
        # Native rules state (schema /4), as the engine reads it back.
        "rules_state": {
            "combat_groups": 0,
            "combat_attackers": 0,
            "extra_turns": 0,
            "pending_triggers": 0,
            "continuous_effects": 0,
        },
        "players": [
            {
                "player_id": f"P{seat}",
                "seat": seat,
                "life": 40,
                "poison": 0,
                "lost": False,
                "left": False,
                "library_size": 92,
                "hand_size": 7,
                "library_and_hand_digest": _deck_digest(f"P{seat}", {"Mountain": 99}),
                "graveyard_size": 0,
                "exile_size": 0,
                "battlefield_size": 0,
                "library_shuffles": 1,
                "knowledge": {"visible_hidden_cards": 0},
                "commander_damage_taken": 0,
                "commanders": [
                    {
                        "card_identity": ROGRAKH,
                        "owner": f"P{seat}",
                        "zone": "command",
                        "prior_command_zone_cast_count": 0,
                        # Native attributes (schema /3), as the engine emits them.
                        "controller": f"P{seat}",
                        "counters": {},
                        "face_down": False,
                        "tapped": False,
                        "attachments": 0,
                    }
                ],
            }
            for seat in range(1, players + 1)
        ],
    }


def _proof(record, state, **overrides):
    kwargs = {
        "acknowledged_seed": 424242,
        "first_priority_seat": "p1",
        "capture": generic_construction.CAPTURE_POINT,
        "orchestration_key": KEY,
    }
    kwargs.update(overrides)
    return generic_construction.compare(record, state, **kwargs)


def test_recorded_deck_digests_are_named_for_what_they_are(record) -> None:
    # Sealed epochs carry these documents, and the broad secret scan (gitleaks
    # generic-api-key) reads a 64-hex value under a field name containing "key"
    # as a credential. The values are HMAC-SHA-256 digests, never the key.
    proof = _proof(record, _state())
    check = next(c for c in proof.checks if c.field == "deck_state.P4.main_deck")
    document = check.to_document()
    assert set(document["observed"]) == {"hmac_sha256"}
    assert set(document["requested"]) == {"card_counts", "hmac_sha256"}
    assert document["observed"]["hmac_sha256"] == document["requested"]["hmac_sha256"]


def test_the_requested_natural_game_start_is_established(record) -> None:
    proof = _proof(record, _state())
    assert proof.verdict == generic_construction.EQUAL, proof.reason()
    assert proof.established
    assert full107.construction_credit_gap(record, proof) is None
    fields = {check.field for check in proof.checks}
    for required in (
        "players.P1.life",
        "deck_state.P4.main_deck",
        "commander_state.P2.commanders",
        "semantic_objects.obj:P3-commander",
        "temporal_state.active_player",
        "rules_randomness.rules_seed",
        "stack_state",
        "knowledge_state.P1",
        "knowledge_state.channel_policy",
        "rules_state.combat_groups",
        "rules_state.extra_turns",
        "rules_state.pending_triggers",
        "rules_state.continuous_effects",
        "commander_state.commander_damage_matrix.P3",
    ):
        assert required in fields, required


def _mutate(path: list, value) -> dict:
    state = _state()
    node = state
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return state


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        (
            (
                ["players", 1, "library_and_hand_digest"],
                _deck_digest("P2", {"Mountain": 98, "Lightning Bolt": 1}),
            ),
            "deck_state.P2.main_deck",
        ),
        (
            (["players", 1, "library_and_hand_digest"], _deck_digest("P1", {"Mountain": 99})),
            "deck_state.P2.main_deck",
        ),
        ((["players", 2, "life"], 20), "players.P3.life"),
        ((["players", 0, "poison"], 1), "players.P1.poison"),
        ((["players", 3, "battlefield_size"], 1), "zones.P4.battlefield"),
        ((["players", 0, "graveyard_size"], 1), "zones.P1.graveyard"),
        ((["players", 2, "exile_size"], None), "zones.P3.exile"),
        (
            (["players", 1, "commanders", 0, "card_identity"], "Isamaru, Hound of Konda"),
            "commander_state.P2.commanders",
        ),
        (
            (["players", 2, "commanders", 0, "prior_command_zone_cast_count"], 1),
            "commander_state.P3.commanders",
        ),
        ((["players", 0, "commanders", 0, "zone"], "battlefield"), "commander_state.P1.commanders"),
        ((["players", 1, "hand_size"], 6), "deck_state.P2.opening_hand_size"),
        ((["stack_size"], 1), "stack_state"),
        # Codex P1 (#530): a library the Rules RNG never shuffled.
        ((["players", 2, "library_shuffles"], 0), "rules_randomness.channel.library_shuffle:P3"),
        # Codex P1 (#530): the commander's native owner is compared.
        ((["players", 0, "commanders", 0, "owner"], "P4"), "commander_state.P1.commanders"),
        # Codex P1 (#530, second round): each native object attribute is the
        # engine's own value, compared with the record's semantic object.
        (
            (["players", 0, "commanders", 0, "controller"], "P2"),
            "semantic_objects.obj:P1-commander",
        ),
        ((["players", 1, "commanders", 0, "tapped"], True), "semantic_objects.obj:P2-commander"),
        ((["players", 2, "commanders", 0, "face_down"], True), "semantic_objects.obj:P3-commander"),
        (
            (["players", 3, "commanders", 0, "counters"], {"charge": 1}),
            "semantic_objects.obj:P4-commander",
        ),
        ((["players", 0, "commanders", 0, "attachments"], 1), "semantic_objects.obj:P1-commander"),
        (
            (["players", 0, "commanders", 0, "controller"], None),
            "semantic_objects.obj:P1-commander",
        ),
        # Codex P1 (#530): the emitted temporal fields decide the point.
        ((["phase"], "ending"), "temporal_state.phase"),
        ((["turn_number"], 999), "temporal_state.turn_number"),
        ((["active_player"], "P1"), "temporal_state.phase"),
        ((["priority_player"], "P2"), "temporal_state.phase"),
        # Codex P1 (#530, third round): every must-be-empty projection is the
        # engine's own readback, never inferred from the request.
        ((["rules_state", "combat_groups"], 1), "rules_state.combat_groups"),
        ((["rules_state", "combat_attackers"], 2), "rules_state.combat_attackers"),
        ((["rules_state", "extra_turns"], 1), "rules_state.extra_turns"),
        ((["rules_state", "pending_triggers"], 1), "rules_state.pending_triggers"),
        ((["rules_state", "continuous_effects"], 3), "rules_state.continuous_effects"),
        ((["players", 1, "knowledge", "visible_hidden_cards"], 1), "knowledge_state.P2"),
        (
            (["players", 2, "commander_damage_taken"], 7),
            "commander_state.commander_damage_matrix.P3",
        ),
    ],
)
def test_one_changed_fact_is_a_named_mismatch(record, mutation, field) -> None:
    path, value = mutation
    proof = _proof(record, _mutate(path, value))
    assert proof.verdict == generic_construction.MISMATCH
    assert field in {check.field for check in proof.failures()}, proof.reason()
    gap = full107.construction_credit_gap(record, proof)
    assert gap is not None and field in gap


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"acknowledged_seed": None}, "rules_randomness.rules_seed"),
        ({"acknowledged_seed": 7}, "rules_randomness.rules_seed"),
        ({"first_priority_seat": "p2"}, "temporal_state.active_player"),
        ({"capture": "after_start_game"}, "temporal_state.phase"),
        ({"orchestration_key": bytes(reversed(range(32)))}, "deck_state.P1.main_deck"),
    ],
)
def test_run_facts_are_checked_too(record, overrides, field) -> None:
    proof = _proof(record, _state(), **overrides)
    assert proof.verdict == generic_construction.MISMATCH
    assert field in {check.field for check in proof.failures()}


@pytest.mark.parametrize("key", [None, b"", bytes(15), "00" * 32])
def test_without_this_runs_orchestration_key_nothing_is_compared(record, key) -> None:
    proof = _proof(record, _state(), orchestration_key=key)
    assert proof.verdict == generic_construction.UNSUPPORTED
    assert [check.field for check in proof.checks] == ["constructed_state.observation_scope"]


def test_a_state_outside_the_orchestration_scope_is_unsupported(record) -> None:
    state = _state()
    state["observation_scope"] = "principal_scoped_observation"
    assert _proof(record, state).verdict == generic_construction.UNSUPPORTED
    state.pop("observation_scope")
    assert _proof(record, state).verdict == generic_construction.UNSUPPORTED


def test_the_digest_matches_the_providers_token_layout() -> None:
    # The same HMAC the XMage bridge test computes independently in Java:
    # schema, zone, seat, then name<TAB>count per name in String order.
    import hashlib
    import hmac

    tokens = [generic_construction.SCHEMA, "library_and_hand", "P2", "Lightning Bolt\t1"]
    tokens.append("Mountain\t98")
    mac = hmac.new(KEY, b"".join(t.encode() + b"\n" for t in tokens), hashlib.sha256)
    assert _deck_digest("P2", {"Mountain": 98, "Lightning Bolt": 1}) == mac.hexdigest()
    assert _deck_digest("P2", {"Mountain": 98, "Lightning Bolt": 1}) != _deck_digest(
        "P2", {"Mountain": 99}
    )


def test_the_mulligan_step_record_is_established_at_the_same_point() -> None:
    mulligan = load_effective_materialization().record("PILOT_MULLIGAN")
    assert mulligan["temporal_state"]["step"] == "mulligan"
    proof = _proof(mulligan, _state())
    assert proof.established, proof.reason()


def test_game_start_needs_the_declared_shuffle_and_draw(record) -> None:
    check = next(c for c in _proof(record, _state()).checks if c.field == "temporal_state.step")
    assert check.verdict == "EQUAL"
    assert (
        check.observed["declared_native_steps"]
        == list(generic_construction._GAME_START_TO_MULLIGAN)
        or tuple(check.observed["declared_native_steps"])
        == generic_construction._GAME_START_TO_MULLIGAN
    )
    undeclared = copy.deepcopy(record)
    undeclared["native_procedure"] = [
        step
        for step in undeclared["native_procedure"]
        if step["operation"] != "NATIVE_OPENING_HAND_DRAW"
    ]
    proof = _proof(undeclared, _state())
    assert "temporal_state.step" in {c.field for c in proof.failures()}


def test_a_missing_player_is_a_roster_mismatch(record) -> None:
    proof = _proof(record, _state(players=3))
    assert "players.roster" in {check.field for check in proof.failures()}


def test_an_unreported_cast_count_is_unsupported_not_equal(record) -> None:
    state = _mutate(["players", 0, "commanders", 0, "prior_command_zone_cast_count"], None)
    proof = _proof(record, state)
    assert proof.verdict == generic_construction.UNSUPPORTED


def test_no_state_and_unknown_schema_are_unsupported(record) -> None:
    assert _proof(record, None).verdict == generic_construction.UNSUPPORTED
    assert _proof(record, {"schema": "other"}).verdict == generic_construction.UNSUPPORTED


def test_a_native_state_load_record_is_never_constructed_here() -> None:
    start2 = load_effective_materialization().record("WS05-CMD-START-2")
    proof = _proof(start2, _state(players=2))
    assert proof.verdict == generic_construction.UNSUPPORTED
    assert "execution_entry_mode" in {check.field for check in proof.failures()}


def test_a_requested_knowledge_permission_is_unsupported(record) -> None:
    changed = copy.deepcopy(record)
    changed["knowledge_state"]["viewer_states"][0]["known_object_identities"] = ["obj:x"]
    assert _proof(changed, _state()).verdict == generic_construction.UNSUPPORTED


def _run(state: dict | None, *, supported: bool = True) -> CommandedGameResult:
    result = CommandedGameResult(
        candidate="xmage", player_count=4, deck_identity=["d"] * 4, game_id="g"
    )
    result.terminal_facts["created_player_count"] = 4
    result.terminal_facts["provider_constructed_state_supported"] = supported
    result.terminal_facts["constructed_state_channel"] = "orchestration_keyed_launch"
    result.orchestration_key = KEY
    if supported:
        result.constructed_state = state
        result.terminal_facts["constructed_state_capture"] = generic_construction.CAPTURE_POINT
    result.terminal_facts["first_priority_seat"] = "p1"
    result.seed_binding = classify_seed_binding(
        requested_seed=424242, acknowledged_seed=424242, source="test"
    )
    result.decision_tape = [_keep(seat) for seat in ("p1", "p2", "p3", "p4")]
    return result


def _keep(seat: str) -> DecisionTapeEntry:
    return DecisionTapeEntry(
        "mulligan",
        "KEEP_OR_MULLIGAN",
        f"engine-{seat}",
        1,
        "record_plan",
        None,
        ["opt-keep"],
        "planned",
        seat=seat,
        keep=True,
    )


@pytest.fixture
def complete_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        full107.lifecycle, "lifecycle_completeness", lambda run: {"complete": True, "reasons": []}
    )


@pytest.mark.usefixtures("complete_lifecycle")
def test_cardinality_passes_only_with_an_established_proof(record) -> None:
    row = full107.cardinality_row(record, _run(_state()), candidate="xmage", runtime_identity={})
    assert row.outcome == "PASS", row.reason
    assert row.evidence["construction_proof"]["verdict"] == generic_construction.EQUAL

    odd = _mutate(
        ["players", 1, "library_and_hand_digest"], _deck_digest("P2", {"Mountain": 98, "Plains": 1})
    )
    row = full107.cardinality_row(record, _run(odd), candidate="xmage", runtime_identity={})
    assert row.outcome == "UNKNOWN"
    assert "deck_state.P2.main_deck" in row.reason

    row = full107.cardinality_row(
        record, _run(None, supported=False), candidate="xmage", runtime_identity={}
    )
    assert row.outcome == "UNKNOWN"
    assert "emits no normalized constructed state" in row.reason
    assert "construction_proof" not in row.evidence


@pytest.mark.usefixtures("complete_lifecycle")
def test_a_principal_facing_launch_gives_no_proof(record) -> None:
    run = _run(_state())
    run.terminal_facts["constructed_state_channel"] = "no_launch_key"
    row = full107.cardinality_row(record, run, candidate="xmage", runtime_identity={})
    assert row.outcome == "UNKNOWN"
    assert "emits no normalized constructed state" in row.reason


def test_neither_the_state_nor_the_key_is_persisted() -> None:
    result = _run(_state())
    document = str(result.to_document())
    assert "library_and_hand_digest" not in document
    assert KEY.hex() not in document
    assert "'orchestration_key'" not in document
    assert repr(KEY) not in document


def _plan(**overrides: str) -> bridge_launcher.LaunchPlan:
    return bridge_launcher.LaunchPlan(
        candidate="xmage",
        lane="compat",
        argv=("java",),
        cwd=Path("."),
        env_overrides=dict(overrides),
        expected_engine_commit="c" * 40,
        build_identity={},
        workspace=".",
    )


def test_an_orchestration_plan_carries_a_fresh_key_and_leaves_the_plan_alone() -> None:
    plan = _plan(OTHER="1")
    first = bridge_launcher.orchestration_plan(plan)
    second = bridge_launcher.orchestration_plan(plan)
    variable = bridge_launcher.ORCHESTRATION_KEY_VARIABLE
    assert variable not in plan.env_overrides
    assert len(bytes.fromhex(first.env_overrides[variable])) == 32
    assert first.env_overrides[variable] != second.env_overrides[variable]
    assert first.env_overrides["OTHER"] == "1"


class _FakeProcess:
    def __init__(self, plan: bridge_launcher.LaunchPlan) -> None:
        self.plan = plan


def test_only_an_orchestration_launch_has_a_key_for_the_driver() -> None:
    assert game_driver._launch_orchestration_key(_FakeProcess(_plan())) is None
    short = _plan(**{bridge_launcher.ORCHESTRATION_KEY_VARIABLE: "00" * 8})
    assert game_driver._launch_orchestration_key(_FakeProcess(short)) is None
    keyed = bridge_launcher.orchestration_plan(_plan())
    key = game_driver._launch_orchestration_key(_FakeProcess(keyed))
    assert (
        key is not None
        and key.hex() == keyed.env_overrides[bridge_launcher.ORCHESTRATION_KEY_VARIABLE]
    )


def _runner_module():
    import importlib.util
    import sys

    path = Path(__file__).resolve().parents[2] / "scripts/run_current_boundary_qualification.py"
    spec = importlib.util.spec_from_file_location("cb_runner_for_receipts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_scripted_pregame_pass_gets_an_exact_direct_receipt() -> None:
    runner = _runner_module()
    assert full107.SCRIPTED_PREGAME_MODE in runner.DIRECT_RECEIPT_MODES
    mulligan = load_effective_materialization().record("PILOT_MULLIGAN")
    row = full107.RowResult(
        "PILOT_MULLIGAN", "xmage", "PASS", full107.SCRIPTED_PREGAME_MODE, "observed", {}
    )
    receipt = runner._direct_positive_receipt(
        row, mulligan, candidate_commit="c" * 40, runner_digest="r" * 64
    )
    assert receipt["test_identity"] == (
        "current-boundary-direct:PROTOCOL2_SCRIPTED_PREGAME#PILOT_MULLIGAN"
    )
    assert receipt["obligation_exercised"]["obligation_digest"] == mulligan["obligation_digest"]
    # An UNKNOWN row (no established construction proof) gets no receipt.
    unknown = full107.RowResult(
        "PILOT_MULLIGAN", "xmage", "UNKNOWN", full107.SCRIPTED_PREGAME_MODE, "gap", {}
    )
    with pytest.raises(ValueError):
        runner._direct_positive_receipt(
            unknown, mulligan, candidate_commit="c" * 40, runner_digest="r" * 64
        )


@pytest.mark.parametrize("turn_number", [0, 1])
def test_a_pre_first_turn_counter_of_either_convention_is_pregame(record, turn_number) -> None:
    # Forge reports 0 before the first turn, XMage 1; with no phase, active or
    # priority player both mean that no turn has begun.
    proof = _proof(record, _mutate(["turn_number"], turn_number))
    assert proof.established, proof.reason()


@pytest.mark.parametrize(
    ("clause", "value"),
    [
        ("forbidden_external_rules", ["legality_calculation", "teleportation"]),
        ("on_mismatch", "WARN"),
        ("construct_inside_rules_process", False),
        ("an_unknown_requirement", True),
    ],
)
def test_a_setup_clause_the_lane_cannot_establish_is_unsupported(record, clause, value) -> None:
    # Codex P1 (#530): setup_validation is a projection key and is checked.
    changed = copy.deepcopy(record)
    changed["setup_validation"][clause] = value
    proof = _proof(changed, _state())
    assert proof.verdict == generic_construction.UNSUPPORTED
    assert f"setup_validation.{clause}" in {c.field for c in proof.failures()}


def test_every_setup_clause_of_the_record_is_checked(record) -> None:
    fields = {c.field for c in _proof(record, _state()).checks}
    assert {f"setup_validation.{key}" for key in record["setup_validation"]} <= fields


def test_a_provider_without_shuffle_evidence_is_unsupported(record) -> None:
    state = _state()
    del state["players"][1]["library_shuffles"]
    proof = _proof(record, state)
    assert proof.verdict == generic_construction.UNSUPPORTED
    assert "rules_randomness.channel.library_shuffle:P2" in {c.field for c in proof.failures()}


def test_a_channel_other_than_a_library_shuffle_is_unsupported(record) -> None:
    changed = copy.deepcopy(record)
    changed["rules_randomness"]["channels"].append("coin_flip:P1")
    proof = _proof(changed, _state())
    assert proof.verdict == generic_construction.UNSUPPORTED


def test_every_requested_channel_is_checked(record) -> None:
    fields = {c.field for c in _proof(record, _state()).checks}
    for channel in record["rules_randomness"]["channels"]:
        assert f"rules_randomness.channel.{channel}" in fields


# --------------------------------------------------------------------------- #
# Codex P1s on 3813140d: the record's scripted pregame and the persisted proof
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("complete_lifecycle")
def test_the_cardinality_row_needs_the_records_own_pregame(record) -> None:
    run = _run(_state())
    assert full107.cardinality_row(record, run, candidate="xmage", runtime_identity={}).outcome == (
        "PASS"
    )
    for tape in (
        [_keep(seat) for seat in ("p1", "p3", "p4")],  # a skipped seat
        [_keep(seat) for seat in ("p1", "p2", "p2", "p3", "p4")],  # a repeated seat
        [_keep(seat) for seat in ("p2", "p1", "p3", "p4")],  # another order
        [],  # no pregame at all
    ):
        diverged = _run(_state())
        diverged.decision_tape = tape
        row = full107.cardinality_row(record, diverged, candidate="xmage", runtime_identity={})
        assert row.outcome == "UNKNOWN", tape
        assert "record's plan" in row.reason
    mulligan = _run(_state())
    mulligan.decision_tape = [
        DecisionTapeEntry(
            "mulligan", "KEEP_OR_MULLIGAN", "engine-p1", 1, "x", None, [], "", seat="p1", keep=False
        ),
        *(_keep(seat) for seat in ("p2", "p3", "p4")),
    ]
    row = full107.cardinality_row(record, mulligan, candidate="xmage", runtime_identity={})
    assert row.outcome == "UNKNOWN"


@pytest.mark.usefixtures("complete_lifecycle")
def test_a_plan_the_engine_did_not_follow_is_unknown_not_a_rules_failure(record) -> None:
    run = _run(_state())
    run.failure = "DecisionUnsatisfied: the engine asked mulligan #2 of p3; the plan names p2"
    row = full107.cardinality_row(record, run, candidate="xmage", runtime_identity={})
    assert row.outcome == "UNKNOWN"
    assert "scripted pregame did not complete" in row.reason
    run.failure = "BridgeError: the process died"
    assert full107.cardinality_row(record, run, candidate="xmage", runtime_identity={}).outcome == (
        "FAIL"
    )


def test_run_cardinality_drives_the_records_plan(record, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def fake_drive(proc, **kwargs):
        seen.update(kwargs)
        return _run(_state())

    monkeypatch.setattr(full107, "drive_commander_game", fake_drive)
    full107.run_cardinality(
        object(), candidate="xmage", player_count=4, runtime_identity={}, record=record
    )
    assert seen["mulligan_plan"] == (("p1", True), ("p2", True), ("p3", True), ("p4", True))
    full107.run_cardinality(object(), candidate="xmage", player_count=4, runtime_identity={})
    assert seen["mulligan_plan"] is None


@pytest.mark.usefixtures("complete_lifecycle")
def test_the_persisted_row_and_its_receipt_carry_the_proof(record) -> None:
    row = full107.cardinality_row(record, _run(_state()), candidate="xmage", runtime_identity={})
    assert row.outcome == "PASS"
    document = row.to_document(record)
    assert document["construction_proof"]["verdict"] == generic_construction.EQUAL
    assert document["scripted_pregame_plan"] == document["observed_pregame_decisions"]
    runner = _runner_module()
    receipt = runner._direct_positive_receipt(
        row, record, candidate_commit="c" * 40, runner_digest="r" * 64
    )
    tampered = copy.deepcopy(row)
    tampered.evidence["construction_proof"]["verdict"] = generic_construction.MISMATCH
    forged = runner._direct_positive_receipt(
        tampered, record, candidate_commit="c" * 40, runner_digest="r" * 64
    )
    # The receipt's row digest binds the proof: another proof is another receipt.
    assert (
        receipt["observed_assertion"]["row_document_sha256"]
        != forged["observed_assertion"]["row_document_sha256"]
    )


@pytest.mark.parametrize(
    "attribute", ["controller", "tapped", "face_down", "counters", "attachments"]
)
def test_a_provider_that_omits_a_native_attribute_is_unsupported(record, attribute) -> None:
    state = _state()
    del state["players"][0]["commanders"][0][attribute]
    proof = _proof(record, state)
    assert proof.verdict == generic_construction.UNSUPPORTED, proof.reason()
    assert not proof.established


@pytest.mark.parametrize("extra", ["duplicate", "malformed"])
def test_a_duplicate_or_malformed_roster_row_is_a_mismatch(record, extra) -> None:
    """Codex P2 (#530): the raw roster is compared, never a collapsed mapping."""
    state = _state()
    row = copy.deepcopy(state["players"][0])
    if extra == "malformed":
        row["player_id"] = None
    state["players"].append(row)
    proof = _proof(record, state)
    assert proof.verdict == generic_construction.MISMATCH, proof.reason()
    assert "players.roster" in {check.field for check in proof.failures()}


@pytest.mark.parametrize(
    "path",
    [
        ["rules_state"],
        ["rules_state", "combat_groups"],
        ["rules_state", "extra_turns"],
        ["rules_state", "pending_triggers"],
        ["rules_state", "continuous_effects"],
        ["players", 0, "knowledge"],
        ["players", 1, "commander_damage_taken"],
    ],
)
def test_a_provider_that_omits_a_native_readback_is_unsupported(record, path) -> None:
    """Codex P1 (#530): an empty projection is never inferred from the request."""
    state = _state()
    node = state
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    proof = _proof(record, state)
    assert proof.verdict == generic_construction.UNSUPPORTED, proof.reason()
    assert not proof.established


def test_an_unknown_channel_policy_is_unsupported(record) -> None:
    """Codex P1 (#530): the knowledge channel policy is examined, not ignored."""
    changed = copy.deepcopy(record)
    changed["knowledge_state"]["channel_policy"] = "observers may read every hand"
    proof = _proof(changed, _state())
    assert proof.verdict == generic_construction.UNSUPPORTED, proof.reason()
    assert "knowledge_state.channel_policy" in {check.field for check in proof.checks}
