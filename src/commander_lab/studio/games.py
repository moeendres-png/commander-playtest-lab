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

import contextlib
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
    exile_cards = [_card_name(card) for card in _items(player.get("exile"))]
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
        "exile_count": _whole(player.get("exile_count")) or len(exile_cards),
        "exile": exile_cards,
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


def _parse_combat_declaration(decision_class: str, chosen: list[str]) -> dict[str, list[dict[str, str]]]:
    attacks: list[dict[str, str]] = []
    blocks: list[dict[str, str]] = []
    for text in chosen:
        if decision_class == "declare_attacker" and " attacks " in text:
            parts = text.split(" attacks ", 1)
            attacker = parts[0].split(" — ")[-1].strip()
            target = parts[1].strip()
            attacks.append({"attacker": attacker, "target": target})
        elif decision_class == "declare_blocker" and " blocks " in text:
            parts = text.split(" blocks ", 1)
            blocker = parts[0].split(" — ")[-1].strip()
            attacker = parts[1].strip()
            blocks.append({"blocker": blocker, "attacker": attacker})
    result: dict[str, list[dict[str, str]]] = {}
    if attacks:
        result["attacks"] = attacks
    if blocks:
        result["blocks"] = blocks
    return result


def frame_of(
    number: int,
    decision: Mapping[str, object],
    response: Mapping[str, object],
    *,
    combat: Mapping[str, object] | None = None,
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
    dc = _text(decision.get("decision_class")) or "?"
    frame: dict[str, object] = {
        "kind": "frame",
        "n": number,
        "turn": _whole(state.get("turn_number")),
        "phase": _text(state.get("phase")),
        "step": _text(state.get("step")),
        "active_seat": _active_seat(state),
        "seat": _whole(decision.get("seat")),
        "decision_class": dc,
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
    if dc in {"target", "choose_object"} and chosen:
        frame["targets"] = list(chosen)
    if combat is not None:
        frame["combat"] = dict(combat)
    else:
        immediate = _parse_combat_declaration(dc, chosen)
        if immediate:
            frame["combat"] = immediate
    return frame


class GameRecorder:
    """Writes one game log. Every entry is flushed, so a running game can be watched."""

    def __init__(self, data_folder: str | Path, game_id: str, header: Mapping[str, object]) -> None:
        self.game_id = _checked_id(game_id)
        self.path = games_folder(data_folder) / f"{self.game_id}.jsonl"
        self.frames = 0
        self._current_turn: int | None = None
        self._combat_attacks: list[dict[str, str]] = []
        self._combat_blocks: list[dict[str, str]] = []
        self._events: list[dict[str, object]] = []
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
        raw_state = decision.get("pilot_state")
        state: Mapping[str, object] = raw_state if isinstance(raw_state, dict) else {}
        turn = _whole(state.get("turn_number"))
        phase = _text(state.get("phase"))
        if phase != "combat" or turn != self._current_turn:
            self._combat_attacks = []
            self._combat_blocks = []
            self._current_turn = turn

        labels = {
            str(option.get("option_id")): _plain(option.get("label")) or str(option.get("option_id"))
            for option in _items(decision.get("legal_options"))
        }
        chosen: list[str] = []
        for key in ("selected_option_ids", "ordering"):
            picked = response.get(key)
            for option_id in picked if isinstance(picked, list) else []:
                chosen.append(labels.get(str(option_id), str(option_id)))

        dc = str(decision.get("decision_class"))
        parsed = _parse_combat_declaration(dc, chosen)
        if "attacks" in parsed:
            self._combat_attacks.extend(parsed["attacks"])
        if "blocks" in parsed:
            self._combat_blocks.extend(parsed["blocks"])

        combat_data: dict[str, list[dict[str, str]]] | None = None
        if phase == "combat" and (self._combat_attacks or self._combat_blocks):
            combat_data = {}
            if self._combat_attacks:
                combat_data["attacks"] = list(self._combat_attacks)
            if self._combat_blocks:
                combat_data["blocks"] = list(self._combat_blocks)

        self.frames += 1
        self._write(frame_of(self.frames, decision, response, combat=combat_data))

    def save_event_log(self, events: object) -> None:
        if isinstance(events, list):
            self._events = [item for item in events if isinstance(item, dict)]

    def close(self, result: Mapping[str, object]) -> Path:
        """Write the closing entry and pack the log. Returns the packed file."""
        closing: dict[str, object] = {
            "kind": "result",
            "ended_at": now_utc(),
            "frames": self.frames,
            **result,
        }
        if self._events and "event_log" not in closing:
            closing["event_log"] = self._events
        self._write(closing)
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.close()
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


def _read_orphaned_out(data_folder: str | Path, game_id: str) -> dict[str, object]:
    out_path = games_folder(data_folder) / f"{_checked_id(game_id)}.out"
    if not out_path.is_file():
        raise KeyError(game_id)
    text = out_path.read_text(encoding="utf-8", errors="replace").strip()
    mtime = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(out_path.stat().st_mtime))
    tail = "\n".join(text.splitlines()[-10:]) if text else "Keine Ausgabe erfasst."
    header = {
        "kind": "header",
        "schema": LOG_SCHEMA,
        "game_id": game_id,
        "data_class": DataClass.SIMULATED_RESULT.value,
        "rules_authority": "xmage",
        "started_at": mtime,
        "seats": [],
    }
    result = {
        "kind": "result",
        "status": "failed",
        "failure_class": "start_failed",
        "failure_message": f"Start fehlgeschlagen:\n{tail}",
        "stdout": text,
        "ended_at": mtime,
        "frames": 0,
    }
    return {
        "header": header,
        "frames": [],
        "start": 0,
        "total": 0,
        "running": False,
        "result": result,
    }


def read_game(
    data_folder: str | Path, game_id: str, *, start: int = 0, count: int = 200
) -> dict[str, object]:
    """Header, the frames ``start .. start+count`` and, when the game is over, its result."""
    try:
        path = _log_path(data_folder, game_id)
    except KeyError:
        return _read_orphaned_out(data_folder, game_id)
    header: dict[str, object] = {}
    result: dict[str, object] | None = None
    frames: list[dict[str, object]] = []
    total = 0
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
    out_path = path.parent / f"{_checked_id(game_id)}.out"
    out_content: str | None = None
    if out_path.is_file():
        with contextlib.suppress(OSError):
            out_content = out_path.read_text(encoding="utf-8", errors="replace").strip()

    if result is None and time.time() - path.stat().st_mtime > STALE_SECONDS:
        # no closing entry and no new entry for a long time: the game process is gone
        failure_msg = "abgebrochen"
        if out_content:
            tail = "\n".join(out_content.splitlines()[-10:])
            failure_msg = f"abgebrochen: {tail}"
        result = {
            "kind": "result",
            "status": "failed",
            "failure_class": "abgebrochen",
            "failure_message": failure_msg,
        }
    if result is not None and out_content and "stdout" not in result:
        result["stdout"] = out_content
    return {
        "header": header,
        "frames": frames,
        "start": start,
        "total": total,
        "running": result is None,
        "result": result,
    }


def delete_game(data_folder: str | Path, game_id: str) -> bool:
    """Delete all files of a game (logs, stdout). Returns True if deleted."""
    checked = _checked_id(game_id)
    folder = games_folder(data_folder)
    deleted = False
    for suffix in (".jsonl.gz", ".jsonl", ".out"):
        target = folder / f"{checked}{suffix}"
        if target.is_file():
            target.unlink()
            deleted = True
    if not deleted:
        raise KeyError(game_id)
    return True


def list_games(data_folder: str | Path) -> list[dict[str, object]]:
    """Every recorded game, newest first, with its header and (when over) its result."""
    games: list[dict[str, object]] = []
    folder = games_folder(data_folder)
    seen: set[str] = set()
    for path in folder.iterdir():
        if not path.name.endswith((".jsonl", ".jsonl.gz")):
            continue
        game_id = path.name.split(".jsonl", 1)[0]
        if game_id in seen:
            continue
        seen.add(game_id)
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
    for path in folder.iterdir():
        if not path.name.endswith(".out"):
            continue
        game_id = path.name[:-4]
        if game_id in seen:
            continue
        try:
            game = read_game(data_folder, game_id, count=0)
            seen.add(game_id)
            games.append(
                {
                    "game_id": game_id,
                    "header": game["header"],
                    "frames": 0,
                    "running": False,
                    "result": game["result"],
                }
            )
        except (ValueError, KeyError, OSError):
            continue
    games.sort(key=_started_at, reverse=True)
    return games


def _started_at(game: Mapping[str, object]) -> str:
    header = game.get("header")
    return str(header.get("started_at") or "") if isinstance(header, dict) else ""
