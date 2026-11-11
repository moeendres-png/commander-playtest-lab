"""Recorded games: what a spectator of a simulated game sees.

A game is played by the rules engine (XMage, the only rules authority) with the Lab's own
pilots on every seat. This module only writes down what happens: for every decision the
engine asks for, the board as the engine published it and the option the pilot chose.
Nothing here decides a rule, and nothing here is played back into the engine.

The log is a line-per-entry JSON file in ``games/`` of the Studio data folder (outside the
repository). A game log is a ``SIMULATED_RESULT``: one seed, one set of pilots. It says
what happened in this game, not how strong a deck is.
"""

from __future__ import annotations

import gzip
import html
import json
import re
import time
from collections.abc import Iterator, Mapping
from functools import lru_cache
from pathlib import Path
from typing import IO, Protocol

from .store import DataClass, now_utc

LOG_SCHEMA = "studio-game-log-1"
GAMES_FOLDER = "games"
STALE_SECONDS = 600.0
_GAME_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
_TAG = re.compile(r"<[^>]{0,400}>")
_SPACE = re.compile(r"\s+")
_COLORS = ("white", "blue", "black", "red", "green", "colorless")


class DecisionPolicy(Protocol):
    def decide(self, decision: dict[str, object]) -> dict[str, object]: ...


def games_folder(data_folder: str | Path) -> Path:
    folder = Path(data_folder) / GAMES_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _checked_id(game_id: str) -> str:
    if not _GAME_ID.fullmatch(game_id):
        raise ValueError("a game id is lower-case letters, digits, '-' and '_'")
    return game_id


def free_game_id(data_folder: str | Path, wanted: str) -> str:
    """A game id made from ``wanted`` that no recorded game uses yet."""
    base = re.sub(r"[^a-z0-9]+", "-", wanted.casefold()).strip("-")[:70] or "partie"
    folder = games_folder(data_folder)
    taken = {path.name.split(".jsonl", 1)[0] for path in folder.iterdir()}
    game_id, number = base, 2
    while game_id in taken:
        game_id = f"{base}-{number}"
        number += 1
    return game_id


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _plain(value: object) -> str:
    """Engine texts carry markup for XMage's own client; the log keeps the words only."""
    if not isinstance(value, str):
        return ""
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", value))).strip()


def _whole(value: object) -> int | None:
    return value if type(value) is int else None


def _items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _card_name(card: Mapping[str, object]) -> str:
    if card.get("face_down") is True:
        return "(verdeckt)"
    return _plain(card.get("name")) or "?"


def _permanent(card: Mapping[str, object]) -> dict[str, object]:
    row: dict[str, object] = {"name": _card_name(card), "tapped": card.get("tapped") is True}
    for key in ("power", "toughness", "damage"):
        number = _whole(card.get(key))
        if number is not None:
            row[key] = number
    counters = {
        str(entry.get("type")): entry.get("count")
        for entry in _items(card.get("counters"))
        if _whole(entry.get("count"))
    }
    if counters:
        row["counters"] = counters
    return row


def _player(player: Mapping[str, object]) -> dict[str, object]:
    row: dict[str, object] = {
        "seat": _whole(player.get("seat")),
        "life": _whole(player.get("life")),
        "poison": _whole(player.get("poison_counters")) or 0,
        "hand_count": _whole(player.get("hand_count")),
        "library_count": _whole(player.get("library_count")),
        "lost": player.get("has_lost") is True,
        "won": player.get("has_won") is True,
        "battlefield": [_permanent(card) for card in _items(player.get("battlefield"))],
        "graveyard": [_card_name(card) for card in _items(player.get("graveyard"))],
        "command": [_card_name(card) for card in _items(player.get("command"))],
        "exile_count": _whole(player.get("exile_count")) or 0,
    }
    if "hand" in player:
        row["hand"] = [_card_name(card) for card in _items(player.get("hand"))]
    pool = player.get("mana_pool")
    if isinstance(pool, dict):
        mana = {color: pool.get(color) for color in _COLORS if _whole(pool.get(color))}
        if mana:
            row["mana_pool"] = mana
    return row


def _active_seat(state: Mapping[str, object]) -> int | None:
    active = state.get("active_player_id")
    for player in _items(state.get("players")):
        if active is not None and player.get("player_id") == active:
            return _whole(player.get("seat"))
    return None


def frame_of(
    number: int, decision: Mapping[str, object], response: Mapping[str, object]
) -> dict[str, object]:
    """One log entry: the published board at a decision and what the pilot answered."""
    raw_state = decision.get("pilot_state")
    state: Mapping[str, object] = raw_state if isinstance(raw_state, dict) else {}
    labels = {
        str(option.get("option_id")): _plain(option.get("label")) or str(option.get("option_id"))
        for option in _items(decision.get("legal_options"))
    }
    chosen: list[str] = []
    for key in ("selected_option_ids", "ordering"):
        picked = response.get(key)
        for option_id in picked if isinstance(picked, list) else []:
            chosen.append(labels.get(str(option_id), str(option_id)))
    frame: dict[str, object] = {
        "kind": "frame",
        "n": number,
        "turn": _whole(state.get("turn_number")),
        "phase": _text(state.get("phase")),
        "step": _text(state.get("step")),
        "active_seat": _active_seat(state),
        "seat": _whole(decision.get("seat")),
        "decision_class": _text(decision.get("decision_class")) or "?",
        "prompt": _plain(decision.get("prompt")),
        "options": len(labels),
        "chosen": chosen,
        "players": [_player(player) for player in _items(state.get("players"))],
        "stack": [_card_name(item) for item in _items(state.get("stack"))],
    }
    for key in ("numeric_choice", "numeric_choices"):
        if response.get(key) is not None:
            frame[key] = response.get(key)
    source = decision.get("source_object")
    if isinstance(source, dict) and _plain(source.get("name")):
        frame["source"] = _card_name(source)
    return frame


class GameRecorder:
    """Writes one game log. Every entry is flushed, so a running game can be watched."""

    def __init__(self, data_folder: str | Path, game_id: str, header: Mapping[str, object]) -> None:
        self.game_id = _checked_id(game_id)
        self.path = games_folder(data_folder) / f"{self.game_id}.jsonl"
        self.frames = 0
        self._handle: IO[str] | None = self.path.open("w", encoding="utf-8")
        self._write(
            {
                "kind": "header",
                "schema": LOG_SCHEMA,
                "game_id": self.game_id,
                "data_class": DataClass.SIMULATED_RESULT.value,
                "rules_authority": "xmage",
                "started_at": now_utc(),
                **header,
            }
        )

    def _write(self, entry: Mapping[str, object]) -> None:
        if self._handle is None:
            raise RuntimeError("the game log is closed")
        self._handle.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")
        self._handle.flush()

    def record(self, decision: Mapping[str, object], response: Mapping[str, object]) -> None:
        self.frames += 1
        self._write(frame_of(self.frames, decision, response))

    def close(self, result: Mapping[str, object]) -> Path:
        """Write the closing entry and pack the log. Returns the packed file."""
        self._write({"kind": "result", "ended_at": now_utc(), "frames": self.frames, **result})
        assert self._handle is not None
        self._handle.close()
        self._handle = None
        packed = self.path.with_suffix(".jsonl.gz")
        with self.path.open("rb") as source, gzip.open(packed, "wb") as target:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                target.write(chunk)
        self.path.unlink()
        return packed


class RecordingPolicy:
    """Passes every decision to the real pilot policy and writes down question and answer."""

    def __init__(self, inner: DecisionPolicy, recorder: GameRecorder) -> None:
        self._inner = inner
        self._recorder = recorder

    def decide(self, decision: dict[str, object]) -> dict[str, object]:
        response = self._inner.decide(decision)
        self._recorder.record(decision, response)
        return response


def _log_path(data_folder: str | Path, game_id: str) -> Path:
    folder = games_folder(data_folder)
    for suffix in (".jsonl.gz", ".jsonl"):
        path = folder / f"{_checked_id(game_id)}{suffix}"
        if path.is_file():
            return path
    raise KeyError(game_id)


def _lines(path: Path) -> Iterator[dict[str, object]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.endswith("\n"):
                return  # a running game: the last entry is still being written
            entry = json.loads(line)
            if isinstance(entry, dict):
                yield entry


@lru_cache(maxsize=4)
def _packed_entries(path: Path, _size: int, _changed: int) -> tuple[dict[str, object], ...]:
    return tuple(_lines(path))


def _entries(path: Path) -> Iterator[dict[str, object]]:
    if path.suffix != ".gz":
        return _lines(path)  # a running game grows: always read it fresh
    stat = path.stat()
    return iter(_packed_entries(path, stat.st_size, stat.st_mtime_ns))


def read_game(
    data_folder: str | Path, game_id: str, *, start: int = 0, count: int = 200
) -> dict[str, object]:
    """Header, the frames ``start .. start+count`` and, when the game is over, its result."""
    header: dict[str, object] = {}
    result: dict[str, object] | None = None
    frames: list[dict[str, object]] = []
    total = 0
    path = _log_path(data_folder, game_id)
    for entry in _entries(path):
        kind = entry.get("kind")
        if kind == "header":
            header = entry
        elif kind == "result":
            result = entry
        elif kind == "frame":
            if start <= total < start + count:
                frames.append(entry)
            total += 1
    if header.get("schema") != LOG_SCHEMA:
        raise ValueError(f"{game_id}: not a game log of this version")
    if result is None and time.time() - path.stat().st_mtime > STALE_SECONDS:
        # no closing entry and no new entry for a long time: the game process is gone
        result = {"kind": "result", "status": "failed", "failure_class": "abgebrochen"}
    return {
        "header": header,
        "frames": frames,
        "start": start,
        "total": total,
        "running": result is None,
        "result": result,
    }


def list_games(data_folder: str | Path) -> list[dict[str, object]]:
    """Every recorded game, newest first, with its header and (when over) its result."""
    games: list[dict[str, object]] = []
    for path in games_folder(data_folder).iterdir():
        if not path.name.endswith((".jsonl", ".jsonl.gz")):
            continue
        game_id = path.name.split(".jsonl", 1)[0]
        try:
            game = read_game(data_folder, game_id, count=0)
        except (ValueError, KeyError, OSError, json.JSONDecodeError, EOFError):
            continue
        games.append(
            {
                "game_id": game_id,
                "header": game["header"],
                "frames": game["total"],
                "running": game["running"],
                "result": game["result"],
            }
        )
    games.sort(key=_started_at, reverse=True)
    return games


def _started_at(game: Mapping[str, object]) -> str:
    header = game.get("header")
    return str(header.get("started_at") or "") if isinstance(header, dict) else ""
