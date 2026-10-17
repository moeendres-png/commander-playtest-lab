"""Per-card cast rate and rotting cards in scripts/pilot_decision_report.py (#836, #871).

Tests use hand-made recorded-decision fixtures; no JVM, no games are played.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_under_test", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


def _option(
    option_id: str,
    *,
    option_type: str = "cast_spell",
    ability_type: str = "spell",
    source_name: str = "",
) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "metadata": {"ability_type": ability_type, "source_name": source_name},
    }


def _pass_option(option_id: str = "pass") -> dict[str, Any]:
    return {"option_id": option_id, "option_type": "pass_priority", "metadata": {}}


def _priority_record(
    *,
    turn: int = 5,
    seat: int = 0,
    actor_id: str = "p1",
    active_player_id: str = "p1",
    phase: str = "main1",
    options: list[dict[str, Any]] | None = None,
    picked_id: str | None = None,
    stack: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if options is None:
        options = [_pass_option()]
    return {
        "request": {
            "decision_class": "priority",
            "legal_options": options,
            "pilot_state": {
                "phase": phase,
                "step": "main",
                "turn_number": turn,
                "seat": seat,
                "actor_id": actor_id,
                "active_player_id": active_player_id,
                "stack": stack if stack is not None else [],
            },
        },
        "answer": {"selected_option_ids": [picked_id] if picked_id else []},
        "pilot_s": 0.01,
    }


def test_cast_rate_quarter_when_offered_four_times_cast_once() -> None:
    records = [
        _priority_record(
            options=[
                _option("bolt", source_name="Lightning Bolt"),
                _pass_option(),
            ],
            picked_id="bolt" if i == 0 else "pass",
        )
        for i in range(4)
    ]
    summary = pdr.summarize(records, players=4)
    per_card = {(e["seat"], e["card"]): e for e in summary["per_card"]}
    entry = per_card[(1, "Lightning Bolt")]
    assert entry["offered_castable"] == 4
    assert entry["cast"] == 1
    assert entry["first_cast_round"] is not None

    report = {"games": [dict(summary, status="ok", pod="p", seed=1, players=4)]}
    cards = pdr.aggregate_cards(report)
    bolt = next(c for c in cards["cards"] if c["card"] == "Lightning Bolt")
    assert bolt["offered_castable"] == 4
    assert bolt["cast"] == 1
    assert bolt["cast_rate"] == pytest.approx(0.25)
    assert bolt["games_seen"] == 1


def test_land_play_is_not_counted_as_cast() -> None:
    records = [
        _priority_record(
            options=[
                _option(
                    "land", option_type="play_land", ability_type="play_land", source_name="Island"
                ),
                _pass_option(),
            ],
            picked_id="land",
        )
    ]
    summary = pdr.summarize(records, players=4)
    assert summary["per_card"] == []
    # The spell counters are untouched by a land play.
    assert summary["spells_cast"] == 0


def test_opponent_turn_window_not_attributed() -> None:
    # Opponent's main phase: the actor may still get priority (instants), but
    # offered_castable only counts own main-phase windows.
    records = [
        _priority_record(
            active_player_id="p2",  # not the actor's turn
            options=[
                _option("bolt", source_name="Lightning Bolt"),
                _pass_option(),
            ],
            picked_id="pass",
        )
    ]
    summary = pdr.summarize(records, players=4)
    assert summary["per_card"] == []


def test_rotting_list_ranks_by_frequency() -> None:
    def game_with(seed: int, cards: list[tuple[str, int]]) -> dict[str, Any]:
        # cards: (name, offered_windows); never cast.
        per_card = [
            {
                "seat": 1,
                "card": name,
                "offered_castable": n,
                "cast": 0,
                "first_cast_round": None,
            }
            for name, n in cards
        ]
        return {
            "status": "ok",
            "pod": "p",
            "seed": seed,
            "players": 4,
            "per_card": per_card,
            "rounds": 10.0,
        }

    report = {
        "games": [
            game_with(1, [("A", 5), ("B", 4)]),
            game_with(2, [("A", 3), ("C", 2)]),  # C below the 3-window threshold
            game_with(3, [("B", 6)]),
        ]
    }
    cards = pdr.aggregate_cards(report)
    rotting = [(e["card"], e["games_rotted"]) for e in cards["rotting"]]
    # A rotted in games 1+2, B in games 1+3; C never (only 2 windows in game 2).
    assert rotting == [("A", 2), ("B", 2)]
    names = [c["card"] for c in cards["cards"]]
    assert "C" in names  # still listed in per-card figures


def test_totals_unchanged_for_existing_fixture() -> None:
    # Rows without per_card (old reports) aggregate cleanly and totals are
    # unaffected by the new section.
    rows = [
        {
            "pod": "real",
            "seed": seed,
            "players": 4,
            "status": "ok",
            "rounds": 10.0,
            "spells_cast": 40.0,
            "turns": 40,
        }
        for seed in (1, 2)
    ]
    report: dict[str, Any] = {"jar": "bridge.jar", "games": rows}
    out = pdr.totals(report)
    assert out["spells_cast"] == 80.0
    assert out["games_ok"] == 2
    cards = pdr.aggregate_cards(report)
    assert cards["cards"] == []
    assert cards["rotting"] == []
    assert pdr.format_rotting(cards) == [
        "most rotting cards (offered castable, never cast):",
        "  (none)",
    ]


def test_run_prints_top_ten_rotting(capsys: Any) -> None:
    per_card = [
        {
            "seat": 1,
            "card": f"Card{i:02d}",
            "offered_castable": 5,
            "cast": 0,
            "first_cast_round": None,
        }
        for i in range(12)
    ]
    game = {
        "status": "ok",
        "pod": "p",
        "seed": 1,
        "players": 4,
        "per_card": per_card,
        "rounds": 10.0,
    }
    cards = pdr.aggregate_cards({"games": [game]})
    lines = pdr.format_rotting(cards)
    # Header + 10 cards (limit), the 11th and 12th are cut off.
    assert len(lines) == 11
    assert lines[0].startswith("most rotting cards")


# ---------------------------------------------------------------------------
# #871: instant-speed cards count offers/casts in any priority window of the
# actor, except when the stack's top object is a spell this seat cast earlier.
# ---------------------------------------------------------------------------


def _summarized_game(seed: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = pdr.summarize(records, players=4)
    return dict(summary, status="ok", pod="p", seed=seed, players=4)


def test_instant_cast_on_opponents_end_step_counts_offer_and_cast() -> None:
    # (a) A Counterspell cast in the opponent's end step is both an offer and
    # a cast, and counts as cast_on_opponent_turn.
    records = [
        _priority_record(
            active_player_id="p2",
            phase="end",
            options=[_option("cs", source_name="Counterspell"), _pass_option()],
            picked_id="cs",
        )
    ]
    per_card = {(e["seat"], e["card"]): e for e in pdr.summarize(records, players=4)["per_card"]}
    entry = per_card[(1, "Counterspell")]
    assert entry["offered_castable"] == 1
    assert entry["cast"] == 1
    assert entry["cast_on_opponent_turn"] == 1
    assert entry["instant_speed"] is True
    assert entry["first_cast_round"] is not None


def test_counterspell_offer_skipped_with_own_spell_on_stack() -> None:
    # (b) The actor casts its commander first, so its name is remembered as
    # an own cast. With the own spell on top of the stack the Counterspell
    # option is not an offer (withholding it is correct); with an opponent's
    # spell on top it is.
    cast_commander = _priority_record(
        options=[_option("ishai", source_name="Ishai, Ojutai Dragonspeaker"), _pass_option()],
        picked_id="ishai",
    )
    own_on_stack = _priority_record(
        active_player_id="p2",
        options=[_option("cs", source_name="Counterspell"), _pass_option()],
        picked_id="pass",
        stack=[{"name": "Ishai, Ojutai Dragonspeaker"}],
    )
    foe_on_stack = _priority_record(
        active_player_id="p2",
        options=[_option("cs", source_name="Counterspell"), _pass_option()],
        picked_id="pass",
        stack=[{"name": "Sol Ring"}],
    )
    per_card = {
        (e["seat"], e["card"]): e
        for e in pdr.summarize([cast_commander, own_on_stack, foe_on_stack], players=4)["per_card"]
    }
    counter = per_card[(1, "Counterspell")]
    assert counter["offered_castable"] == 1
    assert counter["cast"] == 0
    # The commander's own window keeps the old sorcery-speed accounting.
    ishai = per_card[(1, "Ishai, Ojutai Dragonspeaker")]
    assert ishai["offered_castable"] == 1
    assert ishai["cast"] == 1
    assert ishai["instant_speed"] is False


def test_sorcery_offer_not_counted_on_opponent_turn() -> None:
    # (c) Sorcery-speed cards keep the old rule: no offer on an opponent's
    # turn, even with the stack empty. Sol Ring is a catalog-known artifact.
    records = [
        _priority_record(
            active_player_id="p2",
            options=[_option("ring", source_name="Sol Ring"), _pass_option()],
            picked_id="pass",
        )
    ]
    assert pdr.summarize(records, players=4)["per_card"] == []


def test_rotting_skips_counterspell_held_against_own_spells() -> None:
    # (d) Passed three times against opponent spells and never cast: rotting.
    # Passed three times only against own spells: no counted offers, so not
    # rotting.
    def hold_against(stack_names: list[str], seed: int) -> dict[str, Any]:
        records = [
            _priority_record(
                options=[
                    _option("ishai", source_name="Ishai, Ojutai Dragonspeaker"),
                    _pass_option(),
                ],
                picked_id="ishai",
            )
        ]
        for name in stack_names:
            records.append(
                _priority_record(
                    active_player_id="p2",
                    options=[_option("cs", source_name="Counterspell"), _pass_option()],
                    picked_id="pass",
                    stack=[{"name": name}],
                )
            )
        return _summarized_game(seed, records)

    report = {
        "games": [
            hold_against(["Sol Ring"] * 3, 1),
            hold_against(["Ishai, Ojutai Dragonspeaker"] * 3, 2),
        ]
    }
    cards = pdr.aggregate_cards(report)
    counter = next(c for c in cards["cards"] if c["card"] == "Counterspell")
    assert counter["offered_castable"] == 3
    assert counter["cast"] == 0
    rotting = [(e["card"], e["games_rotted"]) for e in cards["rotting"]]
    # Only the game with the opponent-spell windows rots.
    assert rotting == [("Counterspell", 1)]


def test_old_record_without_version_fields_aggregates() -> None:
    # (e) A game record written before per_card_version 2 has neither the
    # version key nor the new per_card fields; it still aggregates.
    game = {
        "status": "ok",
        "pod": "p",
        "seed": 1,
        "players": 4,
        "rounds": 10.0,
        "per_card": [
            {
                "seat": 1,
                "card": "Counterspell",
                "offered_castable": 4,
                "cast": 1,
                "first_cast_round": 2.5,
            }
        ],
    }
    assert "per_card_version" not in game
    cards = pdr.aggregate_cards({"games": [game]})
    counter = next(c for c in cards["cards"] if c["card"] == "Counterspell")
    assert counter["offered_castable"] == 4
    assert counter["cast"] == 1
    assert counter["cast_on_opponent_turn"] == 0
    assert counter["instant_speed"] is False
    assert counter["cast_rate"] == pytest.approx(0.25)


def test_new_records_carry_per_card_version_2() -> None:
    records = [
        _priority_record(
            options=[_option("cs", source_name="Counterspell"), _pass_option()],
            picked_id="pass",
        )
    ]
    summary = pdr.summarize(records, players=4)
    assert summary["per_card_version"] == 2
    assert summary["per_card"][0]["instant_speed"] is True


def test_compare_warns_when_per_card_versions_differ() -> None:
    # Per-card figures are not compared across different per_card_version
    # values; the comparison prints one line saying so.
    def versioned_report(version: int | None, seed: int) -> dict[str, Any]:
        game = {
            "status": "ok",
            "pod": "p",
            "seed": seed,
            "players": 4,
            "rounds": 10.0,
            "turns": 40,
            "decisions": 10,
            "per_card": [],
        }
        if version is not None:
            game["per_card_version"] = version
        return {"games": [game]}

    same_a = versioned_report(2, 1)
    same_b = versioned_report(2, 1)
    assert not any(
        "per_card_version" in warning for warning in pdr.compare_reports(same_a, same_b)["warnings"]
    )
    mixed = pdr.compare_reports(versioned_report(None, 1), versioned_report(2, 1))
    version_warnings = [warning for warning in mixed["warnings"] if "per_card_version" in warning]
    assert len(version_warnings) == 1
    assert "not compared" in version_warnings[0]


# ---------------------------------------------------------------------------
# #882 review: _stack_top_is_own_cast reads the top *spell* — index 0 is the
# stack top (real recordings), abilities are skipped. Cases from the review
# table; the first two are the Rotprobe (they fail on the old stack[-1] code).
# ---------------------------------------------------------------------------

_OWN_SPELL = "ishai, ojutai dragonspeaker"  # casefolded, as stored in own_names


def _stack_state(names: list[str]) -> dict[str, Any]:
    return {"stack": [{"name": name} for name in names]}


def test_stack_top_foe_spell_on_top_own_below_offers() -> None:
    # [opponent spell, own spell]: top spell is foe's -> offer (False).
    assert (
        pdr._stack_top_is_own_cast(
            _stack_state(["Sol Ring", "Ishai, Ojutai Dragonspeaker"]), {_OWN_SPELL}
        )
        is False
    )


def test_stack_top_own_spell_on_top_foe_below_withholds() -> None:
    # [own spell, opponent spell]: top spell is own -> no offer (True).
    assert (
        pdr._stack_top_is_own_cast(
            _stack_state(["Ishai, Ojutai Dragonspeaker", "Sol Ring"]), {_OWN_SPELL}
        )
        is True
    )


def test_stack_top_ability_skipped_own_spell_below_withholds() -> None:
    # [own ability, own spell]: ability skipped, top spell is own -> True.
    assert (
        pdr._stack_top_is_own_cast(
            _stack_state(["Equip {0}", "Ishai, Ojutai Dragonspeaker"]), {_OWN_SPELL}
        )
        is True
    )


def test_stack_top_ability_skipped_foe_spell_below_offers() -> None:
    # [own ability, opponent spell]: ability skipped, top spell is foe's -> False.
    assert (
        pdr._stack_top_is_own_cast(_stack_state(["Equip {0}", "Sol Ring"]), {_OWN_SPELL}) is False
    )


def test_stack_top_empty_stack_offers() -> None:
    assert pdr._stack_top_is_own_cast({"stack": []}, {_OWN_SPELL}) is False
