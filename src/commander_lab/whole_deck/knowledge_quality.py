from __future__ import annotations

from collections import Counter
from pathlib import Path

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CardRole
from commander_lab.repositories.candidates import inventory_rows

from .search_context import WholeDeckSearchContext

HIGH_RISK_FUNCTIONAL_ROLES = frozenset(
    {
        CardRole.MANA_SOURCE,
        CardRole.RAMP,
        CardRole.DRAW,
        CardRole.SELECTION,
        CardRole.REMOVAL,
        CardRole.COUNTER,
        CardRole.PROTECTION,
        CardRole.WIPE,
        CardRole.RECURSION,
        CardRole.GRAVEYARD_HATE,
        CardRole.TOKEN_SOURCE,
    }
)
THREAT_ANSWER_ROLES = frozenset(
    {
        CardRole.REMOVAL,
        CardRole.COUNTER,
        CardRole.PROTECTION,
        CardRole.WIPE,
        CardRole.GRAVEYARD_HATE,
    }
)


def _has_oracle_text(row: object) -> bool:
    return isinstance(row, dict) and bool(str(row.get("oracle_text", "") or "").strip())


def build_knowledge_quality_report(
    root: str | Path, *, context: WholeDeckSearchContext | None = None
) -> dict[str, object]:
    """Reconcile the current candidate/feature/structural knowledge pipeline.

    The readiness threshold is deliberately not 100% semantic coverage: genuine cards without a
    conservative structural role may remain unknown. Such cards must have no unresolved canonical
    high-risk functional annotation and any finalist containing one is handled by the finalist
    unknown gate.
    """
    project = Path(root).resolve()
    ctx = context or WholeDeckSearchContext.from_project(project)
    universe = ctx.fresh_universe
    if universe is None:
        raise ValueError("knowledge quality requires a project-backed WholeDeckSearchContext")
    annotations = load_canonical_feature_annotations(project)
    candidates = set(ctx.cards)
    facts = set(universe.candidate_facts_by_name)
    annotation_names = set(annotations)

    evidence_counts = Counter(card.semantic_evidence for card in ctx.cards.values())
    known_names = {name for name, card in ctx.cards.items() if card.semantic_known}
    unknown_names = candidates - known_names
    unknown_high_risk_annotations = sorted(
        name
        for name in unknown_names & annotation_names
        if set(annotations[name].mapped_roles) & set(HIGH_RISK_FUNCTIONAL_ROLES)
    )

    raw_rows = inventory_rows(project)
    raw_name_counts = Counter(str(row.get("oracle_name", "")) for row in raw_rows)
    duplicate_inventory_identities = sorted(
        name for name, count in raw_name_counts.items() if name and count > 1 and name in candidates
    )

    vetoes: list[dict[str, object]] = []
    for name in sorted(candidates & annotation_names):
        mapped = set(annotations[name].mapped_roles) & set(HIGH_RISK_FUNCTIONAL_ROLES)
        runtime = set(ctx.cards[name].profile.roles)
        removed = sorted(role.value for role in mapped - runtime)
        if removed:
            vetoes.append(
                {
                    "oracle_name": name,
                    "vetoed_roles": removed,
                    "source_role_tags": sorted(annotations[name].source_role_tags),
                    "status": "QUARANTINED_BY_RUNTIME_SEMANTIC_GATE",
                }
            )

    oracle_count = sum(
        _has_oracle_text(universe.candidate_facts_by_name.get(name)) for name in candidates
    )
    package_count = sum(bool(card.profile.package_ids) for card in ctx.cards.values())
    threat_answer_count = sum(
        bool(set(card.profile.roles) & set(THREAT_ANSWER_ROLES)) for card in ctx.cards.values()
    )
    mana_signal_count = 0
    mana_mapped_count = 0
    for name, card in ctx.cards.items():
        fact = universe.candidate_facts_by_name.get(name, {})
        text = str(fact.get("oracle_text", "") or "").casefold()
        type_line = str(fact.get("card_type", "") or fact.get("type_line", "") or "").casefold()
        signal = "land" in type_line or any(
            marker in text
            for marker in (
                "add {",
                "treasure token",
                "search your library",
                "onto the battlefield",
                " less to cast",
            )
        )
        if signal:
            mana_signal_count += 1
            if set(card.profile.roles) & {CardRole.MANA_SOURCE, CardRole.RAMP}:
                mana_mapped_count += 1

    candidate_count = len(candidates)
    known_count = len(known_names)
    structural_usable_fraction = known_count / candidate_count if candidate_count else 0.0
    minimum_usable_fraction = 0.65
    data_integrity_ready = not (
        annotation_names - candidates
        or candidates - facts
        or duplicate_inventory_identities
        or unknown_high_risk_annotations
    )
    ready = structural_usable_fraction >= minimum_usable_fraction and data_integrity_ready

    return {
        "schema_version": "1.0.0",
        "candidate_universe_count": candidate_count,
        "oracle_coverage_count": oracle_count,
        "oracle_coverage_fraction": oracle_count / candidate_count if candidate_count else 0.0,
        "canonical_overlay_coverage_count": len(annotation_names & candidates),
        "canonical_overlay_coverage_fraction": (
            len(annotation_names & candidates) / candidate_count if candidate_count else 0.0
        ),
        "feature_coverage_count": len(annotation_names & candidates),
        "structurally_usable_count": known_count,
        "structurally_usable_fraction": structural_usable_fraction,
        "semantic_unknown_count": len(unknown_names),
        "semantic_unknown_cards": sorted(unknown_names),
        "semantic_evidence_counts": dict(sorted(evidence_counts.items())),
        "explicit_structural_count": evidence_counts.get("explicit_structural_profile", 0),
        "inferred_structural_count": evidence_counts.get("project_inferred_structural_profile", 0),
        "fact_land_structural_count": evidence_counts.get("fact_land_structural_profile", 0),
        "fact_only_unknown_count": evidence_counts.get("fact_only_semantics_unknown", 0),
        "package_coverage_count": package_count,
        "package_coverage_fraction": package_count / candidate_count if candidate_count else 0.0,
        "mana_signal_count": mana_signal_count,
        "mana_semantic_mapped_count": mana_mapped_count,
        "mana_semantic_coverage_fraction": (
            mana_mapped_count / mana_signal_count if mana_signal_count else 1.0
        ),
        "threat_answer_coverage_count": threat_answer_count,
        "canonical_feature_runtime_veto_count": len(vetoes),
        "canonical_feature_runtime_vetoes": vetoes,
        "unknown_high_risk_annotation_count": len(unknown_high_risk_annotations),
        "unknown_high_risk_annotation_cards": unknown_high_risk_annotations,
        "orphan_feature_annotations": sorted(annotation_names - candidates),
        "feature_rows_without_candidate": sorted(annotation_names - candidates),
        "candidate_without_facts": sorted(candidates - facts),
        "facts_without_candidate": sorted(facts - candidates),
        "duplicate_inventory_identities": duplicate_inventory_identities,
        "readiness_policy": {
            "minimum_structurally_usable_fraction": minimum_usable_fraction,
            "requires_zero_unknown_high_risk_annotations": True,
            "requires_zero_orphan_feature_annotations": True,
            "requires_zero_candidate_without_facts": True,
            "requires_zero_duplicate_candidate_identities": True,
            "remaining_unknowns_require_finalist_review": True,
        },
        "knowledge_pipeline_ready": ready,
        "evidence_boundary": (
            "Functional structural coverage only; no universal power score and no claim that "
            "semantic coverage equals rules-engine fidelity or empirical card strength."
        ),
    }
