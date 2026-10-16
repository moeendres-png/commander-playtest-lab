from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import fsum
from typing import Any

from commander_lab.models import CandidateProfile, StructuralDeckProfile
from commander_lab.optimization import profile_score

_CRITICAL_ROLES = frozenset(
    {"graveyard_hate", "removal", "counter", "protection", "wipe", "recursion", "rebuild"}
)


@dataclass(frozen=True, slots=True)
class CutHypothesis:
    oracle_name: str
    lanes: tuple[str, ...]
    roles: tuple[str, ...]
    unique_roles: tuple[str, ...]
    package_ids: tuple[str, ...]
    singleton_package_ids: tuple[str, ...]
    mana_value: float
    commander_synergy: float
    redundancy_units: int
    structural_challenge_priority: float
    rationale: tuple[str, ...]
    truth_boundary: str = "cut hypothesis for exploration, not empirical card weakness"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_cut_hypotheses(
    deck: StructuralDeckProfile,
    *,
    protected: set[str] | frozenset[str] = frozenset(),
    max_hypotheses: int = 32,
) -> list[CutHypothesis]:
    """Build a diverse structural cut challenge set without treating a scalar score as truth."""
    if max_hypotheses < 1:
        raise ValueError("max_hypotheses must be positive")
    role_counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()
    for card in deck.cards:
        role_counts.update(role.value for role in card.roles)
        package_counts.update(card.package_ids)

    rows: list[CutHypothesis] = []
    for card in deck.cards:
        if (
            card.oracle_name in deck.commander_names
            or card.is_land
            or card.oracle_name in protected
        ):
            continue
        roles = tuple(sorted(role.value for role in card.roles))
        unique_roles = tuple(sorted(role for role in roles if role_counts[role] <= 1))
        packages = tuple(sorted(card.package_ids))
        singleton_packages = tuple(sorted(p for p in packages if package_counts[p] <= 1))
        redundancy_units = sum(max(0, role_counts[role] - 1) for role in roles)
        lanes = {"functional_replacement"}
        rationale: list[str] = ["eligible non-land, non-commander, non-protected slot"]
        if redundancy_units:
            lanes.add("role_redundancy")
            rationale.append(f"role redundancy units={redundancy_units}")
        if card.mana_value >= 4.0:
            lanes.add("curve_mana_pressure")
            rationale.append(f"mana value {card.mana_value:.1f} permits a curve-pressure challenge")
        if packages:
            lanes.add("package_axis_challenge")
            rationale.append(f"package memberships={','.join(packages)}")
        if card.commander_synergy >= 1.0:
            lanes.add("commander_dependence_challenge")
            rationale.append(
                "high modeled commander synergy merits an independence challenge, not a weakness claim"
            )
        unique_critical = sum(role in _CRITICAL_ROLES for role in unique_roles)
        priority = (
            -profile_score(card)
            + 0.16 * redundancy_units
            + 0.08 * max(0.0, card.mana_value - 3.0)
            - 1.6 * unique_critical
            - 0.85 * len(singleton_packages)
            - 0.35 * len(unique_roles)
        )
        if unique_roles:
            rationale.append(f"unique roles protected by penalty={','.join(unique_roles)}")
        if singleton_packages:
            rationale.append(
                "singleton package memberships protected by penalty=" + ",".join(singleton_packages)
            )
        rows.append(
            CutHypothesis(
                oracle_name=card.oracle_name,
                lanes=tuple(sorted(lanes)),
                roles=roles,
                unique_roles=unique_roles,
                package_ids=packages,
                singleton_package_ids=singleton_packages,
                mana_value=float(card.mana_value),
                commander_synergy=float(card.commander_synergy),
                redundancy_units=redundancy_units,
                structural_challenge_priority=priority,
                rationale=tuple(rationale),
            )
        )

    rows.sort(key=lambda row: (-row.structural_challenge_priority, row.oracle_name.casefold()))
    by_lane: dict[str, list[CutHypothesis]] = defaultdict(list)
    for row in rows:
        for lane in row.lanes:
            by_lane[lane].append(row)
    selected: list[CutHypothesis] = []
    seen: set[str] = set()
    lane_order = (
        "role_redundancy",
        "curve_mana_pressure",
        "package_axis_challenge",
        "commander_dependence_challenge",
        "functional_replacement",
    )
    depth = 0
    while len(selected) < max_hypotheses:
        added = False
        for lane in lane_order:
            group = by_lane.get(lane, [])
            if depth >= len(group):
                continue
            row = group[depth]
            if row.oracle_name in seen:
                continue
            selected.append(row)
            seen.add(row.oracle_name)
            added = True
            if len(selected) >= max_hypotheses:
                break
        if not added and all(depth >= len(by_lane.get(lane, [])) for lane in lane_order):
            break
        depth += 1
    for row in rows:
        if len(selected) >= max_hypotheses:
            break
        if row.oracle_name not in seen:
            selected.append(row)
            seen.add(row.oracle_name)
    return selected


def build_static_swap_rows(
    deck: StructuralDeckProfile,
    candidates: Mapping[str, CandidateProfile],
    *,
    protected: set[str] | frozenset[str] = frozenset(),
    max_cut_hypotheses: int = 32,
) -> list[dict[str, Any]]:
    """Generate a broad deterministic pair pool from candidate and diverse cut hypotheses."""
    cuts = build_cut_hypotheses(deck, protected=protected, max_hypotheses=max_cut_hypotheses)
    cut_cards = {card.oracle_name: card for card in deck.cards}
    rows: list[dict[str, Any]] = []
    for cut_hypothesis in cuts:
        cut = cut_cards[cut_hypothesis.oracle_name]
        for candidate_id, candidate in candidates.items():
            if candidate.allowed_deck_ids and deck.deck_id not in candidate.allowed_deck_ids:
                continue
            raw_delta = profile_score(candidate.card) - profile_score(cut)
            overlap = candidate.card.roles & cut.roles
            lost_roles = cut.roles - candidate.card.roles
            critical_loss = sum(role.value in _CRITICAL_ROLES for role in lost_roles)
            compatibility_adjustment = (
                1.5 * len(overlap)
                - 0.5 * len(lost_roles)
                - 3.0 * critical_loss
                - (0.75 if not overlap else 0.0)
            )
            candidate_packages = set(candidate.card.package_ids)
            unmatched_singleton_packages = tuple(
                package
                for package in cut_hypothesis.singleton_package_ids
                if package not in candidate_packages
            )
            unique_role_loss = tuple(
                role
                for role in cut_hypothesis.unique_roles
                if role not in {r.value for r in candidate.card.roles}
            )
            commander_synergy_loss = max(
                0.0, cut.commander_synergy - candidate.card.commander_synergy
            )
            axis_adjustment = (
                -1.25 * len(unmatched_singleton_packages)
                - 1.0 * len(unique_role_loss)
                - 0.25 * commander_synergy_loss
            )
            delta = raw_delta + compatibility_adjustment + axis_adjustment
            rows.append(
                {
                    "remove": cut.oracle_name,
                    "add": candidate.card.oracle_name,
                    "candidate_id": candidate_id,
                    "screening_delta": delta,
                    "raw_profile_delta": raw_delta,
                    "role_compatibility_adjustment": compatibility_adjustment,
                    "package_axis_adjustment": axis_adjustment,
                    "screening_uncertainty_penalty": 0.0,
                    "legacy_screening_uncertainty_penalty": (
                        2.5 if candidate_id.startswith("inventory/") else 0.0
                    ),
                    "semantic_quality": (
                        "keyword_inferred_structural_only"
                        if candidate.card.source_quality.value == "project_inferred"
                        else "curated_structural_profile"
                    ),
                    "role_gain": sorted(role.value for role in candidate.card.roles - cut.roles),
                    "role_loss": sorted(role.value for role in lost_roles),
                    "unique_role_loss": list(unique_role_loss),
                    "unmatched_singleton_packages": list(unmatched_singleton_packages),
                    "mana_value_delta": float(candidate.card.mana_value - cut.mana_value),
                    "commander_synergy_delta": float(
                        candidate.card.commander_synergy - cut.commander_synergy
                    ),
                    "physical_status": candidate.physical_status,
                    "requires_paired_validation": True,
                    "cut_hypothesis": cut_hypothesis.as_dict(),
                }
            )
    rows.sort(
        key=lambda row: (
            float(row["screening_delta"]),
            float(row["cut_hypothesis"]["structural_challenge_priority"]),
            str(row["add"]).casefold(),
        ),
        reverse=True,
    )
    return rows


def select_diverse_swap_frontier(
    rows: list[dict[str, Any]], *, max_pairs: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select capacity-bounded pairs with cut coverage first, then deterministic score fill."""
    if max_pairs < 1:
        raise ValueError("max_pairs must be positive")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["remove"])].append(row)
    for group in grouped.values():
        group.sort(key=lambda row: float(row["screening_delta"]), reverse=True)
    cut_order = sorted(
        grouped,
        key=lambda cut: (
            -float(grouped[cut][0]["cut_hypothesis"]["structural_challenge_priority"]),
            -float(grouped[cut][0]["screening_delta"]),
            cut.casefold(),
        ),
    )
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()
    # Coverage pass: one strongest compatible hypothesis per plausible cut.
    for cut in cut_order:
        if len(selected) >= max_pairs:
            break
        row = grouped[cut][0]
        key = (str(row["remove"]), str(row["candidate_id"]))
        selected.append(row)
        selected_keys.add(key)
    # Quality fill: remaining capacity goes to the strongest deterministic hypotheses globally.
    for row in rows:
        if len(selected) >= max_pairs:
            break
        key = (str(row["remove"]), str(row["candidate_id"]))
        if key in selected_keys:
            continue
        selected.append(row)
        selected_keys.add(key)

    counts = Counter(str(row["remove"]) for row in selected)
    total = len(selected)
    shares = [count / total for count in counts.values()] if total else []
    lanes: Counter[str] = Counter()
    for row in selected:
        lanes.update(str(lane) for lane in row["cut_hypothesis"].get("lanes", ()))
    metrics = {
        "unique_cut_count": len(counts),
        "top_cut_pair_share": max(shares, default=0.0),
        "cut_concentration_metric": fsum(share * share for share in shares),
        "cut_pair_distribution": dict(sorted(counts.items())),
        "cut_lane_distribution": dict(sorted(lanes.items())),
        "pair_count": total,
        "selection_policy": "plausible_cut_coverage_then_deterministic_score_fill",
        "truth_boundary": "frontier composition metric, not empirical card weakness",
    }
    return selected, metrics


__all__ = [
    "CutHypothesis",
    "build_cut_hypotheses",
    "build_static_swap_rows",
    "select_diverse_swap_frontier",
]
