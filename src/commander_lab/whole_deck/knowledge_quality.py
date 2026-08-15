from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CardRole
from commander_lab.repositories.candidates import inventory_rows
from commander_lab.semantic_features import rules_text, structural_roles_from_oracle

from .oracle_fact_verification import verified_empty_oracle_names
from .search_context import (
    SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE,
    SEMANTIC_STRUCTURALLY_MODELED,
    SEMANTIC_UNKNOWN,
    WholeDeckSearchContext,
)

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
    """Return whether a fact row has non-empty Oracle rules text.

    This is deliberately *not* a fact-completeness predicate: verified vanilla cards can have
    legitimately empty Oracle rules text.
    """
    return isinstance(row, dict) and bool(str(row.get("oracle_text", "") or "").strip())


def _canonical_inventory_facts(root: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    path = root / "data/canonical_import/2026-08-07/inventory.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("cards", []) if isinstance(payload, dict) else []
        records.update(
            {
                str(row.get("oracle_name")): dict(row)
                for row in rows
                if isinstance(row, dict) and row.get("oracle_name")
            }
        )
    # The current K1/K2 contract contains narrowly verified post-snapshot inventory deltas.
    # Merge them only as fact-source fallbacks; this never mutates the canonical inventory.
    contract_path = root / "data/rogshai_mvp/K1_K2_RUNTIME_CONTRACT.json"
    if contract_path.exists():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        delta = (
            contract.get("current_drive_inventory_delta", []) if isinstance(contract, dict) else []
        )
        for row in delta:
            if isinstance(row, dict) and row.get("oracle_name"):
                records.setdefault(str(row["oracle_name"]), dict(row))
    return records


def _fact_record_complete(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    required_present = (
        bool(str(row.get("oracle_name", "") or "").strip()),
        isinstance(row.get("mana_value"), (int, float))
        and not isinstance(row.get("mana_value"), bool),
        bool(str(row.get("card_type", "") or row.get("type_line", "") or "").strip()),
        "color_identity" in row,
        "oracle_text" in row,
        str(row.get("commander_legality", row.get("commander_legal", "")) or "").casefold()
        in {"legal", "banned", "unknown", "true", "false"},
    )
    return all(required_present)


def classify_semantic_unknown_cause(fact: object) -> str:
    """Classify why a genuinely unknown candidate lacks a conservative structural role.

    Verified no-rules-text cards are separated before this taxonomy. This function therefore
    describes unresolved semantic uncertainty only and never assigns gameplay strength.
    """
    if not isinstance(fact, dict):
        return "oracle_facts_missing"
    oracle_text = str(fact.get("oracle_text", "") or "").strip()
    type_line = str(fact.get("card_type", "") or fact.get("type_line", "") or "")
    if not oracle_text:
        return "oracle_facts_missing"
    if structural_roles_from_oracle(oracle_text, type_line):
        return "parser_or_projection_gap"
    text = rules_text(oracle_text)
    if any(
        marker in text
        for marker in (
            "each opponent",
            "whenever an opponent",
            "each player's",
            "each player",
            "opponent's upkeep",
            "opponents' upkeep",
        )
    ):
        return "unsupported_opponent_or_table_scaling_mechanic"
    if any(
        marker in text
        for marker in (
            "can't cast",
            "can't attack",
            "can't block",
            "can't be cast",
            "cannot cast",
            "unless that player",
            "instead",
            "doesn't untap",
            "does not untap",
        )
    ):
        return "unsupported_static_tax_or_replacement_effect"
    if any(marker in text for marker in ("equipped creature", "enchanted creature", "equip ")):
        return "unsupported_aura_or_equipment_modifier"
    if any(
        marker in text
        for marker in (
            "attacks",
            "attacking",
            "blocks",
            "blocking",
            "combat damage",
            "gets +",
            "gets -",
        )
    ):
        return "unsupported_combat_or_stat_modifier"
    if any(
        marker in text
        for marker in (
            "gain control",
            "tap target",
            "untap target",
            "copy target",
            "copy that spell",
        )
    ):
        return "unsupported_control_tap_or_copy_effect"
    return "ambiguous_or_no_safe_structural_role"


def build_knowledge_quality_report(
    root: str | Path, *, context: WholeDeckSearchContext | None = None
) -> dict[str, object]:
    """Reconcile current card facts, semantic states and structural search coverage.

    `semantic_known` continues to mean that a usable structural profile exists. Separately, the
    report distinguishes verified no-functional-rules-text cards from genuinely unresolved
    semantic unknowns. No role, strength or multiplayer value is fabricated for either group.
    """
    project = Path(root).resolve()
    ctx = context or WholeDeckSearchContext.from_project(project)
    universe = ctx.fresh_universe
    if universe is None:
        raise ValueError("knowledge quality requires a project-backed WholeDeckSearchContext")
    annotations = load_canonical_feature_annotations(project)
    canonical_facts = _canonical_inventory_facts(project)
    candidates = set(ctx.cards)
    facts = set(universe.candidate_facts_by_name)
    annotation_names = set(annotations)

    verified_empty = set(verified_empty_oracle_names(project, universe.candidate_facts_by_name))
    evidence_counts = Counter(card.semantic_evidence for card in ctx.cards.values())
    state_counts = Counter(card.effective_semantic_state for card in ctx.cards.values())
    structurally_known_names = {name for name, card in ctx.cards.items() if card.semantic_known}
    known_no_functional_names = {
        name
        for name, card in ctx.cards.items()
        if card.effective_semantic_state == SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE
    }
    semantic_unknown_names = {
        name
        for name, card in ctx.cards.items()
        if card.effective_semantic_state == SEMANTIC_UNKNOWN
    }
    structurally_unmodeled_names = candidates - structurally_known_names

    if structurally_known_names | structurally_unmodeled_names != candidates:
        raise RuntimeError("structural coverage partition does not span candidate universe")
    if known_no_functional_names | semantic_unknown_names != structurally_unmodeled_names:
        raise RuntimeError("unmodeled semantic-state partition does not match structural coverage")
    if known_no_functional_names & semantic_unknown_names:
        raise RuntimeError("known-no-functional and semantic-unknown states overlap")
    if known_no_functional_names != verified_empty - structurally_known_names:
        raise RuntimeError("verified-empty Oracle facts disagree with search semantic states")
    if any(
        card.semantic_known == (card.effective_semantic_state == SEMANTIC_STRUCTURALLY_MODELED)
        is False
        for card in ctx.cards.values()
    ):
        raise RuntimeError("semantic_known disagrees with explicit semantic state")

    unknown_causes = {
        name: classify_semantic_unknown_cause(universe.candidate_facts_by_name.get(name))
        for name in sorted(semantic_unknown_names)
    }
    unknown_cause_counts = Counter(unknown_causes.values())
    unknown_high_risk_annotations = sorted(
        name
        for name in semantic_unknown_names & annotation_names
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
    complete_fact_cards = sorted(
        name for name in candidates if _fact_record_complete(canonical_facts.get(name))
    )
    truly_missing_fact_cards = sorted(candidates - set(complete_fact_cards))
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
    structurally_known_count = len(structurally_known_names)
    structural_usable_fraction = (
        structurally_known_count / candidate_count if candidate_count else 0.0
    )
    minimum_usable_fraction = 0.65
    data_integrity_ready = not (
        annotation_names - candidates
        or candidates - facts
        or duplicate_inventory_identities
        or unknown_high_risk_annotations
        or truly_missing_fact_cards
    )
    ready = structural_usable_fraction >= minimum_usable_fraction and data_integrity_ready

    return {
        "schema_version": "1.1.0",
        "candidate_universe_count": candidate_count,
        # Backward-compatible rules-text coverage. This intentionally excludes verified vanilla
        # cards whose Oracle rules text is legitimately empty.
        "oracle_coverage_count": oracle_count,
        "oracle_coverage_fraction": oracle_count / candidate_count if candidate_count else 0.0,
        "rules_text_nonempty_count": oracle_count,
        "rules_text_nonempty_fraction": oracle_count / candidate_count if candidate_count else 0.0,
        "verified_empty_rules_text_count": len(verified_empty),
        "verified_empty_rules_text_cards": sorted(verified_empty),
        "candidate_fact_coverage_count": len(complete_fact_cards),
        "candidate_fact_coverage_fraction": (
            len(complete_fact_cards) / candidate_count if candidate_count else 0.0
        ),
        "truly_missing_fact_count": len(truly_missing_fact_cards),
        "truly_missing_fact_cards": truly_missing_fact_cards,
        "oracle_fact_semantics": (
            "Non-empty rules-text coverage is separate from fact completeness. Verified empty "
            "Oracle rules text is valid fact evidence and is checked fail-closed against current "
            "project facts before it can resolve a semantic state."
        ),
        "canonical_overlay_coverage_count": len(annotation_names & candidates),
        "canonical_overlay_coverage_fraction": (
            len(annotation_names & candidates) / candidate_count if candidate_count else 0.0
        ),
        "feature_coverage_count": len(annotation_names & candidates),
        "structurally_usable_count": structurally_known_count,
        "structurally_unmodeled_count": len(structurally_unmodeled_names),
        "structurally_usable_fraction": structural_usable_fraction,
        "known_no_functional_rules_role_count": len(known_no_functional_names),
        "known_no_functional_rules_role_cards": sorted(known_no_functional_names),
        "semantic_resolved_count": structurally_known_count + len(known_no_functional_names),
        "semantic_unknown_count": len(semantic_unknown_names),
        "semantic_unknown_cards": sorted(semantic_unknown_names),
        "semantic_unknown_cause_counts": dict(sorted(unknown_cause_counts.items())),
        "semantic_unknown_causes": unknown_causes,
        "semantic_recoverable_parser_gap_count": unknown_cause_counts.get(
            "parser_or_projection_gap", 0
        ),
        "semantic_state_counts": dict(sorted(state_counts.items())),
        "semantic_evidence_counts": dict(sorted(evidence_counts.items())),
        "explicit_structural_count": evidence_counts.get("explicit_structural_profile", 0),
        "inferred_structural_count": evidence_counts.get("project_inferred_structural_profile", 0),
        "fact_land_structural_count": evidence_counts.get("fact_land_structural_profile", 0),
        "known_no_functional_evidence_count": evidence_counts.get(
            SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE, 0
        ),
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
            "requires_zero_truly_missing_fact_records": True,
            "verified_empty_rules_text_is_fact_complete": True,
            "remaining_unknowns_require_finalist_review": True,
        },
        "knowledge_pipeline_ready": ready,
        "evidence_boundary": (
            "Functional structural coverage only; verified empty Oracle text is a complete factual "
            "state, not a gameplay-strength claim. No universal power score and no claim that "
            "semantic coverage equals rules-engine fidelity or empirical card strength."
        ),
    }
