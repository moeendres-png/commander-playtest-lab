"""Generic-lane construction proof (#441, Owner decision (c)).

The provider's normalized constructed state must equal the record's requested
state field by field. Each control below changes exactly one fact and must stop
the proof (wrong deck card, commander, owner, life, zone content, seed, starting
seat, capture point, cast count, entry mode); a provider that emits nothing gives
no proof at all, which keeps the decision (a) UNKNOWN.
"""

from __future__ import annotations

import copy

import pytest

from commander_lab.qualification.current_boundary import full107, generic_construction
from commander_lab.qualification.current_boundary.game_driver import CommandedGameResult
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)
from commander_lab.qualification.current_boundary.receipts import classify_seed_binding

ROGRAKH = "Rograkh, Son of Rohgahh"


@pytest.fixture(scope="module")
def record() -> dict:
    return load_effective_materialization().record("PLAYER_COUNT_4P")


def _state(players: int = 4) -> dict:
    return {
        "schema": generic_construction.SCHEMA,
        "lifecycle": "started",
        "turn_number": 1,
        "phase": "beginning",
        "active_player": "P1",
        "priority_player": "P1",
        "stack_size": 0,
        "players": [
            {
                "player_id": f"P{seat}",
                "seat": seat,
                "life": 40,
                "poison": 0,
                "lost": False,
                "left": False,
                "library_size": 92,
                "library_card_counts": {"Mountain": 92},
                "hand_size": 7,
                "hand_card_counts": {"Mountain": 7},
                "graveyard_card_counts": {},
                "exile_card_counts": {},
                "battlefield_card_counts": {},
                "commanders": [
                    {
                        "card_identity": ROGRAKH,
                        "owner": f"P{seat}",
                        "zone": "command",
                        "prior_command_zone_cast_count": 0,
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
    }
    kwargs.update(overrides)
    return generic_construction.compare(record, state, **kwargs)


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
        "knowledge_state",
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
            (["players", 1, "library_card_counts"], {"Mountain": 91, "Lightning Bolt": 1}),
            "deck_state.P2.main_deck",
        ),
        ((["players", 2, "life"], 20), "players.P3.life"),
        ((["players", 0, "poison"], 1), "players.P1.poison"),
        ((["players", 3, "battlefield_card_counts"], {"Mountain": 1}), "zones.P4.battlefield"),
        ((["players", 0, "graveyard_card_counts"], {"Mountain": 1}), "zones.P1.graveyard"),
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
    ],
)
def test_run_facts_are_checked_too(record, overrides, field) -> None:
    proof = _proof(record, _state(), **overrides)
    assert proof.verdict == generic_construction.MISMATCH
    assert field in {check.field for check in proof.failures()}


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
    if supported:
        result.constructed_state = state
        result.terminal_facts["constructed_state_capture"] = generic_construction.CAPTURE_POINT
    result.terminal_facts["first_priority_seat"] = "p1"
    result.seed_binding = classify_seed_binding(
        requested_seed=424242, acknowledged_seed=424242, source="test"
    )
    return result


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

    odd = _mutate(["players", 1, "library_card_counts"], {"Mountain": 91, "Plains": 1})
    row = full107.cardinality_row(record, _run(odd), candidate="xmage", runtime_identity={})
    assert row.outcome == "UNKNOWN"
    assert "deck_state.P2.main_deck" in row.reason

    row = full107.cardinality_row(
        record, _run(None, supported=False), candidate="xmage", runtime_identity={}
    )
    assert row.outcome == "UNKNOWN"
    assert "emits no normalized constructed state" in row.reason
    assert "construction_proof" not in row.evidence


def test_the_raw_constructed_state_is_never_persisted() -> None:
    result = _run(_state())
    document = result.to_document()
    assert "hand_card_counts" not in str(document)
    assert "library_card_counts" not in str(document)
