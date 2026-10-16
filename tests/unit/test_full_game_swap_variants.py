"""``--swap``: a deck-comparison variant made from the baseline by exchanging cards.

A swap replaces one card of the baseline in its library slot, so the variant stays
paired with the baseline game for game until the swapped card matters.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from commander_lab.engine.rules.full_game_comparison import (
    SwapSpecError,
    apply_swaps,
    parse_swaps,
)
from commander_lab.models import RulesDeckInput

ROOT = Path(__file__).resolve().parents[2]
_FILLER = tuple(f"Filler {index}" for index in range(99))


def _deck(*cards: str) -> RulesDeckInput:
    return RulesDeckInput(
        deck_id="base",
        name="base",
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=(*cards, *_FILLER[: 99 - len(cards)]),
        deck_hash="1" * 64,
    )


def _cli() -> ModuleType:
    path = ROOT / "scripts/run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("run_full_game_deck_comparison", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_swaps_reads_one_or_several_pairs_and_keeps_commas_in_names() -> None:
    assert parse_swaps("Sol Ring=>Mind Stone") == (("Sol Ring", "Mind Stone"),)
    assert parse_swaps(" Chandra, Torch of Defiance => Arcane Signet ; A=>B ") == (
        ("Chandra, Torch of Defiance", "Arcane Signet"),
        ("A", "B"),
    )


@pytest.mark.parametrize("text", ["", ";", "Sol Ring", "Sol Ring=>", "=>Mind Stone", "A->B"])
def test_parse_swaps_rejects_text_that_is_not_a_swap(text: str) -> None:
    with pytest.raises(SwapSpecError):
        parse_swaps(text)


def test_apply_swaps_exchanges_the_card_in_its_slot() -> None:
    deck = apply_swaps(_deck("A", "B", "C"), [("B", "X")])
    assert deck.mainboard[:3] == ("A", "X", "C")
    assert len(deck.mainboard) == 99


def test_apply_swaps_replaces_only_the_first_copy_of_a_repeated_card() -> None:
    deck = apply_swaps(_deck("Plains", "A", "Plains", "Plains"), [("Plains", "Island")])
    assert deck.mainboard[:4] == ("Island", "A", "Plains", "Plains")


def test_apply_swaps_applies_several_swaps_of_one_variant() -> None:
    deck = apply_swaps(_deck("A", "B", "C"), [("A", "X"), ("C", "Y")])
    assert deck.mainboard[:3] == ("X", "B", "Y")


def test_apply_swaps_matches_ignoring_case_when_that_is_unambiguous() -> None:
    deck = apply_swaps(_deck("Sol Ring", "A"), [("sol ring", "Mind Stone")])
    assert deck.mainboard[:2] == ("Mind Stone", "A")


def test_apply_swaps_names_a_card_that_is_not_in_the_mainboard() -> None:
    with pytest.raises(SwapSpecError, match="Mox Diamond"):
        apply_swaps(_deck("A"), [("Mox Diamond", "X")])


def test_apply_swaps_cannot_swap_the_commander() -> None:
    with pytest.raises(SwapSpecError, match="Isamaru"):
        apply_swaps(_deck("A"), [("Isamaru, Hound of Konda", "X")])


def test_apply_swaps_leaves_the_baseline_alone_and_clears_the_stale_hash() -> None:
    baseline = _deck("A", "B")
    variant = apply_swaps(baseline, [("A", "X")])
    assert baseline.mainboard[0] == "A" and baseline.deck_hash == "1" * 64
    assert variant.deck_hash is None


def test_swap_variants_get_their_own_ids_and_a_content_hash() -> None:
    cli = _cli()
    baseline = _deck("A", "B", "C")
    variants = cli.swap_variants(baseline, ["A=>X", "B=>Y;C=>Z"])
    assert [variant.deck_id for variant in variants] == ["base#swap1", "base#swap2"]
    assert all(variant.deck_hash is not None for variant in variants)
    assert variants[0].deck_hash != variants[1].deck_hash != baseline.deck_hash
    assert variants[1].mainboard[:3] == ("A", "Y", "Z")


def _plan_only(cli: ModuleType, *extra: str) -> int:
    result = cli.main(
        [
            "--baseline",
            str(ROOT / "data/decks/rogshai_current.json"),
            "--opponent",
            str(ROOT / "data/decks/opponents/kaervek/current/deck.json"),
            "--opponent",
            str(ROOT / "data/opponents/hosts_of_mordor_precon.json"),
            "--opponent",
            str(ROOT / "data/opponents/lorehold_spirit_precon.json"),
            "--seeds",
            "1-2",
            "--out",
            "unused",
            "--workers",
            "2",
            "--plan-only",
            *extra,
        ]
    )
    assert isinstance(result, int)
    return result


def test_cli_plans_a_swap_variant_on_the_real_deck(capsys: pytest.CaptureFixture[str]) -> None:
    assert _plan_only(_cli(), "--swap", "Sol Ring=>Mind Stone") == 0
    out = capsys.readouterr().out
    assert "rogshai/current#swap1: Sol Ring=>Mind Stone" in out
    assert "16 games: 2 contenders x 2 seeds x 4 seats, 4 players, 2 workers" in out


def test_cli_refuses_a_swap_of_a_card_the_baseline_does_not_play() -> None:
    with pytest.raises(SystemExit) as exit_info:
        _plan_only(_cli(), "--swap", "Black Lotus=>Mind Stone")
    assert exit_info.value.code == 2


def test_cli_needs_a_variant_or_a_swap() -> None:
    with pytest.raises(SystemExit) as exit_info:
        _plan_only(_cli())
    assert exit_info.value.code == 2
