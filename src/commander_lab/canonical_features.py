from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from commander_lab.models import CardRole, DataQuality, SourceRef, StructuralCardProfile


class CanonicalFeatureError(ValueError):
    """Raised when the repo-local canonical feature projection is invalid."""


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


def _projection_root(root: Path) -> Path:
    return root / "data/collections/current/rogshai_feature_projection"


def load_canonical_feature_annotations(
    root: str | Path,
) -> dict[str, CanonicalFeatureAnnotation]:
    project_root = Path(root).resolve()
    projection_root = _projection_root(project_root)
    manifest_path = projection_root / "manifest.json"
    if not manifest_path.is_file():
        raise CanonicalFeatureError("canonical RogShai feature projection manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CanonicalFeatureError("canonical RogShai feature manifest is invalid JSON") from exc
    if manifest.get("deck_id") != "rogshai/current":
        raise CanonicalFeatureError("canonical feature projection deck_id is not RogShai")
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise CanonicalFeatureError("canonical feature projection has no parts")

    annotations: dict[str, CanonicalFeatureAnnotation] = {}
    for part_name in parts:
        if not isinstance(part_name, str) or Path(part_name).name != part_name:
            raise CanonicalFeatureError("canonical feature projection contains an unsafe part path")
        path = projection_root / part_name
        if not path.is_file():
            raise CanonicalFeatureError(f"canonical feature projection part is missing: {part_name}")
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CanonicalFeatureError(f"invalid canonical feature projection part: {part_name}") from exc
        if not isinstance(rows, list):
            raise CanonicalFeatureError(f"canonical feature projection part is not a list: {part_name}")
        for row in rows:
            if not isinstance(row, list) or len(row) != 3:
                raise CanonicalFeatureError(f"invalid feature row in {part_name}")
            name, raw_tags, raw_packages = row
            if not isinstance(name, str) or not isinstance(raw_tags, list) or not isinstance(raw_packages, list):
                raise CanonicalFeatureError(f"invalid feature row types in {part_name}")
            if name in annotations:
                raise CanonicalFeatureError(f"duplicate canonical feature row: {name}")
            tags = frozenset(str(value) for value in raw_tags)
            unknown = tags - set(ROLE_TAG_MAP) - set(UNMAPPED_TAGS)
            if unknown:
                raise CanonicalFeatureError(
                    f"unmapped canonical feature tags for {name}: {sorted(unknown)}"
                )
            mapped = frozenset(
                role for tag in tags for role in ROLE_TAG_MAP.get(tag, frozenset())
            )
            packages = frozenset(str(value) for value in raw_packages)
            if any(not package.startswith("package:rogshai:") for package in packages):
                raise CanonicalFeatureError(f"non-RogShai package in feature projection for {name}")
            annotations[name] = CanonicalFeatureAnnotation(
                oracle_name=name,
                source_role_tags=tags,
                mapped_roles=mapped,
                package_ids=packages,
            )

    expected_rows = manifest.get("materialized_role_or_package_rows")
    if expected_rows != len(annotations):
        raise CanonicalFeatureError(
            f"canonical feature projection row count mismatch: expected {expected_rows}, got {len(annotations)}"
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
        source_name="RogShai current feature/package projection",
        source_path="data/collections/current/rogshai_feature_projection/manifest.json",
        quality=DataQuality.PROJECT_INFERRED,
        notes=(
            "Derived from current Drive Card Features / Multiplayer Features / Synergy Graph / "
            "Package Taxonomy. Adds structural roles/packages only; does not overwrite curated "
            "numeric power values and is not empirical or rules-engine evidence."
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
            "sources": tuple(profile.sources) + (projection_source,),
            "notes": note,
        }
    )
