"""Start a simulated game from the Studio page.

The page chooses one of the owner's deck revisions, the other seats' decks and a seed. The
game itself runs in its own process (``python -m commander_lab.studio play``), so the page
stays usable and can follow the growing game log. This module holds only the light parts:
where the engine is, which decks can sit at the table, and the process start.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
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


def engine_command(data_folder: str | Path) -> tuple[str, ...] | None:
    """How the rules engine is started here, or ``None`` when it is not set up.

    The environment names the command as for every full game of the Lab. Without it, the
    engine file in ``engine/`` of the Studio data folder is used when Java is installed.
    """
    raw = os.environ.get(ENGINE_COMMAND_ENV, "").strip()
    if raw:
        return tuple(shlex.split(raw))
    jar = Path(data_folder) / ENGINE_JAR
    java = shutil.which("java")
    if jar.is_file() and java:
        return (java, "-Xmx3g", "-jar", str(jar), "full-game")
    return None


def engine_state(data_folder: str | Path) -> dict[str, object]:
    if engine_command(data_folder) is not None:
        return {"ready": True, "reason": ""}
    jar = Path(data_folder) / ENGINE_JAR
    if not jar.is_file():
        return {"ready": False, "reason": f"Die Engine-Datei fehlt: {jar}"}
    return {"ready": False, "reason": "Java ist nicht installiert (Java 17 oder neuer)."}


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


def start_game(
    store: StudioStore,
    data_folder: str | Path,
    *,
    revision_id: str,
    opponent_ids: list[str],
    seed: int,
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
    raise RuntimeError("Die Partie konnte nicht gestartet werden.")
