"""Per-card outcomes from simulated games: first dealt hand versus not.

The shuffle decides which seven cards a seat is dealt, so "the card is in the first dealt
hand" is a randomised exposure inside every game. The win rate of that seat with the card in
its first hand minus the win rate without it is therefore a fair comparison, unlike "the card
was cast", which depends on how the pilot played. Everything here reads the recorded game
logs (``games.py``) and decides no rule. The result is a ``SIMULATED_RESULT``: these pilots,
this pod set, this engine commit. It says nothing about pilot quality or about cards whose
value arrives late.

Cards seen by the end of the seat's third own turn are reported as a secondary count only:
effect draws and mulligan bottoms depend on play, so that set is NOT randomised.

Games are counted per deck state (#1657): a seat is grouped by (``deck_id``, ``deck_hash``) of
the log header. Logs written before the header carried a hash form the visible stand "Stand
unbekannt" with its own n/N and are never added to a known stand. Several known stands of one
deck are combined only stratified (one difference per stand, Mantel-Haenszel weights), with the
number of strata in the answer, and never across a change of engine, bridge jar, pilot, decision
policy or pod set.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import zlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from commander_lab.bridge_qualification import BRIDGE_AHEAD, BRIDGE_ALIGNED

from .games import LOG_SCHEMA
from .simulations import wilson_score_interval

SCHEMA = "studio-card-outcomes-2"
DATA_CLASS = "SIMULATED_RESULT"
ESTIMAND = (
    "win rate with the card in the first dealt hand minus without; "
    "simulated games, these pilots, this pod set"
)
DEFAULT_MIN_EXPOSED = 100
MULLIGAN_CLASS = "mulligan"
TAKE_MULLIGAN_LABEL = "Take mulligan"
OWN_TURNS_SECONDARY = 3
# A typical card is in the first seven of a 99-card library about 7 % of the time.
EXPECTED_EXPOSURE = 7 / 99
CACHE_DIR = ".outcomes-cache"
# 3 since #1657: a seat carries the deck state (``deck_hash``, ``revision_id``) of the header;
# a version-2 entry knows no hash and is read again from its log.
CACHE_VERSION = 3
PARALLEL_MIN_LOGS = 8  # cold logs before a process pool pays for itself
MAX_WORKERS = 4
CHANCE_RATE = 0.05
_DECK_HASH = re.compile(r"[0-9a-f]{64}")
POOLING_METHOD = (
    "stratified by deck state: Mantel-Haenszel risk difference (weights n_in*n_not/n per "
    "stand), 95 % Wald interval with the Sato variance; rates are given per stand only"
)
# The scalar keys that open every frame line; None groups mean JSON ``null``.
_FRAME_HEAD = re.compile(
    rb'\{\s*"kind"\s*:\s*"frame"\s*,[^{}\[\]]{0,300}?"turn"\s*:\s*(-?\d+|null)\s*,'
    rb'[^{}\[\]]{0,300}?"active_seat"\s*:\s*(-?\d+|null)\s*,\s*"seat"\s*:\s*(-?\d+|null)\s*,'
    rb'\s*"decision_class"\s*:\s*"([^"\\]*)"'
)

Result = Literal["win", "loss", "draw"]
CardStatus = Literal["MEASURED", "INSUFFICIENT_SAMPLE"]


class SeatExposure(TypedDict):
    seat: int
    deck_id: str
    commanders: list[str]
    first_dealt_hand: list[str] | None
    mulligans_taken: int
    seen_by_own_turn_3: list[str]
    result: Result
    win_credit: float
    # The deck state of the seat (#1657); missing or None in a log without one.
    deck_hash: NotRequired[str | None]
    revision_id: NotRequired[str | None]


class GameExposure(TypedDict):
    game_id: str
    seed: int | None
    engine_commit: str | None
    bridge_jar_sha256: NotRequired[str | None]
    bridge_qualification_state: NotRequired[str | None]
    covered_by_sealed_epoch: NotRequired[bool]
    pilot: str | None
    decision_policy: str | None
    winner_seats: list[int]
    seats: list[SeatExposure]


class SecondaryCount(TypedDict):
    games_seen_by_own_turn_3: int
    wins_seen_by_own_turn_3: float
    note: str


class CardOutcome(TypedDict):
    card: str
    status: CardStatus
    reason: str | None
    games_total: int
    games_in_first_hand: int
    wins_in_first_hand: float
    games_not_in_first_hand: int
    wins_not_in_first_hand: float
    rate_in: float | None
    rate_in_ci95: list[float] | None
    rate_not: float | None
    rate_not_ci95: list[float] | None
    difference_pp: float | None
    difference_ci95_pp: list[float] | None
    secondary: SecondaryCount
    # Pooled row only: the number of deck states whose own difference enters this row.
    strata: NotRequired[int]


class PodCount(TypedDict):
    opponents: list[str]
    games: int


class Pooling(TypedDict):
    status: Literal["NO_KNOWN_STAND", "SINGLE_STAND", "POOLED", "NOT_POOLED"]
    reason: str | None
    method: str | None


class CardOutcomeTable(TypedDict):
    schema: str
    status: Literal["OK", "NO_GAMES", "NOT_POOLED"]
    deck_id: str
    data_class: str
    estimand: str
    min_exposed: int
    games_total: int
    games_skipped: int
    games_skipped_unreadable: int
    seats_without_opening_hand: int
    duplicate_logs_ignored: int
    multi_seat_games: int
    comparisons: int
    expected_chance_findings: float
    draw_games: int
    mulligans_taken: int
    engine_commits: list[str]
    bridge_jar_sha256s: list[str]
    bridge_qualification_states: list[str]
    covered_by_sealed_epoch: bool
    pilots: list[str]
    decision_policies: list[str]
    seeds: int
    pods: list[PodCount]
    commanders_excluded: list[str]
    warnings: list[str]
    cards: list[CardOutcome]
    # One deck state (#1657): its hash (None = "Stand unbekannt") and the Studio revisions
    # the logs name for it.
    deck_hash: NotRequired[str | None]
    revision_ids: NotRequired[list[str]]
    # The answer for a deck (``stand_tables``): the known stands, the unknown stand apart.
    strata: NotRequired[int]
    pooling: NotRequired[Pooling]
    stands: NotRequired[list[CardOutcomeTable]]
    unknown_stand: NotRequired[CardOutcomeTable | None]


class UnrankedCard(TypedDict):
    card: str
    status: CardStatus
    reason: str | None


class Ranking(TypedDict):
    ranked: list[CardOutcome]
    unranked: list[UnrankedCard]


class LoadReport(TypedDict):
    exposures: list[GameExposure]
    skipped_with_deck: dict[str, int]
    skipped_unreadable: int
    skipped_ids: list[str]
    duplicate_logs: int
    pool_fallback: bool


# --- reading one log -------------------------------------------------------------------


def _int(value: object) -> int | None:
    return value if type(value) is int else None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _names(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, str)]


def _credit(seat: int, winners: Sequence[int]) -> tuple[Result, float]:
    if seat in winners:
        return ("win", 1.0) if len(winners) == 1 else ("draw", 1.0 / len(winners))
    return ("draw", 0.0) if not winners else ("loss", 0.0)


def _deck_hash(value: object) -> str | None:
    """A header hash names a deck state only as 64 lowercase hex digits; else unknown."""
    return value if isinstance(value, str) and _DECK_HASH.fullmatch(value) else None


def _seat_exposure(
    seat: int,
    deck_id: str,
    commanders: list[str],
    frames: Sequence[dict[str, object]],
    winners: Sequence[int],
    *,
    deck_hash: str | None = None,
    revision_id: str | None = None,
) -> SeatExposure:
    first: list[str] | None = None
    taken = 0
    seen: set[str] = set()
    own_turns: set[int] = set()
    for frame in frames:
        turn = _int(frame.get("turn"))
        if _int(frame.get("active_seat")) == seat and turn is not None:
            own_turns.add(turn)
        if _int(frame.get("seat")) != seat:
            continue  # only the deciding seat's own hand is visible
        hand = _hand_of(frame, seat)
        if frame.get("decision_class") == MULLIGAN_CLASS:
            chosen = _names(frame.get("chosen")) or []
            if TAKE_MULLIGAN_LABEL in chosen:
                taken += 1
            if first is None and hand:
                first = list(hand)
        if hand and len(own_turns) <= OWN_TURNS_SECONDARY:
            seen.update(hand)
    result, credit = _credit(seat, winners)
    return {
        "seat": seat,
        "deck_id": deck_id,
        "commanders": commanders,
        "first_dealt_hand": first,
        "mulligans_taken": taken,
        "seen_by_own_turn_3": sorted(seen),
        "result": result,
        "win_credit": credit,
        "deck_hash": deck_hash,
        "revision_id": revision_id,
    }


def _player_rows(frame: dict[str, object]) -> list[dict[str, object]]:
    players = frame.get("players")
    if not isinstance(players, list):
        return []
    return [row for row in players if isinstance(row, dict)]


def _hand_of(frame: dict[str, object], seat: int) -> list[str] | None:
    """The hand of ``seat`` only when ``seat`` is the deciding seat (others are hidden)."""
    if _int(frame.get("seat")) != seat:
        return None
    for row in _player_rows(frame):
        if _int(row.get("seat")) == seat:
            return _names(row.get("hand")) or None
    return None


def _opt_int(raw: bytes) -> int | None:
    return None if raw == b"null" else int(raw)


def _unpacked(path: Path) -> bytes:
    """The whole log as bytes; a packed log is inflated straight from its bytes."""
    data = path.read_bytes()
    if path.suffix != ".gz":
        return data
    parts: list[bytes] = []
    while data:
        inflater = zlib.decompressobj(wbits=31)
        parts.append(inflater.decompress(data))
        if not inflater.eof:
            raise EOFError("truncated gzip member")
        data = inflater.unused_data
    return b"".join(parts)


def _scan(
    path: Path, *, fast: bool
) -> tuple[dict[str, object] | None, dict[str, object] | None, list[dict[str, object]]]:
    """Header, last result record and the frames that can matter, from one line stream.

    ``fast`` skips ``json.loads`` for a frame line whose head (turn, active seat, deciding
    seat, decision class) is read by pattern when the frame is not a mulligan decision and the
    deciding seat is already past its ``OWN_TURNS_SECONDARY``-th own turn: such a frame can only
    add an own turn, which is kept as a stub. Once every seat is past that turn, such frames
    are dropped. A line whose head does not match is always parsed.
    """
    header: dict[str, object] | None = None
    result: dict[str, object] | None = None
    frames: list[dict[str, object]] = []
    own_turns: dict[int, set[int]] = {}
    raw = _unpacked(path)
    settled = False  # every seat is past its OWN_TURNS_SECONDARY-th own turn
    pos = 0
    while True:
        end = raw.find(b"\n", pos)
        if end < 0:
            break  # after the last newline: nothing, or an entry still being written
        start, pos = pos, end + 1
        match = _FRAME_HEAD.match(raw, start, end) if fast and own_turns else None
        if match is not None and match.group(4) != MULLIGAN_CLASS.encode():
            if settled:
                continue  # no hand or turn after this point can change the result
            turn, active, deciding = (_opt_int(g) for g in match.groups()[:3])
            new_turn = False
            if active in own_turns and turn is not None and turn not in own_turns[active]:
                own_turns[active].add(turn)
                new_turn = True
                settled = all(len(t) > OWN_TURNS_SECONDARY for t in own_turns.values())
            if deciding not in own_turns or len(own_turns[deciding]) > OWN_TURNS_SECONDARY:
                if new_turn:
                    frames.append({"kind": "frame", "turn": turn, "active_seat": active})
                continue
        entry = json.loads(raw[start:end])
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == "header":
            if header is None:
                header = entry
                rows = entry.get("seats")
                for row in rows if isinstance(rows, list) else []:
                    seat = _int(row.get("seat")) if isinstance(row, dict) else None
                    if seat is not None:
                        own_turns[seat] = set()
        elif kind == "result":
            result = entry
        elif kind == "frame":
            frames.append(entry)
            turn, active = _int(entry.get("turn")), _int(entry.get("active_seat"))
            if active in own_turns and turn is not None:
                own_turns[active].add(turn)
                settled = all(len(t) > OWN_TURNS_SECONDARY for t in own_turns.values())
    return header, result, frames


def _read_log(path: Path, *, fast: bool = True) -> tuple[GameExposure | None, list[str]]:
    """The exposure of one log (or None) and the deck ids named in its header."""
    try:
        header, result, frames = _scan(path, fast=fast)
    except (OSError, EOFError, ValueError, zlib.error):
        return None, []
    if header is None or header.get("schema") != LOG_SCHEMA:
        return None, []
    seats_raw = header.get("seats")
    seat_rows = [s for s in seats_raw if isinstance(s, dict)] if isinstance(seats_raw, list) else []
    deck_ids = [d for d in (_str(s.get("deck_id")) for s in seat_rows) if d]
    if result is None or result.get("status") != "finished":
        return None, deck_ids
    winners_raw = result.get("winner_seats")
    winners = (
        sorted({w for w in (_int(x) for x in winners_raw) if w is not None})
        if isinstance(winners_raw, list)
        else []
    )
    seats: list[SeatExposure] = []
    for row in seat_rows:
        seat, deck_id = _int(row.get("seat")), _str(row.get("deck_id"))
        if seat is None or deck_id is None:
            continue
        seats.append(
            _seat_exposure(
                seat,
                deck_id,
                _names(row.get("commanders")) or [],
                frames,
                winners,
                deck_hash=_deck_hash(row.get("deck_hash")),
                revision_id=_str(row.get("studio_revision_id")),
            )
        )
    game_id = _str(header.get("game_id")) or path.name.split(".jsonl", 1)[0]
    bridge_sha = _str(header.get("bridge_jar_sha256")) or _str(result.get("bridge_jar_sha256"))
    qual_state = _str(header.get("bridge_qualification_state")) or _str(
        result.get("bridge_qualification_state")
    )
    covered = (
        header.get("covered_by_sealed_epoch") is True
        and qual_state == BRIDGE_ALIGNED
        and bridge_sha is not None
    )
    return {
        "game_id": game_id,
        "seed": _int(header.get("seed")),
        "engine_commit": _str(header.get("engine_commit")),
        "bridge_jar_sha256": bridge_sha,
        "bridge_qualification_state": qual_state,
        "covered_by_sealed_epoch": covered,
        "pilot": _str(header.get("pilot")),
        "decision_policy": _str(header.get("decision_policy")),
        "winner_seats": winners,
        "seats": seats,
    }, deck_ids


def _cache_file(path: Path) -> Path:
    return path.parent / CACHE_DIR / f"{path.name}.json"


def _valid_seat(row: object) -> bool:
    """One cached seat entry, field by field: ``aggregate`` reads every one of these."""
    if not isinstance(row, dict):
        return False
    hand = row.get("first_dealt_hand")
    credit = row.get("win_credit")
    deck_hash = row.get("deck_hash")
    revision_id = row.get("revision_id")
    return (
        type(row.get("seat")) is int
        and isinstance(row.get("deck_id"), str)
        and isinstance(row.get("commanders"), list)
        and all(isinstance(name, str) for name in row["commanders"])
        and (hand is None or (isinstance(hand, list) and all(isinstance(c, str) for c in hand)))
        and type(row.get("mulligans_taken")) is int
        and isinstance(row.get("seen_by_own_turn_3"), list)
        and all(isinstance(c, str) for c in row["seen_by_own_turn_3"])
        and row.get("result") in ("win", "loss", "draw")
        and isinstance(credit, (int, float))
        and not isinstance(credit, bool)
        # A NaN or infinite credit parses as a float and would sail through the
        # type check, then poison every rate of the table; it is a miss instead.
        and math.isfinite(credit)
        # A missing key reads as "Stand unbekannt"; only CACHE_VERSION keeps an entry written
        # before #1657 from passing as such (it is read again from its log).
        and (deck_hash is None or _deck_hash(deck_hash) is not None)
        and (revision_id is None or isinstance(revision_id, str))
    )


def _valid_exposure(exposure: object) -> bool:
    """The whole cached exposure, structurally: anything less is a miss, never a crash.

    A cache entry is only a shortcut for re-reading the log. An entry that parses as JSON
    and matches version, size and mtime but is damaged inside (a seat that is no dict, a
    credit that is a string) used to sail through the shallow check and then raise inside
    ``aggregate`` — a 500 on the outcomes route. Such an entry is now rejected here and
    rebuilt from the log instead (#1267, robustness from the #1245 review).
    """
    if not isinstance(exposure, dict):
        return False
    winners = exposure.get("winner_seats")
    seats = exposure.get("seats")
    covered = exposure.get("covered_by_sealed_epoch")
    return (
        isinstance(exposure.get("game_id"), str)
        and (exposure.get("seed") is None or type(exposure.get("seed")) is int)
        and all(
            exposure.get(key) is None or isinstance(exposure.get(key), str)
            for key in (
                "engine_commit",
                "bridge_jar_sha256",
                "bridge_qualification_state",
                "pilot",
                "decision_policy",
            )
        )
        and (covered is None or isinstance(covered, bool))
        and isinstance(winners, list)
        and all(type(w) is int for w in winners)
        and isinstance(seats, list)
        and all(_valid_seat(row) for row in seats)
    )


def _cached(cache: Path, size: int, mtime_ns: int) -> tuple[GameExposure, list[str]] | None:
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    exposure, deck_ids = data.get("exposure"), data.get("deck_ids")
    if (
        data.get("version") != CACHE_VERSION
        or data.get("size") != size
        or data.get("mtime_ns") != mtime_ns
        or not _valid_exposure(exposure)
        or not isinstance(deck_ids, list)
        or not all(isinstance(d, str) for d in deck_ids)
    ):
        return None
    return cast(GameExposure, exposure), deck_ids


def _store(
    cache: Path, size: int, mtime_ns: int, exposure: GameExposure, deck_ids: list[str]
) -> None:
    payload = {
        "version": CACHE_VERSION,
        "size": size,
        "mtime_ns": mtime_ns,
        "exposure": exposure,
        "deck_ids": deck_ids,
    }
    # The temp name carries the thread id as well as the process id: two threads of one
    # process storing the same entry must not write through one shared temp file and
    # replace each other's half-written payload (#1267, robustness from the #1245 review).
    temp = cache.with_name(f"{cache.name}.{os.getpid()}-{threading.get_ident()}.tmp")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        temp.unlink(missing_ok=True)  # a cache that cannot be written is only slower


def _is_cached(path: Path) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    return _cached(_cache_file(path), stat.st_size, stat.st_mtime_ns) is not None


def _read(path: Path, *, fast: bool = True) -> tuple[GameExposure | None, list[str]]:
    """``_read_log`` through the per-log cache (finished packed logs only)."""
    if not fast or path.suffix != ".gz":
        return _read_log(path, fast=fast)
    try:
        stat = path.stat()
    except OSError:
        return None, []
    cache = _cache_file(path)
    hit = _cached(cache, stat.st_size, stat.st_mtime_ns)
    if hit is not None:
        return hit
    exposure, deck_ids = _read_log(path, fast=True)
    if exposure is not None:
        _store(cache, stat.st_size, stat.st_mtime_ns, exposure, deck_ids)
    return exposure, deck_ids


def game_exposures(log_path: str | Path) -> GameExposure | None:
    """Per-seat exposure of one finished game; None for an unfinished or failed game.

    A game without a ``result`` record, or whose status is not ``finished``, is skipped by
    the caller and never counted as a loss.
    """
    return _read(Path(log_path))[0]


def load_exposures(games_dir: str | Path) -> LoadReport:
    """Every usable game in a games folder, plus which logs were skipped and for which decks."""
    folder = Path(games_dir)
    paths: dict[str, Path] = {}
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.name.endswith((".jsonl.gz", ".jsonl")):
                key = path.name.split(".jsonl", 1)[0]
                if key not in paths or path.suffix == ".gz":
                    paths[key] = path
    exposures: list[GameExposure] = []
    skipped_with_deck: Counter[str] = Counter()
    unreadable = 0
    skipped_ids: list[str] = []
    seen_games: set[str] = set()
    duplicates = 0
    ordered = sorted(paths.items())
    cold = [path for _, path in ordered if path.suffix == ".gz" and not _is_cached(path)]
    warmed: dict[Path, tuple[GameExposure | None, list[str]]] = {}
    pool_fallback = False
    if len(cold) >= PARALLEL_MIN_LOGS:
        try:
            with ProcessPoolExecutor(max_workers=min(MAX_WORKERS, os.cpu_count() or 1)) as pool:
                warmed = dict(zip(cold, pool.map(_read, cold, chunksize=4), strict=True))
        except Exception:
            # A pool that cannot start (restricted sandbox, no semaphore, interpreter
            # shutdown) must not lose the whole folder: the same reads run serially in
            # the loop below, only slower (#1267, robustness from the #1245 review).
            warmed = {}
            pool_fallback = True
    for key, path in ordered:
        exposure, deck_ids = warmed[path] if path in warmed else _read(path)
        if exposure is not None:
            if exposure["game_id"] in seen_games:
                duplicates += 1  # the same game under another file name: first name wins
                continue
            seen_games.add(exposure["game_id"])
            exposures.append(exposure)
            continue
        skipped_ids.append(key)
        if not deck_ids:
            unreadable += 1
        for deck_id in set(deck_ids):
            skipped_with_deck[deck_id] += 1
    return {
        "exposures": exposures,
        "skipped_with_deck": dict(skipped_with_deck),
        "skipped_unreadable": unreadable,
        "skipped_ids": skipped_ids,
        "duplicate_logs": duplicates,
        "pool_fallback": pool_fallback,
    }


# --- statistics ------------------------------------------------------------------------


def newcombe_difference(
    p1: float, ci1: tuple[float, float], p2: float, ci2: tuple[float, float]
) -> tuple[float, float, float]:
    """Newcombe hybrid score interval for ``p1 - p2`` built from two Wilson intervals.

    lower = d - sqrt((p1 - l1)^2 + (u2 - p2)^2), upper = d + sqrt((u1 - p1)^2 + (p2 - l2)^2).
    """
    d = p1 - p2
    lower = d - math.sqrt((p1 - ci1[0]) ** 2 + (ci2[1] - p2) ** 2)
    upper = d + math.sqrt((ci1[1] - p1) ** 2 + (p2 - ci2[0]) ** 2)
    return d, lower, upper


def wilson_unrounded(wins: float, total: int) -> tuple[float, float]:
    """The Wilson 95 % bounds of ``simulations.wilson_score_interval`` without rounding."""
    if total <= 0:
        return (0.0, 0.0)
    p = max(0.0, min(1.0, wins / total))
    z = 1.95996
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    spread = (
        z * math.sqrt(max(0.0, (p * (1.0 - p)) / total + (z * z) / (4.0 * total * total)))
    ) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def _pp(value: float) -> float:
    return round(value * 100.0, 3)


def _card_row(
    card: str,
    *,
    total: int,
    total_wins: float,
    n_in: int,
    wins_in: float,
    seen_games: int,
    seen_wins: float,
    min_exposed: int,
) -> CardOutcome:
    n_not, wins_not = total - n_in, total_wins - wins_in
    rate_in = wins_in / n_in if n_in else None
    rate_not = wins_not / n_not if n_not else None
    ci_in = wilson_score_interval(wins_in, n_in) if n_in else None
    ci_not = wilson_score_interval(wins_not, n_not) if n_not else None
    diff: float | None = None
    diff_ci: list[float] | None = None
    if rate_in is not None and rate_not is not None:
        d, lo, hi = newcombe_difference(
            rate_in, wilson_unrounded(wins_in, n_in), rate_not, wilson_unrounded(wins_not, n_not)
        )
        diff, diff_ci = _pp(d), [_pp(lo), _pp(hi)]
    reasons = []
    if n_in < min_exposed:
        reasons.append(f"first-hand games {n_in} < {min_exposed}")
    if n_not < min_exposed:
        reasons.append(f"games without the card in the first hand {n_not} < {min_exposed}")
    return {
        "card": card,
        "status": "INSUFFICIENT_SAMPLE" if reasons else "MEASURED",
        "reason": "; ".join(reasons) or None,
        "games_total": total,
        "games_in_first_hand": n_in,
        "wins_in_first_hand": round(wins_in, 6),
        "games_not_in_first_hand": n_not,
        "wins_not_in_first_hand": round(wins_not, 6),
        "rate_in": None if rate_in is None else round(rate_in, 6),
        "rate_in_ci95": None if ci_in is None else list(ci_in),
        "rate_not": None if rate_not is None else round(rate_not, 6),
        "rate_not_ci95": None if ci_not is None else list(ci_not),
        "difference_pp": diff,
        "difference_ci95_pp": diff_ci,
        "secondary": {
            "games_seen_by_own_turn_3": seen_games,
            "wins_seen_by_own_turn_3": round(seen_wins, 6),
            "note": "NOT randomised: effect draws and mulligan bottoms depend on play",
        },
    }


def _distinct(values: Iterable[str | None]) -> list[str]:
    return sorted({v for v in values if v})


def empty_table(deck_id: str, *, min_exposed: int = DEFAULT_MIN_EXPOSED) -> CardOutcomeTable:
    return {
        "schema": SCHEMA,
        "status": "NO_GAMES",
        "deck_id": deck_id,
        "data_class": DATA_CLASS,
        "estimand": ESTIMAND,
        "min_exposed": min_exposed,
        "games_total": 0,
        "games_skipped": 0,
        "games_skipped_unreadable": 0,
        "seats_without_opening_hand": 0,
        "duplicate_logs_ignored": 0,
        "multi_seat_games": 0,
        "comparisons": 0,
        "expected_chance_findings": 0.0,
        "draw_games": 0,
        "mulligans_taken": 0,
        "engine_commits": [],
        "bridge_jar_sha256s": [],
        "bridge_qualification_states": [],
        "covered_by_sealed_epoch": False,
        "pilots": [],
        "decision_policies": [],
        "seeds": 0,
        "pods": [],
        "commanders_excluded": [],
        "warnings": [],
        "cards": [],
    }


def aggregate(
    exposures: Iterable[GameExposure],
    *,
    deck_id: str,
    min_exposed: int = DEFAULT_MIN_EXPOSED,
    allow_mixed: bool = False,
    games_skipped: int = 0,
    games_skipped_unreadable: int = 0,
    duplicate_logs_ignored: int = 0,
) -> CardOutcomeTable:
    """The card table of one deck. Mixed engine commits, bridge jars or pilots raise unless allowed."""
    table = empty_table(deck_id, min_exposed=min_exposed)
    table["games_skipped"] = games_skipped
    table["games_skipped_unreadable"] = games_skipped_unreadable
    table["duplicate_logs_ignored"] = duplicate_logs_ignored
    units: list[tuple[GameExposure, SeatExposure]] = []
    multi_seat = 0
    for game in exposures:
        own = sorted((s for s in game["seats"] if s["deck_id"] == deck_id), key=lambda s: s["seat"])
        if own:
            units.append((game, own[0]))  # one seat per deck and game: the lowest
            multi_seat += len(own) > 1
    if not units:
        return table
    commits = _distinct(g["engine_commit"] for g, _ in units)
    bridge_shas = _distinct(g.get("bridge_jar_sha256") for g, _ in units)
    qual_states = _distinct(g.get("bridge_qualification_state") for g, _ in units)
    pilots = _distinct(g["pilot"] for g, _ in units)
    policies = _distinct(g["decision_policy"] for g, _ in units)
    warnings: list[str] = []
    for label, values in (
        ("engine commits", commits),
        ("bridge jar SHA-256 digests", bridge_shas),
        ("pilot versions", pilots),
        ("decision policies", policies),
    ):
        if len(values) > 1:
            if not allow_mixed:
                raise ValueError(f"mixed {label} in one aggregate: {', '.join(values)}")
            warnings.append(f"mixed {label} pooled: {', '.join(values)}")
    if any(g["engine_commit"] is None for g, _ in units):
        warnings.append("some games carry no engine commit")
    if any(not g.get("bridge_jar_sha256") for g, _ in units):
        warnings.append("some games carry no bridge jar SHA-256")
    if BRIDGE_AHEAD in qual_states:
        warnings.append(
            "BRIDGE_AHEAD_OF_QUALIFICATION: bridge differs from sealed epoch; "
            "results are not covered by the sealed epoch"
        )
    commanders = sorted({name for _, s in units for name in s["commanders"]})
    commander_set = set(commanders)
    usable = [(g, s) for g, s in units if s["first_dealt_hand"] is not None]
    no_hand = len(units) - len(usable)
    total = len(usable)
    covered_by_sealed_epoch = bool(usable) and all(
        (g.get("covered_by_sealed_epoch") is True)
        and (g.get("bridge_qualification_state") == BRIDGE_ALIGNED)
        and bool(g.get("bridge_jar_sha256"))
        for g, _ in usable
    )
    total_wins = sum(s["win_credit"] for _, s in usable)
    n_in: Counter[str] = Counter()
    wins_in: defaultdict[str, float] = defaultdict(float)
    seen_n: Counter[str] = Counter()
    seen_w: defaultdict[str, float] = defaultdict(float)
    pods: Counter[tuple[str, ...]] = Counter()
    for game, seat in usable:
        hand = set(seat["first_dealt_hand"] or []) - commander_set
        for card in hand:
            n_in[card] += 1
            wins_in[card] += seat["win_credit"]
        for card in set(seat["seen_by_own_turn_3"]) - commander_set:
            seen_n[card] += 1
            seen_w[card] += seat["win_credit"]
        pods[tuple(sorted(o["deck_id"] for o in game["seats"] if o["seat"] != seat["seat"]))] += 1
    names = sorted(set(n_in) | set(seen_n))
    table["status"] = "OK"
    table["games_total"] = total
    table["seats_without_opening_hand"] = no_hand
    table["draw_games"] = sum(1 for _, s in usable if s["result"] == "draw")
    table["mulligans_taken"] = sum(s["mulligans_taken"] for _, s in usable)
    table["engine_commits"] = commits
    table["bridge_jar_sha256s"] = bridge_shas
    table["bridge_qualification_states"] = qual_states
    table["covered_by_sealed_epoch"] = covered_by_sealed_epoch
    table["pilots"] = pilots
    table["decision_policies"] = policies
    table["seeds"] = len({g["seed"] for g, _ in usable if g["seed"] is not None})
    table["pods"] = [
        {"opponents": list(pod), "games": count}
        for pod, count in sorted(pods.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    table["commanders_excluded"] = commanders
    table["multi_seat_games"] = multi_seat
    if multi_seat:
        warnings.append(
            f"{multi_seat} game(s) seat this deck more than once: only the lowest seat is counted"
        )
    if duplicate_logs_ignored:
        warnings.append(
            f"{duplicate_logs_ignored} duplicate log(s) with an already counted game_id ignored"
        )
    if no_hand:
        warnings.append(f"{no_hand} seat(s) without a recorded opening hand were left out")
    if total < math.ceil(min_exposed / EXPECTED_EXPOSURE):
        warnings.append(
            f"only {total} games: a typical card is in the first hand in about "
            f"{EXPECTED_EXPOSURE:.0%} of games, so few cards can reach {min_exposed} exposed games"
        )
    table["warnings"] = warnings
    rows = [
        _card_row(
            card,
            total=total,
            total_wins=total_wins,
            n_in=n_in[card],
            wins_in=wins_in[card],
            seen_games=seen_n[card],
            seen_wins=seen_w[card],
            min_exposed=min_exposed,
        )
        for card in names
    ]
    table["cards"] = rows
    table["comparisons"] = sum(1 for row in rows if row["status"] == "MEASURED")
    table["expected_chance_findings"] = round(CHANCE_RATE * table["comparisons"], 1)
    return table


# --- deck states (#1657) ----------------------------------------------------------------


def stand_of(seat: SeatExposure) -> str | None:
    """The deck state a seat is counted under, inside its deck id: its header hash.

    ``None`` is the stand "Stand unbekannt" (a log written before the header named a hash).
    """
    return seat.get("deck_hash")


def own_seat(game: GameExposure, deck_id: str) -> SeatExposure | None:
    """The seat of ``deck_id`` that counts in ``game``: the lowest, as in :func:`aggregate`."""
    own = sorted((s for s in game["seats"] if s["deck_id"] == deck_id), key=lambda s: s["seat"])
    return own[0] if own else None


def _usable_counts(
    games: Iterable[GameExposure], deck_id: str, commander_set: set[str]
) -> tuple[
    int, float, Counter[str], defaultdict[str, float], Counter[str], defaultdict[str, float]
]:
    """Games, wins and per-card first-hand / seen counts of one stand (as :func:`aggregate`)."""
    total, total_wins = 0, 0.0
    n_in: Counter[str] = Counter()
    wins_in: defaultdict[str, float] = defaultdict(float)
    seen_n: Counter[str] = Counter()
    seen_w: defaultdict[str, float] = defaultdict(float)
    for game in games:
        seat = own_seat(game, deck_id)
        if seat is None or seat["first_dealt_hand"] is None:
            continue
        total += 1
        total_wins += seat["win_credit"]
        for card in set(seat["first_dealt_hand"]) - commander_set:
            n_in[card] += 1
            wins_in[card] += seat["win_credit"]
        for card in set(seat["seen_by_own_turn_3"]) - commander_set:
            seen_n[card] += 1
            seen_w[card] += seat["win_credit"]
    return total, total_wins, n_in, wins_in, seen_n, seen_w


def mantel_haenszel_difference(
    strata: Sequence[tuple[int, float, int, float]],
) -> tuple[float, float, float, int] | None:
    """Stratified risk difference over ``(n_in, wins_in, n_not, wins_not)`` per stratum.

    Mantel-Haenszel weights ``n_in * n_not / n``; the variance is Sato's estimator, which is
    the Wald variance for one stratum. Returns ``(difference, lower, upper, strata used)`` with
    95 % bounds, or None when no stratum has games on both sides. A stratum without games on
    one side has weight 0 and does not count as used.
    """
    sum_w = sum_dw = sum_p = sum_q = 0.0
    used = 0
    for n1, y1, n0, y0 in strata:
        n = n1 + n0
        if n1 <= 0 or n0 <= 0:
            continue
        used += 1
        sum_w += n1 * n0 / n
        sum_dw += (y1 * n0 - y0 * n1) / n
        sum_p += (n1 * n1 * y0 - n0 * n0 * y1 + n1 * n0 * (n0 - n1) / 2.0) / (n * n)
        sum_q += (y1 * (n0 - y0) + y0 * (n1 - y1)) / (2.0 * n)
    if not used:
        return None
    d = sum_dw / sum_w
    spread = 1.95996 * math.sqrt(max(0.0, (d * sum_p + sum_q) / (sum_w * sum_w)))
    return d, max(-1.0, d - spread), min(1.0, d + spread), used


def _pooled_row(
    card: str,
    per_stand: Sequence[tuple[int, float, int, float, int, float]],
    *,
    min_exposed: int,
) -> CardOutcome:
    """One card over several stands: counts are n/N sums, the difference only stratified."""
    total = sum(n for n, *_ in per_stand)
    n_in = sum(row[2] for row in per_stand)
    wins_in = sum(row[3] for row in per_stand)
    wins_total = sum(row[1] for row in per_stand)
    strata = [(ni, wi, n - ni, w - wi) for n, w, ni, wi, _sn, _sw in per_stand]
    pooled = mantel_haenszel_difference(strata)
    n_not = total - n_in
    reasons = []
    if n_in < min_exposed:
        reasons.append(f"first-hand games {n_in} < {min_exposed}")
    if n_not < min_exposed:
        reasons.append(f"games without the card in the first hand {n_not} < {min_exposed}")
    if pooled is None:
        reasons.append("no deck state has games with and without the card in the first hand")
    return {
        "card": card,
        "status": "INSUFFICIENT_SAMPLE" if reasons else "MEASURED",
        "reason": "; ".join(reasons) or None,
        "games_total": total,
        "games_in_first_hand": n_in,
        "wins_in_first_hand": round(wins_in, 6),
        "games_not_in_first_hand": n_not,
        "wins_not_in_first_hand": round(wins_total - wins_in, 6),
        # rates of different stands are never added: they are given per stand only
        "rate_in": None,
        "rate_in_ci95": None,
        "rate_not": None,
        "rate_not_ci95": None,
        "difference_pp": None if pooled is None else _pp(pooled[0]),
        "difference_ci95_pp": None if pooled is None else [_pp(pooled[1]), _pp(pooled[2])],
        "secondary": {
            "games_seen_by_own_turn_3": sum(row[4] for row in per_stand),
            "wins_seen_by_own_turn_3": round(sum(row[5] for row in per_stand), 6),
            "note": "NOT randomised: effect draws and mulligan bottoms depend on play",
        },
        "strata": 0 if pooled is None else pooled[3],
    }


def _pod_set(table: CardOutcomeTable) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(tuple(pod["opponents"]) for pod in table["pods"]))


def _not_poolable(stands: Sequence[CardOutcomeTable]) -> str | None:
    """Why the stands of one deck may not be combined, or None when they may."""
    for label, values in (
        ("engine commit", [tuple(t["engine_commits"]) for t in stands]),
        ("bridge jar SHA-256", [tuple(t["bridge_jar_sha256s"]) for t in stands]),
        ("pilot version", [tuple(t["pilots"]) for t in stands]),
        ("decision policy", [tuple(t["decision_policies"]) for t in stands]),
    ):
        if any(len(v) > 1 for v in values) or len(set(values)) > 1:
            return f"the deck states differ in {label} (or mix it): not pooled"
    if len({_pod_set(stand) for stand in stands}) > 1:
        return "the deck states were played against different pod sets: not pooled"
    return None


def _stand_table(
    games: list[GameExposure],
    *,
    deck_id: str,
    deck_hash: str | None,
    min_exposed: int,
    allow_mixed: bool,
) -> CardOutcomeTable:
    table = aggregate(games, deck_id=deck_id, min_exposed=min_exposed, allow_mixed=allow_mixed)
    table["deck_hash"] = deck_hash
    revisions = (own_seat(game, deck_id) for game in games)
    table["revision_ids"] = _distinct(seat.get("revision_id") for seat in revisions if seat)
    return table


def stand_tables(
    exposures: Iterable[GameExposure],
    *,
    deck_id: str,
    min_exposed: int = DEFAULT_MIN_EXPOSED,
    allow_mixed: bool = False,
    games_skipped: int = 0,
    games_skipped_unreadable: int = 0,
    duplicate_logs_ignored: int = 0,
) -> CardOutcomeTable:
    """The card answer for one deck, counted per deck state (#1657).

    ``stands`` holds one :func:`aggregate` table per known ``deck_hash``; ``unknown_stand``
    holds the logs without a hash, with their own n/N, never added to a known stand. The top
    level counts the known stands only: one stand is shown as it is; several are combined only
    stratified (``strata`` = number of stands, rows from :func:`mantel_haenszel_difference`)
    and only when engine, bridge jar, pilot, decision policy and pod set agree; otherwise the
    top level carries no card rows (``NOT_POOLED``) and a reason. Mixed values inside one
    stand raise as in :func:`aggregate` unless allowed.
    """
    groups: dict[str | None, list[GameExposure]] = {}
    for game in exposures:
        seat = own_seat(game, deck_id)
        if seat is not None:
            groups.setdefault(stand_of(seat), []).append(game)
    known = sorted((key for key in groups if key is not None), key=lambda k: (-len(groups[k]), k))
    stands = [
        _stand_table(
            groups[key],
            deck_id=deck_id,
            deck_hash=key,
            min_exposed=min_exposed,
            allow_mixed=allow_mixed,
        )
        for key in known
    ]
    unknown = (
        _stand_table(
            groups[None],
            deck_id=deck_id,
            deck_hash=None,
            min_exposed=min_exposed,
            allow_mixed=allow_mixed,
        )
        if None in groups
        else None
    )
    if len(stands) == 1:
        top = cast(CardOutcomeTable, dict(stands[0]))
        pooling: Pooling = {"status": "SINGLE_STAND", "reason": None, "method": None}
    elif not stands:
        top = empty_table(deck_id, min_exposed=min_exposed)
        pooling = {
            "status": "NO_KNOWN_STAND",
            "reason": "no game names the deck state of this deck",
            "method": None,
        }
    else:
        top = _pooled_table(
            [groups[key] for key in known], stands, deck_id=deck_id, min_exposed=min_exposed
        )
        reason = _not_poolable(stands)
        pooling = {
            "status": "NOT_POOLED" if reason else "POOLED",
            "reason": reason,
            "method": None if reason else POOLING_METHOD,
        }
        if reason:
            top["status"] = "NOT_POOLED"
            top["cards"] = []
            top["comparisons"] = 0
            top["expected_chance_findings"] = 0.0
    top["deck_hash"] = stands[0]["deck_hash"] if len(stands) == 1 else None
    top["revision_ids"] = _distinct(r for stand in stands for r in stand.get("revision_ids", []))
    top["games_skipped"] = games_skipped
    top["games_skipped_unreadable"] = games_skipped_unreadable
    top["duplicate_logs_ignored"] = duplicate_logs_ignored
    top["strata"] = len(stands)
    top["pooling"] = pooling
    top["stands"] = stands
    top["unknown_stand"] = unknown
    warnings = list(top["warnings"])
    if duplicate_logs_ignored:
        warnings.append(
            f"{duplicate_logs_ignored} duplicate log(s) with an already counted game_id ignored"
        )
    if unknown is not None and unknown["games_total"]:
        warnings.append(
            f"{unknown['games_total']} game(s) without a deck state (Stand unbekannt) are "
            "shown apart and never added to a known deck state"
        )
    if pooling["reason"]:
        warnings.append(pooling["reason"])
    top["warnings"] = warnings
    return top


def _pooled_table(
    groups: Sequence[list[GameExposure]],
    stands: Sequence[CardOutcomeTable],
    *,
    deck_id: str,
    min_exposed: int,
) -> CardOutcomeTable:
    """The top level over several known stands: n/N sums and stratified card rows."""
    table = empty_table(deck_id, min_exposed=min_exposed)
    commanders = sorted({name for stand in stands for name in stand["commanders_excluded"]})
    counts = [_usable_counts(games, deck_id, set(commanders)) for games in groups]
    names = sorted({card for c in counts for card in (*c[2], *c[4])})
    rows = [
        _pooled_row(
            card,
            [(c[0], c[1], c[2][card], c[3][card], c[4][card], c[5][card]) for c in counts],
            min_exposed=min_exposed,
        )
        for card in names
    ]
    pods: Counter[tuple[str, ...]] = Counter()
    for stand in stands:
        for pod in stand["pods"]:
            pods[tuple(pod["opponents"])] += pod["games"]
    total = sum(stand["games_total"] for stand in stands)
    table["status"] = "OK" if total else "NO_GAMES"
    table["games_total"] = total
    table["seats_without_opening_hand"] = sum(t["seats_without_opening_hand"] for t in stands)
    table["draw_games"] = sum(t["draw_games"] for t in stands)
    table["mulligans_taken"] = sum(t["mulligans_taken"] for t in stands)
    table["multi_seat_games"] = sum(t["multi_seat_games"] for t in stands)
    table["engine_commits"] = _distinct(v for t in stands for v in t["engine_commits"])
    table["bridge_jar_sha256s"] = _distinct(v for t in stands for v in t["bridge_jar_sha256s"])
    table["bridge_qualification_states"] = _distinct(
        v for t in stands for v in t["bridge_qualification_states"]
    )
    table["pilots"] = _distinct(v for t in stands for v in t["pilots"])
    table["decision_policies"] = _distinct(v for t in stands for v in t["decision_policies"])
    table["covered_by_sealed_epoch"] = all(stand["covered_by_sealed_epoch"] for stand in stands)
    table["seeds"] = len({g["seed"] for games in groups for g in games if g["seed"] is not None})
    table["pods"] = [
        {"opponents": list(pod), "games": count}
        for pod, count in sorted(pods.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    table["commanders_excluded"] = commanders
    warnings: list[str] = []
    if total < math.ceil(min_exposed / EXPECTED_EXPOSURE):
        warnings.append(
            f"only {total} games: a typical card is in the first hand in about "
            f"{EXPECTED_EXPOSURE:.0%} of games, so few cards can reach {min_exposed} exposed games"
        )
    table["warnings"] = warnings
    table["cards"] = rows
    table["comparisons"] = sum(1 for row in rows if row["status"] == "MEASURED")
    table["expected_chance_findings"] = round(CHANCE_RATE * table["comparisons"], 1)
    return table


def ranked(table: CardOutcomeTable) -> Ranking:
    """MEASURED cards by the lower bound of the difference interval (best first), ties by name.

    Every other card is returned unranked with its reason; nothing is scored for it.
    """
    measured: list[CardOutcome] = []
    unranked: list[UnrankedCard] = []
    for row in table["cards"]:
        ci = row["difference_ci95_pp"]
        if row["status"] == "MEASURED" and ci is not None:
            measured.append(row)
        else:
            unranked.append({"card": row["card"], "status": row["status"], "reason": row["reason"]})
    measured.sort(key=lambda r: (-(r["difference_ci95_pp"] or [0.0])[0], r["card"]))
    return {"ranked": measured, "unranked": unranked}


def outcomes_for_folder(
    games_dir: str | Path,
    *,
    deck_id: str,
    min_exposed: int = DEFAULT_MIN_EXPOSED,
    allow_mixed: bool = False,
) -> CardOutcomeTable:
    """Read a games folder and build the answer of one deck, per deck state (``stand_tables``)."""
    report = load_exposures(games_dir)
    return stand_tables(
        report["exposures"],
        deck_id=deck_id,
        min_exposed=min_exposed,
        allow_mixed=allow_mixed,
        games_skipped=report["skipped_with_deck"].get(deck_id, 0),
        games_skipped_unreadable=report["skipped_unreadable"],
        duplicate_logs_ignored=report["duplicate_logs"],
    )


def deck_ids_in(report: LoadReport) -> list[str]:
    """Every deck id that sits in the folder's logs, at any seat, sorted.

    Finished games contribute the decks of all their seats; skipped (unfinished or
    failed) games contribute the deck ids of their headers, so a deck whose games all
    failed is still listed — with a ``NO_GAMES`` table, never silently absent (#1267).
    """
    ids = {seat["deck_id"] for game in report["exposures"] for seat in game["seats"]}
    return sorted(ids | set(report["skipped_with_deck"]))


def outcomes_for_all_decks(
    games_dir: str | Path,
    *,
    min_exposed: int = DEFAULT_MIN_EXPOSED,
    allow_mixed: bool = False,
) -> dict[str, CardOutcomeTable]:
    """The card table of every deck in the folder, keyed by deck id (#1267 point 1).

    Every seat of every game is data: the folder is read once and each deck that sits
    in the logs — the Owner's deck, the opponents, the precons — gets the same table a
    single-deck call would build, including the rule that a deck seated twice in one
    game counts once (its lowest seat, as in :func:`aggregate`).
    """
    report = load_exposures(games_dir)
    return {
        deck_id: stand_tables(
            report["exposures"],
            deck_id=deck_id,
            min_exposed=min_exposed,
            allow_mixed=allow_mixed,
            games_skipped=report["skipped_with_deck"].get(deck_id, 0),
            games_skipped_unreadable=report["skipped_unreadable"],
            duplicate_logs_ignored=report["duplicate_logs"],
        )
        for deck_id in deck_ids_in(report)
    }


def _fmt(value: float | None, scale: float = 1.0) -> str:
    return "-" if value is None else f"{value * scale:5.1f}"


def format_table(table: CardOutcomeTable, *, limit: int = 15) -> str:
    """Compact text view: header counts, top and bottom measured cards, unmeasured counts."""
    ranking = ranked(table)
    bridge_shas = ", ".join(s[:12] for s in table.get("bridge_jar_sha256s", [])) or "-"
    sealed = "yes" if table.get("covered_by_sealed_epoch") else "NO"
    lines = [
        f"{table['deck_id']}  [{table['data_class']}]  status {table['status']}",
        f"games {table['games_total']}  skipped {table['games_skipped']} "
        f"(+{table['games_skipped_unreadable']} unreadable)  draws {table['draw_games']}  "
        f"mulligans {table['mulligans_taken']}  seeds {table['seeds']}  "
        f"pods {len(table['pods'])}  min_exposed {table['min_exposed']}",
        f"engine {', '.join(c[:10] for c in table['engine_commits']) or '-'}  "
        f"bridge {bridge_shas}  sealed {sealed}  "
        f"pilots {', '.join(table['pilots']) or '-'}",
        f"measured {len(ranking['ranked'])}  unmeasured (INSUFFICIENT_SAMPLE) "
        f"{len(ranking['unranked'])}",
    ]
    if "strata" in table:
        unknown = table.get("unknown_stand")
        pooling = table.get("pooling")
        stand_line = (
            f"deck states {table['strata']} ({pooling['status'] if pooling else '-'})  "
            f"Stand unbekannt: "
            + (f"{unknown['games_total']} games, never added" if unknown else "none")
        )
        lines.append(stand_line)
        for stand in table.get("stands", []):
            lines.append(
                f"  state {str(stand.get('deck_hash'))[:12]}  games {stand['games_total']}  "
                f"revisions {', '.join(stand.get('revision_ids', [])) or '-'}"
            )
    lines.append(
        f"{table['comparisons']} cards compared at 95 %: about "
        f"{table['expected_chance_findings']} will look different from 0 by chance; treat the "
        "ends of the list as hypotheses to re-test, not as verdicts"
    )
    lines += [f"WARNING {w}" for w in table["warnings"]]
    rows = ranking["ranked"]
    shown = rows[:limit] + rows[limit:][-limit:]
    if shown:
        lines.append("card (diff pp [lower, upper], in/not games)")
    for row in shown:
        ci = row["difference_ci95_pp"] or [0.0, 0.0]
        lines.append(
            f"  {row['card'][:36]:36} {_fmt(row['difference_pp'])} "
            f"[{ci[0]:6.1f}, {ci[1]:6.1f}]  {row['games_in_first_hand']}/"
            f"{row['games_not_in_first_hand']}"
        )
    return "\n".join(lines)
