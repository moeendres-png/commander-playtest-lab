from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from commander_lab.storage import atomic_write_json, sha256_value

from .models import PolicyId
from .optimizer_calibration import calibration_report
from .optimizer_runtime import (
    DEFAULT_POLICIES,
    _initial_variants,
    build_optimizer_manifest_from_project,
    verify_optimizer_preflight,
)
from .optimizer_search import AdaptiveWholeDeckSearch
from .optimizer_v2 import (
    EvidenceContext,
    EvidencePartition,
    OptimizerCheckpointStore,
    OptimizerLock,
    build_semantic_review_queue,
    decision_for_interval,
)
from .optimizer_v2_diagnostics import build_near_frontier_diagnostics
from .optimizer_v2_evaluator import CachedPartitionEvaluator
from .optimizer_v2_release_models import (
    FaceValidityCase,
    FrontierHandoff,
    OptimizerExecutionAudit,
    OptimizerV2Manifest,
)
from .orchestrator import WholeDeckCampaignOrchestrator
from .search import current_control_mainboard
from .search_context import SEMANTIC_UNKNOWN
from .search_models import WholeDeckVariant
from .lab import WholeDeckDesignLab

OPTIMIZER_V2_RELEASE_RUNTIME = "optimizer-v2-release-runtime-1.0.0"


def _calibration_partition(
    orchestrator: WholeDeckCampaignOrchestrator,
    *,
    search_seed: int,
    games: int,
) -> EvidencePartition:
    master_seed = search_seed ^ 0x6CA1_BA7E
    scenarios = orchestrator.scheduler.schedule(games, seed=master_seed)
    return EvidencePartition.create(
        partition_id="calibration",
        evidence_context=EvidenceContext.CALIBRATION,
        master_seed=master_seed,
        scenario_ids=tuple(row.scenario_id for row in scenarios),
        scenario_seeds=tuple(row.seed for row in scenarios),
    )


def build_release_manifest_from_project(
    root: str | Path,
    *,
    run_id: str,
    search_seed: int,
    exploratory_games: int = 256,
    calibration_games: int = 128,
    confirmatory_games: int = 512,
    holdout_games: int = 512,
    policies: Iterable[str] = DEFAULT_POLICIES,
) -> OptimizerV2Manifest:
    base = build_optimizer_manifest_from_project(
        root,
        run_id=run_id,
        search_seed=search_seed,
        exploratory_games=exploratory_games,
        confirmatory_games=confirmatory_games,
        holdout_games=holdout_games,
        policies=policies,
    )
    orchestrator = WholeDeckCampaignOrchestrator(root)
    payload = base.model_dump(mode="json")
    payload["calibration_partition"] = _calibration_partition(
        orchestrator,
        search_seed=search_seed,
        games=calibration_games,
    ).model_dump(mode="json")
    return OptimizerV2Manifest.model_validate(payload)


def load_release_manifest(path: str | Path) -> OptimizerV2Manifest:
    return OptimizerV2Manifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_release_preflight(
    root: str | Path, manifest: OptimizerV2Manifest
) -> dict[str, object]:
    base = verify_optimizer_preflight(root, manifest)
    return {
        **base,
        "release_schema": manifest.schema_version,
        "calibration_partition_identity": manifest.calibration_partition.identity,
        "partition_disjointness": "validated_fail_closed_by_manifest",
    }


def _frontier_hashes(search_report: Any) -> tuple[str, ...]:
    cells = search_report.archive.get("cells", {})
    if not isinstance(cells, dict):
        raise RuntimeError("adaptive search archive cells are malformed")
    hashes: set[str] = set()
    for raw in cells.values():
        if isinstance(raw, list):
            hashes.update(str(value) for value in raw)
    return tuple(sorted(hashes))


def _build_frontier_handoff(
    *,
    manifest: OptimizerV2Manifest,
    search_report: Any,
    evaluator: CachedPartitionEvaluator,
) -> FrontierHandoff:
    elites: list[dict[str, Any]] = []
    for deck_hash in _frontier_hashes(search_report):
        variant = evaluator.variants_by_hash.get(deck_hash)
        evaluation = evaluator.evaluations_by_hash.get(deck_hash)
        if variant is None or evaluation is None:
            raise RuntimeError(f"frontier deck was not retained by evaluator: {deck_hash}")
        if not variant.hard_gate.valid:
            raise RuntimeError("illegal deck reached frontier handoff")
        cached = evaluator.cached_payload_by_hash.get(deck_hash, {})
        elites.append(
            {
                "deck_hash": deck_hash,
                "variant": variant.model_dump(mode="json"),
                "evaluation": evaluation.model_dump(mode="json"),
                "sensitivity": cached.get("sensitivity", {}),
                "provenance": {
                    "manifest_hash": manifest.manifest_hash,
                    "parent_candidate_id": variant.parent_variant_id,
                    "mutation": (
                        variant.mutation.model_dump(mode="json")
                        if variant.mutation is not None
                        else None
                    ),
                    "policy_id": variant.policy_id.value,
                    "policy_version": variant.policy_version,
                    "seed": variant.seed,
                },
            }
        )
    return FrontierHandoff.create(manifest_hash=manifest.manifest_hash, elites=tuple(elites))


def _semantic_queue(
    *, lab: WholeDeckDesignLab, handoff: FrontierHandoff
) -> dict[str, object]:
    unknown = {
        name
        for name, card in lab.context.cards.items()
        if card.effective_semantic_state == SEMANTIC_UNKNOWN
    }
    frontier_counts: Counter[str] = Counter()
    high_counts: Counter[str] = Counter()
    robust_values = [
        float(row["evaluation"]["robust_lower_bound"])
        for row in handoff.elites
        if isinstance(row.get("evaluation"), dict)
    ]
    threshold = median(robust_values) if robust_values else 0.0
    for row in handoff.elites:
        variant = row.get("variant", {})
        evaluation = row.get("evaluation", {})
        if not isinstance(variant, dict) or not isinstance(evaluation, dict):
            continue
        mainboard = variant.get("mainboard", [])
        if not isinstance(mainboard, list):
            continue
        names = [str(name) for name in mainboard if str(name) in unknown]
        frontier_counts.update(names)
        if float(evaluation.get("robust_lower_bound", -999.0)) >= threshold:
            high_counts.update(names)
    total = max(1, len(handoff.elites))
    signals = []
    for name in sorted(unknown):
        occurrences = frontier_counts[name]
        high = high_counts[name]
        differentiator = 1.0 if 0 < occurrences < total else 0.0
        impact = min(1.0, occurrences / total + high / total)
        signals.append(
            {
                "oracle_name": name,
                "frontier_occurrences": occurrences,
                "high_quality_cell_occurrences": high,
                "package_completion_signal": 0.0,
                "differentiator_signal": differentiator,
                "possible_decision_impact": impact,
            }
        )
    queue = build_semantic_review_queue(signals)
    return {
        "schema_version": "1.0.0",
        "source_frontier_hash": handoff.frontier_hash,
        "semantic_unknown_total": len(unknown),
        "queued_total": len(queue),
        "frontier_relevant_unknowns": sum(row.frontier_occurrences > 0 for row in queue),
        "items": [row.model_dump(mode="json") for row in queue],
        "processing_status": "all_current_unknowns_scored_decision_weighted",
        "automatic_semantic_mutation": False,
        "evidence_boundary": "unknown semantics remain fail-closed until separately verified",
    }


def _face_validity_calibration(
    *,
    root: Path,
    run_path: Path,
    manifest: OptimizerV2Manifest,
    lab: WholeDeckDesignLab,
    orchestrator: WholeDeckCampaignOrchestrator,
    engines: dict[str, Any],
    initial: tuple[WholeDeckVariant, ...],
    workers: int,
    max_turns: int,
) -> dict[str, object]:
    evaluator = CachedPartitionEvaluator(
        root=root,
        manifest=manifest,
        orchestrator=orchestrator,
        control_mainboard=current_control_mainboard(root),
        context=lab.context,
        evidence_context=EvidenceContext.CALIBRATION,
        run_directory=run_path,
        workers=workers,
        max_turns=max_turns,
        enable_mulligan_sensitivity=True,
    )
    first_engine = engines[sorted(engines)[0]]
    control_variant = first_engine.evaluate_mainboard(
        current_control_mainboard(root), seed=manifest.search_seed ^ 0xCA11_BA7E
    )
    stress = sorted(
        (row for row in initial if row.deck_hash != control_variant.deck_hash),
        key=lambda row: (row.objective_prior, row.deck_hash),
    )[:2]
    cases: list[tuple[str, str, WholeDeckVariant, bool, bool]] = [
        (
            "real-control-noop",
            "the same legal real control deck should be equivalent to itself",
            control_variant,
            False,
            True,
        )
    ]
    for index, variant in enumerate(stress, start=1):
        cases.append(
            (
                f"legal-low-construction-prior-{index}",
                "a legal low construction-prior stress deck must not be automatically promoted by calibration",
                variant,
                True,
                False,
            )
        )
    budget = min(64, len(manifest.calibration_partition.scenario_ids))
    results: list[FaceValidityCase] = []
    for index, (case_id, hypothesis, variant, not_promote, equivalent) in enumerate(cases):
        evaluation = evaluator(variant, budget, 7000 + index)
        decision = decision_for_interval(
            interval_low=evaluation.interval_low,
            interval_high=evaluation.interval_high,
            policy=manifest.calibration,
        )
        results.append(
            FaceValidityCase(
                case_id=case_id,
                hypothesis=hypothesis,
                candidate_deck_hash=variant.deck_hash,
                decision=decision,
                score=evaluation.score,
                interval_low=evaluation.interval_low,
                interval_high=evaluation.interval_high,
                robust_lower_bound=evaluation.robust_lower_bound,
                legal=variant.hard_gate.valid,
                expected_not_promote=not_promote,
                expected_equivalent=equivalent,
            )
        )
    synthetic = calibration_report()
    synthetic_summary = synthetic.get("summary", {})
    synthetic_pass = bool(
        isinstance(synthetic_summary, dict) and synthetic_summary.get("targets_met") is True
    )
    real_pass = all(
        row.legal
        and (not row.expected_not_promote or row.decision != "PROMOTE")
        and (not row.expected_equivalent or row.decision == "EQUIVALENT")
        for row in results
    )
    return {
        "schema_version": "1.0.0",
        "manifest_hash": manifest.manifest_hash,
        "synthetic": synthetic,
        "legal_real_deck_face_validity": [row.model_dump(mode="json") for row in results],
        "real_face_validity_pass": real_pass,
        "synthetic_targets_pass": synthetic_pass,
        "calibration_acceptance_pass": synthetic_pass and real_pass,
        "calibration_partition_identity": manifest.calibration_partition.identity,
        "evidence_type": "structural_model_estimates",
        "truth_boundary": "legal real-deck stress hypotheses are face-validity checks, not empirical gameplay truth",
        "evaluator_audit": evaluator.audit().model_dump(mode="json"),
    }


def _write_audit(
    *,
    run_path: Path,
    manifest: OptimizerV2Manifest,
    stage: str,
    evidence_context: str,
    evaluator_payload: dict[str, Any],
    outputs: dict[str, Any],
    resumed: int = 0,
    search_proposal_rejections: int = 0,
    confirmatory_opened: bool = False,
    holdout_opened: bool = False,
) -> OptimizerExecutionAudit:
    hashes = {key: sha256_value(value) for key, value in sorted(outputs.items())}
    audit = OptimizerExecutionAudit(
        manifest_hash=manifest.manifest_hash,
        run_id=manifest.run_id,
        stage=stage,
        evidence_context=evidence_context,
        evaluator=evaluator_payload,
        resumed=resumed,
        search_proposal_rejections=search_proposal_rejections,
        outputs=hashes,
        confirmatory_partition_opened=confirmatory_opened,
        sealed_holdout_partition_opened=holdout_opened,
    )
    atomic_write_json(run_path / f"optimizer-execution-audit-{stage}.json", audit.model_dump(mode="json"))
    return audit


def run_release_search(
    root: str | Path,
    manifest: OptimizerV2Manifest,
    *,
    run_directory: str | Path,
    policies: Iterable[str] = DEFAULT_POLICIES,
    diversified_starts: int = 2,
    steps_per_start: int = 8,
    finalists_per_policy: int = 4,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    preflight = verify_release_preflight(root_path, manifest)
    lock = OptimizerLock.acquire(run_path, manifest_hash=manifest.manifest_hash)
    checkpoints = OptimizerCheckpointStore(run_path, manifest_hash=manifest.manifest_hash)
    try:
        previous = checkpoints.read("release-search")
        if previous is not None:
            audit_path = run_path / "optimizer-execution-audit-search.json"
            if audit_path.is_file():
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                if isinstance(audit, dict):
                    audit["resumed"] = int(audit.get("resumed", 0)) + 1
                    atomic_write_json(audit_path, audit)
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
        evaluator = CachedPartitionEvaluator(
            root=root_path,
            manifest=manifest,
            orchestrator=orchestrator,
            control_mainboard=current_control_mainboard(root_path),
            context=lab.context,
            evidence_context=EvidenceContext.EXPLORATORY,
            run_directory=run_path,
            workers=workers,
            max_turns=max_turns,
            enable_mulligan_sensitivity=True,
        )
        adaptive = AdaptiveWholeDeckSearch(
            engines,
            evaluator=evaluator,
            seed=manifest.search_seed,
            qd=manifest.qd,
            racing=manifest.racing,
            learning=manifest.learning,
        )
        search_report = adaptive.run(
            initial_variants=initial,
            generations=manifest.max_generations,
            proposals_per_generation=manifest.proposals_per_generation,
        )
        handoff = _build_frontier_handoff(
            manifest=manifest, search_report=search_report, evaluator=evaluator
        )
        semantic = _semantic_queue(lab=lab, handoff=handoff)
        diagnostics = build_near_frontier_diagnostics(
            root=root_path,
            run_directory=run_path,
            manifest=manifest,
            orchestrator=orchestrator,
            context=lab.context,
            elites=handoff.elites,
            variants_by_hash=evaluator.variants_by_hash,
            evaluations_by_hash=evaluator.evaluations_by_hash,
            cached_payload_by_hash=evaluator.cached_payload_by_hash,
            max_turns=max_turns,
        )
        calibration = _face_validity_calibration(
            root=root_path,
            run_path=run_path,
            manifest=manifest,
            lab=lab,
            orchestrator=orchestrator,
            engines=engines,
            initial=initial,
            workers=workers,
            max_turns=max_turns,
        )
        search_payload = {
            "schema_version": "2.0.0",
            "runtime_version": OPTIMIZER_V2_RELEASE_RUNTIME,
            "manifest_hash": manifest.manifest_hash,
            "preflight": preflight,
            "search": asdict(search_report),
            "initial_legal_seed_count": len(initial),
            "frontier_hash": handoff.frontier_hash,
            "semantic_unknown_total": semantic["semantic_unknown_total"],
            "frontier_relevant_unknowns": semantic["frontier_relevant_unknowns"],
            "diagnostic_candidate_count": diagnostics["selected_candidate_count"],
            "calibration_acceptance_pass": calibration["calibration_acceptance_pass"],
            "confirmatory_partition_opened": False,
            "sealed_holdout_partition_opened": False,
            "official_winner_declared": False,
            "canonical_deck_mutation": False,
        }
        atomic_write_json(run_path / "optimizer-search-report.json", search_payload)
        atomic_write_json(run_path / "frontier-handoff.json", handoff.model_dump(mode="json"))
        atomic_write_json(run_path / "semantic-review-queue.json", semantic)
        atomic_write_json(run_path / "calibration-report.json", calibration)
        rejected = sum(
            max(0, int(row.get("attempts", 0)) - int(row.get("candidate_count", 0)))
            for row in search_report.generations
            if isinstance(row, dict)
        )
        audit = _write_audit(
            run_path=run_path,
            manifest=manifest,
            stage="search",
            evidence_context="exploratory+calibration",
            evaluator_payload={
                "exploratory": evaluator.audit().model_dump(mode="json"),
                "calibration": calibration["evaluator_audit"],
            },
            outputs={
                "search": search_payload,
                "frontier": handoff.model_dump(mode="json"),
                "semantic_queue": semantic,
                "diagnostics": diagnostics,
                "calibration": calibration,
            },
            search_proposal_rejections=rejected,
        )
        payload = {
            **search_payload,
            "execution_audit": audit.model_dump(mode="json"),
            "resume_status": "fresh_compute",
        }
        checkpoints.write("release-search", payload)
        return payload
    finally:
        lock.release()


def _load_handoff(path: str | Path, manifest: OptimizerV2Manifest) -> FrontierHandoff:
    handoff = FrontierHandoff.model_validate_json(Path(path).read_text(encoding="utf-8"))
    if handoff.manifest_hash != manifest.manifest_hash:
        raise RuntimeError("frontier handoff manifest mismatch")
    recreated = FrontierHandoff.create(manifest_hash=handoff.manifest_hash, elites=handoff.elites)
    if recreated.frontier_hash != handoff.frontier_hash:
        raise RuntimeError("frontier handoff hash mismatch")
    return handoff


def run_release_confirmatory(
    root: str | Path,
    manifest: OptimizerV2Manifest,
    *,
    frontier_path: str | Path,
    run_directory: str | Path,
    workers: int = 1,
    max_turns: int = 35,
    budget: int | None = None,
) -> dict[str, object]:
    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    verify_release_preflight(root_path, manifest)
    handoff = _load_handoff(frontier_path, manifest)
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    evaluator = CachedPartitionEvaluator(
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
    )
    games = budget or len(manifest.confirmatory.scenario_ids)
    if games > len(manifest.confirmatory.scenario_ids):
        raise ValueError("confirmatory budget exceeds frozen partition")
    rows: list[dict[str, object]] = []
    for index, elite in enumerate(handoff.elites):
        variant = WholeDeckVariant.model_validate(elite["variant"])
        evaluation = evaluator(variant, games, 20_000 + index)
        decision = decision_for_interval(
            interval_low=evaluation.interval_low,
            interval_high=evaluation.interval_high,
            policy=manifest.calibration,
        )
        rows.append(
            {
                "deck_hash": variant.deck_hash,
                "candidate_id": variant.variant_id,
                "evaluation": evaluation.model_dump(mode="json"),
                "decision": decision,
            }
        )
    report: dict[str, object] = {
        "schema_version": "1.0.0",
        "manifest_hash": manifest.manifest_hash,
        "frontier_hash": handoff.frontier_hash,
        "evidence_context": "confirmatory",
        "evidence_type": "structural_model_estimates",
        "learning_updates": False,
        "construction_updates": False,
        "sealed_holdout_partition_opened": False,
        "rows": rows,
        "evaluator_audit": evaluator.audit().model_dump(mode="json"),
        "canonical_deck_mutation": False,
    }
    atomic_write_json(run_path / "confirmatory-report.json", report)
    _write_audit(
        run_path=run_path,
        manifest=manifest,
        stage="confirmatory",
        evidence_context="confirmatory",
        evaluator_payload=report["evaluator_audit"],
        outputs={"confirmatory": report},
        confirmatory_opened=True,
    )
    return report


def run_release_holdout(
    root: str | Path,
    manifest: OptimizerV2Manifest,
    *,
    confirmatory_path: str | Path,
    run_directory: str | Path,
    authorize_holdout: bool = False,
    workers: int = 1,
    max_turns: int = 35,
    budget: int | None = None,
) -> dict[str, object]:
    if not authorize_holdout:
        raise RuntimeError("sealed holdout requires explicit --authorize-holdout")
    root_path = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    verify_release_preflight(root_path, manifest)
    confirmatory = json.loads(Path(confirmatory_path).read_text(encoding="utf-8"))
    if not isinstance(confirmatory, dict) or confirmatory.get("manifest_hash") != manifest.manifest_hash:
        raise RuntimeError("confirmatory report manifest mismatch")
    promoted = [
        row
        for row in confirmatory.get("rows", [])
        if isinstance(row, dict) and row.get("decision") == "PROMOTE"
    ]
    lab = WholeDeckDesignLab(root_path)
    orchestrator = WholeDeckCampaignOrchestrator(root_path)
    evaluator = CachedPartitionEvaluator(
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
    )
    games = budget or len(manifest.sealed_holdout.scenario_ids)
    if games > len(manifest.sealed_holdout.scenario_ids):
        raise ValueError("holdout budget exceeds frozen partition")
    frontier_path = run_path / "frontier-handoff.json"
    if not frontier_path.is_file():
        raise RuntimeError("holdout requires the manifest-bound frontier handoff")
    handoff = _load_handoff(frontier_path, manifest)
    by_hash = {str(row["deck_hash"]): row for row in handoff.elites}
    rows: list[dict[str, object]] = []
    for index, promoted_row in enumerate(promoted):
        deck_hash = str(promoted_row["deck_hash"])
        elite = by_hash.get(deck_hash)
        if elite is None:
            raise RuntimeError("confirmatory finalist is absent from frozen frontier")
        variant = WholeDeckVariant.model_validate(elite["variant"])
        evaluation = evaluator(variant, games, 30_000 + index)
        rows.append(
            {
                "deck_hash": deck_hash,
                "evaluation": evaluation.model_dump(mode="json"),
                "decision": decision_for_interval(
                    interval_low=evaluation.interval_low,
                    interval_high=evaluation.interval_high,
                    policy=manifest.calibration,
                ),
            }
        )
    report: dict[str, object] = {
        "schema_version": "1.0.0",
        "manifest_hash": manifest.manifest_hash,
        "evidence_context": "holdout",
        "evidence_type": "structural_model_estimates",
        "authorized": True,
        "search_learning_updates": False,
        "construction_updates": False,
        "rows": rows,
        "no_promoted_confirmatory_finalist": not promoted,
        "evaluator_audit": evaluator.audit().model_dump(mode="json"),
        "official_winner_declared": False,
        "canonical_deck_mutation": False,
    }
    atomic_write_json(run_path / "holdout-report.json", report)
    _write_audit(
        run_path=run_path,
        manifest=manifest,
        stage="holdout",
        evidence_context="holdout",
        evaluator_payload=report["evaluator_audit"],
        outputs={"holdout": report},
        confirmatory_opened=True,
        holdout_opened=True,
    )
    return report
