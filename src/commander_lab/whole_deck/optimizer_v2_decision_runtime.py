from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import NormalDist, fmean
from typing import Any

from pydantic import Field, model_validator

from commander_lab.decision_statistics import (
    distributionally_robust_lower_bound,
    monte_carlo_standard_error,
    paired_bootstrap_interval,
)
from commander_lab.models import (
    CardRole,
    FrozenModel,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import atomic_write_json, sha256_value

from .campaign import run_balanced_paired_campaign
from .lab import WholeDeckDesignLab
from .optimizer_runtime import DEFAULT_POLICIES
from .optimizer_v2 import EvidenceContext
from .optimizer_v2_evaluator import CachedPartitionEvaluator, _number
from .optimizer_v2_release import (
    _load_handoff,
    _write_audit,
    build_release_manifest_from_project,
    run_release_search,
    verify_release_preflight,
)
from .optimizer_v2_release_models import FrontierHandoff, OptimizerV2Manifest
from .orchestrator import WholeDeckCampaignOrchestrator
from .search import current_control_mainboard
from .search_context import SEMANTIC_UNKNOWN
from .search_models import WholeDeckVariant

DECISION_RUNTIME_VERSION = "optimizer-v2-decision-runtime-1E-2F-1.0.0"
DECISION_CONTRACT_PATH = Path("data/decision/DECISION_CONTRACT_CURRENT.json")
PRECISION_POLICY_PATH = Path("docs/decision_quality/MODEL_PRECISION_POLICY_CURRENT.md")
SEMANTIC_PROJECTION_PATH = Path("data/cards/rogshai_semantic_projection_current.zlib.b64")
CKB_MANIFEST_PATH = Path("data/cards/FULL_PHYSICAL_CARD_KNOWLEDGE_MANIFEST_CURRENT.json")
CONFIRMATORY_LOOKS = (128, 256, 512, 1024, 2048)
SHORTLIST_LIMIT = 8
FAMILY_ALPHA = 0.05
SESOI = 0.05
MCSE_MAX = 0.025
ROBUSTNESS_MARGIN = -0.05
SEED_BLOCK_COUNT = 4


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CriticalDiagnosticsPartition(FrozenModel):
    partition_id: str = "critical_diagnostics"
    master_seed: int = Field(ge=0)
    scenario_ids: tuple[str, ...]
    scenario_seeds: tuple[int, ...]
    identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(
        cls,
        orchestrator: WholeDeckCampaignOrchestrator,
        *,
        master_seed: int,
        games: int,
    ) -> CriticalDiagnosticsPartition:
        scenarios = tuple(orchestrator.scheduler.schedule(games, seed=master_seed))
        payload = {
            "partition_id": "critical_diagnostics",
            "master_seed": master_seed,
            "scenario_ids": tuple(row.scenario_id for row in scenarios),
            "scenario_seeds": tuple(row.seed for row in scenarios),
        }
        return cls(
            master_seed=master_seed,
            scenario_ids=tuple(row.scenario_id for row in scenarios),
            scenario_seeds=tuple(row.seed for row in scenarios),
            identity=sha256_value(payload),
        )


class DecisionOptimizerV2Manifest(OptimizerV2Manifest):
    schema_version: str = "2.2.0"
    decision_runtime_version: str = DECISION_RUNTIME_VERSION
    operational_pod_size: int = 4
    rogshai_candidate_count: int = Field(ge=1)
    decision_contract_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    precision_policy_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_projection_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    ckb_manifest_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    critical_diagnostics: CriticalDiagnosticsPartition

    @model_validator(mode="after")
    def validate_decision_contract(self) -> DecisionOptimizerV2Manifest:
        if self.operational_pod_size != 4:
            raise ValueError("current decision runtime is 4-player only")
        partitions = (
            self.exploratory,
            self.calibration_partition,
            self.confirmatory,
            self.sealed_holdout,
        )
        seed_sets = [set(row.scenario_seeds) for row in partitions]
        scenario_sets = [set(row.scenario_ids) for row in partitions]
        diag_seeds = set(self.critical_diagnostics.scenario_seeds)
        diag_scenarios = set(self.critical_diagnostics.scenario_ids)
        if any(diag_seeds & values for values in seed_sets):
            raise ValueError("critical diagnostics seed leakage into another evidence partition")
        if any(diag_scenarios & values for values in scenario_sets):
            raise ValueError(
                "critical diagnostics scenario leakage into another evidence partition"
            )
        if len(self.confirmatory.scenario_ids) < CONFIRMATORY_LOOKS[-1]:
            raise ValueError("confirmatory partition is below frozen 2F ceiling")
        if len(self.sealed_holdout.scenario_ids) != 2048:
            raise ValueError("sealed holdout must contain exactly 2048 paired 4P scenarios")
        return self


def build_decision_manifest_from_project(
    root: str | Path,
    *,
    run_id: str,
    search_seed: int,
    exploratory_games: int = 256,
    calibration_games: int = 128,
    confirmatory_games: int = 2048,
    diagnostics_games: int = 512,
    holdout_games: int = 2048,
    policies: Sequence[str] = DEFAULT_POLICIES,
) -> DecisionOptimizerV2Manifest:
    if confirmatory_games != 2048 or holdout_games != 2048:
        raise ValueError(
            "current frozen 2F/holdout policy requires 2048 confirmatory and holdout scenarios"
        )
    root_path = Path(root).resolve()
    required = (
        DECISION_CONTRACT_PATH,
        PRECISION_POLICY_PATH,
        SEMANTIC_PROJECTION_PATH,
        CKB_MANIFEST_PATH,
    )
    missing = [str(path) for path in required if not (root_path / path).is_file()]
    if missing:
        raise RuntimeError(f"current decision knowledge files are missing: {', '.join(missing)}")
    base = build_release_manifest_from_project(
        root_path,
        run_id=run_id,
        search_seed=search_seed,
        exploratory_games=exploratory_games,
        calibration_games=calibration_games,
        confirmatory_games=confirmatory_games,
        holdout_games=holdout_games,
        policies=policies,
    )
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    diagnostics = CriticalDiagnosticsPartition.create(
        orchestrator,
        master_seed=search_seed ^ 0x71D9_2BF3,
        games=diagnostics_games,
    )
    payload = base.model_dump(mode="json")
    payload.update(
        {
            "schema_version": "2.2.0",
            "decision_runtime_version": DECISION_RUNTIME_VERSION,
            "operational_pod_size": 4,
            "rogshai_candidate_count": len(lab.context.cards),
            "decision_contract_identity": _file_sha256(root_path / DECISION_CONTRACT_PATH),
            "precision_policy_identity": _file_sha256(root_path / PRECISION_POLICY_PATH),
            "semantic_projection_identity": _file_sha256(root_path / SEMANTIC_PROJECTION_PATH),
            "ckb_manifest_identity": _file_sha256(root_path / CKB_MANIFEST_PATH),
            "critical_diagnostics": diagnostics.model_dump(mode="json"),
        }
    )
    return DecisionOptimizerV2Manifest.model_validate(payload)


def load_decision_manifest(path: str | Path) -> DecisionOptimizerV2Manifest:
    return DecisionOptimizerV2Manifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _verify_partition_4p(
    orchestrator: WholeDeckCampaignOrchestrator,
    *,
    master_seed: int,
    expected_ids: Sequence[str],
    expected_seeds: Sequence[int],
) -> bool:
    rows = tuple(orchestrator.scheduler.schedule(len(expected_ids), seed=master_seed))
    return (
        tuple(row.scenario_id for row in rows) == tuple(expected_ids)
        and tuple(row.seed for row in rows) == tuple(expected_seeds)
        and all(len(row.opponent_deck_ids) == 3 for row in rows)
    )


def verify_decision_preflight(
    root: str | Path, manifest: DecisionOptimizerV2Manifest
) -> dict[str, object]:
    root_path = Path(root).resolve()
    base = verify_release_preflight(root_path, manifest)
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    unknown = tuple(
        sorted(
            name
            for name, card in lab.context.cards.items()
            if card.effective_semantic_state == SEMANTIC_UNKNOWN
        )
    )
    contract = json.loads((root_path / DECISION_CONTRACT_PATH).read_text(encoding="utf-8"))
    checks = {
        "decision_contract_content_addressed": _file_sha256(root_path / DECISION_CONTRACT_PATH)
        == manifest.decision_contract_identity,
        "precision_policy_content_addressed": _file_sha256(root_path / PRECISION_POLICY_PATH)
        == manifest.precision_policy_identity,
        "semantic_projection_content_addressed": _file_sha256(root_path / SEMANTIC_PROJECTION_PATH)
        == manifest.semantic_projection_identity,
        "ckb_manifest_content_addressed": _file_sha256(root_path / CKB_MANIFEST_PATH)
        == manifest.ckb_manifest_identity,
        "candidate_count": len(lab.context.cards) == manifest.rogshai_candidate_count,
        "semantic_unknown_zero": not unknown,
        "contract_1e": contract.get("contract_id") == "rogshai-hierarchical-pareto-1E-v1",
        "precision_contract_2f": contract.get("precision_contract_id")
        == "rogshai-hybrid-sequential-2F-v1",
        "sesoi_separate_from_precision": float(
            contract.get("practical_effect", {}).get("sesoi", -1)
        )
        == SESOI
        and contract.get("practical_effect", {}).get("sesoi_is_model_precision") is False,
        "confirmatory_2f_budget": len(manifest.confirmatory.scenario_ids) == 2048,
        "sealed_holdout_single_look_budget": len(manifest.sealed_holdout.scenario_ids) == 2048,
        "exploratory_4p": _verify_partition_4p(
            orchestrator,
            master_seed=manifest.exploratory.master_seed,
            expected_ids=manifest.exploratory.scenario_ids,
            expected_seeds=manifest.exploratory.scenario_seeds,
        ),
        "calibration_4p": _verify_partition_4p(
            orchestrator,
            master_seed=manifest.calibration_partition.master_seed,
            expected_ids=manifest.calibration_partition.scenario_ids,
            expected_seeds=manifest.calibration_partition.scenario_seeds,
        ),
        "confirmatory_4p": _verify_partition_4p(
            orchestrator,
            master_seed=manifest.confirmatory.master_seed,
            expected_ids=manifest.confirmatory.scenario_ids,
            expected_seeds=manifest.confirmatory.scenario_seeds,
        ),
        "diagnostics_4p": _verify_partition_4p(
            orchestrator,
            master_seed=manifest.critical_diagnostics.master_seed,
            expected_ids=manifest.critical_diagnostics.scenario_ids,
            expected_seeds=manifest.critical_diagnostics.scenario_seeds,
        ),
        "holdout_4p": _verify_partition_4p(
            orchestrator,
            master_seed=manifest.sealed_holdout.master_seed,
            expected_ids=manifest.sealed_holdout.scenario_ids,
            expected_seeds=manifest.sealed_holdout.scenario_seeds,
        ),
    }
    if not all(checks.values()):
        failed = sorted(key for key, passed in checks.items() if not passed)
        raise RuntimeError(f"decision preflight failed closed: {', '.join(failed)}")
    return {
        **base,
        "decision_runtime_version": DECISION_RUNTIME_VERSION,
        "decision_checks": checks,
        "candidate_count": len(lab.context.cards),
        "semantic_unknown_count": len(unknown),
        "operational_pod_size": 4,
    }


def _normal_interval(values: Sequence[float], confidence: float) -> tuple[float, float]:
    mean = fmean(values)
    mcse = monte_carlo_standard_error(values)
    if mcse == 0:
        return mean, mean
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    return mean - z * mcse, mean + z * mcse


def _seed_stability(values: Sequence[float], *, mcse: float) -> dict[str, object]:
    blocks = [tuple(values[index::SEED_BLOCK_COUNT]) for index in range(SEED_BLOCK_COUNT)]
    means = tuple(fmean(block) for block in blocks if block)
    pooled = fmean(values)
    tolerance = max(2.0 * SESOI, 4.0 * mcse)
    maximum_deviation = max((abs(value - pooled) for value in means), default=0.0)
    direction_consistent = all(value >= ROBUSTNESS_MARGIN for value in means)
    return {
        "block_count": len(means),
        "block_means": means,
        "maximum_deviation_from_pooled": maximum_deviation,
        "tolerance": tolerance,
        "direction_consistent": direction_consistent,
        "pass": len(means) == SEED_BLOCK_COUNT
        and direction_consistent
        and maximum_deviation <= tolerance,
        "evidence_boundary": "within-partition same-model seed stability; not real-world replication",
    }


class DecisionPartitionEvaluator(CachedPartitionEvaluator):
    def __init__(self, *args: Any, confidence: float, **kwargs: Any) -> None:
        if not 0.0 < confidence < 1.0:
            raise ValueError("decision confidence must be between zero and one")
        self.decision_confidence = confidence
        super().__init__(*args, **kwargs)

    def _identity(
        self, *, candidate_hash: str, scenarios: tuple[Any, ...], budget: int
    ) -> dict[str, Any]:
        identity = super()._identity(
            candidate_hash=candidate_hash, scenarios=scenarios, budget=budget
        )
        identity["decision_runtime_version"] = DECISION_RUNTIME_VERSION
        identity["decision_interval_confidence"] = self.decision_confidence
        return identity

    def _compute(
        self, *, candidate: Any, scenarios: tuple[Any, ...], budget: int
    ) -> dict[str, Any]:
        observations: list[dict[str, object]] = []
        pilot_deltas: dict[str, list[float]] = defaultdict(list)
        groups = (
            (
                "strong_deterministic",
                PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC),
                scenarios[::2],
            ),
            (
                "average_deterministic",
                PilotConfig(strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC),
                scenarios[1::2],
            ),
        )
        statistics_seed = int(
            sha256_value(
                {
                    "partition": self.partition.identity,
                    "candidate": candidate.deck_hash,
                    "budget": budget,
                    "axis": "decision-runtime-statistics",
                }
            )[:16],
            16,
        ) % (2**31 - 1)
        for label, pilot, group in groups:
            if not group:
                continue
            result = run_balanced_paired_campaign(
                baseline=self.control,
                variant=candidate,
                opponent_profiles=self.orchestrator.opponents.profiles(),
                scenarios=group,
                pilot_config=pilot,
                max_turns=self.max_turns,
                statistics_seed=statistics_seed,
                workers=self.workers,
            )
            raw = result.get("paired_observations", [])
            if not isinstance(raw, list):
                raise TypeError("paired campaign observations are malformed")
            for row in raw:
                if not isinstance(row, dict):
                    continue
                delta = _number(row, "baseline_placement") - _number(row, "variant_placement")
                pilot_deltas[label].append(delta)
                observations.append(row)
        differences = tuple(
            _number(row, "baseline_placement") - _number(row, "variant_placement")
            for row in observations
        )
        if len(differences) != budget:
            raise RuntimeError("decision evaluator did not cover requested frozen budget")
        interval = _normal_interval(differences, self.decision_confidence)
        bootstrap95 = paired_bootstrap_interval(
            differences, confidence=0.95, seed=statistics_seed + 23
        )
        mcse = monte_carlo_standard_error(differences)
        per_seat: dict[str, list[float]] = defaultdict(list)
        per_opponent: dict[str, list[float]] = defaultdict(list)
        per_triple: dict[str, list[float]] = defaultdict(list)
        for row, delta in zip(observations, differences, strict=True):
            per_seat[str(int(_number(row, "own_seat")))].append(delta)
            opponents = row.get("opponent_deck_ids", [])
            if isinstance(opponents, list):
                names = tuple(sorted(str(value) for value in opponents))
                per_triple["|".join(names)].append(delta)
                for name in names:
                    per_opponent[name].append(delta)
        per_pilot = {key: fmean(values) for key, values in sorted(pilot_deltas.items())}
        sensitivity = {
            "pilot": {"mean_paired_delta": per_pilot},
            "seat": {key: fmean(values) for key, values in sorted(per_seat.items())},
            "per_opponent": {key: fmean(values) for key, values in sorted(per_opponent.items())},
            "exact_opponent_triple_diagnostic": {
                key: fmean(values) for key, values in sorted(per_triple.items())
            },
            "mulligan": self._mulligan_sensitivity(candidate, budget),
        }
        return {
            "budget": budget,
            "score": fmean(differences),
            "interval_low": interval[0],
            "interval_high": interval[1],
            "decision_interval_confidence": self.decision_confidence,
            "bootstrap_95_interval": bootstrap95,
            "mcse": mcse,
            "seed_stability": _seed_stability(differences, mcse=mcse),
            "robust_lower_bound": distributionally_robust_lower_bound(differences),
            "sensitivity": sensitivity,
            "observation_count": len(observations),
            "evidence_context": self.evidence_context.value,
            "evidence_type": "structural_model_estimates",
        }


def _broad_robustness(payload: Mapping[str, Any]) -> dict[str, object]:
    sensitivity = payload.get("sensitivity", {})
    if not isinstance(sensitivity, Mapping):
        return {"pass": False, "reason": "missing_sensitivity"}
    pilot_raw = sensitivity.get("pilot", {})
    pilot_means = pilot_raw.get("mean_paired_delta", {}) if isinstance(pilot_raw, Mapping) else {}
    seat_means = sensitivity.get("seat", {})
    opponent_means = sensitivity.get("per_opponent", {})
    groups = (
        pilot_means if isinstance(pilot_means, Mapping) else {},
        seat_means if isinstance(seat_means, Mapping) else {},
        opponent_means if isinstance(opponent_means, Mapping) else {},
    )
    values = [
        float(value)
        for group in groups
        for value in group.values()
        if isinstance(value, int | float)
    ]
    complete = (
        len(pilot_means) == 2
        and set(str(key) for key in seat_means) == {"1", "2", "3", "4"}
        and bool(opponent_means)
    )
    worst = min(values) if values else float("-inf")
    return {
        "pass": complete and worst >= ROBUSTNESS_MARGIN,
        "coverage_complete": complete,
        "worst_broad_stratum_mean": worst,
        "margin": ROBUSTNESS_MARGIN,
        "pilot_means": dict(pilot_means),
        "seat_means": dict(seat_means) if isinstance(seat_means, Mapping) else {},
        "per_opponent_means": dict(opponent_means) if isinstance(opponent_means, Mapping) else {},
        "exact_triples_are_diagnostics_not_frequency_weighted_gates": True,
    }


def _semantic_fidelity(lab: WholeDeckDesignLab, variant: WholeDeckVariant) -> dict[str, object]:
    unknown = tuple(
        sorted(
            name
            for name in set(variant.mainboard)
            if name not in lab.context.cards
            or lab.context.cards[name].effective_semantic_state == SEMANTIC_UNKNOWN
        )
    )
    return {"pass": not unknown, "unknown_cards": unknown}


def _shortlist(
    handoff: FrontierHandoff, limit: int = SHORTLIST_LIMIT
) -> tuple[dict[str, Any], ...]:
    rows = [row for row in handoff.elites if isinstance(row.get("evaluation"), dict)]
    rows.sort(
        key=lambda row: (
            -float(row["evaluation"].get("robust_lower_bound", -999.0)),
            -float(row["evaluation"].get("score", -999.0)),
            str(row.get("deck_hash", "")),
        )
    )
    selected: list[dict[str, Any]] = []
    seen_cells: set[str] = set()
    for row in rows:
        cell = str(row["evaluation"].get("qd_cell", ""))
        if cell and cell not in seen_cells:
            selected.append(row)
            seen_cells.add(cell)
            if len(selected) >= limit:
                break
    if len(selected) < limit:
        chosen = {str(row.get("deck_hash")) for row in selected}
        for row in rows:
            if str(row.get("deck_hash")) in chosen:
                continue
            selected.append(row)
            if len(selected) >= limit:
                break
    return tuple(selected)


def _sequential_status(
    *,
    evaluation: Any,
    payload: Mapping[str, Any],
    budget: int,
    semantic_pass: bool,
) -> tuple[str, dict[str, object]]:
    precision = {
        "mcse": float(payload.get("mcse", float("inf"))),
        "mcse_threshold": MCSE_MAX,
        "mcse_pass": float(payload.get("mcse", float("inf"))) <= MCSE_MAX,
        "seed_stability": payload.get("seed_stability", {}),
    }
    seed_pass = bool(
        isinstance(precision["seed_stability"], Mapping)
        and precision["seed_stability"].get("pass") is True
    )
    precision_pass = bool(precision["mcse_pass"] and seed_pass)
    robustness = _broad_robustness(payload)
    if evaluation.interval_high < 0:
        status = "REJECT_HARM"
    elif budget >= 1024 and evaluation.interval_high < SESOI:
        status = "FUTILITY_BELOW_SESOI"
    elif evaluation.interval_low > SESOI:
        if precision_pass and robustness.get("pass") is True and semantic_pass:
            status = "PROMOTION_CANDIDATE"
        elif budget < CONFIRMATORY_LOOKS[-1]:
            status = "MORE_SAMPLES"
        elif not precision_pass:
            status = "BLOCKED_PRECISION"
        elif robustness.get("pass") is not True:
            status = "BLOCKED_ROBUSTNESS"
        else:
            status = "BLOCKED_SEMANTIC_FIDELITY"
    elif budget == CONFIRMATORY_LOOKS[-1]:
        status = "PRECISION_LIMIT"
    else:
        status = "MORE_SAMPLES"
    return status, {
        "precision": {**precision, "pass": precision_pass},
        "robustness": robustness,
        "semantic_fidelity_pass": semantic_pass,
    }


def _changed_slots(control: Sequence[str], candidate: Sequence[str]) -> int:
    left = Counter(control)
    right = Counter(candidate)
    return sum(max(0, right[name] - left[name]) for name in set(left) | set(right))


def _mapping_float(mapping: Mapping[str, object], key: str) -> float:
    value = mapping.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def _pareto_dimensions(row: Mapping[str, Any]) -> dict[str, float]:
    terminal = row["terminal_evaluation"]
    variant = WholeDeckVariant.model_validate(row["variant"])
    roles = variant.feature_vector.get("role_strengths", {})
    role_map = roles if isinstance(roles, Mapping) else {}
    robustness = row["terminal_gates"]["robustness"]
    return {
        "paired_effect": float(terminal["score"]),
        "worst_broad_stratum": float(robustness["worst_broad_stratum_mean"]),
        "precision_inverse_mcse": -float(terminal["mcse"]),
        "interaction": sum(
            _mapping_float(role_map, key)
            for key in ("counter", "removal", "wipe", "graveyard_hate")
        ),
        "protection": _mapping_float(role_map, "protection"),
        "velocity": sum(_mapping_float(role_map, key) for key in ("ramp", "selection", "draw")),
        "finish": sum(
            _mapping_float(role_map, key) for key in ("finisher", "payoff", "combat_payoff")
        ),
        "semantic_support": float(
            variant.feature_vector.get("semantic_support_fraction", 0.0) or 0.0
        ),
        "multiplayer_scaling": float(variant.feature_vector.get("multiplayer_scaling", 0.0) or 0.0),
    }


def _dominates(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    keys = tuple(left)
    return all(left[key] >= right[key] for key in keys) and any(
        left[key] > right[key] for key in keys
    )


def _select_single_challenger(
    rows: Sequence[dict[str, Any]], control: Sequence[str]
) -> tuple[tuple[str, ...], str | None, str]:
    promoted = [row for row in rows if row.get("terminal_status") == "PROMOTION_CANDIDATE"]
    if not promoted:
        return (), None, "no_confirmatory_promotion_candidate"
    dimensions = {str(row["deck_hash"]): _pareto_dimensions(row) for row in promoted}
    frontier = tuple(
        sorted(
            deck_hash
            for deck_hash, vector in dimensions.items()
            if not any(
                other_hash != deck_hash and _dominates(other_vector, vector)
                for other_hash, other_vector in dimensions.items()
            )
        )
    )
    by_hash = {str(row["deck_hash"]): row for row in promoted}
    chosen = max(
        frontier,
        key=lambda deck_hash: (
            dimensions[deck_hash]["worst_broad_stratum"],
            dimensions[deck_hash]["paired_effect"],
            dimensions[deck_hash]["precision_inverse_mcse"],
            dimensions[deck_hash]["semantic_support"],
            -_changed_slots(
                control, WholeDeckVariant.model_validate(by_hash[deck_hash]["variant"]).mainboard
            ),
            deck_hash,
        ),
    )
    return frontier, chosen, "pareto_frontier_then_preregistered_lexicographic_tiebreak"


def run_decision_search(
    root: str | Path,
    manifest: DecisionOptimizerV2Manifest,
    *,
    run_directory: str | Path,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    verify_decision_preflight(root, manifest)
    return run_release_search(
        root,
        manifest,
        run_directory=run_directory,
        workers=workers,
        max_turns=max_turns,
    )


def run_decision_confirmatory(
    root: str | Path,
    manifest: DecisionOptimizerV2Manifest,
    *,
    frontier_path: str | Path,
    run_directory: str | Path,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    preflight = verify_decision_preflight(root_path, manifest)
    handoff = _load_handoff(frontier_path, manifest)
    shortlist = _shortlist(handoff)
    if not shortlist:
        report: dict[str, object] = {
            "schema_version": "2.0.0",
            "manifest_hash": manifest.manifest_hash,
            "shortlist_size": 0,
            "rows": [],
            "pareto_frontier": [],
            "single_challenger_hash": None,
            "decision": "NO_CHALLENGER",
            "sealed_holdout_partition_opened": False,
            "canonical_deck_mutation": False,
        }
        atomic_write_json(run_path / "confirmatory-report.json", report)
        return report
    alpha_per_candidate_look = FAMILY_ALPHA / (len(shortlist) * len(CONFIRMATORY_LOOKS))
    confidence = 1.0 - alpha_per_candidate_look
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    evaluator = DecisionPartitionEvaluator(
        root=root_path,
        manifest=manifest,
        orchestrator=orchestrator,
        control_mainboard=current_control_mainboard(root_path),
        context=lab.context,
        evidence_context=EvidenceContext.CONFIRMATORY,
        run_directory=run_path,
        workers=workers,
        max_turns=max_turns,
        enable_mulligan_sensitivity=False,
        confidence=confidence,
    )
    rows: list[dict[str, Any]] = []
    for index, elite in enumerate(shortlist):
        variant = WholeDeckVariant.model_validate(elite["variant"])
        semantic = _semantic_fidelity(lab, variant)
        looks: list[dict[str, object]] = []
        terminal_status = "PRECISION_LIMIT"
        terminal_evaluation: dict[str, Any] = {}
        terminal_gates: dict[str, Any] = {}
        for look_index, budget in enumerate(CONFIRMATORY_LOOKS):
            evaluation = evaluator(variant, budget, 20_000 + index * 100 + look_index)
            payload = evaluator.cached_payload_by_hash[variant.deck_hash]
            status, gates = _sequential_status(
                evaluation=evaluation,
                payload=payload,
                budget=budget,
                semantic_pass=bool(semantic["pass"]),
            )
            terminal_status = status
            terminal_evaluation = {
                **evaluation.model_dump(mode="json"),
                "mcse": payload["mcse"],
                "seed_stability": payload["seed_stability"],
                "decision_interval_confidence": confidence,
            }
            terminal_gates = gates
            looks.append(
                {
                    "look": look_index + 1,
                    "budget": budget,
                    "evaluation": terminal_evaluation,
                    "gates": gates,
                    "status": status,
                }
            )
            if status != "MORE_SAMPLES":
                break
        rows.append(
            {
                "deck_hash": variant.deck_hash,
                "candidate_id": variant.variant_id,
                "variant": variant.model_dump(mode="json"),
                "semantic_fidelity": semantic,
                "looks": looks,
                "terminal_status": terminal_status,
                "terminal_evaluation": terminal_evaluation,
                "terminal_gates": terminal_gates,
            }
        )
    control = current_control_mainboard(root_path)
    pareto_frontier, chosen, selection_rule = _select_single_challenger(rows, control)
    report = {
        "schema_version": "2.0.0",
        "runtime_version": DECISION_RUNTIME_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "frontier_hash": handoff.frontier_hash,
        "preflight": preflight,
        "evidence_context": "confirmatory",
        "evidence_type": "structural_model_estimates",
        "shortlist_limit": SHORTLIST_LIMIT,
        "shortlist_size": len(shortlist),
        "shortlist_hashes": [str(row["deck_hash"]) for row in shortlist],
        "family_alpha": FAMILY_ALPHA,
        "planned_looks": list(CONFIRMATORY_LOOKS),
        "alpha_per_candidate_look": alpha_per_candidate_look,
        "decision_interval_confidence": confidence,
        "mcse_threshold": MCSE_MAX,
        "rows": rows,
        "pareto_frontier": list(pareto_frontier),
        "single_challenger_hash": chosen,
        "single_challenger_selection_rule": selection_rule,
        "critical_diagnostics_required_before_holdout": chosen is not None,
        "sealed_holdout_partition_opened": False,
        "learning_updates": False,
        "construction_updates": False,
        "canonical_deck_mutation": False,
    }
    atomic_write_json(run_path / "confirmatory-report.json", report)
    _write_audit(
        run_path=run_path,
        manifest=manifest,
        stage="confirmatory",
        evidence_context="confirmatory",
        evaluator_payload=evaluator.audit().model_dump(mode="json"),
        outputs={"confirmatory": report},
        confirmatory_opened=True,
    )
    return report


def _deny_commanders(deck: StructuralDeckProfile, denied: frozenset[str]) -> StructuralDeckProfile:
    costs = dict(deck.commander_base_costs)
    for name in denied:
        if name not in costs:
            raise RuntimeError(f"unknown commander for denial stress: {name}")
        costs[name] = 100.0
    return deck.model_copy(update={"commander_base_costs": costs})


def _ablate_added_package(
    deck: StructuralDeckProfile,
    *,
    affected_names: frozenset[str],
    package_id: str,
) -> StructuralDeckProfile:
    cards: list[StructuralCardProfile] = []
    for card in deck.cards:
        if card.oracle_name not in affected_names or package_id not in card.package_ids:
            cards.append(card)
            continue
        keep_mana = CardRole.MANA_SOURCE in card.roles
        roles = frozenset({CardRole.MANA_SOURCE}) if keep_mana else frozenset()
        role_strengths = {CardRole.MANA_SOURCE: 1.0} if keep_mana else {}
        cards.append(
            card.model_copy(
                update={
                    "roles": roles,
                    "role_strengths": role_strengths,
                    "mechanic_tags": frozenset(),
                    "commander_synergy": 0.0,
                    "floor_value": 0.5,
                    "immediate_impact": 0.5,
                    "turn_cycle_risk": 0.5,
                    "multiplayer_scaling": 0.0,
                    "conditional_strength": (),
                    "package_ids": frozenset(pid for pid in card.package_ids if pid != package_id),
                    "notes": (
                        (card.notes or "") + " Synthetic package-ablation stress only."
                    ).strip(),
                }
            )
        )
    return deck.model_copy(update={"cards": tuple(cards)})


def _run_diagnostic_pair(
    *,
    baseline: StructuralDeckProfile,
    candidate: StructuralDeckProfile,
    orchestrator: WholeDeckCampaignOrchestrator,
    scenarios: Sequence[Any],
    workers: int,
    max_turns: int,
    seed: int,
) -> dict[str, object]:
    observations: list[dict[str, object]] = []
    for offset, (strength, group) in enumerate(
        ((PilotStrength.STRONG, scenarios[::2]), (PilotStrength.AVERAGE, scenarios[1::2]))
    ):
        if not group:
            continue
        result = run_balanced_paired_campaign(
            baseline=baseline,
            variant=candidate,
            opponent_profiles=orchestrator.opponents.profiles(),
            scenarios=group,
            pilot_config=PilotConfig(strength=strength, mode=PilotDecisionMode.DETERMINISTIC),
            max_turns=max_turns,
            statistics_seed=seed + offset,
            workers=workers,
        )
        raw = result.get("paired_observations", [])
        if isinstance(raw, list):
            observations.extend(row for row in raw if isinstance(row, dict))
    values = tuple(
        _number(row, "baseline_placement") - _number(row, "variant_placement")
        for row in observations
    )
    if len(values) != len(scenarios):
        raise RuntimeError("critical diagnostic did not cover frozen partition")
    interval = _normal_interval(values, 0.95)
    return {
        "paired_count": len(values),
        "mean_delta": fmean(values),
        "interval_low": interval[0],
        "interval_high": interval[1],
        "mcse": monte_carlo_standard_error(values),
    }


def run_critical_diagnostics(
    root: str | Path,
    manifest: DecisionOptimizerV2Manifest,
    *,
    confirmatory_path: str | Path,
    run_directory: str | Path,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    verify_decision_preflight(root_path, manifest)
    confirmatory = json.loads(Path(confirmatory_path).read_text(encoding="utf-8"))
    if (
        not isinstance(confirmatory, dict)
        or confirmatory.get("manifest_hash") != manifest.manifest_hash
    ):
        raise RuntimeError("confirmatory report manifest mismatch")
    deck_hash = confirmatory.get("single_challenger_hash")
    if not isinstance(deck_hash, str) or not deck_hash:
        raise RuntimeError(
            "critical diagnostics require exactly one frozen confirmatory challenger"
        )
    handoff = _load_handoff(run_path / "frontier-handoff.json", manifest)
    elite = next((row for row in handoff.elites if str(row.get("deck_hash")) == deck_hash), None)
    if elite is None:
        raise RuntimeError("frozen challenger is absent from manifest-bound frontier")
    variant = WholeDeckVariant.model_validate(elite["variant"])
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    control_mainboard = current_control_mainboard(root_path)
    baseline = lab.context.materialize(control_mainboard, label="critical-control")
    candidate = lab.context.materialize(variant.mainboard, label="critical-candidate")
    scenarios = tuple(
        orchestrator.scheduler.schedule(
            len(manifest.critical_diagnostics.scenario_ids),
            seed=manifest.critical_diagnostics.master_seed,
        )
    )
    if (
        tuple(row.scenario_id for row in scenarios) != manifest.critical_diagnostics.scenario_ids
        or tuple(row.seed for row in scenarios) != manifest.critical_diagnostics.scenario_seeds
        or any(len(row.opponent_deck_ids) != 3 for row in scenarios)
    ):
        raise RuntimeError("critical diagnostics partition mismatch")
    commanders = tuple(candidate.commander_names)
    if len(commanders) != 2:
        raise RuntimeError("RogShai critical diagnostics require exactly two commanders")
    conditions: list[tuple[str, StructuralDeckProfile, StructuralDeckProfile, str]] = []
    for name in commanders:
        conditions.append(
            (
                f"deny_{name}",
                _deny_commanders(baseline, frozenset({name})),
                _deny_commanders(candidate, frozenset({name})),
                "synthetic_assumption+structural_model_estimates",
            )
        )
    conditions.append(
        (
            "deny_both_commanders",
            _deny_commanders(baseline, frozenset(commanders)),
            _deny_commanders(candidate, frozenset(commanders)),
            "synthetic_assumption+structural_model_estimates",
        )
    )
    control_counts = Counter(control_mainboard)
    candidate_counts = Counter(variant.mainboard)
    added = frozenset(
        name for name in candidate_counts if candidate_counts[name] > control_counts.get(name, 0)
    )
    package_counts: Counter[str] = Counter(
        package_id for name in added for package_id in lab.context.cards[name].profile.package_ids
    )
    ablation_package = None
    if package_counts:
        ablation_package = min(
            package_counts,
            key=lambda key: (-package_counts[key], key),
        )
        conditions.append(
            (
                f"ablate_added_package:{ablation_package}",
                baseline,
                _ablate_added_package(candidate, affected_names=added, package_id=ablation_package),
                "synthetic_assumption+structural_model_estimates",
            )
        )
    rows: list[dict[str, object]] = []
    for index, (condition, left, right, evidence) in enumerate(conditions):
        result = _run_diagnostic_pair(
            baseline=left,
            candidate=right,
            orchestrator=orchestrator,
            scenarios=scenarios,
            workers=workers,
            max_turns=max_turns,
            seed=manifest.critical_diagnostics.master_seed + index * 101,
        )
        if condition.startswith("ablate_added_package:"):
            passed = (
                _number(result, "interval_high") >= ROBUSTNESS_MARGIN
                and _number(result, "mean_delta") >= -0.10
            )
            rule = "not clearly >SESOI worse after top added-package ablation; mean >= -0.10"
        else:
            passed = (
                _number(result, "mean_delta") >= ROBUSTNESS_MARGIN
                and _number(result, "interval_high") >= ROBUSTNESS_MARGIN
            )
            rule = "mean candidate delta under matched denial >= -SESOI and not clearly materially worse"
        rows.append(
            {
                "condition": condition,
                "evidence_type": evidence,
                "result": result,
                "pass": passed,
                "rule": rule,
            }
        )
    overall = bool(rows) and all(row["pass"] is True for row in rows)
    report = {
        "schema_version": "1.0.0",
        "runtime_version": DECISION_RUNTIME_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "challenger_hash": deck_hash,
        "partition_identity": manifest.critical_diagnostics.identity,
        "operational_pod_size": 4,
        "rows": rows,
        "top_added_package_ablation": ablation_package,
        "critical_diagnostics_pass": overall,
        "sealed_holdout_partition_opened": False,
        "canonical_deck_mutation": False,
        "evidence_boundary": "commander denial and package ablation are synthetic structural stress tests, not real observations",
    }
    atomic_write_json(run_path / "critical-diagnostics-report.json", report)
    return report


def run_decision_holdout(
    root: str | Path,
    manifest: DecisionOptimizerV2Manifest,
    *,
    confirmatory_path: str | Path,
    diagnostics_path: str | Path,
    run_directory: str | Path,
    authorize_holdout: bool = False,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    if not authorize_holdout:
        raise RuntimeError("fresh sealed holdout requires explicit --authorize-holdout")
    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    verify_decision_preflight(root_path, manifest)
    confirmatory = json.loads(Path(confirmatory_path).read_text(encoding="utf-8"))
    diagnostics = json.loads(Path(diagnostics_path).read_text(encoding="utf-8"))
    if (
        not isinstance(confirmatory, dict)
        or confirmatory.get("manifest_hash") != manifest.manifest_hash
    ):
        raise RuntimeError("confirmatory report manifest mismatch")
    if (
        not isinstance(diagnostics, dict)
        or diagnostics.get("manifest_hash") != manifest.manifest_hash
    ):
        raise RuntimeError("critical diagnostics report manifest mismatch")
    deck_hash = confirmatory.get("single_challenger_hash")
    if not isinstance(deck_hash, str) or not deck_hash:
        raise RuntimeError("holdout requires exactly one frozen challenger")
    if (
        diagnostics.get("challenger_hash") != deck_hash
        or diagnostics.get("critical_diagnostics_pass") is not True
    ):
        raise RuntimeError("critical diagnostics did not authorize the frozen challenger")
    handoff = _load_handoff(run_path / "frontier-handoff.json", manifest)
    elite = next((row for row in handoff.elites if str(row.get("deck_hash")) == deck_hash), None)
    if elite is None:
        raise RuntimeError("frozen challenger is absent from manifest-bound frontier")
    variant = WholeDeckVariant.model_validate(elite["variant"])
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    evaluator = DecisionPartitionEvaluator(
        root=root_path,
        manifest=manifest,
        orchestrator=orchestrator,
        control_mainboard=current_control_mainboard(root_path),
        context=lab.context,
        evidence_context=EvidenceContext.HOLDOUT,
        run_directory=run_path,
        workers=workers,
        max_turns=max_turns,
        enable_mulligan_sensitivity=False,
        confidence=0.95,
    )
    evaluation = evaluator(variant, 2048, 30_000)
    payload = evaluator.cached_payload_by_hash[variant.deck_hash]
    robustness = _broad_robustness(payload)
    winner = evaluation.interval_low > SESOI and robustness.get("pass") is True
    report: dict[str, object] = {
        "schema_version": "2.0.0",
        "runtime_version": DECISION_RUNTIME_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "evidence_context": "holdout",
        "evidence_type": "structural_model_estimates",
        "authorized": True,
        "single_frozen_challenger_hash": deck_hash,
        "paired_4p_budget": 2048,
        "planned_looks": 1,
        "decision_interval_confidence": 0.95,
        "evaluation": {**evaluation.model_dump(mode="json"), "mcse": payload["mcse"]},
        "holdout_robustness": robustness,
        "critical_diagnostics_pass": True,
        "decision": "WINNER" if winner else "NO_WINNER",
        "official_winner_declared": winner,
        "search_learning_updates": False,
        "construction_updates": False,
        "canonical_deck_mutation": False,
    }
    atomic_write_json(run_path / "holdout-report.json", report)
    _write_audit(
        run_path=run_path,
        manifest=manifest,
        stage="holdout",
        evidence_context="holdout",
        evaluator_payload=evaluator.audit().model_dump(mode="json"),
        outputs={"holdout": report},
        confirmatory_opened=True,
        holdout_opened=True,
    )
    return report
