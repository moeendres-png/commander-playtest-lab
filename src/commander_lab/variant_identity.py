from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from commander_lab.storage import sha256_value


@dataclass(frozen=True)
class CanonicalVariantIdentity:
    baseline_deck_hash: str
    variant_deck_hash: str
    context_snapshot_hash: str
    deck_diff: tuple[tuple[str, str], ...]
    package_diff: tuple[str, ...]
    functional_replacement_groups: tuple[str, ...]

    @property
    def identity_hash(self) -> str:
        return sha256_value(asdict(self))

    @property
    def functional_family_hash(self) -> str:
        return sha256_value(
            {
                "baseline_deck_hash": self.baseline_deck_hash,
                "context_snapshot_hash": self.context_snapshot_hash,
                "package_diff": self.package_diff,
                "functional_replacement_groups": self.functional_replacement_groups,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity_hash": self.identity_hash,
            "functional_family_hash": self.functional_family_hash,
            **asdict(self),
        }


def build_variant_identity(
    *,
    baseline_deck_hash: str,
    variant_deck_hash: str,
    context_snapshot_hash: str,
    deck_diff: Iterable[tuple[str, str]],
    package_diff: Iterable[str] = (),
    functional_replacement_groups: Iterable[str] = (),
) -> CanonicalVariantIdentity:
    return CanonicalVariantIdentity(
        baseline_deck_hash=baseline_deck_hash,
        variant_deck_hash=variant_deck_hash,
        context_snapshot_hash=context_snapshot_hash,
        deck_diff=tuple(sorted((str(remove), str(add)) for remove, add in deck_diff)),
        package_diff=tuple(sorted(str(value) for value in package_diff)),
        functional_replacement_groups=tuple(
            sorted(str(value) for value in functional_replacement_groups)
        ),
    )


def deduplicate_exact_variants(
    variants: Iterable[CanonicalVariantIdentity],
) -> tuple[tuple[CanonicalVariantIdentity, ...], dict[str, str]]:
    """Deduplicate exact deck identities; functional families remain diagnostic only.

    Weakly modeled or merely similar cards are never removed by this function.
    """

    unique: list[CanonicalVariantIdentity] = []
    seen_decks: dict[tuple[str, str], str] = {}
    duplicates: dict[str, str] = {}
    for variant in variants:
        exact_key = (variant.context_snapshot_hash, variant.variant_deck_hash)
        existing = seen_decks.get(exact_key)
        if existing is not None:
            duplicates[variant.identity_hash] = existing
            continue
        seen_decks[exact_key] = variant.identity_hash
        unique.append(variant)
    return tuple(unique), dict(sorted(duplicates.items()))


__all__ = [
    "CanonicalVariantIdentity",
    "build_variant_identity",
    "deduplicate_exact_variants",
]
