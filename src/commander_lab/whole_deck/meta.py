from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from commander_lab.models import (
    CardRole,
    FormatBand,
    MetaComboLine,
    MetaDeckSnapshot,
    MetaKnowledgeBaseSnapshot,
    MetaPackage,
    MetaTier,
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

# Meta-Lane PR4 guardrails (design §5.1-§5.3). Tier caps bound the weight of
# an external meta signal: Tier A caps at 0.45 (META_MEDIUM level), Tier B
# at 0.30, Tier C at 0.0: Tier C appears in read lists only, never in
# scoring. The floor (§5.2) lives in search_meta_score._objective; the veto
# (§5.3) is set and queried below.
META_TIER_WEIGHT_CAPS: dict[MetaTier, float] = {
    MetaTier.A: 0.45,
    MetaTier.B: 0.30,
    MetaTier.C: 0.0,
}

_TIER_STRENGTH: dict[MetaTier, int] = {
    MetaTier.C: 0,
    MetaTier.B: 1,
    MetaTier.A: 2,
}


def capped_meta_weight(weight: float, tier: MetaTier | None) -> float:
    """Cap an external meta weight by source tier (design §5.1).

    An untiered (legacy/internal) reference keeps the policy weight
    unchanged, so the pinned pre-PR1 snapshot scores exactly as before.
    In particular MAX_FEASIBLE_META_SHAPE (1.0) stays reserved for
    internal references: a tiered external reference never runs at 1.0.
    """
    if tier is None:
        return weight
    return min(weight, META_TIER_WEIGHT_CAPS[tier])


def reference_source_tier(
    snapshot: MetaKnowledgeBaseSnapshot,
    refs: Sequence[MetaDeckSnapshot],
) -> MetaTier | None:
    """Weakest tier among the tiered sources backing the given decks.

    Decks link to sources via source_id. Untiered sources are ignored;
    when no backing source carries a tier, the result is None (uncapped
    legacy behavior). Weakest wins: a reference is only as strong as its
    weakest tiered source, so a Tier-C source in the mix zeroes it.
    """
    tiers = {
        source.tier
        for ref in refs
        for source in snapshot.sources
        if source.source_id == ref.source_id and source.tier is not None
    }
    if not tiers:
        return None
    return min(tiers, key=lambda tier: _TIER_STRENGTH[tier])


def vetoed_package_ids(snapshot: MetaKnowledgeBaseSnapshot) -> frozenset[str]:
    """Package ids whose external endorsement paired games overruled (§5.3)."""
    return frozenset(package.package_id for package in snapshot.packages if package.vetoed_by_games)


def mark_package_vetoed(
    snapshot: MetaKnowledgeBaseSnapshot, package_id: str
) -> MetaKnowledgeBaseSnapshot:
    """Return a copy of the snapshot with the package vetoed by games (§5.3).

    Own paired games beat any external prior; the contradiction itself must
    still be documented in the PR/artifact that records it — this function
    only sets the flag, it does not write that documentation. Unknown
    package ids raise ValueError; re-marking is idempotent. The input
    snapshot is left unchanged.

    Deliberate limit: no live scoring consumer reads snapshot packages
    today (package_density is informational; the distance compares
    dimensions), so this flag is set and queryable, but its enforcement in
    live scoring lands with PR5's package enrichment, which first makes
    snapshot packages a scoring input. PR4 invents no package-to-dimension
    mapping to pretend otherwise.
    """
    packages = list(snapshot.packages)
    for index, package in enumerate(packages):
        if package.package_id == package_id:
            packages[index] = package.model_copy(update={"vetoed_by_games": True})
            return snapshot.model_copy(update={"packages": tuple(packages)})
    raise ValueError(f"unknown package_id in snapshot: {package_id}")


def _normalized_card_name(name: str) -> str:
    return name.strip().casefold()


def load_snapshot_packages(path: str | Path) -> tuple[MetaPackage, ...]:
    """Load the packages of a snapshot-shaped file (Meta-Lane PR5).

    The PR5 package files are snapshots with empty deck_snapshots; they
    validate through the same model as the refresh snapshots, so a
    malformed file fails here, not in scoring.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    snapshot = MetaKnowledgeBaseSnapshot.model_validate(data)
    return snapshot.packages


def load_spellbook_combos(path: str | Path) -> tuple[MetaComboLine, ...]:
    """Load known combo lines from an offline JSON file (Meta-Lane PR5).

    The file carries a free-form provenance block plus a "combos" list;
    only the combos validate. Nothing here touches the network: the
    Spellbook sync module is deliberately not imported on this path.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    combos = data.get("combos") if isinstance(data, dict) else None
    if not isinstance(combos, list):
        raise ValueError(f"spellbook combos file has no combos list: {path}")
    return tuple(MetaComboLine.model_validate(item) for item in combos)


def known_combos_in_deck(
    deck: Sequence[str],
    combos: Sequence[MetaComboLine],
    *,
    band: FormatBand | None = None,
) -> tuple[MetaComboLine, ...]:
    """Combo lines fully contained in a deck (metadata only, PR5).

    A line counts only when every named card is present and every
    any_of group has at least one card present. A partial line never
    counts. When band is given, only lines covering that band count:
    a cEDH line never reports for a casual band. This says nothing
    about whether the line is legal or good in a real game — that is
    the engine's call, not this function's.
    """
    present = {_normalized_card_name(name) for name in deck}
    found = []
    for combo in combos:
        if band is not None and band not in combo.bands:
            continue
        if not all(_normalized_card_name(card) in present for card in combo.cards):
            continue
        if not all(
            any(_normalized_card_name(option) in present for option in group)
            for group in combo.any_of
        ):
            continue
        found.append(combo)
    return tuple(found)


def snapshot_package_term(
    packages: Sequence[MetaPackage],
    deck: Sequence[str],
    band: FormatBand,
) -> float:
    """Package enrichment term for one band (Meta-Lane PR5, <= 0).

    For each non-vetoed package covering this band, an overlap of at
    least 2 cards contributes -0.01 * (overlap - 1) ** 2 — the same
    shape as the internal package bonus, but as a reduction of the
    band's meta distance. The caller clamps the band total at zero,
    so packages can at most cancel a band's meta penalty, never push
    a score above its internal value (PR4 floor semantics). Vetoed
    packages (§5.3: paired games overruled them) contribute exactly 0:
    the veto is live in scoring from PR5 on.
    """
    present = {_normalized_card_name(name) for name in deck}
    term = 0.0
    for package in packages:
        if package.vetoed_by_games:
            continue
        package_bands = {category.value for category in package.categories}
        if band.value not in package_bands:
            continue
        overlap = sum(1 for card in package.cards if _normalized_card_name(card) in present)
        if overlap >= 2:
            term -= 0.01 * (overlap - 1) ** 2
    return term


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
    role_totals: defaultdict[str, float] = defaultdict(float)
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
    return (
        dims,
        package_totals,
        len(known_cards),
        tuple(sorted(set(missing))),
        tuple(sorted(set(fallback))),
    )


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
    return MetaFunctionalProfile.model_validate({**payload, "profile_hash": sha256_value(payload)})


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
    package_values: dict[str, list[tuple[float, float, FunctionalEvidenceQuality]]] = defaultdict(
        list
    )
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
        rows: dict[str, list[tuple[float, float, FunctionalEvidenceQuality]]],
    ) -> dict[str, FunctionalDimension]:
        result: dict[str, FunctionalDimension] = {}
        for key, samples in sorted(rows.items()):
            weights = [max(0.01, support) for _, support, _ in samples]
            value = sum(
                sample * weight for (sample, _, _), weight in zip(samples, weights, strict=True)
            ) / sum(weights)
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
        "package_density": {
            key: row.model_dump(mode="json") for key, row in package_density.items()
        },
        "profiled_card_count": profiled_total,
        "missing_profile_cards": tuple(sorted(missing)),
        "name_fallback_cards": tuple(sorted(fallback)),
    }
    # The tier rides outside the hash payload, so existing profile hashes
    # do not change when a reference gains tiered sources.
    return MetaFunctionalProfile.model_validate(
        {
            **payload,
            "profile_hash": sha256_value(payload),
            "source_tier": reference_source_tier(snapshot, refs),
        }
    )


def functional_meta_distance(
    candidate: MetaFunctionalProfile,
    reference: MetaFunctionalProfile,
    *,
    policy: DeckDesignPolicy,
    source_tier: MetaTier | None = None,
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
    weighted = raw * capped_meta_weight(policy.functional_meta_weight, source_tier) * band_weight
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
