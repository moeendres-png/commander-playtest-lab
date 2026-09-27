from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from .mana import mana_soft_score
from .search_base import SearchEngineBase
from .search_context import _corridor_penalty, stable_variant_hash


def _number(value: object, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return default


def _mapping(value: object) -> Mapping[object, object]:
    return value if isinstance(value, Mapping) else {}


class _MetaScoreMixin(SearchEngineBase):
    def _meta_distance(self, mainboard: tuple[str, ...]) -> dict[str, float | None]:
        if not self.meta_references or self.policy.functional_meta_weight <= 0.0:
            return {}
        from .meta import functional_meta_distance, profile_card_names

        profiles = {
            name: card.profile for name, card in self.context.cards.items() if card.semantic_known
        }
        result: dict[str, float | None] = {}
        for band, reference in self.meta_references.items():
            candidate = profile_card_names(
                mainboard,
                profiles,
                format_band=band,
                source_snapshot_id=self.context.snapshot_hash,
                profile_id=(
                    "candidate:"
                    f"{stable_variant_hash(mainboard, self.context.snapshot_hash, self.context.commander_names)}:"
                    f"{band.value}"
                ),
            )
            distance = functional_meta_distance(candidate, reference, policy=self.policy)
            result[band.value] = distance.policy_weighted_distance
        return dict(sorted(result.items()))

    def _objective(
        self,
        mainboard: tuple[str, ...],
        features: dict[str, object],
        mana: dict[str, object],
        meta: dict[str, float | None],
    ) -> float:
        card_prior = sum(self._utility[name] for name in mainboard) / max(1, len(mainboard))
        penalty = 0.0
        for key, corridor in self.policy.target_corridors.items():
            if key == "land_count":
                value = _number(features.get("land_count"))
            elif key == "average_nonland_mv":
                value = _number(features.get("average_nonland_mv"))
            elif key.startswith("role."):
                support = _number(features.get("semantic_support_fraction"))
                if support < 0.35:
                    continue
                role_strengths = _mapping(features.get("role_strengths"))
                value = _number(role_strengths.get(key.split(".", 1)[1]))
                penalty += (
                    _corridor_penalty(
                        value,
                        corridor.preferred_minimum,
                        corridor.preferred_maximum,
                        corridor.weight,
                    )
                    * support
                )
                continue
            else:
                continue
            penalty += _corridor_penalty(
                value,
                corridor.preferred_minimum,
                corridor.preferred_maximum,
                corridor.weight,
            )
        package_counts = Counter(
            {
                str(key): int(_number(value))
                for key, value in _mapping(features.get("package_counts")).items()
            }
        )
        package_bonus = (
            sum((count - 1) ** 2 for count in package_counts.values() if count >= 2) * 0.01
        )
        mana_score = mana_soft_score(mana, self.mana_policy)
        meta_penalty = sum(value for value in meta.values() if value is not None)
        return card_prior + package_bonus + mana_score - penalty - meta_penalty
