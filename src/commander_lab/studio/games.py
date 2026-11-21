"""Recorded games: what a spectator of a simulated game sees.

A game is played by the rules engine (XMage, the only rules authority) with the Lab's own
pilots on every seat. This module only writes down what happens: for every decision the
engine asks for, the board as the engine published it and the option the pilot chose.
Nothing here decides a rule, and nothing here is played back into the engine.

The log is a line-per-entry JSON file in ``games/`` of the Studio data folder (outside the
repository). A game log is a ``SIMULATED_RESULT``: one seed, one set of pilots. It says
what happened in this game, not how strong a deck is. A game with a human seat (``human_seats``
in the header) is a ``PLAYED_GAME`` (#1662): its own cohort, which no simulation figure, card
evaluation or aggregate counts (``game_cohort``).
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import html
import itertools
import json
import re
import time
from collections.abc import Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
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
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_COLORS = ("white", "blue", "black", "red", "green", "colorless")


# The cohorts a game log can belong to (#1662). ``UNKNOWN``: the header's cohort fields cannot be
# read; such a log is counted in neither cohort (fail-closed) and is shown apart.
COHORT_SIMULATED = DataClass.SIMULATED_RESULT.value
COHORT_PLAYED = DataClass.PLAYED_GAME.value
COHORT_UNKNOWN = DataClass.UNKNOWN.value
HUMAN_PILOT_LABEL = "Mensch"


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


@lru_cache(maxsize=4096)
def _plain_str(text: str) -> str:
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", text))).strip()


def _plain(value: object) -> str:
    """Engine texts carry markup for XMage's own client; the log keeps the words only."""
    if not isinstance(value, str):
        return ""
    return _plain_str(value)


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


def _parse_combat_declaration(
    decision_class: str, chosen: list[str]
) -> dict[str, list[dict[str, str]]]:
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


_PUBLIC_ZONES = frozenset({"battlefield", "graveyard", "exiled", "stack", "command"})


def _is_private_selection(decision: Mapping[str, object], response: Mapping[str, object]) -> bool:
    """True when the answer picked cards out of a hidden zone (hand or library).

    The engine facts decide it, no rule: the bridge's own marker of a London-mulligan bottom pick
    (``context.bottom_of_library_selection``), or a ``choose_object``/``target`` answer whose
    chosen options the engine places in the hand or the library (``metadata.zone``). A zone the
    engine did not name counts as hidden (conservative); only a named public zone stays visible.
    """
    context = decision.get("context")
    if isinstance(context, Mapping) and context.get("bottom_of_library_selection") is True:
        return True
    if decision.get("decision_class") not in {"choose_object", "target"}:
        return False
    picked: set[str] = set()
    for key in ("selected_option_ids", "ordering"):
        raw = response.get(key)
        if isinstance(raw, list):
            picked.update(str(item) for item in raw)
    by_id = {
        str(option.get("option_id")): option for option in _items(decision.get("legal_options"))
    }
    for option_id in picked:
        metadata = by_id.get(option_id, {}).get("metadata")
        zone = metadata.get("zone") if isinstance(metadata, Mapping) else None
        if not (isinstance(zone, str) and zone in _PUBLIC_ZONES):
            return True
    return False


SERIES_BUFFER_BYTES = 65_536
SERIES_GZIP_COMPRESSLEVEL = 1
DEFAULT_GZIP_COMPRESSLEVEL = 9


def _published_object_labels(decision: Mapping[str, object]) -> dict[str, str]:
    """Display labels for published ``pilot_state`` objects indexed by engine ``object_id``.

    Reads only public card characteristics (``face_down`` and ``name`` via :func:`_card_name`),
    never ``private_identity``.
    """
    raw_state = decision.get("pilot_state")
    if not isinstance(raw_state, Mapping):
        return {}
    labels: dict[str, str] = {}
    for item in _items(raw_state.get("stack")):
        oid = _text(item.get("object_id"))
        if oid:
            labels.setdefault(oid, _card_name(item))
    for player in _items(raw_state.get("players")):
        for zone in ("battlefield", "graveyard", "command", "exile", "hand"):
            for item in _items(player.get(zone)):
                oid = _text(item.get("object_id"))
                if oid:
                    labels.setdefault(oid, _card_name(item))
    return labels


def _fallback_option_label(
    oid: str,
    raw_label: str,
    option: Mapping[str, object] | None,
    published: Mapping[str, str],
) -> str:
    """Resolve a readable label when an engine option carries an empty string or raw UUID (#1651)."""
    if option is not None:
        metadata = option.get("metadata")
        if isinstance(metadata, Mapping):
            if metadata.get("face_down") is True:
                return "(verdeckt)"
            meta_name = _plain(metadata.get("name"))
            if meta_name and not _UUID.fullmatch(meta_name):
                return meta_name
            meta_oid = _text(metadata.get("object_id"))
            if meta_oid and meta_oid in published:
                return published[meta_oid]
    if oid in published:
        return published[oid]
    if _UUID.fullmatch(raw_label):
        return published.get(raw_label, "?")
    if _UUID.fullmatch(oid):
        return "?"
    return oid


def _resolve_options(
    decision: Mapping[str, object], response: Mapping[str, object]
) -> tuple[int, list[str]]:
    by_id = {
        str(option.get("option_id")): option for option in _items(decision.get("legal_options"))
    }
    published: dict[str, str] | None = None
    chosen: list[str] = []
    for key in ("selected_option_ids", "ordering"):
        picked = response.get(key)
        for option_id in picked if isinstance(picked, list) else []:
            oid = str(option_id)
            option = by_id.get(oid)
            label = _plain(option.get("label")) if option is not None else ""
            if not label or _UUID.fullmatch(label):
                if published is None:
                    published = _published_object_labels(decision)
                label = _fallback_option_label(oid, label, option, published)
            chosen.append(label or ("?" if _UUID.fullmatch(oid) else oid))
    return len(by_id), chosen


def _build_frame(
    number: int,
    decision: Mapping[str, object],
    response: Mapping[str, object],
    *,
    option_count: int,
    chosen: list[str],
    combat: Mapping[str, object] | None = None,
) -> dict[str, object]:
    raw_state = decision.get("pilot_state")
    state: Mapping[str, object] = raw_state if isinstance(raw_state, dict) else {}
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
        "options": option_count,
        "chosen": chosen,
        "players": [_player(player) for player in _items(state.get("players"))],
        "stack": [_card_name(item) for item in _items(state.get("stack"))],
    }
    for key in ("numeric_choice", "numeric_choices"):
        if response.get(key) is not None:
            frame[key] = response.get(key)
    if _is_private_selection(decision, response):
        # A pick of the deciding seat's own hand cards stays hidden from the other seats while
        # the game runs (see redact_frame_for_human_seats).
        frame["private_selection"] = True
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


def frame_of(
    number: int,
    decision: Mapping[str, object],
    response: Mapping[str, object],
    *,
    combat: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """One log entry: the published board at a decision and what the pilot answered."""
    option_count, chosen = _resolve_options(decision, response)
    return _build_frame(
        number, decision, response, option_count=option_count, chosen=chosen, combat=combat
    )


def game_cohort(header: object) -> str:
    """The cohort of a game log from its header: ``SIMULATED_RESULT``, ``PLAYED_GAME`` or ``UNKNOWN``.

    A game is ``PLAYED_GAME`` when its header says so (``data_class``), names a human seat
    (``human_seats`` a non-empty list of seat numbers) or seats a human pilot (a seat row with
    ``pilot`` "Mensch"). The last two also recognise logs written before #1662, whose header
    still says ``SIMULATED_RESULT``: no backfill is needed. ``human_seats: []`` (written for a
    non-default timeout without a human) is no human seat. A header whose cohort fields cannot
    be read (no mapping, ``human_seats`` not a list of seat numbers, a seat list that is no list
    or holds a row that is no mapping, a ``data_class`` that is neither cohort) is ``UNKNOWN`` and never read as a simulation. A
    header without ``data_class`` and without a human seat stays a simulation (older logs).
    """
    if not isinstance(header, Mapping):
        return COHORT_UNKNOWN
    data_class = header.get("data_class")
    if data_class == COHORT_PLAYED:
        return COHORT_PLAYED
    unknown = data_class is not None and data_class != COHORT_SIMULATED
    raw_humans = header.get("human_seats")
    if raw_humans is not None:
        if not isinstance(raw_humans, list) or any(type(s) is not int for s in raw_humans):
            unknown = True
        elif raw_humans:
            return COHORT_PLAYED
    raw_seats = header.get("seats")
    if raw_seats is not None and not isinstance(raw_seats, list):
        unknown = True
    for row in raw_seats if isinstance(raw_seats, list) else []:
        if not isinstance(row, Mapping):
            unknown = True  # a seat row that is no mapping cannot say whether a human sat there
        elif row.get("pilot") == HUMAN_PILOT_LABEL:
            return COHORT_PLAYED
    return COHORT_UNKNOWN if unknown else COHORT_SIMULATED


def played_seats(header: object) -> list[int]:
    """The seat numbers (0-based) a human sits on, from the header's own fields, sorted.

    The union of ``human_seats`` (a list of seat numbers) and every seat row whose ``pilot`` is
    "Mensch". Anything unreadable adds nothing; the page then names no seat rather than a guess.
    """
    if not isinstance(header, Mapping):
        return []
    seats: set[int] = set()
    raw_humans = header.get("human_seats")
    if isinstance(raw_humans, list):
        seats.update(s for s in raw_humans if type(s) is int)
    raw_rows = header.get("seats")
    for row in raw_rows if isinstance(raw_rows, list) else []:
        if (
            isinstance(row, Mapping)
            and row.get("pilot") == HUMAN_PILOT_LABEL
            and type(row.get("seat")) is int
        ):
            seats.add(row["seat"])
    return sorted(seats)


def cohort_fields(header: object) -> dict[str, object]:
    """The read fields the pages show instead of guessing (#1662): ``cohort`` (see
    ``game_cohort``) and, for a ``PLAYED_GAME``, ``played_seats`` (empty otherwise)."""
    cohort = game_cohort(header)
    return {
        "cohort": cohort,
        "played_seats": played_seats(header) if cohort == COHORT_PLAYED else [],
    }


class GameRecorder:
    """Writes one game log.

    Interactive games keep ``flush_each_frame=True`` so a running game can be watched live;
    non-interactive series pass ``flush_each_frame=False`` and ``gzip_compresslevel=1`` for
    buffered writes and faster closing compression with byte-identical decompressed logs.
    """

    def __init__(
        self,
        data_folder: str | Path,
        game_id: str,
        header: Mapping[str, object],
        *,
        flush_each_frame: bool = True,
        gzip_compresslevel: int = DEFAULT_GZIP_COMPRESSLEVEL,
    ) -> None:
        if (
            isinstance(gzip_compresslevel, bool)
            or not isinstance(gzip_compresslevel, int)
            or not 1 <= gzip_compresslevel <= 9
        ):
            raise ValueError("gzip_compresslevel must be an integer between 1 and 9")
        self.game_id = _checked_id(game_id)
        self.path = games_folder(data_folder) / f"{self.game_id}.jsonl"
        self.frames = 0
        self.header: dict[str, object] = dict(header)
        self.flush_each_frame = bool(flush_each_frame)
        self.gzip_compresslevel = gzip_compresslevel
        self._current_turn: int | None = None
        self._combat_attacks: list[dict[str, str]] = []
        self._combat_blocks: list[dict[str, str]] = []
        self._events: list[dict[str, object]] = []
        buffering = -1 if self.flush_each_frame else SERIES_BUFFER_BYTES
        self._handle: IO[str] | None = self.path.open("w", encoding="utf-8", buffering=buffering)
        entry: dict[str, object] = {
            "kind": "header",
            "schema": LOG_SCHEMA,
            "game_id": self.game_id,
            "data_class": COHORT_SIMULATED,
            "rules_authority": "xmage",
            "started_at": now_utc(),
            **header,
        }
        # A game with a human seat is its own cohort (#1662), never a simulation; the class is
        # set after the caller's header so no header field can turn it back. A header whose
        # cohort fields cannot be read is written UNKNOWN, never stamped as a simulation.
        entry["data_class"] = game_cohort(entry)
        self._write(entry)

    def _write(self, entry: Mapping[str, object]) -> None:
        if self._handle is None:
            raise RuntimeError("the game log is closed")
        self._handle.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")
        if self.flush_each_frame:
            self._handle.flush()

    def record(
        self, decision: Mapping[str, object], response: Mapping[str, object]
    ) -> dict[str, object]:
        raw_state = decision.get("pilot_state")
        state: Mapping[str, object] = raw_state if isinstance(raw_state, dict) else {}
        turn = _whole(state.get("turn_number"))
        phase = _text(state.get("phase"))
        if phase != "combat" or turn != self._current_turn:
            self._combat_attacks = []
            self._combat_blocks = []
            self._current_turn = turn

        option_count, chosen = _resolve_options(decision, response)
        dc = str(decision.get("decision_class"))
        if dc in {"declare_attacker", "declare_blocker"}:
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
        frame = _build_frame(
            self.frames,
            decision,
            response,
            option_count=option_count,
            chosen=chosen,
            combat=combat_data,
        )
        self._write(frame)
        return frame

    def discard(self) -> None:
        """Stop writing without closing the log: the game is played again from its start."""
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.close()

    def save_event_log(self, events: object) -> None:
        if isinstance(events, list):
            self._events = canonicalize_event_log(
                [item for item in events if isinstance(item, Mapping)]
            )

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
        with (
            self.path.open("rb") as source,
            gzip.open(packed, "wb", compresslevel=self.gzip_compresslevel) as target,
        ):
            for chunk in iter(lambda: source.read(1 << 20), b""):
                target.write(chunk)
        self.path.unlink()
        return packed


def _event_step_group(event: Mapping[str, object]) -> tuple[object, object]:
    return (event.get("turn"), event.get("step"))


def _event_content_key(event: Mapping[str, object]) -> str:
    payload = {key: value for key, value in event.items() if key != "sequence"}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonicalize_event_log(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Return a copy of ``events`` with simultaneous events in each ``(turn, step)`` stably ordered.

    Contiguous runs sharing ``(turn, step)`` are sorted by their canonical JSON content (ignoring
    ``sequence``) so non-deterministic iteration order of simultaneous engine events (such as
    combat damage to multiple permanents) yields an identical sequence and digest across runs,
    while preserving chronological step and turn boundaries.
    """
    canonical: list[dict[str, object]] = []
    seq = 0
    for _group_key, group in itertools.groupby(events, key=_event_step_group):
        ordered = sorted(group, key=_event_content_key)
        for item in ordered:
            seq += 1
            entry = dict(item)
            if "sequence" in entry:
                entry["sequence"] = seq
            canonical.append(entry)
    return canonical


def event_log_sha256(events: Sequence[Mapping[str, object]]) -> str:
    """Deterministic SHA-256 hex digest of ``events`` after canonicalizing simultaneous entries."""
    canonical = canonicalize_event_log(events)
    stripped = [
        {key: value for key, value in entry.items() if key != "sequence"} for entry in canonical
    ]
    encoded = json.dumps(
        stripped, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
        # made up by this reader: whether a human sat at the table is not known
        "data_class": COHORT_UNKNOWN,
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
        # The header above is made up by this reader (the game never wrote a log), so it cannot
        # say whether a human sat at the table: the cohort is unknown, never a simulation.
        "cohort": COHORT_UNKNOWN,
        "played_seats": [],
        "result": result,
    }


def _human_seat_set(raw: object) -> frozenset[int]:
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(item for item in raw if type(item) is int)


def redact_frame_for_human_seats(
    frame: Mapping[str, object],
    human_seats: frozenset[int] | set[int],
) -> dict[str, object]:
    """Return a copy of ``frame`` omitting ``hand`` for every seat not in ``human_seats``.

    Used only while a game runs. Owner decision 2026-11-17: once the game has ended its closing
    result exists and the hands of the AI seats are shown (``read_game``, ``play``); a running
    game never shows them. A hidden pick of an AI seat (``private_selection``: cards it put on
    the bottom of its library) loses its card names as well.
    """
    copy_frame = dict(frame)
    if frame.get("private_selection") is True and _whole(frame.get("seat")) not in human_seats:
        copy_frame["chosen"] = []
        copy_frame.pop("targets", None)
    raw_players = frame.get("players")
    if isinstance(raw_players, list):
        redacted_players: list[dict[str, object]] = []
        for player in raw_players:
            if not isinstance(player, Mapping):
                continue
            p_copy = dict(player)
            seat = _whole(p_copy.get("seat"))
            if seat not in human_seats:
                p_copy.pop("hand", None)
                p_copy.pop("hand_cards", None)
            redacted_players.append(p_copy)
        copy_frame["players"] = redacted_players
    return copy_frame


def redact_pilot_state_for_human_seats(
    pilot_state: Mapping[str, object],
    human_seats: frozenset[int] | set[int],
) -> dict[str, object]:
    """Return a copy of ``pilot_state`` omitting ``hand`` for every seat not in ``human_seats``."""
    copy_state = dict(pilot_state)
    raw_players = pilot_state.get("players")
    if isinstance(raw_players, list):
        redacted_players: list[dict[str, object]] = []
        for player in raw_players:
            if not isinstance(player, Mapping):
                continue
            p_copy = dict(player)
            seat = _whole(p_copy.get("seat"))
            if seat not in human_seats:
                p_copy.pop("hand", None)
                p_copy.pop("hand_cards", None)
            redacted_players.append(p_copy)
        copy_state["players"] = redacted_players
    return copy_state


def read_game(
    data_folder: str | Path,
    game_id: str,
    *,
    start: int = 0,
    count: int = 200,
    live_game_ids: AbstractSet[str] = frozenset(),
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
    human_seats = _human_seat_set(header.get("human_seats"))
    # Owner decision 2026-11-17: the hands of the AI seats are hidden while the game runs and
    # shown after it ended (the closing entry exists). Never revealed before that.
    hands_hidden = result is None and bool(human_seats)
    if hands_hidden:
        frames = [redact_frame_for_human_seats(frame, human_seats) for frame in frames]
    out_path = path.parent / f"{_checked_id(game_id)}.out"
    out_content: str | None = None
    if out_path.is_file():
        with contextlib.suppress(OSError):
            out_content = out_path.read_text(encoding="utf-8", errors="replace").strip()

    stale_after = STALE_SECONDS
    raw_timeout = header.get("decision_timeout_seconds")
    if type(raw_timeout) is int and raw_timeout > 0:
        stale_after = max(STALE_SECONDS, float(raw_timeout) + 120.0)
    is_live = game_id in live_game_ids
    if result is None and not is_live and time.time() - path.stat().st_mtime > stale_after:
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
    if result is not None:
        raw_events = result.get("event_log")
        needs_stdout = bool(out_content and "stdout" not in result)
        if isinstance(raw_events, list) or needs_stdout:
            result = dict(result)
            if isinstance(raw_events, list):
                result["event_log"] = canonicalize_event_log(
                    [item for item in raw_events if isinstance(item, Mapping)]
                )
            if needs_stdout and out_content is not None:
                result["stdout"] = out_content
    return {
        "header": header,
        "frames": frames,
        "start": start,
        "total": total,
        "running": result is None,
        "hands_revealed": bool(human_seats) and not hands_hidden,
        **cohort_fields(header),
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


def list_games(
    data_folder: str | Path,
    *,
    live_game_ids: AbstractSet[str] = frozenset(),
) -> list[dict[str, object]]:
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
            game = read_game(data_folder, game_id, count=0, live_game_ids=live_game_ids)
        except (ValueError, KeyError, OSError, json.JSONDecodeError, EOFError):
            continue
        games.append(
            {
                "game_id": game_id,
                "header": game["header"],
                "frames": game["total"],
                "running": game["running"],
                "cohort": game["cohort"],
                "played_seats": game["played_seats"],
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
                    "cohort": game["cohort"],
                    "played_seats": game["played_seats"],
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
