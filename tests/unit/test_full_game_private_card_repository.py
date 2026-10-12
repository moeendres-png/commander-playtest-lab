"""#739: parallel bridge JVMs get their own copy of XMage's card repository.

XMage opens ``./db/cards.h2`` relative to the process working directory with
``AUTO_SERVER``; JVMs starting together in one directory collided while
scanning it (XMAGE_CARD_REPOSITORY_INIT_FAILED). A client in private mode
spawns its JVM in its own directory with a copy of the shared repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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


def test_parallel_clients_run_in_distinct_private_copies(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=True)
    first = _spawn(shared, tmp_path / "a.json", private=True)
    second = _spawn(shared, tmp_path / "b.json", private=True)

    for seen in (first, second):
        cwd = Path(str(seen["cwd"]))
        assert cwd.parent == (shared / PRIVATE_ENGINE_DIRECTORY).resolve()
        assert seen["repository"] is True, "the shared repository was copied in"
        assert not cwd.exists(), "the private directory is removed after the game"
    assert first["cwd"] != second["cwd"]
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
    assert not private.exists()


def test_a_killed_jvms_repository_is_never_promoted(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=False)
    client, private = _private_client(shared)
    (private / "db").mkdir()
    (private / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"half-written")

    client._release_private_directory(FULL_GAME_SHUTDOWN_FORCED_KILL)

    assert not (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).exists()
    assert not private.exists()


def test_an_existing_shared_repository_is_never_replaced(tmp_path: Path) -> None:
    shared = _shared(tmp_path, built=True)
    client, private = _private_client(shared)
    (private / "db" / XMAGE_CARD_REPOSITORY_FILE).write_bytes(b"private-copy")

    client._release_private_directory(FULL_GAME_SHUTDOWN_GRACEFUL)

    assert (shared / "db" / XMAGE_CARD_REPOSITORY_FILE).read_bytes() == b"shared-repository"
    assert not private.exists()


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
