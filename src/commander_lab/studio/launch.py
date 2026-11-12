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
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from .decks import lab_snapshot
from .games import free_game_id, games_folder
from .store import StudioStore

ENGINE_COMMAND_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"
ENGINE_JAR = Path("engine") / "xmage-engine-bridge.jar"
MIN_SEATS, MAX_SEATS = 2, 6
START_WAIT_SECONDS = 20.0
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
    if jar.is_file() and java:
        return (java, "-Xmx3g", "-jar", str(jar), "full-game")
    return None


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
