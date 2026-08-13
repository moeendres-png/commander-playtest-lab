from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from commander_lab.models import (
    CardRole,
    FormatBand,
    MetaKnowledgeBaseSnapshot,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import sha256_value

from .models import (
    DeckDesignPolicy,
    FunctionalDimension,
    FunctionalEvidenceQuality,
    FunctionalMetaDistance,
    MetaFunctionalProfile,
)

ROLE_DIMENSIONS: tuple[CardRole, ...] = (
    CardRole.RAMP,
    CardRole.DRAW,
    CardRole.SELECTION,
    CardRole.REMOVAL,
    CardRole.COUNTER,
    CardRole.PROTECTION,
    CardRole.WIPE,
    CardRole.RECURSION,
    CardRole.GRAVEYARD_HATE,
    CardRole.ENGINE,
    CardRole.ENABLER,
    CardRole.PAYOFF,
    CardRole.FINISHER,
    CardRole.COMBAT_PAYOFF,
)


def _quality(profiled: int, fallback: int, total: int) -> FunctionalEvidenceQuality:
    if total <= 0 or profiled + fallback <= 0:
        return FunctionalEvidenceQuality.UNKNOWN
    if fallback and profiled:
        return FunctionalEvidenceQuality.MIXED
    if fallback:
        return FunctionalEvidenceQuality.LOW_EVIDENCE_FALLBACK
    if profiled < total:
        return FunctionalEvidenceQuality.PARTIAL_STRUCTURAL
    return FunctionalEvidenceQuality.STRUCTURAL


def _name_fallback_roles(name: str) -> frozenset[CardRole]:
    lowered = name.casefold()
    roles: set[CardRole] = set()
    if any(key in lowered for key in ("signet", "talisman", "mox", "lotus", "ritual")):
        roles.add(CardRole.RAMP)
    if any(key in lowered for key in ("counter", "force", "flusterstorm", "misstep")):
        roles.add(CardRole.COUNTER)
    if any(key in lowered for key in ("study", "remora", "curiosity", "insight")):
        roles.add(CardRole.DRAW)
    if any(key in lowered for key in ("swords to plowshares", "blast", "vandalblast")):
        roles.add(CardRole.REMOVAL)
    if "silence" in lowered:
        roles.add(CardRole.PROTECTION)
    return frozenset(roles)


def _profile_one_deck(
    cards: Sequence[str],
    profiles: Mapping[str, StructuralCardProfile],
    *,
    allow_name_fallback: bool,
) -> tuple[dict[str, float], Counter[str], int, tuple[str, ...], tuple[str, ...]]:
    total = len(cards)
    role_totals: Counter[str] = Counter()
    package_totals: Counter[str] = Counter()
    known_cards: list[StructuralCardProfile] = []
    missing: list[str] = []
    fallback: list[str] = []
    land_count = 0
    for name in cards:
        profile = profiles.get(name)
        if profile is not None:
            known_cards.append(profile)
            land_count += int(profile.is_land)
            for role in profile.roles:
                role_totals[f"role.{role.value}"] += profile.strength(role)
            package_totals.update(profile.package_ids)
            continue
        missing.append(name)
        if allow_name_fallback:
            roles = _name_fallback_roles(name)
            if roles:
                fallback.append(name)
                for role in roles:
                    role_totals[f"role.{role.value}"] += 1.0

    nonlands = [card for card in known_cards if not card.is_land]
    dims: dict[str, float] = {}
    if total:
        for role in ROLE_DIMENSIONS:
            dims[f"role.{role.value}"] = role_totals[f"role.{role.value}"] * 100.0 / total
    if known_cards:
        dims["land_count"] = land_count * 100.0 / len(known_cards)
        dims["commander_synergy"] = sum(card.commander_synergy for card in known_cards) / len(
            known_cards
        )
        dims["multiplayer_scaling"] = sum(card.multiplayer_scaling for card in known_cards) / len(
            known_cards
        )
        dims["commander_independence"] = (
            sum(
                any(tag.value == "commander_independent" for tag in card.mechanic_tags)
                for card in known_cards
            )
            * 100.0
            / len(known_cards)
        )
        dims["rebuild"] = (
            sum(any(tag.value == "rebuild" for tag in card.mechanic_tags) for card in known_cards)
            * 100.0
            / len(known_cards)
        )
    if nonlands:
        dims["average_nonland_mv"] = sum(card.mana_value for card in nonlands) / len(nonlands)
    return dims, package_totals, len(known_cards), tuple(sorted(set(missing))), tuple(sorted(set(fallback)))


def profile_structural_deck(
    deck: StructuralDeckProfile,
    *,
    format_band: FormatBand,
    source_snapshot_id: str = "candidate",
) -> MetaFunctionalProfile:
    profiles = {card.oracle_name: card for card in deck.cards}
    names = tuple(card.oracle_name for card in deck.cards)
    return profile_card_names(
        names,
        profiles,
        format_band=format_band,
        source_snapshot_id=source_snapshot_id,
        profile_id=f"deck:{deck.deck_hash}",
    )


def profile_card_names(
    cards: Sequence[str],
    profiles: Mapping[str, StructuralCardProfile],
    *,
    format_band: FormatBand,
    source_snapshot_id: str,
    profile_id: str,
    allow_name_fallback: bool = False,
) -> MetaFunctionalProfile:
    dims, packages, profiled, missing, fallback = _profile_one_deck(
        cards, profiles, allow_name_fallback=allow_name_fallback
    )
    total = len(cards)
    support = profiled / total if total else 0.0
    quality = _quality(profiled, len(fallback), total)
    dimension_rows = {
        key: FunctionalDimension(value=value, support_fraction=support, evidence_quality=quality)
        for key, value in sorted(dims.items())
    }
    package_rows = {
        key: FunctionalDimension(
            value=value * 100.0 / total if total else None,
            support_fraction=support,
            evidence_quality=quality,
        )
        for key, value in sorted(packages.items())
    }
    payload = {
        "profile_id": profile_id,
        "format_band": format_band.value,
        "source_snapshot_id": source_snapshot_id,
        "reference_deck_count": 1,
        "dimensions": {key: row.model_dump(mode="json") for key, row in dimension_rows.items()},
        "package_density": {key: row.model_dump(mode="json") for key, row in package_rows.items()},
        "profiled_card_count": profiled,
        "missing_profile_cards": missing,
        "name_fallback_cards": fallback,
    }
    return MetaFunctionalProfile(**payload, profile_hash=sha256_value(payload))


def build_meta_functional_profile(
    snapshot: MetaKnowledgeBaseSnapshot,
    *,
    commander: str,
    format_band: FormatBand,
    profiles: Mapping[str, StructuralCardProfile],
    allow_name_fallback: bool = False,
) -> MetaFunctionalProfile:
    refs = [
        deck
        for deck in snapshot.deck_snapshots
        if deck.commander == commander and deck.format_band == format_band
    ]
    if not refs:
        raise ValueError("no matching meta snapshots")

    values: dict[str, list[tuple[float, float, FunctionalEvidenceQuality]]] = defaultdict(list)
    package_values: dict[str, list[tuple[float, float, FunctionalEvidenceQuality]]] = defaultdict(list)
    missing: set[str] = set()
    fallback: set[str] = set()
    profiled_total = 0
    for ref in refs:
        profile = profile_card_names(
            ref.decklist,
            profiles,
            format_band=format_band,
            source_snapshot_id=snapshot.manifest.snapshot_id,
            profile_id=f"meta-source:{ref.deck_hash}",
            allow_name_fallback=allow_name_fallback,
        )
        profiled_total += profile.profiled_card_count
        missing.update(profile.missing_profile_cards)
        fallback.update(profile.name_fallback_cards)
        raw_completeness = ref.provenance.get("decklist_completeness")
        if isinstance(raw_completeness, (int, float)):
            completeness = max(0.0, min(1.0, float(raw_completeness)))
        else:
            completeness = min(1.0, len(ref.decklist) / 100.0)
        for key, row in profile.dimensions.items():
            if row.value is None:
                continue
            if completeness < 0.999 and key in {"land_count", "average_nonland_mv"}:
                # A frequency-ranked/representative partial extract cannot support a whole-deck
                # land count or average mana value. Keep those dimensions unknown rather than
                # turning omitted cards into invented zeros or biased deck-shape estimates.
                continue
            values[key].append(
                (row.value, row.support_fraction * completeness, row.evidence_quality)
            )
        for key, row in profile.package_density.items():
            if row.value is not None:
                package_values[key].append(
                    (row.value, row.support_fraction * completeness, row.evidence_quality)
                )

    def aggregate(
        rows: dict[str, list[tuple[float, float, FunctionalEvidenceQuality]]]
    ) -> dict[str, FunctionalDimension]:
        result: dict[str, FunctionalDimension] = {}
        for key, samples in sorted(rows.items()):
            weights = [max(0.01, support) for _, support, _ in samples]
            value = sum(sample * weight for (sample, _, _), weight in zip(samples, weights, strict=True)) / sum(
                weights
            )
            support = sum(support for _, support, _ in samples) / len(samples)
            qualities = {quality for _, _, quality in samples}
            if qualities == {FunctionalEvidenceQuality.STRUCTURAL} and support >= 0.999:
                quality = FunctionalEvidenceQuality.STRUCTURAL
            elif qualities <= {
                FunctionalEvidenceQuality.STRUCTURAL,
                FunctionalEvidenceQuality.PARTIAL_STRUCTURAL,
            }:
                quality = FunctionalEvidenceQuality.PARTIAL_STRUCTURAL
            elif FunctionalEvidenceQuality.UNKNOWN in qualities and len(qualities) == 1:
                quality = FunctionalEvidenceQuality.UNKNOWN
            else:
                quality = FunctionalEvidenceQuality.MIXED
            result[key] = FunctionalDimension(
                value=value,
                support_fraction=support,
                evidence_quality=quality,
            )
        return result

    dimensions = aggregate(values)
    package_density = aggregate(package_values)
    payload = {
        "profile_id": f"meta:{snapshot.manifest.snapshot_id}:{commander}:{format_band.value}",
        "format_band": format_band.value,
        "source_snapshot_id": snapshot.manifest.snapshot_id,
        "reference_deck_count": len(refs),
        "dimensions": {key: row.model_dump(mode="json") for key, row in dimensions.items()},
        "package_density": {key: row.model_dump(mode="json") for key, row in package_density.items()},
        "profiled_card_count": profiled_total,
        "missing_profile_cards": tuple(sorted(missing)),
        "name_fallback_cards": tuple(sorted(fallback)),
    }
    return MetaFunctionalProfile(**payload, profile_hash=sha256_value(payload))


def functional_meta_distance(
    candidate: MetaFunctionalProfile,
    reference: MetaFunctionalProfile,
    *,
    policy: DeckDesignPolicy,
) -> FunctionalMetaDistance:
    if candidate.format_band != reference.format_band:
        raise ValueError("functional meta distance cannot collapse format bands")
    common = sorted(set(candidate.dimensions) & set(reference.dimensions))
    components: dict[str, float] = {}
    evidence_qualities: set[FunctionalEvidenceQuality] = set()
    unknown: set[str] = set(candidate.dimensions) ^ set(reference.dimensions)
    for key in common:
        left = candidate.dimensions[key]
        right = reference.dimensions[key]
        if left.value is None or right.value is None:
            unknown.add(key)
            continue
        scale = max(1.0, abs(right.value))
        components[key] = abs(left.value - right.value) / scale
        evidence_qualities.update((left.evidence_quality, right.evidence_quality))
    if not components:
        return FunctionalMetaDistance(
            format_band=candidate.format_band,
            unknown_dimensions=tuple(sorted(unknown | set(common))),
        )
    raw = math.sqrt(sum(value * value for value in components.values()) / len(components))
    band_weight = policy.meta_band_weights.get(candidate.format_band, 0.0)
    weighted = raw * policy.functional_meta_weight * band_weight
    if evidence_qualities == {FunctionalEvidenceQuality.STRUCTURAL}:
        quality = FunctionalEvidenceQuality.STRUCTURAL
    elif evidence_qualities <= {
        FunctionalEvidenceQuality.STRUCTURAL,
        FunctionalEvidenceQuality.PARTIAL_STRUCTURAL,
    }:
        quality = FunctionalEvidenceQuality.PARTIAL_STRUCTURAL
    elif evidence_qualities == {FunctionalEvidenceQuality.LOW_EVIDENCE_FALLBACK}:
        quality = FunctionalEvidenceQuality.LOW_EVIDENCE_FALLBACK
    elif not evidence_qualities:
        quality = FunctionalEvidenceQuality.UNKNOWN
    else:
        quality = FunctionalEvidenceQuality.MIXED
    return FunctionalMetaDistance(
        format_band=candidate.format_band,
        raw_distance=raw,
        policy_weighted_distance=weighted,
        compared_dimensions=tuple(sorted(components)),
        unknown_dimensions=tuple(sorted(unknown)),
        component_distances=dict(sorted(components.items())),
        evidence_quality=quality,
    )
