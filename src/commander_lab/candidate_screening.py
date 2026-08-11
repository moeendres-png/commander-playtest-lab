from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from commander_lab.models import CandidateProfile, DataQuality, StructuralDeckProfile, VariantSwap
from commander_lab.optimization import build_search_candidate, profile_score
from commander_lab.playstyle import PlaystyleAnalyzer


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
    playstyle_fit: str
    playstyle_confidence: str
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
    playstyle: dict[str, object]
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
        tuple(sorted((color.value, int(count)) for color, count in card.color_requirements.items())),
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


class RogShaiCandidateScreener:
    """Conservative static screen that reduces default simulation work without hiding exploration."""

    def __init__(self, root: str | Path, *, service: Any) -> None:
        self.root = Path(root).resolve()
        self.service = service
        self.playstyle = PlaystyleAnalyzer(self.root)

    def screen_pool(self, deck_id: str = "rogshai/current") -> dict[str, object]:
        if deck_id != "rogshai/current":
            raise ValueError("priority candidate screening is scoped to current RogShai")
        candidates = [
            candidate
            for candidate in self.service.candidates.values()
            if deck_id in candidate.allowed_deck_ids
            and self.service.candidate_inventory.get(candidate.card.oracle_name, 0) > 0
        ]
        by_signature: dict[tuple[object, ...], list[CandidateProfile]] = defaultdict(list)
        for candidate in candidates:
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

        rows: list[CandidateScreenRow] = []
        for candidate in candidates:
            confidence = _confidence(candidate)
            dominated = dominated_by.get(candidate.candidate_id)
            if dominated is not None:
                bucket = "defer_clear_static_dominance"
            elif confidence.startswith("low_") or confidence == "unknown":
                if not candidate.card.package_ids and not _canonical_overlay(candidate):
                    bucket = "defer_low_confidence_default"
                else:
                    bucket = "explore"
            elif candidate.card.package_ids or _canonical_overlay(candidate):
                bucket = "advance"
            else:
                bucket = "explore"
            playstyle = self.playstyle.analyze_card(candidate.card)
            rows.append(
                CandidateScreenRow(
                    candidate_id=candidate.candidate_id,
                    oracle_name=candidate.card.oracle_name,
                    bucket=bucket,
                    confidence=confidence,
                    roles=tuple(sorted(role.value for role in candidate.card.roles)),
                    package_ids=tuple(sorted(candidate.card.package_ids)),
                    mana_value=float(candidate.card.mana_value),
                    clear_static_dominance_by=dominated,
                    playstyle_fit=playstyle.playstyle_fit,
                    playstyle_confidence=playstyle.confidence,
                )
            )

        bucket_order = {
            "advance": 0,
            "explore": 1,
            "defer_low_confidence_default": 2,
            "defer_clear_static_dominance": 3,
        }
        rows.sort(
            key=lambda row: (
                bucket_order[row.bucket],
                row.oracle_name.casefold(),
                row.candidate_id,
            )
        )
        counts = {bucket: 0 for bucket in bucket_order}
        for row in rows:
            counts[row.bucket] += 1
        simulation_ready = sum(row.bucket in {"advance", "explore"} for row in rows)
        return {
            "deck_id": deck_id,
            "physical_legal_candidate_count": len(rows),
            "candidate_pool_after_default_screen": simulation_ready,
            "bucket_counts": counts,
            "rows": [row.as_dict() for row in rows],
            "unusual_candidates_remain_explorable": True,
            "playstyle_is_hard_filter": False,
            "screening_boundary": (
                "Static structural screening only. Deferred candidates remain queryable and may "
                "be explicitly explored; no empirical power claim is made."
            ),
        }

    def screen_swap(
        self,
        *,
        baseline: StructuralDeckProfile,
        remove: str,
        add_candidate_id: str,
    ) -> SwapScreenDecision:
        candidate = self.service.candidates[add_candidate_id]
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
                playstyle=self.playstyle.compare_cards(original, candidate.card),
                automatic_rejection=True,
            )
        if not built.constraint_report.valid:
            return SwapScreenDecision(
                status="invalid_swap",
                bucket="hard_constraint_reject",
                screening_delta=built.screening_score,
                constraint_valid=False,
                rationale=tuple(issue.message for issue in built.constraint_report.issues),
                playstyle=self.playstyle.compare_cards(original, candidate.card),
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
            playstyle=self.playstyle.compare_cards(original, candidate.card),
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
