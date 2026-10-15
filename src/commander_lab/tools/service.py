from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING, Any

from commander_lab.agents.ensemble import PilotEnsembleRunner, PilotRegistry
from commander_lab.agents.pilots import build_pilot
from commander_lab.decision_statistics import holm_adjust
from commander_lab.engine.rules import (
    RulesEngineManager,
    load_project_rules_decks,
)
from commander_lab.models import (
    ActionProposal,
    ComparePilotsInput,
    CreateDeckImprovementReportInput,
    CreateReportInput,
    ExplainRecommendationInput,
    ExportRecommendationEvidenceInput,
    GeneratePilotRobustnessReportInput,
    InspectPilotInput,
    ListPilotProfilesInput,
    PilotConfig,
    PilotEnsembleDefinition,
    PilotEnsembleMember,
    PilotStrength,
    RankVariantsInput,
    RulesGameRequest,
    RunEngineBackedMatchupInput,
    RunMultifidelityComparisonInput,
    RunPilotBenchmarkInput,
    RunPilotEnsembleInput,
    RunRobustnessSuiteInput,
    RunRulesCoverageGateInput,
    TestVariantAcrossPilotsInput,
    ToolResponse,
    ValidateDeckInput,
    ValidateSwapInput,
)
from commander_lab.models.mulligan import (
    MulliganPolicyName,
)
from commander_lab.models.tooling import (
    CompareMulliganPoliciesInput,
)
from commander_lab.robustness import POLITICS_REGIMES
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
    sha256_value,
)

if TYPE_CHECKING:
    from commander_lab.counterfactual import CounterfactualReplayLab
    from commander_lab.diagnostics import DecisionDiagnosticEngine

from .service_core import ApprovalRequired as ApprovalRequired
from .service_core import EstimateType as EstimateType
from .service_core import ServiceCore
from .service_core import ToolExecutionError as ToolExecutionError
from .service_core import _deterministic_structural_run_id as _deterministic_structural_run_id
from .service_knowledge import ServiceKnowledgeMixin
from .service_mulligan import ServiceMulliganMixin
from .service_optimizer import ServiceOptimizerMixin
from .service_search import ServiceSearchMixin
from .service_simulation import ServiceSimulationMixin


class CommanderToolService(
    ServiceOptimizerMixin,
    ServiceSearchMixin,
    ServiceSimulationMixin,
    ServiceMulliganMixin,
    ServiceKnowledgeMixin,
    ServiceCore,
):
    """Deterministic local Function Tool service.

    The service is the sole mutation boundary for local artifacts. Agent code receives only these
    methods and cannot directly mutate game state. Simulation results remain structural estimates.
    """

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

    @property
    def git_tree(self) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD^{tree}"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    @property
    def tracked_worktree_dirty(self) -> bool:
        try:
            output = subprocess.check_output(
                ["git", "-C", str(self.root), "status", "--porcelain", "--untracked-files=no"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return bool(output.strip())
        except (OSError, subprocess.CalledProcessError):
            return False

    def run_rules_coverage_gate(self, request: RunRulesCoverageGateInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            registry = self._read_optional_json("data/rules/card_rules_coverage.json", {})
            cards = registry.get("cards", [])
            prefixes = self._coverage_version_prefixes(request.deck_id)
            selected = [
                row
                for row in cards
                if any(
                    version.startswith(prefix)
                    for version in row.get("deck_versions", [])
                    for prefix in prefixes
                )
            ]
            if request.card_names:
                wanted = set(request.card_names)
                selected = [row for row in selected if row.get("oracle_name") in wanted]
            statuses = Counter(row.get("coverage_status", "unsupported") for row in selected)
            external = (
                all(row.get("xmage_rules_verified") for row in selected) if selected else False
            )
            return {
                "deck_id": request.deck_id,
                "cards_checked": len(selected),
                "coverage_version_prefixes": list(prefixes),
                "coverage_counts": dict(statuses),
                "external_engine_execution_status": registry.get(
                    "external_engine_execution_status", "blocked"
                ),
                "external_gate_passed": external,
                "gate_status": "passed"
                if (external or not request.require_external)
                else "blocked",
                "highest_validation_level": "external_rules_engine"
                if external
                else ("tactical_oracle" if statuses.get("tactical_only") else "structural_only"),
                "unsupported_cards": [
                    row.get("oracle_name")
                    for row in selected
                    if row.get("coverage_status") == "unsupported"
                ],
            }

        return self._invoke("run_rules_coverage_gate", request, work, deck_ids=(request.deck_id,))

    def run_multifidelity_comparison(
        self, request: RunMultifidelityComparisonInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            structural = self.validate_swap(
                ValidateSwapInput.model_validate(
                    request.model_dump(
                        exclude={"include_tactical_oracle", "request_external_engine"}
                    )
                )
            ).result
            cards = tuple(
                card
                for card in (structural.get("current_card"), structural.get("candidate_card"))
                if card
            )
            coverage = self.run_rules_coverage_gate(
                RunRulesCoverageGateInput(
                    deck_id=request.deck_id,
                    card_names=cards,
                    require_external=request.request_external_engine,
                )
            ).result
            tactical = (
                self._tactical_interaction_evidence(cards)
                if request.include_tactical_oracle
                else {"execution_status": "not_run", "validation_level": "structural_only"}
            )
            external_results: dict[str, Any] = {}
            if request.request_external_engine:
                for provider in ("xmage",):
                    external_results[provider] = self.run_engine_backed_matchup(
                        RunEngineBackedMatchupInput(
                            deck_ids=(request.deck_id, *request.opponent_deck_ids),
                            provider=provider,
                            seed=request.seed,
                            iterations=1,
                            workers=1,
                            pilot_strength=request.pilot_strength,
                            pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            approval_token=request.approval_token,
                        )
                    ).result
            status = structural.get("recommendation_status", "insufficient_evidence")
            if (
                status == "robust_in_structural_holdout"
                and tactical.get("execution_status") == "passed"
            ):
                status = "tactical_oracle_supported"
            passed_external = [
                p for p, row in external_results.items() if row.get("execution_status") == "passed"
            ]
            if (
                status == "tactical_oracle_supported"
                and coverage.get("external_gate_passed")
                and passed_external
            ):
                status = "external_engine_supported"
            return {
                "formal_gate": "passed"
                if structural.get("recommendation_status") != "rejected"
                else "failed",
                "structural_result": structural,
                "tactical_oracle_result": tactical,
                "external_rules_result": external_results
                if request.request_external_engine
                else {"execution_status": "not_run"},
                "coverage_gate": coverage,
                "recommendation_status": status,
                "evidence_ladder": [
                    "candidate_swap",
                    "formally_valid",
                    "structurally_supported",
                    "robust_in_structural_holdout",
                    "tactical_oracle_supported",
                    "external_engine_supported",
                ],
                "automatic_application": False,
            }

        return self._invoke(
            "run_multifidelity_comparison",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_engine_backed_matchup(self, request: RunEngineBackedMatchupInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            manager = RulesEngineManager(root=self.root)
            try:
                adapter = manager.xmage
                probe = adapter.probe()
                if (
                    probe.availability.value != "available"
                    or probe.capabilities.runtime_kind != "external_rules_engine"
                ):
                    return {
                        "execution_status": "blocked",
                        "validation_level": "structural_only",
                        "provider": request.provider,
                        "provider_status": probe.availability.value,
                        "runtime_kind": probe.capabilities.runtime_kind,
                        "reason": "; ".join(probe.details)
                        or "external provider handshake unavailable",
                        "external_rules_engine_observations": 0,
                        "synthetic_or_tactical_substitution": False,
                    }
                rules_decks = load_project_rules_decks(self.root)
                missing = [deck_id for deck_id in request.deck_ids if deck_id not in rules_decks]
                if missing:
                    return {
                        "execution_status": "blocked",
                        "validation_level": "structural_only",
                        "provider": request.provider,
                        "provider_status": "available",
                        "reason": f"rules-engine deck exports missing for: {missing}",
                        "external_rules_engine_observations": 0,
                        "synthetic_or_tactical_substitution": False,
                    }
                observations: list[dict[str, Any]] = []
                for index in range(request.iterations):
                    handles = [
                        adapter.load_deck(rules_decks[deck_id]) for deck_id in request.deck_ids
                    ]
                    game = adapter.start_commander_game(
                        RulesGameRequest(
                            game_id=f"engine-backed-{request.provider}-{request.seed}-{index}",
                            deck_handles=tuple(handle.handle_id for handle in handles),
                            seed=request.seed + index,
                            starting_player_seat=index % len(handles),
                        )
                    )
                    actions = adapter.get_legal_actions(game.session_id)
                    submitted = False
                    if actions:
                        action = actions[0]
                        adapter.submit_action(
                            game.session_id,
                            ActionProposal(
                                proposal_id=f"engine-backed-action-{index}",
                                actor_id=action.actor_id,
                                legal_action_id=action.action_id,
                                action_type=action.action_type,
                                policy_name="external_engine_acceptance",
                            ),
                        )
                        submitted = True
                    logs = adapter.get_logs(game.session_id)
                    replay = (
                        adapter.export_replay(game.session_id)
                        if probe.capabilities.replay_supported
                        else None
                    )
                    observations.append(
                        {
                            "game_id": game.game_id,
                            "legal_action_count": len(actions),
                            "action_submitted": submitted,
                            "event_count": len(logs.events),
                            "replay_exported": replay is not None,
                        }
                    )
                full = all(
                    row["legal_action_count"] > 0
                    and row["action_submitted"]
                    and row["event_count"] > 0
                    and row["replay_exported"]
                    for row in observations
                )
                return {
                    "execution_status": "passed" if full else "passed_with_limitations",
                    "validation_level": "external_rules_engine",
                    "provider": request.provider,
                    "provider_status": "available",
                    "runtime_kind": "external_rules_engine",
                    "external_rules_engine_observations": len(observations),
                    "observations": observations,
                    "synthetic_or_tactical_substitution": False,
                }
            except Exception as exc:
                return {
                    "execution_status": "failed",
                    "validation_level": "structural_only",
                    "provider": request.provider,
                    "provider_status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "external_rules_engine_observations": 0,
                    "synthetic_or_tactical_substitution": False,
                }
            finally:
                manager.close()

        return self._invoke(
            "run_engine_backed_matchup",
            request,
            work,
            deck_ids=request.deck_ids,
            seed=request.seed,
            iterations=request.iterations,
            estimate_type="external_rules_engine_results",
        )

    def run_robustness_suite(self, request: RunRobustnessSuiteInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            baseline, variant, _ = self._build_variant(request)
            profile_name = request.pilot_strength.value
            rows = self._politics_pod_sensitivity(
                baseline=baseline,
                variant=variant,
                opponent_deck_ids=request.opponent_deck_ids,
                pod_sizes=request.include_pod_sizes,
                seed=request.seed,
                iterations=request.iterations,
                max_turns=request.max_turns,
                profile_name=profile_name,
                include_politics=request.include_politics,
            )
            worst = min((row["placement_improvement"] for row in rows), default=0.0)
            mean = fmean(row["placement_improvement"] for row in rows) if rows else 0.0
            status = (
                "robust_in_structural_holdout" if rows and worst >= 0 else "insufficient_evidence"
            )
            return {
                "validation_level": "structural_only",
                "execution_status": "passed",
                "scenario_count": len(rows),
                "pod_sizes": list(request.include_pod_sizes),
                "politics_included": request.include_politics,
                "politics_regimes": list(POLITICS_REGIMES)
                if request.include_politics
                else ["rational_threat_focus"],
                "scenario_results": rows,
                "mean_effect": mean,
                "worst_case_effect": worst,
                "recommendation_status": status,
                "automatic_application": False,
            }

        return self._invoke(
            "run_robustness_suite",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def rank_variants(self, request: RankVariantsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            def score(row: dict[str, Any]) -> tuple[float, float, float]:
                worst = float(row.get("worst_case_effect", -999.0) or 0.0)
                paired = float(
                    (row.get("paired_structural_effect") or {}).get(
                        "placement_improvement", row.get("effect_size", 0.0)
                    )
                    or 0.0
                )
                coverage_key = str(row.get("rules_coverage") or "")
                coverage = {
                    "external_rules_engine": 3,
                    "tactical_oracle": 2,
                    "structural_only": 1,
                }.get(coverage_key, 0)
                return (worst if request.prefer_worst_case else paired, paired, float(coverage))

            ranked = sorted((dict(row) for row in request.variants), key=score, reverse=True)
            p_rows: list[tuple[int, float]] = []
            for index, row in enumerate(ranked):
                raw_p = row.get("p_value")
                if raw_p is None:
                    raw_p = (row.get("paired_structural_effect") or {}).get(
                        "paired_randomization_p_value"
                    )
                if isinstance(raw_p, (int, float)) and not isinstance(raw_p, bool):
                    row["raw_model_internal_p_value"] = float(raw_p)
                    p_rows.append((index, float(raw_p)))
            if p_rows:
                adjusted = holm_adjust(value for _, value in p_rows)
                for (index, _), value in zip(p_rows, adjusted, strict=True):
                    ranked[index]["holm_adjusted_p_value"] = value
            for index, row in enumerate(ranked, start=1):
                row["rank"] = index
            return {
                "ranked_variants": ranked,
                "method": "worst_case_then_paired_then_coverage",
                "multiple_testing_method": "Holm family-wise correction over the ranked variant family using paired model-internal randomization p-values when available",
                "selection_policy": "constraint gate -> staged structural preselection -> robust/worst-case ranking -> Holm-adjusted family -> independent optimizer holdout",
                "automatic_application": False,
            }

        return self._invoke("rank_variants", request, work)

    def explain_recommendation(self, request: ExplainRecommendationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            evidence = request.evidence
            return {
                "recommendation_status": evidence.get(
                    "recommendation_status", "insufficient_evidence"
                ),
                "summary": (
                    f"{evidence.get('current_card', 'current card')} → "
                    f"{evidence.get('candidate_card', 'candidate card')}"
                ),
                "why": evidence.get("role_changes", []),
                "tradeoffs": {
                    "worst_case_effect": evidence.get("worst_case_effect"),
                    "remaining_uncertainty": evidence.get("remaining_uncertainty", []),
                    "provider_disagreement": evidence.get("provider_disagreement", False),
                },
                "truth_boundary": (
                    "Structural results are model estimates; Tactical Oracle is not an external "
                    "rules engine."
                ),
                "automatic_application": False,
            }

        return self._invoke("explain_recommendation", request, work)

    def export_recommendation_evidence(
        self, request: ExportRecommendationEvidenceInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            target_dir = self.root / "data/runs/recommendations"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / Path(request.output_name).name
            atomic_write_json(
                target,
                {"schema_version": 1, "automatic_application": False, "evidence": request.evidence},
            )
            return {
                "path": str(target),
                "sha256": sha256_value(request.evidence),
                "canonical_files_modified": False,
            }

        return self._invoke("export_recommendation_evidence", request, work)

    def create_deck_improvement_report(
        self, request: CreateDeckImprovementReportInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            target = self.report_dir / Path(request.output_name).name
            lines = [
                f"# Deck improvement report — {request.deck_id}",
                "",
                "Validation boundary: structural model estimates unless an individual "
                "evidence item explicitly records a higher executed level.",
                "",
                "No deck, inventory, or allocation change was applied.",
                "",
            ]
            for index, item in enumerate(request.evidence_items, start=1):
                lines += [
                    f"## Candidate {index}",
                    "",
                    f"- Status: `{item.get('recommendation_status', 'insufficient_evidence')}`",
                    f"- Swap: `{item.get('current_card')}` → `{item.get('candidate_card')}`",
                    f"- Worst-case effect: `{item.get('worst_case_effect')}`",
                    f"- Rules coverage: `{item.get('rules_coverage', 'structural_only')}`",
                    "",
                ]
            atomic_write_text(target, "\n".join(lines))
            return {
                "report_path": str(target),
                "evidence_items": len(request.evidence_items),
                "automatic_application": False,
            }

        return self._invoke(
            "create_deck_improvement_report", request, work, deck_ids=(request.deck_id,)
        )

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
                lines.extend(
                    [
                        f"## Evidence {index}",
                        "",
                        "```json",
                        json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True),
                        "```",
                        "",
                    ]
                )
            output.write_text("\n".join(lines), encoding="utf-8")
            return {
                "report_path": str(output),
                "evidence_items": len(request.tool_responses),
                "decisions": decisions,
            }

        return self._invoke("create_report", request, work)

    def list_pilot_profiles(self, request: ListPilotProfilesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            profiles = PilotRegistry(self.root).profiles()
            filtered = [
                profile
                for profile in profiles
                if (
                    request.commander_family is None
                    or profile.commander_family == request.commander_family
                )
                and (request.include_baselines or not profile.is_baseline)
            ]
            return {
                "profiles": [profile.model_dump(mode="json") for profile in filtered],
                "count": len(filtered),
                "legal_actions_only": True,
                "omniscient_information_used": False,
                "automatic_deck_changes": False,
            }

        return self._invoke("list_pilot_profiles", request, work)

    def inspect_pilot(self, request: InspectPilotInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            profile = PilotRegistry(self.root).profile(request.pilot_name)
            pilot = build_pilot(
                PilotConfig(
                    pilot_name=profile.pilot_name,
                    strength=PilotStrength.STRONG,
                    mode=profile.mode,
                ),
                strategy=profile.commander_family,
            )
            return {
                "profile": profile.model_dump(mode="json"),
                "runtime_weights": pilot.weights.model_dump(mode="json"),
                "parameter_hash_matches_registry": profile.parameter_hash
                == PilotRegistry(self.root).profile(profile.pilot_name).parameter_hash,
                "legal_actions_only": True,
                "omniscient_information_used": False,
            }

        return self._invoke("inspect_pilot", request, work)

    def run_pilot_benchmark(self, request: RunPilotBenchmarkInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, None)
            runner = PilotEnsembleRunner(self.root, self.decks)
            payload = runner.benchmark(
                deck_id=request.deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=Path(request.output_name).name,
            )
            payload["result_path"] = str(
                self.root
                / "data/runs/pilot_ensembles"
                / Path(request.output_name).name
                / "pilot_benchmark.json"
            )
            return payload

        return self._invoke(
            "run_pilot_benchmark",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def compare_pilots(self, request: ComparePilotsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            runner = PilotEnsembleRunner(self.root, self.decks)
            benchmark = runner.benchmark(
                deck_id=request.deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=Path(request.output_name).name,
            )
            return runner.compare(benchmark, request.pilot_names)

        return self._invoke(
            "compare_pilots",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_pilot_ensemble(self, request: RunPilotEnsembleInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            runner = PilotEnsembleRunner(self.root, self.decks)
            registry = runner.registry
            if request.ensemble_id:
                ensemble = registry.ensemble(request.ensemble_id)
            else:
                ensemble = PilotEnsembleDefinition(
                    ensemble_id=f"custom.{request.deck_id.replace('/', '.')}.{request.seed}",
                    version="1.0.0",
                    deck_id=request.deck_id,
                    members=tuple(
                        PilotEnsembleMember(pilot_name=item.pilot_name, weight=item.weight)
                        for item in request.custom_weights
                    ),
                )
            if ensemble.deck_id != request.deck_id:
                raise ToolExecutionError("ensemble deck_id does not match request deck_id")
            names = tuple(member.pilot_name for member in ensemble.members)
            baseline_name = (
                "KorvoldPilot" if request.deck_id.startswith("korvold/") else "RogShaiPilot"
            )
            benchmark_names = tuple(dict.fromkeys((baseline_name, *names)))
            benchmark = runner.benchmark(
                deck_id=request.deck_id,
                pilot_names=benchmark_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=Path(request.output_name).name,
            )
            summary = runner.ensemble_summary(benchmark, ensemble)
            output = (
                self.root
                / "data/runs/pilot_ensembles"
                / Path(request.output_name).name
                / "ensemble_summary.json"
            )
            atomic_write_json(output, summary)
            summary["result_path"] = str(output)
            return summary

        return self._invoke(
            "run_pilot_ensemble",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def test_variant_across_pilots(self, request: TestVariantAcrossPilotsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            if (
                request.baseline_deck_id not in self.decks
                or request.variant_deck_id not in self.decks
            ):
                raise ToolExecutionError("baseline and variant must be registered structural decks")
            runner = PilotEnsembleRunner(self.root, self.decks)
            baseline = runner.benchmark(
                deck_id=request.baseline_deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=f"{Path(request.output_name).name}-baseline",
            )
            variant = runner.benchmark(
                deck_id=request.variant_deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=f"{Path(request.output_name).name}-variant",
            )
            result = runner.variant_robustness(baseline, variant)
            output = (
                self.root / "data/runs/pilot_ensembles" / f"{Path(request.output_name).name}.json"
            )
            atomic_write_json(output, result)
            result["result_path"] = str(output)
            return result

        return self._invoke(
            "test_variant_across_pilots",
            request,
            work,
            deck_ids=(
                request.baseline_deck_id,
                request.variant_deck_id,
                *request.opponent_deck_ids,
            ),
            seed=request.seed,
            iterations=request.iterations,
        )

    def generate_pilot_robustness_report(
        self, request: GeneratePilotRobustnessReportInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            source = (self.root / request.result_path).resolve()
            if self.root not in source.parents:
                raise ToolExecutionError("result_path escapes project root")
            payload = json.loads(source.read_text(encoding="utf-8"))
            target = self.report_dir / Path(request.output_name).name
            text = PilotEnsembleRunner.markdown_report(payload)
            atomic_write_text(target, text)
            return {
                "report_path": str(target),
                "source_path": str(source),
                "estimate_type": "structural_model_estimates",
                "automatic_deck_changes": False,
            }

        return self._invoke("generate_pilot_robustness_report", request, work)

    def _counterfactual_lab(self) -> CounterfactualReplayLab:
        from commander_lab.counterfactual import CounterfactualReplayLab

        return CounterfactualReplayLab(self.root, external_engine_available=False)

    def find_counterfactual_branchpoints(self, request: Any) -> ToolResponse:
        def work() -> dict[str, Any]:
            rows = self._counterfactual_lab().find_branchpoints(
                request.source_path, actor_id=request.actor_id, phase=request.phase
            )
            return {
                "branchpoints": [row.model_dump(mode="json") for row in rows],
                "count": len(rows),
                "model_alternatives_only": True,
            }

        return self._invoke("find_counterfactual_branchpoints", request, work)

    def list_alternative_actions(self, request: Any) -> ToolResponse:
        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            lab.verify_branchpoint(branch, request.expected_state_hash)
            return {
                "branchpoint": branch.model_dump(mode="json"),
                "alternatives": [
                    row.model_dump(mode="json")
                    for row in branch.available_actions
                    if row.action_id != branch.chosen_action and row.legal
                ],
                "only_recorded_legal_candidates": True,
            }

        return self._invoke("list_alternative_actions", request, work)

    def run_counterfactual(self, request: Any) -> ToolResponse:
        from commander_lab.models import (
            CounterfactualEngineMode,
            HiddenInformationPolicy,
            SeedPolicy,
        )

        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            result = lab.run(
                branch,
                alternative_action=request.alternative_action,
                expected_state_hash=request.expected_state_hash,
                hidden_information_policy=HiddenInformationPolicy(
                    request.hidden_information_policy
                ),
                engine_mode=CounterfactualEngineMode(request.engine_mode),
                seed_policy=SeedPolicy(request.seed_policy),
                seed=request.seed,
                future_samples=request.future_samples,
                workers=request.workers,
            )
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {
                "result_path": str(target.relative_to(self.root))
            }

        return self._invoke(
            "run_counterfactual",
            request,
            work,
            seed=request.seed,
            iterations=request.future_samples,
        )

    def compare_counterfactuals(self, request: Any) -> ToolResponse:
        from commander_lab.counterfactual import CounterfactualReplayLab
        from commander_lab.models import CounterfactualResult

        def work() -> dict[str, Any]:
            rows = [
                CounterfactualResult.model_validate_json(
                    self._project_path(path).read_text(encoding="utf-8")
                )
                for path in request.result_paths
            ]
            result = CounterfactualReplayLab.compare(rows)
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {
                "result_path": str(target.relative_to(self.root))
            }

        return self._invoke("compare_counterfactuals", request, work)

    def generate_decision_regret_report(self, request: Any) -> ToolResponse:
        from commander_lab.counterfactual import CounterfactualReplayLab
        from commander_lab.models import CounterfactualResult

        def work() -> dict[str, Any]:
            result = CounterfactualResult.model_validate_json(
                self._project_path(request.result_path).read_text(encoding="utf-8")
            )
            regret = CounterfactualReplayLab.regret(result)
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            CounterfactualReplayLab.report(result, target)
            return {
                "regret": regret.model_dump(mode="json"),
                "report_path": str(target.relative_to(self.root)),
                "model_dependent": True,
            }

        return self._invoke("generate_decision_regret_report", request, work)

    def export_minimal_counterfactual_fixture(self, request: Any) -> ToolResponse:
        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            lab.verify_branchpoint(branch, request.expected_state_hash)
            target = self.root / "data/evals/golden" / Path(request.output_name).name
            payload = lab.export_fixture(branch, target)
            return payload | {"fixture_path": str(target.relative_to(self.root))}

        return self._invoke("export_minimal_counterfactual_fixture", request, work)

    def _diagnostic_engine(self) -> DecisionDiagnosticEngine:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        return DecisionDiagnosticEngine()

    def diagnose_card_performance(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.card_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("diagnose_card_performance", request, work)

    def diagnose_pilot_behavior(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.pilot_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("diagnose_pilot_behavior", request, work)

    def compare_deck_and_pilot_effects(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            result = self._diagnostic_engine().compare_effects(dataset)
            return result.model_dump(mode="json") | {"causal_identification": False}

        return self._invoke("compare_deck_and_pilot_effects", request, work)

    def classify_failure_cause(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.subject)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("classify_failure_cause", request, work)

    def recommend_next_experiment(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord

        def work() -> dict[str, Any]:
            diagnosis = DiagnosisRecord.model_validate_json(
                self._project_path(request.diagnosis_path).read_text(encoding="utf-8")
            )
            return DecisionDiagnosticEngine.next_experiment(diagnosis)

        return self._invoke("recommend_next_experiment", request, work)

    def generate_diagnostic_report(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord

        def work() -> dict[str, Any]:
            diagnoses = [
                DiagnosisRecord.model_validate_json(
                    self._project_path(path).read_text(encoding="utf-8")
                )
                for path in request.diagnosis_paths
            ]
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            DecisionDiagnosticEngine.report(diagnoses, target)
            return {
                "report_path": str(target.relative_to(self.root)),
                "diagnosis_count": len(diagnoses),
                "automatic_deck_changes": False,
                "empirical_proof_claimed": False,
            }

        return self._invoke("generate_diagnostic_report", request, work)

    def deck_decision_prepare(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                facade = PriorityWorkflowFacade(
                    self.root,
                    service=self,
                    context=session.context,
                )
                screen = facade.build_screen(request.deck_id, limit=request.candidate_limit)
                mana = facade.mulligan_mana(request.deck_id)
                validation = self._validate_deck_payload(
                    ValidateDeckInput(deck_id=request.deck_id, include_physical_allocation=True)
                )
                mulligan_request = CompareMulliganPoliciesInput(
                    deck_id=request.deck_id,
                    policies=request.mulligan_policies,
                    samples=request.mulligan_samples,
                    followup_samples=0,
                    seat_position=request.seat_position,
                    starting_player=request.seat_position == 1,
                    pod_size=4,
                    pilot_profile_id="rogshai.current.baseline",
                    pilot_version="current",
                    game_plan="balanced",
                    seed=request.mulligan_seed,
                    generate_keep_rules=False,
                )
                mulligan_context = self._mulligan_context_from_request(mulligan_request)
                mulligan_baseline = facade.mulligan.run(
                    mulligan_context,
                    tuple(MulliganPolicyName(value) for value in request.mulligan_policies),
                    samples=request.mulligan_samples,
                    followup_samples=0,
                    generate_keep_rules=False,
                ).model_dump(mode="json")
            session_identity = session.identity()
            return {
                "workflow": "deck_decision_prepare",
                "context": screen["context"],
                "deck_id": request.deck_id,
                "deck_hash": screen["deck_hash"],
                "validation": {
                    "active_deck": request.deck_id in facade.context.active_own_deck_ids,
                    "physical_legal_candidates": screen["eligible_candidate_count"],
                    "candidate_recall": screen["challenge_benchmark"]["legal_candidate_recall"],
                    "deck": validation,
                },
                "candidate_coverage": screen,
                "mana_mulligan_baseline": mana,
                "mulligan_policy_baseline": mulligan_baseline,
                "keep_rule_research_executed": False,
                "model_informativeness_status": "requires_structural_baseline_before_search",
                "next_call": "deck_decision_run",
                "workflow_session": session_identity,
                "automatic_deck_mutation": False,
            }

        return self._invoke(
            "deck_decision_prepare",
            request,
            work,
            deck_ids=(request.deck_id,),
        )

    def deck_decision_run(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                facade = PriorityWorkflowFacade(
                    self.root,
                    service=self,
                    context=session.context,
                )
                result = facade.compare_validate(
                    deck_id=request.deck_id,
                    remove=request.remove,
                    add_candidate_id=request.add_candidate_id,
                    iterations=request.iterations,
                    seed=request.seed,
                    max_turns=request.max_turns,
                    workers=request.workers,
                )
            result["workflow_session"] = session.identity()
            result["execution_envelope"] = {
                "requested_workers": request.workers,
                "effective_workers": 1,
                "worker_fallback_applied": request.workers != 1,
                "default_max_simulation_seconds": float(self.limits.max_simulation_seconds),
                "requested_max_simulation_seconds": request.max_simulation_seconds,
                "effective_max_simulation_seconds": (
                    float(request.max_simulation_seconds)
                    if request.max_simulation_seconds is not None
                    else float(self.limits.max_simulation_seconds)
                ),
                "classification": "execution_envelope_only_not_deck_quality_evidence",
            }
            return result

        return self._invoke(
            "deck_decision_run",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
        )

    def deck_decision_diagnose(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                result: dict[str, Any] = dict(
                    PriorityWorkflowFacade.diagnose_next_experiment(
                        request.comparison,
                        cohort_comparisons=tuple(request.cohort_comparisons),
                        opponent_evidence_quality=dict(request.opponent_evidence_quality),
                        failure_mode_metrics=tuple(request.failure_mode_metrics),
                    )
                )
            result["workflow_session"] = session.identity()
            return result

        return self._invoke("deck_decision_diagnose", request, work)

    def deck_decision_bundle(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                facade = PriorityWorkflowFacade(
                    self.root,
                    service=self,
                    context=session.context,
                )
                result: dict[str, Any] = dict(
                    facade.create_decision_bundle(
                        request.comparison,
                        self._project_path(request.output_directory),
                        worst_case_sensitivity_result=request.worst_case_sensitivity_result,
                        commander_denial_result=request.commander_denial_result,
                        ablation_result=request.ablation_result,
                        recommendation_status=request.recommendation_status,
                    )
                )
            result["workflow_session"] = session.identity()
            return result

        return self._invoke("deck_decision_bundle", request, work)
