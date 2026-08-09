from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import Deck, StructuralDeckProfile
from commander_lab.storage import load_model

from .fixtures import build_current_opponent_profiles, build_synthetic_deck_profile
from .profiles import StructuralProfileCatalog, build_structural_deck_profile


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
    decks: dict[str, StructuralDeckProfile] = {}
    for filename in ("korvold_current.json", "rogshai_current.json"):
        deck = load_model(root_path / "data/decks" / filename, Deck)
        profile = build_structural_deck_profile(deck, profiles, data_snapshot_hash=snapshot_hash)
        profile = _attach_package_membership(profile, root_path)
        decks[profile.deck_id] = profile
    if include_synthetic_fixtures:
        for archetype in ("aggro", "control", "engine"):
            profile = build_synthetic_deck_profile(archetype, data_snapshot_hash=snapshot_hash)
            decks[profile.deck_id] = profile
    if include_current_opponents:
        opponent_path = root_path / "data/opponents/current_structural_profiles.json"
        if opponent_path.exists():
            decks.update(
                build_current_opponent_profiles(opponent_path, data_snapshot_hash=snapshot_hash)
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
            for card_name in package.get(field, []):
                memberships.setdefault(str(card_name), set()).add(package_id)
    cards = tuple(
        card.model_copy(update={"package_ids": frozenset(memberships.get(card.oracle_name, set()))})
        for card in profile.cards
    )
    return profile.model_copy(update={"cards": cards})
