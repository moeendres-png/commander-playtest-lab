from __future__ import annotations

import json
import subprocess
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Callable

from commander_lab.analysis import DeckValidator, validate_collection_quantities
from commander_lab.cards.catalog import CardCatalog
from commander_lab.engine.structural import ENGINE_VERSION, load_project_structural_decks, run_structural_batch
from commander_lab.importers import RealPlaytestImporter
from commander_lab.models import (
    CalibrateInput,
    CardAblationInput,
    Collection,
    CommanderDenialInput,
    CompareDecksInput,
    CostLimits,
    CreateReportInput,
    GoldfishInput,
    HoldoutInput,
    IngestPlaytestInput,
    InspectDeckInput,
    MatchupBatchInput,
    PackageAblationInput,
    PairedVariantInput,
    PilotConfig,
    RecommendUpgradesInput,
    SearchVariantsInput,
    SensitivityInput,
    StructuralBatchConfig,
    StructuralDeckProfile,
    SwapMatrixInput,
    ToolExecutionMetadata,
    ToolResponse,
    ToolStatus,
    ValidateDeckInput,
    ValidateUpgradeInput,
)
from commander_lab.optimization import (
    ablation_filler,
    profile_score,
    role_summary,
    run_paired_structural_comparison,
    variant_deck,
)
from commander_lab.storage import load_model, sha256_value
from commander_lab.models import Deck

from .candidates import load_candidate_profiles


class ToolExecutionError(RuntimeError):
    pass


class ApprovalRequired(ToolExecutionError):
    pass


class CommanderToolService:
    """Deterministic local Function Tool service.

    The service is the sole mutation boundary for local artifacts. Agent code receives only these
    methods and cannot directly mutate game state. Simulation results remain structural estimates.
    """

    def __init__(self, root: str | Path, *, limits: CostLimits | None = None) -> None:
        self.root = Path(root).resolve()
        self.limits = limits or self._load_limits()
        self.decks = load_project_structural_decks(self.root, include_synthetic_fixtures=True)
        self.candidates = load_candidate_profiles(self.root)
        protected_path = self.root / "config/protected_cards.json"
        self.protected_cards = json.loads(protected_path.read_text(encoding="utf-8")) if protected_path.exists() else {}
        self.manifest = json.loads((self.root / "data/decks/manifest.json").read_text(encoding="utf-8"))
        self.trace_dir = self.root / "data/runs/openai_traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.root / "data/runs/reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _load_limits(self) -> CostLimits:
        path = self.root / "config/openai_workflow.json"
        if not path.exists():
            return CostLimits()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CostLimits.model_validate(payload.get("budgets", payload))

    @property
    def git_commit(self) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    def _check_iterations(self, iterations: int, approval_token: str | None) -> None:
        if iterations > self.limits.hard_max_iterations:
            raise ToolExecutionError(
                f"iterations {iterations} exceed hard maximum {self.limits.hard_max_iterations}"
            )
        if iterations > self.limits.approval_threshold_iterations and approval_token != "APPROVED_LARGE_RUN":
            raise ApprovalRequired(
                f"iterations {iterations} require approval token APPROVED_LARGE_RUN"
            )

    def _deck(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self.decks[deck_id]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown structural deck: {deck_id}") from exc


    def _is_protected(self, deck_id: str, card_name: str) -> bool:
        return card_name in set(self.protected_cards.get(deck_id, []))

    def _validate_swap_policy(self, deck_id: str, remove: str, candidate_card: Any) -> None:
        if not self._is_protected(deck_id, remove):
            return
        deck = self._deck(deck_id)
        original = next((card for card in deck.cards if card.oracle_name == remove), None)
        if original is None:
            raise ToolExecutionError(f"protected card not found in deck: {remove}")
        same_role_upgrade = original.roles.issubset(candidate_card.roles) and profile_score(candidate_card) > profile_score(original)
        if not same_role_upgrade:
            raise ToolExecutionError(
                f"{remove} is protected by current deckbuilding rules and may only be tested against "
                "a clear direct upgrade covering the same roles"
            )

    def _candidate(self, candidate_id: str, deck_id: str):
        try:
            candidate = self.candidates[candidate_id]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown upgrade candidate: {candidate_id}") from exc
        if candidate.allowed_deck_ids and deck_id not in candidate.allowed_deck_ids:
            raise ToolExecutionError(f"candidate {candidate_id} is not allowed for {deck_id}")
        return candidate

    def _metadata(
        self,
        *,
        tool_name: str,
        invocation_id: str,
        started: float,
        scenario: object,
        deck_ids: tuple[str, ...] = (),
        seed: int | None = None,
        iterations: int | None = None,
        log_dir: str | None = None,
    ) -> ToolExecutionMetadata:
        return ToolExecutionMetadata(
            tool_name=tool_name,
            invocation_id=invocation_id,
            created_at=datetime.now(UTC),
            git_commit=self.git_commit,
            engine_version=ENGINE_VERSION,
            data_snapshot_hash=str(self.manifest["data_snapshot_hash"]),
            deck_hashes={deck_id: self._deck(deck_id).deck_hash for deck_id in deck_ids if deck_id in self.decks},
            scenario_hash=sha256_value(scenario),
            seed=seed,
            iterations=iterations,
            elapsed_seconds=time.monotonic() - started,
            deterministic_game_log_directory=log_dir,
            openai_trace_directory=str(self.trace_dir),
        )

    def _invoke(
        self,
        tool_name: str,
        request: Any,
        fn: Callable[[], dict[str, Any]],
        *,
        deck_ids: tuple[str, ...] = (),
        seed: int | None = None,
        iterations: int | None = None,
        log_dir: str | None = None,
    ) -> ToolResponse:
        started = time.monotonic()
        invocation_id = f"{tool_name}-{uuid.uuid4().hex[:12]}"
        try:
            result = fn()
            elapsed = time.monotonic() - started
            if elapsed > self.limits.max_simulation_seconds:
                raise ToolExecutionError(
                    f"tool exceeded simulation budget: {elapsed:.3f}s > {self.limits.max_simulation_seconds:.3f}s"
                )
            status = ToolStatus.COMPLETED
            warnings: list[str] = []
            errors: list[str] = []
        except ApprovalRequired as exc:
            result = {}
            status = ToolStatus.REQUIRES_APPROVAL
            warnings = [str(exc)]
            errors = []
        except Exception as exc:  # Tool boundary intentionally converts failures.
            result = {}
            status = ToolStatus.FAILED
            warnings = []
            errors = [f"{type(exc).__name__}: {exc}"]
        metadata = self._metadata(
            tool_name=tool_name,
            invocation_id=invocation_id,
            started=started,
            scenario=request.model_dump(mode="json") if hasattr(request, "model_dump") else request,
            deck_ids=deck_ids,
            seed=seed,
            iterations=iterations,
            log_dir=log_dir,
        )
        return ToolResponse(status=status, metadata=metadata, result=result, warnings=warnings, errors=errors)

    def validate_deck(self, request: ValidateDeckInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            spec = self.manifest["decks"].get(request.deck_id)
            if spec is None:
                raise ToolExecutionError(f"validation is available only for local current decks: {request.deck_id}")
            filename = spec["normalized_file"]
            deck = load_model(self.root / "data/decks" / filename, Deck)
            catalog = CardCatalog.from_json(self.root / "data/cards/oracle_subset.json")
            report = DeckValidator(catalog).validate(deck)
            allocation = None
            if request.include_physical_allocation:
                collection = Collection.model_validate_json(
                    (self.root / "data/collections/current_deck_allocations.json").read_text(encoding="utf-8")
                )
                allocation = validate_collection_quantities(collection, [deck]).model_dump(mode="json")
            return {
                "deck_id": request.deck_id,
                "deck_hash": deck.deck_hash,
                "validation": report.model_dump(mode="json"),
                "physical_allocation": allocation,
            }
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
            if request.include_cards:
                payload["cards"] = [card.model_dump(mode="json") for card in deck.cards]
            return payload
        return self._invoke("inspect_deck", request, work, deck_ids=(request.deck_id,))

    def run_goldfish(self, request: GoldfishInput) -> ToolResponse:
        output = self.root / "data/runs/tool_runs" / f"goldfish-{uuid.uuid4().hex[:8]}"
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            config = StructuralBatchConfig(
                run_id=output.name,
                seed=request.seed,
                iterations=request.iterations,
                deck_ids=(request.deck_id,),
                workers=request.workers,
                pilot_configs=(PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),),
                output_directory=str(output),
            )
            return run_structural_batch(config, self.decks).aggregate
        return self._invoke(
            "run_goldfish", request, work, deck_ids=(request.deck_id,), seed=request.seed,
            iterations=request.iterations, log_dir=str(output / "events")
        )

    def run_matchup_batch(self, request: MatchupBatchInput) -> ToolResponse:
        output = self.root / "data/runs/tool_runs" / f"matchup-{uuid.uuid4().hex[:8]}"
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            for deck_id in request.deck_ids:
                self._deck(deck_id)
            config = StructuralBatchConfig(
                run_id=output.name,
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
            "run_matchup_batch", request, work, deck_ids=request.deck_ids, seed=request.seed,
            iterations=request.iterations, log_dir=str(output / "events")
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
            )
            return {"comparison": metrics.as_dict(), "pair_sample": pairs[:20]}
        ids = (*request.deck_ids, *request.opponent_deck_ids)
        return self._invoke("compare_decks", request, work, deck_ids=ids, seed=request.seed, iterations=request.iterations)

    def _build_variant(self, request: PairedVariantInput) -> tuple[StructuralDeckProfile, StructuralDeckProfile, list[dict[str, Any]]]:
        baseline = self._deck(request.deck_id)
        additions = []
        removals = []
        swap_rows = []
        for swap in request.swaps:
            candidate = self._candidate(swap.add_candidate_id, request.deck_id)
            self._validate_swap_policy(request.deck_id, swap.remove, candidate.card)
            removals.append(swap.remove)
            additions.append(candidate.card)
            swap_rows.append({
                "remove": swap.remove,
                "add": candidate.card.oracle_name,
                "candidate_id": candidate.candidate_id,
                "physical_status": candidate.physical_status,
            })
        variant = variant_deck(
            baseline,
            variant_id=f"{request.deck_id}/variant/{sha256_value(swap_rows)[:12]}",
            removals=removals,
            additions=additions,
        )
        return baseline, variant, swap_rows

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
            )
            return {
                "baseline_deck_hash": baseline.deck_hash,
                "variant_deck_hash": variant.deck_hash,
                "swaps": swaps,
                "comparison": metrics.as_dict(),
                "pair_sample": pairs[:20],
            }
        return self._invoke(
            "compare_variants_paired", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def run_card_ablation(self, request: CardAblationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            card = next((card for card in baseline.cards if card.oracle_name == request.card_name), None)
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
        return self._invoke("run_card_ablation", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def run_package_ablation(self, request: PackageAblationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            originals = []
            fillers = []
            for name in request.card_names:
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
                baseline=baseline, variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations, seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns, pair_id=f"package-{sha256_value(originals)[:12]}",
            )
            return {"cards": originals, "ablation_comparison": metrics.as_dict()}
        return self._invoke("run_package_ablation", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def run_commander_denial(self, request: CommanderDenialInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            variant = variant_deck(
                baseline,
                variant_id=f"{request.deck_id}/commander-denial/{request.additional_commander_tax}",
                additional_commander_tax=request.additional_commander_tax,
                suppress_commander_synergy=request.suppress_commander_synergy,
            )
            metrics, _ = run_paired_structural_comparison(
                baseline=baseline, variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations, seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns, pair_id=f"denial-{request.deck_id}",
            )
            return {
                "additional_commander_tax": request.additional_commander_tax,
                "commander_synergy_suppressed": request.suppress_commander_synergy,
                "comparison": metrics.as_dict(),
                "commander_dependency_penalty": -metrics.placement_improvement,
            }
        return self._invoke("run_commander_denial", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def generate_swap_matrix(self, request: SwapMatrixInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            cells = len(request.remove_cards) * len(request.add_candidate_ids)
            if cells > self.limits.max_variants:
                raise ToolExecutionError(f"swap matrix has {cells} cells; limit is {self.limits.max_variants}")
            total = cells * request.iterations_per_cell
            self._check_iterations(total, request.approval_token)
            rows = []
            for remove in request.remove_cards:
                for candidate_id in request.add_candidate_ids:
                    paired = PairedVariantInput(
                        deck_id=request.deck_id,
                        swaps=({"remove": remove, "add_candidate_id": candidate_id},),
                        opponent_deck_ids=request.opponent_deck_ids,
                        seed=request.seed,
                        iterations=request.iterations_per_cell,
                        workers=1,
                        pilot_strength=request.pilot_strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                    )
                    response = self.compare_variants_paired(paired)
                    rows.append({
                        "remove": remove,
                        "candidate_id": candidate_id,
                        "status": response.status.value,
                        "comparison": response.result.get("comparison"),
                    })
            rows.sort(key=lambda row: (row["comparison"] or {}).get("placement_improvement", -99), reverse=True)
            return {"cells": rows, "best": rows[0] if rows else None}
        return self._invoke("generate_swap_matrix", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations_per_cell)

    def search_variants(self, request: SearchVariantsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            cuts = [
                card.oracle_name for card in sorted(deck.cards, key=profile_score)
                if card.oracle_name not in deck.commander_names
                and not card.is_land
                and not self._is_protected(request.deck_id, card.oracle_name)
            ][:request.max_cuts]
            candidate_ids = request.candidate_ids or tuple(
                candidate_id for candidate_id, candidate in self.candidates.items()
                if not candidate.allowed_deck_ids or request.deck_id in candidate.allowed_deck_ids
            )
            cells = min(len(cuts) * len(candidate_ids), self.limits.max_variants)
            self._check_iterations(cells * request.iterations, request.approval_token)
            results = []
            for remove in cuts:
                for candidate_id in candidate_ids:
                    if len(results) >= self.limits.max_variants:
                        break
                    paired = PairedVariantInput(
                        deck_id=request.deck_id,
                        swaps=({"remove": remove, "add_candidate_id": candidate_id},),
                        opponent_deck_ids=request.opponent_deck_ids,
                        seed=request.seed,
                        iterations=request.iterations,
                        workers=1,
                        pilot_strength=request.pilot_strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                    )
                    response = self.compare_variants_paired(paired)
                    if response.status == ToolStatus.COMPLETED:
                        results.append({
                            "remove": remove,
                            "candidate_id": candidate_id,
                            "comparison": response.result["comparison"],
                            "variant_deck_hash": response.result["variant_deck_hash"],
                        })
            results.sort(key=lambda row: row["comparison"]["placement_improvement"], reverse=True)
            return {"searched": len(results), "variants": results[:request.max_results]}
        return self._invoke("search_variants", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def run_holdout(self, request: HoldoutInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations * len(request.holdout_pods), request.approval_token)
            baseline, variant, swaps = self._build_variant(request)
            results = []
            for index, pod in enumerate(request.holdout_pods):
                opponents = tuple(self._deck(deck_id) for deck_id in pod)
                metrics, _ = run_paired_structural_comparison(
                    baseline=baseline, variant=variant, opponents=opponents,
                    iterations=request.iterations, seed=request.seed + index,
                    pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                    max_turns=request.max_turns, pair_id=f"holdout-{variant.deck_hash[:8]}-{index}",
                )
                results.append({"pod": pod, "comparison": metrics.as_dict()})
            improvements = [row["comparison"]["placement_improvement"] for row in results]
            return {
                "swaps": swaps,
                "holdouts": results,
                "mean_placement_improvement": fmean(improvements) if improvements else 0.0,
                "all_holdouts_nonnegative": all(value >= 0 for value in improvements),
            }
        return self._invoke("run_holdout", request, work, deck_ids=(request.deck_id,), seed=request.seed, iterations=request.iterations)

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
                    rows.append({"seed": seed, "pilot_strength": strength.value, "aggregate": response.result.get("aggregate")})
            return {"runs": rows}
        return self._invoke("run_sensitivity", request, work, deck_ids=request.deck_ids, iterations=request.iterations)

    def recommend_upgrades(self, request: RecommendUpgradesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            cuts = [
                card for card in sorted(deck.cards, key=profile_score)
                if card.oracle_name not in deck.commander_names
                and not card.is_land
                and not self._is_protected(request.deck_id, card.oracle_name)
            ][: max(16, request.max_recommendations)]
            candidate_ids = request.candidate_ids or tuple(
                candidate_id for candidate_id, candidate in self.candidates.items()
                if not candidate.allowed_deck_ids or request.deck_id in candidate.allowed_deck_ids
            )
            recommendations = []
            for cut in cuts:
                for candidate_id in candidate_ids:
                    candidate = self._candidate(candidate_id, request.deck_id)
                    raw_delta = profile_score(candidate.card) - profile_score(cut)
                    overlap = candidate.card.roles & cut.roles
                    lost_roles = cut.roles - candidate.card.roles
                    critical_roles = {
                        "graveyard_hate", "removal", "counter", "protection", "wipe", "recursion"
                    }
                    critical_loss = sum(role.value in critical_roles for role in lost_roles)
                    compatibility_adjustment = (
                        1.5 * len(overlap)
                        - 0.5 * len(lost_roles)
                        - 3.0 * critical_loss
                        - (0.75 if not overlap else 0.0)
                    )
                    delta = raw_delta + compatibility_adjustment
                    role_gain = sorted(role.value for role in candidate.card.roles - cut.roles)
                    role_loss = sorted(role.value for role in lost_roles)
                    recommendations.append({
                        "remove": cut.oracle_name,
                        "add": candidate.card.oracle_name,
                        "candidate_id": candidate_id,
                        "screening_delta": delta,
                        "raw_profile_delta": raw_delta,
                        "role_compatibility_adjustment": compatibility_adjustment,
                        "role_gain": role_gain,
                        "role_loss": role_loss,
                        "physical_status": candidate.physical_status,
                        "requires_paired_validation": True,
                    })
            recommendations.sort(key=lambda row: row["screening_delta"], reverse=True)
            return {
                "method": "role_profile_screening_only",
                "recommendations": recommendations[: request.max_recommendations],
                "warning": "Candidates are not confirmed until paired and holdout validation pass.",
            }
        return self._invoke("recommend_upgrades", request, work, deck_ids=(request.deck_id,))

    def validate_upgrade(self, request: ValidateUpgradeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            paired = self.compare_variants_paired(request)
            if paired.status != ToolStatus.COMPLETED:
                raise ToolExecutionError("paired comparison failed")
            improvement = float(paired.result["comparison"]["placement_improvement"])
            holdout_result = None
            holdout_passed = True
            if request.require_holdout:
                holdout = HoldoutInput(
                    deck_id=request.deck_id,
                    swaps=request.swaps,
                    opponent_deck_ids=request.opponent_deck_ids,
                    seed=request.seed,
                    iterations=request.iterations,
                    workers=request.workers,
                    pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    approval_token=request.approval_token,
                )
                holdout_response = self.run_holdout(holdout)
                if holdout_response.status != ToolStatus.COMPLETED:
                    raise ToolExecutionError("holdout failed")
                holdout_result = holdout_response.result
                holdout_passed = bool(holdout_result["all_holdouts_nonnegative"])
            confirmed = improvement >= request.minimum_place_delta and holdout_passed
            return {
                "decision": "confirmed" if confirmed else "rejected",
                "paired": paired.result,
                "holdout": holdout_result,
                "threshold": request.minimum_place_delta,
                "reason": (
                    "paired improvement and holdout criteria passed"
                    if confirmed else "one or more validation criteria failed"
                ),
            }
        return self._invoke("validate_upgrade", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def ingest_playtest(self, request: IngestPlaytestInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            source = Path(request.source_path).resolve()
            if not source.is_file():
                raise ToolExecutionError(f"playtest file not found: {source}")
            games = RealPlaytestImporter().import_file(source, sheet_name=request.sheet_name)
            destination = self.root / "data/playtests/ingested" / f"{sha256_value(str(source))[:12]}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps([game.model_dump(mode="json") for game in games], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return {"games_imported": len(games), "game_ids": [game.game_id for game in games], "output_path": str(destination)}
        return self._invoke("ingest_playtest", request, work)

    def calibrate(self, request: CalibrateInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            ingested = self.root / "data/playtests/ingested"
            games = []
            for path in sorted(ingested.glob("*.json")) if ingested.exists() else []:
                games.extend(json.loads(path.read_text(encoding="utf-8")))
            if request.playtest_ids:
                games = [game for game in games if game.get("game_id") in request.playtest_ids]
            turns = [game["turns"] for game in games if game.get("turns") is not None]
            placements: Counter[str] = Counter()
            samples: Counter[str] = Counter()
            for game in games:
                for participant in game.get("participants", []):
                    deck_name = participant["deck_name"]
                    samples[deck_name] += 1
                    if participant.get("placement") == 1:
                        placements[deck_name] += 1
            calibration = {
                "schema_version": "0.5.0",
                "games": len(games),
                "average_observed_turns": fmean(turns) if turns else None,
                "observed_place_1_share": {
                    deck: placements[deck] / samples[deck] for deck in sorted(samples)
                },
                "status": "insufficient_data" if len(games) < 10 else "provisional",
                "engine_parameters_modified": False,
            }
            output = self.root / "data/playtests" / request.output_name
            output.write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")
            return {**calibration, "output_path": str(output)}
        return self._invoke("calibrate", request, work)

    def create_report(self, request: CreateReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            safe_name = Path(request.output_name).name
            output = self.report_dir / safe_name
            lines = [
                f"# {request.title}",
                "",
                "All numerical simulation outputs are `structural_model_estimates`.",
                "",
                "## Evidence summary",
                "",
                "| # | Tool | Status | Invocation |",
                "|---:|---|---|---|",
            ]
            for index, response in enumerate(request.tool_responses, start=1):
                metadata = response.get("metadata", {})
                lines.append(
                    f"| {index} | {metadata.get('tool_name', 'unknown')} | "
                    f"{response.get('status', 'unknown')} | {metadata.get('invocation_id', '')} |"
                )
            decisions = [
                response.get("result", {}).get("decision")
                for response in request.tool_responses
                if response.get("result", {}).get("decision")
            ]
            if decisions:
                lines.extend(["", "## Validation decision", "", f"**{decisions[-1]}**", ""])
            for index, response in enumerate(request.tool_responses, start=1):
                lines.extend([
                    f"## Evidence {index}",
                    "",
                    "```json",
                    json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True),
                    "```",
                    "",
                ])
            output.write_text("\n".join(lines), encoding="utf-8")
            return {
                "report_path": str(output),
                "evidence_items": len(request.tool_responses),
                "decisions": decisions,
            }
        return self._invoke("create_report", request, work)
