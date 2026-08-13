from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from commander_lab.engine.structural.profiles import build_default_profile
from commander_lab.fresh_rebuild import (
    ROGSHAI_COMMANDERS,
    FreshRogShaiUniverse,
    build_fresh_rogshai_profile,
    load_fresh_rogshai_universe,
)
from commander_lab.mana_analysis import ManaAnalyzer
from commander_lab.models import CardRole, DataQuality, StructuralCardProfile, StructuralDeckProfile
from commander_lab.storage import sha256_value
from commander_lab.tools.candidates import BASIC_LANDS, load_candidate_profiles

SEARCH_ENGINE_VERSION = "whole-deck-search-0.1.0"
JESKAI = frozenset({"W", "U", "R"})
INTERACTION_ROLES = frozenset({CardRole.COUNTER, CardRole.REMOVAL, CardRole.PROTECTION})
ENGINE_ROLES = frozenset({CardRole.ENGINE, CardRole.ENABLER, CardRole.PAYOFF})
FINISH_ROLES = frozenset({CardRole.FINISHER, CardRole.PAYOFF, CardRole.COMBAT_PAYOFF})


@dataclass(frozen=True, slots=True)
class SearchCard:
    oracle_name: str
    profile: StructuralCardProfile
    available_quantity: int
    is_basic: bool
    semantic_evidence: str
    semantic_known: bool
    color_identity: frozenset[str]
    search_utility_override: float | None = None


@dataclass(slots=True)
class WholeDeckSearchContext:
    cards: dict[str, SearchCard]
    snapshot_hash: str
    commander_names: tuple[str, ...] = ROGSHAI_COMMANDERS
    root: Path | None = None
    fresh_universe: FreshRogShaiUniverse | None = None
    mana_analyzer: ManaAnalyzer | None = None

    @classmethod
    def from_project(cls, root: str | Path) -> WholeDeckSearchContext:
        project = Path(root).resolve()
        universe = load_fresh_rogshai_universe(project)
        inferred = {
            candidate.card.oracle_name: candidate.card
            for candidate in load_candidate_profiles(project).values()
        }
        explicit = {
            candidate.card.oracle_name: candidate.card for candidate in universe.candidates.values()
        }
        identities = dict(universe.review_required)
        cards: dict[str, SearchCard] = {}
        for name in sorted(universe.candidate_names):
            profile = explicit.get(name)
            semantic_evidence = "explicit_structural_profile"
            semantic_known = True
            if profile is None:
                profile = inferred.get(name)
                semantic_evidence = "project_inferred_structural_profile"
                semantic_known = profile is not None
            identity = identities.get(name)
            if profile is None:
                if identity is None:
                    raise RuntimeError(f"fresh candidate lacks identity facts: {name}")
                baseline = build_default_profile(identity)
                roles = frozenset({CardRole.MANA_SOURCE}) if baseline.is_land else frozenset()
                profile = baseline.model_copy(
                    update={
                        "roles": roles,
                        "role_strengths": {},
                        "mechanic_tags": frozenset(),
                        "color_identity": identity.color_identity,
                        "commander_synergy": 0.0,
                        "floor_value": 0.5,
                        "immediate_impact": 0.5,
                        "turn_cycle_risk": 0.5,
                        "multiplayer_scaling": 0.0,
                        "conditional_strength": (),
                        "package_ids": frozenset(),
                        "source_quality": DataQuality.UNKNOWN,
                        "sources": (),
                        "notes": (
                            "Fact-only Whole-Deck search representation. Semantic roles and card "
                            "strength are intentionally UNKNOWN rather than inferred for this row."
                        ),
                    }
                )
                semantic_evidence = "fact_only_semantics_unknown"
            color_identity = (
                frozenset(color.value for color in identity.color_identity)
                if identity is not None
                else frozenset(color.value for color in profile.color_identity)
            )
            cards[name] = SearchCard(
                oracle_name=name,
                profile=profile,
                available_quantity=int(universe.available_quantities.get(name, 0)),
                is_basic=name in BASIC_LANDS,
                semantic_evidence=semantic_evidence,
                semantic_known=semantic_known,
                color_identity=color_identity,
            )
        return cls(
            cards=cards,
            snapshot_hash=universe.runtime_sha256,
            root=project,
            fresh_universe=universe,
            mana_analyzer=ManaAnalyzer(project),
        )

    @classmethod
    def synthetic(
        cls,
        cards: Sequence[SearchCard],
        *,
        snapshot_hash: str = "synthetic-whole-deck-fixture",
        commander_names: tuple[str, ...] = ROGSHAI_COMMANDERS,
    ) -> WholeDeckSearchContext:
        return cls(
            cards={card.oracle_name: card for card in cards},
            snapshot_hash=sha256_value(snapshot_hash),
            commander_names=commander_names,
        )

    def materialize(self, mainboard: tuple[str, ...], *, label: str) -> StructuralDeckProfile:
        if self.root is not None and self.fresh_universe is not None:
            explicit = self.fresh_universe.candidate_by_name()
            overrides = {
                name: self.cards[name].profile for name in set(mainboard) if name not in explicit
            }
            return build_fresh_rogshai_profile(
                self.root,
                mainboard,
                variant_label=label,
                profile_overrides=overrides,
                universe=self.fresh_universe,
            )
        profiles = [self.cards[name].profile for name in mainboard]
        for commander in self.commander_names:
            profiles.append(self.cards[commander].profile)
        deck_hash = stable_variant_hash(mainboard, self.snapshot_hash, self.commander_names)
        return StructuralDeckProfile(
            deck_id=f"synthetic/whole-deck/{deck_hash[:12]}",
            deck_hash=deck_hash,
            commander_names=self.commander_names,
            cards=tuple(profiles),
            commander_base_costs={
                name: (4.0 if name == self.commander_names[0] else 0.0)
                for name in self.commander_names
            },
            commander_base_power={
                name: (1.0 if name == self.commander_names[0] else 0.0)
                for name in self.commander_names
            },
            commander_strategy="rogshai",
            data_snapshot_hash=self.snapshot_hash,
        )


def stable_variant_hash(
    mainboard: Sequence[str],
    snapshot_hash: str,
    commander_names: Sequence[str] = ROGSHAI_COMMANDERS,
) -> str:
    return sha256_value(
        {
            "mainboard": sorted(Counter(mainboard).items()),
            "commanders": tuple(commander_names),
            "data_snapshot_hash": snapshot_hash,
        }
    )


def current_control_mainboard(root: str | Path) -> tuple[str, ...]:
    payload = json.loads(
        (Path(root) / "data/decks/rogshai_current.json").read_text(encoding="utf-8")
    )
    result: list[str] = []
    for row in payload.get("cards", []):
        if row.get("zone") == "commander":
            continue
        name = str(row["oracle_name"])
        result.extend([name] * int(row.get("quantity", 1)))
    if len(result) != 98:
        raise ValueError(f"current RogShai mainboard expected 98 cards, got {len(result)}")
    return tuple(result)


def _corridor_penalty(value: float, low: float, high: float, weight: float) -> float:
    if low <= value <= high:
        return 0.0
    distance = low - value if value < low else value - high
    return weight * distance / max(1.0, high - low + 1.0)
