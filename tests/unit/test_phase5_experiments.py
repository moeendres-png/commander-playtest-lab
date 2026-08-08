from pathlib import Path

from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.models import PilotConfig
from commander_lab.optimization import ablation_filler, run_paired_structural_comparison, variant_deck

ROOT = Path(__file__).resolve().parents[2]


def test_variant_preserves_card_count_and_changes_hash() -> None:
    decks = load_project_structural_decks(ROOT, include_synthetic_fixtures=True)
    deck = decks["korvold/current"]
    card = next(card for card in deck.cards if card.oracle_name == "Vampiric Rites")
    variant = variant_deck(
        deck,
        variant_id="test/variant",
        removals=(card.oracle_name,),
        additions=(ablation_filler(card),),
    )
    assert len(variant.cards) == len(deck.cards)
    assert variant.deck_hash != deck.deck_hash


def test_paired_comparison_is_reproducible() -> None:
    decks = load_project_structural_decks(ROOT, include_synthetic_fixtures=True)
    baseline = decks["korvold/current"]
    card = next(card for card in baseline.cards if card.oracle_name == "Vampiric Rites")
    variant = variant_deck(
        baseline, variant_id="test/repro", removals=(card.oracle_name,), additions=(ablation_filler(card),)
    )
    kwargs = dict(
        baseline=baseline,
        variant=variant,
        opponents=(decks["synthetic/aggro"], decks["synthetic/control"], decks["synthetic/engine"]),
        iterations=6,
        seed=20260804,
        pilot_config=PilotConfig(),
        max_turns=25,
        pair_id="repro",
    )
    first, pairs_a = run_paired_structural_comparison(**kwargs)
    second, pairs_b = run_paired_structural_comparison(**kwargs)
    assert first == second
    assert pairs_a == pairs_b
