from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from commander_lab.agents.ensemble import PilotEnsembleRunner, PilotRegistry
from commander_lab.agents.pilots import (
    build_pilot,
)  # Legacy builder: profile comes from PilotRegistry (#1036)
from commander_lab.models import (
    ComparePilotsInput,
    GeneratePilotRobustnessReportInput,
    InspectPilotInput,
    ListPilotProfilesInput,
    PilotConfig,
    PilotEnsembleDefinition,
    PilotEnsembleMember,
    PilotStrength,
    RunPilotBenchmarkInput,
    RunPilotEnsembleInput,
    TestVariantAcrossPilotsInput,
    ToolResponse,
)
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
)

if TYPE_CHECKING:
    pass

from .service_core import (
    ServiceCore,
    ToolExecutionError,
)


class ServicePilotsMixin(ServiceCore):
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
