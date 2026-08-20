from __future__ import annotations

import base64
import json
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

from commander_lab.models import CardRole, StructuralCardProfile
from commander_lab.models.roles import StructuralMechanic
from commander_lab.repositories.candidates import inventory_rows
from commander_lab.semantic_features import (
    SEMANTIC_FEATURE_VERSION,
    produced_self_colors,
    sanitize_structural_profile_semantics,
)
from commander_lab.storage import sha256_value

from .enrichment import WholeDeckKnowledgeEnrichment, classify_threat_answers
from .models import PolicyId
from .search import WholeDeckSearchEngine
from .search_context import (
    SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE,
    SEMANTIC_STRUCTURALLY_MODELED,
    SearchCard,
    WholeDeckSearchContext,
)

WHOLE_DECK_LAB_VERSION = "whole-deck-design-lab-0.4.0"
SEMANTIC_PROJECTION_PATH = Path("data/cards/rogshai_semantic_projection_current.zlib.b64")


def _sanitize_profile(
    profile: StructuralCardProfile,
    *,
    oracle_text: str,
    type_line: str,
    enrichment: WholeDeckKnowledgeEnrichment,
) -> StructuralCardProfile:
    sanitized = sanitize_structural_profile_semantics(
        profile, oracle_text=oracle_text, type_line=type_line
    )
    return sanitized.model_copy(
        update={
            "produces_colors": produced_self_colors(
                oracle_text,
                type_line,
                oracle_name=profile.oracle_name,
            ),
            "package_ids": enrichment.enriched_package_ids(sanitized, oracle_text),
            "notes": (
                (sanitized.notes or "")
                + " Whole-Deck runtime semantics hardened before search use."
            ).strip(),
        }
    )


def _projection_profile(
    profile: StructuralCardProfile,
    raw: dict[str, Any],
) -> StructuralCardProfile:
    role_values = tuple(str(value) for value in raw.get("r", ()))
    roles = frozenset(CardRole(value) for value in role_values)
    strength_overrides = raw.get("s", {})
    if not isinstance(strength_overrides, dict):
        raise RuntimeError(f"semantic projection role strengths malformed: {profile.oracle_name}")
    strengths = {role: 1.0 for role in roles}
    for key, value in strength_overrides.items():
        role = CardRole(str(key))
        if role not in roles:
            raise RuntimeError(
                f"semantic projection strength references absent role for {profile.oracle_name}: {role.value}"
            )
        strengths[role] = float(value)
    mechanics = frozenset(StructuralMechanic(str(value)) for value in raw.get("m", ()))
    package_ids = frozenset(str(value) for value in raw.get("p", ()))
    state = str(raw.get("q", SEMANTIC_STRUCTURALLY_MODELED))
    if state not in {
        SEMANTIC_STRUCTURALLY_MODELED,
        SEMANTIC_KNOWN_NO_FUNCTIONAL_RULES_ROLE,
    }:
        raise RuntimeError(
            f"semantic projection contains unsupported state for {profile.oracle_name}: {state}"
        )
    return profile.model_copy(
        update={
            "roles": roles,
            "role_strengths": strengths,
            "mechanic_tags": mechanics,
            "package_ids": package_ids,
            "commander_synergy": float(raw.get("c", 0.0)),
            "floor_value": float(raw.get("f", 0.5)),
            "immediate_impact": float(raw.get("i", 0.5)),
            "turn_cycle_risk": float(raw.get("t", 0.5)),
            "multiplayer_scaling": float(raw.get("u", 0.0)),
            "notes": (
                (profile.notes or "")
                + " Current full-physical CKB structural semantic projection applied."
            ).strip(),
        }
    )


def _apply_semantic_projection(
    project: Path,
    base: WholeDeckSearchContext,
) -> tuple[WholeDeckSearchContext, str]:
    path = project / SEMANTIC_PROJECTION_PATH
    if not path.is_file():
        raise RuntimeError(f"current RogShai semantic projection is missing: {path}")
    try:
        compressed = base64.b64decode(path.read_text(encoding="ascii"), validate=True)
        payload = json.loads(zlib.decompress(compressed).decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("current RogShai semantic projection cannot be decoded") from exc
    templates = payload.get("t")
    row_index = payload.get("r")
    if not isinstance(templates, list) or not isinstance(row_index, dict):
        raise RuntimeError("current RogShai semantic projection rows are malformed")
    rows: dict[str, dict[str, Any]] = {}
    for name, template_index in row_index.items():
        if not isinstance(template_index, int) or not 0 <= template_index < len(templates):
            raise RuntimeError(f"semantic projection template index is malformed: {name}")
        template = templates[template_index]
        if not isinstance(template, dict):
            raise RuntimeError(f"semantic projection template is malformed: {name}")
        rows[str(name)] = template
    expected = set(base.cards)
    actual = set(rows)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(
            "current RogShai semantic projection does not match the candidate universe: "
            f"missing={missing[:8]} extra={extra[:8]}"
        )
    cards: dict[str, SearchCard] = {}
    for name, card in base.cards.items():
        raw = rows[name]
        state = str(raw.get("q", SEMANTIC_STRUCTURALLY_MODELED))
        profile = _projection_profile(card.profile, raw)
        cards[name] = SearchCard(
            oracle_name=card.oracle_name,
            profile=profile,
            available_quantity=card.available_quantity,
            is_basic=card.is_basic,
            semantic_evidence="full_physical_ckb_structural_projection",
            semantic_known=True,
            color_identity=card.color_identity,
            semantic_state=state,
            search_utility_override=card.search_utility_override,
        )
    projection_hash = sha256_value(payload)
    context = WholeDeckSearchContext(
        cards=cards,
        snapshot_hash=sha256_value(
            {
                "fresh_universe": base.snapshot_hash,
                "semantic_projection": projection_hash,
            }
        ),
        commander_names=base.commander_names,
        root=base.root,
        fresh_universe=base.fresh_universe,
        mana_analyzer=base.mana_analyzer,
    )
    return context, projection_hash


def enriched_context(
    root: str | Path,
) -> tuple[
    WholeDeckSearchContext,
    WholeDeckKnowledgeEnrichment,
    dict[str, tuple[frozenset[str], frozenset[str]]],
]:
    project = Path(root).resolve()
    raw_base = WholeDeckSearchContext.from_project(project)
    base, projection_hash = _apply_semantic_projection(project, raw_base)
    enrichment = WholeDeckKnowledgeEnrichment.load(project)
    facts = {str(row.get("oracle_name", "")): row for row in inventory_rows(project)}
    cards: dict[str, SearchCard] = {}
    answers: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for name, card in base.cards.items():
        fact = facts.get(name, {})
        oracle_text = str(fact.get("oracle_text", "") or "")
        type_line = str(fact.get("card_type", "") or "")
        profile = _sanitize_profile(
            card.profile,
            oracle_text=oracle_text,
            type_line=type_line,
            enrichment=enrichment,
        )
        answers[name] = classify_threat_answers(profile, oracle_text)
        cards[name] = SearchCard(
            oracle_name=card.oracle_name,
            profile=profile,
            available_quantity=card.available_quantity,
            is_basic=card.is_basic,
            semantic_evidence=f"{card.semantic_evidence}+runtime_hardened",
            semantic_known=card.semantic_known,
            color_identity=card.color_identity,
            semantic_state=card.semantic_state,
            search_utility_override=card.search_utility_override,
        )
    snapshot = sha256_value(
        {
            "fresh_universe": base.snapshot_hash,
            "semantic_projection": projection_hash,
            "enrichment": enrichment.snapshot_hash,
            "semantic_feature_version": SEMANTIC_FEATURE_VERSION,
            "lab_version": WHOLE_DECK_LAB_VERSION,
        }
    )
    context = WholeDeckSearchContext(
        cards=cards,
        snapshot_hash=snapshot,
        commander_names=base.commander_names,
        root=base.root,
        fresh_universe=base.fresh_universe,
        mana_analyzer=base.mana_analyzer,
    )
    return context, enrichment, answers


class EnrichedWholeDeckSearchEngine(WholeDeckSearchEngine):
    """Existing Phase-3 engine with hardened search-only knowledge priors."""

    def __init__(
        self,
        *args: Any,
        enrichment: WholeDeckKnowledgeEnrichment,
        answer_map: dict[str, tuple[frozenset[str], frozenset[str]]],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.knowledge_enrichment = enrichment
        self.answer_map = answer_map

    def _feature_summary(self, mainboard: tuple[str, ...]) -> dict[str, object]:
        features = dict(super()._feature_summary(mainboard))
        mode_counts: Counter[str] = Counter()
        axis_counts: Counter[str] = Counter()
        for name in mainboard:
            modes, axes = self.answer_map.get(name, (frozenset(), frozenset()))
            mode_counts.update(modes)
            axis_counts.update(axes)
        broad = self.knowledge_enrichment.broad_threat_axes
        covered = set(axis_counts) & set(broad)
        features.update(
            {
                "answer_mode_counts": dict(sorted(mode_counts.items())),
                "threat_axis_counts": dict(sorted(axis_counts.items())),
                "threat_axis_coverage_fraction": (len(covered) / len(broad) if broad else 0.0),
                "threat_axis_weighting": "presence_only_no_invented_opponent_frequency",
                "runtime_enrichment_snapshot_hash": self.knowledge_enrichment.snapshot_hash,
            }
        )
        return features

    def _objective(
        self,
        mainboard: tuple[str, ...],
        features: dict[str, object],
        mana: dict[str, object],
        meta: dict[str, float | None],
    ) -> float:
        base = super()._objective(mainboard, features, mana, meta)
        raw_packages = features.get("package_counts", {})
        package_counts = (
            {
                str(key): int(value)
                for key, value in raw_packages.items()
                if isinstance(value, int | float)
            }
            if isinstance(raw_packages, dict)
            else {}
        )
        legacy = sum((count - 1) ** 2 for count in package_counts.values() if count >= 2) * 0.01
        score = base - legacy + self.knowledge_enrichment.package_coherence_bonus(package_counts)
        coverage = features.get("threat_axis_coverage_fraction", 0.0)
        coverage_value = float(coverage) if isinstance(coverage, int | float) else 0.0
        if self.policy.policy_id == PolicyId.INTERACTION_HEAVY_LOCAL_META:
            score += min(0.25, max(0.0, coverage_value) * 0.25)
        if self.policy.policy_id == PolicyId.LOW_LAND_HIGH_VELOCITY:
            score += min(
                0.12,
                self.knowledge_enrichment.mulligan_proxy(features, mana) * 0.12,
            )
        return score
