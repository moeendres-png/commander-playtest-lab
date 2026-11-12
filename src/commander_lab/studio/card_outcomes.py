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
"""

from __future__ import annotations

import gzip
import json
import math
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, TypedDict, cast

from .games import LOG_SCHEMA
from .simulations import wilson_score_interval

SCHEMA = "studio-card-outcomes-1"
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
CACHE_VERSION = 1
CHANCE_RATE = 0.05
_KIND = re.compile(r'\{\s*"kind"\s*:\s*"([a-z_]+)"')

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


class GameExposure(TypedDict):
    game_id: str
    seed: int | None
    engine_commit: str | None
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


class PodCount(TypedDict):
    opponents: list[str]
    games: int


class CardOutcomeTable(TypedDict):
    schema: str
    status: Literal["OK", "NO_GAMES"]
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
    pilots: list[str]
    decision_policies: list[str]
    seeds: int
    pods: list[PodCount]
    commanders_excluded: list[str]
    warnings: list[str]
    cards: list[CardOutcome]


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


def _seat_exposure(
    seat: int,
    deck_id: str,
    commanders: list[str],
    frames: Sequence[dict[str, object]],
    winners: Sequence[int],
) -> SeatExposure:
    first: list[str] | None = None
    taken = 0
    seen: set[str] = set()
    own_turns: set[int] = set()
    for frame in frames:
        turn = _int(frame.get("turn"))
        if _int(frame.get("active_seat")) == seat and turn is not None:
            own_turns.add(turn)
        hand = _hand_of(frame, seat)
        if _int(frame.get("seat")) == seat and frame.get("decision_class") == MULLIGAN_CLASS:
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


def _scan(
    path: Path, *, fast: bool
) -> tuple[dict[str, object] | None, dict[str, object] | None, list[dict[str, object]]]:
    """Header, last result record and the frames that can matter, from one line stream.

    ``fast`` skips ``json.loads`` for a frame line once every seat has passed its
    ``OWN_TURNS_SECONDARY``-th own turn and has its first hand, unless the line mentions a
    mulligan; a line whose kind cannot be told from its start is always parsed.
    """
    header: dict[str, object] | None = None
    result: dict[str, object] | None = None
    frames: list[dict[str, object]] = []
    own_turns: dict[int, set[int]] = {}
    has_first: set[int] = set()
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.endswith("\n"):
                break  # a running game: the last entry is still being written
            if fast and own_turns and "mulligan" not in line:
                match = _KIND.match(line)
                if (
                    match is not None
                    and match.group(1) == "frame"
                    and all(
                        len(turns) > OWN_TURNS_SECONDARY and seat in has_first
                        for seat, turns in own_turns.items()
                    )
                ):
                    continue
            entry = json.loads(line)
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
                deciding = _int(entry.get("seat"))
                if (
                    deciding in own_turns
                    and entry.get("decision_class") == MULLIGAN_CLASS
                    and _hand_of(entry, deciding)
                ):
                    has_first.add(deciding)
    return header, result, frames


def _read_log(path: Path, *, fast: bool = True) -> tuple[GameExposure | None, list[str]]:
    """The exposure of one log (or None) and the deck ids named in its header."""
    try:
        header, result, frames = _scan(path, fast=fast)
    except (OSError, EOFError, ValueError):
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
            _seat_exposure(seat, deck_id, _names(row.get("commanders")) or [], frames, winners)
        )
    game_id = _str(header.get("game_id")) or path.name.split(".jsonl", 1)[0]
    return {
        "game_id": game_id,
        "seed": _int(header.get("seed")),
        "engine_commit": _str(header.get("engine_commit")),
        "pilot": _str(header.get("pilot")),
        "decision_policy": _str(header.get("decision_policy")),
        "winner_seats": winners,
        "seats": seats,
    }, deck_ids


def _cache_file(path: Path) -> Path:
    return path.parent / CACHE_DIR / f"{path.name}.json"


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
        or not isinstance(exposure, dict)
        or not isinstance(exposure.get("game_id"), str)
        or not isinstance(exposure.get("seats"), list)
        or not isinstance(deck_ids, list)
    ):
        return None
    return cast(GameExposure, exposure), [d for d in deck_ids if isinstance(d, str)]


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
    temp = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        temp.unlink(missing_ok=True)  # a cache that cannot be written is only slower


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
    for key, path in sorted(paths.items()):
        exposure, deck_ids = _read(path)
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
    """The card table of one deck. Mixed engine commits or pilots raise unless allowed."""
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
    pilots = _distinct(g["pilot"] for g, _ in units)
    policies = _distinct(g["decision_policy"] for g, _ in units)
    warnings: list[str] = []
    for label, values in (
        ("engine commits", commits),
        ("pilot versions", pilots),
        ("decision policies", policies),
    ):
        if len(values) > 1:
            if not allow_mixed:
                raise ValueError(f"mixed {label} in one aggregate: {', '.join(values)}")
            warnings.append(f"mixed {label} pooled: {', '.join(values)}")
    if any(g["engine_commit"] is None for g, _ in units):
        warnings.append("some games carry no engine commit")
    commanders = sorted({name for _, s in units for name in s["commanders"]})
    commander_set = set(commanders)
    usable = [(g, s) for g, s in units if s["first_dealt_hand"] is not None]
    no_hand = len(units) - len(usable)
    total = len(usable)
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
    """Read a games folder and build the table of one deck (``NO_GAMES`` when it has none)."""
    report = load_exposures(games_dir)
    return aggregate(
        report["exposures"],
        deck_id=deck_id,
        min_exposed=min_exposed,
        allow_mixed=allow_mixed,
        games_skipped=report["skipped_with_deck"].get(deck_id, 0),
        games_skipped_unreadable=report["skipped_unreadable"],
        duplicate_logs_ignored=report["duplicate_logs"],
    )


def _fmt(value: float | None, scale: float = 1.0) -> str:
    return "-" if value is None else f"{value * scale:5.1f}"


def format_table(table: CardOutcomeTable, *, limit: int = 15) -> str:
    """Compact text view: header counts, top and bottom measured cards, unmeasured counts."""
    ranking = ranked(table)
    lines = [
        f"{table['deck_id']}  [{table['data_class']}]  status {table['status']}",
        f"games {table['games_total']}  skipped {table['games_skipped']} "
        f"(+{table['games_skipped_unreadable']} unreadable)  draws {table['draw_games']}  "
        f"mulligans {table['mulligans_taken']}  seeds {table['seeds']}  "
        f"pods {len(table['pods'])}  min_exposed {table['min_exposed']}",
        f"engine {', '.join(c[:10] for c in table['engine_commits']) or '-'}  "
        f"pilots {', '.join(table['pilots']) or '-'}",
        f"measured {len(ranking['ranked'])}  unmeasured (INSUFFICIENT_SAMPLE) "
        f"{len(ranking['unranked'])}",
    ]
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
