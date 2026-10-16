"""The bridge jar is hashed once per batch, and again when the file changes."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from commander_lab.engine.rules import full_game_batch
from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import execution_identity_of


def _runner(tmp_path: Path, jar: Path) -> XmageFullGameRunner:
    return XmageFullGameRunner(("java", "-jar", str(jar), "full-game"), cwd=tmp_path)


def _count_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    reads: list[int] = []
    real = hashlib.sha256

    class Spy:
        def __init__(self, data: bytes = b"") -> None:
            reads.append(1)
            self._inner = real(data)

        def update(self, data: bytes) -> None:
            self._inner.update(data)

        def hexdigest(self) -> str:
            return self._inner.hexdigest()

    monkeypatch.setattr(full_game_batch.hashlib, "sha256", Spy)
    return reads


def test_repeated_identity_reads_the_jar_once_and_is_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"jar-bytes")
    runner = _runner(tmp_path, jar)
    expected = hashlib.sha256(b"jar-bytes").hexdigest()
    full_game_batch._ARTIFACT_DIGESTS.clear()
    reads = _count_reads(monkeypatch)

    identities = [execution_identity_of(runner) for _ in range(4)]

    # One artifact hash plus one runner-configuration digest per call.
    assert len(reads) == 1 + 4
    assert all(identity == identities[0] for identity in identities)
    assert identities[0]["bridge_artifacts"] == {"2": expected}


def test_a_changed_jar_is_hashed_again(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"first")
    runner = _runner(tmp_path, jar)
    full_game_batch._ARTIFACT_DIGESTS.clear()
    before = execution_identity_of(runner)

    jar.write_bytes(b"second-longer")  # new size
    after_size = execution_identity_of(runner)
    assert after_size["bridge_artifacts"] == {"2": hashlib.sha256(b"second-longer").hexdigest()}

    stat = jar.stat()
    jar.write_bytes(b"third-longer!")  # same size, new mtime
    os.utime(jar, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    after_mtime = execution_identity_of(runner)

    assert before != after_size != after_mtime
    assert after_mtime["bridge_artifacts"] == {"2": hashlib.sha256(b"third-longer!").hexdigest()}
