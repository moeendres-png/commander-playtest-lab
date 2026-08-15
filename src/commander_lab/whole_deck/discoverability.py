from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .search_context import (
    SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE,
    SEMANTIC_STRUCTURALLY_MODELED,
    SEMANTIC_UNKNOWN,
    WholeDeckSearchContext,
)
from .search_models import WholeDeckSearchResult

DISCOVERABILITY_REPORT_VERSION = "2026-08-15.2"


def build_discoverability_report(
    context: WholeDeckSearchContext,
    results: Iterable[WholeDeckSearchResult],
) -> dict[str, object]:
    """Measure finite-search exposure and surface every unseen candidate explicitly.

    ``candidate_search_exploration_recall`` is observed finite-budget archive coverage, not a
    claim about card quality. ``candidate_visibility_recall`` counts both observed cards and the
    explicit review queue, preventing unseen candidates from silently disappearing before a
    finalist decision.
    """
    rows = tuple(results)
    eligible = {
        name
        for name, card in context.cards.items()
        if name not in context.commander_names and card.available_quantity > 0
    }
    structurally_modeled = {
        name
        for name in eligible
        if context.cards[name].effective_semantic_state == SEMANTIC_STRUCTURALLY_MODELED
    }
    known_no_functional = {
        name
        for name in eligible
        if context.cards[name].effective_semantic_state == SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE
    }
    unknown = {
        name
        for name in eligible
        if context.cards[name].effective_semantic_state == SEMANTIC_UNKNOWN
    }
    if structurally_modeled | known_no_functional | unknown != eligible:
        raise RuntimeError("discoverability semantic-state partition does not span eligible pool")
    if (
        structurally_modeled & known_no_functional
        or structurally_modeled & unknown
        or known_no_functional & unknown
    ):
        raise RuntimeError("discoverability semantic-state partition overlaps")

    seen: set[str] = set()
    per_policy: list[dict[str, object]] = []
    for result in rows:
        policy_seen: set[str] = set()
        for variant in result.variants:
            policy_seen.update(name for name in variant.mainboard if name in eligible)
        seen.update(policy_seen)
        per_policy.append(
            {
                "policy_id": result.policy_id.value,
                "explored_variant_count": len(result.explored_variant_ids),
                "unique_candidate_cards_seen": len(policy_seen),
                "candidate_exploration_fraction": len(policy_seen) / len(eligible)
                if eligible
                else 1.0,
                "known_no_functional_cards_seen": len(policy_seen & known_no_functional),
                "semantic_unknown_cards_seen": len(policy_seen & unknown),
                "semantic_unknown_exploration_fraction": (
                    len(policy_seen & unknown) / len(unknown) if unknown else 1.0
                ),
            }
        )

    unseen = eligible - seen
    package_members: defaultdict[str, set[str]] = defaultdict(set)
    for name in eligible:
        for package_id in context.cards[name].profile.package_ids:
            package_members[package_id].add(name)
    unseen_packages = sorted(
        package_id for package_id, members in package_members.items() if not (members & seen)
    )
    partial_packages = sorted(
        package_id
        for package_id, members in package_members.items()
        if members & seen and not members <= seen
    )
    fully_seen_packages = sorted(
        package_id for package_id, members in package_members.items() if members and members <= seen
    )

    review_queue = [
        {
            "oracle_name": name,
            "semantic_known": context.cards[name].semantic_known,
            "semantic_state": context.cards[name].effective_semantic_state,
            "semantic_evidence": context.cards[name].semantic_evidence,
            "mana_value": context.cards[name].profile.mana_value,
            "is_land": context.cards[name].profile.is_land,
            "is_basic": context.cards[name].is_basic,
            "color_identity": sorted(context.cards[name].color_identity),
            "available_quantity": context.cards[name].available_quantity,
            "roles": sorted(role.value for role in context.cards[name].profile.roles)
            if context.cards[name].semantic_known
            else [],
            "package_ids": sorted(context.cards[name].profile.package_ids),
            "review_reason": "not_seen_in_finite_whole_deck_search_archive",
            "automatic_negative_evidence": False,
        }
        for name in sorted(unseen)
    ]
    visible = seen | {str(row["oracle_name"]) for row in review_queue}
    return {
        "schema_version": "1.0.0",
        "report_version": DISCOVERABILITY_REPORT_VERSION,
        "search_eligible_candidate_count": len(eligible),
        # Backward-compatible: semantic_known means a structural profile is modeled.
        "semantic_known_eligible_count": len(structurally_modeled),
        "structurally_modeled_eligible_count": len(structurally_modeled),
        "known_no_functional_eligible_count": len(known_no_functional),
        "semantic_unknown_eligible_count": len(unknown),
        "observed_archive_candidate_count": len(seen),
        "candidate_search_exploration_recall": len(seen) / len(eligible) if eligible else 1.0,
        "observed_unknown_candidate_count": len(seen & unknown),
        "semantic_unknown_search_exploration_recall": (
            len(seen & unknown) / len(unknown) if unknown else 1.0
        ),
        "unseen_candidate_count": len(unseen),
        "unseen_semantic_unknown_count": len(unseen & unknown),
        "unseen_known_no_functional_count": len(unseen & known_no_functional),
        "unseen_semantic_known_count": len(unseen & structurally_modeled),
        "discovery_review_queue": review_queue,
        "candidate_visibility_recall": len(visible) / len(eligible) if eligible else 1.0,
        "candidate_discoverability_status": (
            "PASS_FULL_ARCHIVE_COVERAGE"
            if not unseen
            else "PASS_WITH_EXPLICIT_DISCOVERY_REVIEW_QUEUE"
        ),
        "package_universe_count": len(package_members),
        "fully_seen_packages": fully_seen_packages,
        "partially_seen_packages": partial_packages,
        "unseen_packages": unseen_packages,
        "package_discovery_status": (
            "PASS_ALL_PACKAGES_SEEN"
            if not unseen_packages
            else "REVIEW_UNSEEN_PACKAGES_BEFORE_FINALIST_FREEZE"
        ),
        "per_policy": per_policy,
        "evidence_boundary": (
            "Observed archive coverage measures hypothesis-generation exposure under the configured "
            "finite search budget. Unseen does not mean weak; the explicit review queue is not a "
            "positive include prior and must not be treated as simulation evidence."
        ),
    }


def build_forced_inclusion_feasibility_report(
    context: WholeDeckSearchContext,
    candidate_names: Iterable[str],
    *,
    seed: int,
) -> dict[str, object]:
    """Hard-gate probe unseen cards without creating positive/negative performance evidence.

    Each candidate is forced into one deterministic neutral-policy constructive mainboard by
    replacing one card of the same broad land/basic class. The probe answers only whether the
    candidate can remain legally/physically materializable under that policy's hard gates.
    """
    from .models import PolicyId
    from .policies import get_policy
    from .search import WholeDeckSearchEngine
    from .search_models import WholeDeckSearchConfig

    engine = WholeDeckSearchEngine(
        context,
        get_policy(PolicyId.OWNED_POOL_NEUTRAL),
        config=WholeDeckSearchConfig(
            seed=seed,
            diversified_starts=0,
            max_steps_per_start=1,
            finalist_limit=1,
            archive_limit=32,
        ),
    )
    base = engine.constructive_start()
    rows: list[dict[str, object]] = []
    for name in sorted(set(candidate_names)):
        card = context.cards.get(name)
        if card is None or name in context.commander_names or card.available_quantity < 1:
            rows.append(
                {
                    "oracle_name": name,
                    "feasible": False,
                    "issues": ["not_search_eligible"],
                    "automatic_positive_evidence": False,
                    "automatic_negative_evidence": False,
                }
            )
            continue
        if name in base:
            gate = engine._hard_gate(base)
            rows.append(
                {
                    "oracle_name": name,
                    "feasible": gate.valid,
                    "issues": list(gate.issues),
                    "replaced_card": None,
                    "automatic_positive_evidence": False,
                    "automatic_negative_evidence": False,
                }
            )
            continue

        target_is_land = card.profile.is_land
        target_is_basic = card.is_basic

        def same_class(
            other_name: str,
            target_is_land: bool = target_is_land,
            target_is_basic: bool = target_is_basic,
        ) -> bool:
            other = context.cards[other_name]
            if target_is_land != other.profile.is_land:
                return False
            if target_is_land and target_is_basic != other.is_basic:
                return False
            return other_name not in context.commander_names

        removable = [other for other in base if same_class(other)]
        removable.sort(key=lambda other: (engine._utility[other], other))
        if not removable:
            rows.append(
                {
                    "oracle_name": name,
                    "feasible": False,
                    "issues": ["no_same_class_replacement_slot"],
                    "automatic_positive_evidence": False,
                    "automatic_negative_evidence": False,
                }
            )
            continue
        replaced = removable[0]
        proposal = list(base)
        proposal[proposal.index(replaced)] = name
        gate = engine._hard_gate(tuple(proposal))
        rows.append(
            {
                "oracle_name": name,
                "feasible": gate.valid,
                "issues": list(gate.issues),
                "replaced_card": replaced,
                "automatic_positive_evidence": False,
                "automatic_negative_evidence": False,
            }
        )
    feasible = sum(bool(row["feasible"]) for row in rows)
    return {
        "schema_version": "1.0.0",
        "probe_type": "forced_inclusion_hard_gate_feasibility_not_performance",
        "policy_id": PolicyId.OWNED_POOL_NEUTRAL.value,
        "seed": seed,
        "candidate_count": len(rows),
        "feasible_count": feasible,
        "infeasible_count": len(rows) - feasible,
        "rows": rows,
        "evidence_boundary": (
            "A feasible forced-inclusion probe proves only legal/physical hard-gate reachability. "
            "It is neither positive card evidence nor structural performance evidence."
        ),
    }
