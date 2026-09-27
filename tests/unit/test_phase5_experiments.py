from pathlib import Path

from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.models import PilotConfig
from commander_lab.optimization import (
    ablation_filler,
    run_paired_structural_comparison,
    variant_deck,
)

ROOT = Path(__file__).resolve().parents[2]


def test_variant_preserves_card_count_and_changes_hash() -> None:
    decks = load_project_structural_decks(ROOT, include_synthetic_fixtures=True)
    deck = decks["rogshai/current"]
    card = next(card for card in deck.cards if card.oracle_name == "Consider")
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
    baseline = decks["rogshai/current"]
    card = next(card for card in baseline.cards if card.oracle_name == "Consider")
    variant = variant_deck(
        baseline,
        variant_id="test/repro",
        removals=(card.oracle_name,),
        additions=(ablation_filler(card),),
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


def test_paired_comparison_is_reproducible_across_worker_counts() -> None:
    decks = load_project_structural_decks(ROOT, include_synthetic_fixtures=True)
    baseline = decks["rogshai/current"]
    card = next(card for card in baseline.cards if card.oracle_name == "Consider")
    variant = variant_deck(
        baseline,
        variant_id="test/worker-repro",
        removals=(card.oracle_name,),
        additions=(ablation_filler(card),),
    )
    common = dict(
        baseline=baseline,
        variant=variant,
        opponents=(decks["synthetic/aggro"], decks["synthetic/control"]),
        iterations=8,
        seed=20260821,
        pilot_config=PilotConfig(),
        max_turns=14,
        pair_id="worker-repro",
    )
    single, single_pairs = run_paired_structural_comparison(**common, workers=1)
    parallel, parallel_pairs = run_paired_structural_comparison(**common, workers=2)
    single_payload = single.as_dict()
    parallel_payload = parallel.as_dict()
    single_payload.pop("worker_count")
    parallel_payload.pop("worker_count")

    assert single_payload == parallel_payload
    assert single_pairs == parallel_pairs
    assert parallel.worker_count == 2


def test_commander_denial_can_tax_each_partner_or_both() -> None:
    baseline = load_project_structural_decks(ROOT, include_synthetic_fixtures=True)[
        "rogshai/current"
    ]
    ishai = "Ishai, Ojutai Dragonspeaker"
    rograkh = "Rograkh, Son of Rohgahh"
    ishai_only = variant_deck(
        baseline,
        variant_id="test/deny-ishai",
        additional_commander_tax=6,
        denied_commanders=(ishai,),
    )
    rograkh_only = variant_deck(
        baseline,
        variant_id="test/deny-rograkh",
        additional_commander_tax=6,
        denied_commanders=(rograkh,),
    )
    both = variant_deck(
        baseline,
        variant_id="test/deny-both",
        additional_commander_tax=6,
    )

    assert ishai_only.commander_base_costs[ishai] == baseline.commander_base_costs[ishai] + 6
    assert ishai_only.commander_base_costs[rograkh] == baseline.commander_base_costs[rograkh]
    assert rograkh_only.commander_base_costs[rograkh] == (
        baseline.commander_base_costs[rograkh] + 6
    )
    assert rograkh_only.commander_base_costs[ishai] == baseline.commander_base_costs[ishai]
    assert all(
        both.commander_base_costs[name] == cost + 6
        for name, cost in baseline.commander_base_costs.items()
    )
