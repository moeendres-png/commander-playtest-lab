from __future__ import annotations

import json
from pathlib import Path

import commander_lab.fresh_rebuild as fresh_rebuild
from commander_lab.engine.structural import StructuralSimulator, load_project_structural_decks
from commander_lab.fresh_rebuild import (
    ROGSHAI_COMMANDERS,
    build_fresh_rogshai_profile,
    load_fresh_rogshai_universe,
)
from commander_lab.fresh_rebuild_experiments import (
    candidates_for_fresh_baseline,
    commander_denial_variant,
)
from commander_lab.models import Deck, DeckZone, PilotConfig, StructuralAbortLimits, StructuralMatchConfig
from commander_lab.optimization import (
    DEFAULT_CONSTRAINTS,
    ablation_filler,
    all_legal_single_swaps,
    run_paired_structural_comparison,
    variant_deck,
)
from commander_lab.storage import load_model


def _contract(repo_root: Path) -> dict[str, object]:
    return json.loads(
        (repo_root / "data/rogshai_mvp/K1_K2_RUNTIME_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )


def _development_mainboard(repo_root: Path) -> tuple[str, ...]:
    """Current list is used only as a visible test fixture, never as a fresh-build prior."""

    deck = load_model(repo_root / "data/decks/rogshai_current.json", Deck)
    names = tuple(
        entry.oracle_name
        for entry in deck.cards
        if entry.zone == DeckZone.MAIN
        for _ in range(entry.quantity)
    )
    assert len(names) == 98
    return names


def _opponents(repo_root: Path):
    decks = load_project_structural_decks(repo_root, include_synthetic_fixtures=True)
    return (
        decks["synthetic/aggro"],
        decks["synthetic/control"],
        decks["synthetic/engine"],
    )


def test_k2_bias_gate_current_deck_is_not_a_fresh_universe_input(
    repo_root: Path, monkeypatch
) -> None:
    original = fresh_rebuild.load_model

    def guarded_load(path, model):
        assert Path(path).name != "rogshai_current.json"
        return original(path, model)

    monkeypatch.setattr(fresh_rebuild, "load_model", guarded_load)
    universe = load_fresh_rogshai_universe(repo_root)
    assert universe.candidate_count > 0


def test_fresh_universe_matches_k1_and_retains_uncertainty(repo_root: Path) -> None:
    contract = _contract(repo_root)
    expected = contract["rogshai_candidate_pool"]
    assert isinstance(expected, dict)
    universe = load_fresh_rogshai_universe(repo_root)
    assert universe.candidate_count == int(expected["expected_count"])
    assert universe.candidate_count == (
        universe.structurally_scorable_count + universe.review_required_count
    )
    assert universe.review_required_count > 0
    assert set(universe.review_required) <= set(universe.candidate_names)
    assert all(name not in universe.candidate_by_name() for name in universe.review_required)
    for basic in ("Plains", "Island", "Mountain"):
        assert universe.available_quantities.get(basic, 0) >= 50


def test_arbitrary_fresh_profile_is_100_cards_and_uses_rogshai_pilot(repo_root: Path) -> None:
    universe = load_fresh_rogshai_universe(repo_root)
    fresh = build_fresh_rogshai_profile(
        repo_root,
        _development_mainboard(repo_root),
        variant_label="mvp-development-fixture",
        universe=universe,
    )
    assert len(fresh.cards) == 100
    assert fresh.commander_names == ROGSHAI_COMMANDERS
    assert fresh.commander_strategy == "rogshai"
    assert fresh.deck_id.startswith("rogshai/fresh/")

    opponents = _opponents(repo_root)
    registry = {deck.deck_id: deck for deck in (fresh, *opponents)}
    config = StructuralMatchConfig(
        match_id="rogshai-mvp-pilot",
        seed=20260810,
        deck_ids=(fresh.deck_id, *(deck.deck_id for deck in opponents)),
        limits=StructuralAbortLimits(
            max_turns=20,
            max_events=30_000,
            max_no_progress_turns=15,
        ),
    )
    result = StructuralSimulator(registry).simulate(config)
    assert result.player_metrics["p1"].pilot_name == "RogShaiPilot"
    assert result.estimate_type == "structural_model_estimates"


def test_fresh_structural_replay_is_deterministic(repo_root: Path, tmp_path: Path) -> None:
    fresh = build_fresh_rogshai_profile(
        repo_root,
        _development_mainboard(repo_root),
        variant_label="mvp-replay",
    )
    opponents = _opponents(repo_root)
    registry = {deck.deck_id: deck for deck in (fresh, *opponents)}
    config = StructuralMatchConfig(
        match_id="rogshai-mvp-replay",
        seed=424242,
        deck_ids=(fresh.deck_id, *(deck.deck_id for deck in opponents)),
        limits=StructuralAbortLimits(
            max_turns=20,
            max_events=30_000,
            max_no_progress_turns=15,
        ),
    )
    simulator = StructuralSimulator(registry)
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    first = simulator.simulate(config, event_log_path=first_path)
    second = simulator.simulate(config, event_log_path=second_path)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.log_sha256 == second.log_sha256


def test_fresh_paired_ablation_search_and_denial_smoke(repo_root: Path) -> None:
    universe = load_fresh_rogshai_universe(repo_root)
    baseline = build_fresh_rogshai_profile(
        repo_root,
        _development_mainboard(repo_root),
        variant_label="mvp-experiments",
        universe=universe,
    )
    opponents = _opponents(repo_root)
    baseline_names = {card.oracle_name for card in baseline.cards}

    candidate_rows = candidates_for_fresh_baseline(universe, baseline)
    eligible_ids = tuple(
        candidate_id
        for candidate_id, candidate in candidate_rows.items()
        if candidate.card.oracle_name not in baseline_names
        and not candidate.card.is_land
        and universe.available_quantities.get(candidate.card.oracle_name, 0) > 0
    )[:64]
    assert eligible_ids

    search_results = all_legal_single_swaps(
        baseline,
        candidate_rows,
        eligible_ids,
        DEFAULT_CONSTRAINTS["rogshai/current"],
        inventory=dict(universe.available_quantities),
        verified_physical_names=set(universe.verified_physical_names),
    )
    assert search_results
    searched = search_results[0]
    assert searched.constraint_report.valid

    paired, _ = run_paired_structural_comparison(
        baseline=baseline,
        variant=searched.variant,
        opponents=opponents,
        iterations=1,
        seed=515151,
        pilot_config=PilotConfig(),
        max_turns=20,
        pair_id="rogshai-mvp-paired",
    )
    assert paired.actual_sample_size == 1

    ablated_name = next(
        card.oracle_name
        for card in baseline.cards
        if card.oracle_name not in baseline.commander_names and not card.is_land
    )
    original = next(card for card in baseline.cards if card.oracle_name == ablated_name)
    ablated = variant_deck(
        baseline,
        variant_id=f"{baseline.deck_id}/ablation-smoke",
        removals=(ablated_name,),
        additions=(ablation_filler(original, suffix="mvp smoke"),),
    )
    ablation_metrics, _ = run_paired_structural_comparison(
        baseline=baseline,
        variant=ablated,
        opponents=opponents,
        iterations=1,
        seed=616161,
        pilot_config=PilotConfig(),
        max_turns=20,
        pair_id="rogshai-mvp-ablation",
    )
    assert ablation_metrics.actual_sample_size == 1

    for denied in (
        ("Ishai, Ojutai Dragonspeaker",),
        ("Rograkh, Son of Rohgahh",),
        ROGSHAI_COMMANDERS,
    ):
        denial = commander_denial_variant(baseline, denied, additional_tax=6)
        denial_metrics, _ = run_paired_structural_comparison(
            baseline=baseline,
            variant=denial,
            opponents=opponents,
            iterations=1,
            seed=717171,
            pilot_config=PilotConfig(),
            max_turns=20,
            pair_id="rogshai-mvp-denial-" + "-".join(denied),
        )
        assert denial_metrics.actual_sample_size == 1


def test_fresh_sensitivity_smoke_across_seed_and_pilot_strength(repo_root: Path) -> None:
    from commander_lab.models import PilotStrength

    fresh = build_fresh_rogshai_profile(
        repo_root,
        _development_mainboard(repo_root),
        variant_label="mvp-sensitivity",
    )
    opponents = _opponents(repo_root)
    registry = {deck.deck_id: deck for deck in (fresh, *opponents)}
    simulator = StructuralSimulator(registry)
    rows = []
    for seed in (808080, 808081):
        for strength in (PilotStrength.AVERAGE, PilotStrength.STRONG):
            configs = (PilotConfig(strength=strength),) * 4
            result = simulator.simulate(
                StructuralMatchConfig(
                    match_id=f"rogshai-mvp-sensitivity-{seed}-{strength.value}",
                    seed=seed,
                    deck_ids=(fresh.deck_id, *(deck.deck_id for deck in opponents)),
                    pilot_configs=configs,
                    limits=StructuralAbortLimits(
                        max_turns=20,
                        max_events=30_000,
                        max_no_progress_turns=15,
                    ),
                )
            )
            rows.append((seed, strength.value, result.player_metrics["p1"].placement))
    assert len(rows) == 4
    assert {row[0] for row in rows} == {808080, 808081}
    assert {row[1] for row in rows} == {"average", "strong"}
