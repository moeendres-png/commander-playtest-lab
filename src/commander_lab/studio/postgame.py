"""PLAY v1 postgame sheet summary and persisted session/note records (#1662 part 4).

Reads recorded game logs exclusively through ``games.read_game`` and engine-published
frames/events without implementing any game rules. Keeps ``PLAYED_GAME`` and
``SIMULATED_RESULT`` cohorts strictly separated.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from datetime import UTC, datetime
from pathlib import Path

from . import games
from .store import DataClass, StudioStore, now_utc

_UNKNOWN_CARD_LABELS = frozenset({"", "?", "(verdeckt)"})


def _opt_str(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _whole(value: object) -> int | None:
    return value if type(value) is int else None


def _opt_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clean_card_name(value: object) -> str | None:
    if isinstance(value, Mapping):
        if value.get("face_down") is True:
            return None
        value = value.get("name")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in _UNKNOWN_CARD_LABELS:
        return None
    return stripped


def _parse_iso_timestamp(raw: object) -> datetime | None:
    text = _opt_str(raw)
    if text is None:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _duration_seconds(
    header: Mapping[str, object], result: Mapping[str, object] | None
) -> float | None:
    if result is None:
        return None
    start_dt = _parse_iso_timestamp(header.get("started_at"))
    end_dt = _parse_iso_timestamp(result.get("ended_at"))
    if start_dt is None or end_dt is None:
        return None
    return max(0.0, round((end_dt - start_dt).total_seconds(), 3))


def _table_seats(header: Mapping[str, object]) -> list[dict[str, object]]:
    raw_seats = header.get("seats")
    if not isinstance(raw_seats, list):
        return []
    seats: list[dict[str, object]] = []
    for item in raw_seats:
        if not isinstance(item, Mapping):
            continue
        raw_commanders = item.get("commanders")
        commanders = (
            [c.strip() for c in raw_commanders if isinstance(c, str) and c.strip()]
            if isinstance(raw_commanders, list)
            else []
        )
        seats.append(
            {
                "seat": _whole(item.get("seat")),
                "deck_id": _opt_str(item.get("deck_id")),
                "revision_id": _opt_str(item.get("studio_revision_id"))
                or _opt_str(item.get("revision_id")),
                "deck_hash": _opt_str(item.get("deck_hash")),
                "commanders": commanders,
                "pilot": _opt_str(item.get("pilot")),
            }
        )
    return seats


def _winner_seats(result: Mapping[str, object] | None) -> list[int]:
    if result is None:
        return []
    raw_list = result.get("winner_seats")
    if isinstance(raw_list, list):
        return [s for s in raw_list if type(s) is int]
    single = result.get("winner_seat")
    if type(single) is int:
        return [single]
    return []


def _outcome_for_seat(
    status: str, result: Mapping[str, object] | None, winners: Sequence[int], focus_seat: int
) -> str:
    if result is None or status != "finished":
        return "incomplete"
    if not winners:
        return "draw"
    if focus_seat in winners:
        return "won" if len(winners) == 1 else "draw"
    return "lost"


def _event_matches_seat(event: Mapping[str, object], focus_seat: int) -> bool:
    for key in ("seat", "player_seat"):
        raw_seat = event.get(key)
        if type(raw_seat) is int:
            return raw_seat == focus_seat
    player_label = event.get("player_player")
    if isinstance(player_label, str):
        return player_label in {
            f"P{focus_seat + 1}",
            f"seat_{focus_seat + 1}",
            f"p{focus_seat}",
        }
    return False


def _player_row_for_seat(
    frame: Mapping[str, object], focus_seat: int
) -> Mapping[str, object] | None:
    raw_players = frame.get("players")
    if not isinstance(raw_players, list):
        return None
    for row in raw_players:
        if isinstance(row, Mapping) and _whole(row.get("seat")) == focus_seat:
            return row
    return None


def _append_unique(ordered: list[str], seen: set[str], name: str | None) -> None:
    if name is not None and name not in seen:
        seen.add(name)
        ordered.append(name)


def _extract_card_activity(
    frames: Sequence[Mapping[str, object]],
    result: Mapping[str, object] | None,
    focus_seat: int,
) -> tuple[list[str], list[str], list[str]]:
    drawn: list[str] = []
    drawn_seen: set[str] = set()
    cast: list[str] = []
    cast_seen: set[str] = set()

    # 1. Authoritative cast / hand->stack|battlefield events from engine event_log, if recorded.
    raw_events = result.get("event_log") if isinstance(result, Mapping) else None
    if isinstance(raw_events, list):
        for event in raw_events:
            if not isinstance(event, Mapping) or not _event_matches_seat(event, focus_seat):
                continue
            ev_type = str(event.get("type") or "").upper()
            if ev_type == "SPELL_CAST":
                if event.get("source_hidden") is True:
                    continue
                name = (
                    _clean_card_name(event.get("source_name"))
                    or _clean_card_name(event.get("target_name"))
                    or _clean_card_name(event.get("card_name"))
                )
                _append_unique(cast, cast_seen, name)
            elif ev_type == "ZONE_CHANGE":
                if event.get("target_hidden") is True:
                    continue
                from_zone = str(event.get("from") or "").upper()
                to_zone = str(event.get("to") or "").upper()
                if from_zone == "HAND" and to_zone in {"STACK", "BATTLEFIELD"}:
                    name = (
                        _clean_card_name(event.get("target_name"))
                        or _clean_card_name(event.get("source_name"))
                        or _clean_card_name(event.get("card_name"))
                    )
                    _append_unique(cast, cast_seen, name)

    # 2. Frame-level observations: cards in hand/battlefield and Hand -> Stack/Battlefield moves.
    ever_in_hand: set[str] = set()
    last_hand_counts: Counter[str] = Counter()
    prev_bf: set[str] = set()
    prev_stack: set[str] = set()
    prev_deciding_seat: int | None = None
    last_known_hand: list[str] | None = None

    for frame in frames:
        player = _player_row_for_seat(frame, focus_seat)
        cur_bf: set[str] = set()
        cur_hand_names: list[str] | None = None
        if player is not None:
            raw_hand = player.get("hand")
            if isinstance(raw_hand, list):
                cur_hand_names = [
                    name for item in raw_hand if (name := _clean_card_name(item)) is not None
                ]
                last_known_hand = list(cur_hand_names)
                for name in cur_hand_names:
                    _append_unique(drawn, drawn_seen, name)
            elif _whole(player.get("hand_count")) == 0:
                last_known_hand = []

            raw_bf = player.get("battlefield")
            if isinstance(raw_bf, list):
                for item in raw_bf:
                    name = _clean_card_name(item)
                    if name is not None:
                        cur_bf.add(name)
                        _append_unique(drawn, drawn_seen, name)

        raw_stack = frame.get("stack")
        cur_stack: set[str] = set()
        if isinstance(raw_stack, list):
            for item in raw_stack:
                name = _clean_card_name(item)
                if name is not None:
                    cur_stack.add(name)

        # Transition: card previously seen in focus_seat's hand newly appears on focus_seat's
        # battlefield or on the stack when focus_seat acted/holds priority.
        for name in sorted(cur_bf - prev_bf):
            if name in ever_in_hand:
                _append_unique(cast, cast_seen, name)

        cur_seat = _whole(frame.get("seat"))
        active_seat = _whole(frame.get("active_seat"))
        for name in sorted(cur_stack - prev_stack):
            if name not in ever_in_hand:
                continue
            left_hand = (
                cur_hand_names is None or Counter(cur_hand_names)[name] < last_hand_counts[name]
            )
            if left_hand and (
                prev_deciding_seat == focus_seat
                or cur_seat == focus_seat
                or active_seat == focus_seat
            ):
                _append_unique(cast, cast_seen, name)

        if cur_hand_names is not None:
            ever_in_hand.update(cur_hand_names)
            last_hand_counts = Counter(cur_hand_names)
        prev_bf = cur_bf
        prev_stack = cur_stack
        prev_deciding_seat = cur_seat

    for name in cast:
        _append_unique(drawn, drawn_seen, name)

    left_in_hand: list[str] = []
    if frames:
        last_player = _player_row_for_seat(frames[-1], focus_seat)
        last_hand = last_player.get("hand") if last_player is not None else None
        if isinstance(last_hand, list):
            left_in_hand = [
                name for item in last_hand if (name := _clean_card_name(item)) is not None
            ]
        elif last_player is not None and _whole(last_player.get("hand_count")) == 0:
            left_in_hand = []
        elif last_known_hand is not None:
            left_in_hand = list(last_known_hand)

    return drawn, cast, left_in_hand


def _max_turn(
    frames: Sequence[Mapping[str, object]], result: Mapping[str, object] | None
) -> int | None:
    turns: list[int] = []
    for frame in frames:
        turn = _whole(frame.get("turn"))
        if turn is not None:
            turns.append(turn)
    raw_events = result.get("event_log") if isinstance(result, Mapping) else None
    if isinstance(raw_events, list):
        for event in raw_events:
            if isinstance(event, Mapping):
                turn = _whole(event.get("turn"))
                if turn is not None:
                    turns.append(turn)
    return max(turns) if turns else None


def summarize_game_for_postgame(
    data_folder: str | Path,
    game_id: str,
    *,
    seat: int | None = None,
    live_game_ids: AbstractSet[str] = frozenset(),
) -> dict[str, object]:
    """Build the postgame summary for one recorded game from its log."""
    game = games.read_game(
        data_folder,
        game_id,
        start=0,
        count=1_000_000,
        live_game_ids=live_game_ids,
    )
    total_frames = _whole(game.get("total")) or 0
    raw_frames = game.get("frames")
    if isinstance(raw_frames, list) and total_frames > len(raw_frames):
        game = games.read_game(
            data_folder,
            game_id,
            start=0,
            count=total_frames,
            live_game_ids=live_game_ids,
        )
        raw_frames = game.get("frames")

    header_raw = game.get("header")
    header: Mapping[str, object] = header_raw if isinstance(header_raw, Mapping) else {}
    result_raw = game.get("result")
    result: Mapping[str, object] | None = result_raw if isinstance(result_raw, Mapping) else None
    frames = (
        [f for f in raw_frames if isinstance(f, Mapping)] if isinstance(raw_frames, list) else []
    )

    data_class = games.game_cohort(header)
    human_seats_list = games.played_seats(header)
    if seat is not None:
        focus_seat = seat
    elif human_seats_list:
        focus_seat = human_seats_list[0]
    else:
        focus_seat = 0

    if data_class == games.COHORT_PLAYED:
        human_seat: int | None = (
            focus_seat
            if focus_seat in human_seats_list
            else (human_seats_list[0] if human_seats_list else None)
        )
    else:
        human_seat = None

    table_seats = _table_seats(header)
    focus_row = next(
        (row for row in table_seats if row.get("seat") == focus_seat),
        None,
    )
    deck_id = _opt_str(focus_row.get("deck_id")) if focus_row is not None else None
    revision_id = _opt_str(focus_row.get("revision_id")) if focus_row is not None else None
    deck_hash = _opt_str(focus_row.get("deck_hash")) if focus_row is not None else None

    running = bool(game.get("running"))
    status = "running" if result is None else (_opt_str(result.get("status")) or "unknown")
    winners = _winner_seats(result)
    outcome = _outcome_for_seat(status, result, winners, focus_seat)

    cards_drawn, cards_cast, cards_left_in_hand = _extract_card_activity(frames, result, focus_seat)
    if data_class == games.COHORT_PLAYED and frames:
        human_clicks: int | None = sum(
            1 for frame in frames if _whole(frame.get("seat")) == focus_seat
        )
    else:
        human_clicks = None

    bridge_jar_sha256 = (
        _opt_str(result.get("bridge_jar_sha256")) if result is not None else None
    ) or _opt_str(header.get("bridge_jar_sha256"))
    bridge_qualification_state = (
        _opt_str(result.get("bridge_qualification_state")) if result is not None else None
    ) or _opt_str(header.get("bridge_qualification_state"))

    return {
        "game_id": game_id,
        "data_class": data_class,
        "status": status,
        "finished": not running and result is not None,
        "outcome": outcome,
        "winner_seats": winners,
        "seed": _whole(header.get("seed")),
        "deck_id": deck_id,
        "revision_id": revision_id,
        "deck_hash": deck_hash,
        "table_seats": table_seats,
        "human_seat": human_seat,
        "focus_seat": focus_seat,
        "bridge_jar_sha256": bridge_jar_sha256,
        "bridge_qualification_state": bridge_qualification_state,
        "cards_drawn": cards_drawn,
        "cards_cast": cards_cast,
        "cards_left_in_hand": cards_left_in_hand,
        "human_clicks": human_clicks,
        "duration_seconds": _duration_seconds(header, result),
        "total_turns": _max_turn(frames, result),
    }


def _row_to_play_session(row: sqlite3.Row) -> dict[str, object]:
    return {
        "game_id": str(row["game_id"]),
        "deck_id": _opt_str(row["deck_id"]),
        "revision_id": _opt_str(row["revision_id"]),
        "deck_hash": _opt_str(row["deck_hash"]),
        "table_json": _opt_str(row["table_json"]),
        "seed": _whole(row["seed"]),
        "human_seat": _whole(row["human_seat"]),
        "outcome": _opt_str(row["outcome"]),
        "duration_seconds": _opt_float(row["duration_seconds"]),
        "human_clicks": _whole(row["human_clicks"]),
        "bridge_jar_sha256": _opt_str(row["bridge_jar_sha256"]),
        "bridge_qualification_state": _opt_str(row["bridge_qualification_state"]),
        "data_class": str(row["data_class"]),
        "created_at": str(row["created_at"]),
    }


def record_play_session(store: StudioStore, summary: Mapping[str, object]) -> dict[str, object]:
    """Persist or update one ``play_session`` row idempotently."""
    game_id = _opt_str(summary.get("game_id"))
    if game_id is None:
        raise ValueError("game_id darf nicht leer sein")
    raw_table_json = summary.get("table_json")
    if isinstance(raw_table_json, str):
        table_json: str | None = raw_table_json
    elif "table_seats" in summary and summary.get("table_seats") is not None:
        table_json = json.dumps(
            summary.get("table_seats"), ensure_ascii=False, separators=(",", ":")
        )
    else:
        table_json = None
    data_class = _opt_str(summary.get("data_class")) or DataClass.UNKNOWN.value
    created_at = _opt_str(summary.get("created_at")) or now_utc()
    with store.connection as db:
        existing = db.execute(
            "SELECT created_at FROM play_session WHERE game_id = ?", (game_id,)
        ).fetchone()
        if existing is not None and summary.get("created_at") is None:
            created_at = str(existing["created_at"])
        db.execute(
            "INSERT OR REPLACE INTO play_session("
            "game_id, deck_id, revision_id, deck_hash, table_json, seed, human_seat, "
            "outcome, duration_seconds, human_clicks, bridge_jar_sha256, "
            "bridge_qualification_state, data_class, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                game_id,
                _opt_str(summary.get("deck_id")),
                _opt_str(summary.get("revision_id")),
                _opt_str(summary.get("deck_hash")),
                table_json,
                _whole(summary.get("seed")),
                _whole(summary.get("human_seat")),
                _opt_str(summary.get("outcome")),
                _opt_float(summary.get("duration_seconds")),
                _whole(summary.get("human_clicks")),
                _opt_str(summary.get("bridge_jar_sha256")),
                _opt_str(summary.get("bridge_qualification_state")),
                data_class,
                created_at,
            ),
        )
        row = db.execute("SELECT * FROM play_session WHERE game_id = ?", (game_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"play_session {game_id} konnte nicht gelesen werden")
    return _row_to_play_session(row)


def _row_to_play_note(row: sqlite3.Row) -> dict[str, object]:
    return {
        "note_id": int(row["note_id"]),
        "game_id": str(row["game_id"]),
        "deck_id": _opt_str(row["deck_id"]),
        "revision_id": _opt_str(row["revision_id"]),
        "card_name": _opt_str(row["card_name"]),
        "note_text": str(row["note_text"]),
        "action_hint": _opt_str(row["action_hint"]),
        "created_at": str(row["created_at"]),
    }


def add_play_note(
    store: StudioStore,
    *,
    game_id: str,
    note_text: str,
    deck_id: str | None = None,
    revision_id: str | None = None,
    card_name: str | None = None,
    action_hint: str | None = None,
) -> dict[str, object]:
    """Create one ``play_note`` row; rejects empty ``note_text`` with ``ValueError``."""
    clean_game_id = _opt_str(game_id)
    if clean_game_id is None:
        raise ValueError("game_id darf nicht leer sein")
    clean_text = _opt_str(note_text)
    if clean_text is None:
        raise ValueError("note_text darf nicht leer sein")
    created_at = now_utc()
    with store.connection as db:
        cursor = db.execute(
            "INSERT INTO play_note("
            "game_id, deck_id, revision_id, card_name, note_text, action_hint, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                clean_game_id,
                _opt_str(deck_id),
                _opt_str(revision_id),
                _opt_str(card_name),
                clean_text,
                _opt_str(action_hint),
                created_at,
            ),
        )
        note_id = cursor.lastrowid
        row = db.execute("SELECT * FROM play_note WHERE note_id = ?", (note_id,)).fetchone()
    if row is None:
        raise RuntimeError("play_note konnte nicht gelesen werden")
    return _row_to_play_note(row)


def list_play_notes(
    store: StudioStore,
    *,
    game_id: str | None = None,
    deck_id: str | None = None,
    revision_id: str | None = None,
) -> list[dict[str, object]]:
    """List saved ``play_note`` rows filtered by game, deck, and/or revision."""
    clauses: list[str] = []
    params: list[object] = []
    if game_id is not None:
        clauses.append("game_id = ?")
        params.append(game_id)
    if deck_id is not None:
        clauses.append("deck_id = ?")
        params.append(deck_id)
    if revision_id is not None:
        clauses.append("revision_id = ?")
        params.append(revision_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = store.connection.execute(
        f"SELECT * FROM play_note{where} ORDER BY note_id DESC",
        params,
    ).fetchall()
    return [_row_to_play_note(row) for row in rows]
