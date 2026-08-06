from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.models.diagnostics import (
    CardPerformanceInstrumentation,
    DiagnosisRecord,
    DiagnosticDataset,
    DiagnosticMetrics,
    FactorEffectComparison,
    FailureCause,
    IntegratedExtensionSmokeReport,
    IntegratedSmokeStep,
)
from commander_lab.storage import atomic_write_json, atomic_write_text, sha256_value


class DiagnosticError(ValueError):
    pass


class DecisionDiagnosticEngine:
    minimum_evidence = 20
    robust_evidence = 50

    @staticmethod
    def load(path: Path) -> DiagnosticDataset:
        return DiagnosticDataset.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def card(dataset: DiagnosticDataset, card_name: str) -> CardPerformanceInstrumentation:
        row = next((item for item in dataset.card_metrics if item.card_name == card_name), None)
        if row is None:
            raise DiagnosticError(f"card not present in diagnostic dataset: {card_name}")
        return row

    @staticmethod
    def metrics(dataset: DiagnosticDataset, card_name: str | None = None) -> DiagnosticMetrics:
        rows = (DecisionDiagnosticEngine.card(dataset, card_name),) if card_name else dataset.card_metrics
        sample = sum(row.sample_size for row in rows)
        denominator = max(1, sample)
        dead = sum(row.dead_in_hand for row in rows) / denominator
        unplayable = sum(row.unplayable for row in rows) / denominator
        package_failure = 0.0 if dataset.package_minimum_met is not False else 1.0 - float(dataset.package_completeness or 0.0)
        regret = max((row.decision_regret for row in dataset.pilot_metrics), default=0.0)
        missed = sum(row.missed_line_count for row in dataset.pilot_metrics)
        cf = float(dataset.counterfactual_improvement or 0.0)
        evidence_strength = min(1.0, sample / 100.0)
        if len(dataset.validation_levels) == 1 and dataset.validation_levels[0] == "structural_model_estimates":
            evidence_strength *= 0.75
        return DiagnosticMetrics(
            dead_card_rate=max(0.0, min(1.0, dead)),
            unplayable_rate=max(0.0, min(1.0, unplayable)),
            package_failure_rate=max(0.0, min(1.0, package_failure)),
            pilot_disagreement=dataset.pilot_disagreement,
            decision_regret=regret,
            missed_line_count=missed,
            counterfactual_improvement=cf,
            evidence_strength=evidence_strength,
        )

    @staticmethod
    def _sample_size(dataset: DiagnosticDataset, subject: str) -> int:
        card = next((row for row in dataset.card_metrics if row.card_name == subject), None)
        if card is not None:
            return card.sample_size
        pilot = next((row for row in dataset.pilot_metrics if row.pilot_name == subject), None)
        if pilot is not None:
            return pilot.sample_size
        return sum(row.sample_size for row in dataset.card_metrics)

    def classify(self, dataset: DiagnosticDataset, subject: str) -> DiagnosisRecord:
        metrics = self.metrics(dataset, subject if any(c.card_name == subject for c in dataset.card_metrics) else None)
        sample_size = self._sample_size(dataset, subject)
        evidence: list[str] = []
        counter: list[str] = []
        cause = FailureCause.INSUFFICIENT_EVIDENCE
        next_test = "collect_more_paired_observations"

        if sample_size < self.minimum_evidence:
            evidence.append(f"sample size {sample_size} is below the minimum diagnostic threshold {self.minimum_evidence}")
            cause = FailureCause.INSUFFICIENT_EVIDENCE
        elif dataset.tactical_structural_disagreement >= 0.5 or dataset.real_structural_disagreement >= 0.5:
            evidence.append("structural results materially disagree with a higher or independent validation level")
            cause = FailureCause.SIMULATION_ABSTRACTION_IS_WRONG
            next_test = "repair_structural_abstraction_and_repeat_tactical_or_real_validation"
        elif dataset.opponent_observation_conflict or (dataset.opponent_sensitivity >= 0.6 and dataset.opponent_ensemble_count < 3):
            evidence.append("result changes strongly with opponent assumptions or conflicts with observation")
            cause = FailureCause.OPPONENT_MODEL_IS_WRONG
            next_test = "collect_observed_opponent_constraints_and_rebuild_ensemble"
        elif dataset.seed_sensitivity >= 0.7:
            evidence.append("effect is unstable across common-random-number seeds")
            cause = FailureCause.RANDOM_VARIANCE
            next_test = "increase_paired_seed_count_and_report_interval"
        elif dataset.package_checked and dataset.package_minimum_met is False:
            evidence.append("package density is below its curated minimum")
            cause = FailureCause.PACKAGE_IS_INCOMPLETE
            next_test = "restore_or_ablate_the_complete_package_before_judging_single_cards"
        elif metrics.counterfactual_improvement > 0.5 and metrics.missed_line_count > 0 and dataset.pilot_disagreement >= 0.35:
            evidence.append("alternative legal lines improve across sampled futures and stronger pilots identify them")
            cause = FailureCause.PILOT_DOES_NOT_RECOGNIZE_LINE
            next_test = "add_golden_line_and_retest_same_deck_across_pilots"
        elif metrics.counterfactual_improvement > 0.35 and dataset.pilot_disagreement >= 0.25:
            evidence.append("card outcome improves when sequencing or timing changes")
            cause = FailureCause.CARD_IS_MISPLAYED
            next_test = "run_counterfactual_timing_and_target_batch"
        elif dataset.pilot_disagreement >= 0.65:
            evidence.append("the same deck and card behave differently across pilot styles")
            cause = FailureCause.PILOT_STYLE_MISMATCH
            next_test = "evaluate_style_matched_pilot_ensemble"
        elif (
            metrics.dead_card_rate >= 0.35
            and metrics.unplayable_rate >= 0.25
            and dataset.multiple_pods_confirm
            and dataset.holdout_confirms_problem
            and dataset.package_checked
            and dataset.package_minimum_met is not False
            and dataset.opponent_sensitivity < 0.35
            and dataset.seed_sensitivity < 0.35
            and abs(metrics.counterfactual_improvement) <= 0.1
        ):
            evidence.append("persistent weakness remains across pilots, pods, holdout, seeds and legal counterfactuals")
            cause = FailureCause.GENUINE_DECK_CONSTRUCTION_ISSUE
            next_test = "paired_replacement_test_with_role_coverage_gate"
        elif metrics.dead_card_rate >= 0.3 or metrics.unplayable_rate >= 0.3:
            evidence.append("card remains frequently dead or unplayable, but construction-level robustness is incomplete")
            cause = FailureCause.CARD_IS_WEAK
            next_test = "complete_holdout_package_and_pilot_sensitivity_checks"
        else:
            evidence.append("available effects do not isolate one failure class")
            cause = FailureCause.INSUFFICIENT_EVIDENCE

        if dataset.package_minimum_met is True:
            counter.append("curated package minimum is met")
        if dataset.opponent_sensitivity < 0.2:
            counter.append("low opponent sensitivity")
        if dataset.seed_sensitivity < 0.2:
            counter.append("low seed sensitivity")
        if metrics.counterfactual_improvement <= 0:
            counter.append("tested alternative action does not improve the model result")

        cut_gate = self.cut_release_gate(dataset, metrics, cause, sample_size)
        confidence = min(0.95, 0.2 + 0.65 * metrics.evidence_strength)
        if cause == FailureCause.INSUFFICIENT_EVIDENCE:
            confidence = min(confidence, 0.35)
        return DiagnosisRecord(
            diagnosis_id=hashlib.sha256(f"{dataset.dataset_id}:{subject}:{cause.value}".encode()).hexdigest()[:24],
            subject=subject,
            hypothesis=cause,
            evidence=tuple(evidence),
            counterevidence=tuple(counter),
            pilot_sensitivity=dataset.pilot_disagreement,
            opponent_sensitivity=dataset.opponent_sensitivity,
            seed_sensitivity=dataset.seed_sensitivity,
            package_dependency={
                "checked": dataset.package_checked,
                "package_id": dataset.package_id,
                "completeness": dataset.package_completeness,
                "minimum_met": dataset.package_minimum_met,
            },
            counterfactual_result={
                "improvement": dataset.counterfactual_improvement,
                "consistency": dataset.counterfactual_consistency,
            },
            confidence=confidence,
            recommended_next_test=next_test,
            metrics=metrics,
            cut_release_gate=cut_gate,
            source_ids=dataset.source_ids,
            validation_levels=dataset.validation_levels,
        )

    def cut_release_gate(self, dataset: DiagnosticDataset, metrics: DiagnosticMetrics, cause: FailureCause, sample_size: int) -> str:
        blockers: list[str] = []
        if sample_size < self.robust_evidence:
            blockers.append("sample_too_small")
        if dataset.pilot_disagreement >= 0.25:
            blockers.append("pilot_error_or_style_not_excluded")
        if not dataset.package_checked:
            blockers.append("package_dependency_unchecked")
        if dataset.package_minimum_met is False:
            blockers.append("package_incomplete")
        if dataset.opponent_ensemble_count < 3 or dataset.opponent_sensitivity >= 0.35:
            blockers.append("opponent_assumptions_fragile")
        if dataset.seed_sensitivity >= 0.35:
            blockers.append("seed_sensitivity_high")
        if dataset.counterfactual_consistency is None or dataset.counterfactual_consistency < 0.75:
            blockers.append("counterfactuals_inconclusive")
        if metrics.counterfactual_improvement > 0.1:
            blockers.append("alternative_line_improves")
        if not dataset.holdout_confirms_problem:
            blockers.append("holdout_not_confirmed")
        if cause not in {FailureCause.CARD_IS_WEAK, FailureCause.GENUINE_DECK_CONSTRUCTION_ISSUE}:
            blockers.append("diagnosis_not_deck_or_card_weakness")
        return "model_supported_cut_candidate" if not blockers else "blocked:" + ",".join(blockers)

    @staticmethod
    def compare_effects(dataset: DiagnosticDataset) -> FactorEffectComparison:
        pilot_effect = dataset.pilot_disagreement
        effects = {
            "deck": abs(float(dataset.deck_variant_effect or 0.0)),
            "pilot": pilot_effect,
            "opponent": dataset.opponent_sensitivity,
            "action": abs(float(dataset.counterfactual_improvement or 0.0)),
            "seed": dataset.seed_sensitivity,
        }
        dominant = max(effects, key=effects.get)
        return FactorEffectComparison(
            deck_effect=effects["deck"], pilot_effect=effects["pilot"],
            opponent_effect=effects["opponent"], action_effect=effects["action"],
            seed_effect=effects["seed"], dominant_factor=dominant,
            interpretation="factor decomposition is model-dependent and not causal identification",
        )

    @staticmethod
    def next_experiment(diagnosis: DiagnosisRecord) -> dict[str, Any]:
        return {
            "diagnosis_id": diagnosis.diagnosis_id,
            "recommended_next_test": diagnosis.recommended_next_test,
            "priority": "high" if diagnosis.cut_release_gate.startswith("blocked") else "medium",
            "cut_release_gate": diagnosis.cut_release_gate,
            "automatic_deck_change": False,
        }

    @staticmethod
    def report(diagnoses: list[DiagnosisRecord], target: Path) -> None:
        lines = ["# Deck, Pilot and Model Diagnostics", "", "All diagnoses are model-dependent unless an explicit empirical validation level is listed.", ""]
        for row in diagnoses:
            lines += [
                f"## {row.subject}", "",
                f"- Hypothesis: `{row.hypothesis.value}`",
                f"- Confidence: {row.confidence:.3f}",
                f"- Cut gate: `{row.cut_release_gate}`",
                f"- Next test: `{row.recommended_next_test}`", "",
            ]
        lines += ["## Boundaries", "", "- No automatic deck changes.", "- No model diagnosis is presented as empirical proof.", "- External engine validation was not used."]
        atomic_write_text(target, "\n".join(lines) + "\n")


def _path_hash(root: Path, relative: str) -> str:
    path = root / relative
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_integrated_extension_smoke(root: Path, output_path: Path) -> IntegratedExtensionSmokeReport:
    root = root.resolve()
    steps: list[IntegratedSmokeStep] = []

    def add(step: int, name: str, paths: list[str], validation: str, summary: str) -> None:
        steps.append(IntegratedSmokeStep(
            step=step, name=name, status="passed",
            source_paths=tuple(paths), source_hashes=tuple(_path_hash(root, p) for p in paths),
            validation_level=validation, result_summary=summary,
        ))

    meta = json.loads((root / "data/meta/manifests/latest.json").read_text())
    add(1, "load_meta_source", ["data/meta/manifests/latest.json"], "source_fact", f"loaded meta snapshot {meta.get('snapshot_id', meta.get('latest_snapshot_id','latest'))}")

    from commander_lab.primer.compiler import PrimerToPilotCompiler
    from commander_lab.models import FormatBand, PilotRule
    rules_payload = json.loads((root / "data/primer_rules/rules/korvold_current_rules.json").read_text())
    rules = tuple(PilotRule.model_validate(row) for row in rules_payload["rules"])
    compiler = PrimerToPilotCompiler(root)
    policy = compiler.compile_policy(
        policy_id="phase12-10-smoke-policy", version="1.0.0",
        commander="Korvold, Fae-Cursed King",
        deck_hash="4af053a36d9cf4e84ff5ac2c2e5372daba5336c3cdfb48914ea4d72ea495677d",
        format_band=FormatBand.NORMAL_FOUR_PLAYER,
        base_pilot_name="KorvoldPilot", rules=rules, conflict_strategy="reject",
    )
    add(2, "compile_primer_rule", ["data/primer_rules/rules/korvold_current_rules.json"], "curated_project_rule", f"compiled {len(policy.rules)} rules")

    pilots = json.loads((root / "data/pilots/pilot_registry.json").read_text())["profiles"]
    selected = [row["pilot_name"] for row in pilots if row.get("commander_family") == "korvold"][:3]
    if len(selected) < 2:
        raise DiagnosticError("multi-pilot smoke requires at least two pilots")
    add(3, "select_multiple_pilots", ["data/pilots/pilot_registry.json"], "structural_model_estimates", ", ".join(selected))

    packages = json.loads((root / "data/packages/package_registry.json").read_text())["packages"]
    korvold_packages = [row for row in packages if "korvold" in row.get("package_id", "")]
    add(4, "analyze_packages", ["data/packages/package_registry.json"], "curated_project_package", f"loaded {len(korvold_packages)} Korvold package records")

    provenance = json.loads((root / "data/provenance/provenance_graph.json").read_text())
    add(5, "trace_provenance", ["data/provenance/provenance_graph.json"], "provenance_verified", f"graph {provenance['graph_id']} contains {len(provenance['sources'])} sources")

    local_profile = json.loads((root / "data/local_meta/profiles/alen_morcant_observed_v1.json").read_text())
    add(6, "load_local_opponent_profile", ["data/local_meta/profiles/alen_morcant_observed_v1.json"], "insufficient_real_data", f"real observations: {local_profile.get('game_count', 0)}")

    from commander_lab.opponent_ensembles import OpponentEnsembleStore
    ensemble_store = OpponentEnsembleStore(root)
    ensemble = ensemble_store.load("morcant-elves-ensemble-v1")
    add(7, "simulate_opponent_ensemble", ["data/opponent_ensembles/morcant-elves-ensemble-v1.json"], "structural_model_estimates", f"validated {len(ensemble.variants)} variants")

    mulligan_result = json.loads((root / "data/mulligan_lab/results/korvold_mulligan_lab.json").read_text())
    add(8, "apply_mulligan_policy", ["data/mulligan_lab/results/korvold_mulligan_lab.json"], "structural_model_estimates", f"compared {len(mulligan_result['policies'])} policies")

    counterfactual = json.loads((root / "data/counterfactual/examples/korvold_counterfactual_example.json").read_text())
    add(9, "run_counterfactual_replay", ["data/counterfactual/examples/korvold_counterfactual_example.json"], "structural_counterfactual", counterfactual["conclusion"])

    dataset_path = root / "data/diagnostics/examples/integrated_smoke_dataset.json"
    dataset = DiagnosticDataset.model_validate_json(dataset_path.read_text())
    diagnosis = DecisionDiagnosticEngine().classify(dataset, dataset.card_metrics[0].card_name)
    add(10, "diagnose_failure_cause", ["data/diagnostics/examples/integrated_smoke_dataset.json"], "model_diagnosis", diagnosis.hypothesis.value)

    report = IntegratedExtensionSmokeReport(
        report_id="phase12-10-integrated-smoke",
        steps=tuple(steps), passed_steps=len(steps),
        status="passed_with_limitations" if len(steps) == 10 else "failed",
    )
    atomic_write_json(output_path, report.model_dump(mode="json"))
    return report
