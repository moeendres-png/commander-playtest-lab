"""Observed payment cancellations must not look like successful spell selections."""

from __future__ import annotations

import pytest

from tests.unit.test_pilot_decision_report_cards import (
    _option,
    _pass_option,
    _priority_record,
    pdr,
)


def _cast(name: str, *, turn: int = 5, seat: int = 0, own_turn: bool = True) -> dict:
    return _priority_record(
        turn=turn,
        seat=seat,
        actor_id=f"p{seat + 1}",
        active_player_id=f"p{seat + 1}" if own_turn else "opponent",
        options=[_option("spell", source_name=name), _pass_option()],
        picked_id="spell",
    )


def _cancel(*, seat: int = 0, turn: int = 5) -> dict:
    record = _priority_record(turn=turn, seat=seat, actor_id=f"p{seat + 1}")
    record["request"]["decision_class"] = "mana_payment"
    record["request"]["legal_options"] = [
        {"option_id": "cancel", "option_type": "cancel_mana_payment"}
    ]
    record["answer"]["selected_option_ids"] = ["cancel"]
    return record


@pytest.mark.parametrize("name", ["Lightning Bolt", "Farewell", "Counterspell"])
def test_cancelled_spell_does_not_count_as_cast_or_first_cast(name: str) -> None:
    summary = pdr.summarize([_cast(name, own_turn=False), _cancel()], players=4)
    assert summary["spells_cast"] == 0
    assert summary["wipes_cast"] == summary["counters_cast"] == 0
    assert summary["mana_payments_cancelled"] == 1
    entry = summary["per_card"][0]
    assert entry["cast"] == entry["cast_in_offer_window"] == entry["cast_on_opponent_turn"] == 0
    assert entry["first_cast_round"] is None
    assert entry["cancelled_payments"] == 1


def test_cancelled_first_attempt_does_not_hide_rotting_or_later_first_cast() -> None:
    records = [_cast("Rampant Growth", turn=5), _cancel(turn=5)]
    for turn in (9, 13, 17):
        record = _cast("Rampant Growth", turn=turn)
        record["answer"]["selected_option_ids"] = ["pass"]
        records.append(record)
    summary = pdr.summarize(records, players=4)
    cards = pdr.aggregate_cards({"games": [dict(summary, status="ok")]})
    assert cards["cards"][0]["cast_rate"] == 0
    assert cards["rotting"][0]["card"] == "Rampant Growth"
    assert cards["rotting"][0]["games_rotted"] == 1

    summary = pdr.summarize([*records, _cast("Rampant Growth", turn=21)], players=4)
    entry = summary["per_card"][0]
    assert entry["cast"] == entry["cast_in_offer_window"] == 1
    assert entry["first_cast_round"] == 5


def test_interleaved_seats_keep_their_own_cast_and_cancellation() -> None:
    summary = pdr.summarize(
        [_cast("Lightning Bolt"), _cast("Counterspell", seat=1), _cancel()], players=4
    )
    assert summary["spells_cast"] == 1
    assert summary["by_seat"]["1"]["spells_cast"] == 0
    assert summary["by_seat"]["2"]["spells_cast"] == 1
    entries = {entry["card"]: entry for entry in summary["per_card"]}
    assert entries["Lightning Bolt"]["cast"] == 0
    assert entries["Counterspell"]["cast"] == 1


@pytest.mark.parametrize("forced", [True, False])
def test_later_priority_clears_cancellation_attribution(forced: bool) -> None:
    options = [_pass_option()]
    if not forced:
        options.append(_option("ability", ability_type="activated", source_name="Sol Ring"))
    summary = pdr.summarize(
        [_cast("Lightning Bolt"), _priority_record(options=options, picked_id="pass"), _cancel()],
        players=4,
    )
    assert summary["spells_cast"] == 1
    assert summary["mana_payments_cancelled"] == 1
    assert summary["per_card"][0]["cancelled_payments"] == 0


def test_repeated_cancel_does_not_erase_a_previous_successful_cast() -> None:
    summary = pdr.summarize(
        [_cast("Lightning Bolt"), _cast("Lightning Bolt"), _cancel(), _cancel()], players=4
    )
    assert summary["spells_cast"] == 1
    assert summary["mana_payments_cancelled"] == 2
    assert summary["per_card"][0]["cast"] == 1
    assert summary["per_card"][0]["cancelled_payments"] == 1


def test_resolution_time_cast_failure_uses_the_engine_source_without_a_priority_selection() -> None:
    cancel = _cancel()
    cancel["request"]["source_object"] = {
        "ability_type": "spell",
        "source_name": "Fellwar Stone",
    }
    summary = pdr.summarize([cancel], players=4)
    entry = summary["per_card"][0]
    assert entry["card"] == "Fellwar Stone"
    assert entry["cast"] == 0
    assert entry["cancelled_payments"] == 1


@pytest.mark.parametrize("ability_type", ["spell", "activated_mana"])
def test_nested_payment_cancellation_does_not_erase_a_different_spell(ability_type: str) -> None:
    cancel = _cancel()
    cancel["request"]["source_object"] = {
        "ability_type": ability_type,
        "source_name": "Fellwar Stone",
    }
    summary = pdr.summarize([_cast("Lightning Bolt"), cancel], players=4)
    bolt = next(entry for entry in summary["per_card"] if entry["card"] == "Lightning Bolt")
    assert bolt["cast"] == 1
    assert bolt["cancelled_payments"] == 0


@pytest.mark.parametrize("same_object", [True, False])
def test_engine_source_identity_distinguishes_two_copies_of_the_same_card(
    same_object: bool,
) -> None:
    cast = _cast("Lightning Bolt")
    cast["request"]["legal_options"][0]["metadata"]["source_object_id"] = "first"
    cancel = _cancel()
    cancel["request"]["source_object"] = {
        "ability_type": "spell",
        "source_name": "Lightning Bolt",
        "source_object_id": "first" if same_object else "second",
    }
    summary = pdr.summarize([cast, cancel], players=4)
    assert summary["per_card"][0]["cast"] == (0 if same_object else 1)
