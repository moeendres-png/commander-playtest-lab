from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from commander_lab.models import CardRole, StructuralCardProfile
from commander_lab.semantic_features import (
    combat_draw_semantics,
    double_strike_semantics,
    graveyard_hate_semantics,
    protection_semantics,
    removal_targets,
    rules_text,
    self_mana_semantics,
    self_token_creation,
    spellslinger_engine_semantics,
    stack_interaction_semantics,
)
from commander_lab.storage import sha256_value

ENRICHMENT_VERSION = "rogshai-pre-sim-2026-08-14.2"
ENRICHMENT_ROOT = Path("data/enrichment/rogshai_pre_sim")
_BROAD_PRE_STACK_AXES = frozenset(
    {
        "artifact_engine",
        "boardwipe",
        "commander_creature",
        "direct_damage",
        "enchantment_engine",
        "graveyard_recursion",
        "planeswalker_engine",
        "punisher",
        "recursion",
        "resource_denial",
        "single_large_threat",
        "token_engine",
        "value_engine",
        "voltron_equipment_pressure",
    }
)


def _package_members(spec: Mapping[str, object]) -> frozenset[str]:
    names: set[str] = set()
    for key in (
        "core_cards",
        "enablers",
        "payoffs",
        "support_cards",
        "substitutes",
        "shared_cards",
    ):
        value = spec.get(key, ())
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            names.update(str(item) for item in value if str(item).strip())
    return frozenset(names)


def _semantic_package_allowed(
    package_id: str, profile: StructuralCardProfile, oracle_text: str | None
) -> bool:
    _, acceleration = self_mana_semantics(oracle_text, None)
    if package_id == "package:rogshai:commander_protection":
        return protection_semantics(oracle_text)
    if package_id == "package:rogshai:combat_draw":
        return combat_draw_semantics(oracle_text)
    if package_id == "package:rogshai:double_strike":
        return double_strike_semantics(oracle_text)
    if package_id == "package:rogshai:stack_interaction":
        return stack_interaction_semantics(oracle_text)
    if package_id == "package:rogshai:spellslinger_engine":
        return spellslinger_engine_semantics(oracle_text)
    if package_id == "package:rogshai:token_mana_spell_engine":
        return acceleration or (
            self_token_creation(oracle_text) and spellslinger_engine_semantics(oracle_text)
        )
    if package_id == "package:rogshai:low_curve_velocity":
        meaningful = bool(
            set(profile.roles)
            & {
                CardRole.RAMP,
                CardRole.DRAW,
                CardRole.SELECTION,
                CardRole.COUNTER,
                CardRole.REMOVAL,
                CardRole.PROTECTION,
            }
        )
        return not profile.is_land and profile.mana_value <= 2.5 and meaningful
    if package_id == "package:rogshai:recursion_rebuild":
        mechanics = {tag.value for tag in profile.mechanic_tags}
        return CardRole.RECURSION in profile.roles or "rebuild" in mechanics
    return True


def classify_threat_answers(
    profile: StructuralCardProfile, oracle_text: str | None
) -> tuple[frozenset[str], frozenset[str]]:
    """Conservative functional answer modes; not exact target/timing proof."""
    modes: set[str] = set()
    axes: set[str] = set()
    text = rules_text(oracle_text)
    if CardRole.COUNTER in profile.roles and stack_interaction_semantics(oracle_text):
        modes.add("stack_interaction")
        axes.update(_BROAD_PRE_STACK_AXES)
    targets = set(removal_targets(oracle_text))
    if "permanent" in targets:
        targets.update({"artifact", "enchantment", "creature", "planeswalker"})
    if "creature" in targets:
        modes.add("creature_removal")
        axes.update(
            {
                "combat_explosion",
                "commander_creature",
                "direct_damage",
                "punisher",
                "single_large_threat",
                "token_engine",
                "value_engine",
                "voltron_equipment_pressure",
            }
        )
    if "artifact" in targets:
        modes.add("artifact_removal")
        axes.update({"artifact_engine", "resource_denial", "voltron_equipment_pressure"})
    if "enchantment" in targets:
        modes.add("enchantment_removal")
        axes.update({"enchantment_engine", "punisher", "resource_denial", "value_engine"})
    if "planeswalker" in targets:
        modes.add("planeswalker_removal")
        axes.update({"planeswalker_engine", "direct_damage", "value_engine"})
    if CardRole.GRAVEYARD_HATE in profile.roles and graveyard_hate_semantics(oracle_text):
        modes.add("graveyard_interaction")
        axes.update({"graveyard_recursion", "recursion"})
    if CardRole.WIPE in profile.roles:
        modes.add("boardwipe")
        axes.update({"combat_explosion", "go_wide", "token_engine", "wide_board"})
    if CardRole.PROTECTION in profile.roles and protection_semantics(oracle_text):
        modes.add("defensive_protection")
        axes.update(
            {"boardwipe", "combat_explosion", "direct_damage", "punisher", "resource_denial"}
        )
    if "return target" in text and "owner's hand" in text:
        modes.add("bounce")
    if "can't cast spells" in text or "cannot cast spells" in text:
        modes.add("silence_effect")
        axes.update(_BROAD_PRE_STACK_AXES)
    return frozenset(sorted(modes)), frozenset(sorted(axes))


@dataclass(frozen=True, slots=True)
class WholeDeckKnowledgeEnrichment:
    snapshot_hash: str
    package_members: Mapping[str, frozenset[str]]
    broad_threat_axes: frozenset[str]
    mulligan_contract: Mapping[str, object]
    source_hashes: Mapping[str, str]

    @classmethod
    def load(cls, root: str | Path) -> WholeDeckKnowledgeEnrichment:
        project = Path(root).resolve()
        base = project / ENRICHMENT_ROOT
        payloads: dict[str, object] = {}
        source_hashes: dict[str, str] = {}
        for name in ("package_graph.json", "threat_axes.json", "mulligan_contract.json"):
            path = base / name
            if not path.is_file():
                payloads[name] = {}
                source_hashes[name] = "missing"
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            payloads[name] = value
            source_hashes[name] = sha256_value(value)
        package_members: dict[str, frozenset[str]] = {}
        package_graph = payloads["package_graph.json"]
        if isinstance(package_graph, Mapping):
            raw_packages = package_graph.get("packages", {})
            if isinstance(raw_packages, Mapping):
                for package_id, spec in raw_packages.items():
                    if isinstance(spec, Mapping):
                        package_members[str(package_id)] = _package_members(spec)
        broad: set[str] = set()
        threat_axes = payloads["threat_axes.json"]
        if isinstance(threat_axes, Mapping):
            raw_axes = threat_axes.get("broad_axes", ())
            if isinstance(raw_axes, Sequence) and not isinstance(raw_axes, str | bytes):
                for row in raw_axes:
                    if isinstance(row, Mapping) and row.get("axis_id"):
                        broad.add(str(row["axis_id"]))
                    elif isinstance(row, str):
                        broad.add(row)
        mulligan = payloads["mulligan_contract.json"]
        mulligan_contract = dict(mulligan) if isinstance(mulligan, Mapping) else {}
        snapshot = sha256_value(
            {
                "version": ENRICHMENT_VERSION,
                "sources": source_hashes,
                "package_ids": sorted(package_members),
                "threat_axes": sorted(broad),
                "mulligan_current_hash": mulligan_contract.get("current_deck", {}),
            }
        )
        return cls(snapshot, package_members, frozenset(broad), mulligan_contract, source_hashes)

    def enriched_package_ids(
        self, profile: StructuralCardProfile, oracle_text: str | None
    ) -> frozenset[str]:
        packages = {
            package_id
            for package_id in profile.package_ids
            if _semantic_package_allowed(package_id, profile, oracle_text)
        }
        for package_id in (
            "package:rogshai:low_curve_velocity",
            "package:rogshai:recursion_rebuild",
            "package:rogshai:trigger_multiplier",
        ):
            if profile.oracle_name in self.package_members.get(
                package_id, frozenset()
            ) and _semantic_package_allowed(package_id, profile, oracle_text):
                packages.add(package_id)
        return frozenset(sorted(packages))

    def package_coherence_bonus(self, package_counts: Mapping[str, int]) -> float:
        """Bounded package prior; broad density tags never get quadratic reward."""
        config = {
            "package:rogshai:combat_draw": (4, 0.018),
            "package:rogshai:commander_damage": (2, 0.060),
            "package:rogshai:compact_finish": (2, 0.030),
            "package:rogshai:double_strike": (3, 0.025),
            "package:rogshai:jeska_finish": (1, 0.020),
            "package:rogshai:kediss_multi_opponent_damage": (1, 0.020),
            "package:rogshai:spellslinger_engine": (5, 0.022),
            "package:rogshai:token_mana_spell_engine": (5, 0.022),
            "package:rogshai:trigger_multiplier": (2, 0.040),
            "package:rogshai:recursion_rebuild": (4, 0.018),
        }
        total = 0.0
        for package_id, count in package_counts.items():
            if count <= 0 or package_id not in config:
                continue
            cap, weight = config[package_id]
            effective = min(count, cap)
            if effective >= 2 or cap == 1:
                total += effective * weight
        return min(0.40, total)

    def mulligan_proxy(self, features: Mapping[str, object], mana: Mapping[str, object]) -> float:
        """Architecture-only hand-readiness proxy, never a keep-rate or win-rate claim."""

        def number(value: object, default: float = 0.0) -> float:
            return (
                float(value)
                if isinstance(value, int | float) and not isinstance(value, bool)
                else default
            )

        t2 = max(0.0, min(1.0, number(mana.get("turn2_source_supported_share"))))
        commander = max(0.0, min(1.0, number(mana.get("commander_castability_support"))))
        support = max(0.0, min(1.0, number(features.get("semantic_support_fraction"))))
        recovery = min(
            1.0, (number(mana.get("ramp_count")) + number(mana.get("selection_count"))) / 12.0
        )
        land_count = number(mana.get("land_count"))
        land_sanity = (
            1.0 if 30.0 <= land_count <= 39.0 else max(0.0, 1.0 - abs(34.5 - land_count) / 12.0)
        )
        return max(
            0.0,
            min(
                1.0,
                0.40 * t2
                + 0.20 * commander
                + 0.15 * recovery
                + 0.15 * support
                + 0.10 * land_sanity,
            ),
        )
