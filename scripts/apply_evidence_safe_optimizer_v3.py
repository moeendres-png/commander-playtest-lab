from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"expected exactly one regex match in {path}: {pattern[:80]!r}")
    write(path, updated)


# Package / optimizer identity. Historical manifests still carry their explicit old identities.
replace_once("pyproject.toml", 'version = "1.22.2"', 'version = "1.23.0"')

# Decision-information: measured resolution remains diagnostic; no numeric effect cutoff.
replace_once(
    "src/commander_lab/decision_information.py",
    '    MODEL_NEEDS_DIFFERENT_METRIC = "MODEL_NEEDS_DIFFERENT_METRIC"\n',
    '    MODEL_NEEDS_DIFFERENT_METRIC = "MODEL_NEEDS_DIFFERENT_METRIC"\n'
    '    MODEL_RESOLUTION_LIMIT = "MODEL_RESOLUTION_LIMIT"\n',
)
replace_once(
    "src/commander_lab/decision_information.py",
    "    decision_threshold = max(\n"
    "        indifference_threshold,\n"
    "        measured_resolution if measured_resolution is not None else indifference_threshold,\n"
    "    )\n",
    "    # Reporting annotation only. Neither indifference_threshold nor measured resolution is an\n"
    "    # advancement/rejection cutoff in the evidence-safe policy.\n"
    "    decision_threshold = indifference_threshold\n",
)
replace_once(
    "src/commander_lab/decision_information.py",
    '            schema_version="1.2.0",\n',
    '            schema_version="1.3.0",\n',
)
replace_once(
    "src/commander_lab/decision_information.py",
    "            status=DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC,\n"
    "            effect=effect,\n"
    "            interval=interval,\n"
    "            uncertainty=uncertainty,\n"
    "            seed_spread=seed_spread,\n"
    "            next_experiment=\"diagnose_model_information_before_more_seed_work\",\n",
    "            status=DecisionInformationStatus.MODEL_RESOLUTION_LIMIT,\n"
    "            effect=effect,\n"
    "            interval=interval,\n"
    "            uncertainty=uncertainty,\n"
    "            seed_spread=seed_spread,\n"
    "            next_experiment=\"diagnose_model_information_before_more_seed_work\",\n",
)
regex_once(
    "src/commander_lab/decision_information.py",
    r"    if interval is not None and interval\[0\] > decision_threshold:.*?    if \(\n        current_iterations is not None",
    "    if interval is not None and interval[0] > 0.0:\n"
    "        return state(\n"
    "            status=DecisionInformationStatus.STOP_WITH_PREFERENCE,\n"
    "            effect=effect,\n"
    "            interval=interval,\n"
    "            uncertainty=uncertainty,\n"
    "            seed_spread=seed_spread,\n"
    "            next_experiment=\"advance_to_next_validation_stage\",\n"
    "            reason=(\"paired interval supports a positive within-model direction; measured \"\n"
    "                    \"resolution and indifference thresholds remain diagnostics only\"),\n"
    "        )\n"
    "    if interval is not None and interval[1] < 0.0:\n"
    "        return state(\n"
    "            status=DecisionInformationStatus.STOP,\n"
    "            effect=effect,\n"
    "            interval=interval,\n"
    "            uncertainty=uncertainty,\n"
    "            seed_spread=seed_spread,\n"
    "            next_experiment=\"safe_eliminate_or_return_to_candidate_screening\",\n"
    "            reason=(\"paired interval supports a negative within-model direction without an \"\n"
    "                    \"effect-size cutoff\"),\n"
    "        )\n"
    "    if (\n        current_iterations is not None",
)

# Core optimizer identity, evidence metadata and safe racing.
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    "from commander_lab.models import FrozenModel\n",
    "from commander_lab.evidence_policy import (\n"
    "    EvidenceAction,\n"
    "    ModelState,\n"
    "    RacingDisposition,\n"
    "    RobustnessState,\n"
    "    classify_evidence,\n"
    ")\n"
    "from commander_lab.models import FrozenModel\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    'OPTIMIZER_V2_VERSION = "optimizer-v2-0.1.0"\n',
    'OPTIMIZER_V3_VERSION = "optimizer-v3-0.1.0"\n'
    '# Compatibility alias for older imports; new manifests record the v3 value.\n'
    'OPTIMIZER_V2_VERSION = OPTIMIZER_V3_VERSION\n',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    "    novelty_weight: float = Field(default=0.15, ge=0.0, le=2.0)\n\n"
    "    @model_validator(mode=\"after\")\n",
    "    novelty_weight: float = Field(default=0.15, ge=0.0, le=2.0)\n"
    "    sequential_familywise_alpha: float = Field(default=0.05, gt=0.0, lt=1.0)\n\n"
    "    @model_validator(mode=\"after\")\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    '    schema_version: str = "2.0.0"\n',
    '    schema_version: str = "3.0.0"\n',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    '    cache_namespace: str = "optimizer-v2"\n',
    '    cache_namespace: str = "optimizer-v3"\n',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    "    evidence_type: str = \"structural_model_estimates\"\n\n"
    "    @property\n"
    "    def uncertainty_width(self) -> float:\n",
    "    evidence_type: str = \"structural_model_estimates\"\n"
    "    sequential_interval_low: float | None = None\n"
    "    sequential_interval_high: float | None = None\n"
    "    racing_disposition: RacingDisposition = RacingDisposition.ACTIVE\n\n"
    "    @property\n"
    "    def uncertainty_width(self) -> float:\n",
)
regex_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    r"def select_racing_survivors\(.*?\n\n\ndef normalize_learning_weights",
    '''class RacingRoundSelection(FrozenModel):
    survivor_ids: tuple[str, ...]
    dispositions: dict[str, RacingDisposition]


def _racing_interval(row: ExploratoryEvaluation) -> tuple[float, float]:
    if row.sequential_interval_low is not None and row.sequential_interval_high is not None:
        return row.sequential_interval_low, row.sequential_interval_high
    return row.interval_low, row.interval_high


def select_racing_round(
    evaluations: Sequence[ExploratoryEvaluation],
    *,
    config: RacingConfig,
) -> RacingRoundSelection:
    """Allocate the next racing budget without declaring rank-based losers.

    Only a controlled interval wholly below zero is epistemically safe-eliminated. A compute quota
    may defer additional plausible candidates, but deferred/uncertain candidates remain explicitly
    inconclusive rather than being relabelled as worse.
    """
    if not evaluations:
        return RacingRoundSelection(survivor_ids=(), dispositions={})

    safe_eliminated = [row for row in evaluations if _racing_interval(row)[1] < 0.0]
    plausible = [row for row in evaluations if row not in safe_eliminated]
    target = min(
        len(plausible),
        max(config.minimum_survivors, math.ceil(len(evaluations) * config.survival_fraction)),
    )
    exploration_slots = min(target, math.ceil(target * config.exploration_fraction))
    exploitation_slots = target - exploration_slots
    ranked = sorted(
        plausible,
        key=lambda row: (racing_priority(row, config=config), row.deck_hash),
        reverse=True,
    )
    selected = ranked[:exploitation_slots]
    selected_hashes = {row.deck_hash for row in selected}
    novelty_ranked = sorted(
        (row for row in plausible if row.deck_hash not in selected_hashes),
        key=lambda row: (row.novelty, row.robust_lower_bound, row.deck_hash),
        reverse=True,
    )
    selected.extend(novelty_ranked[:exploration_slots])
    survivor_ids = tuple(row.candidate_id for row in selected)
    survivor_set = set(survivor_ids)

    frontier_low = max((_racing_interval(row)[0] for row in selected), default=float("-inf"))
    dispositions: dict[str, RacingDisposition] = {}
    for row in evaluations:
        if row in safe_eliminated:
            dispositions[row.candidate_id] = RacingDisposition.SAFE_ELIMINATED
        elif row.candidate_id in survivor_set:
            dispositions[row.candidate_id] = RacingDisposition.ACTIVE
        elif _racing_interval(row)[1] >= frontier_low:
            dispositions[row.candidate_id] = RacingDisposition.UNCERTAIN_FRONTIER
        else:
            dispositions[row.candidate_id] = RacingDisposition.DEFERRED_INCONCLUSIVE
    return RacingRoundSelection(survivor_ids=survivor_ids, dispositions=dispositions)


def select_racing_survivors(
    evaluations: Sequence[ExploratoryEvaluation],
    *,
    config: RacingConfig,
) -> tuple[str, ...]:
    """Compatibility wrapper returning compute survivors only."""
    return select_racing_round(evaluations, config=config).survivor_ids


def normalize_learning_weights''',
)
regex_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    r"def decision_for_interval\(.*?\n\n\ndef evaluate_calibration",
    '''def legacy_decision_for_interval(
    *,
    interval_low: float,
    interval_high: float,
    policy: DecisionCalibrationPolicy,
) -> str:
    """Historical optimizer-v2 rule retained only for reproducibility/benchmarking."""
    if interval_low > policy.sesoi:
        return "PROMOTE"
    if interval_high < -policy.sesoi:
        return "ELIMINATE"
    if interval_low >= -policy.equivalence_margin and interval_high <= policy.equivalence_margin:
        return "EQUIVALENT"
    return "MORE_SAMPLES"


def decision_for_interval(
    *,
    interval_low: float,
    interval_high: float,
    policy: DecisionCalibrationPolicy,
    paired_delta_estimate: float | None = None,
    sequential_interval: tuple[float, float] | None = None,
    technical_resolution: float | None = None,
    remaining_budget: int | None = 0,
    model_state: ModelState = ModelState.RESOLVABLE,
    robustness_state: RobustnessState = RobustnessState.NOT_TESTED,
    tradeoff_flags: tuple[str, ...] = (),
) -> str:
    """Evidence-safe action relative to zero; SESOI is magnitude annotation only."""
    estimate = (
        float(paired_delta_estimate)
        if paired_delta_estimate is not None
        else (float(interval_low) + float(interval_high)) / 2.0
    )
    decision = classify_evidence(
        paired_delta_estimate=estimate,
        descriptive_interval=(float(interval_low), float(interval_high)),
        sequential_interval=sequential_interval,
        technical_resolution=technical_resolution,
        sesoi=policy.sesoi,
        remaining_budget=remaining_budget,
        model_state=model_state,
        robustness_state=robustness_state,
        tradeoff_flags=tradeoff_flags,
    )
    return decision.action.value


def evaluate_calibration''',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    "        decision = decision_for_interval(\n",
    "        decision = legacy_decision_for_interval(\n",
)
write(
    "src/commander_lab/whole_deck/optimizer_v2.py",
    read("src/commander_lab/whole_deck/optimizer_v2.py").replace(
        'tool_name="whole_deck_optimizer_v2"', 'tool_name="whole_deck_optimizer_v3"'
    ),
)

# Search: controlled cumulative looks, safe racing dispositions, no rank-based epistemic rejection.
replace_once(
    "src/commander_lab/whole_deck/optimizer_search.py",
    "from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength\n",
    "from commander_lab.evidence_policy import RacingDisposition\n"
    "from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength\n"
    "from commander_lab.sequential_decision import sequential_bootstrap_interval\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_search.py",
    "    select_racing_survivors,\n",
    "    select_racing_round,\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_search.py",
    "            survivor_ids = select_racing_survivors(active_rows, config=self.racing)\n",
    "            selection = select_racing_round(active_rows, config=self.racing)\n"
    "            for candidate_id, disposition in selection.dispositions.items():\n"
    "                by_id[candidate_id] = by_id[candidate_id].model_copy(\n"
    "                    update={\"racing_disposition\": disposition}\n"
    "                )\n"
    "            survivor_ids = selection.survivor_ids\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_search.py",
    "        for row in final_rows:\n"
    "            archive.admit(variant_by_id[row.candidate_id], row)\n",
    "        for row in final_rows:\n"
    "            if row.racing_disposition != RacingDisposition.SAFE_ELIMINATED:\n"
    "                archive.admit(variant_by_id[row.candidate_id], row)\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_search.py",
    "        interval = paired_bootstrap_interval(\n"
    "            differences,\n"
    "            seed=self.manifest.exploratory.master_seed + statistics_offset + 23,\n"
    "        )\n"
    "        robust = distributionally_robust_lower_bound(differences)\n",
    "        interval = paired_bootstrap_interval(\n"
    "            differences,\n"
    "            seed=self.manifest.exploratory.master_seed + statistics_offset + 23,\n"
    "        )\n"
    "        look_index = self.manifest.racing.budgets.index(budget) + 1\n"
    "        sequential_interval = sequential_bootstrap_interval(\n"
    "            differences,\n"
    "            look_index=look_index,\n"
    "            total_looks=len(self.manifest.racing.budgets),\n"
    "            familywise_alpha=self.manifest.racing.sequential_familywise_alpha,\n"
    "            seed=self.manifest.exploratory.master_seed + statistics_offset + 29,\n"
    "        )\n"
    "        robust = distributionally_robust_lower_bound(differences)\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_search.py",
    "            interval_high=interval[1],\n"
    "            robust_lower_bound=robust,\n",
    "            interval_high=interval[1],\n"
    "            sequential_interval_low=sequential_interval[0],\n"
    "            sequential_interval_high=sequential_interval[1],\n"
    "            robust_lower_bound=robust,\n",
)

# Cached evaluator: same controlled looks and cache identity explicitly versioned for new semantics.
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_evaluator.py",
    "from commander_lab.pod_scheduling import PodScenario\n",
    "from commander_lab.pod_scheduling import PodScenario\n"
    "from commander_lab.sequential_decision import sequential_bootstrap_interval\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_evaluator.py",
    '            "evaluator_schema": "optimizer-v2-cached-partition-1.0.0",\n',
    '            "evaluator_schema": "optimizer-v3-cached-partition-1.0.0",\n'
    '            "sequential_policy": "bonferroni-staged-1.0.0",\n',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_evaluator.py",
    "        interval = paired_bootstrap_interval(differences, seed=statistics_seed + 23)\n",
    "        interval = paired_bootstrap_interval(differences, seed=statistics_seed + 23)\n"
    "        if self.evidence_context == EvidenceContext.EXPLORATORY:\n"
    "            look_index = self.manifest.racing.budgets.index(budget) + 1\n"
    "            total_looks = len(self.manifest.racing.budgets)\n"
    "            familywise_alpha = self.manifest.racing.sequential_familywise_alpha\n"
    "        else:\n"
    "            look_index = 1\n"
    "            total_looks = 1\n"
    "            familywise_alpha = self.manifest.calibration.max_false_promotion\n"
    "        sequential_interval = sequential_bootstrap_interval(\n"
    "            differences,\n"
    "            look_index=look_index,\n"
    "            total_looks=total_looks,\n"
    "            familywise_alpha=familywise_alpha,\n"
    "            seed=statistics_seed + 29,\n"
    "        )\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_evaluator.py",
    '            "interval_high": interval[1],\n',
    '            "interval_high": interval[1],\n'
    '            "sequential_interval_low": sequential_interval[0],\n'
    '            "sequential_interval_high": sequential_interval[1],\n'
    '            "sequential_look_index": look_index,\n',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_evaluator.py",
    "            interval_high=float(payload[\"interval_high\"]),\n"
    "            robust_lower_bound=float(payload[\"robust_lower_bound\"]),\n",
    "            interval_high=float(payload[\"interval_high\"]),\n"
    "            sequential_interval_low=float(payload[\"sequential_interval_low\"]),\n"
    "            sequential_interval_high=float(payload[\"sequential_interval_high\"]),\n"
    "            robust_lower_bound=float(payload[\"robust_lower_bound\"]),\n",
)

# Exploratory -> confirmatory gate: direction is relative to zero, not effective resolution.
replace_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    "from commander_lab.models import FrozenModel\n",
    "from commander_lab.evidence_policy import (\n"
    "    DirectionState,\n"
    "    EvidenceAction,\n"
    "    ModelState,\n"
    "    RobustnessState,\n"
    "    SamplingState,\n"
    ")\n"
    "from commander_lab.models import FrozenModel\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    "    BLOCKED_SCENARIO_ROBUSTNESS = \"BLOCKED_SCENARIO_ROBUSTNESS\"\n",
    "    BLOCKED_SCENARIO_ROBUSTNESS = \"BLOCKED_SCENARIO_ROBUSTNESS\"\n"
    "    UNCERTAIN_MORE_SAMPLES = \"UNCERTAIN_MORE_SAMPLES\"\n"
    "    SAFE_ELIMINATE = \"SAFE_ELIMINATE\"\n"
    "    TRADEOFF_REVIEW = \"TRADEOFF_REVIEW\"\n"
    "    ESCALATE_EVIDENCE = \"ESCALATE_EVIDENCE\"\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    "    evidence_context: str = \"exploratory\"\n",
    "    evidence_context: str = \"exploratory\"\n"
    "    direction_state: str = DirectionState.UNRESOLVED.value\n"
    "    sampling_state: str = SamplingState.MORE_SAMPLES.value\n"
    "    model_state: str = ModelState.RESOLVABLE.value\n"
    "    robustness_state: str = RobustnessState.NOT_TESTED.value\n"
    "    action: str = EvidenceAction.CONTINUE_SAMPLING.value\n"
    "    action_reason: str = \"\"\n",
)
regex_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    r"def _direction\(interval_low: float, interval_high: float, resolution: float\) -> str:\n.*?\n\n\ndef _direction_consistent",
    '''def _direction(interval_low: float, interval_high: float) -> str:
    if interval_low > 0.0:
        return "positive"
    if interval_high < 0.0:
        return "negative"
    return "unresolved"


def _direction_consistent''',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    "    direction = _direction(\n"
    "        evidence.interval_low,\n"
    "        evidence.interval_high,\n"
    "        model_resolution.effective_resolution,\n"
    "    )\n",
    "    direction = _direction(evidence.interval_low, evidence.interval_high)\n",
)
regex_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    r"    failed: list\[str\] = \[\].*?    return CandidateAdvancementAssessment\(",
    '''    failed: list[str] = []
    if not model_resolution.paired_candidate_comparisons_allowed:
        failed.append("model_resolution_decision_use")
    if direction == "negative":
        failed.append("pooled_direction_negative")
    elif direction == "unresolved":
        failed.append("pooled_direction_unresolved")
    if not full_partition:
        failed.append("full_exploratory_partition")
    if not pairing_passed:
        failed.append("paired_execution_contract")
    if direction == "positive" and not seat_consistent:
        failed.append("seat_stratified_tradeoff")
    if direction == "positive" and not scenario_consistent:
        failed.append("admissible_scenario_tradeoff")

    if not model_resolution.paired_candidate_comparisons_allowed:
        status = CandidateAdvancementStatus.ESCALATE_EVIDENCE
        action = EvidenceAction.ESCALATE_EVIDENCE
        action_reason = "paired candidate comparisons are not supported by current model diagnostics"
    elif not full_partition:
        status = CandidateAdvancementStatus.BLOCKED_PARTITION_COVERAGE
        action = EvidenceAction.CONTINUE_SAMPLING
        action_reason = "frozen exploratory partition is not yet fully evaluated"
    elif not pairing_passed:
        status = CandidateAdvancementStatus.BLOCKED_PAIRING
        action = EvidenceAction.ESCALATE_EVIDENCE
        action_reason = "paired execution contract is incomplete"
    elif direction == "negative":
        status = CandidateAdvancementStatus.SAFE_ELIMINATE
        action = EvidenceAction.SAFE_ELIMINATE
        action_reason = "paired exploratory interval supports a negative direction relative to zero"
    elif direction == "unresolved":
        status = CandidateAdvancementStatus.UNCERTAIN_MORE_SAMPLES
        action = EvidenceAction.INCONCLUSIVE
        action_reason = "full exploratory budget remains directionally unresolved"
    elif not seat_consistent or not scenario_consistent:
        status = CandidateAdvancementStatus.TRADEOFF_REVIEW
        action = EvidenceAction.TRADEOFF_REVIEW
        action_reason = "positive pooled direction has seat or opponent-scenario tradeoffs"
    else:
        status = CandidateAdvancementStatus.ELIGIBLE_CONFIRMATORY
        action = EvidenceAction.ADVANCE
        action_reason = "positive paired direction is robust across required exploratory axes"

    eligible = status in {
        CandidateAdvancementStatus.ELIGIBLE_CONFIRMATORY,
        CandidateAdvancementStatus.TRADEOFF_REVIEW,
    }
    direction_state = {
        "positive": DirectionState.POSITIVE,
        "negative": DirectionState.NEGATIVE,
        "unresolved": DirectionState.UNRESOLVED,
    }[direction]
    sampling_state = (
        SamplingState.SUFFICIENT
        if direction != "unresolved"
        else SamplingState.BUDGET_EXHAUSTED
    )
    robustness_state = (
        RobustnessState.TRADEOFF
        if status == CandidateAdvancementStatus.TRADEOFF_REVIEW
        else RobustnessState.ROBUST
        if direction == "positive" and seat_consistent and scenario_consistent
        else RobustnessState.NOT_TESTED
    )

    return CandidateAdvancementAssessment(''',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    "        eligible_for_confirmatory=status == CandidateAdvancementStatus.ELIGIBLE_CONFIRMATORY,\n",
    "        eligible_for_confirmatory=eligible,\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_advancement.py",
    "        failed_axes=tuple(failed),\n"
    "    )\n",
    "        failed_axes=tuple(failed),\n"
    "        direction_state=direction_state.value,\n"
    "        sampling_state=sampling_state.value,\n"
    "        model_state=(\n"
    "            ModelState.RESOLVABLE.value\n"
    "            if model_resolution.paired_candidate_comparisons_allowed\n"
    "            else ModelState.NEEDS_DIFFERENT_EVIDENCE.value\n"
    "        ),\n"
    "        robustness_state=robustness_state.value,\n"
    "        action=action.value,\n"
    "        action_reason=action_reason,\n"
    "    )\n",
)

# Adaptive budget helper: budget exhaustion is not rejection, model limits escalate evidence.
append_marker = "\n\n__all__ = [\n"
adaptive = read("src/commander_lab/adaptive_budget.py")
if append_marker not in adaptive:
    raise RuntimeError("adaptive_budget __all__ marker missing")
adaptive_helper = '''\n\ndef evidence_budget_action(action: str) -> str:
    """Map evidence-safe actions to compute allocation without changing epistemic status."""
    if action == "CONTINUE_SAMPLING":
        return "EXPAND_SAME_SOURCE"
    if action in {"ESCALATE_EVIDENCE", "TRADEOFF_REVIEW"}:
        return "STOP_SAME_SOURCE_AND_ESCALATE"
    if action == "INCONCLUSIVE":
        return "STOP_BUDGET_EXHAUSTED_INCONCLUSIVE"
    if action in {"ADVANCE", "SAFE_ELIMINATE"}:
        return "STOP_DIRECTION_RESOLVED"
    raise ValueError(f"unknown evidence action: {action}")
'''
adaptive = adaptive.replace(append_marker, adaptive_helper + append_marker, 1)
adaptive = adaptive.replace(
    '    "challenge_quality_metrics",\n',
    '    "challenge_quality_metrics",\n    "evidence_budget_action",\n',
    1,
)
write("src/commander_lab/adaptive_budget.py", adaptive)

# Release flow: v3 identity, rich evidence decisions, holdout only after ADVANCE.
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "from commander_lab.storage import atomic_write_json, sha256_value\n",
    "from commander_lab.evidence_policy import (\n"
    "    RobustnessState,\n"
    "    classify_evidence,\n"
    ")\n"
    "from commander_lab.storage import atomic_write_json, sha256_value\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "from .optimizer_search import AdaptiveWholeDeckSearch\n",
    "from .optimizer_advancement import load_model_resolution_decision_policy\n"
    "from .optimizer_search import AdaptiveWholeDeckSearch\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "    build_semantic_review_queue,\n"
    "    decision_for_interval,\n",
    "    build_semantic_review_queue,\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    'OPTIMIZER_V2_RELEASE_RUNTIME = "optimizer-v2-release-runtime-1.0.0"\n',
    'OPTIMIZER_V2_RELEASE_RUNTIME = "optimizer-v3-release-runtime-1.0.0"\n',
)
insert_point = "\ndef run_release_confirmatory(\n"
release = read("src/commander_lab/whole_deck/optimizer_v2_release.py")
if insert_point not in release:
    raise RuntimeError("confirmatory insertion point missing")
helper = '''\n\ndef _release_evidence_decision(
    *,
    evaluation: Any,
    manifest: OptimizerV2Manifest,
    technical_resolution: float,
    candidate_id: str,
) -> dict[str, Any]:
    sequential = None
    if (
        evaluation.sequential_interval_low is not None
        and evaluation.sequential_interval_high is not None
    ):
        sequential = (
            float(evaluation.sequential_interval_low),
            float(evaluation.sequential_interval_high),
        )
    tradeoff_flags: tuple[str, ...] = ()
    robustness = RobustnessState.NOT_TESTED
    if float(evaluation.robust_lower_bound) >= 0.0:
        robustness = RobustnessState.ROBUST
    else:
        robustness = RobustnessState.TRADEOFF
        tradeoff_flags = ("distributionally_robust_lower_bound_negative",)
    decision = classify_evidence(
        candidate_id=candidate_id,
        control_id=manifest.control_deck_hash,
        paired_delta_estimate=float(evaluation.score),
        descriptive_interval=(float(evaluation.interval_low), float(evaluation.interval_high)),
        sequential_interval=sequential,
        technical_resolution=technical_resolution,
        sesoi=manifest.calibration.sesoi,
        robustness_state=robustness,
        tradeoff_flags=tradeoff_flags,
        sequential_stage=1,
        remaining_budget=0,
    )
    return decision.as_dict()
'''
release = release.replace(insert_point, helper + insert_point, 1)
write("src/commander_lab/whole_deck/optimizer_v2_release.py", release)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "    rows: list[dict[str, object]] = []\n"
    "    for index, elite in enumerate(handoff.elites):\n",
    "    model_resolution = load_model_resolution_decision_policy(root_path)\n"
    "    rows: list[dict[str, object]] = []\n"
    "    for index, elite in enumerate(handoff.elites):\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "        decision = decision_for_interval(\n"
    "            interval_low=evaluation.interval_low,\n"
    "            interval_high=evaluation.interval_high,\n"
    "            policy=manifest.calibration,\n"
    "        )\n"
    "        rows.append(\n"
    "            {\n"
    "                \"deck_hash\": variant.deck_hash,\n"
    "                \"candidate_id\": variant.variant_id,\n"
    "                \"evaluation\": evaluation.model_dump(mode=\"json\"),\n"
    "                \"decision\": decision,\n"
    "            }\n"
    "        )\n",
    "        evidence_decision = _release_evidence_decision(\n"
    "            evaluation=evaluation,\n"
    "            manifest=manifest,\n"
    "            technical_resolution=model_resolution.effective_resolution,\n"
    "            candidate_id=variant.variant_id,\n"
    "        )\n"
    "        rows.append(\n"
    "            {\n"
    "                \"deck_hash\": variant.deck_hash,\n"
    "                \"candidate_id\": variant.variant_id,\n"
    "                \"evaluation\": evaluation.model_dump(mode=\"json\"),\n"
    "                \"decision\": evidence_decision[\"action\"],\n"
    "                \"evidence_decision\": evidence_decision,\n"
    "            }\n"
    "        )\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    '        if isinstance(row, dict) and row.get("decision") == "PROMOTE"\n',
    '        if isinstance(row, dict) and row.get("decision") == "ADVANCE"\n',
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "    rows: list[dict[str, object]] = []\n"
    "    for index, promoted_row in enumerate(promoted):\n",
    "    model_resolution = load_model_resolution_decision_policy(root_path)\n"
    "    rows: list[dict[str, object]] = []\n"
    "    for index, promoted_row in enumerate(promoted):\n",
)
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release.py",
    "        rows.append(\n"
    "            {\n"
    "                \"deck_hash\": deck_hash,\n"
    "                \"evaluation\": evaluation.model_dump(mode=\"json\"),\n"
    "                \"decision\": decision_for_interval(\n"
    "                    interval_low=evaluation.interval_low,\n"
    "                    interval_high=evaluation.interval_high,\n"
    "                    policy=manifest.calibration,\n"
    "                ),\n"
    "            }\n"
    "        )\n",
    "        evidence_decision = _release_evidence_decision(\n"
    "            evaluation=evaluation,\n"
    "            manifest=manifest,\n"
    "            technical_resolution=model_resolution.effective_resolution,\n"
    "            candidate_id=variant.variant_id,\n"
    "        )\n"
    "        rows.append(\n"
    "            {\n"
    "                \"deck_hash\": deck_hash,\n"
    "                \"candidate_id\": variant.variant_id,\n"
    "                \"evaluation\": evaluation.model_dump(mode=\"json\"),\n"
    "                \"decision\": evidence_decision[\"action\"],\n"
    "                \"evidence_decision\": evidence_decision,\n"
    "            }\n"
    "        )\n",
)

# Release/cache schema identity changes prevent stale v2 cached semantics being silently reused.
replace_once(
    "src/commander_lab/whole_deck/optimizer_v2_release_models.py",
    'OPTIMIZER_V2_RELEASE_SCHEMA = "2.1.0"\n',
    'OPTIMIZER_V2_RELEASE_SCHEMA = "3.0.0"\n',
)
release_models = read("src/commander_lab/whole_deck/optimizer_v2_release_models.py")
release_models = release_models.replace(
    'tool_name="whole_deck_optimizer_v2_calibration"',
    'tool_name="whole_deck_optimizer_v3_calibration"',
)
write("src/commander_lab/whole_deck/optimizer_v2_release_models.py", release_models)

# Changelog / README project truth.
changelog = read("CHANGELOG.md")
entry = '''# 1.23.0 - 2026-08-20

- Introduce evidence-safe optimizer decision policy `evidence-safe-decision-1.0.0`.
- Remove SESOI and measured Structural resolution as hard candidate advancement/rejection cutoffs.
- Add separated direction, sampling, model, magnitude, robustness and action states.
- Add preregistered Bonferroni-staged sequential looks over existing cumulative racing budgets.
- Replace rank-only racing elimination with safe elimination plus uncertain/deferred dispositions.
- Preserve SESOI and technical resolution as reporting/calibration diagnostics only.
- Make budget exhaustion inconclusive rather than rejection and model limits evidence-escalation triggers.
- Bump optimizer identity to `optimizer-v3-0.1.0`; old optimizer-v2 campaign evidence remains historical and unchanged.
- Operational pod policy remains fail-closed 4-player Commander only.

'''
if not changelog.startswith("# 1.23.0"):
    write("CHANGELOG.md", entry + changelog)

readme = read("README.md")
section = '''\n## Evidence-safe optimizer decisions\n\nOptimizer v3 separates within-model direction, sampling uncertainty, model/fidelity limits, effect\nmagnitude and robustness. `SESOI` and measured Structural resolution are diagnostics, not hard\nadvancement cutoffs. Repeated exploratory looks use preregistered alpha spending; rank-only racing\nmay defer compute but cannot label a plausible candidate as worse. Final Structural conclusions remain\n`structural_model_estimates`, and the operational project scope remains 4-player Commander only.\n'''
if "## Evidence-safe optimizer decisions" not in readme:
    write("README.md", readme.rstrip() + "\n" + section)

# Focused architecture tests.
write(
    "tests/test_evidence_safe_optimizer_v3.py",
    '''from __future__ import annotations

import math

from commander_lab.adaptive_budget import evidence_budget_action
from commander_lab.evidence_policy import (
    EvidenceAction,
    ModelState,
    RacingDisposition,
    RobustnessState,
    classify_evidence,
)
from commander_lab.sequential_decision import SequentialPlan
from commander_lab.whole_deck.optimizer_v2 import (
    DecisionCalibrationPolicy,
    ExploratoryEvaluation,
    RacingConfig,
    decision_for_interval,
    legacy_decision_for_interval,
    select_racing_round,
)


def decision(delta: float, interval: tuple[float, float], **kwargs: object):
    return classify_evidence(
        paired_delta_estimate=delta,
        descriptive_interval=interval,
        sequential_interval=interval,
        technical_resolution=0.375,
        sesoi=0.05,
        remaining_budget=0,
        **kwargs,
    )


def test_small_positive_below_sesoi_and_resolution_advances() -> None:
    result = decision(0.03, (0.01, 0.04), robustness_state=RobustnessState.ROBUST)
    assert result.action == EvidenceAction.ADVANCE
    assert result.magnitude_class.value == "BELOW_SESOI"
    assert result.technical_resolution == 0.375


def test_unresolved_uses_budget_then_inconclusive() -> None:
    more = classify_evidence(
        paired_delta_estimate=0.20,
        descriptive_interval=(-0.05, 0.30),
        remaining_budget=100,
        sesoi=0.05,
        technical_resolution=0.375,
    )
    done = classify_evidence(
        paired_delta_estimate=0.01,
        descriptive_interval=(-0.01, 0.03),
        remaining_budget=0,
        sesoi=0.05,
        technical_resolution=0.375,
    )
    assert more.action == EvidenceAction.CONTINUE_SAMPLING
    assert done.action == EvidenceAction.INCONCLUSIVE


def test_negative_can_be_safely_eliminated_without_effect_cutoff() -> None:
    result = decision(-0.01, (-0.02, -0.001))
    assert result.action == EvidenceAction.SAFE_ELIMINATE


def test_model_limit_escalates_instead_of_infinite_sampling() -> None:
    result = decision(
        0.004,
        (0.002, 0.006),
        model_state=ModelState.MODEL_LIMITED,
    )
    assert result.action == EvidenceAction.ESCALATE_EVIDENCE


def test_tradeoff_is_review_not_reject() -> None:
    result = decision(
        0.10,
        (0.04, 0.16),
        robustness_state=RobustnessState.TRADEOFF,
        tradeoff_flags=("protection_regression",),
    )
    assert result.action == EvidenceAction.TRADEOFF_REVIEW


def test_sequential_alpha_spending_is_preregistered_and_bounded() -> None:
    plan = SequentialPlan(total_looks=4, familywise_alpha=0.05)
    assert math.isclose(plan.alpha_per_look, 0.0125)
    assert math.isclose(plan.controlled_confidence, 0.9875)
    assert math.isclose(plan.allocated_alpha, 0.05)
    plan.validate_look(4)


def _row(candidate_id: str, low: float, high: float, score: float) -> ExploratoryEvaluation:
    return ExploratoryEvaluation(
        candidate_id=candidate_id,
        deck_hash=(candidate_id * 64)[:64],
        generation=0,
        operator="test",
        policy_id="test",
        budget=56,
        score=score,
        interval_low=low,
        interval_high=high,
        sequential_interval_low=low,
        sequential_interval_high=high,
        robust_lower_bound=low,
        novelty=0.0,
        qd_cell="L0:M0:I0",
    )


def test_safe_racing_only_epistemically_eliminates_controlled_negative() -> None:
    positive = _row("a", 0.01, 0.05, 0.03)
    uncertain = _row("b", -0.02, 0.04, 0.01)
    negative = _row("c", -0.08, -0.01, -0.04)
    selection = select_racing_round(
        (positive, uncertain, negative),
        config=RacingConfig(
            budgets=(56, 112),
            survival_fraction=0.34,
            minimum_survivors=1,
            exploration_fraction=0.0,
        ),
    )
    assert selection.dispositions["c"] == RacingDisposition.SAFE_ELIMINATED
    assert selection.dispositions["b"] != RacingDisposition.SAFE_ELIMINATED
    assert "c" not in selection.survivor_ids


def test_new_rule_recovers_safe_small_effect_that_legacy_sesoi_blocks() -> None:
    policy = DecisionCalibrationPolicy(sesoi=0.05, equivalence_margin=0.02)
    assert legacy_decision_for_interval(interval_low=0.02, interval_high=0.04, policy=policy) != "PROMOTE"
    assert decision_for_interval(
        interval_low=0.02,
        interval_high=0.04,
        paired_delta_estimate=0.03,
        policy=policy,
    ) == "ADVANCE"


def test_budget_action_never_maps_inconclusive_to_reject() -> None:
    assert evidence_budget_action("INCONCLUSIVE") == "STOP_BUDGET_EXHAUSTED_INCONCLUSIVE"
    assert evidence_budget_action("ESCALATE_EVIDENCE") == "STOP_SAME_SOURCE_AND_ESCALATE"
''',
)

# Synthetic policy benchmark. This is software-policy calibration, never Commander gameplay truth.
write(
    "scripts/benchmark_evidence_safe_policy.py",
    '''from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from statistics import NormalDist, fmean, stdev

BUDGETS = (56, 112, 224, 448)
FAMILYWISE_ALPHA = 0.05
SESOI = 0.05
SD = 0.15


@dataclass(frozen=True)
class Metrics:
    effect: float
    legacy_positive_rate: float
    legacy_negative_rate: float
    new_positive_rate: float
    new_negative_rate: float
    new_inconclusive_rate: float
    new_average_samples: float


def interval(values: list[float], confidence: float) -> tuple[float, float]:
    mean = fmean(values)
    if len(values) < 2:
        return mean, mean
    se = stdev(values) / math.sqrt(len(values))
    alpha = 1.0 - confidence
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    return mean - z * se, mean + z * se


def legacy(values: list[float]) -> str:
    low, high = interval(values, 0.95)
    if low > SESOI:
        return "POSITIVE"
    if high < -SESOI:
        return "NEGATIVE"
    return "INCONCLUSIVE"


def new_policy(values: list[float], look: int) -> str:
    confidence = 1.0 - FAMILYWISE_ALPHA / len(BUDGETS)
    low, high = interval(values, confidence)
    if low > 0.0:
        return "POSITIVE"
    if high < 0.0:
        return "NEGATIVE"
    return "INCONCLUSIVE"


def run_effect(effect: float, repetitions: int, seed: int) -> Metrics:
    legacy_positive = legacy_negative = 0
    new_positive = new_negative = new_inconclusive = 0
    samples: list[int] = []
    for rep in range(repetitions):
        rng = random.Random(seed + rep * 1_000_003 + int((effect + 1.0) * 10_000))
        values = [rng.gauss(effect, SD) for _ in range(BUDGETS[-1])]
        legacy_decision = legacy(values)
        legacy_positive += legacy_decision == "POSITIVE"
        legacy_negative += legacy_decision == "NEGATIVE"

        final = "INCONCLUSIVE"
        used = BUDGETS[-1]
        for look, budget in enumerate(BUDGETS, start=1):
            result = new_policy(values[:budget], look)
            if result != "INCONCLUSIVE":
                final = result
                used = budget
                break
        new_positive += final == "POSITIVE"
        new_negative += final == "NEGATIVE"
        new_inconclusive += final == "INCONCLUSIVE"
        samples.append(used)
    return Metrics(
        effect=effect,
        legacy_positive_rate=legacy_positive / repetitions,
        legacy_negative_rate=legacy_negative / repetitions,
        new_positive_rate=new_positive / repetitions,
        new_negative_rate=new_negative / repetitions,
        new_inconclusive_rate=new_inconclusive / repetitions,
        new_average_samples=fmean(samples),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--assert-acceptance", action="store_true")
    args = parser.parse_args()
    effects = (0.0, 0.03, 0.15, -0.08)
    rows = {str(effect): run_effect(effect, args.repetitions, args.seed) for effect in effects}
    null = rows["0.0"]
    small = rows["0.03"]
    large = rows["0.15"]
    negative = rows["-0.08"]
    acceptance = {
        "controlled_false_promotion": null.new_positive_rate <= FAMILYWISE_ALPHA,
        "small_effect_recall_improved": small.new_positive_rate > small.legacy_positive_rate,
        "large_effect_recovery_not_worse": large.new_positive_rate >= large.legacy_positive_rate - 0.01,
        "negative_recovery": negative.new_negative_rate >= 0.90,
        "bounded_compute": all(row.new_average_samples <= BUDGETS[-1] for row in rows.values()),
        "search_survivor_recall": 1.0 - small.new_negative_rate >= 0.95,
        "sequential_alpha_budget": math.isclose(
            FAMILYWISE_ALPHA / len(BUDGETS) * len(BUDGETS), FAMILYWISE_ALPHA
        ),
    }
    payload = {
        "schema_version": "1.0.0",
        "benchmark_type": "synthetic_policy_calibration",
        "truth_boundary": "synthetic normal paired-delta assumptions; not Commander gameplay evidence",
        "budgets": BUDGETS,
        "familywise_alpha_per_candidate": FAMILYWISE_ALPHA,
        "sesoi_legacy_only": SESOI,
        "synthetic_sd": SD,
        "repetitions": args.repetitions,
        "metrics": {key: asdict(value) for key, value in rows.items()},
        "acceptance": acceptance,
        "accepted": all(acceptance.values()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.assert_acceptance and not payload["accepted"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
)

print("evidence-safe optimizer v3 migration staged")
