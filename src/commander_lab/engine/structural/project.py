from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import Deck, StructuralCardProfile, StructuralDeckProfile
from commander_lab.storage import load_model

from .fixtures import build_current_opponent_profiles, build_synthetic_deck_profile
from .profiles import StructuralProfileCatalog, build_structural_deck_profile


def _merge_unique_structural_profiles(
    target: dict[str, StructuralDeckProfile],
    incoming: dict[str, StructuralDeckProfile],
    *,
    source: str | Path,
) -> None:
    collisions = sorted(set(target).intersection(incoming))
    if collisions:
        joined = ", ".join(collisions)
        raise ValueError(f"structural deck_id collision from {source}: {joined}")
    target.update(incoming)


def _validate_structural_profile_ids(config_path: str | Path) -> None:
    path = Path(config_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    duplicates: set[str] = set()
    for spec in payload["profiles"]:
        deck_id = str(spec["deck_id"])
        if deck_id in seen:
            duplicates.add(deck_id)
        seen.add(deck_id)
    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate structural deck_id in {path}: {joined}")


def load_project_structural_decks(
    root: str | Path,
    *,
    include_synthetic_fixtures: bool = False,
    include_current_opponents: bool = False,
) -> dict[str, StructuralDeckProfile]:
    root_path = Path(root)
    manifest = json.loads((root_path / "data/decks/manifest.json").read_text(encoding="utf-8"))
    snapshot_hash = str(manifest["data_snapshot_hash"])
    profiles = StructuralProfileCatalog.from_json(
        root_path / "data/cards/structural_role_profiles.json"
    )
    overlay_path = root_path / "data/decks/rogshai_current_structural_overrides.json"
    if overlay_path.exists():
        overlay_payload = json.loads(overlay_path.read_text(encoding="utf-8"))
        overlay_rows = overlay_payload.get("profiles", [])
        if not isinstance(overlay_rows, list):
            raise ValueError("current RogShai structural overlay is malformed")
        profiles = StructuralProfileCatalog(
            (
                *profiles.profiles,
                *(StructuralCardProfile.model_validate(row) for row in overlay_rows),
            )
        )
    decks: dict[str, StructuralDeckProfile] = {}
    deck_specs = manifest.get("decks", {})
    if not isinstance(deck_specs, dict) or not deck_specs:
        raise ValueError("current deck manifest does not contain any operational decks")
    for deck_id, spec in deck_specs.items():
        if not isinstance(spec, dict):
            raise ValueError(f"invalid deck manifest entry for {deck_id}")
        filename = spec.get("normalized_file")
        if not isinstance(filename, str) or not filename:
            raise ValueError(f"current deck manifest entry {deck_id} has no normalized_file")
        deck_path = root_path / "data/decks" / filename
        deck = load_model(deck_path, Deck)
        if deck.deck_id != deck_id:
            raise ValueError(
                f"deck manifest id mismatch: expected {deck_id}, loaded {deck.deck_id} from {deck_path}"
            )
        profile = build_structural_deck_profile(deck, profiles, data_snapshot_hash=snapshot_hash)
        profile = _attach_package_membership(profile, root_path)
        _merge_unique_structural_profiles(
            decks,
            {profile.deck_id: profile},
            source=deck_path,
        )
    if include_synthetic_fixtures:
        for archetype in ("aggro", "control", "engine"):
            profile = build_synthetic_deck_profile(archetype, data_snapshot_hash=snapshot_hash)
            _merge_unique_structural_profiles(
                decks,
                {profile.deck_id: profile},
                source=f"synthetic fixture {archetype}",
            )
    if include_current_opponents:
        opponent_dir = root_path / "data/opponents"
        opponent_paths = [opponent_dir / "current_structural_profiles.json"]
        opponent_paths.extend(sorted(opponent_dir.glob("*_structural_profile.json")))
        for opponent_path in opponent_paths:
            if opponent_path.exists():
                _validate_structural_profile_ids(opponent_path)
                opponent_profiles = build_current_opponent_profiles(
                    opponent_path,
                    data_snapshot_hash=snapshot_hash,
                )
                _merge_unique_structural_profiles(
                    decks,
                    opponent_profiles,
                    source=opponent_path,
                )
    return decks


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _attach_package_membership(
    profile: StructuralDeckProfile, root_path: Path
) -> StructuralDeckProfile:
    registry_path = root_path / "data/packages/package_registry.json"
    if not registry_path.exists():
        return profile
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    commander = (
        "Korvold, Fae-Cursed King"
        if profile.deck_id == "korvold/current"
        else "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"
        if profile.deck_id == "rogshai/current"
        else " / ".join(profile.commander_names)
    )
    latest: dict[str, dict[str, object]] = {}
    for package in payload.get("packages", []):
        if package.get("commander") != commander or package.get("status") not in {
            "curated",
            "validated",
        }:
            continue
        previous = latest.get(str(package["package_id"]))
        if previous is None or _version_key(str(package["version"])) > _version_key(
            str(previous["version"])
        ):
            latest[str(package["package_id"])] = package
    memberships: dict[str, set[str]] = {}
    for package_id, package in latest.items():
        for field in (
            "core_cards",
            "support_cards",
            "optional_cards",
            "enablers",
            "payoffs",
            "finishers",
        ):
            raw_names = package.get(field, [])
            if not isinstance(raw_names, list):
                continue
            for card_name in raw_names:
                memberships.setdefault(str(card_name), set()).add(package_id)
    cards = tuple(
        card.model_copy(update={"package_ids": frozenset(memberships.get(card.oracle_name, set()))})
        for card in profile.cards
    )
    return profile.model_copy(update={"cards": cards})
