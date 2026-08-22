from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from commander_lab.storage import atomic_write_json, sha256_value
from commander_lab.technical_truth import build_technical_truth

from .lab import WholeDeckDesignLab
from .lab_context import EnrichedWholeDeckSearchEngine
from .models import PolicyId
from .optimizer_advancement import (
    build_confirmatory_frontier,
    load_model_resolution_decision_policy,
)
from .optimizer_calibration import calibrate_decision_policy
from .optimizer_search import AdaptiveWholeDeckSearch, ProjectPairedEvaluator
from .optimizer_v2 import (
    EvidenceContext,
    EvidencePartition,
    OptimizerCheckpointStore,
    OptimizerLock,
    OptimizerManifest,
)
from .orchestrator import WholeDeckCampaignOrchestrator
from .policies import get_policy
from .search import current_control_mainboard
from .search_models import WholeDeckSearchConfig, WholeDeckVariant

OPTIMIZER_RUNTIME_VERSION = "optimizer-v2-runtime-0.2.0"
DEFAULT_POLICIES = tuple(policy.value for policy in PolicyId)


def _require_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"technical truth is missing {key}")
    return value


def _partition_from_scheduler(
    orchestrator: WholeDeckCampaignOrchestrator,
    *,
    partition_id: str,
    context: EvidenceContext,
    master_seed: int,
    games: int,
) -> EvidencePartition:
    scenarios = orchestrator.scheduler.schedule(games, seed=master_seed)
    return EvidencePartition.create(
        partition_id=partition_id,
        evidence_context=context,
        master_seed=master_seed,
        scenario_ids=tuple(row.scenario_id for row in scenarios),
        scenario_seeds=tuple(row.seed for row in scenarios),
    )


def build_optimizer_manifest_from_project(
    root: str | Path,
    *,
    run_id: str,
    search_seed: int,
    exploratory_games: int = 256,
    confirmatory_games: int = 512,
    holdout_games: int = 512,
    policies: Iterable[str] = DEFAULT_POLICIES,
) -> OptimizerManifest:
    """Freeze a live project snapshot without running optimizer evaluations."""

    root_path = Path(root).resolve()
    truth = build_technical_truth(root_path)
    git = truth.get("git")
    if not isinstance(git, dict):
        raise RuntimeError("technical truth has no git identity")
    if git.get("tracked_dirty") is not False:
        raise RuntimeError("optimizer manifest requires a clean tracked worktree")

    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    control_mainboard = current_control_mainboard(root_path)
    control = lab.context.materialize(control_mainboard, label="optimizer-v2-control")
    selected = calibrate_decision_policy()
    policy_names = tuple(sorted(str(value) for value in policies))
    pilot_contract = {
        "assignment": "scenario_parity_fixed_ensemble",
        "profiles": ("strong_deterministic", "average_deterministic"),
        "outcome_dependent": False,
    }
    construction_contract = {
        "policies": policy_names,
        "role": "proposal_priors_not_ground_truth",
        "search_seed": search_seed,
    }
    return OptimizerManifest(
        run_id=run_id,
        software_commit=_require_text(git, "commit"),
        software_tree=_require_text(git, "tree"),
        package_version=_require_text(truth, "package_version"),
        engine_version=_require_text(truth, "engine_version"),
        physical_pool_identity=lab.context.snapshot_hash,
        control_deck_hash=control.deck_hash,
        opponent_data_identity=orchestrator.opponents.registry_hash,
        knowledge_identity=lab.enrichment.snapshot_hash,
        pilot_policy_identity=sha256_value(pilot_contract),
        mulligan_policy_identity=sha256_value(lab.enrichment.mulligan_contract),
        construction_prior_identity=sha256_value(construction_contract),
        search_seed=search_seed,
        exploratory=_partition_from_scheduler(
            orchestrator,
            partition_id="exploratory",
            context=EvidenceContext.EXPLORATORY,
            master_seed=search_seed ^ 0x12A4_7C31,
            games=exploratory_games,
        ),
        confirmatory=_partition_from_scheduler(
            orchestrator,
            partition_id="confirmatory",
            context=EvidenceContext.CONFIRMATORY,
            master_seed=search_seed ^ 0x37C9_41A5,
            games=confirmatory_games,
        ),
        sealed_holdout=_partition_from_scheduler(
            orchestrator,
            partition_id="sealed_holdout",
            context=EvidenceContext.HOLDOUT,
            master_seed=search_seed ^ 0x5F37_9A21,
            games=holdout_games,
        ),
        calibration=selected.policy,
    )


def load_optimizer_manifest(path: str | Path) -> OptimizerManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return OptimizerManifest.model_validate(payload)


def verify_optimizer_preflight(root: str | Path, manifest: OptimizerManifest) -> dict[str, object]:
    root_path = Path(root).resolve()
    truth = build_technical_truth(root_path)
    git = truth.get("git")
    if not isinstance(git, dict):
        raise RuntimeError("technical truth has no git identity")
    checks = {
        "git_commit": git.get("commit") == manifest.software_commit,
        "git_tree": git.get("tree") == manifest.software_tree,
        "package": truth.get("package_version") == manifest.package_version,
        "engine": truth.get("engine_version") == manifest.engine_version,
        "tracked_clean": git.get("tracked_dirty") is False,
    }
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    control = lab.context.materialize(
        current_control_mainboard(root_path),
        label="optimizer-v2-control",
    )
    checks.update(
        {
            "physical_pool": lab.context.snapshot_hash == manifest.physical_pool_identity,
            "control": control.deck_hash == manifest.control_deck_hash,
            "opponents": orchestrator.opponents.registry_hash == manifest.opponent_data_identity,
            "knowledge": lab.enrichment.snapshot_hash == manifest.knowledge_identity,
        }
    )
    if not all(checks.values()):
        failed = sorted(key for key, passed in checks.items() if not passed)
        raise RuntimeError(f"optimizer preflight failed closed: {', '.join(failed)}")
    return {
        "status": "pass",
        "manifest_hash": manifest.manifest_hash,
        "checks": checks,
    }


def _initial_variants(
    lab: WholeDeckDesignLab,
    manifest: OptimizerManifest,
    *,
    policies: Iterable[str],
    diversified_starts: int,
    steps_per_start: int,
    finalists_per_policy: int,
) -> tuple[dict[str, EnrichedWholeDeckSearchEngine], tuple[WholeDeckVariant, ...]]:
    control = current_control_mainboard(lab.root)
    engines: dict[str, EnrichedWholeDeckSearchEngine] = {}
    by_hash: dict[str, WholeDeckVariant] = {}
    control_anchor: WholeDeckVariant | None = None
    policy_ids = tuple(PolicyId(raw) for raw in policies)
    for index, policy_id in enumerate(policy_ids):
        policy = get_policy(policy_id)
        config = WholeDeckSearchConfig(
            seed=manifest.search_seed + index * 1009,
            diversified_starts=diversified_starts,
            max_steps_per_start=steps_per_start,
            finalist_limit=finalists_per_policy,
            archive_limit=max(32, finalists_per_policy * 4),
        )
        engine = EnrichedWholeDeckSearchEngine(
            lab.context,
            policy,
            config=config,
            enrichment=lab.enrichment,
            answer_map=lab.answer_map,
        )
        engines[policy.policy_id.value] = engine
        result = engine.run(current_control=control)
        finalist_ids = set(result.finalist_variant_ids)
        for variant in result.variants:
            if variant.variant_id in finalist_ids and variant.hard_gate.valid:
                previous = by_hash.get(variant.deck_hash)
                if previous is None or variant.objective_prior > previous.objective_prior:
                    by_hash[variant.deck_hash] = variant
        if policy.policy_id == PolicyId.CURRENT_CONTROL:
            anchor_id = result.control_variant_id
            if anchor_id is None:
                raise RuntimeError(
                    "CURRENT_CONTROL construction result is missing its control arm"
                )
            anchor = next(
                (variant for variant in result.variants if variant.variant_id == anchor_id),
                None,
            )
            if anchor is None:
                raise RuntimeError(
                    "CURRENT_CONTROL control arm is missing from construction variants"
                )
            if not anchor.hard_gate.valid:
                raise RuntimeError("CURRENT_CONTROL control arm failed construction hard gates")
            if anchor.mainboard != control:
                raise RuntimeError(
                    "CURRENT_CONTROL control arm does not match the exact current control"
                )
            control_anchor = anchor
    if PolicyId.CURRENT_CONTROL in policy_ids:
        if control_anchor is None:
            raise RuntimeError(
                "CURRENT_CONTROL policy produced no explicit optimizer search anchor"
            )
        # The exact control is a separate decision-safe search anchor, not a construction
        # finalist. Force its own policy identity when the same deck hash appears elsewhere
        # so Fresh-Rebuild policies remain control-blind and cannot become its search parent.
        by_hash[control_anchor.deck_hash] = control_anchor
    if not by_hash:
        raise RuntimeError("construction priors produced no legal optimizer seeds")
    return engines, tuple(sorted(by_hash.values(), key=lambda row: row.deck_hash))


def run_optimizer_search(
    root: str | Path,
    manifest: OptimizerManifest,
    *,
    run_directory: str | Path,
    policies: Iterable[str] = DEFAULT_POLICIES,
    diversified_starts: int = 2,
    steps_per_start: int = 8,
    finalists_per_policy: int = 4,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    """Execute only the adaptive exploratory lane; confirmatory/holdout remain sealed."""

    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    preflight = verify_optimizer_preflight(root_path, manifest)
    lock = OptimizerLock.acquire(run_path, manifest_hash=manifest.manifest_hash)
    checkpoints = OptimizerCheckpointStore(run_path, manifest_hash=manifest.manifest_hash)
    try:
        previous = checkpoints.read("search")
        if previous is not None:
            return {**previous, "resume_status": "resumed_without_reexecution"}
        lab = WholeDeckDesignLab(root_path)
        orchestrator = WholeDeckCampaignOrchestrator(root_path)
        engines, initial = _initial_variants(
            lab,
            manifest,
            policies=tuple(policies),
            diversified_starts=diversified_starts,
            steps_per_start=steps_per_start,
            finalists_per_policy=finalists_per_policy,
        )
        evaluator = ProjectPairedEvaluator(
            root=str(root_path),
            manifest=manifest,
            orchestrator=orchestrator,
            control_mainboard=current_control_mainboard(root_path),
            context=lab.context,
            workers=workers,
            max_turns=max_turns,
        )
        adaptive = AdaptiveWholeDeckSearch(
            engines,
            evaluator=evaluator,
            seed=manifest.search_seed,
            qd=manifest.qd,
            racing=manifest.racing,
            learning=manifest.learning,
        )
        report = adaptive.run(
            initial_variants=initial,
            generations=manifest.max_generations,
            proposals_per_generation=manifest.proposals_per_generation,
        )
        resolution_policy = load_model_resolution_decision_policy(root_path)
        confirmatory_frontier = build_confirmatory_frontier(
            evaluator.advancement_evidence,
            full_scenarios=evaluator.scenarios,
            model_resolution=resolution_policy,
        )
        payload: dict[str, object] = {
            "schema_version": "1.1.0",
            "runtime_version": OPTIMIZER_RUNTIME_VERSION,
            "manifest_hash": manifest.manifest_hash,
            "evidence_context": "exploratory",
            "evidence_type": "structural_model_estimates",
            "preflight": preflight,
            "search": asdict(report),
            "initial_legal_seed_count": len(initial),
            "confirmatory_advancement_gate_enforced": True,
            "confirmatory_eligible_candidate_ids": list(
                confirmatory_frontier.eligible_candidate_ids
            ),
            "confirmatory_advancement_gate": {
                **confirmatory_frontier.model_dump(mode="json"),
                "frontier_hash": confirmatory_frontier.frontier_hash,
            },
            "confirmatory_partition_opened": False,
            "sealed_holdout_partition_opened": False,
            "official_winner_declared": False,
            "canonical_deck_mutation": False,
        }
        checkpoints.write("search", payload)
        atomic_write_json(run_path / "optimizer-search-report.json", payload)
        return {**payload, "resume_status": "fresh_compute"}
    finally:
        lock.release()
