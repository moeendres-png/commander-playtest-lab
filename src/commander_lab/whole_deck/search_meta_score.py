from __future__ import annotations

from collections import Counter

from .mana import mana_soft_score
from .search_context import stable_variant_hash, _corridor_penalty


class _MetaScoreMixin:
    def _meta_distance(self, mainboard: tuple[str, ...]) -> dict[str, float | None]:
        if not self.meta_references or self.policy.functional_meta_weight <= 0.0:
            return {}
        from .meta import functional_meta_distance, profile_card_names

        profiles = {name: card.profile for name, card in self.context.cards.items() if card.semantic_known}
        result: dict[str, float | None] = {}
        for band, reference in self.meta_references.items():
            candidate = profile_card_names(
                mainboard,
                profiles,
                format_band=band,
                source_snapshot_id=self.context.snapshot_hash,
                profile_id=f"candidate:{stable_variant_hash(mainboard, self.context.snapshot_hash, self.context.commander_names)}:{band.value}",
            )
            distance = functional_meta_distance(candidate, reference, policy=self.policy)
            result[band.value] = distance.policy_weighted_distance
        return dict(sorted(result.items()))

    def _objective(self, mainboard: tuple[str, ...], features: dict[str, object], mana: dict[str, object], meta: dict[str, float | None]) -> float:
        card_prior = sum(self._utility[name] for name in mainboard) / max(1, len(mainboard))
        penalty = 0.0
        for key, corridor in self.policy.target_corridors.items():
            if key == "land_count":
                value = float(features["land_count"])
            elif key == "average_nonland_mv":
                value = float(features["average_nonland_mv"])
            elif key.startswith("role."):
                support = float(features.get("semantic_support_fraction", 0.0))
                if support < 0.35:
                    continue
                value = float(dict(features.get("role_strengths", {})).get(key.split(".", 1)[1], 0.0))
                penalty += _corridor_penalty(value, corridor.preferred_minimum, corridor.preferred_maximum, corridor.weight) * support
                continue
            else:
                continue
            penalty += _corridor_penalty(value, corridor.preferred_minimum, corridor.preferred_maximum, corridor.weight)
        package_counts = Counter({str(k): int(v) for k, v in dict(features.get("package_counts", {})).items()})
        package_bonus = sum((count - 1) ** 2 for count in package_counts.values() if count >= 2) * 0.01
        mana_score = mana_soft_score(mana, self.mana_policy)
        meta_penalty = sum(value for value in meta.values() if value is not None)
        return card_prior + package_bonus + mana_score - penalty - meta_penalty
