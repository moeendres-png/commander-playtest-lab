from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from commander_lab.models import (
    ClassifyFailureCauseInput,
    CompareCounterfactualsInput,
    CompareDeckAndPilotEffectsInput,
    DiagnoseCardPerformanceInput,
    DiagnosePilotBehaviorInput,
    ExportMinimalCounterfactualFixtureInput,
    FindCounterfactualBranchpointsInput,
    GenerateDecisionRegretReportInput,
    GenerateDiagnosticReportInput,
    ListAlternativeActionsInput,
    RecommendNextExperimentInput,
    RunCounterfactualInput,
    ToolResponse,
)
from commander_lab.storage import (
    atomic_write_json,
)

if TYPE_CHECKING:
    from commander_lab.counterfactual import CounterfactualReplayLab
    from commander_lab.diagnostics import DecisionDiagnosticEngine

from .service_core import (
    ServiceCore,
)


class ServiceDiagnosticsMixin(ServiceCore):
    def _counterfactual_lab(self) -> CounterfactualReplayLab:
        from commander_lab.counterfactual import CounterfactualReplayLab

        return CounterfactualReplayLab(self.root, external_engine_available=False)

    def find_counterfactual_branchpoints(
        self, request: FindCounterfactualBranchpointsInput
    ) -> ToolResponse:
        def work() -> dict[str, object]:
            rows = self._counterfactual_lab().find_branchpoints(
                request.source_path, actor_id=request.actor_id, phase=request.phase
            )
            return {
                "branchpoints": [row.model_dump(mode="json") for row in rows],
                "count": len(rows),
                "model_alternatives_only": True,
            }

        return self._invoke("find_counterfactual_branchpoints", request, work)

    def list_alternative_actions(self, request: ListAlternativeActionsInput) -> ToolResponse:
        def work() -> dict[str, object]:
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

    def run_counterfactual(self, request: RunCounterfactualInput) -> ToolResponse:
        from commander_lab.models import (
            CounterfactualEngineMode,
            HiddenInformationPolicy,
            SeedPolicy,
        )

        def work() -> dict[str, object]:
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

    def compare_counterfactuals(self, request: CompareCounterfactualsInput) -> ToolResponse:
        from commander_lab.counterfactual import CounterfactualReplayLab
        from commander_lab.models import CounterfactualResult

        def work() -> dict[str, object]:
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

    def generate_decision_regret_report(
        self, request: GenerateDecisionRegretReportInput
    ) -> ToolResponse:
        from commander_lab.counterfactual import CounterfactualReplayLab
        from commander_lab.models import CounterfactualResult

        def work() -> dict[str, object]:
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

    def export_minimal_counterfactual_fixture(
        self, request: ExportMinimalCounterfactualFixtureInput
    ) -> ToolResponse:
        def work() -> dict[str, object]:
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

    def diagnose_card_performance(self, request: DiagnoseCardPerformanceInput) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, object]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.card_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("diagnose_card_performance", request, work)

    def diagnose_pilot_behavior(self, request: DiagnosePilotBehaviorInput) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, object]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.pilot_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("diagnose_pilot_behavior", request, work)

    def compare_deck_and_pilot_effects(
        self, request: CompareDeckAndPilotEffectsInput
    ) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, object]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            result = self._diagnostic_engine().compare_effects(dataset)
            return result.model_dump(mode="json") | {"causal_identification": False}

        return self._invoke("compare_deck_and_pilot_effects", request, work)

    def classify_failure_cause(self, request: ClassifyFailureCauseInput) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, object]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.subject)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("classify_failure_cause", request, work)

    def recommend_next_experiment(self, request: RecommendNextExperimentInput) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord

        def work() -> dict[str, object]:
            diagnosis = DiagnosisRecord.model_validate_json(
                self._project_path(request.diagnosis_path).read_text(encoding="utf-8")
            )
            return DecisionDiagnosticEngine.next_experiment(diagnosis)

        return self._invoke("recommend_next_experiment", request, work)

    def generate_diagnostic_report(self, request: GenerateDiagnosticReportInput) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord

        def work() -> dict[str, object]:
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
