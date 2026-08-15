from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CardRole
from commander_lab.repositories.candidates import inventory_rows
from commander_lab.semantic_features import rules_text, structural_roles_from_oracle

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
ORACLE_FACT_EXCEPTIONS_PATH = Path("data/cards/oracle_fact_exceptions.json")
ORACLE_TEXT_PRESENT = "oracle_text_present"
ORACLE_TEXT_LEGITIMATELY_EMPTY = "oracle_text_legitimately_empty"
ORACLE_FACT_MISSING = "oracle_fact_record_missing_or_incomplete"
IDENTITY_AMBIGUOUS = "identity_ambiguous"
_VALID_ORACLE_STATUSES = frozenset(
    {
        ORACLE_TEXT_PRESENT,
        ORACLE_TEXT_LEGITIMATELY_EMPTY,
        ORACLE_FACT_MISSING,
        IDENTITY_AMBIGUOUS,
    }
)


def _load_oracle_fact_exceptions(root: Path) -> dict[str, dict[str, object]]:
    path = root / ORACLE_FACT_EXCEPTIONS_PATH
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("oracle fact exception registry records must be a list")
    result: dict[str, dict[str, object]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError("oracle fact exception registry row must be an object")
        name = str(raw.get("oracle_name", "")).strip()
        status = str(raw.get("oracle_text_status", "")).strip()
        if not name or status not in _VALID_ORACLE_STATUSES:
            raise ValueError(f"invalid oracle fact exception row: {raw!r}")
        if name in result:
            raise ValueError(f"duplicate oracle fact exception: {name}")
        result[name] = dict(raw)
    return result


def _effective_fact(
    fact: object, exception: dict[str, object] | None = None
) -> dict[str, object] | None:
    if not isinstance(fact, dict):
        return None
    result = dict(fact)
    if exception:
        result["oracle_text_status"] = exception["oracle_text_status"]
        if "oracle_text" in exception:
            result["oracle_text"] = exception["oracle_text"]
        result["oracle_fact_source"] = exception.get("source")
    return result


def _oracle_text_status(fact: object) -> str:
    if not isinstance(fact, dict):
        return ORACLE_FACT_MISSING
    explicit = str(fact.get("oracle_text_status", "")).strip()
    if explicit in _VALID_ORACLE_STATUSES:
        return explicit
    if bool(str(fact.get("oracle_text", "") or "").strip()):
        return ORACLE_TEXT_PRESENT
    return ORACLE_FACT_MISSING


def _has_oracle_text(row: object) -> bool:
    return _oracle_text_status(row) == ORACLE_TEXT_PRESENT


def _has_complete_core_facts(fact: object) -> bool:
    if not isinstance(fact, dict):
        return False
    status = _oracle_text_status(fact)
    if status not in {ORACLE_TEXT_PRESENT, ORACLE_TEXT_LEGITIMATELY_EMPTY}:
        return False
    name = str(fact.get("oracle_name", "")).strip()
    type_line = str(fact.get("card_type", "") or fact.get("type_line", "")).strip()
    if not name or not type_line or fact.get("mana_value") is None:
        return False
    color_identity = fact.get("color_identity")
    return isinstance(color_identity, (list, tuple, set, frozenset, str))


def classify_semantic_unknown_cause(fact: object) -> str:
    """Classify why a fact-only candidate remains outside conservative structural roles.

    Fact completeness and non-empty rules text are intentionally separate. A verified vanilla
    card can have complete Oracle facts while legitimately having no functional rules role.
    This taxonomy is diagnostic only; it never assigns gameplay strength.
    """
    if not isinstance(fact, dict):
        return "oracle_facts_missing"
    status = _oracle_text_status(fact)
    if status == IDENTITY_AMBIGUOUS:
        return "identity_ambiguous"
    if status == ORACLE_FACT_MISSING:
        return "oracle_facts_missing"
    if status == ORACLE_TEXT_LEGITIMATELY_EMPTY:
        return "known_no_functional_rules_role"
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
    exceptions = _load_oracle_fact_exceptions(project)
    effective_facts = {
        name: _effective_fact(universe.candidate_facts_by_name.get(name), exceptions.get(name))
        for name in candidates
    }

    evidence_counts = Counter(card.semantic_evidence for card in ctx.cards.values())
    known_names = {name for name, card in ctx.cards.items() if card.semantic_known}
    unknown_names = candidates - known_names
    unknown_causes = {
        name: classify_semantic_unknown_cause(effective_facts.get(name))
        for name in sorted(unknown_names)
    }
    unknown_cause_counts = Counter(unknown_causes.values())
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

    status_counts = Counter(_oracle_text_status(effective_facts.get(name)) for name in candidates)
    rules_text_nonempty_count = status_counts[ORACLE_TEXT_PRESENT]
    verified_empty_rules_text_count = status_counts[ORACLE_TEXT_LEGITIMATELY_EMPTY]
    truly_missing_fact_count = status_counts[ORACLE_FACT_MISSING]
    identity_ambiguous_count = status_counts[IDENTITY_AMBIGUOUS]
    candidate_fact_coverage_count = sum(
        _has_complete_core_facts(effective_facts.get(name)) for name in candidates
    )
    exception_without_candidate = sorted(set(exceptions) - candidates)

    package_count = sum(bool(card.profile.package_ids) for card in ctx.cards.values())
    threat_answer_count = sum(
        bool(set(card.profile.roles) & set(THREAT_ANSWER_ROLES)) for card in ctx.cards.values()
    )
    mana_signal_count = 0
    mana_mapped_count = 0
    for name, card in ctx.cards.items():
        fact = effective_facts.get(name) or {}
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
        or truly_missing_fact_count
        or identity_ambiguous_count
        or exception_without_candidate
    )
    ready = structural_usable_fraction >= minimum_usable_fraction and data_integrity_ready

    return {
        "schema_version": "1.1.0",
        "candidate_universe_count": candidate_count,
        "candidate_fact_coverage_count": candidate_fact_coverage_count,
        "candidate_fact_coverage_fraction": (
            candidate_fact_coverage_count / candidate_count if candidate_count else 0.0
        ),
        "rules_text_nonempty_count": rules_text_nonempty_count,
        "verified_empty_rules_text_count": verified_empty_rules_text_count,
        "truly_missing_fact_count": truly_missing_fact_count,
        "identity_ambiguous_count": identity_ambiguous_count,
        "oracle_text_status_counts": dict(sorted(status_counts.items())),
        "oracle_coverage_count": rules_text_nonempty_count,
        "oracle_coverage_fraction": (
            rules_text_nonempty_count / candidate_count if candidate_count else 0.0
        ),
        "canonical_overlay_coverage_count": len(annotation_names & candidates),
        "canonical_overlay_coverage_fraction": (
            len(annotation_names & candidates) / candidate_count if candidate_count else 0.0
        ),
        "feature_coverage_count": len(annotation_names & candidates),
        "structurally_usable_count": known_count,
        "structurally_usable_fraction": structural_usable_fraction,
        "semantic_unknown_count": len(unknown_names),
        "semantic_unknown_cards": sorted(unknown_names),
        "semantic_unknown_cause_counts": dict(sorted(unknown_cause_counts.items())),
        "semantic_unknown_causes": unknown_causes,
        "semantic_recoverable_parser_gap_count": unknown_cause_counts.get(
            "parser_or_projection_gap", 0
        ),
        "known_no_functional_rules_role_count": unknown_cause_counts.get(
            "known_no_functional_rules_role", 0
        ),
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
        "oracle_fact_exception_without_candidate": exception_without_candidate,
        "duplicate_inventory_identities": duplicate_inventory_identities,
        "readiness_policy": {
            "minimum_structurally_usable_fraction": minimum_usable_fraction,
            "requires_zero_unknown_high_risk_annotations": True,
            "requires_zero_orphan_feature_annotations": True,
            "requires_zero_candidate_without_facts": True,
            "requires_zero_duplicate_candidate_identities": True,
            "requires_zero_truly_missing_oracle_fact_records": True,
            "requires_zero_identity_ambiguities": True,
            "remaining_unknowns_require_finalist_review": True,
        },
        "knowledge_pipeline_ready": ready,
        "evidence_boundary": (
            "Core fact completeness is distinct from non-empty rules text and structural semantic "
            "coverage. Functional structural coverage is not a universal power score and does not "
            "claim rules-engine fidelity or empirical card strength."
        ),
    }
