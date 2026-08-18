from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from commander_lab.models import Color


class DeckRegistryError(ValueError):
    """Raised when deck decision routing/policy data is missing or contradictory."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DeckRegistryError(f"required deck-registry input is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeckRegistryError(f"invalid deck-registry JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise DeckRegistryError(f"deck-registry JSON must be an object: {path}")
    return payload


def _safe_relative_path(root: Path, value: object, *, field: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value.strip():
        raise DeckRegistryError(f"deck-registry path is missing: {field}")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise DeckRegistryError(f"unsafe deck-registry path for {field}: {value}")
    resolved = (root / relative).resolve()
    if root != resolved and root not in resolved.parents:
        raise DeckRegistryError(f"deck-registry path escapes project root: {field}")
    return relative.as_posix(), resolved


@dataclass(frozen=True, slots=True)
class DeckDecisionPolicy:
    deck_id: str
    commander_identity: frozenset[Color]
    feature_projection_manifest: str | None = None
    package_prefixes: tuple[str, ...] = ()

    def package_id_allowed(self, package_id: str) -> bool:
        return bool(self.package_prefixes) and any(
            package_id.startswith(prefix) for prefix in self.package_prefixes
        )


class DeckPolicyRegistry:
    """Read-only routing registry for active own-deck decision inputs.

    Activation is derived from the configured live-scope source. Registry configuration only
    routes sources/policies; it never activates a deck, reserves inventory, or mutates canonical
    project data.
    """

    CONFIG_PATH = "config/deck_decision_registry.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.config_path = self.root / self.CONFIG_PATH
        self.config = _load_json(self.config_path)

        sources = self.config.get("sources")
        if not isinstance(sources, dict):
            raise DeckRegistryError("deck decision registry has no sources mapping")
        self._source_specs = {str(key): value for key, value in sources.items()}

        scope = _load_json(self.source_path("active_scope"))
        active_raw = scope.get("active_own_decks")
        if not isinstance(active_raw, list) or not active_raw:
            raise DeckRegistryError("live scope contains no active own decks")
        active = tuple(str(value) for value in active_raw)
        if len(active) != len(set(active)):
            raise DeckRegistryError("live scope contains duplicate active own deck ids")
        self.active_deck_ids = active

        historical_raw = scope.get("historical_own_decks", ())
        self.historical_deck_ids = (
            tuple(str(value) for value in historical_raw)
            if isinstance(historical_raw, list)
            else ()
        )
        frozen_raw = scope.get("frozen_opponent_only_decks", ())
        self.frozen_opponent_ids = (
            frozenset(str(value) for value in frozen_raw)
            if isinstance(frozen_raw, list)
            else frozenset()
        )

        primary = scope.get("primary_deckbuilding_focus") or scope.get("primary_active_own_deck_id")
        self.primary_deck_id = str(primary) if primary else active[0]
        if self.primary_deck_id not in self.active_deck_ids:
            raise DeckRegistryError(
                f"primary deck is not active in live scope: {self.primary_deck_id}"
            )

        manifest = _load_json(self.source_path("deck_manifest"))
        manifest_decks = manifest.get("decks")
        if not isinstance(manifest_decks, dict):
            raise DeckRegistryError("deck manifest has no decks mapping")

        policy_rows = self.config.get("deck_policies", {})
        if not isinstance(policy_rows, dict):
            raise DeckRegistryError("deck decision registry deck_policies must be an object")

        policies: dict[str, DeckDecisionPolicy] = {}
        for deck_id in self.active_deck_ids:
            raw_deck = manifest_decks.get(deck_id)
            if not isinstance(raw_deck, dict):
                raise DeckRegistryError(f"active own deck is missing from manifest: {deck_id}")
            validation = raw_deck.get("validation")
            metrics = validation.get("metrics") if isinstance(validation, dict) else None
            raw_identity = metrics.get("commander_identity") if isinstance(metrics, dict) else None
            if not isinstance(raw_identity, list):
                raise DeckRegistryError(
                    f"active own deck has no commander_identity metadata: {deck_id}"
                )
            try:
                commander_identity = frozenset(Color(str(value)) for value in raw_identity)
            except ValueError as exc:
                raise DeckRegistryError(
                    f"invalid commander_identity metadata for {deck_id}: {raw_identity}"
                ) from exc

            raw_policy = policy_rows.get(deck_id, {})
            if not isinstance(raw_policy, dict):
                raise DeckRegistryError(f"deck policy must be an object: {deck_id}")
            raw_projection = raw_policy.get("feature_projection_manifest")
            projection: str | None = None
            if raw_projection is not None:
                projection, projection_path = _safe_relative_path(
                    self.root,
                    raw_projection,
                    field=f"deck_policies.{deck_id}.feature_projection_manifest",
                )
                feature_manifest = _load_json(projection_path)
                if feature_manifest.get("deck_id") != deck_id:
                    raise DeckRegistryError(
                        f"feature projection deck_id mismatch for {deck_id}: "
                        f"{feature_manifest.get('deck_id')}"
                    )

            raw_prefixes = raw_policy.get("package_prefixes", ())
            if not isinstance(raw_prefixes, list):
                raise DeckRegistryError(f"package_prefixes must be a list: {deck_id}")
            prefixes = tuple(str(value) for value in raw_prefixes if str(value))
            if len(prefixes) != len(set(prefixes)):
                raise DeckRegistryError(f"duplicate package prefix for {deck_id}")

            policies[deck_id] = DeckDecisionPolicy(
                deck_id=deck_id,
                commander_identity=commander_identity,
                feature_projection_manifest=projection,
                package_prefixes=prefixes,
            )
        self._policies = policies

    def source_path(self, source_name: str, *, required: bool = True) -> Path:
        value = self._source_specs.get(source_name)
        if value is None:
            if required:
                raise DeckRegistryError(f"deck-registry source is not configured: {source_name}")
            return self.root / "__missing_optional_source__"
        _relative, resolved = _safe_relative_path(self.root, value, field=f"sources.{source_name}")
        if required and not resolved.is_file():
            raise DeckRegistryError(
                f"configured deck-registry source is missing: {source_name} -> {resolved}"
            )
        return resolved

    def source_relative_path(self, source_name: str) -> str:
        value = self._source_specs.get(source_name)
        relative, _resolved = _safe_relative_path(self.root, value, field=f"sources.{source_name}")
        return relative

    def source_hash(self, source_name: str, *, required: bool = True) -> str | None:
        path = self.source_path(source_name, required=required)
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def assert_active(self, deck_id: str) -> None:
        if deck_id not in self._policies:
            raise DeckRegistryError(f"deck is not an active own-deck decision target: {deck_id}")

    def policy(self, deck_id: str) -> DeckDecisionPolicy:
        self.assert_active(deck_id)
        return self._policies[deck_id]

    def commander_identity(self, deck_id: str) -> frozenset[Color]:
        return self.policy(deck_id).commander_identity

    def feature_manifest_path(self, deck_id: str) -> Path | None:
        policy = self.policy(deck_id)
        if policy.feature_projection_manifest is None:
            return None
        _relative, path = _safe_relative_path(
            self.root,
            policy.feature_projection_manifest,
            field=f"deck_policies.{deck_id}.feature_projection_manifest",
        )
        if not path.is_file():
            raise DeckRegistryError(f"feature projection is missing for {deck_id}: {path}")
        return path

    def as_dict(self) -> dict[str, object]:
        return {
            "active_deck_ids": list(self.active_deck_ids),
            "historical_deck_ids": list(self.historical_deck_ids),
            "frozen_opponent_ids": sorted(self.frozen_opponent_ids),
            "primary_deck_id": self.primary_deck_id,
            "policies": {
                deck_id: {
                    "commander_identity": sorted(
                        color.value for color in policy.commander_identity
                    ),
                    "feature_projection_manifest": policy.feature_projection_manifest,
                    "package_prefixes": list(policy.package_prefixes),
                }
                for deck_id, policy in sorted(self._policies.items())
            },
            "truth_boundary": (
                "routing_and_policy_only; activation comes from live scope and no canonical "
                "deck/inventory/allocation mutation is performed"
            ),
        }


def load_deck_policy_registry(root: str | Path) -> DeckPolicyRegistry:
    return DeckPolicyRegistry(root)


__all__ = [
    "DeckDecisionPolicy",
    "DeckPolicyRegistry",
    "DeckRegistryError",
    "load_deck_policy_registry",
]
