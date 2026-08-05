from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from commander_lab.models import (
    EvidenceSplit,
    PlaytestDatasetManifest,
    RealPlaytest,
    SplitStrategy,
)

from .atomic import atomic_write_json
from .hashing import sha256_value


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PlaytestConflictError(RuntimeError):
    pass


class PlaytestRepository:
    """Versioned, append-only storage for real playtest evidence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.base = self.root / "data" / "playtests" / "datasets"

    @staticmethod
    def _safe_identifier(value: str, *, label: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"invalid {label}: {value!r}")
        return value

    def dataset_directory(self, dataset_version: str) -> Path:
        safe = self._safe_identifier(dataset_version, label="dataset_version")
        return self.base / safe

    def ingest(
        self,
        games: Iterable[RealPlaytest],
        *,
        dataset_version: str,
    ) -> PlaytestDatasetManifest:
        dataset_version = self._safe_identifier(dataset_version, label="dataset_version")
        directory = self.dataset_directory(dataset_version)
        games_directory = directory / "games"
        games_directory.mkdir(parents=True, exist_ok=True)

        existing = self.load_manifest(dataset_version, required=False)
        game_hashes = dict(existing.game_hashes) if existing else {}
        source_files = set(existing.source_files if existing else ())
        now = datetime.now(UTC)

        for imported in games:
            game = imported.model_copy(deep=True)
            game.dataset_version = dataset_version
            game_hash = self.game_hash(game)
            game_id = self._safe_identifier(game.game_id, label="game_id")
            destination = games_directory / f"{game_id}.json"
            if existing and existing.split_sealed_at is not None and game_id not in existing.game_ids:
                raise PlaytestConflictError(
                    "the dataset split is already sealed; append new games under a new dataset version"
                )
            if destination.exists():
                current = RealPlaytest.model_validate(json.loads(destination.read_text(encoding="utf-8")))
                current_hash = self.game_hash(current)
                if current_hash != game_hash:
                    raise PlaytestConflictError(
                        f"game_id {game_id!r} already exists with different content; "
                        "create a new dataset version rather than overwriting evidence"
                    )
            else:
                atomic_write_json(destination, game.model_dump(mode="json"))
            game_hashes[game_id] = game_hash
            if game.source_file:
                source_files.add(game.source_file)

        loaded = self.load_games(dataset_version)
        data_hash = sha256_value(
            {game_id: game_hashes[game_id] for game_id in sorted(game_hashes)}
        )
        manifest = PlaytestDatasetManifest(
            dataset_id=f"real-playtests/{dataset_version}",
            dataset_version=dataset_version,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            game_ids=tuple(sorted(game_hashes)),
            game_hashes={game_id: game_hashes[game_id] for game_id in sorted(game_hashes)},
            data_hash=data_hash,
            source_files=tuple(sorted(source_files)),
            validated_games=sum(game.validated and not game.excluded_reason for game in loaded),
            excluded_games=sum(bool(game.excluded_reason) for game in loaded),
            split_strategy=existing.split_strategy if existing else None,
            split_seed=existing.split_seed if existing else None,
            train_fraction=existing.train_fraction if existing else None,
            split_assignments=existing.split_assignments if existing else {},
            split_sealed_at=existing.split_sealed_at if existing else None,
        )
        atomic_write_json(directory / "manifest.json", manifest.model_dump(mode="json"))
        return manifest

    def load_manifest(
        self,
        dataset_version: str,
        *,
        required: bool = True,
    ) -> PlaytestDatasetManifest | None:
        path = self.dataset_directory(dataset_version) / "manifest.json"
        if not path.exists():
            if required:
                raise FileNotFoundError(path)
            return None
        return PlaytestDatasetManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def load_games(self, dataset_version: str) -> list[RealPlaytest]:
        directory = self.dataset_directory(dataset_version) / "games"
        if not directory.exists():
            return []
        games = [
            RealPlaytest.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(directory.glob("*.json"))
        ]
        manifest = self.load_manifest(dataset_version, required=False)
        if manifest and manifest.split_assignments:
            for game in games:
                game.evidence_split = manifest.split_assignments.get(
                    game.game_id, EvidenceSplit.UNSPLIT
                )
        return games

    def seal_split(
        self,
        dataset_version: str,
        *,
        assignments: dict[str, EvidenceSplit],
        strategy: SplitStrategy,
        seed: int,
        train_fraction: float,
    ) -> PlaytestDatasetManifest:
        manifest = self.load_manifest(dataset_version)
        unknown = set(assignments) - set(manifest.game_ids)
        if unknown:
            raise ValueError(f"split references unknown games: {sorted(unknown)}")
        expected = {
            game_id: assignments.get(game_id, EvidenceSplit.EXCLUDED)
            for game_id in manifest.game_ids
        }
        if manifest.split_sealed_at is not None:
            if (
                manifest.split_strategy != strategy
                or manifest.split_seed != seed
                or manifest.train_fraction != train_fraction
                or manifest.split_assignments != expected
            ):
                raise PlaytestConflictError(
                    "the dataset split is already sealed; create a new dataset version to change it"
                )
            return manifest

        updated = manifest.model_copy(
            update={
                "updated_at": datetime.now(UTC),
                "split_strategy": strategy,
                "split_seed": seed,
                "train_fraction": train_fraction,
                "split_assignments": expected,
                "split_sealed_at": datetime.now(UTC),
            }
        )
        atomic_write_json(
            self.dataset_directory(dataset_version) / "manifest.json",
            updated.model_dump(mode="json"),
        )
        return updated

    @staticmethod
    def game_hash(game: RealPlaytest) -> str:
        payload = game.model_dump(
            mode="json",
            exclude={
                "imported_at",
                "evidence_split",
                "source_file",
                "source_sha256",
            },
        )
        return sha256_value(payload)
