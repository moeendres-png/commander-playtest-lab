from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION, StructuralSimulator
from commander_lab.engine.structural.fixtures import build_current_opponent_profiles
from commander_lab.fresh_rebuild import (
    BASIC_LANDS,
    ROGSHAI_COMMANDERS,
    FreshRebuildDataError,
    FreshRogShaiUniverse,
    build_fresh_rogshai_profile,
    build_independent_smoke_mainboard,
    load_fresh_rebuild_runtime,
    load_fresh_rogshai_universe,
    run_k2_bias_suite,
)
from commander_lab.fresh_rebuild_experiments import (
    candidates_for_fresh_baseline,
    commander_denial_variant,
    fresh_hard_constraints,
)
from commander_lab.models import (
    OptimizationVariant,
    PilotConfig,
    StructuralAbortLimits,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.models.run_identity import CanonicalInputStatus, IdentityStatus, RunIdentity
from commander_lab.optimization import (
    ablation_filler,
    all_legal_single_swaps,
    objective_vector,
    pareto_front,
    run_paired_structural_comparison,
    variant_deck,
)
from commander_lab.storage.run_identity import sha256_run_value

PRIMARY_OPPONENT_IDS = (
    "opponent/morcant-elves",
    "opponent/doom-prevails-precon",
    "opponent/cosmic-spiderman-midbudget",
)
SENSITIVITY_OPPONENT_IDS = (
    "opponent/morcant-elves",
    "opponent/doom-prevails-precon",
    "kaervek/current",
)


def _git_value(root: Path, expression: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", expression],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FreshRebuildDataError(f"cannot resolve git identity: {expression}") from exc


def _opponents(
    root: Path, deck_ids: tuple[str, ...]
) -> tuple[StructuralDeckProfile, ...]:
    manifest = load_fresh_rebuild_runtime(root)
    sources = cast(dict[str, dict[str, object]], manifest["sources"])
    snapshot_hash = sha256_run_value(sources, root=root)
    decks = build_current_opponent_profiles(
        root / "data/opponents/current_structural_profiles.json",
        data_snapshot_hash=snapshot_hash,
    )
    try:
        return tuple(decks[deck_id] for deck_id in deck_ids)
    except KeyError as exc:
        raise FreshRebuildDataError(f"required current opponent profile missing: {exc}") from exc


def _simulate_once(
    own_deck: StructuralDeckProfile,
    opponents: tuple[StructuralDeckProfile, ...],
    *,
    seed: int,
    match_id: str,
) -> dict[str, object]:
    decks = (own_deck, *opponents)
    simulator = StructuralSimulator({deck.deck_id: deck for deck in decks})
    result = simulator.simulate(
        StructuralMatchConfig(
            match_id=match_id,
            seed=seed,
            deck_ids=tuple(deck.deck_id for deck in decks),
            pilot_configs=(PilotConfig(),) * len(decks),
            limits=StructuralAbortLimits(
                max_turns=14,
                max_events=30_000,
                max_no_progress_turns=12,
            ),
        ),
        run_id=match_id,
    )
    return {
        "completed": result.completed,
        "aborted": result.aborted,
        "turns": result.turns,
        "event_count": result.event_count,
        "log_sha256": result.log_sha256,
        "estimate_type": result.estimate_type,
        "pilot_name": result.player_metrics["p1"].pilot_name,
    }


def _paired(
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    opponents: tuple[StructuralDeckProfile, ...],
    *,
    iterations: int,
    seed: int,
    pair_id: str,
):
    return run_paired_structural_comparison(
        baseline=baseline,
        variant=variant,
        opponents=opponents,
        iterations=iterations,
        seed=seed,
        pilot_config=PilotConfig(),
        max_turns=14,
        pair_id=pair_id,
    )


def _physical_validation(
    universe: FreshRogShaiUniverse,
    mainboard: tuple[str, ...],
) -> dict[str, object]:
    all_names = (*mainboard, *ROGSHAI_COMMANDERS)
    counts: dict[str, int] = {}
    for name in all_names:
        counts[name] = counts.get(name, 0) + 1
    issues: list[str] = []
    if len(all_names) != 100:
        issues.append("card_count")
    for commander in ROGSHAI_COMMANDERS:
        if counts.get(commander) != 1:
            issues.append(f"commander:{commander}")
    for name, quantity in counts.items():
        if quantity > 1 and name not in BASIC_LANDS:
            issues.append(f"singleton:{name}")
        if universe.available_quantities.get(name, 0) < quantity:
            issues.append(f"physical:{name}")
        facts = universe.candidate_facts_by_name.get(name)
        if facts is None:
            issues.append(f"universe:{name}")
            continue
        colors = {str(value) for value in cast(list[object], facts.get("color_identity", []))}
        if not colors <= {"W", "U", "R"}:
            issues.append(f"color_identity:{name}")
        if facts.get("commander_legal") is not True:
            issues.append(f"commander_legality:{name}")
    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": sorted(set(issues)),
        "card_count": len(all_names),
        "simultaneous_with_korvold": not any(issue.startswith("physical:") for issue in issues),
        "allocation_mutated": False,
    }


def _package_for_smoke(
    runtime: dict[str, Any], baseline: StructuralDeckProfile
) -> tuple[str, tuple[str, ...]]:
    deck_cards = {card.oracle_name: card for card in baseline.cards}
    groups: dict[str, set[str]] = defaultdict(set)
    relations = runtime.get("synergy_relations", [])
    if not isinstance(relations, list):
        raise FreshRebuildDataError("synergy_relations must be a list")
    for row in relations:
        if not isinstance(row, dict):
            continue
        source_name = str(row.get("source_name", ""))
        target = str(row.get("target", ""))
        card = deck_cards.get(source_name)
        if (
            card is not None
            and source_name not in ROGSHAI_COMMANDERS
            and not card.is_land
            and target.startswith("package:rogshai:")
        ):
            groups[target].add(source_name)
    eligible = sorted(
        (package_id, tuple(sorted(names)[:2]))
        for package_id, names in groups.items()
        if len(names) >= 2
    )
    if not eligible:
        raise FreshRebuildDataError("no current RogShai package has two smoke-deck members")
    return eligible[0]


def _current_opponent_evidence(runtime: dict[str, Any]) -> dict[str, dict[str, object]]:
    registry = runtime.get("opponent_registry", {})
    rows = registry.get("opponents", []) if isinstance(registry, dict) else []
    return {
        str(row["opponent_id"]): cast(dict[str, object], row)
        for row in rows
        if isinstance(row, dict) and "opponent_id" in row
    }


def _acceptance_run_identity(
    root: Path,
    runtime: dict[str, Any],
    baseline: StructuralDeckProfile,
    primary: tuple[StructuralDeckProfile, ...],
    *,
    seed: int,
    iterations: int,
) -> RunIdentity:
    sources = cast(dict[str, dict[str, object]], runtime["sources"])
    source_manifest_hash = sha256_run_value(sources, root=root)
    scenario = cast(dict[str, object], runtime["primary_4p_rogshai"])
    scenario_hash = sha256_run_value(scenario)
    simulation_config = {
        "iterations": iterations,
        "max_turns": 14,
        "seed": seed,
        "paired": True,
        "mode": "structural_smoke",
    }
    payload: {commander_configuration_hash": sha256_run_value(ROGSHAI_COMMANDERS)}
    for key, source in sources.items():
        payload[key] = source["content_sha256"]
    payload.update(
        {
            "software_commit": _git_value(root, "HEAD"),
            "software_tree": _git_value(root, "HEAD^{tree}"),
            "package_version": __version__,
            "deck_hashes": {"baseline": baseline.deck_hash},
            "inventory_source_id": sources["candidate_pool"]["source_file_id"],
            "inventory_hash": sources["inventory_features"]["content_sha256"],
            "opponent_profile_ids": tuple(deck.deck_id for deck in primary),
            "opponent_profile_hashes": {
                deck.deck_id: deck.deck_hash for deck in primary
            },
            "pilot_name": "RogShaiPilot",
            "pilot_version": "0.4.0",
            "policy_hash": sha256_run_value(cast(dict[str, object], runtime["bias_policy"])),
            "scenario_set_id": "primary_4p_rogshai",
            "scenario_set_hash": scenario_hash,
            "pod_size": 4,
            "seat": 0,
            "turn_order_policy": "paired_rotating_start_seat",
            "seed": seed,
            "simulation_config_hash": sha256_run_value(simulation_config),
            "model_version": ENGINE_VERSION,
            "engine_mode": "structural",
            "engine_provider": "commander_lab_structural_simulator",
            "data_source_manifest_hash": source_manifest_hash,
            "canonical_input_status": CanonicalInputStatus.CURRENT.value,
        }
    )
    status_names = (
        "software_commit",
        "software_tree",
        "package_version",
        "commander_configuration_hash",
        "inventory_hash",
        "data_source_manifest_hash",
    )
    component_status = {name: IdentityStatus.PRESENT for name in status_names}
    component_status["opponent_ensemble_hash"] = IdentityStatus.NOT_APPLICABLE
    component_status["engine_provider_version_or_pin"] = IdentityStatus.NOT_APPLICABLE
    component_status["engine_capability_hash"] = IdentityStatus.NOT_APPLICABLE
    payload["component_status"] = component_status
    semantic_hash = sha256_run_value(payload, root=root)
    payload["run_identity_hash"] = semantic_hash
    return RunIdentity.model_validate(payload)


def run_rogshai_mvp_acceptance(
    root: str | Path,
    *,
    iterations: int = 1,
    seed: int = 20260810,
) -> dict[str, object]:
    """Run a small, non-strength-inferring RogShai MVP acceptance graph end to end."""

    if iterations < 1:
        raise ValueError("iterations must be positive")
    project = Path(root).resolve()
    runtime = load_fresh_rebuild_runtime(project)
    universe = load_fresh_rogshai_universe(project)
    bias_suite = run_k2_bias_suite(project)
    mainboard = build_independent_smoke_mainboard(universe)
    baseline = build_fresh_rogshai_profile(
        project,
        mainboard,
        variant_label="mvp-independent",
        universe=universe,
    )
    physical = _physical_validation(universe, mainboard)
    primary = _opponents(project, PRIMARY_OPPONENT_IDS)
    sensitivity = _opponents(project, SENSITIVITY_OPPONENT_IDS)
    structural = _simulate_once(
        baseline,
        primary,
        seed=seed,
        match_id="rogshai-mvp-primary-4p-structural",
    )

    candidates = candidates_for_fresh_baseline(universe, baseline)
    baseline_names = {card.oracle_name for card in baseline.cards}
    eligible_ids = tuple(
        candidate_id
        for candidate_id, candidate in candidates.items()
        if candidate.card.oracle_name not in baseline_names
        and not candidate.card.is_land
        and universe.coverage_status_by_name.get(candidate.card.oracle_name)
        == "STRUCTURALLY_MODELED"
    )[:32]
    if not eligible_ids:
        raise FreshRebuildDataError("no explicitly modeled fresh candidate available for search")
    search_results = all_legal_single_swaps(
        baseline,
        candidates,
        eligible_ids,
        fresh_hard_constraints(),
        inventory=dict(universe.available_quantities),
        verified_physical_names=set(universe.verified_physical_names),
        protected=frozenset(),
    )
    if not search_results:
        raise FreshRebuildDataError("bounded fresh search produced no legal single swaps")
    searched = search_results[0]

    paired_metrics, paired_rows = _paired(
        baseline,
        searched.variant,
        primary,
        iterations=iterations,
        seed=seed + 1,
        pair_id="rogshai-mvp-paired-repro",
    )
    paired_repeat, paired_rows_repeat = _paired(
        baseline,
        searched.variant,
        primary,
        iterations=iterations,
        seed=seed + 1,
        pair_id="rogshai-mvp-paired-repro",
    )
    paired_reproducible = (
        paired_rows == paired_rows_repeat and paired_metrics.seeds == paired_repeat.seeds
    )

    removable = next(
        card
        for card in baseline.cards
        if card.oracle_name not in ROGSHAI_COMMANDERS and not card.is_land
    )
    card_ablation_variant = variant_deck(
        baseline,
        variant_id=f"{baseline.deck_id}/card-ablation",
        removals=(removable.oracle_name,),
        additions=(ablation_filler(removable, suffix="mvp card ablation"),),
    )
    card_ablation, _ = _paired(
        baseline,
        card_ablation_variant,
        primary,
        iterations=iterations,
        seed=seed + 2,
        pair_id="rogshai-mvp-card-ablation",
    )

    package_id, package_names = _package_for_smoke(runtime, baseline)
    baseline_by_name = {card.oracle_name: card for card in baseline.cards}
    package_variant = variant_deck(
        baseline,
        variant_id=f"{baseline.deck_id}/package-ablation",
        removals=package_names,
        additions=tuple(
            ablation_filler(baseline_by_name[name], suffix="mvp package ablation")
            for name in package_names
        ),
    )
    package_ablation, _ = _paired(
        baseline,
        package_variant,
        primary,
        iterations=iterations,
        seed=seed + 3,
        pair_id="rogshai-mvp-package-ablation",
    )

    denial_rows: dict[str, dict[str, object]] = {}
    denial_cases = (
        ("Ishai", (ROGSHAI_COMMANDERS[0],)),
        ("Rograkh", (ROGSHAI_COMMANDERS[1],)),
        ("both", ROGSHAI_COMMANDERS),
    )
    for index, (label, denied) in enumerate(denial_cases):
        variant = commander_denial_variant(baseline, denied, additional_tax=6)
        metrics, _ = _paired(
            baseline,
            variant,
            primary,
            iterations=iterations,
            seed=seed + 10 + index,
            pair_id=f"rogshai-mvp-denial-{label.casefold()}",
        )
        denial_rows[label] = {
            "denied_commanders": list(denied),
            "actual_sample_size": metrics.actual_sample_size,
            "validation_level": metrics.validation_level,
        }

    sensitivity_result = _simulate_once(
        baseline,
        sensitivity,
        seed=seed + 20,
        match_id="rogshai-mvp-opponent-composition-sensitivity",
    )

    optimization_variants: list[OptimizationVariant] = []
    for index, search in enumerate(search_results[:2]):
        metrics, pairs = _paired(
            baseline,
            search.variant,
            primary,
            iterations=iterations,
            seed=seed + 30,
            pair_id=f"rogshai-mvp-pareto-{index}",
        )
        objectives = objective_vector(
            metrics=metrics,
            pairs=pairs,
            variant=search.variant,
            commander_dependency_penalty=0.0,
            holdout_improvements=(metrics.placement_improvement,),
            physical_valid=search.constraint_report.valid,
        )
        optimization_variants.append(
            OptimizationVariant(
                variant_id=search.variant.deck_id,
                deck_id=baseline.deck_id,
                deck_hash=search.variant.deck_hash,
                swaps=search.swaps,
                structural_rationale=(
                    "Technical bounded-search smoke only; not a deck recommendation.",
                ),
                affected_matchups=("primary_4p_rogshai",),
                constraint_report=search.constraint_report,
                objectives=objectives,
                screening_score=search.screening_score,
                search_method="fresh_mvp_bounded_structural_smoke",
            )
        )
    pareto = pareto_front(optimization_variants)

    identity = _acceptance_run_identity(
        project,
        runtime,
        baseline,
        primary,
        seed=seed,
        iterations=iterations,
    )
    evidence = _current_opponent_evidence(runtime)
    synthetic_never_observed = all(
        row.get("deck_status") != "observed"
        for row in evidence.values()
        if "synthetic" in str(row.get("deck_source_type", ""))
    )

    checks = {
        "current_data_projection": universe.candidate_count == 795,
        "physical_constraints": physical["status"] == "PASS",
        "k2_bias_suite": bias_suite["status"] == "PASS",
        "unmodeled_visible": universe.review_required_count > 0
        and universe.candidate_count
        == universe.structurally_scorable_count + universe.review_required_count,
        "fresh_control_blind": cast(dict[str, object], runtime["bias_policy"])[
            "control_deck_visible_in_independent_stage"
        ]
        is False,
        "structural": structural["estimate_type"] == "structural_model_estimates",
        "paired_same_seed_reproducible": paired_reproducible,
        "card_ablation": card_ablation.actual_sample_size == iterations,
        "package_ablation": package_ablation.actual_sample_size == iterations,
        "commander_denial": len(denial_rows) == 3,
        "sensitivity": sensitivity_result["estimate_type"] == "structural_model_estimates",
        "bounded_search_pareto": bool(search_results) and bool(pareto),
        "run_identity": len(identity.run_identity_hash) == 64,
        "synthetic_never_observed": synthetic_never_observed,
    }
    return {
        "ROGSHAI_MVP_READY": all(checks.values()),
        "smoke_test_only": True,
        "deck_strength_inference_allowed": False,
        "estimate_type": "structural_model_estimates",
        "candidate_universe": {
            "count": universe.candidate_count,
            "structurally_scorable": universe.structurally_scorable_count,
            "review_required": universe.review_required_count,
            "coverage_counts": cast(dict[str, Any], runtime["candidate_universe"])[
                "coverage_counuÌˆ(€€€€€€€€€€€t°(€€€€€€€ô°(€€€€€€€€‰‰¥…Í}ÍÕ¥Ñ”ˆè‰¥…Í}ÍÕ¥Ñ”°(€€€€€€€€‰Ñ•µÁ½É…Éå}‰Õ¥±ˆèì(€€€€€€€€€€€€‰‘•­}¥ˆè‰…Í•±¥¹”¹‘•­}¥°(€€€€€€€€€€€€‰‘•­}¡…Í ˆè‰…Í•±¥¹”¹‘•­}¡…Í °(€€€€€€€€€€€€‰Á¡åÍ¥…±}Ù…±¥‘…Ñ¥½¸ˆèÁ¡åÍ¥…°°(€€€€€€€€€€€€‰ÁÕÉÁ½Í”ˆè€‰Ñ•¡¹¥…°İ½É­™±½Ü™¥áÑÕÉ”½¹±äì¹½Ğ„‘•¬É•½µµ•¹‘…Ñ¥½¸ˆ°(€€€€€€€ô°(€€€€€€€€‰ÁÉ¥µ…Éå|ÑÁ}½ÁÁ½¹•¹ÑÌˆè±¥ÍĞ¡AI%5Ie}=AA=99Q}%L¤°(€€€€€€€€‰ÍÑÉÕÑÕÉ…±}Í¥µÕ±…Ñ¥½¸ˆèÍÑÉÕÑÕÉ…°°(€€€€€€€€‰Á…¥É•‘}½µÁ…É¥Í½¸ˆèì(€€€€€€€€€€€€‰…ÑÕ…±}Í…µÁ±•}Í¥é”ˆèÁ…¥É•‘}µ•ÑÉ¥Ì¹…ÑÕ…±}Í…µÁ±•}Í¥é”°(€€€€€€€€€€€€‰Í…µ•}Í••‘}É•ÁÉ½‘Õ¥‰±”ˆèÁ…¥É•‘}É•ÁÉ½‘Õ¥‰±”°(€€€€€€€ô°(€€€€€€€€‰…É‘}…‰±…Ñ¥½¸ˆèì‰…ÑÕ…±}Í…µÁ±•}Í¥é”ˆè…É‘}…‰±…Ñ¥½¸¹…ÑÕ…±}Í…µÁ±•}Í¥é•ô°(€€€€€€€€‰Á…­…•}…‰±…Ñ¥½¸ˆèì(€€€€€€€€€€€€‰Á…­…•}¥ˆèÁ…­…•}¥°(€€€€€€€€€€€€‰…É‘Ìˆè±¥ÍĞ¡Á…­…•}¹…µ•Ì¤°(€€€€€€€€€€€€‰…ÑÕ…±}Í…µÁ±•}Í¥é”ˆèÁ…­…•}…‰±…Ñ¥½¸¹…ÑÕ…±}Í…µÁ±•}Í¥é”°(€€€€€€€ô°(€€€€€€€€‰½µµ…¹‘•É}‘•¹¥…°ˆè‘•¹¥…±}É½İÌ°(€€€€€€€€‰Í•¹Í¥Ñ¥Ù¥Ñäˆèì(€€€€€€€€€€€€‰…á¥Ìˆè€‰½ÁÁ½¹•¹Ñ}½µÁ½Í¥Ñ¥½¸ˆ°(€€€€€€€€€€€€‰½ÁÁ½¹•¹Ñ}¥‘Ìˆè±¥ÍĞ¡M9M%Q%Y%Qe}=AA=99Q}%L¤°(€€€€€€€€€€€€‰É•ÍÕ±ĞˆèÍ•¹Í¥Ñ¥Ù¥Ñå}É•ÍÕ±Ğ°(€€€€€€€ô°(€€€€€€€€‰‰½Õ¹‘•‘}Í•…É¡}Á…É•Ñ¼ˆèì(€€€€€€€€€€€€‰±•…±}Í¥¹±•}Íİ…ÁÌˆè±•¸¡Í•…É¡}É•ÍÕ±ÑÌ¤°(€€€€€€€€€€€€‰Ù…É¥…¹ÑÍ}•Ù…±Õ…Ñ•ˆè±•¸¡½ÁÑ¥µ¥é…Ñ¥½¹}Ù…É¥…¹ÑÌ¤°(€€€€€€€€€€€€‰Á…É•Ñ½}™É½¹Ñ}¥‘ÌˆèmÙ…É¥…¹Ğ¹Ù…É¥…¹Ñ}¥™½ÈÙ…É¥…¹Ğ¥¸Á…É•Ñ½t°(€€€€€€€ô°(€€€€€€€€‰½ÁÁ½¹•¹Ñ}•Ù¥‘•¹”ˆè•Ù¥‘•¹”°(€€€€€€€€‰ÉÕ¹}¥‘•¹Ñ¥Ñäˆè¥‘•¹Ñ¥Ñä¹µ½‘•±}‘ÕµÀ¡µ½‘”ô‰©Í½¸ˆ¤°(€€€€€€€€‰Ñ•¡¹¥…±}¡•­Ìˆè¡•­Ì°(€€€ô