from __future__ import annotations

from collections import Counter, defaultdict
from statistics import fmean

from commander_lab.models import CardRole

from .search_base import SearchEngineBase


class _FeatureMixin(SearchEngineBase):
    def _feature_summary(self, mainboard: tuple[str, ...]) -> dict[str, object]:
        cards = [self.context.cards[name] for name in mainboard]
        nonlands = [card for card in cards if not card.profile.is_land]
        known = [card for card in cards if card.semantic_known]
        roles: defaultdict[str, float] = defaultdict(float)
        packages: Counter[str] = Counter()
        for card in known:
            for role in card.profile.roles:
                roles[role.value] += card.profile.strength(role)
            packages.update(card.profile.package_ids)
        return {
            "land_count": sum(card.profile.is_land for card in cards),
            "basic_count": sum(card.is_basic for card in cards),
            "average_nonland_mv": (
                fmean(card.profile.mana_value for card in nonlands) if nonlands else 0.0
            ),
            "role_strengths": dict(sorted(roles.items())),
            "package_counts": dict(sorted(packages.items())),
            "semantic_support_fraction": len(known) / len(cards) if cards else 0.0,
            "semantic_unknown_cards": tuple(
                sorted(card.oracle_name for card in cards if not card.semantic_known)
            ),
            "evidence_type": "search_features_with_unknowns_preserved",
        }

    def _synthetic_mana_summary(self, mainboard: tuple[str, ...]) -> dict[str, object]:
        cards = [self.context.cards[name] for name in mainboard]
        lands = [card for card in cards if card.profile.is_land]
        colored: Counter[str] = Counter()
        flexible = 0
        for card in lands:
            colors = {color.value for color in card.profile.produces_colors}
            for color in colors:
                colored[color] += 1
            flexible += len(colors) >= 2
        nonlands = [card for card in cards if not card.profile.is_land]
        return {
            "land_count": len(lands),
            "basic_count": sum(card.is_basic for card in lands),
            "nonbasic_land_count": sum(not card.is_basic for card in lands),
            "colored_sources": dict(sorted(colored.items())),
            "ishai_wu_source_counts": {"W": colored["W"], "U": colored["U"]},
            "flexible_source_count": flexible,
            "definitely_tapped_land_count": 0,
            "conditionally_tapped_land_count": 0,
            "t1_untapped_land_sources": dict(sorted(colored.items())),
            "turn2_source_supported_share": 1.0,
            "ramp_count": sum(CardRole.RAMP in card.profile.roles for card in nonlands),
            "selection_count": sum(CardRole.SELECTION in card.profile.roles for card in nonlands),
            "average_nonland_mv": (
                fmean(card.profile.mana_value for card in nonlands) if nonlands else 0.0
            ),
            "commander_castability_support": min(1.0, (colored["W"] + colored["U"]) / 20.0),
            "evidence_type": "synthetic_fixture_mana_summary",
        }
