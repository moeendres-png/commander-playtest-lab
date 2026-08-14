from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .search_context import WholeDeckSearchContext
from .search_models import WholeDeckSearchResult

DISCOVERABILITY_REPORT_VERSION = "2026-08-14.1"


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
    known = {name for name in eligible if context.cards[name].semantic_known}
    unknown = eligible - known

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
            "semantic_evidence": context.cards[name].semantic_evidence,
            "mana_value": context.cards[name].profile.mana_value,
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
        "semantic_known_eligible_count": len(known),
        "semantic_unknown_eligible_count": len(unknown),
        "observed_archive_candidate_count": len(seen),
        "candidate_search_exploration_recall": len(seen) / len(eligible) if eligible else 1.0,
        "observed_unknown_candidate_count": len(seen & unknown),
        "semantic_unknown_search_exploration_recall": (
            len(seen & unknown) / len(unknown) if unknown else 1.0
        ),
        "unseen_candidate_count": len(unseen),
        "unseen_semantic_unknown_count": len(unseen & unknown),
        "unseen_semantic_known_count": len(unseen & known),
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
