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
MIN_SEATS, MAX_SEATS = 2, 6  # what the engine can seat (series and the CLI comparison use this)
# What the Studio lets someone start (PLAY, watched games, series): two to four seats. Five and six
# seats are not released: they stay locked until the qualification is shown and the Owner decides
# (E15 Q5, AGENTS.md section 1); the engine could seat them, so this is a rule, not a limit. The
# planning of five- and six-seat series (``pod_opponent_ids``, ``paired_series.rotation_plan``)
# exists behind this lock and starts nothing. Freigabe nur per Owner-Entscheid: raise this
# constant (and the table-size lists in partie.js and paired.js) only when the Owner has released it.
MAX_RELEASED_SEATS = 4
START_WAIT_SECONDS = 20.0
MIN_WORKERS, MAX_WORKERS = 1, 16
MIN_GAMES_PER_JVM, MAX_GAMES_PER_JVM = 1, 24
# Studio series default (#1587): 16 games per bridge JVM, up from 6. Source: Owner-PC throughput
# measurement #1588 (docs/analysis-reports/owner_pc_throughput_1588_20261120.md), WSL2, Ryzen 7
# 7700, SIMULATED_RESULT: against 8 games per JVM, 6 workers gained +10.5 % and 7 workers +13.6 %
# games/hour at 16, peak RSS per JVM unchanged (about 1.06 GB), swap 0, 168 of 168 repeated seeds
# semantically identical. Native Windows (without WSL2) is UNKNOWN. 24 stays selectable (+19 to
# 20 %) but is not the default: at 24 a 48-game series fills only two JVMs. The Studio budget of
# at most 56 games per JVM (Owner decision E9, ``SERIES_JVM_GAME_CAP``) stays above the maximum.
DEFAULT_GAMES_PER_JVM = 16
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
# Seats five and six of the same presets (#1702): the opponents beyond the four-seat table, named
# one by one. ``POD_PRESETS`` plus these are the opponents of a table of up to six seats in this
# order; a table of ``n`` seats takes the first ``n - 1`` of them (``pod_opponent_ids``). Plain
# repository precons, chosen for a distinct commander each; no strength claim, and the engine's
# support for each of them at five or six seats is UNKNOWN until the real-engine part of #1661.
POD_PRESET_EXTRA_OPPONENTS: dict[str, tuple[str, str]] = {
    "precon": ("precon/2023/veloci_ramp_tor", "precon/2023/blood_rites"),
    "mixed": ("precon/2022/token_triumph", "precon/2023/veloci_ramp_tor"),
    "optimized": ("precon/2023/divine_convocation", "precon/2024/death_toll"),
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


SKIP_FORCED_DECISIONS_PROPERTY = "commanderlab.fullGame.skipForcedDecisions"
# a JVM option that selects a garbage collector (-XX:+UseG1GC, -XX:+UseParallelGC, -XX:+UseZGC, ...)
_GC_SELECTOR = re.compile(r"-XX:[+-]Use\w*GC")


def fast_bridge_command(base: Sequence[str]) -> tuple[str, ...] | None:
    """``base`` with the fast JVM options and the forced-pass switch, or ``None``.

    One builder for a series and for interactive play, so both start the bridge the same way.
    The options come from the benchmark's helper ``fast_jvm_options`` (serial GC; the AppCDS
    archive only when ``<jar>.jsa`` exists next to the jar; the JVM itself ignores an archive that
    does not match the jar and says so on stderr) plus
    ``-Dcommanderlab.fullGame.skipForcedDecisions=true`` (the engine answers a forced priority
    pass of an AI seat itself; a human seat is never skipped, the bridge sees to that). They
    change how the JVM runs and how often Python is asked, not the game. An option the command
    already carries is kept as it is, so the environment command can switch the pass skipping
    off with ``-Dcommanderlab.fullGame.skipForcedDecisions=false``.
    ``None``: not a java launcher with ``-jar <file>`` (a wrapper is used as it is).
    """
    from commander_lab.engine.rules.fast_jvm_options import fast_jvm_options

    command = tuple(base)
    if (
        not _is_java_launcher(command)
        or "-jar" not in command
        or command.index("-jar") + 1 >= len(command)
    ):
        return None
    jar_at = command.index("-jar") + 1
    jar = Path(command[jar_at]).resolve()
    # a private card repository starts each JVM in a directory of its own: the jar path must
    # not depend on the working directory
    command = (*command[:jar_at], str(jar), *command[jar_at + 1 :])
    options = [option for option in fast_jvm_options(jar) if option not in command]
    if any(_GC_SELECTOR.fullmatch(part) for part in command[: command.index("-jar")]):
        # the JVM refuses to start with two collectors: the user's choice stands (#1577)
        options = [option for option in options if option != "-XX:+UseSerialGC"]
    if not any(part.startswith(f"-D{SKIP_FORCED_DECISIONS_PROPERTY}=") for part in command):
        options.append(f"-D{SKIP_FORCED_DECISIONS_PROPERTY}=true")
    return (command[0], *options, *command[1:])


def interactive_bridge_command(base: Sequence[str] | None) -> tuple[str, ...] | None:
    """The engine command of an interactive game: the same fast options as a series (#1591).

    A forced priority pass of an AI seat then no longer runs through Python as a decision of its
    own (it waited out the AI pause each time); the engine answers it, and the game log counts
    them in ``forced_decisions_skipped``. Every decision of a human seat still comes to the
    human. ``None`` stays ``None``; a command that is not a java launcher is returned unchanged.
    """
    if base is None:
        return None
    fast = fast_bridge_command(base)
    return fast if fast is not None else tuple(base)


def series_engine(data_folder: str | Path, games_per_jvm: int) -> SeriesEngine | None:
    """The engine command of a series: fast JVM options and room for ``games_per_jvm`` games.

    The options are those of ``fast_bridge_command``. A launcher that is not java is used as it
    is, one game per process. ``None``: no engine.
    """
    from commander_lab.engine.rules.full_game_batch import command_with_games_per_jvm

    base = engine_command(data_folder)
    if base is None:
        return None
    fast = fast_bridge_command(base)
    if fast is None:
        return SeriesEngine(base, (), 1, serial_gc=False, appcds=False)
    command = command_with_games_per_jvm(fast, games_per_jvm)
    flags = command[1 : command.index("-jar")]
    return SeriesEngine(
        command=command,
        jvm_flags=flags,
        games_per_jvm=games_per_jvm,
        serial_gc="-XX:+UseSerialGC" in flags,
        appcds=any(flag.startswith("-XX:SharedArchiveFile=") for flag in flags),
    )


APPCDS_JVM_LOG_FLAGS = ("-Xlog:disable", "-Xlog:all=warning:stderr")
APPCDS_SPEED_FLAGS = ("-XX:+UseSerialGC", "-Dh2.bindAddress=127.0.0.1")
APPCDS_TRAINING_DECISIONS = 40
APPCDS_SHUTDOWN_GRACE_SECONDS = 300.0
_APPCDS_DECK_PATHS = (
    Path("data/decks/rogshai_current.json"),
    Path("data/decks/opponents/kaervek/current/deck.json"),
    Path("data/opponents/hosts_of_mordor_precon.json"),
    Path("data/opponents/lorehold_spirit_precon.json"),
)


def command_text(command: Sequence[str]) -> str:
    """``command`` as the one string ``COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD`` takes."""
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def resolve_bridge_jar(
    data_folder: str | Path | None = None, jar_path: str | Path | None = None
) -> Path:
    """Resolve the XMage bridge JAR path from explicit argument, data dir/env, or repo build."""
    if jar_path is not None:
        return Path(jar_path).resolve()
    if data_folder is not None:
        cmd = engine_command(data_folder)
        jar = jar_path_for_command(cmd)
        if jar is not None:
            return jar.resolve()
        candidate = Path(data_folder) / ENGINE_JAR
        if candidate.is_file():
            return candidate.resolve()
    from .store import studio_data_dir

    data_dir = Path(data_folder).resolve() if data_folder is not None else studio_data_dir()
    cmd = engine_command(data_dir)
    jar = jar_path_for_command(cmd)
    if jar is not None and jar.is_file():
        return jar.resolve()
    installed = data_dir / ENGINE_JAR
    if installed.is_file():
        return installed.resolve()
    return (
        _repository_root() / "engine-bridge" / "target" / "xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
    ).resolve()


def appcds_archive_path(jar: Path, archive: str | Path | None = None) -> Path:
    """Companion AppCDS ``.jsa`` path matching ``fast_jvm_options(jar)``."""
    return (Path(archive) if archive is not None else jar.with_suffix(".jsa")).resolve()


def appcds_jar_sha256_path(archive: Path) -> Path:
    """Sidecar recording the bridge JAR SHA-256 used to train ``archive``."""
    return archive.with_name(f"{archive.name}.jar.sha256")


def default_appcds_deck_paths(root: Path | None = None) -> tuple[Path, ...]:
    """Resolve 4 training deck paths for AppCDS class-loading coverage."""
    base = _repository_root() if root is None else root
    explicit = tuple((base / rel).resolve() for rel in _APPCDS_DECK_PATHS)
    if all(path.is_file() for path in explicit):
        return explicit
    precons = tuple(path.resolve() for _did, _name, _cmds, _yr, path in _precons()[:4])
    if len(precons) >= 2:
        return precons
    missing = ", ".join(str(p) for p in explicit if not p.is_file())
    raise FileNotFoundError(
        f"Standard-Trainingsdecks für AppCDS nicht gefunden ({missing}); bitte 2-6 Decks per --deck angeben."
    )


def build_appcds_archive(
    data_folder: str | Path | None = None,
    *,
    jar: str | Path | None = None,
    archive: str | Path | None = None,
    deck_paths: Sequence[str | Path] | None = None,
    decisions: int = APPCDS_TRAINING_DECISIONS,
) -> dict[str, object]:
    """Train a companion ``<jar>.jsa`` AppCDS archive using a short smoke game."""
    from commander_lab.candidates.models import FutureXmageScenario
    from commander_lab.engine.rules.full_game import FullGamePilotBinding, XmageFullGameRunner
    from commander_lab.engine.rules.project import load_rules_deck_snapshot
    from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_xmage_engine_pin,
    )
    from commander_lab.storage import sha256_value

    if decisions < 1:
        raise ValueError("decisions must be at least 1")

    resolved_jar = resolve_bridge_jar(data_folder, jar)
    if not resolved_jar.is_file():
        raise FileNotFoundError(f"Bridge-JAR nicht gefunden: {resolved_jar}")

    java = _java_executable()
    if java is None:
        raise RuntimeError("Java 17 oder neuer wurde nicht im PATH/JAVA_HOME gefunden.")
    old_major = _java_too_old(java)
    if old_major is not None:
        raise RuntimeError(
            f"Java ist zu alt: gefunden wurde Version {old_major}, nötig ist Java {MIN_JAVA_MAJOR} oder neuer."
        )

    resolved_decks = (
        tuple(Path(p).resolve() for p in deck_paths) if deck_paths else default_appcds_deck_paths()
    )
    if not MIN_SEATS <= len(resolved_decks) <= MAX_SEATS:
        raise ValueError(
            f"AppCDS benötigt {MIN_SEATS} bis {MAX_SEATS} Decks, erhalten: {len(resolved_decks)}"
        )

    loaded_decks = []
    for path in resolved_decks:
        if not path.is_file():
            raise FileNotFoundError(f"Trainingsdeck nicht gefunden: {path}")
        deck = load_rules_deck_snapshot(path)
        if deck.deck_hash is None:
            deck = deck.model_copy(
                update={
                    "deck_hash": sha256_value(
                        {
                            "deck_id": deck.deck_id,
                            "commander_names": list(deck.commander_names),
                            "mainboard": list(deck.mainboard),
                            "sideboard": list(deck.sideboard),
                        }
                    )
                }
            )
        loaded_decks.append(deck)

    deck_tuple = tuple(loaded_decks)
    own = deck_tuple[0]
    if own.deck_hash is None:
        raise RuntimeError("deck_hash missing after snapshot hash fallback")
    pin = canonical_xmage_engine_pin()
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(d.deck_id for d in deck_tuple[1:]),
        player_count=len(deck_tuple),
        seat=1,
        scenario_id="studio-appcds-training-smoke-v1",
        seed=20260923,
        xmage_commit=pin,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    pilots = tuple(
        FullGamePilotBinding(
            seat=seat,
            deck_id=deck.deck_id,
            strategy="generic",
            commander_names=deck.commander_names,
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        for seat, deck in enumerate(deck_tuple, start=1)
    )

    target_archive = appcds_archive_path(resolved_jar, archive)
    sidecar = appcds_jar_sha256_path(target_archive)
    target_archive.parent.mkdir(parents=True, exist_ok=True)
    target_archive.unlink(missing_ok=True)
    sidecar.unlink(missing_ok=True)

    runner = XmageFullGameRunner(
        (
            java,
            *APPCDS_JVM_LOG_FLAGS,
            *APPCDS_SPEED_FLAGS,
            f"-XX:ArchiveClassesAtExit={target_archive}",
            "-jar",
            str(resolved_jar),
            "full-game",
        ),
        shutdown_grace_seconds=APPCDS_SHUTDOWN_GRACE_SECONDS,
    )
    runner.run_smoke(
        scenario=scenario,
        decks=deck_tuple,
        pilots=pilots,
        smoke_decision_target=decisions,
    )
    if not target_archive.is_file():
        raise RuntimeError(
            f"Die Trainings-JVM hat kein AppCDS-Archiv geschrieben: {target_archive}"
        )

    jar_sha256 = _file_sha256(resolved_jar)
    if jar_sha256 is not None:
        sidecar.write_text(f"{jar_sha256}\n", encoding="utf-8")

    run_cmd = (
        java,
        *APPCDS_JVM_LOG_FLAGS,
        *APPCDS_SPEED_FLAGS,
        f"-XX:SharedArchiveFile={target_archive}",
        "-jar",
        str(resolved_jar),
        "full-game",
    )
    return {
        "status": "built",
        "jar_path": str(resolved_jar),
        "jar_sha256": jar_sha256,
        "archive_path": str(target_archive),
        "archive_bytes": target_archive.stat().st_size,
        "decisions": decisions,
        "engine_pin": pin,
        "command": command_text(run_cmd),
    }


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


def jar_path_for_command(command: Sequence[str] | None) -> Path | None:
    """Return the bridge jar path named after ``-jar`` in ``command``, if any."""
    if not command:
        return None
    for index, token in enumerate(command):
        if token == "-jar" and index + 1 < len(command):
            return Path(command[index + 1])
    return None


def bridge_jar_sha256(
    data_folder: str | Path | None = None,
    command: Sequence[str] | None = None,
) -> str | None:
    """SHA-256 of the bridge jar invoked for games in ``data_folder``."""
    resolved = (
        command
        if command is not None
        else (engine_command(data_folder) if data_folder is not None else None)
    )
    if resolved is not None:
        jar_from_cmd = jar_path_for_command(resolved)
        if jar_from_cmd is None:
            return None
        return _file_sha256(jar_from_cmd)
    if data_folder is not None:
        return _file_sha256(Path(data_folder) / ENGINE_JAR)
    return None


def bridge_qualification_state() -> dict[str, object]:
    """Live bridge qualification state against the sealed epoch."""
    from commander_lab.bridge_qualification import bridge_qualification

    return bridge_qualification()


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

    command = engine_command(data_folder)
    active_jar_sha256 = bridge_jar_sha256(data_folder, command)
    qual = bridge_qualification_state()

    if command is not None:
        return {
            "ready": True,
            "reason": "",
            "pin": pin,
            "jar_path": jar_path,
            "jar_sha256": jar_sha256,
            "bridge_jar_sha256": active_jar_sha256,
            "bridge_qualification": qual,
            "recorded_pin": recorded_pin,
            "pin_matches": pin_matches if pin_matches is not None else True,
            "warning": warning,
            "command": list(command),
        }

    if not jar.is_file():
        return {
            "ready": False,
            "reason": f"Die Engine-Datei fehlt: {jar}",
            "pin": pin,
            "jar_path": None,
            "jar_sha256": None,
            "bridge_jar_sha256": active_jar_sha256,
            "bridge_qualification": qual,
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
            "bridge_jar_sha256": active_jar_sha256,
            "bridge_qualification": qual,
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
        "bridge_jar_sha256": active_jar_sha256,
        "bridge_qualification": qual,
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


def validate_released_seat_count(
    opponent_count: int,
    *,
    allow_unreleased_seats: bool = False,
) -> int:
    """Validate opponent count (1..5) and enforce ``MAX_RELEASED_SEATS`` unless overridden."""
    if not MIN_SEATS - 1 <= opponent_count <= MAX_SEATS - 1:
        raise ValueError("a game requires 1 to 5 opponents (zwischen 1 und 5)")
    if not allow_unreleased_seats and opponent_count > MAX_RELEASED_SEATS - 1:
        raise ValueError(
            f"tables of {opponent_count + 1} seats are locked: the Studio starts {MIN_SEATS} to "
            f"{MAX_RELEASED_SEATS} seats; five and six seats need a qualification and an explicit "
            "Owner decision"
        )
    return 1 + opponent_count


def pod_opponent_ids(pod: str, opponent_count: int) -> tuple[str, ...]:
    """The opponents of a table of ``opponent_count + 1`` seats from a pod preset (#1702).

    The preset names its opponents in a fixed order (``POD_PRESETS``, then
    ``POD_PRESET_EXTRA_OPPONENTS``); a table takes the first ``opponent_count`` of them.
    A preset with fewer decks than the table needs is an error: nothing is filled up with
    another deck, no first option stands in (B2, #1658). The seat lock is not checked here
    (``validate_released_seat_count`` does that); this only plans the table.
    """
    if pod not in POD_PRESETS:
        raise ValueError(f"Unbekannter Gegnertisch (pod): {pod!r}")
    if not MIN_SEATS - 1 <= opponent_count <= MAX_SEATS - 1:
        raise ValueError("a game requires 1 to 5 opponents (zwischen 1 und 5)")
    declared = (*POD_PRESETS[pod], *POD_PRESET_EXTRA_OPPONENTS.get(pod, ()))
    if opponent_count > len(declared):
        raise ValueError(
            f"Der Gegnertisch {pod!r} nennt nur {len(declared)} Decks, ein Tisch mit "
            f"{opponent_count + 1} Sitzen braucht {opponent_count}; es wird nichts aufgefüllt"
        )
    return declared[:opponent_count]


def resolve_opponent_paths(
    pod: str,
    opponent_ids: Sequence[str] | None,
    *,
    allow_unreleased_seats: bool = False,
) -> list[Path]:
    """The deck files of the opponents: the given precon ids, else the pod preset.

    An unknown pod or deck id is an error (B2, #1658); no other deck takes its seat.
    """
    by_id = {deck_id: path for deck_id, _name, _cmds, _year, path in _precons()}
    if opponent_ids is not None:
        opp_list = [str(oid).strip() for oid in opponent_ids]
    elif pod in POD_PRESETS:
        opp_list = list(POD_PRESETS[pod])
    else:
        raise ValueError(f"Unbekannter Gegnertisch (pod): {pod!r}")
    validate_released_seat_count(len(opp_list), allow_unreleased_seats=allow_unreleased_seats)
    if len(set(opp_list)) != len(opp_list):
        raise ValueError("Gegner-Decks dürfen nicht doppelt vorkommen")
    paths: list[Path] = []
    for oid in opp_list:
        path = by_id.get(oid)
        if path is None:
            raise ValueError(f"Unbekanntes Gegner-Deck: {oid!r}")
        paths.append(path)
    return paths


def prepare_table_deck_paths(
    store: StudioStore,
    data_folder: str | Path,
    *,
    revision_id: str,
    opponent_ids: list[str],
    seed: int,
) -> tuple[str, list[Path]]:
    """Validate decks and resolve ordered seat deck paths plus a fresh ``game_id``."""
    others = len(opponent_ids)
    validate_released_seat_count(others)
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
    return game_id, [own, *opponents]


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
    game_id, deck_paths = prepare_table_deck_paths(
        store,
        data_folder,
        revision_id=revision_id,
        opponent_ids=opponent_ids,
        seed=seed,
    )
    own, *opponents = deck_paths
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
