"""Start a simulated game from the Studio page.

The page chooses one of the owner's deck revisions, the other seats' decks and a seed. The
game itself runs in its own process (``python -m commander_lab.studio play``), so the page
stays usable and can follow the growing game log. This module holds only the light parts:
where the engine is, which decks can sit at the table, and the process start.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .decks import lab_snapshot
from .games import free_game_id, games_folder
from .store import StudioStore

ENGINE_COMMAND_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"
ENGINE_JAR = Path("engine") / "xmage-engine-bridge.jar"
MIN_SEATS, MAX_SEATS = 2, 6
START_WAIT_SECONDS = 20.0
MIN_WORKERS, MAX_WORKERS = 1, 16
MIN_GAMES_PER_JVM, MAX_GAMES_PER_JVM, DEFAULT_GAMES_PER_JVM = 1, 24, 6
POD_PRESETS: dict[str, tuple[str, str, str]] = {
    "precon": (
        "precon/2026/lorehold_spirit",
        "precon/2024/animated_army",
        "precon/2022/token_triumph",
    ),
    "mixed": (
        "kaervek/current",
        "precon/2024/animated_army",
        "precon/2026/lorehold_spirit",
    ),
    "optimized": (
        "precon/2023/eldrazi_unbound",
        "kaervek/current",
        "opponent/hosts-of-mordor-precon",
    ),
}
_EXTRA_OPPONENT_PATHS = (
    Path("data/decks/opponents/kaervek/current/deck.json"),
    Path("data/opponents/hosts_of_mordor_precon.json"),
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _java_executable() -> str | None:
    java = shutil.which("java") or shutil.which("java.exe")
    if java:
        return java
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.is_file():
            return str(candidate)
    return None


_JAVA_VERSION = re.compile(r'version "(\d+)(?:\.(\d+))?')
MIN_JAVA_MAJOR = 17


def _parse_java_major(version_output: str) -> int | None:
    """The major version from ``java -version`` output, or ``None`` when unreadable.

    Java 8 and older report ``1.8.0`` for major 8; from Java 9 the first number is the
    major version itself.
    """
    match = _JAVA_VERSION.search(version_output)
    if match is None:
        return None
    major = int(match.group(1))
    if major == 1 and match.group(2) is not None:
        return int(match.group(2))
    return major


def _java_major(java: str) -> int | None:
    # Deliberately uncached: the answer can change when the JDK at this path is replaced,
    # and a stale "too old" verdict would block legitimate starts until a Studio restart.
    try:
        run = subprocess.run(  # the resolved Java binary, fixed argument
            [java, "-version"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return _parse_java_major(f"{run.stderr}\n{run.stdout}")


def _java_too_old(java: str) -> int | None:
    """The found major version when it is known and below the minimum, else ``None``.

    An unreadable version is not treated as too old: the engine process then decides."""
    major = _java_major(java)
    return major if major is not None and major < MIN_JAVA_MAJOR else None


def engine_command(data_folder: str | Path) -> tuple[str, ...] | None:
    """How the rules engine is started here, or ``None`` when it is not set up.

    The environment names the command as for every full game of the Lab. Without it, the
    engine file in ``engine/`` of the Studio data folder is used when Java is installed.
    """
    raw = os.environ.get(ENGINE_COMMAND_ENV, "").strip()
    if raw:
        return tuple(shlex.split(raw, posix=(os.name != "nt")))
    jar = Path(data_folder) / ENGINE_JAR
    java = _java_executable()
    if jar.is_file() and java and _java_too_old(java) is None:
        return (java, "-Xmx3g", "-jar", str(jar), "full-game")
    return None


def default_workers() -> int:
    """Games a series plays at once unless told otherwise: ``min(4, cpu count - 1)``, at least 1."""
    return max(MIN_WORKERS, min(4, (os.cpu_count() or 1) - 1))


def checked_series_settings(workers: int | None, games_per_jvm: int | None) -> tuple[int, int]:
    """The series settings with their defaults; ``ValueError`` outside the allowed ranges."""
    used_workers = default_workers() if workers is None else workers
    used_batch = DEFAULT_GAMES_PER_JVM if games_per_jvm is None else games_per_jvm
    if not MIN_WORKERS <= used_workers <= MAX_WORKERS:
        raise ValueError(f"workers must be between {MIN_WORKERS} and {MAX_WORKERS}")
    if not MIN_GAMES_PER_JVM <= used_batch <= MAX_GAMES_PER_JVM:
        raise ValueError(
            f"games_per_jvm must be between {MIN_GAMES_PER_JVM} and {MAX_GAMES_PER_JVM}"
        )
    return used_workers, used_batch


@dataclass(frozen=True)
class SeriesEngine:
    """How a Studio series starts its bridge JVMs: the command and what it is made of."""

    command: tuple[str, ...]
    #: Every JVM option between the launcher and ``-jar`` (heap, serial GC, AppCDS, batch size).
    jvm_flags: tuple[str, ...]
    #: Games one bridge JVM plays before the next one starts; 1 when the launcher is not java.
    games_per_jvm: int
    serial_gc: bool
    appcds: bool


def _is_java_launcher(command: Sequence[str]) -> bool:
    return bool(command) and os.path.basename(command[0]).lower() in ("java", "javaw", "java.exe")


def series_engine(data_folder: str | Path, games_per_jvm: int) -> SeriesEngine | None:
    """The engine command of a series: fast JVM options and room for ``games_per_jvm`` games.

    The options come from the benchmark's helper ``fast_jvm_options`` (serial GC; the AppCDS
    archive only when ``<jar>.jsa`` exists next to the jar; the JVM itself ignores an archive that
    does not match the jar and says so on stderr). They change how the JVM runs, not a game. A
    launcher that is not java is used as it is, one game per process. ``None``: no engine.
    """
    from commander_lab.engine.rules.fast_jvm_options import fast_jvm_options
    from commander_lab.engine.rules.full_game_batch import command_with_games_per_jvm

    base = engine_command(data_folder)
    if base is None:
        return None
    if not _is_java_launcher(base) or "-jar" not in base or base.index("-jar") + 1 >= len(base):
        return SeriesEngine(base, (), 1, serial_gc=False, appcds=False)
    jar_at = base.index("-jar") + 1
    jar = Path(base[jar_at]).resolve()
    # a private card repository starts each JVM in a directory of its own: the jar path must
    # not depend on the working directory
    base = (*base[:jar_at], str(jar), *base[jar_at + 1 :])
    options = [option for option in fast_jvm_options(jar) if option not in base]
    command = command_with_games_per_jvm((base[0], *options, *base[1:]), games_per_jvm)
    flags = command[1 : command.index("-jar")]
    return SeriesEngine(
        command=command,
        jvm_flags=flags,
        games_per_jvm=games_per_jvm,
        serial_gc="-XX:+UseSerialGC" in flags,
        appcds=any(flag.startswith("-XX:SharedArchiveFile=") for flag in flags),
    )


def command_text(command: Sequence[str]) -> str:
    """``command`` as the one string ``COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD`` takes."""
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


@lru_cache(maxsize=16)
def _file_sha256_cached(path_str: str, mtime_ns: int, size: int) -> str:
    path = Path(path_str)
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _file_sha256(path: Path) -> str | None:
    try:
        stat = path.stat()
        return _file_sha256_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None


def engine_state(data_folder: str | Path) -> dict[str, object]:
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_xmage_engine_pin,
    )

    pin = canonical_xmage_engine_pin()
    jar = Path(data_folder) / ENGINE_JAR
    jar_path = str(jar) if jar.is_file() else None
    jar_sha256 = _file_sha256(jar) if jar.is_file() else None

    # Check companion pin file if present
    pin_file = jar.parent / "ENGINE_PIN.txt" if jar.is_file() else None
    recorded_pin = (
        pin_file.read_text(encoding="utf-8").strip() if pin_file and pin_file.is_file() else None
    )
    pin_matches = (recorded_pin == pin) if recorded_pin else None

    warning = None
    if recorded_pin and recorded_pin != pin:
        warning = (
            f"Die installierte Engine-Datei stammt von Pin {recorded_pin[:10]}, "
            f"erwartet wird jedoch {pin[:10]} aus config/rules_engines.json."
        )

    if engine_command(data_folder) is not None:
        return {
            "ready": True,
            "reason": "",
            "pin": pin,
            "jar_path": jar_path,
            "jar_sha256": jar_sha256,
            "recorded_pin": recorded_pin,
            "pin_matches": pin_matches if pin_matches is not None else True,
            "warning": warning,
            "command": list(engine_command(data_folder) or ()),
        }

    if not jar.is_file():
        return {
            "ready": False,
            "reason": f"Die Engine-Datei fehlt: {jar}",
            "pin": pin,
            "jar_path": None,
            "jar_sha256": None,
            "recorded_pin": None,
            "pin_matches": False,
            "warning": f"Engine-Datei fehlt unter {jar}",
            "command": None,
        }

    java = _java_executable()
    old_major = _java_too_old(java) if java else None
    if old_major is not None:
        too_old = (
            f"Java ist zu alt: gefunden wurde Version {old_major}, "
            f"nötig ist Java {MIN_JAVA_MAJOR} oder neuer."
        )
        return {
            "ready": False,
            "reason": too_old,
            "pin": pin,
            "jar_path": jar_path,
            "jar_sha256": jar_sha256,
            "recorded_pin": recorded_pin,
            "pin_matches": pin_matches,
            "java_version": old_major,
            "warning": too_old,
            "command": None,
        }

    return {
        "ready": False,
        "reason": "Java ist nicht installiert (Java 17 oder neuer).",
        "pin": pin,
        "jar_path": jar_path,
        "jar_sha256": jar_sha256,
        "recorded_pin": recorded_pin,
        "pin_matches": pin_matches,
        "warning": "Java 17 oder neuer fehlt im PATH.",
        "command": None,
    }


@lru_cache(maxsize=1)
def _precons() -> tuple[tuple[str, str, tuple[str, ...], str, Path], ...]:
    root = _repository_root()
    found: list[tuple[str, str, tuple[str, ...], str, Path]] = []
    candidate_paths = [
        *(root / rel for rel in _EXTRA_OPPONENT_PATHS),
        *sorted((root / "data" / "decks" / "precons").glob("*.json")),
    ]
    for path in candidate_paths:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            deck = raw.get("deck") if isinstance(raw.get("deck"), dict) else raw
            cmd_field = deck.get("commander")
            if isinstance(cmd_field, dict):
                commanders = tuple(str(name) for name in cmd_field["commanders"])
            elif isinstance(cmd_field, str) and cmd_field:
                commanders = (cmd_field,)
            else:
                continue
            year = str(
                deck.get("release_date")
                or deck.get("snapshot_date")
                or deck.get("data_as_of")
                or ""
            )[:4]
            found.append(
                (
                    str(deck["deck_id"]),
                    str(deck["name"]),
                    commanders,
                    year,
                    path,
                )
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return tuple(found)


def opponent_decks() -> list[dict[str, object]]:
    """The public preconstructed decks of the repository that can take a seat."""
    return [
        {"deck_id": deck_id, "name": name, "commanders": list(commanders), "year": year}
        for deck_id, name, commanders, year, _path in _precons()
    ]


def cards_unknown_to_pilots(snapshot: dict[str, object]) -> list[str]:
    """Card names of a deck snapshot the pilots' public card catalog has no entry for.

    The full-game runner refuses such a deck before the game starts (it cannot check the
    deck's construction); the page says which cards it is about.
    """
    from commander_lab.agents.card_knowledge import card_facts

    cards = snapshot.get("cards")
    names = sorted(
        {
            str(card.get("oracle_name"))
            for card in (cards if isinstance(cards, list) else [])
            if isinstance(card, dict)
        }
    )
    return [name for name in names if card_facts(name) is None]


def cards_unsupported_by_engine(snapshot: dict[str, object]) -> list[str]:
    """Card names of a deck snapshot that the pinned XMage rules engine does not know or support.

    Detects missing engine cards pre-flight before `import_deck` fails.
    """
    from commander_lab.studio.builder import sim_readiness_status

    cards = snapshot.get("cards")
    names = sorted(
        {
            str(card.get("oracle_name") or card.get("name") or "")
            for card in (cards if isinstance(cards, list) else [])
            if isinstance(card, dict)
        }
    )
    unsupported: list[str] = []
    for name in names:
        if not name:
            continue
        status = sim_readiness_status(name)
        if status in {"KNOWN_MISSING_IN_XMAGE", "NO_CARD_FACTS"}:
            unsupported.append(name)
    return unsupported


def collection_cards_unknown_to_pilots(store: StudioStore) -> list[str]:
    """Find all cards in the studio collection that are missing from the pilots' card knowledge catalog."""
    from commander_lab.agents.card_knowledge import card_facts

    rows = store.connection.execute(
        "SELECT DISTINCT oracle_name FROM card ORDER BY oracle_name"
    ).fetchall()
    missing: list[str] = []
    for r in rows:
        name = str(r["oracle_name"])
        if card_facts(name) is None:
            missing.append(name)
    return missing


def collection_cards_unsupported_by_engine(store: StudioStore) -> list[str]:
    """Find all cards in the studio collection that the pinned XMage engine does not know."""
    from commander_lab.studio.builder import sim_readiness_status

    rows = store.connection.execute(
        "SELECT DISTINCT oracle_name FROM card ORDER BY oracle_name"
    ).fetchall()
    unsupported: list[str] = []
    for r in rows:
        name = str(r["oracle_name"])
        status = sim_readiness_status(name)
        if status in {"KNOWN_MISSING_IN_XMAGE", "NO_CARD_FACTS"}:
            unsupported.append(name)
    return unsupported


def start_game(
    store: StudioStore,
    data_folder: str | Path,
    *,
    revision_id: str,
    opponent_ids: list[str],
    seed: int,
    style: float | None = None,
    seat_styles: Sequence[float] | None = None,
) -> str:
    """Start the game process and return the id of the game it records.

    Seat 1 is the owner's deck revision, written as a deck snapshot next to the game logs
    (it stays in the Studio data folder). Raises ``KeyError`` for an unknown revision or
    opponent and ``RuntimeError`` when the engine is not set up.
    """
    if not MIN_SEATS - 1 <= len(opponent_ids) <= MAX_SEATS - 1:
        raise ValueError("a game has one to five other seats")
    if len(set(opponent_ids)) != len(opponent_ids):
        raise ValueError("every seat needs its own deck")
    if engine_command(data_folder) is None:
        raise RuntimeError(str(engine_state(data_folder)["reason"]))
    paths = {deck_id: path for deck_id, _name, _commanders, _year, path in _precons()}
    opponents = [paths[deck_id] for deck_id in opponent_ids]
    snapshot = lab_snapshot(store, revision_id)
    engine_unsupported = cards_unsupported_by_engine(snapshot)
    if engine_unsupported:
        raise ValueError(
            "Die Regeln-Engine XMage unterstützt diese Karten noch nicht: "
            + ", ".join(engine_unsupported[:8])
        )
    unknown = cards_unknown_to_pilots(snapshot)
    if unknown:
        raise ValueError(
            "Das Kartenwissen der KI kennt diese Karten noch nicht: " + ", ".join(unknown[:8])
        )
    deck_folder = games_folder(data_folder) / "decks"
    deck_folder.mkdir(exist_ok=True)
    own = deck_folder / (revision_id.replace("@", "-").replace("/", "-") + ".json")
    own.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    seats = len(opponents) + 1
    game_id = free_game_id(data_folder, f"{snapshot['deck_id']}-{seats}p-seed{seed}")
    command = [
        sys.executable, "-m", "commander_lab.studio", "--data", str(Path(data_folder)),
        "play", "--seed", str(seed), "--game-id", game_id, "--deck", str(own),
    ]  # fmt: skip
    for path in opponents:
        command += ["--deck", str(path)]
    if style is not None:
        command += ["--style", str(style)]
    if seat_styles:
        for idx, s in enumerate(seat_styles, start=1):
            command += ["--seat-style", f"{idx}:{s}"]
    folder = games_folder(data_folder)
    with (folder / f"{game_id}.out").open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            command, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
        )
    # the page opens the game right away: wait until its log exists
    deadline = time.monotonic() + START_WAIT_SECONDS
    while time.monotonic() < deadline:
        if any(folder.glob(f"{game_id}.jsonl*")):
            return game_id
        if process.poll() is not None:
            break
        time.sleep(0.2)
    if any(folder.glob(f"{game_id}.jsonl*")):
        return game_id
    out_file = folder / f"{game_id}.out"
    detail = ""
    if out_file.is_file():
        with contextlib.suppress(OSError):
            detail = out_file.read_text(encoding="utf-8", errors="replace").strip()
    if detail:
        tail = "\n".join(detail.splitlines()[-5:])
        raise RuntimeError(f"Die Partie konnte nicht gestartet werden: {tail}")
    raise RuntimeError("Die Partie konnte nicht gestartet werden.")
