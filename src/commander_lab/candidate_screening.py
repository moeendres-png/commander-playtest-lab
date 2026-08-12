from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CandidateProfile, DataQuality, StructuralDeckProfile, VariantSwap
from commander_lab.optimization import build_search_candidate, profile_score
from commander_lab.tools.candidates import load_candidate_profiles


@dataclass(frozen=True)
class CandidateScreenRow:
    candidate_id: str
    oracle_name: str
    bucket: str
    confidence: str
    roles: tuple[str, ...]
    package_ids: tuple[str, ...]
    mana_value: float
    clear_static_dominance_by: str | None
    playstyle_review_status: str = "deferred_until_post_build_review"
    explorable: bool = True

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SwapScreenDecision:
    status: str
    bucket: str
    screening_delta: float | None
    constraint_valid: bool
    rationale: tuple[str, ...]
    playstyle_review_status: str
    automatic_rejection: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_overlay(candidate: CandidateProfile) -> bool:
    return any(
        source.source_type == "canonical_drive_derived_projection"
        for source in candidate.card.sources
    )


def _confidence(candidate: CandidateProfile) -> str:
    if candidate.card.source_quality in {DataQuality.AUTHORITATIVE, DataQuality.PROJECT_VERIFIED}:
        return "high_project_verified_or_curated"
    if _canonical_overlay(candidate):
        return "medium_canonical_derived"
    if candidate.card.source_quality == DataQuality.PROJECT_INFERRED:
        return "low_local_heuristic_fallback"
    return "unknown"


def _functional_signature(candidate: CandidateProfile) -> tuple[object, ...]:
    card = candidate.card
    return (
        tuple(sorted(role.value for role in card.roles)),
        tuple(sorted(card.package_ids)),
        tuple(
            sorted((color.value, int(count)) for color, count in card.color_requirements.items())
        ),
        card.is_land,
        card.is_permanent,
        card.is_creature,
    )


def _clearly_dominates(left: CandidateProfile, right: CandidateProfile) -> bool:
    if _functional_signature(left) != _functional_signature(right):
        return False
    a = left.card
    b = right.card
    checks = (
        a.mana_value <= b.mana_value,
        profile_score(a) >= profile_score(b),
        a.floor_value >= b.floor_value,
        a.immediate_impact >= b.immediate_impact,
        a.turn_cycle_risk <= b.turn_cycle_risk,
    )
    strict = (
        a.mana_value < b.mana_value
        or profile_score(a) > profile_score(b)
        or a.floor_value > b.floor_value
        or a.immediate_impact > b.immediate_impact
        or a.turn_cycle_risk < b.turn_cycle_risk
    )
    return all(checks) and strict


_PROFILE_NEXT_ROLES = {
    "counter",
    "draw",
    "engine",
    "finisher",
    "land",
    "protection",
    "ramp",
    "rebuild",
    "removal",
    "selection",
    "wipe",
}


def _profile_next(rows: list[dict[str, object]], *, limit: int = 12) -> list[dict[str, object]]:
    candidates: list[tuple[int, str, dict[str, object]]] = []
    for row in rows:
        if row.get("bucket") != "requires_profile_before_model_dependent_recommendation":
            continue
        raw_roles = row.get("roles", ())
        raw_packages = row.get("package_ids", ())
        roles = {str(role) for role in raw_roles} if isinstance(raw_roles, tuple | list) else set()
        packages = (
            {str(package) for package in raw_packages}
            if isinstance(raw_packages, tuple | list)
            else set()
        )
        relevant = roles & _PROFILE_NEXT_ROLES
        if not relevant and not packages:
            continue
        score = len(relevant) * 4 + min(3, len(packages))
        candidates.append((score, str(row["oracle_name"]).casefold(), row))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "oracle_name": row["oracle_name"],
            "candidate_id": row.get("candidate_id"),
            "reason": "touches a current decision-relevant role or package and requires profiling",
            "roles": row.get("roles", ()),
            "package_ids": row.get("package_ids", ()),
            "performance_assumption": None,
            "simulation_allowed_before_profile": False,
        }
        for _, _, row in candidates[:limit]
    ]


class RogShaiCandidateScreener:
    """Conservative static screen that reduces default simulation work without hiding exploration."""

    def __init__(self, root: str | Path, *, service: Any) -> None:
        self.root = Path(root).resolve()
        self.service = service

    def screen_pool(self, deck_id: str = "rogshai/current") -> dict[str, object]:
        if deck_id != "rogshai/current":
            raise ValueError("priority candidate screening is scoped to current RogShai")

        eligibility_path = (
            self.root / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
        )
        payload = json.loads(eligibility_path.read_text(encoding="utf-8"))
        raw_rows = payload.get("eligible_by_deck", {}).get(deck_id)
        if not isinstance(raw_rows, dict):
            raise ValueError("current RogShai candidate eligibility is missing or invalid")

        manifest_path = (
            self.root / "data/collections/current/rogshai_feature_projection/manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_count = int(manifest.get("canonical_candidate_count", -1))

        eligible: dict[str, dict[str, object]] = {}
        excluded: dict[str, int] = {}
        for name, raw_spec in raw_rows.items():
            if not isinstance(raw_spec, dict):
                excluded["invalid_eligibility_record"] = (
                    excluded.get("invalid_eligibility_record", 0) + 1
                )
                continue
            if raw_spec.get("commander_legal") is not True:
                excluded["not_commander_legal"] = excluded.get("not_commander_legal", 0) + 1
                continue
            quantity = int(raw_spec.get("physical_available_quantity", 0))
            if quantity <= 0:
                excluded["not_physically_available"] = (
                    excluded.get("not_physically_available", 0) + 1
                )
                continue
            eligible[str(name)] = dict(raw_spec)

        if expected_count != len(eligible):
            raise ValueError(
                "current RogShai candidate universe disagrees with the canonical feature manifest: "
                f"expected {expected_count}, got {len(eligible)}"
            )

        all_profiles = load_candidate_profiles(self.root)
        modeled_by_name = {
            candidate.card.oracle_name: candidate
            for candidate in all_profiles.values()
            if deck_id in candidate.allowed_deck_ids
        }
        annotations = load_canonical_feature_annotations(self.root)

        modeled_candidates = [modeled_by_name[name] for name in eligible if name in modeled_by_name]
        by_signature: dict[tuple[object, ...], list[CandidateProfile]] = defaultdict(list)
        for candidate in modeled_candidates:
            by_signature[_functional_signature(candidate)].append(candidate)

        dominated_by: dict[str, str] = {}
        for group in by_signature.values():
            for candidate in group:
                dominators = [other for other in group if _clearly_dominates(other, candidate)]
                if dominators:
                    dominators.sort(
                        key=lambda other: (
                            -profile_score(other.card),
                            other.card.mana_value,
                            other.card.oracle_name.casefold(),
                        )
                    )
                    dominated_by[candidate.candidate_id] = dominators[0].candidate_id

        bucket_order = {
            "advance": 0,
            "explore": 1,
            "requires_profile_before_model_dependent_recommendation": 2,
            "defer_low_confidence_default": 3,
            "defer_clear_static_dominance": 4,
        }
        rows: list[dict[str, object]] = []
        high_confidence = 0
        partially_modeled = 0
        structurally_unmodeled = 0
        heuristic_fallback_count = 0
        canonical_feature_coverage = 0

        for name in sorted(eligible, key=str.casefold):
            profile = modeled_by_name.get(name)
            annotation = annotations.get(name)
            if annotation is not None:
                canonical_feature_coverage += 1
            if profile is None:
                structurally_unmodeled += 1
                rows.append(
                    {
                        "candidate_id": None,
                        "oracle_name": name,
                        "bucket": "requires_profile_before_model_dependent_recommendation",
                        "confidence": "insufficient_structural_model_requires_profile",
                        "roles": tuple(sorted(role.value for role in annotation.mapped_roles))
                        if annotation is not None
                        else (),
                        "package_ids": tuple(sorted(annotation.package_ids))
                        if annotation is not None
                        else (),
                        "mana_value": None,
                        "clear_static_dominance_by": None,
                        "playstyle_review_status": "deferred_until_post_build_review",
                        "explorable": True,
                        "model_dependent_recommendation_ready": False,
                    }
                )
                continue

            confidence = _confidence(profile)
            if annotation is not None and (
                confidence.startswith("low_") or confidence == "unknown"
            ):
                confidence = "medium_canonical_derived"
            if confidence == "high_project_verified_or_curated":
                high_confidence += 1
            else:
                partially_modeled += 1
            if profile.card.source_quality == DataQuality.PROJECT_INFERRED:
                heuristic_fallback_count += 1

            dominated = dominated_by.get(profile.candidate_id)
            if dominated is not None:
                bucket = "defer_clear_static_dominance"
            elif confidence.startswith("low_") or confidence == "unknown":
                if not profile.card.package_ids and annotation is None:
                    bucket = "defer_low_confidence_default"
                else:
                    bucket = "explore"
            elif profile.card.package_ids or annotation is not None:
                bucket = "advance"
            else:
                bucket = "explore"

            roles = set(profile.card.roles)
            packages = set(profile.card.package_ids)
            if annotation is not None:
                roles.update(annotation.mapped_roles)
                packages.update(annotation.package_ids)
            rows.append(
                {
                    "candidate_id": profile.candidate_id,
                    "oracle_name": name,
                    "bucket": bucket,
                    "confidence": confidence,
                    "roles": tuple(sorted(role.value for role in roles)),
                    "package_ids": tuple(sorted(packages)),
                    "mana_value": float(profile.card.mana_value),
                    "clear_static_dominance_by": dominated,
                    "playstyle_review_status": "deferred_until_post_build_review",
                    "explorable": True,
                    "model_dependent_recommendation_ready": True,
                }
            )

        rows.sort(
            key=lambda row: (
                bucket_order[str(row["bucket"])],
                str(row["oracle_name"]).casefold(),
                str(row.get("candidate_id") or ""),
            )
        )
        counts = {bucket: 0 for bucket in bucket_order}
        for row in rows:
            counts[str(row["bucket"])] += 1
        simulation_ready = sum(str(row["bucket"]) in {"advance", "explore"} for row in rows)
        discoverable = len(rows)
        profile_next = _profile_next(rows)
        return {
            "deck_id": deck_id,
            "physical_legal_candidate_count": len(eligible),
            "discoverable_candidate_count": discoverable,
            "excluded_candidate_count_by_reason": excluded,
            "candidate_recall": discoverable / len(eligible) if eligible else 1.0,
            "candidate_pool_after_default_screen": simulation_ready,
            "bucket_counts": counts,
            "fully_high_confidence_modeled": high_confidence,
            "partially_modeled": partially_modeled,
            "structurally_unmodeled": structurally_unmodeled,
            "canonical_feature_coverage": canonical_feature_coverage,
            "heuristic_fallback_count": heuristic_fallback_count,
            "rows": rows,
            "progressive_model_coverage": {
                "lane": "explore/profile_next",
                "fixed_budget": len(profile_next),
                "selected": profile_next,
                "selection_uses_playstyle": False,
                "unmodeled_is_negative": False,
                "profiling_required_before_simulation": True,
            },
            "unusual_candidates_remain_explorable": True,
            "unmodeled_candidate_discoverability": True,
            "fresh_rebuild_current_deck_neutrality": True,
            "historical_allocation_neutrality": True,
            "playstyle_policy": "post_build_review_only",
            "playstyle_used_for_screening": False,
            "screening_boundary": (
                "Complete legal/physical discovery is separated from model-dependent screening. "
                "Unmodeled candidates remain discoverable and require explicit profiling before "
                "model-dependent recommendation; no empirical power claim is made."
            ),
        }

    def screen_swap(
        self,
        *,
        baseline: StructuralDeckProfile,
        remove: str,
        add_candidate_id: str,
    ) -> SwapScreenDecision:
        original = next((card for card in baseline.cards if card.oracle_name == remove), None)
        if original is None:
            raise ValueError(f"card not found in baseline: {remove}")
        try:
            built = build_search_candidate(
                baseline,
                (VariantSwap(remove=remove, add_candidate_id=add_candidate_id),),
                self.service.candidates,
                self.service._optimization_constraints(baseline.deck_id),
                inventory=self.service.candidate_inventory,
                verified_physical_names=self.service.verified_candidate_names,
            )
        except (KeyError, ValueError) as exc:
            return SwapScreenDecision(
                status="invalid_swap",
                bucket="hard_constraint_reject",
                screening_delta=None,
                constraint_valid=False,
                rationale=(str(exc),),
                playstyle_review_status="deferred_until_post_build_review",
                automatic_rejection=True,
            )
        if not built.constraint_report.valid:
            return SwapScreenDecision(
                status="invalid_swap",
                bucket="hard_constraint_reject",
                screening_delta=built.screening_score,
                constraint_valid=False,
                rationale=tuple(issue.message for issue in built.constraint_report.issues),
                playstyle_review_status="deferred_until_post_build_review",
                automatic_rejection=True,
            )
        if built.screening_score >= 0.25:
            bucket = "advance"
        elif built.screening_score <= -0.50:
            bucket = "deprioritize_static"
        else:
            bucket = "explore"
        return SwapScreenDecision(
            status="valid",
            bucket=bucket,
            screening_delta=built.screening_score,
            constraint_valid=True,
            rationale=built.rationale,
            playstyle_review_status="deferred_until_post_build_review",
            automatic_rejection=False,
        )

    def benchmark_challenge_set(self) -> dict[str, object]:
        path = self.root / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = [row for row in payload["variants"] if row["deck_id"] == "rogshai/current"]
        evaluated: list[dict[str, object]] = []
        legal_count = 0
        good_count = 0
        good_recovered = 0
        bad_count = 0
        bad_rejected = 0
        for row in rows:
            decision = self.screen_swap(
                baseline=self.service.decks["rogshai/current"],
                remove=str(row["remove"]),
                add_candidate_id=str(row["add_candidate_id"]),
            )
            evaluated.append({**row, "decision": decision.as_dict()})
            if decision.constraint_valid:
                legal_count += 1
            label = str(row["class"])
            if label == "good":
                good_count += 1
                if decision.bucket in {"advance", "explore"}:
                    good_recovered += 1
            elif label == "bad":
                bad_count += 1
                if decision.bucket in {"deprioritize_static", "hard_constraint_reject"}:
                    bad_rejected += 1

        return {
            "challenge_set_id": payload["challenge_set_id"],
            "rogshai_variant_count": len(evaluated),
            "legal_candidate_recall": legal_count / len(evaluated) if evaluated else 1.0,
            "known_good_candidate_recall": good_recovered / good_count if good_count else 1.0,
            "known_bad_candidate_rejection": bad_rejected / bad_count if bad_count else 1.0,
            "evaluated": evaluated,
            "evidence_boundary": payload["evidence_boundary"],
        }


__all__ = ["CandidateScreenRow", "RogShaiCandidateScreener", "SwapScreenDecision"]
