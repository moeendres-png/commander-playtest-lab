from __future__ import annotations

import itertools
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
    BeamSearchInput,
    CandidatePackage,
    LocalSearchInput,
    OptimizationConstraints,
    OptimizationVariant,
    PackageSearchInput,
    ParetoFrontInput,
    ShapleyInput,
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
    DEFAULT_CONSTRAINTS,
    SearchCandidate,
    ablation_filler,
    all_legal_single_swaps,
    approximate_shapley_profile,
    build_search_candidate,
    default_constraints,
    evaluate_constraints,
    load_candidate_inventory,
    objective_vector,
    pareto_front,
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
        self.candidate_inventory = load_candidate_inventory(self.root)
        self.verified_candidate_names = {
            candidate.card.oracle_name
            for candidate in self.candidates.values()
            if candidate.physical_status == "local_project_verified_owned"
        }
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

    def _optimization_constraints(
        self, deck_id: str, supplied: OptimizationConstraints | None = None
    ) -> OptimizationConstraints:
        if supplied is not None:
            return supplied
        path = self.root / "config/phase7_optimization.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if deck_id in payload.get("constraints", {}):
                return OptimizationConstraints.model_validate(payload["constraints"][deck_id])
        return default_constraints(deck_id, None, DEFAULT_CONSTRAINTS)

    def _eligible_candidate_ids(
        self, deck_id: str, requested: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        ids = requested or tuple(self.candidates)
        return tuple(
            candidate_id for candidate_id in ids
            if candidate_id in self.candidates
            and (
                not self.candidates[candidate_id].allowed_deck_ids
                or deck_id in self.candidates[candidate_id].allowed_deck_ids
            )
        )

    def _paired_variant_metrics(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        opponent_deck_ids: tuple[str, ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
        pair_id: str,
    ):
        return run_paired_structural_comparison(
            baseline=baseline,
            variant=variant,
            opponents=tuple(self._deck(deck_id) for deck_id in opponent_deck_ids),
            iterations=iterations,
            seed=seed,
            pilot_config=PilotConfig(strength=pilot_strength, mode=pilot_mode),
            max_turns=max_turns,
            pair_id=pair_id,
        )

    @staticmethod
    def _commander_dependency_penalty(deck: StructuralDeckProfile) -> float:
        nonlands = [card for card in deck.cards if not card.is_land]
        if not nonlands:
            return 0.0
        synergy = fmean(card.commander_synergy for card in nonlands) / 2.0
        floor = fmean(card.floor_value for card in nonlands) / 2.0
        return max(0.0, min(1.0, synergy * (1.0 - 0.35 * floor)))

    def _holdout_improvements(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        holdout_pods: tuple[tuple[str, ...], ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, pod in enumerate(holdout_pods):
            metrics, pairs = self._paired_variant_metrics(
                baseline=baseline, variant=variant, opponent_deck_ids=pod,
                iterations=iterations, seed=seed + index + 1,
                pilot_strength=pilot_strength, pilot_mode=pilot_mode, max_turns=max_turns,
                pair_id=f"holdout-{variant.deck_hash[:10]}-{index}",
            )
            rows.append({
                "pod": pod,
                "comparison": metrics.as_dict(),
                "pair_count": len(pairs),
            })
        return rows

    def _red_team_review(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        swaps: tuple[Any, ...],
        constraint_report: Any,
        paired: dict[str, Any],
        holdouts: list[dict[str, Any]],
        sensitivity: list[dict[str, Any]],
    ) -> dict[str, Any]:
        concerns: list[str] = []
        alternatives: list[str] = []
        if not constraint_report.valid:
            concerns.append("The variant violates one or more hard deck constraints.")
        if paired.get("placement_improvement", 0.0) <= 0:
            concerns.append("The primary paired comparison does not improve average placement.")
        if paired.get("paired_win_count", 0) <= paired.get("paired_loss_count", 0):
            concerns.append("Paired game outcomes do not favor the variant over the baseline.")
        negative_holdouts = [
            row for row in holdouts
            if row["comparison"].get("placement_improvement", 0.0) < 0
        ]
        if negative_holdouts:
            concerns.append("At least one holdout matchup becomes worse.")
        sensitivity_values = [row["placement_improvement"] for row in sensitivity]
        if sensitivity_values and min(sensitivity_values) < 0:
            concerns.append("The result changes sign across sensitivity settings.")
        if len(sensitivity_values) >= 2 and max(sensitivity_values) - min(sensitivity_values) > 0.20:
            concerns.append("The estimated effect is highly sensitive to seed or pilot strength.")
        removed_roles = Counter()
        added_roles = Counter()
        for swap in swaps:
            original = next((c for c in baseline.cards if c.oracle_name == swap.remove), None)
            candidate = self.candidates.get(swap.add_candidate_id)
            if original:
                removed_roles.update(original.roles)
            if candidate:
                added_roles.update(candidate.card.roles)
        for role, count in removed_roles.items():
            if added_roles[role] < count:
                concerns.append(f"Net role loss detected: {role.value}.")
        if len(swaps) > 1:
            alternatives.append("Validate each swap separately to distinguish package synergy from a weak component.")
        alternatives.append("Retain the baseline when the effect is small relative to holdout or sensitivity variation.")
        passed = not concerns
        return {
            "passed": passed,
            "concerns": concerns,
            "alternative_explanations": alternatives,
            "automatic_application_allowed": False,
        }

    def _evaluate_search_candidate(
        self,
        *,
        baseline: StructuralDeckProfile,
        candidate: Any,
        opponent_deck_ids: tuple[str, ...],
        holdout_pods: tuple[tuple[str, ...], ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
        search_method: str,
    ) -> tuple[OptimizationVariant, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        metrics, pairs = self._paired_variant_metrics(
            baseline=baseline, variant=candidate.variant, opponent_deck_ids=opponent_deck_ids,
            iterations=iterations, seed=seed, pilot_strength=pilot_strength,
            pilot_mode=pilot_mode, max_turns=max_turns,
            pair_id=f"phase7-{search_method}-{candidate.variant.deck_hash[:10]}",
        )
        holdouts = self._holdout_improvements(
            baseline=baseline, variant=candidate.variant, holdout_pods=holdout_pods,
            iterations=iterations, seed=seed, pilot_strength=pilot_strength,
            pilot_mode=pilot_mode, max_turns=max_turns,
        )
        holdout_values = [row["comparison"]["placement_improvement"] for row in holdouts]
        objectives = objective_vector(
            metrics=metrics, pairs=pairs, variant=candidate.variant,
            commander_dependency_penalty=self._commander_dependency_penalty(candidate.variant),
            holdout_improvements=holdout_values,
            physical_valid=candidate.constraint_report.valid,
        )
        result = OptimizationVariant(
            variant_id=candidate.variant.deck_id,
            deck_id=baseline.deck_id,
            deck_hash=candidate.variant.deck_hash,
            swaps=candidate.swaps,
            structural_rationale=candidate.rationale,
            affected_matchups=candidate.affected_matchups,
            constraint_report=candidate.constraint_report,
            objectives=objectives,
            screening_score=candidate.screening_score,
            search_method=search_method,
            parent_variant_id=candidate.parent_variant_id,
        )
        return result, {"comparison": metrics.as_dict(), "pairs": pairs}, holdouts, []

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

    def generate_swap_matrix(self, request: SwapMatrixInput) -> ToolResponse:
        """Generate every requested cut/add cell, preserving invalid cells as evidence."""
        def work() -> dict[str, Any]:
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.add_candidate_ids)
            remove_cards = request.remove_cards or tuple(dict.fromkeys(
                card.oracle_name for card in baseline.cards
                if card.oracle_name not in baseline.commander_names
                and not self._is_protected(request.deck_id, card.oracle_name)
            ))
            cells = len(remove_cards) * len(candidate_ids)
            if cells > self.limits.max_swap_matrix_cells:
                raise ToolExecutionError(
                    f"swap matrix has {cells} cells; limit is {self.limits.max_swap_matrix_cells}"
                )
            if request.simulate_valid_cells:
                self._check_iterations(cells * request.iterations_per_cell, request.approval_token)
            rows: list[dict[str, Any]] = []
            valid_count = 0
            simulated_count = 0
            for remove in remove_cards:
                for candidate_id in candidate_ids:
                    row: dict[str, Any] = {
                        "remove": remove,
                        "candidate_id": candidate_id,
                        "status": "invalid",
                        "constraint_report": None,
                        "comparison": None,
                    }
                    try:
                        candidate = build_search_candidate(
                            baseline,
                            (self.models_variant_swap(remove, candidate_id),),
                            self.candidates,
                            constraints,
                            inventory=self.candidate_inventory,
                            verified_physical_names=self.verified_candidate_names,
                        )
                    except Exception as exc:
                        row["errors"] = [f"{type(exc).__name__}: {exc}"]
                        rows.append(row)
                        continue
                    row.update({
                        "add": candidate.additions[0].card.oracle_name,
                        "screening_score": candidate.screening_score,
                        "constraint_report": candidate.constraint_report.model_dump(mode="json"),
                        "structural_rationale": candidate.rationale,
                        "affected_matchups": candidate.affected_matchups,
                    })
                    if not candidate.constraint_report.valid:
                        rows.append(row)
                        continue
                    valid_count += 1
                    row["status"] = "screened_valid"
                    if request.simulate_valid_cells:
                        metrics, _ = self._paired_variant_metrics(
                            baseline=baseline,
                            variant=candidate.variant,
                            opponent_deck_ids=request.opponent_deck_ids,
                            iterations=request.iterations_per_cell,
                            seed=request.seed,
                            pilot_strength=request.pilot_strength,
                            pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            pair_id=f"matrix-{candidate.variant.deck_hash[:12]}",
                        )
                        row["comparison"] = metrics.as_dict()
                        row["status"] = "paired_screened"
                        simulated_count += 1
                    rows.append(row)
            rows.sort(
                key=lambda row: (
                    (row.get("comparison") or {}).get("placement_improvement", -99.0),
                    row.get("screening_score", -99.0),
                    row["remove"],
                    row["candidate_id"],
                ),
                reverse=True,
            )
            return {
                "matrix_complete": len(rows) == cells,
                "cells": cells,
                "valid_cells": valid_count,
                "simulated_cells": simulated_count,
                "rows": rows,
                "best_valid_cell": next((row for row in rows if row["status"] != "invalid"), None),
                "automatic_application": False,
            }
        return self._invoke(
            "generate_swap_matrix", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations_per_cell,
        )

    @staticmethod
    def models_variant_swap(remove: str, candidate_id: str):
        from commander_lab.models import VariantSwap
        return VariantSwap(remove=remove, add_candidate_id=candidate_id)

    def search_variants(self, request: SearchVariantsInput) -> ToolResponse:
        """Backward-compatible bounded local one-swap search with hard constraints."""
        local_request = LocalSearchInput(
            deck_id=request.deck_id,
            candidate_ids=request.candidate_ids,
            max_steps=1,
            cuts_per_step=request.max_cuts,
            opponent_deck_ids=request.opponent_deck_ids,
            seed=request.seed,
            iterations=request.iterations,
            workers=request.workers,
            pilot_strength=request.pilot_strength,
            pilot_mode=request.pilot_mode,
            max_turns=request.max_turns,
            approval_token=request.approval_token,
        )
        response = self.run_local_search(local_request)
        if response.status == ToolStatus.COMPLETED:
            path = response.result.get("path", [])
            response.result = {
                "searched": response.result.get("evaluated_neighbors", 0),
                "variants": path[: request.max_results],
                "search_method": "phase7_constrained_local_search",
                "automatic_application": False,
            }
        return response

    def run_local_search(self, request: LocalSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.max_steps * request.cuts_per_step * max(1, len(self._eligible_candidate_ids(request.deck_id, request.candidate_ids))) * request.iterations,
                request.approval_token,
            )
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            current = baseline
            cumulative_swaps: list[Any] = []
            used_candidates: set[str] = set()
            used_cuts: set[str] = set()
            path: list[dict[str, Any]] = []
            evaluated = 0
            for step in range(request.max_steps):
                cut_map = {
                    card.oracle_name: card for card in sorted(baseline.cards, key=profile_score)
                    if card.oracle_name not in baseline.commander_names
                    and card.oracle_name not in used_cuts
                    and not card.is_land
                    and not self._is_protected(request.deck_id, card.oracle_name)
                }
                cuts = list(cut_map.values())[: request.cuts_per_step]
                neighbors: list[tuple[float, SearchCandidate, dict[str, Any]]] = []
                for cut in cuts:
                    for candidate_id in candidate_ids:
                        if candidate_id in used_candidates:
                            continue
                        swaps = tuple(cumulative_swaps + [self.models_variant_swap(cut.oracle_name, candidate_id)])
                        try:
                            neighbor = build_search_candidate(
                                baseline, swaps, self.candidates, constraints,
                                inventory=self.candidate_inventory,
                                verified_physical_names=self.verified_candidate_names,
                                parent_variant_id=current.deck_id,
                            )
                        except Exception:
                            continue
                        if not neighbor.constraint_report.valid:
                            continue
                        metrics, _ = self._paired_variant_metrics(
                            baseline=current, variant=neighbor.variant,
                            opponent_deck_ids=request.opponent_deck_ids,
                            iterations=request.iterations, seed=request.seed + step,
                            pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            pair_id=f"local-{step}-{neighbor.variant.deck_hash[:10]}",
                        )
                        evaluated += 1
                        neighbors.append((metrics.placement_improvement, neighbor, metrics.as_dict()))
                if not neighbors:
                    break
                neighbors.sort(key=lambda row: (row[0], row[1].screening_score, row[1].variant.deck_hash), reverse=True)
                improvement, best, comparison = neighbors[0]
                if improvement <= 0:
                    break
                cumulative_swaps = list(best.swaps)
                used_candidates = {swap.add_candidate_id for swap in best.swaps}
                used_cuts = {swap.remove for swap in best.swaps}
                current = best.variant
                path.append({
                    "step": step + 1,
                    "swaps": [swap.model_dump(mode="json") for swap in best.swaps],
                    "comparison_to_parent": comparison,
                    "screening_score": best.screening_score,
                    "constraint_report": best.constraint_report.model_dump(mode="json"),
                    "structural_rationale": best.rationale,
                    "affected_matchups": best.affected_matchups,
                    "variant_deck_hash": best.variant.deck_hash,
                    "automatic_application": False,
                })
            return {
                "method": "constrained_local_search",
                "evaluated_neighbors": evaluated,
                "path": path,
                "best_variant": path[-1] if path else None,
                "automatic_application": False,
            }
        return self._invoke(
            "run_local_search", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def run_beam_search(self, request: BeamSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            estimated = request.depth * request.beam_width * request.max_cuts_per_node * max(1, len(candidate_ids))
            if estimated > self.limits.max_variants * 20:
                raise ToolExecutionError(f"beam expansion estimate {estimated} exceeds safety bound")
            self._check_iterations(min(estimated, self.limits.max_variants) * request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            beam: list[SearchCandidate] = []
            initial_swaps: tuple[Any, ...] = ()
            for depth in range(request.depth):
                parents: list[tuple[tuple[Any, ...], str | None]] = [
                    (node.swaps, node.variant.deck_id) for node in beam
                ] or [(initial_swaps, baseline.deck_id)]
                expanded: dict[str, SearchCandidate] = {}
                for parent_swaps, parent_id in parents:
                    used_cuts = {swap.remove for swap in parent_swaps}
                    used_candidates = {swap.add_candidate_id for swap in parent_swaps}
                    cut_map = {
                        card.oracle_name: card for card in sorted(baseline.cards, key=profile_score)
                        if card.oracle_name not in baseline.commander_names
                        and card.oracle_name not in used_cuts
                        and not card.is_land
                        and not self._is_protected(request.deck_id, card.oracle_name)
                    }
                    cuts = list(cut_map.values())[: request.max_cuts_per_node]
                    for cut in cuts:
                        for candidate_id in candidate_ids:
                            if candidate_id in used_candidates:
                                continue
                            swaps = tuple((*parent_swaps, self.models_variant_swap(cut.oracle_name, candidate_id)))
                            try:
                                node = build_search_candidate(
                                    baseline, swaps, self.candidates, constraints,
                                    inventory=self.candidate_inventory,
                                    verified_physical_names=self.verified_candidate_names,
                                    parent_variant_id=parent_id,
                                )
                            except Exception:
                                continue
                            if node.constraint_report.valid:
                                expanded[node.variant.deck_hash] = node
                candidates = sorted(
                    expanded.values(),
                    key=lambda node: (node.screening_score, node.variant.deck_hash),
                    reverse=True,
                )[: max(request.beam_width * 3, request.beam_width)]
                scored: list[tuple[float, SearchCandidate, dict[str, Any]]] = []
                for node in candidates:
                    metrics, _ = self._paired_variant_metrics(
                        baseline=baseline, variant=node.variant,
                        opponent_deck_ids=request.opponent_deck_ids,
                        iterations=request.iterations, seed=request.seed + depth,
                        pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        pair_id=f"beam-{depth}-{node.variant.deck_hash[:10]}",
                    )
                    scored.append((metrics.placement_improvement, node, metrics.as_dict()))
                scored.sort(key=lambda row: (row[0], row[1].screening_score, row[1].variant.deck_hash), reverse=True)
                beam = [row[1] for row in scored[: request.beam_width]]
                if not beam:
                    break
            final_rows = []
            for node in beam:
                metrics, pairs = self._paired_variant_metrics(
                    baseline=baseline, variant=node.variant,
                    opponent_deck_ids=request.opponent_deck_ids,
                    iterations=request.iterations, seed=request.seed,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    pair_id=f"beam-final-{node.variant.deck_hash[:10]}",
                )
                final_rows.append({
                    "swaps": [swap.model_dump(mode="json") for swap in node.swaps],
                    "comparison": metrics.as_dict(),
                    "worst_quartile_delta": self._worst_quartile(pairs),
                    "screening_score": node.screening_score,
                    "constraint_report": node.constraint_report.model_dump(mode="json"),
                    "structural_rationale": node.rationale,
                    "affected_matchups": node.affected_matchups,
                    "variant_deck_hash": node.variant.deck_hash,
                    "automatic_application": False,
                })
            final_rows.sort(key=lambda row: row["comparison"]["placement_improvement"], reverse=True)
            return {
                "method": "beam_search",
                "beam_width": request.beam_width,
                "depth": request.depth,
                "variants": final_rows,
                "automatic_application": False,
            }
        return self._invoke(
            "run_beam_search", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    @staticmethod
    def _worst_quartile(pairs: list[dict[str, Any]]) -> float:
        from commander_lab.optimization import worst_quartile_improvement
        return worst_quartile_improvement(pairs)

    def run_package_search(self, request: PackageSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            packages = list(request.packages)
            if not packages:
                singles = all_legal_single_swaps(
                    baseline, self.candidates, candidate_ids, constraints,
                    inventory=self.candidate_inventory,
                    verified_physical_names=self.verified_candidate_names,
                    protected=set(self.protected_cards.get(request.deck_id, [])),
                )[:12]
                seen: set[str] = set()
                for size in range(2, request.max_package_size + 1):
                    for combo in itertools.combinations(singles, size):
                        swaps = tuple(item.swaps[0] for item in combo)
                        if len({swap.remove for swap in swaps}) != size or len({swap.add_candidate_id for swap in swaps}) != size:
                            continue
                        key = sha256_value([swap.model_dump(mode="json") for swap in swaps])
                        if key in seen:
                            continue
                        seen.add(key)
                        packages.append(CandidatePackage(package_id=f"auto-{key[:10]}", swaps=swaps))
                        if len(packages) >= request.max_packages:
                            break
                    if len(packages) >= request.max_packages:
                        break
            self._check_iterations(len(packages) * request.iterations, request.approval_token)
            rows: list[dict[str, Any]] = []
            for package in packages[: request.max_packages]:
                try:
                    node = build_search_candidate(
                        baseline, package.swaps, self.candidates, constraints,
                        inventory=self.candidate_inventory,
                        verified_physical_names=self.verified_candidate_names,
                    )
                except Exception as exc:
                    rows.append({"package_id": package.package_id, "status": "invalid", "error": str(exc)})
                    continue
                if not node.constraint_report.valid:
                    rows.append({
                        "package_id": package.package_id,
                        "status": "constraint_failed",
                        "constraint_report": node.constraint_report.model_dump(mode="json"),
                    })
                    continue
                metrics, pairs = self._paired_variant_metrics(
                    baseline=baseline, variant=node.variant,
                    opponent_deck_ids=request.opponent_deck_ids,
                    iterations=request.iterations, seed=request.seed,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    pair_id=f"package-search-{node.variant.deck_hash[:10]}",
                )
                rows.append({
                    "package_id": package.package_id,
                    "status": "paired_screened",
                    "swaps": [swap.model_dump(mode="json") for swap in package.swaps],
                    "comparison": metrics.as_dict(),
                    "worst_quartile_delta": self._worst_quartile(pairs),
                    "constraint_report": node.constraint_report.model_dump(mode="json"),
                    "structural_rationale": node.rationale,
                    "affected_matchups": node.affected_matchups,
                    "automatic_application": False,
                })
            rows.sort(key=lambda row: (row.get("comparison") or {}).get("placement_improvement", -99), reverse=True)
            return {"method": "package_search", "packages": rows, "automatic_application": False}
        return self._invoke(
            "run_package_search", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def evaluate_pareto_front(self, request: ParetoFrontInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(len(request.variants) * (1 + len(request.holdout_pods)) * request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            evaluated: list[OptimizationVariant] = []
            evidence: dict[str, Any] = {}
            for swaps in request.variants:
                node = build_search_candidate(
                    baseline, swaps, self.candidates, constraints,
                    inventory=self.candidate_inventory,
                    verified_physical_names=self.verified_candidate_names,
                )
                if not node.constraint_report.valid:
                    evaluated.append(OptimizationVariant(
                        variant_id=node.variant.deck_id, deck_id=baseline.deck_id,
                        deck_hash=node.variant.deck_hash, swaps=node.swaps,
                        structural_rationale=node.rationale,
                        affected_matchups=node.affected_matchups,
                        constraint_report=node.constraint_report,
                        screening_score=node.screening_score,
                        search_method="pareto_evaluation",
                    ))
                    continue
                variant, paired, holdouts, _ = self._evaluate_search_candidate(
                    baseline=baseline, candidate=node,
                    opponent_deck_ids=request.opponent_deck_ids,
                    holdout_pods=request.holdout_pods,
                    iterations=request.iterations, seed=request.seed,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns, search_method="pareto_evaluation",
                )
                evaluated.append(variant)
                evidence[variant.variant_id] = {"paired": paired, "holdouts": holdouts}
            front = pareto_front(evaluated)
            return {
                "objectives_are_maximized": True,
                "evaluated": [item.model_dump(mode="json") for item in evaluated],
                "pareto_front": [item.model_dump(mode="json") for item in front],
                "evidence": evidence,
                "automatic_application": False,
            }
        return self._invoke(
            "evaluate_pareto_front", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def estimate_shapley(self, request: ShapleyInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(len(request.card_names) * request.iterations, request.approval_token)
            deck = self._deck(request.deck_id)
            values = approximate_shapley_profile(
                deck, request.card_names, permutations=request.permutations, seed=request.seed
            )
            ablations: dict[str, Any] = {}
            for name in request.card_names:
                response = self.run_card_ablation(CardAblationInput(
                    deck_id=request.deck_id, card_name=name,
                    opponent_deck_ids=request.opponent_deck_ids,
                    seed=request.seed, iterations=request.iterations,
                    workers=1, pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode, max_turns=request.max_turns,
                    approval_token=request.approval_token,
                ))
                ablations[name] = response.result if response.status == ToolStatus.COMPLETED else {"errors": response.errors}
            return {
                "method": "permutation_profile_shapley_with_paired_single_card_ablation",
                "permutations": request.permutations,
                "contributions": values,
                "paired_ablation_evidence": ablations,
                "warning": "Shapley values are approximate structural contribution estimates, not causal real-game values.",
            }
        return self._invoke(
            "estimate_shapley", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def validate_upgrade(self, request: ValidateUpgradeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            sensitivity_runs = len(request.sensitivity_seeds) * len(request.sensitivity_strengths)
            total = request.iterations * (1 + len(request.holdout_pods) + sensitivity_runs)
            self._check_iterations(total, request.approval_token)
            baseline, variant, swap_rows = self._build_variant(request)
            constraints = self._optimization_constraints(request.deck_id)
            report = evaluate_constraints(
                variant, constraints,
                candidate_inventory=self.candidate_inventory,
                added_card_names=tuple(row["add"] for row in swap_rows),
                verified_physical_names=self.verified_candidate_names,
            )
            metrics, pairs = self._paired_variant_metrics(
                baseline=baseline, variant=variant,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations, seed=request.seed,
                pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                max_turns=request.max_turns,
                pair_id=f"validate-{variant.deck_hash[:10]}",
            )
            holdouts = self._holdout_improvements(
                baseline=baseline, variant=variant,
                holdout_pods=request.holdout_pods if request.require_holdout else (),
                iterations=request.iterations, seed=request.seed,
                pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                max_turns=request.max_turns,
            )
            sensitivity: list[dict[str, Any]] = []
            for seed in request.sensitivity_seeds:
                for strength in request.sensitivity_strengths:
                    sensitive_metrics, _ = self._paired_variant_metrics(
                        baseline=baseline, variant=variant,
                        opponent_deck_ids=request.opponent_deck_ids,
                        iterations=request.iterations, seed=seed,
                        pilot_strength=strength, pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        pair_id=f"sensitivity-{variant.deck_hash[:8]}-{seed}-{strength.value}",
                    )
                    sensitivity.append({
                        "seed": seed,
                        "pilot_strength": strength.value,
                        "placement_improvement": sensitive_metrics.placement_improvement,
                        "place_1_share_delta": sensitive_metrics.place_1_share_delta,
                    })
            red_team = self._red_team_review(
                baseline=baseline, variant=variant, swaps=request.swaps,
                constraint_report=report, paired=metrics.as_dict(),
                holdouts=holdouts, sensitivity=sensitivity,
            )
            holdout_passed = all(
                row["comparison"]["placement_improvement"] >= 0 for row in holdouts
            ) if request.require_holdout else True
            sensitivity_passed = all(
                row["placement_improvement"] >= 0 for row in sensitivity
            ) if request.require_sensitivity_nonnegative else True
            passed = (
                report.valid
                and metrics.placement_improvement >= request.minimum_place_delta
                and holdout_passed
                and sensitivity_passed
                and (red_team["passed"] or not request.require_red_team_pass)
            )
            removed_cards = [
                next(card for card in baseline.cards if card.oracle_name == swap.remove)
                for swap in request.swaps
            ]
            added_cards = [self._candidate(swap.add_candidate_id, request.deck_id).card for swap in request.swaps]
            rationale = []
            matchups: set[str] = set()
            from commander_lab.optimization import card_matchup_tags, structural_rationale
            for remove, add in zip(removed_cards, added_cards, strict=True):
                rationale.extend(structural_rationale(remove, add))
                matchups.update(card_matchup_tags(remove) | card_matchup_tags(add))
            return {
                "decision": "confirmed" if passed else "rejected",
                "proposal_status": "validated_not_applied" if passed else "rejected_not_applied",
                "swaps": swap_rows,
                "structural_rationale": rationale,
                "affected_matchups": sorted(matchups),
                "constraint_report": report.model_dump(mode="json"),
                "paired_comparison": metrics.as_dict(),
                "pair_sample": pairs[:20],
                "holdout_tests": holdouts,
                "sensitivity_tests": sensitivity,
                "red_team_review": red_team,
                "criteria": {
                    "minimum_place_delta": request.minimum_place_delta,
                    "paired_passed": metrics.placement_improvement >= request.minimum_place_delta,
                    "holdout_passed": holdout_passed,
                    "sensitivity_passed": sensitivity_passed,
                    "red_team_passed": red_team["passed"],
                    "constraints_passed": report.valid,
                },
                "automatic_application": False,
                "canonical_deck_files_modified": False,
            }
        return self._invoke(
            "validate_upgrade", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )


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
