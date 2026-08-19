from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.models import Deck
from commander_lab.storage import compute_deck_hash


class ProjectContextError(ValueError):
    """Raised when a canonical project-context input is missing or contradictory."""


# Stable identity bridge only. Pod membership is never defined here; it is read from
# POD_SCENARIOS_CURRENT.json, the repo-local read-only projection of current Drive pod scenarios.
OPPONENT_ENTITY_TO_REGISTRY_KEY = {
    "opponent:alen_high_perfect_morcant": "alen_morcant/current",
    "opponent:cosmic_spider_man": "cosmic_spiderman/current",
    "opponent:blight_curse": "blight_curse/precon",
    "opponent:kaervek_the_merciless": "kaervek/current",
    "opponent:doom_prevails": "doom_prevails/precon",
    "opponent:dance_of_the_elements": "dance_of_the_elements/precon",
    "opponent:wakanda_forever": "wakanda_forever/precon",
    "opponent:lorehold_spirit": "lorehold_spirit/precon",
    "opponent:scions_spellcraft": "scions_spellcraft/precon",
    "opponent:counter_intelligence": "counter_intelligence/precon",
    "opponent:turtle_power": "turtle_power/precon",
    "opponent:silverquill_influence": "silverquill_influence/precon",
    "opponent:fantastic_four": "fantastic_four/precon",
    "opponent:avengers_assemble": "avengers_assemble/precon",
}

_REQUIRED_FEATURE_SOURCES = {
    "ROGSHAI_CANDIDATE_POOL_CURRENT.jsonl",
    "INVENTORY_CARD_FEATURES_CURRENT.jsonl",
    "MULTIPLAYER_CARD_FEATURES_CURRENT.jsonl",
    "CARD_SYNERGY_GRAPH_CURRENT.jsonl",
    "DECK_PACKAGE_TAXONOMY_CURRENT.json",
}


@dataclass(frozen=True)
class ProjectContextSnapshot:
    root: Path
    software_version: str
    engine_version: str
    active_own_deck_ids: tuple[str, ...]
    historical_own_deck_ids: tuple[str, ...]
    primary_deckbuilding_focus: str
    active_deck_hashes: tuple[tuple[str, str], ...]
    policy_config_hashes: tuple[tuple[str, str], ...]
    source_hashes: tuple[tuple[str, str], ...]
    source_freshness: tuple[tuple[str, str], ...]
    primary_scenarios: tuple[tuple[str, tuple[str, ...]], ...]
    historical_reference_scenarios: tuple[tuple[str, tuple[str, ...]], ...]
    holdout_entity_ids: tuple[str, ...]
    holdout_deck_ids: tuple[str, ...]
    playstyle_preference_type: str
    playstyle_preference_hash: str
    snapshot_hash: str

    def primary_opponent_deck_ids(self, deck_id: str) -> tuple[str, ...]:
        scenarios = dict(self.primary_scenarios)
        try:
            return scenarios[deck_id]
        except KeyError as exc:
            raise ProjectContextError(f"no canonical primary scenario for {deck_id}") from exc

    def historical_reference_opponent_deck_ids(self, deck_id: str) -> tuple[str, ...]:
        scenarios = dict(self.historical_reference_scenarios)
        try:
            return scenarios[deck_id]
        except KeyError as exc:
            raise ProjectContextError(f"no historical reference scenario for {deck_id}") from exc


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ProjectContextError(f"required project-context input is missing: {path}")
    payload = path.read_bytes()
    if path.suffix.casefold() in {".json", ".jsonl", ".yaml", ".yml", ".txt", ".md"}:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


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


def _resolve_entities(entity_ids: list[str], registry: dict[str, Any]) -> tuple[str, ...]:
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
    missing = sorted(_REQUIRED_FEATURE_SOURCES - set(source_artifacts))
    if missing:
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


def _load_scope(scope_path: Path) -> tuple[tuple[str, ...], tuple[str, ...], str, dict[str, Any]]:
    scope = _load_json(scope_path)
    active_raw = scope.get("active_own_decks")
    historical_raw = scope.get("historical_own_decks")
    focus = scope.get("primary_deckbuilding_focus")
    if not isinstance(active_raw, list) or not active_raw:
        raise ProjectContextError("active deck scope is missing or empty")
    if not isinstance(historical_raw, list):
        raise ProjectContextError("historical deck scope is missing")
    if not isinstance(focus, str) or not focus:
        raise ProjectContextError("primary deckbuilding focus is missing")
    active = tuple(str(value) for value in active_raw)
    historical = tuple(str(value) for value in historical_raw)
    if len(active) != len(set(active)) or len(historical) != len(set(historical)):
        raise ProjectContextError("active/historical deck scope contains duplicate ids")
    if set(active).intersection(historical):
        raise ProjectContextError("a deck cannot be both active and historical")
    if focus not in active:
        raise ProjectContextError("primary deckbuilding focus is not an active own deck")
    if scope.get("historical_allocation_blocks_active_deck") is not False:
        raise ProjectContextError("historical allocation must not block the active own deck")
    if scope.get("current_valid") is not True:
        raise ProjectContextError("live active-deck scope is stale or not marked current-valid")
    if scope.get("status") != "canonical_current_live_scope":
        raise ProjectContextError("live active-deck scope has a non-current status")
    sources = scope.get("sources")
    if not isinstance(sources, dict):
        raise ProjectContextError("active scope has no current source identities")
    return active, historical, focus, scope


def _validate_live_scope_projection(payload: dict[str, Any]) -> None:
    active = tuple(str(value) for value in payload.get("active_own_decks", []))
    historical = tuple(str(value) for value in payload.get("historical_own_decks", []))
    live_active = tuple(str(value) for value in payload.get("active_own_deck_ids", []))
    live_historical = tuple(str(value) for value in payload.get("inactive_former_own_deck_ids", []))
    if live_active != active or live_historical != historical:
        raise ProjectContextError("live active-deck projection contradicts itself")
    if payload.get("primary_active_own_deck_id") != payload.get("primary_deckbuilding_focus"):
        raise ProjectContextError("live active-deck projection has conflicting primary identities")


def _validate_playstyle(payload: dict[str, Any]) -> str:
    preference_type = payload.get("preference_type")
    if preference_type != "post_build_review_only":
        raise ProjectContextError("playstyle preference lost its post-build-only semantics")
    if payload.get("current_valid") is not True:
        raise ProjectContextError("playstyle preference is stale or not marked current-valid")
    prohibited_decision_signals = (
        "deckbuilding_bias_allowed",
        "screening_signal_allowed",
        "ranking_signal_allowed",
        "cut_or_package_filter_allowed",
        "finalist_signal_allowed",
        "simulation_budget_signal_allowed",
        "recommendation_status_signal_allowed",
    )
    if any(payload.get(field) is not False for field in prohibited_decision_signals):
        raise ProjectContextError(
            "playstyle preference can still affect an objective decision stage"
        )
    if payload.get("review_stage") != "after_objective_build_and_comparison_decision":
        raise ProjectContextError("playstyle review is not strictly post-build")
    explicitly_not = payload.get("explicitly_not")
    if not isinstance(explicitly_not, list):
        raise ProjectContextError("playstyle preference has no explicit non-ban boundary")
    required_non_bans = {
        "power_score",
        "archetype_ban",
        "ban_on_complexity",
        "ban_on_long_decisive_turns",
        "ban_on_engines_or_combos",
        "ban_on_sacrifice_elements",
    }
    if not required_non_bans.issubset({str(value) for value in explicitly_not}):
        raise ProjectContextError("playstyle preference lost a required evidence/usage boundary")
    return preference_type


def _validate_decision_registry(registry: dict[str, Any], active: tuple[str, ...]) -> None:
    policies = registry.get("deck_policies")
    if not isinstance(policies, dict):
        raise ProjectContextError("deck decision registry has no deck_policies mapping")
    missing = sorted(set(active) - {str(value) for value in policies})
    if missing:
        raise ProjectContextError(f"active decks are missing decision-registry policies: {missing}")


def _active_deck_hashes(
    root: Path, manifest: dict[str, Any], active: tuple[str, ...]
) -> tuple[tuple[tuple[str, str], ...], dict[str, Path]]:
    manifest_active = tuple(str(value) for value in manifest.get("active_own_decks", []))
    if manifest_active != active:
        raise ProjectContextError("deck manifest and live active-deck scope disagree")
    global_active = manifest.get("global_active_own_decks")
    if (
        not isinstance(global_active, list)
        or tuple(str(value) for value in global_active) != active
    ):
        raise ProjectContextError("global deck manifest and live active-deck scope disagree")
    decks = manifest.get("decks")
    if not isinstance(decks, dict):
        raise ProjectContextError("deck manifest has no deck identity mapping")
    unexpected_manifest_decks = sorted(set(str(value) for value in decks) - set(active))
    if unexpected_manifest_decks:
        raise ProjectContextError(
            "deck manifest contains non-active operational deck identities: "
            f"{unexpected_manifest_decks}"
        )
    identities: list[tuple[str, str]] = []
    deck_paths: dict[str, Path] = {}
    for deck_id in active:
        raw = decks.get(deck_id)
        if not isinstance(raw, dict):
            raise ProjectContextError(f"active deck is missing from deck manifest: {deck_id}")
        validation = raw.get("validation")
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            raise ProjectContextError(
                f"active deck is not marked valid in deck manifest: {deck_id}"
            )
        digest = raw.get("deck_hash")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ProjectContextError(f"active deck has invalid hash identity: {deck_id}")
        normalized_file = raw.get("normalized_file")
        if (
            not isinstance(normalized_file, str)
            or not normalized_file
            or Path(normalized_file).name != normalized_file
        ):
            raise ProjectContextError(f"active deck has unsafe normalized file: {deck_id}")
        deck_path = root / "data/decks" / normalized_file
        try:
            deck = Deck.model_validate(_load_json(deck_path))
        except ValueError as exc:
            raise ProjectContextError(f"active deck file is invalid: {deck_id}") from exc
        if deck.deck_id != deck_id:
            raise ProjectContextError(f"active deck file identity mismatch: {deck_id}")
        if deck.deck_hash != digest:
            raise ProjectContextError(f"active deck embedded hash mismatch: {deck_id}")
        if compute_deck_hash(deck) != digest:
            raise ProjectContextError(f"active deck content hash mismatch: {deck_id}")
        if raw.get("total_cards") != deck.total_cards:
            raise ProjectContextError(f"active deck total-card count mismatch: {deck_id}")
        if raw.get("library_cards") != deck.library_cards:
            raise ProjectContextError(f"active deck library-card count mismatch: {deck_id}")
        if tuple(raw.get("commanders", ())) != tuple(deck.commander.commanders):
            raise ProjectContextError(f"active deck commander identity mismatch: {deck_id}")
        identities.append((deck_id, digest))
        deck_paths[deck_id] = deck_path
    return tuple(identities), deck_paths


def _policy_config_hashes(root: Path) -> tuple[tuple[str, str], ...]:
    config_root = root / "config"
    if not config_root.is_dir():
        raise ProjectContextError("required policy/config directory is missing")
    paths = sorted(
        path
        for path in config_root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".yaml"}
    )
    if not paths:
        raise ProjectContextError("no policy/config identities are available")
    return tuple((path.relative_to(root).as_posix(), _sha256_file(path)) for path in paths)


def load_project_context(root: str | Path) -> ProjectContextSnapshot:
    root_path = Path(root).resolve()
    paths = {
        "active_scope": root_path / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json",
        "playstyle_preference": root_path
        / "data/collections/current/PLAYSTYLE_PREFERENCE_CURRENT.json",
        "inactive_deck_releases": root_path
        / "data/collections/current/INACTIVE_FORMER_OWN_DECK_RELEASES.json",
        "pod_scenarios": root_path / "data/collections/current/POD_SCENARIOS_CURRENT.json",
        "opponent_registry": root_path / "data/opponents/opponent_registry.json",
        "pilot_registry": root_path / "data/pilots/pilot_registry.json",
        "deck_manifest": root_path / "data/decks/manifest.json",
        "deck_decision_registry": root_path / "config/deck_decision_registry.json",
        "inventory_snapshot": root_path
        / "data/canonical_import/2026-08-07/inventory_snapshot.json",
        "allocation_snapshot": root_path / "data/collections/current_deck_allocations.json",
        "candidate_eligibility": root_path
        / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
        "feature_projection_manifest": root_path
        / "data/collections/current/rogshai_feature_projection/manifest.json",
        "protected_cards": root_path / "config/protected_cards.json",
    }
    source_hash_dict = {name: _sha256_file(path) for name, path in paths.items()}
    feature_manifest = _load_json(paths["feature_projection_manifest"])
    source_hash_dict.update(_feature_source_hashes(root_path, feature_manifest))

    active, historical, focus, scope = _load_scope(paths["active_scope"])
    _validate_live_scope_projection(scope)
    _validate_decision_registry(_load_json(paths["deck_decision_registry"]), active)
    playstyle = _load_json(paths["playstyle_preference"])
    playstyle_type = _validate_playstyle(playstyle)
    playstyle_hash = source_hash_dict["playstyle_preference"]

    scope_sources = scope["sources"]
    candidate_scope = scope_sources.get("ROGSHAI_CANDIDATE_POOL_CURRENT.jsonl")
    feature_sources = feature_manifest.get("source_artifacts")
    candidate_feature = (
        feature_sources.get("ROGSHAI_CANDIDATE_POOL_CURRENT.jsonl")
        if isinstance(feature_sources, dict)
        else None
    )
    if not isinstance(candidate_scope, dict) or not isinstance(candidate_feature, dict):
        raise ProjectContextError("candidate universe source identity is missing")
    if candidate_scope.get("sha256") != candidate_feature.get("sha256"):
        raise ProjectContextError(
            "active scope and feature projection disagree on candidate universe"
        )

    pods = _load_json(paths["pod_scenarios"])
    registry = _load_json(paths["opponent_registry"])
    freshness = {
        "active_scope_verified_at": str(scope.get("verified_at", "unknown")),
        "active_decks_generated_at": str(scope.get("generated_at", "unknown")),
        "pod_scenarios_generated_at": str(pods.get("generated_at", "unknown")),
        "playstyle_generated_at": str(playstyle.get("generated_at", "unknown")),
    }
    if "unknown" in freshness.values():
        raise ProjectContextError(
            "required synchronized project-context freshness metadata is missing"
        )

    frequency_policy = str(pods.get("frequency_policy", ""))
    if "No fixed opponent frequency" not in frequency_policy:
        raise ProjectContextError("canonical pod source lost its no-frequency-weights policy")

    raw_scenarios = pods.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise ProjectContextError("canonical pod source has no scenarios list")

    primary: dict[str, tuple[str, ...]] = {}
    primary_entities: dict[str, tuple[str, ...]] = {}
    historical_references: dict[str, tuple[str, ...]] = {}
    holdout: tuple[str, ...] | None = None
    for raw in raw_scenarios:
        if not isinstance(raw, dict):
            raise ProjectContextError("invalid scenario record")
        scenario_type = raw.get("scenario_type")
        if scenario_type in {
            "primary_four_player_context",
            "historical_reference_four_player_context",
        }:
            deck_id = raw.get("own_deck")
            entity_ids = raw.get("opponent_entity_ids")
            if not isinstance(deck_id, str) or not isinstance(entity_ids, list):
                raise ProjectContextError(
                    "four-player scenario is missing deck or opponent entities"
                )
            if raw.get("pod_size") != 4 or len(entity_ids) != 3:
                raise ProjectContextError("four-player scenario must contain exactly 3 opponents")
            normalized_entities = tuple(str(value) for value in entity_ids)
            resolved = _resolve_entities(list(normalized_entities), registry)
            if scenario_type == "primary_four_player_context":
                if deck_id in primary:
                    raise ProjectContextError(f"multiple canonical primary scenarios for {deck_id}")
                primary_entities[deck_id] = normalized_entities
                primary[deck_id] = resolved
            else:
                if deck_id in historical_references:
                    raise ProjectContextError(
                        f"multiple historical reference scenarios for {deck_id}"
                    )
                historical_references[deck_id] = resolved
        elif scenario_type == "opponent_pool_not_fixed_pod":
            entity_ids = raw.get("opponent_entity_ids")
            if not isinstance(entity_ids, list):
                raise ProjectContextError("holdout opponent pool has no entity ids")
            holdout = tuple(str(value) for value in entity_ids)

    missing_active = sorted(set(active) - set(primary))
    if missing_active:
        raise ProjectContextError(
            f"active own decks are missing primary scenarios: {missing_active}"
        )
    unexpected_primary = sorted(set(primary) - set(active))
    if unexpected_primary:
        raise ProjectContextError(
            f"current primary scenarios reference non-active own decks: {unexpected_primary}"
        )
    unexpected_historical = sorted(set(historical_references) - set(historical))
    if unexpected_historical:
        raise ProjectContextError(
            "historical reference scenarios reference non-historical own decks: "
            f"{unexpected_historical}"
        )
    if holdout is None:
        raise ProjectContextError("canonical holdout/sensitivity pool is missing")

    active_primary_entities = {
        entity_id for deck_id in active for entity_id in primary_entities.get(deck_id, ())
    }
    if active_primary_entities.intersection(holdout):
        raise ProjectContextError(
            "holdout opponent was silently promoted into active primary scenario"
        )

    holdout_decks = _resolve_entities(list(holdout), registry)
    deck_manifest = _load_json(paths["deck_manifest"])
    active_deck_hashes, active_deck_paths = _active_deck_hashes(root_path, deck_manifest, active)
    for deck_id, deck_path in active_deck_paths.items():
        source_hash_dict[f"active_deck:{deck_id}"] = _sha256_file(deck_path)
    policy_config_hashes = _policy_config_hashes(root_path)
    source_hashes = tuple(sorted(source_hash_dict.items()))
    source_freshness = tuple(sorted(freshness.items()))
    identity_payload = {
        "software_version": __version__,
        "engine_version": ENGINE_VERSION,
        "active_own_deck_ids": list(active),
        "historical_own_deck_ids": list(historical),
        "primary_deckbuilding_focus": focus,
        "active_deck_hashes": dict(active_deck_hashes),
        "policy_config_hashes": dict(policy_config_hashes),
        "source_hashes": dict(source_hashes),
        "source_freshness": dict(source_freshness),
        "primary_scenarios": {key: list(value) for key, value in sorted(primary.items())},
        "historical_reference_scenarios": {
            key: list(value) for key, value in sorted(historical_references.items())
        },
        "holdout_entity_ids": list(holdout),
        "holdout_deck_ids": list(holdout_decks),
        "playstyle_preference_type": playstyle_type,
        "playstyle_preference_hash": playstyle_hash,
    }
    snapshot_hash = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ProjectContextSnapshot(
        root=root_path,
        software_version=__version__,
        engine_version=ENGINE_VERSION,
        active_own_deck_ids=active,
        historical_own_deck_ids=historical,
        primary_deckbuilding_focus=focus,
        active_deck_hashes=active_deck_hashes,
        policy_config_hashes=policy_config_hashes,
        source_hashes=source_hashes,
        source_freshness=source_freshness,
        primary_scenarios=tuple(sorted(primary.items())),
        historical_reference_scenarios=tuple(sorted(historical_references.items())),
        holdout_entity_ids=holdout,
        holdout_deck_ids=holdout_decks,
        playstyle_preference_type=playstyle_type,
        playstyle_preference_hash=playstyle_hash,
        snapshot_hash=snapshot_hash,
    )
