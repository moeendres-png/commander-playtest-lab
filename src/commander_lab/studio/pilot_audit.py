"""Opt-in audit recording of pilot requests and objective omission counting (#1524).

This module observes engine-authored ``DecisionRequest`` payloads and the pilot's
``DecisionResponse`` strictly in ``SIMULATED_RESULT`` series (all AI seats, zero human seats).
It is opt-in (default OFF) and never touches Rules authority, pilot decision logic, or PLAY
routes:

* ``PilotAuditPolicy`` delegates ``decide(decision)`` to the wrapped pilot first, observes a
  read-only redacted copy of ``(decision, response)``, and returns the pilot's exact response
  object untouched.
* Audit logs live under ``<data_folder>/pilot_audit/<game_id>.audit.jsonl.gz``, strictly
  separate from ``<data_folder>/games/`` so PLAY endpoints (``/api/games*``, ``/api/play*``)
  never read or expose audit records (``AGENTS.md`` §5).
* Any game header that is not ``SIMULATED_RESULT`` or names any human seat is refused
  fail-closed before creating the audit folder or opening a file.
* ``OmissionCounter`` counts only objective engine-offered opportunities and omissions
  (``n/N``, Owner decision E3): land plays offered vs. not taken in that turn, and commander
  casts offered up to own turn ``T`` vs. not taken (cancelled mana payments do not count as a
  completed cast). No decision judgments, no ratings, no tier-list inputs.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import IO

from .games import (
    COHORT_SIMULATED,
    HUMAN_PILOT_LABEL,
    SERIES_BUFFER_BYTES,
    SERIES_GZIP_COMPRESSLEVEL,
    DecisionPolicy,
    game_cohort,
)
from .store import now_utc

AUDIT_SCHEMA = "studio-pilot-audit-1"
AUDIT_FOLDER = "pilot_audit"
DEFAULT_COMMANDER_TURN_LIMIT = 6
REDACTED_ENGINE_KEY = "redacted-engine-key"

_GAME_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
_SAFE_HEADER_FIELDS = (
    "schema",
    "game_id",
    "data_class",
    "seed",
    "engine_commit",
    "bridge_jar_sha256",
    "bridge_qualification_state",
    "covered_by_sealed_epoch",
    "pilot",
    "pilot_fingerprint",
    "decision_policy",
    "strategy",
)
_SAFE_SEAT_FIELDS = (
    "seat",
    "deck_id",
    "deck_name",
    "deck_hash",
    "commanders",
    "pilot",
    "pilot_fingerprint",
    "style",
)


def _checked_game_id(game_id: str) -> str:
    if not isinstance(game_id, str) or not _GAME_ID_RE.fullmatch(game_id):
        raise ValueError("audit game_id must be lower-case letters, digits, '-' and '_'")
    return game_id


def pilot_audit_folder(data_folder: str | Path, *, create: bool = False) -> Path:
    """Return ``<data_folder>/pilot_audit`` (created only when ``create=True``)."""
    folder = Path(data_folder) / AUDIT_FOLDER
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def audit_log_path(data_folder: str | Path, game_id: str) -> Path | None:
    """Locate a completed (``.audit.jsonl.gz``) or plain (``.audit.jsonl``) audit file."""
    checked = _checked_game_id(game_id)
    folder = pilot_audit_folder(data_folder, create=False)
    gz = folder / f"{checked}.audit.jsonl.gz"
    if gz.is_file():
        return gz
    plain = folder / f"{checked}.audit.jsonl"
    if plain.is_file():
        return plain
    return None


def redact_engine_keys(value: object) -> object:
    """Deep-copy JSON-like structures while redacting ``xmage_key`` fields (read-only on input)."""
    if isinstance(value, Mapping):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str == "xmage_key" and isinstance(item, str) and item:
                cleaned[key_str] = REDACTED_ENGINE_KEY
            else:
                cleaned[key_str] = redact_engine_keys(item)
        return cleaned
    if isinstance(value, list):
        return [redact_engine_keys(item) for item in value]
    if isinstance(value, tuple):
        return [redact_engine_keys(item) for item in value]
    return value


def ensure_simulated_audit_header(header: Mapping[str, object]) -> dict[str, object]:
    """Verify fail-closed that ``header`` is a pure ``SIMULATED_RESULT`` game without humans.

    Returns an allowlisted safe copy of header metadata (no arbitrary paths, credentials, or
    environment fields). Raises ``ValueError`` for any human-seat or non-simulated game.
    """
    if not isinstance(header, Mapping):
        raise ValueError("pilot audit requires a mapping game header")
    cohort = game_cohort(header)
    if cohort != COHORT_SIMULATED:
        raise ValueError(
            f"pilot audit recording refused for cohort {cohort!r}; only {COHORT_SIMULATED!r} allowed"
        )
    raw_humans = header.get("human_seats")
    if raw_humans is not None and (
        not isinstance(raw_humans, (list, tuple)) or len(raw_humans) > 0
    ):
        raise ValueError("pilot audit recording refused: human seats present in header")

    safe_seats: list[dict[str, object]] = []
    raw_seats = header.get("seats")
    if isinstance(raw_seats, Sequence) and not isinstance(raw_seats, (str, bytes)):
        for row in raw_seats:
            if not isinstance(row, Mapping):
                continue
            pilot_label = row.get("pilot")
            if (
                pilot_label == HUMAN_PILOT_LABEL
                or row.get("is_human") is True
                or row.get("human") is True
            ):
                raise ValueError("pilot audit recording refused: human seat detected in seats")
            projected_seat: dict[str, object] = {}
            for field in _SAFE_SEAT_FIELDS:
                if field in row:
                    projected_seat[field] = redact_engine_keys(row[field])
            safe_seats.append(projected_seat)

    projected: dict[str, object] = {}
    for field in _SAFE_HEADER_FIELDS:
        if field in header:
            projected[field] = redact_engine_keys(header[field])
    if safe_seats:
        projected["seats"] = safe_seats
    return projected


def _as_non_negative_int(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _as_positive_int(value: object) -> int | None:
    if type(value) is int and value >= 1:
        return value
    return None


def _is_land_play_option(option: Mapping[str, object]) -> bool:
    if option.get("option_type") == "play_land":
        return True
    meta = option.get("metadata")
    return isinstance(meta, Mapping) and meta.get("ability_type") == "play_land"


def _actor_command_zone(pilot_state: Mapping[str, object]) -> tuple[set[str], set[str]]:
    """Return ``(object_ids, card_names)`` in the deciding actor's command zone."""
    players = pilot_state.get("players")
    if not isinstance(players, Sequence) or isinstance(players, (str, bytes)):
        return set(), set()
    actor_id = pilot_state.get("actor_id")
    actor_row: Mapping[str, object] | None = None
    for row in players:
        if not isinstance(row, Mapping):
            continue
        if row.get("is_actor") is True:
            actor_row = row
            break
        if actor_id is not None and row.get("player_id") == actor_id:
            actor_row = row
    if actor_row is None:
        return set(), set()
    command = actor_row.get("command")
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
        return set(), set()
    ids: set[str] = set()
    names: set[str] = set()
    for obj in command:
        if isinstance(obj, Mapping):
            oid = obj.get("object_id") or obj.get("id")
            if isinstance(oid, str) and oid.strip():
                ids.add(oid.strip())
            name = obj.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
        elif isinstance(obj, str) and obj.strip():
            names.add(obj.strip())
    return ids, names


def _commander_option_key(
    option: Mapping[str, object],
    command_ids: set[str],
    command_names: set[str],
) -> str | None:
    """Identify an engine-offered commander cast from the command zone, else ``None``."""
    meta = option.get("metadata")
    meta_map = meta if isinstance(meta, Mapping) else {}
    option_type = option.get("option_type")
    if option_type == "cast_commander":
        raw_name = meta_map.get("source_name") or option.get("label") or option.get("option_id")
        return (
            str(raw_name).strip() if raw_name is not None and str(raw_name).strip() else "commander"
        )
    if meta_map.get("ability_type") != "spell":
        return None
    source_id = meta_map.get("source_object_id")
    source_name = meta_map.get("source_name")
    id_str = source_id.strip() if isinstance(source_id, str) and source_id.strip() else None
    name_str = source_name.strip() if isinstance(source_name, str) and source_name.strip() else None
    if id_str is not None and command_ids:
        if id_str in command_ids:
            return name_str or id_str
        return None
    if name_str is not None and name_str in command_names:
        return name_str
    return None


def _selected_option_ids(response: Mapping[str, object]) -> set[str]:
    raw = response.get("selected_option_ids")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return set()
    return {str(item) for item in raw if item is not None}


def _kind_entry(
    omissions: int, opportunities: int, *, turn_limit: int | None = None
) -> dict[str, object]:
    entry: dict[str, object] = {
        "omissions": omissions,
        "opportunities": opportunities,
        "rate": round(omissions / opportunities, 4) if opportunities > 0 else None,
        "display": f"{omissions}/{opportunities}" if opportunities > 0 else "unbekannt",
    }
    if turn_limit is not None:
        entry["turn_limit"] = turn_limit
    return entry


class OmissionCounter:
    """Objective counter for engine-offered pilot omissions (Owner decision E3).

    Counts strictly from observed ``(decision, response)`` pairs:
    * ``land_play``: per seat and turn, whether a land play was legally offered and never taken
      in that turn (``n_land / N_land``).
    * ``cast_commander``: per seat, whether a commander in the command zone was legally offered
      to cast on or before that seat's ``commander_turn_limit``-th own turn and never cast
      without cancelling mana payment (``n_cmd / N_cmd``).
    """

    def __init__(self, *, commander_turn_limit: int = DEFAULT_COMMANDER_TURN_LIMIT) -> None:
        if type(commander_turn_limit) is not int or commander_turn_limit < 1:
            raise ValueError("commander_turn_limit must be a positive integer")
        self.commander_turn_limit = commander_turn_limit
        self.total_decisions = 0
        self._own_turns: dict[int, list[int]] = {}
        self._land_offered: dict[int, set[int]] = {}
        self._land_played: dict[int, set[int]] = {}
        self._cmd_offered: dict[int, set[str]] = {}
        self._cmd_cast: dict[int, set[str]] = {}
        self._pending_cmd: dict[int, str | None] = {}

    def _own_turn_index(self, seat: int, turn: int, *, is_own_turn: bool) -> int:
        if not is_own_turn:
            seen = self._own_turns.get(seat)
            return len(seen) if seen else turn
        seen = self._own_turns.setdefault(seat, [])
        if (not seen or seen[-1] != turn) and turn not in seen:
            seen.append(turn)
        return len(seen)

    def observe(
        self,
        decision: Mapping[str, object],
        response: Mapping[str, object],
    ) -> None:
        """Observe one engine decision and pilot response (strictly read-only)."""
        self.total_decisions += 1
        raw_state = decision.get("pilot_state")
        pilot_state = raw_state if isinstance(raw_state, Mapping) else {}
        seat_0 = _as_non_negative_int(decision.get("seat"))
        if seat_0 is None:
            seat_0 = _as_non_negative_int(pilot_state.get("seat"))
        if seat_0 is None:
            return
        seat = seat_0 + 1  # Studio validity_block uses 1-based seats

        raw_options = decision.get("legal_options")
        options = (
            [opt for opt in raw_options if isinstance(opt, Mapping)]
            if isinstance(raw_options, Sequence) and not isinstance(raw_options, (str, bytes))
            else []
        )
        selected = _selected_option_ids(response)
        decision_class = str(decision.get("decision_class") or "")

        if decision_class == "mana_payment":
            for opt in options:
                opt_id = opt.get("option_id")
                if (
                    opt_id is not None
                    and str(opt_id) in selected
                    and opt.get("option_type") == "cancel_mana_payment"
                ):
                    self._pending_cmd[seat] = None
                    break
            return

        if decision_class != "priority":
            return

        # Previous commander cast was not cancelled before this priority window: confirm it.
        pending = self._pending_cmd.pop(seat, None)
        if pending is not None:
            self._cmd_cast.setdefault(seat, set()).add(pending)

        turn = _as_positive_int(pilot_state.get("turn_number"))
        if turn is None:
            return
        actor_id = pilot_state.get("actor_id")
        active_id = pilot_state.get("active_player_id")
        is_own_turn = True if (actor_id is None or active_id is None) else (actor_id == active_id)
        own_turn = self._own_turn_index(seat, turn, is_own_turn=is_own_turn)

        # 1. Land play opportunities (each turn where the engine offered at least one land play)
        land_option_ids = {
            str(opt["option_id"])
            for opt in options
            if opt.get("option_id") is not None and _is_land_play_option(opt)
        }
        if land_option_ids:
            self._land_offered.setdefault(seat, set()).add(turn)
            if land_option_ids & selected:
                self._land_played.setdefault(seat, set()).add(turn)

        # 2. Commander cast opportunities up to own turn T
        if own_turn <= self.commander_turn_limit:
            cmd_ids, cmd_names = _actor_command_zone(pilot_state)
            for opt in options:
                cmd_key = _commander_option_key(opt, cmd_ids, cmd_names)
                if cmd_key is None:
                    continue
                self._cmd_offered.setdefault(seat, set()).add(cmd_key)
                opt_id = opt.get("option_id")
                if opt_id is not None and str(opt_id) in selected:
                    self._pending_cmd[seat] = cmd_key

    def summary(self) -> dict[str, object]:
        """Return an idempotent summary dict for this game (does not mutate counter state)."""
        seats = sorted(set(self._land_offered) | set(self._cmd_offered) | set(self._pending_cmd))
        total_land_om = 0
        total_land_opp = 0
        total_cmd_om = 0
        total_cmd_opp = 0
        by_seat: list[dict[str, object]] = []

        for seat in seats:
            land_off = self._land_offered.get(seat, set())
            land_done = self._land_played.get(seat, set())
            n_land = len(land_off - land_done)
            N_land = len(land_off)

            cmd_off = self._cmd_offered.get(seat, set())
            cmd_done = set(self._cmd_cast.get(seat, set()))
            pending = self._pending_cmd.get(seat)
            if pending is not None:
                cmd_done.add(pending)
            n_cmd = len(cmd_off - cmd_done)
            N_cmd = len(cmd_off)

            total_land_om += n_land
            total_land_opp += N_land
            total_cmd_om += n_cmd
            total_cmd_opp += N_cmd

            seat_opp = N_land + N_cmd
            seat_om = n_land + n_cmd
            if seat_opp > 0:
                by_seat.append(
                    {
                        "seat": seat,
                        "omissions": seat_om,
                        "opportunities": seat_opp,
                        "rate": round(seat_om / seat_opp, 4),
                        "display": f"{seat_om}/{seat_opp}",
                        "by_kind": {
                            "land_play": _kind_entry(n_land, N_land),
                            "cast_commander": _kind_entry(
                                n_cmd, N_cmd, turn_limit=self.commander_turn_limit
                            ),
                        },
                    }
                )

        total_om = total_land_om + total_cmd_om
        total_opp = total_land_opp + total_cmd_opp
        series_entry: dict[str, object] | None = None
        if total_opp > 0:
            series_entry = {
                "omissions": total_om,
                "opportunities": total_opp,
                "rate": round(total_om / total_opp, 4),
                "display": f"{total_om}/{total_opp}",
                "by_kind": {
                    "land_play": _kind_entry(total_land_om, total_land_opp),
                    "cast_commander": _kind_entry(
                        total_cmd_om, total_cmd_opp, turn_limit=self.commander_turn_limit
                    ),
                },
            }
        return {
            "commander_turn_limit": self.commander_turn_limit,
            "total_decisions": self.total_decisions,
            "series": series_entry,
            "by_seat": by_seat,
        }


class PilotAuditRecorder:
    """Streaming audit recorder for one simulated game (written outside ``games/``)."""

    def __init__(
        self,
        data_folder: str | Path,
        game_id: str,
        header: Mapping[str, object],
        *,
        commander_turn_limit: int = DEFAULT_COMMANDER_TURN_LIMIT,
        gzip_compresslevel: int = SERIES_GZIP_COMPRESSLEVEL,
    ) -> None:
        self.game_id = _checked_game_id(game_id)
        # Validate fail-closed BEFORE creating any directory or file!
        self.header = ensure_simulated_audit_header(header)
        self.data_folder = Path(data_folder)
        self.gzip_compresslevel = gzip_compresslevel
        self.counter = OmissionCounter(commander_turn_limit=commander_turn_limit)
        self._seq = 0
        self._closed = False

        folder = pilot_audit_folder(self.data_folder, create=True)
        self.plain_path = folder / f"{self.game_id}.audit.jsonl"
        self.gz_path = folder / f"{self.game_id}.audit.jsonl.gz"
        self._handle: IO[str] | None = self.plain_path.open(
            "w", encoding="utf-8", buffering=SERIES_BUFFER_BYTES
        )
        self._write_line(
            {
                "kind": "header",
                "schema": AUDIT_SCHEMA,
                "game_id": self.game_id,
                "recorded_at": now_utc(),
                "commander_turn_limit": self.counter.commander_turn_limit,
                "header": self.header,
            }
        )

    def _write_line(self, payload: Mapping[str, object]) -> None:
        handle = self._handle
        if handle is None:
            return
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def record(
        self,
        decision: Mapping[str, object],
        response: Mapping[str, object],
    ) -> None:
        """Record one full pilot request + response (read-only on inputs)."""
        if self._closed or self._handle is None:
            return
        self._seq += 1
        self.counter.observe(decision, response)
        entry: dict[str, object] = {
            "kind": "decision",
            "seq": self._seq,
            "decision_id": decision.get("decision_id"),
            "decision_class": decision.get("decision_class"),
            "seat": decision.get("seat"),
            "actor_id": decision.get("actor_id"),
            "prompt": decision.get("prompt"),
            "minimum_selections": decision.get("minimum_selections"),
            "maximum_selections": decision.get("maximum_selections"),
            "source_object": redact_engine_keys(decision.get("source_object")),
            "context": redact_engine_keys(decision.get("context")),
            "legal_options": redact_engine_keys(decision.get("legal_options")),
            "pilot_state": redact_engine_keys(decision.get("pilot_state")),
            "response": redact_engine_keys(response),
        }
        self._write_line(entry)

    def discard(self) -> None:
        """Close and delete partial files (used before restarting a retried game)."""
        self._closed = True
        handle, self._handle = self._handle, None
        if handle is not None:
            with contextlib.suppress(OSError):
                handle.close()
        with contextlib.suppress(OSError):
            self.plain_path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            self.gz_path.unlink(missing_ok=True)

    def close(
        self,
        *,
        status: str,
        winner_seats: Sequence[int] | None = None,
        decision_count: int | None = None,
        semantic_transcript_sha256: str | None = None,
        failure_class: str | None = None,
    ) -> tuple[Path, dict[str, object]]:
        """Write closing summary, compress to ``.audit.jsonl.gz``, and remove plain file."""
        summary = self.counter.summary()
        if not self._closed:
            self._write_line(
                {
                    "kind": "end",
                    "ended_at": now_utc(),
                    "status": status,
                    "winner_seats": list(winner_seats) if winner_seats is not None else [],
                    "decision_count": decision_count
                    if decision_count is not None
                    else self.counter.total_decisions,
                    "semantic_transcript_sha256": semantic_transcript_sha256,
                    "failure_class": failure_class,
                    "omissions": summary,
                }
            )
            self._closed = True
            handle, self._handle = self._handle, None
            if handle is not None:
                handle.flush()
                handle.close()
            if self.plain_path.is_file():
                with (
                    self.plain_path.open("rb") as src,
                    gzip.open(self.gz_path, "wb", compresslevel=self.gzip_compresslevel) as dst,
                ):
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        dst.write(chunk)
                self.plain_path.unlink(missing_ok=True)
        final_path = self.gz_path if self.gz_path.is_file() else self.plain_path
        return final_path, summary


class PilotAuditPolicy:
    """Transparent policy wrapper: observes ``(decision, response)`` without altering behavior."""

    def __init__(self, inner: DecisionPolicy, recorder: PilotAuditRecorder) -> None:
        self._inner = inner
        self._recorder = recorder

    def decide(self, decision: dict[str, object]) -> dict[str, object]:
        response = self._inner.decide(decision)
        self._recorder.record(decision, response)
        return response


def read_audit_entries(path: str | Path) -> Iterator[dict[str, object]]:
    """Yield JSON entries from a ``.audit.jsonl`` or ``.audit.jsonl.gz`` file."""
    target = Path(path)
    opener = gzip.open if target.suffix == ".gz" else open
    with opener(target, "rt", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                yield item


def summarize_audit_file(
    path: str | Path,
    *,
    commander_turn_limit: int = DEFAULT_COMMANDER_TURN_LIMIT,
) -> dict[str, object] | None:
    """Extract or recompute the omission summary from one audit file.

    Uses the stored closing summary when its ``commander_turn_limit`` matches; otherwise
    replays the recorded ``decision`` lines through ``OmissionCounter``. Returns ``None``
    when the file is corrupt or has no valid entries.
    """
    counter = OmissionCounter(commander_turn_limit=commander_turn_limit)
    stored_summary: dict[str, object] | None = None
    saw_header = False
    try:
        for entry in read_audit_entries(path):
            kind = entry.get("kind")
            if kind == "header":
                if entry.get("schema") != AUDIT_SCHEMA:
                    return None
                saw_header = True
            elif kind == "decision":
                response = entry.get("response")
                if isinstance(response, Mapping):
                    counter.observe(entry, response)
            elif kind == "end":
                raw_om = entry.get("omissions")
                if (
                    isinstance(raw_om, dict)
                    and raw_om.get("commander_turn_limit") == commander_turn_limit
                ):
                    stored_summary = raw_om
    except (OSError, ValueError, EOFError):
        return None
    if not saw_header:
        return None
    return stored_summary if stored_summary is not None else counter.summary()


def _extract_kind_counts(
    container: Mapping[str, object],
    kind_name: str,
) -> tuple[int, int] | None:
    by_kind = container.get("by_kind")
    if not isinstance(by_kind, Mapping):
        return None
    entry = by_kind.get(kind_name)
    if not isinstance(entry, Mapping):
        return None
    om = entry.get("omissions")
    opp = entry.get("opportunities")
    if type(om) is int and type(opp) is int and 0 <= om <= opp:
        return om, opp
    return None


def aggregate_series_omissions(
    data_folder: str | Path,
    game_ids: Sequence[str],
    *,
    commander_turn_limit: int = DEFAULT_COMMANDER_TURN_LIMIT,
) -> dict[str, object] | None:
    """Aggregate objective pilot omissions (``n/N``) across audited games of a series.

    Missing audit files are NEVER counted as 0. Returns ``None`` when no game has a valid
    audit file or when total opportunities are 0 (so ``_normalize_pilot_omissions`` yields
    ``"unbekannt"``).
    """
    unique_ids: list[str] = []
    seen_ids: set[str] = set()
    for gid in game_ids:
        if isinstance(gid, str) and gid not in seen_ids and _GAME_ID_RE.fullmatch(gid):
            seen_ids.add(gid)
            unique_ids.append(gid)
    if not unique_ids:
        return None

    games_audited = 0
    total_decisions = 0
    # Per-seat accumulators: [land_om, land_opp, cmd_om, cmd_opp, fallback_om, fallback_opp]
    seat_totals: dict[int, list[int]] = {}
    series_land_om = 0
    series_land_opp = 0
    series_cmd_om = 0
    series_cmd_opp = 0
    series_om_total = 0
    series_opp_total = 0

    for gid in unique_ids:
        path = audit_log_path(data_folder, gid)
        if path is None:
            continue
        game_sum = summarize_audit_file(path, commander_turn_limit=commander_turn_limit)
        if game_sum is None:
            continue
        games_audited += 1
        dec = game_sum.get("total_decisions")
        if type(dec) is int and dec >= 0:
            total_decisions += dec

        raw_seats = game_sum.get("by_seat")
        if isinstance(raw_seats, list):
            for row in raw_seats:
                if not isinstance(row, Mapping):
                    continue
                seat = row.get("seat")
                om = row.get("omissions")
                opp = row.get("opportunities")
                if not (
                    type(seat) is int
                    and seat >= 1
                    and type(om) is int
                    and type(opp) is int
                    and opp > 0
                    and 0 <= om <= opp
                ):
                    continue
                acc = seat_totals.setdefault(seat, [0, 0, 0, 0, 0, 0])
                land_pair = _extract_kind_counts(row, "land_play")
                cmd_pair = _extract_kind_counts(row, "cast_commander")
                if land_pair is not None:
                    acc[0] += land_pair[0]
                    acc[1] += land_pair[1]
                    series_land_om += land_pair[0]
                    series_land_opp += land_pair[1]
                if cmd_pair is not None:
                    acc[2] += cmd_pair[0]
                    acc[3] += cmd_pair[1]
                    series_cmd_om += cmd_pair[0]
                    series_cmd_opp += cmd_pair[1]
                acc[4] += om
                acc[5] += opp
                series_om_total += om
                series_opp_total += opp

    if games_audited == 0 or series_opp_total <= 0:
        return None

    by_seat: list[dict[str, object]] = []
    for seat in sorted(seat_totals):
        l_om, l_opp, c_om, c_opp, tot_om, tot_opp = seat_totals[seat]
        if tot_opp <= 0:
            continue
        by_seat.append(
            {
                "seat": seat,
                "omissions": tot_om,
                "opportunities": tot_opp,
                "rate": round(tot_om / tot_opp, 4),
                "display": f"{tot_om}/{tot_opp}",
                "by_kind": {
                    "land_play": _kind_entry(l_om, l_opp),
                    "cast_commander": _kind_entry(c_om, c_opp, turn_limit=commander_turn_limit),
                },
            }
        )

    return {
        "series": {
            "omissions": series_om_total,
            "opportunities": series_opp_total,
            "rate": round(series_om_total / series_opp_total, 4),
            "display": f"{series_om_total}/{series_opp_total}",
            "by_kind": {
                "land_play": _kind_entry(series_land_om, series_land_opp),
                "cast_commander": _kind_entry(
                    series_cmd_om, series_cmd_opp, turn_limit=commander_turn_limit
                ),
            },
        },
        "by_seat": by_seat,
        "commander_turn_limit": commander_turn_limit,
        "games_audited": games_audited,
        "games_requested": len(unique_ids),
        "total_decisions": total_decisions,
    }
