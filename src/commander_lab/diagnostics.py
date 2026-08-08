from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import fmean
from typing import Any, ClassVar

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
from commander_lab.storage import atomic_write_json, atomic_write_text


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
        rows = (
            (DecisionDiagnosticEngine.card(dataset, card_name),)
            if card_name
            else dataset.card_metrics
        )
        sample = sum(row.sample_size for row in rows)
        denominator = max(1, sample)
        dead = sum(row.dead_in_hand for row in rows) / denominator
        unplayable = sum(row.unplayable for row in rows) / denominator
        package_failure = (
            0.0
            if dataset.package_minimum_met is not False
            else 1.0 - float(dataset.package_completeness or 0.0)
        )
        regret = max((row.decision_regret for row in dataset.pilot_metrics), default=0.0)
        missed = sum(row.missed_line_count for row in dataset.pilot_metrics)
        cf = float(dataset.counterfactual_improvement or 0.0)
        evidence_strength = min(1.0, sample / 100.0)
        if (
            len(dataset.validation_levels) == 1
            and dataset.validation_levels[0] == "structural_model_estimates"
        ):
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
        metrics = self.metrics(
            dataset, subject if any(c.card_name == subject for c in dataset.card_metrics) else None
        )
        sample_size = self._sample_size(dataset, subject)
        evidence: list[str] = []
        counter: list[str] = []
        cause = FailureCause.INSUFFICIENT_EVIDENCE
        next_test = "collect_more_paired_observations"

        if sample_size < self.minimum_evidence:
            evidence.append(
                f"sample size {sample_size} is below the minimum diagnostic threshold "
                f"{self.minimum_evidence}"
            )
            cause = FailureCause.INSUFFICIENT_EVIDENCE
        elif (
            dataset.tactical_structural_disagreement >= 0.5
            or dataset.external_rules_structural_disagreement >= 0.5
        ):
            evidence.append(
                "structural results materially disagree with a higher or "
                "independent validation level"
            )
            cause = FailureCause.SIMULATION_ABSTRACTION_IS_WRONG
            next_test = "repair_structural_abstraction_and_repeat_tactical_or_external_validation"
        elif dataset.opponent_observation_conflict or (
            dataset.opponent_sensitivity >= 0.6 and dataset.opponent_ensemble_count < 3
        ):
            evidence.append(
                "result changes strongly with opponent assumptions or conflicts with observation"
            )
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
        elif (
            metrics.counterfactual_improvement > 0.5
            and metrics.missed_line_count > 0
            and dataset.pilot_disagreement >= 0.35
        ):
            evidence.append(
                "alternative legal lines improve across sampled futures and "
                "stronger pilots identify them"
            )
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
            evidence.append(
                "persistent weakness remains across pilots, pods, holdout, "
                "seeds and legal counterfactuals"
            )
            cause = FailureCause.GENUINE_DECK_CONSTRUCTION_ISSUE
            next_test = "paired_replacement_test_with_role_coverage_gate"
        elif metrics.dead_card_rate >= 0.3 or metrics.unplayable_rate >= 0.3:
            evidence.append(
                "card remains frequently dead or unplayable, but "
                "construction-level robustness is incomplete"
            )
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
            diagnosis_id=hashlib.sha256(
                f"{dataset.dataset_id}:{subject}:{cause.value}".encode()
            ).hexdigest()[:24],
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

    def cut_release_gate(
        self,
        dataset: DiagnosticDataset,
        metrics: DiagnosticMetrics,
        cause: FailureCause,
        sample_size: int,
    ) -> str:
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
            deck_effect=effects["deck"],
            pilot_effect=effects["pilot"],
            opponent_effect=effects["opponent"],
            action_effect=effects["action"],
            seed_effect=effects["seed"],
            dominant_factor=dominant,
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
        lines = [
            "# Deck, Pilot and Model Diagnostics",
            "",
            "All diagnoses are model-dependent unless an explicit "
            "empirical validation level is listed.",
            "",
        ]
        for row in diagnoses:
            lines += [
                f"## {row.subject}",
                "",
                f"- Hypothesis: `{row.hypothesis.value}`",
                f"- Confidence: {row.confidence:.3f}",
                f"- Cut gate: `{row.cut_release_gate}`",
                f"- Next test: `{row.recommended_next_test}`",
                "",
            ]
        lines += [
            "## Boundaries",
            "",
            "- No automatic deck changes.",
            "- No model diagnosis is presented as empirical proof.",
            "- External engine validation was not used.",
        ]
        atomic_write_text(target, "\n".join(lines) + "\n")


class DiagnosticInstrumentationCollector:
    """Build diagnostic evidence from actual Structural Simulator event logs.

    The collector never treats structural observations as empirical playtest data. It derives
    auditable counters from immutable JSONL events and retains the source hashes in the dataset.
    """

    SUCCESS_EVENTS: ClassVar[set[str]] = {
        "ramp_resolved",
        "permanent_resolved",
        "selection_resolved",
        "boardwipe_resolved",
        "graveyard_hate_resolved",
        "recursion_resolved",
        "finisher_resolved",
        "protection_resolved",
        "counter_resolved",
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        from commander_lab.engine.structural import load_project_structural_decks

        self.decks = load_project_structural_decks(
            self.root, include_synthetic_fixtures=True, include_current_opponents=True
        )

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise DiagnosticError("diagnostic log path must stay inside project root")
        if not candidate.is_file():
            raise DiagnosticError(f"diagnostic log does not exist: {path}")
        return candidate

    @staticmethod
    def _events(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DiagnosticError(f"invalid diagnostic JSONL at {path}:{number}") from exc
            if not isinstance(row, dict):
                raise DiagnosticError(f"diagnostic event must be an object at {path}:{number}")
            rows.append(row)
        return rows

    def build(
        self,
        *,
        dataset_id: str,
        deck_id: str,
        log_paths: list[str | Path],
        player_id: str = "p1",
        package_id: str | None = None,
        package_completeness: float | None = None,
        package_minimum_met: bool | None = None,
        opponent_ensemble_count: int = 0,
        opponent_sensitivity: float = 0.0,
        seed_sensitivity: float = 0.0,
        counterfactual_improvement: float | None = None,
        counterfactual_consistency: float | None = None,
        holdout_confirms_problem: bool = False,
        multiple_pods_confirm: bool = False,
    ) -> DiagnosticDataset:
        if deck_id not in self.decks:
            raise DiagnosticError(f"unknown structural deck: {deck_id}")
        deck = self.decks[deck_id]
        profiles = {card.oracle_name: card for card in deck.cards}
        counters: dict[str, dict[str, Any]] = {
            name: {
                "drawn": 0,
                "opening_hand": 0,
                "mulliganed": 0,
                "kept": 0,
                "played": 0,
                "unplayable": 0,
                "discarded": 0,
                "removed": 0,
                "successful": 0,
                "without_value": 0,
                "dead_in_hand": 0,
                "turns": [],
                "synergy_partner_present": 0,
                "pilot_decisions": set(),
                "alternative_lines": set(),
            }
            for name in profiles
        }
        pilot_rows: dict[str, dict[str, Any]] = {}
        source_ids: list[str] = []
        game_count = 0

        for raw_path in log_paths:
            path = self._resolve(raw_path)
            events = self._events(path)
            game_count += 1
            source_ids.append(f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}")
            resolved_cards: set[str] = set()
            played_cards: set[str] = set()
            final_hand: list[str] = []
            final_mana = 0.0
            pilot_name = "unknown"
            placement: float | None = None

            for event in events:
                payload = event.get("payload") or {}
                event_type = str(event.get("event_type") or "")
                actor = str(event.get("actor_id") or "")
                if event_type == "game_started":
                    for pilot in payload.get("pilots", []):
                        if str(pilot.get("player_id")) == player_id:
                            pilot_name = str(pilot.get("pilot_name") or "unknown")
                if actor == player_id and event_type == "london_mulligan":
                    initial = [str(v) for v in payload.get("initial_hand", [])]
                    kept = [str(v) for v in payload.get("kept_cards", [])]
                    bottomed = [str(v) for v in payload.get("bottomed", [])]
                    for name in initial:
                        if name in counters:
                            counters[name]["opening_hand"] += 1
                    for name in kept:
                        if name in counters:
                            counters[name]["kept"] += 1
                    for name in bottomed:
                        if name in counters:
                            counters[name]["mulliganed"] += 1
                elif actor == player_id and event_type == "cards_drawn":
                    for name in payload.get("cards", []):
                        if str(name) in counters:
                            counters[str(name)]["drawn"] += 1
                elif actor == player_id and event_type in {"spell_cast", "commander_cast"}:
                    name = str(payload.get("card") or "")
                    if name in counters:
                        counters[name]["played"] += 1
                        played_cards.add(name)
                        counters[name]["turns"].append(float(payload.get("turn") or 0.0))
                elif actor == player_id and event_type == "spell_countered":
                    name = str(payload.get("card") or "")
                    if name in counters:
                        counters[name]["without_value"] += 1
                elif actor == player_id and event_type in self.SUCCESS_EVENTS:
                    name = str(payload.get("card") or "")
                    if name in counters:
                        counters[name]["successful"] += 1
                        resolved_cards.add(name)
                elif event_type == "permanent_removed" and str(payload.get("target")) == player_id:
                    name = str(payload.get("card") or "")
                    if name in counters:
                        counters[name]["removed"] += 1
                elif event_type == "commander_removed" and str(payload.get("target")) == player_id:
                    name = str(payload.get("commander") or "")
                    if name in counters:
                        counters[name]["removed"] += 1
                elif actor == player_id and event_type == "pilot_decision":
                    selected = str(payload.get("selected_action_id") or "pass")
                    selected_utility = float(payload.get("selected_utility") or 0.0)
                    candidates = payload.get("candidates") or []
                    best = max(
                        (
                            float(row[1])
                            for row in candidates
                            if isinstance(row, list) and len(row) > 1
                        ),
                        default=selected_utility,
                    )
                    stats = pilot_rows.setdefault(
                        pilot_name,
                        {
                            "sample_size": 0,
                            "success": 0,
                            "regret": 0.0,
                            "missed": 0,
                            "placements": [],
                        },
                    )
                    stats["sample_size"] += 1
                    stats["regret"] += max(0.0, best - selected_utility)
                    stats["missed"] += int(best > selected_utility + 1e-9)
                    stats["success"] += int(best <= selected_utility + 1e-9)
                    for name in counters:
                        if name.lower() in selected.lower():
                            counters[name]["pilot_decisions"].add(selected)
                        for candidate in candidates:
                            candidate_id = (
                                str(candidate[0])
                                if isinstance(candidate, list) and candidate
                                else ""
                            )
                            if name.lower() in candidate_id.lower() and candidate_id != selected:
                                counters[name]["alternative_lines"].add(candidate_id)
                elif event_type == "turn_summary" and actor == player_id:
                    after = payload.get("after") or {}
                    final_mana = (
                        float(after.get("lands", 0.0))
                        + float(after.get("ramp", 0.0))
                        + float(after.get("resources", 0.0)) * 0.25
                    )
                elif event_type == "state_checkpoint" and payload.get("reason") == "game_end":
                    snapshot = next(
                        (
                            row
                            for row in payload.get("players", [])
                            if str(row.get("player_id")) == player_id
                        ),
                        None,
                    )
                    if snapshot:
                        final_hand = [
                            str(v) for v in (snapshot.get("diagnostic_zones") or {}).get("hand", [])
                        ]
                elif event_type == "player_eliminated" and actor == player_id:
                    placement = float(payload.get("placement") or 0.0)
            if placement is None:
                end = next(
                    (e for e in reversed(events) if e.get("event_type") == "game_ended"), None
                )
                if end:
                    winners = set((end.get("payload") or {}).get("winner_ids", []))
                    placement = 1.0 if player_id in winners else None
            if pilot_name in pilot_rows and placement is not None:
                pilot_rows[pilot_name]["placements"].append(placement)

            for name in played_cards - resolved_cards:
                if counters[name]["without_value"] == 0:
                    counters[name]["without_value"] += 1
            for name in final_hand:
                if name not in counters:
                    continue
                profile = profiles[name]
                if profile.mana_value > final_mana + 0.5:
                    counters[name]["unplayable"] += 1
                if profile.mana_value >= 5 or profile.turn_cycle_risk >= 0.7:
                    counters[name]["dead_in_hand"] += 1
            for name in resolved_cards:
                profile = profiles[name]
                if profile.package_ids:
                    partner = any(
                        other != name and bool(profile.package_ids & profiles[other].package_ids)
                        for other in resolved_cards
                        if other in profiles
                    )
                    counters[name]["synergy_partner_present"] += int(partner)

        card_metrics: list[CardPerformanceInstrumentation] = []
        for name, row in counters.items():
            observed = max(
                game_count,
                *(
                    int(row[key])
                    for key in (
                        "drawn",
                        "opening_hand",
                        "mulliganed",
                        "kept",
                        "played",
                        "unplayable",
                        "discarded",
                        "removed",
                        "successful",
                        "without_value",
                        "dead_in_hand",
                        "synergy_partner_present",
                    )
                ),
            )
            if observed == 0:
                continue
            turns = row["turns"]
            profile = profiles[name]
            card_metrics.append(
                CardPerformanceInstrumentation(
                    card_name=name,
                    sample_size=observed,
                    drawn=row["drawn"],
                    opening_hand=row["opening_hand"],
                    mulliganed=row["mulliganed"],
                    kept=row["kept"],
                    played=row["played"],
                    unplayable=row["unplayable"],
                    discarded=row["discarded"],
                    removed=row["removed"],
                    successful=row["successful"],
                    without_value=row["without_value"],
                    dead_in_hand=row["dead_in_hand"],
                    average_turn_played=fmean(turns) if turns else None,
                    mana_efficiency=(
                        row["successful"] / max(1.0, profile.mana_value * max(1, row["played"]))
                    )
                    if row["played"]
                    else None,
                    synergy_partner_present=row["synergy_partner_present"],
                    pilot_decisions=tuple(sorted(row["pilot_decisions"])),
                    alternative_lines=tuple(sorted(row["alternative_lines"])),
                    counterfactual_outcome_delta=counterfactual_improvement,
                )
            )
        pilot_metrics = []
        for name, row in pilot_rows.items():
            sample = max(1, int(row["sample_size"]))
            pilot_metrics.append(
                __import__(
                    "commander_lab.models.diagnostics", fromlist=["PilotDiagnosticEvidence"]
                ).PilotDiagnosticEvidence(
                    pilot_name=name,
                    sample_size=sample,
                    success_rate=float(row["success"]) / sample,
                    dead_card_rate=sum(c.dead_in_hand for c in card_metrics)
                    / max(1, sum(c.sample_size for c in card_metrics)),
                    unplayable_rate=sum(c.unplayable for c in card_metrics)
                    / max(1, sum(c.sample_size for c in card_metrics)),
                    decision_regret=float(row["regret"]) / sample,
                    missed_line_count=int(row["missed"]),
                    average_placement=fmean(row["placements"]) if row["placements"] else None,
                )
            )
        disagreement = 0.0
        if len(pilot_metrics) > 1:
            rates = [row.success_rate for row in pilot_metrics]
            disagreement = min(1.0, max(rates) - min(rates))
        return DiagnosticDataset(
            dataset_id=dataset_id,
            deck_id=deck_id,
            deck_hash=deck.deck_hash,
            card_metrics=tuple(card_metrics),
            pilot_metrics=tuple(pilot_metrics),
            package_checked=package_id is not None,
            package_id=package_id,
            package_completeness=package_completeness,
            package_minimum_met=package_minimum_met,
            opponent_ensemble_count=opponent_ensemble_count,
            opponent_sensitivity=opponent_sensitivity,
            seed_sensitivity=seed_sensitivity,
            pilot_disagreement=disagreement,
            counterfactual_improvement=counterfactual_improvement,
            counterfactual_consistency=counterfactual_consistency,
            holdout_confirms_problem=holdout_confirms_problem,
            multiple_pods_confirm=multiple_pods_confirm,
            source_ids=tuple(source_ids),
            validation_levels=("structural_model_estimates",),
            notes=(
                "Derived from Structural Simulator event logs; not empirical playtest evidence.",
            ),
        )


def _path_hash(root: Path, relative: str) -> str:
    path = root / relative
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_integrated_extension_smoke(root: Path, output_path: Path) -> IntegratedExtensionSmokeReport:
    """Execute, rather than merely load, all ten extension stages.

    The smoke deliberately uses tiny deterministic Structural batches. It verifies integration
    contracts and provenance, not real-game performance or external-engine correctness.
    """
    root = root.resolve()
    run_dir = root / "data" / "runs" / "integrated_extension_smoke"
    run_dir.mkdir(parents=True, exist_ok=True)
    steps: list[IntegratedSmokeStep] = []

    def relative(path: Path) -> str:
        return str(path.resolve().relative_to(root))

    def add(step: int, name: str, paths: list[str], validation: str, summary: str) -> None:
        if not paths or any(not (root / path).is_file() for path in paths):
            raise DiagnosticError(f"integrated smoke step {step} lacks concrete source artifacts")
        steps.append(
            IntegratedSmokeStep(
                step=step,
                name=name,
                status="passed",
                source_paths=tuple(paths),
                source_hashes=tuple(_path_hash(root, p) for p in paths),
                validation_level=validation,
                result_summary=summary,
            )
        )

    # 1. Load and validate a versioned meta snapshot.
    from commander_lab.meta import MetaKnowledgeBase

    meta_kb = MetaKnowledgeBase(root)
    meta = meta_kb.load_snapshot()
    meta_path = root / "data/meta/manifests/latest.json"
    add(
        1,
        "load_meta_source",
        [relative(meta_path)],
        "source_fact",
        f"loaded and schema-validated {meta.manifest.snapshot_id}",
    )

    # 2. Compile current curated primer rules against the exact Korvold deck hash.
    from commander_lab.models import (
        FormatBand,
        HiddenInformationPolicy,
        MulliganContext,
        MulliganGamePlan,
        MulliganPolicyName,
        PilotConfig,
        PilotDecisionMode,
        PilotRule,
        PilotStrength,
        StructuralAbortLimits,
        StructuralMatchConfig,
    )
    from commander_lab.primer.compiler import PrimerToPilotCompiler

    rules_path = root / "data/primer_rules/rules/korvold_current_rules.json"
    rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = tuple(PilotRule.model_validate(row) for row in rules_payload["rules"])
    compiler = PrimerToPilotCompiler(root)
    policy = compiler.compile_policy(
        policy_id="phase12-10-smoke-policy",
        version="1.0.1",
        commander="Korvold, Fae-Cursed King",
        deck_hash="72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f",
        format_band=FormatBand.NORMAL_FOUR_PLAYER,
        base_pilot_name="KorvoldPilot",
        rules=rules,
        conflict_strategy="reject",
    )
    policy_path = run_dir / "compiled_policy.json"
    atomic_write_json(policy_path, policy.model_dump(mode="json"))
    add(
        2,
        "compile_primer_rule",
        [relative(rules_path), relative(policy_path)],
        "curated_project_rule",
        f"compiled {len(policy.rules)} validated rules",
    )

    # 3. Execute the same deck under multiple non-omniscient pilots and retain event logs.
    from commander_lab.agents.ensemble import PilotRegistry
    from commander_lab.engine.structural import StructuralSimulator, load_project_structural_decks

    registry = PilotRegistry(root)
    selected = ("KorvoldPilot", "KorvoldValuePilot", "KorvoldSacrificePilot")
    decks = load_project_structural_decks(
        root, include_synthetic_fixtures=True, include_current_opponents=True
    )
    simulator = StructuralSimulator(decks)
    log_paths: list[Path] = []
    placements: dict[str, int] = {}
    for index, pilot_name in enumerate(selected):
        profile = registry.profile(pilot_name)
        if (
            profile.information_policy.hidden_opponent_hands
            or profile.information_policy.exact_future_draws
        ):
            raise DiagnosticError("omniscient pilot profile rejected by integrated smoke")
        log_path = run_dir / f"pilot-{index}-{pilot_name}.jsonl"
        config = StructuralMatchConfig(
            match_id=f"integrated-pilot-{index}",
            seed=2026080600 + index,
            deck_ids=(
                "korvold/current",
                "synthetic/aggro",
                "synthetic/control",
                "synthetic/engine",
            ),
            pilot_configs=(
                PilotConfig(
                    pilot_name=pilot_name,
                    strength=PilotStrength.STRONG,
                    mode=PilotDecisionMode.DETERMINISTIC,
                    profile_version=profile.version,
                    parameter_hash=profile.parameter_hash,
                    source_rule_ids=profile.source_rule_ids,
                    allowed_deviation=profile.allowed_deviation,
                    supported_deck_hashes=profile.supported_deck_hashes,
                    information_policy=profile.information_policy,
                ),
                PilotConfig(),
                PilotConfig(),
                PilotConfig(),
            ),
            limits=StructuralAbortLimits(max_turns=12),
        )
        result = simulator.simulate(
            config, run_id="integrated-multi-pilot", event_log_path=log_path, capture_events=True
        )
        placements[pilot_name] = result.player_metrics["p1"].placement
        log_paths.append(log_path)
    add(
        3,
        "select_multiple_pilots",
        [relative(p) for p in log_paths],
        "structural_model_estimates",
        f"executed {len(selected)} legal-action pilot games; placements={placements}",
    )

    # 4. Execute archetype and package evaluation for the current deck.
    from commander_lab.packages import ArchetypePackageExtractor

    extractor = ArchetypePackageExtractor(root)
    package_output = extractor.packages_for_deck("korvold/current")
    package_path = run_dir / "package_analysis.json"
    atomic_write_json(package_path, package_output)
    add(
        4,
        "analyze_packages",
        [relative(root / "data/packages/package_registry.json"), relative(package_path)],
        "curated_project_package",
        (
            f"evaluated {len(package_output['evaluations'])} curated packages; "
            "machine candidates remain unconfirmed"
        ),
    )

    # 5. Execute a provenance graph trace, not just a JSON load.
    from commander_lab.provenance import ProvenanceStore

    provenance_store = ProvenanceStore(root)
    graph = provenance_store.load()
    provenance_store.validate(graph)
    trace_id = (
        graph.derived_data[-1].derived_id if graph.derived_data else graph.artifacts[-1].artifact_id
    )
    trace = provenance_store.trace(trace_id)
    trace_path = run_dir / "provenance_trace.json"
    atomic_write_json(trace_path, trace)
    add(
        5,
        "trace_provenance",
        [relative(provenance_store.path), relative(trace_path)],
        "provenance_verified",
        (
            f"traced {trace_id} through "
            f"{len(trace.get('lineage', trace.get('records', trace.get('trace', []))))} "
            "retained records"
        ),
    )

    # 6. Load the explicit synthetic uncertainty ensemble; no empirical game data is required.
    uncertainty_path = root / "data/opponent_ensembles/morcant-elves-ensemble-v1.json"
    uncertainty_profile = json.loads(uncertainty_path.read_text(encoding="utf-8"))
    add(
        6,
        "load_opponent_uncertainty_ensemble",
        [relative(uncertainty_path)],
        "structural_only",
        (
            f"loaded {len(uncertainty_profile.get('variants', []))} provenance-marked variants "
            "without empirical calibration"
        ),
    )

    # 7. Execute a current opponent-ensemble sensitivity calculation.
    from commander_lab.opponent_ensembles import OpponentEnsembleStore

    ensemble_store = OpponentEnsembleStore(root)
    ensemble_result = ensemble_store.run_matchups(
        decks["korvold/current"], "morcant-elves-ensemble-v1", seed=20260806
    )
    ensemble_path = run_dir / "ensemble_matchup.json"
    atomic_write_json(ensemble_path, ensemble_result.model_dump(mode="json"))
    add(
        7,
        "simulate_opponent_ensemble",
        [
            relative(root / "data/opponent_ensembles/morcant-elves-ensemble-v1.json"),
            relative(ensemble_path),
        ],
        "structural_model_estimates",
        (
            f"executed {len(ensemble_result.per_variant)} variants; "
            f"worst={ensemble_result.worst:.4f}, spread={ensemble_result.spread:.4f}"
        ),
    )

    # 8. Execute all eight Mulligan policies with full structural follow-ups and holdouts.
    from commander_lab.mulligan import MulliganLab

    mulligan_lab = MulliganLab(root)
    deck = mulligan_lab.deck("korvold/current")
    context = MulliganContext(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash,
        opponent_ensemble_id="morcant-elves-ensemble-v1",
        seat_position=2,
        starting_player=False,
        pod_size=4,
        pilot_profile_id="KorvoldPilot",
        pilot_version="1.0.0",
        game_plan=MulliganGamePlan.BALANCED,
        seed=20260806,
    )
    mulligan_result = mulligan_lab.run(
        context, tuple(MulliganPolicyName), samples=8, followup_samples=1
    )
    mulligan_path = run_dir / "mulligan_lab.json"
    atomic_write_json(mulligan_path, mulligan_result.model_dump(mode="json"))
    kinds = sorted({row.context_kind for row in mulligan_result.overfitting_validation})
    add(
        8,
        "apply_mulligan_policy",
        [relative(mulligan_path)],
        "structural_model_estimates",
        f"executed {len(mulligan_result.policies)} policies plus validation contexts {kinds}",
    )

    # 9. Execute a legal structural counterfactual from one of the newly produced replays.
    from commander_lab.counterfactual import CounterfactualReplayLab

    counter_lab = CounterfactualReplayLab(root)
    branch = None
    for log_path in log_paths:
        for candidate in counter_lab.find_branchpoints(relative(log_path), actor_id="p1"):
            alternatives = [
                a
                for a in candidate.available_actions
                if a.legal and a.action_id != candidate.chosen_action
            ]
            if alternatives:
                branch = candidate
                break
        if branch is not None:
            break
    if branch is None:
        raise DiagnosticError("executed replay did not expose a legal alternative branchpoint")
    alternative = max(
        (a for a in branch.available_actions if a.legal and a.action_id != branch.chosen_action),
        key=lambda row: float(row.utility or 0.0),
    )
    counter = counter_lab.run(
        branch,
        alternative_action=alternative.action_id,
        hidden_information_policy=HiddenInformationPolicy.MULTIPLE_FUTURE_SAMPLES,
        seed=20260806,
        future_samples=4,
    )
    counter_path = run_dir / "counterfactual.json"
    atomic_write_json(counter_path, counter.model_dump(mode="json"))
    add(
        9,
        "run_counterfactual_replay",
        [
            relative(
                Path(branch.source_path)
                if Path(branch.source_path).is_absolute()
                else root / branch.source_path
            ),
            relative(counter_path),
        ],
        "structural_counterfactual",
        (
            f"executed {len(counter.future_samples)} futures; {counter.conclusion}; "
            f"mean={counter.mean_improvement:.4f}"
        ),
    )

    # 10. Derive instrumentation from the actual logs and classify conservatively.
    collector = DiagnosticInstrumentationCollector(root)
    package_evaluation = next(iter(package_output["evaluations"]), None)
    dataset = collector.build(
        dataset_id="phase12-10-executed-smoke",
        deck_id="korvold/current",
        log_paths=[relative(p) for p in log_paths],
        package_id=package_evaluation.get("package_id") if package_evaluation else None,
        package_completeness=package_evaluation.get("package_completeness")
        if package_evaluation
        else None,
        package_minimum_met=package_evaluation.get("minimum_density_met")
        if package_evaluation
        else None,
        opponent_ensemble_count=len(ensemble_result.per_variant),
        opponent_sensitivity=min(1.0, ensemble_result.spread),
        counterfactual_improvement=counter.mean_improvement,
        counterfactual_consistency=max(
            counter.positive_future_fraction, 1.0 - counter.positive_future_fraction
        ),
    )
    dataset_path = run_dir / "diagnostic_dataset.json"
    atomic_write_json(dataset_path, dataset.model_dump(mode="json"))
    subject = next(
        (row.card_name for row in dataset.card_metrics if row.played or row.dead_in_hand),
        dataset.card_metrics[0].card_name,
    )
    diagnosis = DecisionDiagnosticEngine().classify(dataset, subject)
    diagnosis_path = run_dir / "diagnosis.json"
    atomic_write_json(diagnosis_path, diagnosis.model_dump(mode="json"))
    add(
        10,
        "diagnose_failure_cause",
        [relative(dataset_path), relative(diagnosis_path)],
        "model_diagnosis",
        (
            f"executed event-derived diagnosis for {subject}: {diagnosis.hypothesis.value}; "
            f"cut_gate={diagnosis.cut_release_gate}"
        ),
    )

    report = IntegratedExtensionSmokeReport(
        report_id="phase12-10-integrated-smoke-executed",
        steps=tuple(steps),
        passed_steps=len(steps),
        status="passed_with_limitations" if len(steps) == 10 else "failed",
    )
    atomic_write_json(output_path, report.model_dump(mode="json"))
    return report
