from __future__ import annotations

from pathlib import Path

from commander_lab.models import CardRole, StructuralCardProfile
from commander_lab.semantic_features import SEMANTIC_FEATURE_VERSION, graveyard_hate_semantics, produced_self_colors, protection_semantics, removal_semantics, self_mana_semantics, self_token_creation
from commander_lab.storage import sha256_value
from commander_lab.tools.candidates import _inventory_rows

from .enrichment import WholeDeckKnowledgeEnrichment, classify_threat_answers
from .search_context import SearchCard, WholeDeckSearchContext

WHOLE_DECK_LAB_VERSION = "whole-deck-design-lab-0.2.0"


def _sanitize_profile(profile: StructuralCardProfile, *, oracle_text: str, type_line: str, enrichment: WholeDeckKnowledgeEnrichment) -> StructuralCardProfile:
    repeatable_mana, acceleration = self_mana_semantics(oracle_text, type_line)
    roles = set(profile.roles)
    strengths = dict(profile.role_strengths)
    guards = {CardRole.MANA_SOURCE: profile.is_land or repeatable_mana, CardRole.RAMP: acceleration, CardRole.GRAVEYARD_HATE: graveyard_hate_semantics(oracle_text), CardRole.REMOVAL: removal_semantics(oracle_text), CardRole.PROTECTION: protection_semantics(oracle_text), CardRole.TOKEN_SOURCE: self_token_creation(oracle_text)}
    for role, allowed in guards.items():
        if not allowed:
            roles.discard(role)
            strengths.pop(role, None)
    return profile.model_copy(update={"roles": frozenset(roles), "role_strengths": strengths, "produces_colors": produced_self_colors(oracle_text, type_line, oracle_name=profile.oracle_name), "package_ids": enrichment.enriched_package_ids(profile, oracle_text), "notes": ((profile.notes or "") + " Whole-Deck runtime semantics hardened before search use.").strip()})


def enriched_context(root: str | Path) -> tuple[WholeDeckSearchContext, WholeDeckKnowledgeEnrichment, dict[str, tuple[frozenset[str], frozenset[str]]]]:
    project = Path(root).resolve()
    base = WholeDeckSearchContext.from_project(project)
    enrichment = WholeDeckKnowledgeEnrichment.load(project)
    facts = {str(row.get("oracle_name", "")): row for row in _inventory_rows(project)}
    cards: dict[str, SearchCard] = {}
    answers: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for name, card in base.cards.items():
        fact = facts.get(name, {})
        oracle_text = str(fact.get("oracle_text", "") or "")
        type_line = str(fact.get("card_type", "") or "")
        profile = _sanitize_profile(card.profile, oracle_text=oracle_text, type_line=type_line, enrichment=enrichment)
        answers[name] = classify_threat_answers(profile, oracle_text)
        cards[name] = SearchCard(oracle_name=card.oracle_name, profile=profile, available_quantity=card.available_quantity, is_basic=card.is_basic, semantic_evidence=f"{card.semantic_evidence}+runtime_hardened", semantic_known=card.semantic_known, color_identity=card.color_identity, search_utility_override=card.search_utility_override)
    snapshot = sha256_value({"fresh_universe": base.snapshot_hash, "enrichment": enrichment.snapshot_hash, "semantic_feature_version": SEMANTIC_FEATURE_VERSION, "lab_version": WHOLE_DECK_LAB_VERSION})
    return WholeDeckSearchContext(cards=cards, snapshot_hash=snapshot, commander_names=base.commander_names, root=base.root, fresh_universe=base.fresh_universe, mana_analyzer=base.mana_analyzer), enrichment, answers
