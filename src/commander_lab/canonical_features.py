from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from commander_lab.deck_registry import DeckPolicyRegistry, load_deck_policy_registry
from commander_lab.models import CardRole, DataQuality, SourceRef, StructuralCardProfile


class CanonicalFeatureError(ValueError):
    """Raised when a configured repo-local feature projection is invalid."""


ROLE_TAG_MAP: dict[str, frozenset[CardRole]] = {
    "mana_source": frozenset({CardRole.MANA_SOURCE}),
    "mana_fixing": frozenset({CardRole.MANA_SOURCE}),
    "fast_mana": frozenset({CardRole.RAMP}),
    "ramp": frozenset({CardRole.RAMP}),
    "card_draw": frozenset({CardRole.DRAW}),
    "combat_draw": frozenset({CardRole.DRAW, CardRole.COMBAT_PAYOFF}),
    "card_selection": frozenset({CardRole.SELECTION}),
    "spot_removal": frozenset({CardRole.REMOVAL}),
    "counterspell": frozenset({CardRole.COUNTER}),
    "protection": frozenset({CardRole.PROTECTION}),
    "boardwipe": frozenset({CardRole.WIPE}),
    "recursion": frozenset({CardRole.RECURSION}),
    "graveyard_hate": frozenset({CardRole.GRAVEYARD_HATE}),
    "engine": frozenset({CardRole.ENGINE}),
    "payoff": frozenset({CardRole.PAYOFF}),
    "finisher": frozenset({CardRole.FINISHER}),
    "commander_damage": frozenset({CardRole.COMBAT_PAYOFF}),
    "table_damage": frozenset({CardRole.PAYOFF}),
    "token_generation": frozenset({CardRole.TOKEN_SOURCE}),
    "sacrifice_fodder": frozenset({CardRole.ENABLER, CardRole.TOKEN_SOURCE}),
    "sacrifice_outlet": frozenset({CardRole.SACRIFICE_OUTLET}),
    "land_rebuild": frozenset({CardRole.LAND_SYNERGY, CardRole.RECURSION}),
}

# Source tags without a structurally equivalent CardRole stay in provenance only.
UNMAPPED_TAGS = frozenset({"tutor"})
DERIVED_ROLE_STRENGTH = 0.70


@dataclass(frozen=True)
class CanonicalFeatureAnnotation:
    oracle_name: str
    source_role_tags: frozenset[str]
    mapped_roles: frozenset[CardRole]
    package_ids: frozenset[str]
    deck_id: str = ""
    source_manifest_path: str = ""


def _read_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalFeatureError(f"invalid {label}: {path}") from exc


def load_canonical_feature_annotations(
    root: str | Path,
    *,
    deck_id: str | None = None,
    registry: DeckPolicyRegistry | None = None,
) -> dict[str, CanonicalFeatureAnnotation]:
    project_root = Path(root).resolve()
    deck_registry = registry or load_deck_policy_registry(project_root)
    selected_deck_id = deck_id or deck_registry.primary_deck_id
    policy = deck_registry.policy(selected_deck_id)
    manifest_path = deck_registry.feature_manifest_path(selected_deck_id)
    if manifest_path is None:
        return {}

    manifest = _read_json(manifest_path, label="feature projection manifest")
    if not isinstance(manifest, dict):
        raise CanonicalFeatureError("feature projection manifest must be an object")
    if manifest.get("deck_id") != selected_deck_id:
        raise CanonicalFeatureError(
            f"feature projection deck_id mismatch: expected {selected_deck_id}, "
            f"got {manifest.get('deck_id')}"
        )
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise CanonicalFeatureError(f"feature projection has no parts: {selected_deck_id}")

    annotations: dict[str, CanonicalFeatureAnnotation] = {}
    projection_root = manifest_path.parent
    for part_name in parts:
        if not isinstance(part_name, str) or Path(part_name).name != part_name:
            raise CanonicalFeatureError("feature projection contains an unsafe part path")
        path = projection_root / part_name
        if not path.is_file():
            raise CanonicalFeatureError(f"feature projection part is missing: {part_name}")
        rows = _read_json(path, label=f"feature projection part {part_name}")
        if not isinstance(rows, list):
            raise CanonicalFeatureError(f"feature projection part is not a list: {part_name}")
        for row in rows:
            if not isinstance(row, list) or len(row) != 3:
                raise CanonicalFeatureError(f"invalid feature row in {part_name}")
            name, raw_tags, raw_packages = row
            if (
                not isinstance(name, str)
                or not isinstance(raw_tags, list)
                or not isinstance(raw_packages, list)
            ):
                raise CanonicalFeatureError(f"invalid feature row types in {part_name}")
            if name in annotations:
                raise CanonicalFeatureError(f"duplicate feature row: {name}")
            tags = frozenset(str(value) for value in raw_tags)
            unknown = tags - set(ROLE_TAG_MAP) - set(UNMAPPED_TAGS)
            if unknown:
                raise CanonicalFeatureError(
                    f"unmapped feature tags for {name}: {sorted(unknown)}"
                )
            mapped = frozenset(
                role for tag in tags for role in ROLE_TAG_MAP.get(tag, frozenset())
            )
            packages = frozenset(str(value) for value in raw_packages)
            invalid_packages = sorted(
                package for package in packages if not policy.package_id_allowed(package)
            )
            if invalid_packages:
                raise CanonicalFeatureError(
                    f"package ids escape configured deck policy for {selected_deck_id}/{name}: "
                    f"{invalid_packages}"
                )
            annotations[name] = CanonicalFeatureAnnotation(
                oracle_name=name,
                source_role_tags=tags,
                mapped_roles=mapped,
                package_ids=packages,
                deck_id=selected_deck_id,
                source_manifest_path=manifest_path.relative_to(project_root).as_posix(),
            )

    expected_rows = manifest.get("materialized_role_or_package_rows")
    if not isinstance(expected_rows, int) or expected_rows != len(annotations):
        raise CanonicalFeatureError(
            f"feature projection row count mismatch for {selected_deck_id}: "
            f"expected {expected_rows}, got {len(annotations)}"
        )
    return annotations


def fuse_canonical_features(
    profile: StructuralCardProfile,
    annotation: CanonicalFeatureAnnotation | None,
) -> StructuralCardProfile:
    if annotation is None:
        return profile
    if annotation.oracle_name != profile.oracle_name:
        raise CanonicalFeatureError("feature annotation/profile name mismatch")

    roles = frozenset(set(profile.roles) | set(annotation.mapped_roles))
    strengths = dict(profile.role_strengths)
    for role in annotation.mapped_roles:
        if role not in profile.roles:
            strengths[role] = DERIVED_ROLE_STRENGTH

    projection_source = SourceRef(
        source_type="canonical_drive_derived_projection",
        source_name=(
            f"{annotation.deck_id} feature/package projection"
            if annotation.deck_id
            else "configured deck feature/package projection"
        ),
        source_path=annotation.source_manifest_path or None,
        quality=DataQuality.PROJECT_INFERRED,
        notes=(
            "Derived from configured current project feature/package sources for the selected "
            "deck. Adds structural roles/packages only; does not overwrite curated numeric power "
            "values and is not empirical or rules-engine evidence."
        ),
    )
    tag_note = ",".join(sorted(annotation.source_role_tags)) or "packages_only"
    current_notes = profile.notes or ""
    note = (
        f"{current_notes} Canonical-derived feature overlay: {tag_note}."
        if current_notes
        else f"Canonical-derived feature overlay: {tag_note}."
    )
    return profile.model_copy(
        update={
            "roles": roles,
            "role_strengths": strengths,
            "package_ids": frozenset(set(profile.package_ids) | set(annotation.package_ids)),
            "sources": (*tuple(profile.sources), projection_source),
            "notes": note,
        }
    )
