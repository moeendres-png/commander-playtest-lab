from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from commander_lab.engine.structural.project import load_project_structural_decks
from commander_lab.models import StructuralDeckProfile
from commander_lab.models.opponents import OpponentEvidenceKind


class OpponentRepositoryError(ValueError):
    """Raised when current opponent truth is missing or contradictory."""


@dataclass(frozen=True, slots=True)
class CurrentOpponentRecord:
    registry_key: str
    deck_id: str
    evidence_kinds: tuple[OpponentEvidenceKind, ...]
    source_status: str
    frozen: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "registry_key": self.registry_key,
            "deck_id": self.deck_id,
            "evidence_kinds": [kind.value for kind in self.evidence_kinds],
            "source_status": self.source_status,
            "frozen": self.frozen,
        }


class CurrentOpponentRepository:
    """Single read-only runtime source for current opponent identities and evidence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.registry_path = self.root / "data/opponents/opponent_registry.json"
        try:
            raw = self.registry_path.read_bytes()
            registry = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpponentRepositoryError("cannot read current opponent registry") from exc
        current = registry.get("current")
        if not isinstance(current, dict) or not current:
            raise OpponentRepositoryError("current opponent registry is empty")
        if len(set(current.values())) != len(current):
            raise OpponentRepositoryError("current opponent registry resolves duplicate deck ids")
        self.registry_hash = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        self._registry = {str(key): str(value) for key, value in current.items()}
        self._evidence = self._load_evidence()
        all_decks = load_project_structural_decks(
            self.root,
            include_current_opponents=True,
            include_synthetic_fixtures=False,
        )
        missing = sorted(set(self._registry.values()) - set(all_decks))
        if missing:
            raise OpponentRepositoryError(
                f"current opponents lack structural representations: {missing}"
            )
        self._profiles = {deck_id: all_decks[deck_id] for deck_id in self._registry.values()}

    def _load_evidence(self) -> dict[str, tuple[tuple[OpponentEvidenceKind, ...], str]]:
        result: dict[str, tuple[tuple[OpponentEvidenceKind, ...], str]] = {}
        paths = [self.root / "data/opponents/current_structural_profiles.json"]
        paths.extend(sorted((self.root / "data/opponents").glob("*_structural_profile.json")))
        for path in paths:
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("profiles", [])
            if not isinstance(rows, list):
                raise OpponentRepositoryError(f"invalid opponent profile list: {path}")
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                deck_id = str(raw.get("deck_id", ""))
                if not deck_id:
                    continue
                kinds_raw = raw.get("evidence_kinds", [])
                kinds: list[OpponentEvidenceKind] = []
                if isinstance(kinds_raw, list):
                    for value in kinds_raw:
                        try:
                            kinds.append(OpponentEvidenceKind(str(value)))
                        except ValueError:
                            kinds.append(OpponentEvidenceKind.UNKNOWN)
                if not kinds:
                    kinds = [OpponentEvidenceKind.UNKNOWN]
                result[deck_id] = (
                    tuple(dict.fromkeys(kinds)),
                    str(raw.get("source_status", "unknown")),
                )
        return result

    def records(self) -> tuple[CurrentOpponentRecord, ...]:
        records: list[CurrentOpponentRecord] = []
        for key, deck_id in sorted(self._registry.items()):
            kinds, source_status = self._evidence.get(
                deck_id, ((OpponentEvidenceKind.UNKNOWN,), "unknown")
            )
            records.append(
                CurrentOpponentRecord(
                    registry_key=key,
                    deck_id=deck_id,
                    evidence_kinds=kinds,
                    source_status=source_status,
                    frozen=deck_id == "kaervek/current",
                )
            )
        return tuple(records)

    def current_deck_ids(self) -> tuple[str, ...]:
        return tuple(record.deck_id for record in self.records())

    def profiles(self) -> dict[str, StructuralDeckProfile]:
        return dict(self._profiles)

    def profile(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self._profiles[deck_id]
        except KeyError as exc:
            raise OpponentRepositoryError(f"not a current opponent: {deck_id}") from exc

    def evidence_by_deck_id(self) -> dict[str, tuple[str, ...]]:
        return {
            record.deck_id: tuple(kind.value for kind in record.evidence_kinds)
            for record in self.records()
        }
