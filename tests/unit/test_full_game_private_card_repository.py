"""#739: parallel bridge JVMs get their own copy of XMage's card repository.

XMage opens ``./db/cards.h2`` relative to the process working directory with
``AUTO_SERVER``; JVMs starting together in one directory collided while
scanning it (XMAGE_CARD_REPOSITORY_INIT_FAILED). A client in private mode
spawns its JVM in its own directory with a copy of the shared repository.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from commander_lab.engine.rules import full_game
from commander_lab.engine.rules.full_game import (
    FULL_GAME_SHUTDOWN_FORCED_KILL,
    FULL_GAME_SHUTDOWN_GRACEFUL,
    PRIVATE_ENGINE_DIRECTORY,
    XMAGE_CARD_REPOSITORY_FILE,
    XmageFullGameRunner,
    _RawFullGameClient,
)
from commander_lab.engine.rules.full_game_batch import (
    XmageFullGameBatchRunner,
    execution_identity_of,
)

_RECORD_CWD = (
    "import json, os, sys; "
    "json.dump({'cwd': os.getcwd(), "
    f"'repository': os.path.isfile(os.path.join('db', '{XMAGE_CARD_REPOSITORY_FILE}'))}}, "
    "open(sys.argv[2], 'w'))"
)


def _shared(tmp_path: Path, *, built: bool) -> Path:
    shared = tmp_path / "engine"
    (shared / "db").mkdir(parents=True)
    if built:
        (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"shared-repository")
    return shared


def _spawn(shared: Path, out: Path, *, private: bool) -> dict[str, object]:
    client = _RawFullGameClient(
        (sys.executable, "-c", _RECORD_CWD, "full-game", str(out)),
        cwd=shared,
        private_card_repository=private,
    )
    client.start()
    assert client._process is not None
    client._process.wait(timeout=30)
    seen = json.loads(out.read_text(encoding="utf-8"))
    client.close()
    return seen


def test_sequential_clients_reuse_one_private_slot(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=True)
    first = _spawn(shared, tmp_path / "a.json", private=True)
    second = _spawn(shared, tmp_path / "b.json", private=True)

    for seen in (first, second):
        cwd = Path(str(seen["cwd"]))
        assert cwd.parent == (shared / PRIVATE_ENGINE_DIRECTORY).resolve()
        assert seen["repository"] is True, "the shared repository was copied in"
        assert cwd.name == "slot-0", "a finished game frees its slot for the next one"
    assert first["cwd"] == second["cwd"]
    assert (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).read_bytes() == b"shared-repository"


def test_default_client_keeps_the_shared_directory(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=True)
    seen = _spawn(shared, tmp_path / "a.json", private=False)
    assert Path(str(seen["cwd"])) == shared.resolve()


def _private_client(shared: Path) -> tuple[_RawFullGameClient, Path]:
    client = _RawFullGameClient(
        ("java", "-jar", "bridge.jar", "full-game"), cwd=shared, private_card_repository=True
    )
    private = Path(str(client._prepare_private_directory()))
    return client, private


def test_a_gracefully_built_private_repository_becomes_the_shared_one(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=False)
    client, private = _private_client(shared)
    assert not (private / "db").exists(), "no shared repository to copy yet"
    (private / "db").mkdir()
    (private / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"built")

    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    assert (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).read_bytes() == b"built"
    assert not (private / "db").exists(), "the promoted repository left the slot"


def test_a_killed_jvms_repository_is_never_promoted(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=False)
    client, private = _private_client(shared)
    (private / "db").mkdir()
    (private / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"half-written")

    client._release_private_directory(FULL_GAME_SHUTDOWN_FORCED_KILL)

    assert not (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).exists()
    assert not (private / "db").exists(), "a killed JVM's files are dropped"


def test_an_existing_shared_repository_is_never_replaced(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=True)
    client, private = _private_client(shared)
    (private / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"private-copy")

    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    assert (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).read_bytes() == b"shared-repository"


def test_parallel_batch_games_use_private_repositories_without_new_identity(
    tmp_path: Path,
) -> None:
    runner = XmageFullGameRunner(("java", "-jar", "bridge.jar", "full-game"), cwd=tmp_path)
    batch = XmageFullGameBatchRunner(runner, tmp_path / "out")

    parallel = batch._parallel_runner()

    assert parallel.private_card_repository is True
    assert runner.private_card_repository is False, "the caller's runner is unchanged"
    # The bridge jar does not exist here, so compare the configuration digest
    # through a stand-in that hashes nothing.
    stand_in = XmageFullGameRunner(("java", "full-game"), cwd=tmp_path)
    copy = XmageFullGameRunner(("java", "full-game"), cwd=tmp_path, private_card_repository=True)
    assert execution_identity_of(stand_in) == execution_identity_of(copy)


def _slot_client(shared: Path) -> _RawFullGameClient:
    return _RawFullGameClient(
        ("java", "-jar", "bridge.jar", "full-game"), cwd=shared, private_card_repository=True
    )


def test_six_games_on_two_workers_copy_the_repository_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = _shared(tmp_path, built=True)
    copies: list[Path] = []
    real_copy = full_game._copy_card_repository

    def spy(source: Path, destination: Path) -> None:
        copies.append(destination)
        real_copy(source, destination)

    monkeypatch.setattr(full_game, "_copy_card_repository", spy)
    barrier = threading.Barrier(2)

    def worker(_: int) -> list[str]:
        slots = []
        for game in range(3):
            client = _slot_client(shared)
            slots.append(Path(str(client._prepare_private_directory())).name)
            if game == 0:
                barrier.wait(timeout=30)  # both workers hold a slot at once
            client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)
        return slots

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))

    assert len(copies) == 2 and len(set(copies)) == 2
    assert {slot for slots in results for slot in slots} == {"slot-0", "slot-1"}


def test_a_slot_is_copied_again_only_when_missing_or_the_shared_repository_changed(
    tmp_path: Path,
) -> None:
    shared = _shared(tmp_path, built=True)
    client = _slot_client(shared)
    slot = Path(str(client._prepare_private_directory()))
    slot_file = slot / "db" / XMAGE_CARD_REPOSITORY_FILE
    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    # H2 rewrites its file when the game closes it: the slot stays in use.
    slot_file.write_bytes(b"closed by the engine")
    client = _slot_client(shared)
    client._prepare_private_directory()
    assert slot_file.read_bytes() == b"closed by the engine"
    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    # A new shared repository replaces the slot's copy.
    (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"rebuilt-repository")
    client = _slot_client(shared)
    client._prepare_private_directory()
    assert slot_file.read_bytes() == b"rebuilt-repository"
    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    slot_file.unlink()
    client = _slot_client(shared)
    client._prepare_private_directory()
    assert slot_file.read_bytes() == b"rebuilt-repository"
    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)


def test_orphans_older_than_a_day_are_removed_and_slots_and_young_ones_kept(
    tmp_path: Path,
) -> None:
    shared = _shared(tmp_path, built=True)
    root = shared / PRIVATE_ENGINE_DIRECTORY
    old, young, slot, other = (root / name for name in ("a" * 32, "b" * 32, "slot-7", "keep-me"))
    for directory in (old, young, slot, other):
        (directory / "db").mkdir(parents=True)
    # Anchor "now" and "young" to the same clock the cleanup reads (time.time), not to the file
    # system's, so the test means the same on any date.
    now = time.time()
    two_days_ago = now - 2 * 24 * 3600
    for directory in (old, slot, other):
        os.utime(directory, (two_days_ago, two_days_ago))
    os.utime(young, (now, now))

    client = _slot_client(shared)
    client._prepare_private_directory()
    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    assert not old.exists()
    assert young.exists() and slot.exists() and other.exists()


def test_concurrent_holders_get_different_slots_until_released(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=True)
    first, second = _slot_client(shared), _slot_client(shared)
    one = Path(str(first._prepare_private_directory()))
    two = Path(str(second._prepare_private_directory()))
    assert one != two

    first._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)
    third = _slot_client(shared)
    assert Path(str(third._prepare_private_directory())) == one, "the freed slot is reused"
    second._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)
    third._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)
