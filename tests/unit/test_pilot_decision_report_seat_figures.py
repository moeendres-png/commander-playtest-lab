"""Figures of scripts/pilot_decision_report.py that mixed seats or counted a card twice (#876).

* the commander's first cast and a card's first cast are rounds, not the game turn counter;
* a split card (Wear // Tear) is one card, not three, and its halves resolve to one name;
* cast_rate stays at or below 1 and the per-game cast share is reported next to it;
* the counters exist for each seat, not only summed over the pod.

Hand-made recorded-decision fixtures; no JVM, no games are played.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from commander_lab.agents.card_knowledge import canonical_card_name

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_seat_figures", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


def _spell(option_id: str, name: str, **meta: Any) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": "cast_spell",
        "metadata": {"ability_type": "spell", "source_name": name, **meta},
    }


def _pass() -> dict[str, Any]:
    return {"option_id": "pass", "option_type": "pass_priority", "metadata": {}}


def _record(
    *,
    seat: int = 0,
    turn: int = 5,
    own_turn: bool = True,
    phase: str = "main1",
    options: list[dict[str, Any]] | None = None,
    picked: str = "pass",
    players: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    actor = f"p{seat + 1}"
    state: dict[str, Any] = {
        "phase": phase,
        "step": "main",
        "turn_number": turn,
        "seat": seat,
        "actor_id": actor,
        "active_player_id": actor if own_turn else "p9",
        "stack": [],
    }
    if players is not None:
        state["players"] = players
    return {
        "request": {
            "decision_class": "priority",
            "legal_options": options if options is not None else [_pass()],
            "pilot_state": state,
        },
        "answer": {"selected_option_ids": [picked]},
        "pilot_s": 0.01,
    }


def _card(summary: dict[str, Any], seat: int, name: str) -> dict[str, Any]:
    return next(e for e in summary["per_card"] if e["seat"] == seat and e["card"] == name)


# --- split cards -----------------------------------------------------------


def test_canonical_card_name_maps_every_half_of_a_split_card() -> None:
    assert canonical_card_name("Wear // Tear") == "Wear // Tear"
    assert canonical_card_name("Wear") == "Wear // Tear"
    assert canonical_card_name("Tear") == "Wear // Tear"
    assert canonical_card_name("tear") == "Wear // Tear"
    assert canonical_card_name("Lightning Bolt") == "Lightning Bolt"
    assert canonical_card_name(None) == ""


def test_split_card_offered_as_three_spells_counts_once() -> None:
    options = [
        _spell("fused", "Wear // Tear"),
        _spell("wear", "Wear"),
        _spell("tear", "Tear"),
        _pass(),
    ]
    summary = pdr.summarize([_record(options=options, picked="tear")], players=4)
    assert [e["card"] for e in summary["per_card"]] == ["Wear // Tear"]
    entry = _card(summary, 1, "Wear // Tear")
    assert (entry["offered_castable"], entry["cast"], entry["cast_in_offer_window"]) == (1, 1, 1)
    assert entry["instant_speed"] is True


def test_back_half_cast_on_the_opponents_turn_is_an_instant_offer_and_cast() -> None:
    # "Tear" has no printed facts of its own; as a half of an instant it is an instant.
    record = _record(own_turn=False, options=[_spell("tear", "Tear"), _pass()], picked="tear")
    entry = _card(pdr.summarize([record], players=4), 1, "Wear // Tear")
    assert (entry["offered_castable"], entry["cast"], entry["cast_in_offer_window"]) == (1, 1, 1)
    assert entry["cast_on_opponent_turn"] == 1


# --- cast_rate and cast_share ----------------------------------------------


def test_cast_outside_a_counted_window_does_not_push_cast_rate_over_one() -> None:
    # A sorcery-speed card is offered once in an own main phase and cast later in a
    # window that does not count as an offer: two casts, one offer.
    records = [
        _record(options=[_spell("s", "Sol Ring Stand-In"), _pass()], picked="pass"),
        _record(own_turn=False, options=[_spell("s", "Sol Ring Stand-In"), _pass()], picked="s"),
        _record(options=[_spell("s", "Sol Ring Stand-In"), _pass()], picked="s"),
    ]
    summary = pdr.summarize(records, players=4)
    entry = _card(summary, 1, "Sol Ring Stand-In")
    assert (entry["offered_castable"], entry["cast"], entry["cast_in_offer_window"]) == (2, 2, 1)
    card = next(
        c
        for c in pdr.aggregate_cards({"games": [dict(summary, status="ok")]})["cards"]
        if c["card"] == "Sol Ring Stand-In"
    )
    assert card["cast_rate"] == pytest.approx(0.5)
    assert card["cast"] == 2


def test_cast_rate_never_exceeds_one_for_legacy_records() -> None:
    game = {
        "status": "ok",
        "per_card": [{"seat": 1, "card": "Tear", "offered_castable": 1, "cast": 3}],
    }
    card = pdr.aggregate_cards({"games": [game]})["cards"][0]
    assert card["cast_rate"] == 1.0


def test_cast_share_counts_games_not_windows() -> None:
    def game(offered: int, cast: int) -> dict[str, Any]:
        records = [
            _record(
                options=[_spell("b", "Lightning Bolt"), _pass()], picked="b" if i < cast else "pass"
            )
            for i in range(offered)
        ]
        return dict(pdr.summarize(records, players=4), status="ok")

    cards = pdr.aggregate_cards({"games": [game(3, 1), game(2, 0), game(1, 1)]})["cards"]
    bolt = next(c for c in cards if c["card"] == "Lightning Bolt")
    assert bolt["offered_castable"] == 6
    assert bolt["cast_rate"] == pytest.approx(2 / 6, abs=1e-3)
    assert bolt["games_offered"] == 3
    assert bolt["games_cast_after_offer"] == 2
    assert bolt["cast_share"] == pytest.approx(2 / 3, abs=1e-3)


def test_cast_share_is_none_when_never_offered() -> None:
    game = {
        "status": "ok",
        "per_card": [{"seat": 1, "card": "Odd", "offered_castable": 0, "cast": 1}],
    }
    odd = pdr.aggregate_cards({"games": [game]})["cards"][0]
    assert (odd["games_offered"], odd["games_cast_after_offer"], odd["cast_share"]) == (0, 0, None)
    assert odd["cast_rate"] == 0.0


# --- rounds, not the turn counter ------------------------------------------


def _own_turn_passes(seat: int, turns: list[int]) -> list[dict[str, Any]]:
    """One priority pass on each of the seat's own turns, as a real game records them."""
    return [_record(seat=seat, turn=turn) for turn in turns]


def _commander_cast(
    seat: int, turn: int, name: str = "Rogshai", object_id: str = "cmd"
) -> dict[str, Any]:
    actor = f"p{seat + 1}"
    return _record(
        seat=seat,
        turn=turn,
        options=[_spell("c", name, source_object_id=object_id), _pass()],
        picked="c",
        players=[{"player_id": actor, "command": [{"object_id": object_id}]}],
    )


@pytest.mark.parametrize(
    ("seat", "turn", "round_"),
    [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 4, 1), (0, 5, 2), (3, 8, 2), (1, 10, 3)],
)
def test_commander_first_cast_is_reported_as_a_round(seat: int, turn: int, round_: int) -> None:
    earlier = [seat + 1 + 4 * k for k in range(round_ - 1)]
    records = [*_own_turn_passes(seat, earlier), _commander_cast(seat, turn)]
    summary = pdr.summarize(records, players=4)
    assert summary["commander_first_cast_round"] == {str(seat + 1): round_}
    # The counter field is unchanged: it still depends on where the seat sits.
    assert summary["commander_first_cast_turn"] == {str(seat + 1): turn}


def test_the_round_counts_own_turns_after_a_player_has_left() -> None:
    # Four players: own turns at 1, 5, 9. A player is eliminated, so the next round has three
    # turns and the seat's fourth turn is turn 12, where counter arithmetic says round 3.
    records = [*_own_turn_passes(0, [1, 5, 9]), _commander_cast(0, 12)]
    summary = pdr.summarize(records, players=4)
    assert summary["commander_first_cast_round"] == {"1": 4}
    assert summary["commander_first_cast_turn"] == {"1": 12}


def test_partner_commanders_keep_their_own_first_cast_round() -> None:
    # Rograkh costs {0} and comes down on the first turn; Ishai follows on the third.
    records = [
        _commander_cast(0, 1, "Rograkh, Son of Rohgahh", "rog"),
        *_own_turn_passes(0, [5]),
        _commander_cast(0, 9, "Ishai, Ojutai Dragonspeaker", "ish"),
    ]
    for record in (records[0], records[2]):
        record["request"]["pilot_state"]["players"] = [
            {"player_id": "p1", "command": [{"object_id": "rog"}, {"object_id": "ish"}]}
        ]
    summary = pdr.summarize(records, players=4)
    assert summary["commander_first_cast_round"] == {"1": 1}
    assert summary["commander_first_cast_round_by_name"] == {
        "1": {"Ishai, Ojutai Dragonspeaker": 3, "Rograkh, Son of Rohgahh": 1}
    }


def test_first_cast_round_of_a_card_does_not_depend_on_the_seat() -> None:
    first_seat = _record(
        seat=0, turn=1, options=[_spell("b", "Lightning Bolt"), _pass()], picked="b"
    )
    last_seat = _record(
        seat=3, turn=4, options=[_spell("b", "Lightning Bolt"), _pass()], picked="b"
    )
    assert _card(pdr.summarize([first_seat], 4), 1, "Lightning Bolt")["first_cast_round"] == 1
    assert _card(pdr.summarize([last_seat], 4), 4, "Lightning Bolt")["first_cast_round"] == 1


# --- by seat ---------------------------------------------------------------


def _idle_with_spell(seat: int, turn: int) -> dict[str, Any]:
    return _record(
        seat=seat,
        turn=turn,
        phase="main2",
        options=[_spell("b", "Lightning Bolt"), _pass()],
        picked="pass",
    )


def test_by_seat_splits_counters_and_adds_up_to_the_pod_total() -> None:
    records = [
        _idle_with_spell(0, 1),
        _idle_with_spell(0, 5),
        _idle_with_spell(1, 2),
        _record(seat=2, turn=3, options=[_spell("b", "Lightning Bolt"), _pass()], picked="b"),
    ]
    summary = pdr.summarize(records, players=4)
    by_seat = summary["by_seat"]
    assert sorted(by_seat) == ["1", "2", "3"]
    assert by_seat["1"]["bad_idle_main_with_castable_spell"] == 2
    assert by_seat["2"]["bad_idle_main_with_castable_spell"] == 1
    assert by_seat["3"]["bad_idle_main_with_castable_spell"] == 0
    assert by_seat["3"]["spells_cast"] == 1
    for key in (
        "decisions",
        "spells_cast",
        "own_turns",
        "bad_idle_main_with_castable_spell",
        "bad_idle_main_with_unplayed_land",
        "forced_priority",
    ):
        assert sum(s[key] for s in by_seat.values()) == summary[key], key
    assert "by_seat" not in by_seat["1"]


def test_by_seat_can_be_left_out() -> None:
    assert "by_seat" not in pdr.summarize([_idle_with_spell(0, 1)], players=4, by_seat=False)


def test_totals_by_seat_sums_the_ok_games() -> None:
    games = [
        dict(pdr.summarize([_idle_with_spell(0, 1), _idle_with_spell(1, 2)], 4), status="ok"),
        dict(pdr.summarize([_idle_with_spell(0, 1)], 4), status="ok"),
        {"status": "failed"},
        {"status": "ok", "wall_s": 3.0},  # a batched game has no decision record
    ]
    out = pdr.totals_by_seat({"games": games})
    assert out["1"]["games_ok"] == 2
    assert out["1"]["bad_idle_main_with_castable_spell"] == 2
    assert out["2"]["bad_idle_main_with_castable_spell"] == 1


def test_aggregate_cards_by_seat_keeps_the_same_card_of_two_seats_apart() -> None:
    def game(seat: int, offered: int, cast: int) -> dict[str, Any]:
        records = [
            _record(
                seat=seat,
                options=[_spell("b", "Lightning Bolt"), _pass()],
                picked="b" if i < cast else "pass",
            )
            for i in range(offered)
        ]
        return dict(pdr.summarize(records, 4), status="ok")

    first = game(0, 4, 1)
    second = game(1, 2, 2)
    # One game in which both seats hold the card.
    both = dict(first, per_card=first["per_card"] + second["per_card"])
    result = pdr.aggregate_cards({"games": [both]})
    merged = next(c for c in result["cards"] if c["card"] == "Lightning Bolt")
    assert merged["offered_castable"] == 6
    assert merged["cast"] == 3
    assert result["by_seat"]["1"]["cards"][0]["cast_rate"] == pytest.approx(0.25)
    assert result["by_seat"]["2"]["cards"][0]["cast_rate"] == pytest.approx(1.0)
    assert result["by_seat"]["1"]["cards"][0]["offered_castable"] == 4
