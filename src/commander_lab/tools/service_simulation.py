from __future__ import annotations

import uuid
from statistics import fmean
from typing import TYPE_CHECKING, Any

from commander_lab.cut_frontier import build_static_swap_rows
from commander_lab.engine.structural import (
    run_structural_batch,
)
from commander_lab.models import (
    CardAblationInput,
    CommanderDenialInput,
    CompareDecksInput,
    GoldfishInput,
    HoldoutInput,
    InspectDeckInput,
    MatchupBatchInput,
    PackageAblationInput,
    PairedVariantInput,
    PilotConfig,
    RecommendUpgradesInput,
    SensitivityInput,
    StructuralBatchConfig,
    ToolResponse,
    ValidateDeckInput,
)
from commander_lab.optimization import (
    ablation_filler,
    profile_score,
    role_summary,
    run_paired_structural_comparison,
    variant_deck,
)
from commander_lab.packages import PackageExtractionError
from commander_lab.storage import (
    sha256_value,
)

if TYPE_CHECKING:
    pass

from .service_core import (
    ServiceCore,
    ToolExecutionError,
    _deterministic_structural_run_id,
)


class ServiceSimulationMixin(ServiceCore):
    def validate_deck(self, request: ValidateDeckInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._validate_deck_payload(request)

        return self._invoke("validate_deck", request, work, deck_ids=(request.deck_id,))

    def inspect_deck(self, request: InspectDeckInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            scores = sorted(
                ((card.oracle_name, profile_score(card)) for card in deck.cards),
                key=lambda item: item[1],
            )
            payload: dict[str, Any] = {
                "deck_id": deck.deck_id,
                "deck_hash": deck.deck_hash,
                "commanders": deck.commander_names,
                "strategy": deck.commander_strategy,
                "card_count": len(deck.cards),
                "role_counts": role_summary(deck),
                "lowest_structural_floor": [
                    {"card": name, "profile_score": score} for name, score in scores[:10]
                ],
            }
            if request.deck_id in self.ACTIVE_OWN_DECK_IDS:
                package_result = self._package_extractor().packages_for_deck(
                    request.deck_id, include_machine_candidates=False
                )
                payload["package_diagnostics"] = {
                    "archetype_profile": package_result["archetype_profile"],
                    "evaluations": package_result["evaluations"],
                    "automatic_deck_application": False,
                }
            if request.include_cards:
                payload["cards"] = [card.model_dump(mode="json") for card in deck.cards]
            return payload

        return self._invoke("inspect_deck", request, work, deck_ids=(request.deck_id,))

    def run_goldfish(self, request: GoldfishInput) -> ToolResponse:
        output = self.root / "data/runs/tool_runs" / f"goldfish-{uuid.uuid4().hex[:8]}"
        simulation_run_id = _deterministic_structural_run_id("goldfish", request)

        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            config = StructuralBatchConfig(
                run_id=simulation_run_id,
                seed=request.seed,
                iterations=request.iterations,
                deck_ids=(request.deck_id,),
                workers=request.workers,
                pilot_configs=(
                    PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                ),
                output_directory=str(output),
            )
            return run_structural_batch(config, self.decks).aggregate

        return self._invoke(
            "run_goldfish",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
            log_dir=str(output / "events"),
        )

    def run_matchup_batch(self, request: MatchupBatchInput) -> ToolResponse:
        output = self.root / "data/runs/tool_runs" / f"matchup-{uuid.uuid4().hex[:8]}"
        simulation_run_id = _deterministic_structural_run_id("matchup", request)

        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            for deck_id in request.deck_ids:
                self._deck(deck_id)
            config = StructuralBatchConfig(
                run_id=simulation_run_id,
                seed=request.seed,
                iterations=request.iterations,
                deck_ids=request.deck_ids,
                workers=request.workers,
                pilot_configs=tuple(
                    PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode)
                    for _ in request.deck_ids
                ),
                output_directory=str(output),
            )
            batch = run_structural_batch(config, self.decks)
            return {"aggregate": batch.aggregate, "result_path": batch.result_path}

        return self._invoke(
            "run_matchup_batch",
            request,
            work,
            deck_ids=request.deck_ids,
            seed=request.seed,
            iterations=request.iterations,
            log_dir=str(output / "events"),
        )

    def compare_decks(self, request: CompareDecksInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            opponents = tuple(self._deck(deck_id) for deck_id in request.opponent_deck_ids)
            baseline = self._deck(request.deck_ids[0])
            variant = self._deck(request.deck_ids[1])
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=opponents,
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"compare-{baseline.deck_id}-{variant.deck_id}",
                workers=request.workers,
            )
            return {"comparison": metrics.as_dict(), "pair_sample": pairs[:20]}

        ids = (*request.deck_ids, *request.opponent_deck_ids)
        return self._invoke(
            "compare_decks",
            request,
            work,
            deck_ids=ids,
            seed=request.seed,
            iterations=request.iterations,
        )

    def compare_variants_paired(self, request: PairedVariantInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline, variant, swaps = self._build_variant(request)
            opponents = tuple(self._deck(deck_id) for deck_id in request.opponent_deck_ids)
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=opponents,
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"paired-{variant.deck_hash[:12]}",
                workers=request.workers,
            )
            return {
                "baseline_deck_hash": baseline.deck_hash,
                "variant_deck_hash": variant.deck_hash,
                "swaps": swaps,
                "comparison": metrics.as_dict(),
                "pair_sample": pairs[:20],
            }

        return self._invoke(
            "compare_variants_paired",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_card_ablation(self, request: CardAblationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            card = next(
                (card for card in baseline.cards if card.oracle_name == request.card_name), None
            )
            if card is None:
                raise ToolExecutionError(f"card not found: {request.card_name}")
            variant = variant_deck(
                baseline,
                variant_id=f"{request.deck_id}/ablation/{sha256_value(request.card_name)[:12]}",
                removals=(request.card_name,),
                additions=(ablation_filler(card),),
            )
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"ablation-{request.card_name}",
                workers=request.workers,
            )
            contribution = -metrics.placement_improvement
            return {
                "card_name": request.card_name,
                "ablation_comparison": metrics.as_dict(),
                "estimated_card_contribution": {
                    "placement_value": contribution,
                    "interpretation": "positive means the original card improved average placement",
                },
                "pair_sample": pairs[:20],
            }

        return self._invoke(
            "run_card_ablation",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_package_ablation(self, request: PackageAblationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            originals = []
            fillers = []
            selected_names = request.card_names
            if request.package_id:
                try:
                    selected_names = self._package_extractor().package_cards_for_ablation(
                        request.deck_id, request.package_id
                    )
                except PackageExtractionError as exc:
                    raise ToolExecutionError(str(exc)) from exc
            for name in selected_names:
                card = next((card for card in baseline.cards if card.oracle_name == name), None)
                if card is None:
                    raise ToolExecutionError(f"card not found: {name}")
                originals.append(name)
                fillers.append(ablation_filler(card, suffix="package ablation"))
            variant = variant_deck(
                baseline,
                variant_id=f"{request.deck_id}/package-ablation/{sha256_value(originals)[:12]}",
                removals=originals,
                additions=fillers,
            )
            metrics, _ = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"package-{sha256_value(originals)[:12]}",
                workers=request.workers,
            )
            return {
                "package_id": request.package_id,
                "cards": originals,
                "ablation_comparison": metrics.as_dict(),
                "automatic_deck_application": False,
                "estimate_type": "structural_model_estimates",
            }

        return self._invoke(
            "run_package_ablation",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_commander_denial(self, request: CommanderDenialInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            denied_commanders = request.denied_commanders or baseline.commander_names
            if len(denied_commanders) != len(set(denied_commanders)):
                raise ToolExecutionError("denied commander identities must be unique")
            unknown = set(denied_commanders) - set(baseline.commander_names)
            if unknown:
                raise ToolExecutionError(f"unknown denied commanders: {sorted(unknown)}")
            suppress_synergy = request.suppress_commander_synergy and set(denied_commanders) == set(
                baseline.commander_names
            )
            variant = variant_deck(
                baseline,
                variant_id=(
                    f"{request.deck_id}/commander-denial/{sha256_value(denied_commanders)[:12]}"
                ),
                additional_commander_tax=request.additional_commander_tax,
                denied_commanders=denied_commanders,
                suppress_commander_synergy=suppress_synergy,
            )
            metrics, _ = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"denial-{request.deck_id}-{sha256_value(denied_commanders)[:8]}",
                workers=request.workers,
            )
            return {
                "additional_commander_tax": request.additional_commander_tax,
                "denied_commanders": list(denied_commanders),
                "commander_synergy_suppressed": suppress_synergy,
                "individual_denial_limitation": (
                    "card-level commander_synergy is aggregate and remains unsuppressed for "
                    "single-commander denial; only that commander's cast cost is taxed"
                    if len(denied_commanders) == 1
                    else None
                ),
                "comparison": metrics.as_dict(),
                "commander_dependency_penalty": -metrics.placement_improvement,
            }

        return self._invoke(
            "run_commander_denial",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_holdout(self, request: HoldoutInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.iterations * len(request.holdout_pods), request.approval_token
            )
            baseline, variant, swaps = self._build_variant(request)
            results: list[dict[str, Any]] = []
            for index, pod in enumerate(request.holdout_pods):
                opponents = tuple(self._deck(deck_id) for deck_id in pod)
                metrics, _ = run_paired_structural_comparison(
                    baseline=baseline,
                    variant=variant,
                    opponents=opponents,
                    iterations=request.iterations,
                    seed=request.seed + index,
                    pilot_config=PilotConfig(
                        strength=request.pilot_strength, mode=request.pilot_mode
                    ),
                    max_turns=request.max_turns,
                    pair_id=f"holdout-{variant.deck_hash[:8]}-{index}",
                    workers=request.workers,
                )
                results.append({"pod": pod, "comparison": metrics.as_dict()})
            improvements = [row["comparison"]["placement_improvement"] for row in results]
            return {
                "swaps": swaps,
                "holdouts": results,
                "mean_placement_improvement": fmean(improvements) if improvements else 0.0,
                "all_holdouts_nonnegative": all(value >= 0 for value in improvements),
            }

        return self._invoke(
            "run_holdout",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_sensitivity(self, request: SensitivityInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            total = len(request.seeds) * len(request.pilot_strengths) * request.iterations
            self._check_iterations(total, request.approval_token)
            rows = []
            for seed in request.seeds:
                for strength in request.pilot_strengths:
                    match = MatchupBatchInput(
                        deck_ids=request.deck_ids,
                        seed=seed,
                        iterations=request.iterations,
                        workers=request.workers,
                        pilot_strength=strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                    )
                    response = self.run_matchup_batch(match)
                    rows.append(
                        {
                            "seed": seed,
                            "pilot_strength": strength.value,
                            "aggregate": response.result.get("aggregate"),
                        }
                    )
            return {"runs": rows}

        return self._invoke(
            "run_sensitivity",
            request,
            work,
            deck_ids=request.deck_ids,
            iterations=request.iterations,
        )

    def recommend_upgrades(self, request: RecommendUpgradesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            deck = self._deck(request.deck_id)
            candidate_ids = set(request.candidate_ids) if request.candidate_ids else None
            candidates = {
                candidate_id: candidate
                for candidate_id, candidate in self.candidates.items()
                if candidate_ids is None or candidate_id in candidate_ids
            }
            rows = build_static_swap_rows(
                deck,
                candidates,
                protected=set(self.protected_cards.get(request.deck_id, [])),
                max_cut_hypotheses=max(16, min(32, request.max_recommendations)),
            )
            return {
                "method": "role_profile_screening_only",
                "cut_frontier_method": "diverse_cut_hypothesis_and_role_package_profile_screening_only",
                "recommendations": rows[: request.max_recommendations],
                "warning": "Candidates are not confirmed until paired and robustness validation pass.",
            }

        return self._invoke("recommend_upgrades", request, work, deck_ids=(request.deck_id,))
