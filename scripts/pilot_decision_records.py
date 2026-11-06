"""Compressed, append-only decision records backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
import zlib
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, overload


class RecordStoreError(RuntimeError):
    """A record could not be persisted or retrieved."""


class DiskRecords(Sequence[dict[str, Any]]):
    """Store snapshots of records, committing bounded batches and on close."""

    def __init__(self, path: Path, *, batch_size: int = 100) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, value BLOB NOT NULL)"
        )
        self._count = self._db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        self._batch_size = batch_size
        self._pending = 0

    def append(self, value: dict[str, Any]) -> None:
        try:
            raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
            self._db.execute(
                "INSERT INTO records VALUES (?, ?)", (self._count, zlib.compress(raw, 3))
            )
            self._count += 1
            self._pending += 1
            if self._pending >= self._batch_size:
                self.commit()
        except (sqlite3.Error, TypeError, ValueError, zlib.error) as exc:
            raise RecordStoreError("could not store decision record") from exc

    def commit(self) -> None:
        try:
            self._db.commit()
            self._pending = 0
        except sqlite3.Error as exc:
            raise RecordStoreError("could not commit decision records") from exc

    def close(self) -> None:
        try:
            self.commit()
        finally:
            self._db.close()

    def __enter__(self) -> DiskRecords:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __len__(self) -> int:
        return self._count

    @staticmethod
    def _decode(raw: bytes) -> dict[str, Any]:
        return json.loads(zlib.decompress(raw))

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for (raw,) in self._db.execute("SELECT value FROM records ORDER BY id"):
            yield self._decode(raw)

    @overload
    def __getitem__(self, index: int) -> dict[str, Any]: ...

    @overload
    def __getitem__(self, index: slice) -> list[dict[str, Any]]: ...

    def __getitem__(self, index: int | slice) -> dict[str, Any] | list[dict[str, Any]]:
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        row = self._db.execute("SELECT value FROM records WHERE id = ?", (index,)).fetchone()
        if row is None:
            raise RecordStoreError(f"missing decision record {index}")
        return self._decode(row[0])


class IndexedRecords(Sequence[dict[str, Any]]):
    """A reusable view whose indices are relative to the selected records."""

    def __init__(self, records: Sequence[dict[str, Any]], indices: list[int]) -> None:
        self._records = records
        self._indices = indices

    def __len__(self) -> int:
        return len(self._indices)

    @overload
    def __getitem__(self, index: int) -> dict[str, Any]: ...

    @overload
    def __getitem__(self, index: slice) -> list[dict[str, Any]]: ...

    def __getitem__(self, index: int | slice) -> dict[str, Any] | list[dict[str, Any]]:
        if isinstance(index, slice):
            return [self._records[i] for i in self._indices[index]]
        return self._records[self._indices[index]]
