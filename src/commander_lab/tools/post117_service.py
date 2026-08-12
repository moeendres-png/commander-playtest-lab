from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import DataQuality
from commander_lab.optimization import profile_score
from commander_lab.semantic_evidence import semantic_evidence_summary
from .service import CommanderToolService as BaseCommanderToolService


@dataclass(frozen=True)
class SemanticFrontierDecision:
    candidate_id: str
    oracle_name: str
    status: str
    simulation_allowed: bool
    requires_semantic_adjudication: bool
    semantic_evidence: dict[str, object]
    legacy_semantic_provenance: dict[str, object]
    conflict_reasons: tuple[str, ...]
    automatic_rejection: bool = False
    truth_boundary: str = (
        "semantic frontier gate; weak or conflicting semantics defer expensive simulation "
        "but are never negative card evidence"
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def semantic_frontier_decision(
    root: str | Path,
    service: BaseCommanderToolService,
    candidate_id: str,
) -> SemanticFrontierDecision:
    candidate = service.candidates.get(candidate_id)
    if candidate is None:
        raise ValueError(f"unknown current RogShai candidate: {candidate_id}")
    annotations = load_canonical_feature_annotations(Path(root))
    annotation = annotations.get(candidate.card.oracle_name)
    annotation_roles = (
        tuple(sorted(role.value for role in annotation.mapped_roles))
        if annotation is not None
        else ()
    )
    annotation_packages = tuple(sorted(annotation.package_ids)) if annotation is not None else ()
    evidence = semantic_evidence_summary(
        oracle_name=candidate.card.oracle_name,
        profile=candidate,
        annotation_roles=annotation_roles,
        annotation_packages=annotation_packages,
    )
    profile_roles = tuple(sorted(role.value for role in candidate.card.roles))
    profile_packages = tuple(sorted(candidate.card.package_ids))
    conflicts: list[str] = []
    if annotation is not None and candidate.card.source_quality == DataQuality.PROJECT_INFERRED:
        if set(profile_roles) != set(annotation_roles):
            conflicts.append(
                "project-inferred profile roles disagree with canonical derived role projection"
            )
        if set(profile_packages) != set(annotation_packages):
            conflicts.append(
                "project-inferred profile packages disagree with canonical derived package projection"
            )
    if evidence.get("needs_targeted_adjudication") is True:
        conflicts.append("decision-material semantic evidence requires targeted adjudication")
    requires = bool(conflicts)
    sources = tuple(
        source.source_path for source in candidate.card.sources if source.source_path is not None
    )
    legacy_quality = (
        "keyword_inferred_structural_only"
        if candidate.card.source_quality == DataQuality.PROJECT_INFERRED
        else "curated_structural_profile"
    )
    return SemanticFrontierDecision(
        candidate_id=candidate_id,
        oracle_name=candidate.card.oracle_name,
        status=(
            "requires_semantic_adjudication" if requires else "ready_for_paired_simulation"
        ),
        simulation_allowed=not requires,
        requires_semantic_adjudication=requires,
        semantic_evidence=dict(evidence),
        legacy_semantic_provenance={
            "semantic_quality": legacy_quality,
            "source_quality": candidate.card.source_quality.value,
            "roles": profile_roles,
            "package_ids": profile_packages,
            "source_ids": sources,
        },
        conflict_reasons=tuple(dict.fromkeys(conflicts)),
    )


def build_fresh_candidate_cut_frontier(
    root: str | Path,
    service: BaseCommanderToolService,
    *,
    deck_id: str = "rogshai/current",
    limit: int = 50,
) -> dict[str, object]:
    if deck_id != "rogshai/current":
        raise ValueError("post-1.17 fresh frontier is scoped to current RogShai")
    if not 1 <= limit <= 50:
        raise ValueError("frontier limit must be between 1 and 50")
    from commander_lab.candidate_screening import RogShaiCandidateScreener

    screen = RogShaiCandidateScreener(root, service=service).screen_pool(deck_id)
    baseline = service.decks[deck_id]
    protected = set(service.protected_cards.get(deck_id, ()))
    cuts = [
        card
        for card in baseline.cards
        if not card.is_land
        and card.oracle_name not in protected
        and card.oracle_name not in {"Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"}
    ]
    cuts.sort(key=lambda card: (profile_score(card), card.mana_value, card.oracle_name.casefold()))
    cut_window = cuts[:16]
    rows: list[dict[str, object]] = []
    deferred: list[dict[str, object]] = []
    for candidate in service.candidates.values():
        if deck_id not in candidate.allowed_deck_ids:
            continue
        semantic = semantic_frontier_decision(root, service, candidate.candidate_id)
        candidate_roles = {role.value for role in candidate.card.roles}
        candidate_score = profile_score(candidate.card)
        best: tuple[float, str] | None = None
        for cut in cut_window:
            overlap = len(candidate_roles & {role.value for role in cut.roles})
            score = candidate_score - profile_score(cut) + 0.15 * overlap
            pair = (score, cut.oracle_name)
            if best is None or pair > best:
                best = pair
        if best is None:
            continue
        row = {
            "candidate_id": candidate.candidate_id,
            "add": candidate.card.oracle_name,
            "remove": best[1],
            "deterministic_structural_frontier_score": best[0],
            "semantic_frontier": semantic.as_dict(),
            "simulation_allowed": semantic.simulation_allowed,
            "automatic_rejection": False,
        }
        if semantic.simulation_allowed:
            rows.append(row)
        else:
            deferred.append(row)
    rows.sort(
        key=lambda row: (
            -float(row["deterministic_structural_frontier_score"]),
            str(row["add"]).casefold(),
            str(row["remove"]).casefold(),
        )
    )
    deferred.sort(key=lambda row: str(row["add"]).casefold())
    return {
        "deck_id": deck_id,
        "physical_legal_candidate_count": screen["physical_legal_candidate_count"],
        "discoverable_candidate_count": screen["discoverable_candidate_count"],
        "candidate_recall": screen["candidate_recall"],
        "frontier_limit": limit,
        "simulation_ready_pairs": rows[:limit],
        "simulation_ready_pair_count": min(limit, len(rows)),
        "requires_semantic_adjudication": deferred,
        "requires_semantic_adjudication_count": len(deferred),
        "noisy_early_elimination_allowed": False,
        "static_deprioritization_only_before_simulation": True,
        "selection_uses_playstyle": False,
        "truth_boundary": (
            "fresh physical/legal frontier with decision-weighted semantic gate; "
            "not empirical card strength"
        ),
    }


class Post117CommanderToolService(BaseCommanderToolService):
    """1.17.1 safety integration for Issues #54/#55 without widening public tools."""

    SAFE_WORKERS = 1
    HIGH_BUDGET_EXECUTION_SECONDS = 300.0

    def deck_decision_prepare(self, request: Any):  # type: ignore[no-untyped-def]
        response = super().deck_decision_prepare(request)
        if response.status.value == "completed":
            response.result["fresh_candidate_cut_frontier"] = build_fresh_candidate_cut_frontier(
                self.root,
                self,
                deck_id=request.deck_id,
                limit=min(50, request.candidate_limit),
            )
        return response

    def deck_decision_run(self, request: Any):  # type: ignore[no-untyped-def]
        semantic = semantic_frontier_decision(self.root, self, request.add_candidate_id)
        if not semantic.simulation_allowed:
            def work() -> dict[str, Any]:
                return {
                    "status": "requires_semantic_adjudication",
                    "deck_id": request.deck_id,
                    "remove": request.remove,
                    "add_candidate_id": request.add_candidate_id,
                    "semantic_frontier": semantic.as_dict(),
                    "missing_semantic_axes": semantic.conflict_reasons,
                    "automatic_deck_mutation": False,
                }

            return self._invoke(
                "deck_decision_run",
                request,
                work,
                deck_ids=(request.deck_id,),
                seed=request.seed,
                iterations=request.iterations,
            )

        effective_request = request.model_copy(update={"workers": self.SAFE_WORKERS})
        original_limits = self.limits
        high_budget_override = request.iterations >= 1024
        if high_budget_override:
            self.limits = self.limits.model_copy(
                update={
                    "max_simulation_seconds": max(
                        original_limits.max_simulation_seconds,
                        self.HIGH_BUDGET_EXECUTION_SECONDS,
                    )
                }
            )
        try:
            response = super().deck_decision_run(effective_request)
        finally:
            self.limits = original_limits
        response.result["semantic_frontier"] = semantic.as_dict()
        response.result["execution_policy"] = {
            "requested_workers": request.workers,
            "effective_workers": self.SAFE_WORKERS,
            "worker_fallback_applied": request.workers != self.SAFE_WORKERS,
            "safe_worker_policy": self.SAFE_WORKERS,
            "bounded_high_budget_override_applied": high_budget_override,
            "max_simulation_seconds": (
                self.HIGH_BUDGET_EXECUTION_SECONDS
                if high_budget_override
                else original_limits.max_simulation_seconds
            ),
            "execution_metadata_is_deck_evidence": False,
            "seed_and_run_semantics_unchanged": True,
        }
        return response


__all__ = [
    "Post117CommanderToolService",
    "SemanticFrontierDecision",
    "build_fresh_candidate_cut_frontier",
    "semantic_frontier_decision",
]
