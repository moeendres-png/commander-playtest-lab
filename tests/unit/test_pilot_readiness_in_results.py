"""The pilot's card knowledge is part of every result (#961 P-2) and two counters say so (P-3).

A verdict about a card the pilot knows nothing about measures "unknown card": the pilot plays it
as a spell without cost or role. Deck comparisons now carry which cards of a variant that
differ from the baseline are not ready, and pilot reports carry how many spell options were for
such cards. No JVM; the games are hand-made records.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.deck_readiness import (
    CardReadinessStatus,
    check_deck,
    compare_readiness,
    readiness_payload,
)
from commander_lab.models import RulesDeckInput

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"{name}_under_test", ROOT / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pdr = _script("pilot_decision_report")
cli = _script("run_full_game_deck_comparison")

_FACTS = json.loads((ROOT / "data/cards/xmage_card_facts.json").read_text(encoding="utf-8"))
_PILOT_CARDS = json.loads(
    (ROOT / "data/cards/pilot_card_knowledge.json").read_text(encoding="utf-8")
)["cards"]
KNOWN = sorted(set(_FACTS["cards"]) & set(_PILOT_CARDS))
UNKNOWN = "Invented Card Name Qzx 999"


def _deck(names: list[str], deck_id: str) -> RulesDeckInput:
    commander, *rest = names
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=(commander,),
        mainboard=tuple((rest * 100)[:99]),
    )


# --- a variant that differs by a card the pilot cannot play well --------------------------


def test_a_variant_that_adds_an_unknown_card_is_not_comparable() -> None:
    baseline = check_deck(_deck(KNOWN[:100], "base"))
    variant = check_deck(_deck([*KNOWN[:99], UNKNOWN], "variant"))
    compared = compare_readiness(baseline, variant)
    assert [c.name for c in compared.added] == [UNKNOWN]
    assert compared.added[0].status is CardReadinessStatus.NO_CARD_FACTS
    assert compared.removed == ()
    assert not compared.comparable


def test_a_variant_that_removes_an_unknown_card_is_not_comparable_either() -> None:
    baseline = check_deck(_deck([*KNOWN[:99], UNKNOWN], "base"))
    variant = check_deck(_deck(KNOWN[:100], "variant"))
    compared = compare_readiness(baseline, variant)
    assert [c.name for c in compared.removed] == [UNKNOWN] and compared.added == ()
    assert not compared.comparable


def test_a_swap_of_two_known_cards_is_comparable_even_when_the_deck_is_not_ready() -> None:
    """The decks share an unknown card; the verdict is about the difference only."""
    shared = [UNKNOWN, *KNOWN[:97]]
    baseline = check_deck(_deck([*shared, KNOWN[97], KNOWN[98]], "base"))
    variant = check_deck(_deck([*shared, KNOWN[97], KNOWN[99]], "variant"))
    assert not baseline.ready and not variant.ready
    assert compare_readiness(baseline, variant).comparable


def test_the_payload_names_the_roles_the_baseline_and_the_unready_cards() -> None:
    contenders = (
        _deck(KNOWN[:100], "base"),
        _deck([*KNOWN[:99], UNKNOWN], "plus-unknown"),
        _deck([*KNOWN[:98], KNOWN[100], KNOWN[101]], "known-swap"),
    )
    opponent = _deck([UNKNOWN, *KNOWN[:99]], "opp")
    payload = readiness_payload(contenders, (opponent,))
    assert {k: v["role"] for k, v in payload["decks"].items()} == {
        "base": "contender",
        "plus-unknown": "contender",
        "known-swap": "contender",
        "opp": "opponent",
    }
    assert payload["decks"]["base"]["ready"] is True
    assert payload["decks"]["opp"]["not_ready"] == [{"name": UNKNOWN, "status": "NO_CARD_FACTS"}]
    assert set(payload["variants"]) == {"plus-unknown", "known-swap"}
    assert payload["variants"]["plus-unknown"]["comparable"] is False
    assert payload["variants"]["plus-unknown"]["baseline"] == "base"
    assert payload["variants"]["plus-unknown"]["added_not_ready"] == [
        {"name": UNKNOWN, "status": "NO_CARD_FACTS"}
    ]
    assert payload["variants"]["known-swap"]["comparable"] is True
    json.dumps(payload)  # it goes into COMPARISON_REPORT.json


def _paired_row(variant: str) -> dict[str, Any]:
    return {
        "variant_deck_id": variant,
        "baseline_deck_id": "base",
        "verdict": "VARIANT_BETTER",
        "pairs_completed": 20,
        "variant_only_wins": 9,
        "baseline_only_wins": 2,
        "identical_pairs": 9,
        "sign_test_p_value": 0.03,
    }


def test_the_summary_marks_a_verdict_about_an_unready_card_partial() -> None:
    contenders = (_deck(KNOWN[:100], "base"), _deck([*KNOWN[:99], UNKNOWN], "plus-unknown"))
    payload = {
        "contenders": [],
        "paired": [_paired_row("plus-unknown")],
        "seeds": [1],
        "pilot_readiness": readiness_payload(contenders, ()),
    }
    lines = cli._summary_lines(payload)
    partial = [line for line in lines if line.startswith("PARTIAL:")]
    assert len(partial) == 1
    assert "plus-unknown adds Invented Card Name Qzx 999 (NO_CARD_FACTS)" in partial[0]
    assert lines.index(partial[0]) == 1, "it follows the verdict line it qualifies"


def test_the_summary_is_unchanged_for_a_comparable_variant_and_for_an_old_payload() -> None:
    contenders = (_deck(KNOWN[:100], "base"), _deck([*KNOWN[:99], KNOWN[100]], "known"))
    with_block = {
        "contenders": [],
        "paired": [_paired_row("known")],
        "seeds": [1],
        "pilot_readiness": readiness_payload(contenders, ()),
    }
    old = {"contenders": [], "paired": [_paired_row("known")], "seeds": [1]}
    assert cli._summary_lines(with_block) == cli._summary_lines(old)
    assert not any(line.startswith("PARTIAL") for line in cli._summary_lines(old))


# --- spell options without pilot knowledge in a pilot report ------------------------------


def _option(option_id: str, name: str) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": "cast_spell",
        "metadata": {"ability_type": "spell", "source_name": name},
    }


def _window(names: list[str], *, seat: int = 0) -> dict[str, Any]:
    options = [_option(f"o{i}", name) for i, name in enumerate(names)]
    options.append({"option_id": "pass", "option_type": "pass_priority", "metadata": {}})
    return {
        "request": {
            "decision_class": "priority",
            "legal_options": options,
            "pilot_state": {
                "phase": "main1",
                "step": "main",
                "turn_number": 3,
                "seat": seat,
                "actor_id": "p1",
                "active_player_id": "p1",
                "stack": [],
            },
        },
        "answer": {"selected_option_ids": ["pass"]},
        "pilot_s": 0.01,
    }


def _known_name() -> str:
    assert card_facts(KNOWN[0]) is not None
    return KNOWN[0]


def test_spell_options_are_counted_with_the_pilots_own_lookup() -> None:
    assert card_facts(UNKNOWN) is None
    records = [
        _window([_known_name(), UNKNOWN]),
        _window([UNKNOWN], seat=1),
        _window([_known_name(), _known_name()], seat=1),
    ]
    game = pdr.summarize(records, players=4)
    assert game["spell_offers"] == 5
    assert game["spell_offers_without_pilot_knowledge"] == 2
    # Seats are numbered from 1: the first window is seat 1, the other two are seat 2.
    assert game["by_seat"]["1"]["spell_offers"] == 2
    assert game["by_seat"]["1"]["spell_offers_without_pilot_knowledge"] == 1
    assert game["by_seat"]["2"]["spell_offers"] == 3
    assert game["by_seat"]["2"]["spell_offers_without_pilot_knowledge"] == 1


def test_a_forced_pass_and_a_window_without_a_spell_count_nothing() -> None:
    forced = _window([])
    land_only = _window([])
    land_only["request"]["legal_options"].insert(
        0,
        {
            "option_id": "land",
            "option_type": "play_land",
            "metadata": {"ability_type": "play_land"},
        },
    )
    game = pdr.summarize([forced, land_only], players=4)
    assert game["spell_offers"] == 0 and game["spell_offers_without_pilot_knowledge"] == 0


def _report(shares: list[tuple[int, int]], *, with_counters: bool = True) -> dict[str, Any]:
    games = []
    for seed, (offers, unknown) in enumerate(shares, start=1):
        game: dict[str, Any] = {
            "status": "ok",
            "pod": "p",
            "seed": seed,
            "turns": 10,
            "spells_cast": 3,
        }
        if with_counters:
            game["spell_offers"] = offers
            game["spell_offers_without_pilot_knowledge"] = unknown
        games.append(game)
    return {"games": games}


def test_totals_carry_the_share_and_an_old_report_does_not() -> None:
    new = pdr.totals(_report([(100, 2), (100, 4)]))
    assert new["spell_offers"] == 200 and new["spell_offers_without_pilot_knowledge"] == 6
    assert new["share_spell_offers_without_pilot_knowledge"] == pytest.approx(0.03)
    assert "spell_offers" not in pdr.totals(_report([(0, 0)], with_counters=False))


def test_compare_prints_both_arms_and_warns_above_the_share_that_matters() -> None:
    low = _report([(100, 2)] * 10)
    high = _report([(100, 30)] * 10)
    result = pdr.compare_reports(low, high, resamples=50, flips=50)
    lines = pdr.format_comparison(result)
    line = next(x for x in lines if x.startswith("spell options for cards without pilot knowledge"))
    assert "before 2.0 % (20 of 1000)".replace(" %", "%") in line
    assert "after 30.0% (300 of 1000)" in line
    assert [w for w in result["warnings"] if "no knowledge of" in w and "(after)" in w]
    assert not [w for w in result["warnings"] if "(before)" in w]
    quiet = pdr.compare_reports(low, low, resamples=50, flips=50)
    assert not [w for w in quiet["warnings"] if "no knowledge of" in w]


def test_compare_of_old_reports_adds_no_knowledge_line() -> None:
    old = _report([(0, 0)] * 10, with_counters=False)
    result = pdr.compare_reports(old, old, resamples=50, flips=50)
    assert result["pilot_knowledge"] == {"before": None, "after": None}
    assert not [x for x in pdr.format_comparison(result) if "without pilot knowledge" in x]


# --- P-3: counters that cannot be non-zero ------------------------------------------------


def test_the_two_self_referential_counters_are_not_compared_but_still_stored() -> None:
    for key in ("bad_attacks_into_killer", "bad_needless_chump_blocks"):
        assert key not in pdr._COMPARE_METRICS
        assert key in pdr._TOTALS and key in pdr._SEAT_KEYS
    result = pdr.compare_reports(
        _report([(1, 0)] * 10), _report([(1, 0)] * 10), resamples=50, flips=50
    )
    assert "bad_attacks_into_killer" not in result["metrics"]
    lines = pdr.format_comparison(result)
    assert any(
        x.startswith("not compared: bad_attacks_into_killer, bad_needless_chump_blocks")
        for x in lines
    )
    payload = pdr.comparison_payload(result, Path("a.json"), Path("b.json"))
    assert set(payload["not_compared"]) == {"bad_attacks_into_killer", "bad_needless_chump_blocks"}
    assert any(
        "not compared" in x for x in pdr.format_markdown(result, Path("a.json"), Path("b.json"))
    )
