"""The code conditions of the START-2/MULL errata (#441 comment 6007651998).

Contract 1.0.22 makes WS05-CMD-START-2 a natural-start record and gives
WS05-CMD-MULL-2/4 their Rules seed. The ruling binds the code to the record:

* C-E1: ``start2_row`` runs the record's own decks and the record's own seed,
  so the construction proof compares the record, never the lane's defaults.
* C-E2: ``scripted_pregame_row`` refuses a record without ``rules_seed``; no
  lane default stands in for it.
* C-E3: the natural-start START-2 stays UNKNOWN when the constructed state is
  absent or unkeyed; a record that keeps NATIVE_STATE_LOAD stays UNSUPPORTED; a
  missing seed is refused; and starting-player credit comes only from the
  first_priority_seat the construction proof compares, never from the first
  actor on the decision tape.

Every run here is a fake engine result: these tests prove the row's own
classification logic, never engine behaviour, and no row earns credit here.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import full107, generic_construction
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


@pytest.fixture(scope="module")
def materialization() -> Any:
    return load_effective_materialization()


@pytest.fixture()
def start2(materialization) -> dict[str, Any]:
    return copy.deepcopy(materialization.record("WS05-CMD-START-2"))


def _state(players: int = 2) -> dict[str, Any]:
    """A provider constructed state equal to the natural START-2 request."""
    return {
        "schema": generic_construction.SCHEMA,
        "observation_scope": "orchestration_keyed_digests",
        "lifecycle": "started",
        "turn_number": 1,
        "phase": None,
        "active_player": None,
        "priority_player": None,
        "stack_size": 0,
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
                "library_and_hand_digest": generic_construction.zone_digest(
                    KEY, f"P{seat}", "library_and_hand", {"Mountain": 99}
                ),
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


def _observed(
    *, keyed: bool = True, state: dict[str, Any] | None = None, first_priority: Any = "p1"
) -> CommandedGameResult:
    """A fully observed CR 103.8a skip on a fake engine."""
    result = CommandedGameResult(
        candidate="xmage", player_count=2, deck_identity=["d1", "d2"], game_id="g"
    )
    counts = [{"hand_count": 7, "library_count": 92}]
    result.terminal_facts.update(
        {
            "start2_baseline_zone_counts": counts,
            "start2_baseline_checkpoint": {
                "turn_number": 1,
                "phase": "beginning",
                "step": "upkeep",
            },
            "start2_post_zone_counts": counts,
            "observed_actor_zone_counts": counts,
            "start2_post_checkpoint": {"turn_number": 1, "phase": "precombat_main", "step": "main"},
            "draw_step_decision_frames": [],
            "priority_reached": True,
        }
    )
    if first_priority is not None:
        result.terminal_facts["first_priority_seat"] = first_priority
    if keyed:
        result.terminal_facts.update(
            {
                "provider_constructed_state_supported": True,
                "constructed_state_channel": "orchestration_keyed_launch",
                "constructed_state_capture": generic_construction.CAPTURE_POINT,
            }
        )
        result.constructed_state = state
        result.orchestration_key = KEY
    result.seed_binding = classify_seed_binding(
        requested_seed=424242, acknowledged_seed=424242, source="test"
    )
    # The first actor on the tape is P1 in every run here; it is never the
    # starting-player evidence.
    result.decision_tape = [
        DecisionTapeEntry(
            "mulligan", "MULLIGAN", "p1", 1, "keep_opening_hand", "keep", ["keep"], "observed"
        )
    ]
    return result


def _start2(
    record: dict[str, Any], monkeypatch: pytest.MonkeyPatch, game: CommandedGameResult
) -> tuple[full107.RowResult, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def drive(*args: Any, **kwargs: Any) -> CommandedGameResult:
        calls.append(kwargs)
        return game

    monkeypatch.setattr(full107, "drive_commander_game", drive)
    row = full107.start2_row(record, object(), candidate="xmage", runtime_identity={})
    return row, calls


def _equal_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    check = generic_construction.FieldCheck("test", "EQUAL", 1, 1, "test proof")
    proof = generic_construction.ConstructionProof(generic_construction.EQUAL, (check,))
    monkeypatch.setattr(full107.generic_construction, "compare", lambda *a, **k: proof)


# --- C-E1: the record's decks and seed ---------------------------------------- #


def test_start2_runs_the_records_decks_and_seed(start2, monkeypatch) -> None:
    start2["rules_randomness"]["rules_seed"] = 777
    _, calls = _start2(start2, monkeypatch, _observed(state=_state()))
    (call,) = calls
    assert call["seed"] == 777
    assert call["decks"] == full107.record_decks(start2)
    assert [deck["commander_names"] for deck in call["decks"]] == [[ROGRAKH], [ROGRAKH]]
    assert all(deck["mainboard"] == ["Mountain"] * 99 for deck in call["decks"])


def test_the_natural_start2_record_constructs_equal_and_passes(start2, monkeypatch) -> None:
    row, _ = _start2(start2, monkeypatch, _observed(state=_state()))
    assert row.evidence["construction_proof"]["verdict"] == generic_construction.EQUAL
    assert row.outcome == "PASS", row.reason


# --- C-E3 (a): absent or unkeyed constructed state ----------------------------- #


@pytest.mark.parametrize(
    "game",
    [
        pytest.param(lambda: _observed(keyed=False), id="unkeyed-launch"),
        pytest.param(lambda: _observed(state=None), id="absent-state"),
        pytest.param(
            lambda: _observed(state={**_state(), "observation_scope": "public"}),
            id="unkeyed-state",
        ),
    ],
)
def test_natural_start2_without_a_keyed_constructed_state_stays_unknown(
    start2, monkeypatch, game
) -> None:
    row, calls = _start2(start2, monkeypatch, game())
    assert row.outcome == "UNKNOWN"
    assert "construction equality is unestablished" in row.reason
    # The run was the record's game, so the gap is the only thing missing.
    assert calls[0]["decks"] == full107.record_decks(start2)


def test_a_launch_without_its_orchestration_key_stays_unknown(start2, monkeypatch) -> None:
    game = _observed(state=_state())
    game.orchestration_key = None
    row, _ = _start2(start2, monkeypatch, game)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["construction_proof"]["verdict"] == generic_construction.UNSUPPORTED


# --- C-E3 (b): a record that keeps NATIVE_STATE_LOAD ---------------------------- #


def test_a_record_that_keeps_native_state_load_stays_unsupported(start2, monkeypatch) -> None:
    start2["execution_entry_mode"] = "NATIVE_STATE_LOAD"
    proof = generic_construction.compare(
        start2,
        _state(),
        acknowledged_seed=424242,
        first_priority_seat="p1",
        capture=generic_construction.CAPTURE_POINT,
        orchestration_key=KEY,
    )
    assert proof.verdict == generic_construction.UNSUPPORTED
    failed = {check.field: check.verdict for check in proof.failures()}
    assert failed == {"execution_entry_mode": "UNSUPPORTED"}
    row, _ = _start2(start2, monkeypatch, _observed(state=_state()))
    assert row.outcome == "UNKNOWN"
    assert row.evidence["construction_proof"]["verdict"] == generic_construction.UNSUPPORTED


# --- C-E2 / C-E3 (c): a missing rules_seed is refused --------------------------- #


@pytest.mark.parametrize("seed", [None, "424242", True, 0.5])
def test_start2_refuses_a_record_without_an_integer_seed(start2, monkeypatch, seed) -> None:
    if seed is None:
        del start2["rules_randomness"]["rules_seed"]
    else:
        start2["rules_randomness"]["rules_seed"] = seed
    row, calls = _start2(start2, monkeypatch, _observed(state=_state()))
    assert calls == []
    assert row.outcome == "UNKNOWN"
    assert row.reason == full107.MISSING_SEED_REASON


def test_start2_refuses_a_record_without_its_decks(start2, monkeypatch) -> None:
    del start2["deck_state"]
    row, calls = _start2(start2, monkeypatch, _observed(state=_state()))
    assert calls == []
    assert row.outcome == "UNKNOWN"
    assert "decks cannot be imported" in row.reason


@pytest.mark.parametrize("fixture_id", ["WS05-CMD-MULL-4", "PILOT_MULLIGAN"])
def test_scripted_pregame_refuses_a_record_without_a_seed(
    materialization, monkeypatch, fixture_id
) -> None:
    record = copy.deepcopy(materialization.record(fixture_id))
    del record["rules_randomness"]["rules_seed"]
    calls: list[Any] = []
    monkeypatch.setattr(
        full107, "drive_commander_game", lambda *a, **k: calls.append(k) or _observed()
    )
    row = full107.scripted_pregame_row(record, object(), candidate="xmage", runtime_identity={})
    assert calls == []
    assert row.outcome == "UNKNOWN"
    assert row.reason == full107.MISSING_SEED_REASON


@pytest.mark.parametrize("fixture_id", ["WS05-CMD-MULL-2", "WS05-CMD-MULL-4"])
def test_the_mull_records_state_their_own_seed(materialization, fixture_id) -> None:
    record = materialization.record(fixture_id)
    assert full107.record_rules_seed(record) == 424242
    seats = [player["player_id"] for player in record["players"]]
    assert record["rules_randomness"]["channels"] == [f"library_shuffle:{s}" for s in seats]


# --- C-E3 (d): the starting player comes from first_priority_seat --------------- #


def test_the_first_tape_actor_is_never_starting_player_credit(start2, monkeypatch) -> None:
    _equal_proof(monkeypatch)
    row, _ = _start2(start2, monkeypatch, _observed(state=_state(), first_priority=None))
    assert row.outcome == "UNKNOWN"
    assert "no first priority seat" in row.reason
    assert row.evidence["observed_starting_actor"] == "p1"
    assert row.evidence["observed_starting_actor_is_starting_player_evidence"] is False


def test_another_first_priority_seat_is_not_the_records_starting_player(
    start2, monkeypatch
) -> None:
    _equal_proof(monkeypatch)
    row, _ = _start2(start2, monkeypatch, _observed(state=_state(), first_priority="p2"))
    assert row.outcome == "UNKNOWN"
    assert "first priority to P2" in row.reason


def test_the_first_priority_seat_credits_without_any_tape_actor(start2, monkeypatch) -> None:
    _equal_proof(monkeypatch)
    game = _observed(state=_state())
    game.decision_tape = []
    row, _ = _start2(start2, monkeypatch, game)
    assert row.outcome == "PASS", row.reason
    assert row.evidence["observed_starting_seat"] == "P1"
