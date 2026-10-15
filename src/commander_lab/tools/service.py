from __future__ import annotations

import subprocess
from collections import Counter
from statistics import fmean
from typing import TYPE_CHECKING, Any

from commander_lab.engine.rules import (
    RulesEngineManager,
    load_project_rules_decks,
)
from commander_lab.models import (
    ActionProposal,
    RulesGameRequest,
    RunEngineBackedMatchupInput,
    RunMultifidelityComparisonInput,
    RunRobustnessSuiteInput,
    RunRulesCoverageGateInput,
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

if TYPE_CHECKING:
    pass

from .service_core import ApprovalRequired as ApprovalRequired
from .service_core import EstimateType as EstimateType
from .service_core import ServiceCore
from .service_core import ToolExecutionError as ToolExecutionError
from .service_core import _deterministic_structural_run_id as _deterministic_structural_run_id
from .service_diagnostics import ServiceDiagnosticsMixin
from .service_knowledge import ServiceKnowledgeMixin
from .service_mulligan import ServiceMulliganMixin
from .service_optimizer import ServiceOptimizerMixin
from .service_pilots import ServicePilotsMixin
from .service_reports import ServiceReportsMixin
from .service_search import ServiceSearchMixin
from .service_simulation import ServiceSimulationMixin


class CommanderToolService(
    ServiceOptimizerMixin,
    ServiceSearchMixin,
    ServiceSimulationMixin,
    ServiceMulliganMixin,
    ServiceKnowledgeMixin,
    ServicePilotsMixin,
    ServiceDiagnosticsMixin,
    ServiceReportsMixin,
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
