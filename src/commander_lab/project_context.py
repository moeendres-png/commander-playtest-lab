from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from commander_lab.engine.structural import ENGINE_VERSION


class ProjectContextError(ValueError):
    """Raised when a canonical project-context input is missing or contradictory."""


# Stable identity bridge only. Pod membership is never defined here; it is read from
# J_P5_POD_SCENARIOS_CURRENT.json, which is the repo-local projection of POD_SCENARIOS_CURRENT.
OPPONENT_ENTITY_TO_REGISTRY_KEY = {
    "opponent:alen_high_perfect_morcant": "alen_morcant/current",
    "opponent:cosmic_spider_man": "cosmic_spiderman/current",
    "opponent:blight_curse": "blight_curse/precon",
    "opponent:kaervek_the_merciless": "kaervek/current",
    "opponent:doom_prevails": "doom_prevails/precon",
    "opponent:dance_of_the_elements": "dance_of_the_elements/precon",
    "opponent:wakanda_forever": "wakanda_forever/precon",
    "opponent:lorehold_spirit": "lorehold_spirit/precon",
}

_REQUIRED_FEATURE_SOURCES = {
    "INVENTORY_CARD_FEATURES_CURRENT.jsonl",
    "MULTIPLAYER_CARD_FEATURES_CURRENT.jsonl",
    "CARD_SYNERGY_GRAPH_CURRENT.jsonl",
    "DECK_PACKAGE_TAXONOMY_CURRENT.json",
}


@dataclass(frozen=True)
class ProjectContextSnapshot:
    root: Path
    engine_version: str
    source_hashes: tuple[tuple[str, str], ...]
    primary_scenarios: tuple[tuple[str, tuple[str, ...]], ...]
    holdout_entity_ids: tuple[str, ...]
    holdout_deck_ids: tuple[str, ...]
    snapshot_hash: str

    def primary_opponent_deck_ids(self, deck_id: str) -> tuple[str, ...]:
        scenarios = dict(self.primary_scenarios)
        try:
            return scenarios[deck_id]
        except KeyError as exc:
            raise ProjectContextError(f"no canonical primary scenario for {deck_id}") from exc


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ProjectContextError(f"required project-context input is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProjectContextError(f"required project-context input is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectContextError(f"invalid project-context JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ProjectContextError(f"project-context JSON must be an object: {path}")
    return payload


def _resolve_entities(
    entity_ids: list[str],
    registry: dict[str, Any],
) -> tuple[str, ...]:
    current = registry.get("current")
    if not isinstance(current, dict):
        raise ProjectContextError("opponent registry has no current mapping")
    resolved: list[str] = []
    for entity_id in entity_ids:
        key = OPPONENT_ENTITY_TO_REGISTRY_KEY.get(entity_id)
        if key is None:
            raise ProjectContextError(f"unknown canonical opponent entity id: {entity_id}")
        deck_id = current.get(key)
        if not isinstance(deck_id, str) or not deck_id:
            raise ProjectContextError(
                f"opponent entity {entity_id} does not resolve through registry key {key}"
            )
        resolved.append(deck_id)
    if len(resolved) != len(set(resolved)):
        raise ProjectContextError("canonical scenario resolves duplicate opponent decks")
    return tuple(resolved)


def _feature_source_hashes(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    source_artifacts = manifest.get("source_artifacts")
    if not isinstance(source_artifacts, dict):
        raise ProjectContextError("canonical feature manifest has no source_artifacts")
    if not _REQUIRED_FEATURE_SOURCES <= set(source_artifacts):
        missing = sorted(_REQUIRED_FEATURE_SOURCES - set(source_artifacts))
        raise ProjectContextError(f"canonical feature manifest is missing sources: {missing}")

    hashes: dict[str, str] = {}
    for source_name, raw in source_artifacts.items():
        if not isinstance(raw, dict):
            raise ProjectContextError(f"invalid feature source metadata: {source_name}")
        drive_id = raw.get("drive_id")
        digest = raw.get("sha256")
        if not isinstance(drive_id, str) or not isinstance(digest, str) or len(digest) != 64:
            raise ProjectContextError(f"invalid feature source identity: {source_name}")
        hashes[f"drive_feature:{source_name}:{drive_id}"] = digest

    projection_root = root / "data/collections/current/rogshai_feature_projection"
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ProjectContextError("canonical feature manifest has no projection parts")
    for part_name in parts:
        if not isinstance(part_name, str) or Path(part_name).name != part_name:
            raise ProjectContextError("canonical feature manifest contains unsafe part path")
        hashes[f"feature_projection:{part_name}"] = _sha256_file(projection_root / part_name)
    return hashes


def load_project_context(root: str | Path) -> ProjectContextSnapshot:
    root_path = Path(root).resolve()
    paths = {
        "pod_scenarios": root_path / "data/collections/current/J_P5_POD_SCENARIOS_CURRENT.json",
        "opponent_registry": root_path / "data/opponents/opponent_registry.json",
        "pilot_registry": root_path / "data/pilots/pilot_registry.json",
        "deck_manifest": root_path / "data/decks/manifest.json",
        "inventory_snapshot": root_path / "data/canonical_import/2026-08-07/inventory_snapshot.json",
        "allocation_snapshot": root_path / "data/collections/current_deck_allocations.json",
        "candidate_eligibility": root_path
        / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
        "optimization_availability": root_path
        / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json",
        "feature_projection_manifest": root_path
        / "data/collections/current/rogshai_feature_projection/manifest.json",
    }
    source_hash_dict = {name: _sha256_file(path) for name, path in paths.items()}
    feature_manifest = _load_json(paths["feature_projection_manifest"])
    source_hash_dict.update(_feature_source_hashes(root_path, feature_manifest))
    source_hashes = tuple(sorted(source_hash_dict.items()))

    pods = _load_json(paths["pod_scenarios"])
    registry = _load_json(paths["opponent_registry"])

    frequency_policy = str(pods.get("frequency_policy", ""))
    if "No fixed opponent frequency" not in frequency_policy:
        raise ProjectContextError("canonical pod source lost its no-frequency-weights policy")

    raw_scenarios = pods.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise ProjectContextError("canonical pod source has no scenarios list")

    primary: dict[str, tuple[str, ...]] = {}
    holdout: tuple[str, ...] | None = None
    for raw in raw_scenarios:
        if not isinstance(raw, dict):
            raise ProjectContextError("invalid scenario record")
        scenario_type = raw.get("scenario_type")
        if scenario_type == "primary_four_player_context":
            deck_id = raw.get("own_deck")
            entity_ids = raw.get("opponent_entity_ids")
            if not isinstance(deck_id, str) or not isinstance(entity_ids, list):
                raise ProjectContextError("primary scenario is missing deck or opponent entities")
            if raw.get("pod_size") != 4 or len(entity_ids) != 3:
                raise ProjectContextError("primary four-player scenario must contain exactly 3 opponents")
            if deck_id in primary:
                raise ProjectContextError(f"multiple canonical primary scenarios for {deck_id}")
            primary[deck_id] = _resolve_entities([str(value) for value in entity_ids], registry)
        elif scenario_type == "opponent_pool_not_fixed_pod":
            entity_ids = raw.get("opponent_entity_ids")
            if not isinstance(entity_ids, list):
                raise ProjectContextError("holdout opponent pool has no entity ids")
            holdout = tuple(str(value) for value in entity_ids)

    expected_decks = {"korvold/current", "rogshai/current"}
    if set(primary) != expected_decks:
        raise ProjectContextError(
            f"canonical primary scenarios must cover exactly {sorted(expected_decks)}; got {sorted(primary)}"
        )
    if holdout is None:
        raise ProjectContextError("canonical holdout/sensitivity pool is missing")

    primary_entity_sets = {
        entity_id
        for raw in raw_scenarios
        if isinstance(raw, dict) and raw.get("scenario_type") == "primary_four_player_context"
        for entity_id in (raw.get("opponent_entity_ids") or [])
    }
    if primary_entity_sets.intersection(holdout):
        raise ProjectContextError("holdout opponent was silently promoted into a primary scenario")

    holdout_decks = _resolve_entities(list(holdout), registry)
    identity_payload = {
        "engine_version": ENGINE_VERSION,
        "source_hashes": dict(source_hashes),
        "primary_scenarios": {key: list(value) for key, value in sorted(primary.items())},
        "holdout_entity_ids": list(holdout),
        "holdout_deck_ids": list(holdout_decks),
    }
    snapshot_hash = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ProjectContextSnapshot(
        root=root_path,
        engine_version=ENGINE_VERSION,
        source_hashes=source_hashes,
        primary_scenarios=tuple(sorted(primary.items())),
        holdout_entity_ids=holdout,
        holdout_deck_ids=holdout_decks,
        snapshot_hash=snapshot_hash,
    )
