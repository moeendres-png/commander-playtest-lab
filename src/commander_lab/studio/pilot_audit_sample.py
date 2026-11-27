"""Sampling, blinding and scoring for the manual 240-decision pilot audit (#1524, G-SIM point 2).

This module never judges a decision. It only (1) draws a stratified, seeded sample of
rateable decisions from ``studio-pilot-audit-1`` recordings, (2) writes blinded annotation
sheets plus a separate key, and (3) scores the human annotations (two annotators, Owner as
reference for a calibration subset and every disputed item). All output is
``SIMULATED_RESULT``, weight 0, and is never an input to a tier list.

Order of work: ``plan`` (seed, tested deck, strata and quotas fixed BEFORE the series), run the
series, ``sample --plan``, annotate, ``score``. The binding minimums (24 games, 240 items, 120
tested-seat items, 40 calibration items) are hard floors that no option can lower.

Rateable rule (a documented PROXY for "at least two legal options with different play
consequence"; the engine does not label consequences): a ``decision`` entry is rateable when
ALL hold:

* ``decision_class`` is not ``mana_payment``;
* it has a ``response`` whose ``selected_option_ids`` are all among the legal option ids;
* after merging options with the same ``(option_type, normalised label)`` signature there are
  at least two distinct options (so duplicate pass entries or a single forced choice do not
  count);
* it is not forced: ``minimum_selections`` (default 1) is smaller than the number of
  distinct options.

Usage: ``python -m commander_lab.studio.pilot_audit_sample plan|sample|score ...``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .pilot_audit import AUDIT_SCHEMA, read_audit_entries, redact_engine_keys
from .store import now_utc

LABEL = "SIMULATED_RESULT"
WEIGHT = 0
KEY_SCHEMA = "studio-pilot-audit-sample-key-2"
PLAN_SCHEMA = "studio-pilot-audit-plan-1"
SCORE_SCHEMA = "studio-pilot-audit-score-1"
DEFAULT_SAMPLE_SIZE = 240
DEFAULT_CALIBRATION_SIZE = 40
DEFAULT_MIN_GAMES = 24
MIN_TESTED_ITEMS = 120
# Fixed strata (decision classes) and per-half quotas; the sum per half is size / 2.
DEFAULT_STRATA: dict[str, int] = {
    "priority": 48,
    "target": 18,
    "declare_attacker": 12,
    "declare_blocker": 12,
    "choose_object": 12,
    "mode": 6,
    "choice": 6,
    "choose_use": 6,
}
WILSON_Z = 1.959963984540054  # 95 % two-sided
MAX_CLEAR_ERROR_UPPER = 0.10
MAX_GAME_DECIDING_UPPER = 0.03
MAX_TESTED_SEAT_UPPER = 0.10
VERDICTS = ("ok", "questionable", "clear_error")
SEVERITIES = ("none", "minor", "major", "game_deciding")
SHEET_COLUMNS = (
    "item_id",
    "game_hash",
    "turn",
    "decision_kind",
    "prompt",
    "state_summary",
    "options",
    "chosen",
    "verdict",
    "severity",
    "note",
)
_MAX_NAMES = 40
_SEAT_NAME_RE = re.compile(r"\b(?:Full Game Seat|Seat) (\d+)\b")
_MANA = ("white", "blue", "black", "red", "green", "colorless")


class AuditSampleError(ValueError):
    """Fail-closed refusal with a human-readable message."""


@dataclass(frozen=True)
class Candidate:
    game_id: str
    seq: int
    seat: int
    tested: bool
    kind: str
    turn: int | None
    prompt: str
    state_summary: str
    option_labels: tuple[str, ...]
    chosen_labels: tuple[str, ...]
    source_sha256: str


# --------------------------------------------------------------------------- helpers


def wilson_upper(successes: int, total: int, z: float = WILSON_Z) -> float:
    """Upper bound of the Wilson score interval for ``successes`` out of ``total``."""
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("wilson_upper needs 0 <= successes <= total and total > 0")
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    centre = p + z2 / (2.0 * total)
    margin = z * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total))
    return min(1.0, (centre + margin) / denom)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_int(value: object) -> int | None:
    return value if type(value) is int else None


def _seq_of(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _clean_cell(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


def _option_label(option: Mapping[str, object], index: int) -> str:
    label = _text(option.get("label"))
    return label if label else f"option {index + 1}"


def _option_signature(option: Mapping[str, object], index: int) -> tuple[str, str]:
    return (_text(option.get("option_type")), _option_label(option, index).casefold())


def _scrub_seats(text: str, actor_seat: int) -> str:
    """Replace seat-revealing engine player names by ``You`` / ``Opponent N``."""

    def repl(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index == actor_seat:
            return "You"
        return f"Opponent {index + 1 if index < actor_seat else index}"

    return _SEAT_NAME_RE.sub(repl, text)


def _permanent_text(perm: Mapping[str, object]) -> str:
    """One battlefield permanent as the redacted state shows it (never more)."""
    if perm.get("face_down") is True:
        identity = _text(perm.get("private_identity"))
        name = (
            f"face-down permanent (known to you: {identity})" if identity else "face-down permanent"
        )
    else:
        name = _text(perm.get("name")) or "permanent"
    bits: list[str] = []
    if perm.get("tapped") is True:
        bits.append("tapped")
    power, toughness = _as_int(perm.get("power")), _as_int(perm.get("toughness"))
    if power is not None and toughness is not None:
        bits.append(f"{power}/{toughness}")
    damage = _as_int(perm.get("damage"))
    if damage:
        bits.append(f"damage {damage}")
    for counter in _seq_of(perm.get("counters")):
        if isinstance(counter, Mapping):
            ctype, count = _text(counter.get("type")), _as_int(counter.get("count"))
            if ctype and count:
                bits.append(f"{count}x {ctype}")
    return f"{name} ({', '.join(bits)})" if bits else name


def _card_names(zone: object) -> list[str]:
    out: list[str] = []
    for obj in _seq_of(zone):
        name = _text(obj.get("name")) if isinstance(obj, Mapping) else _text(obj)
        if isinstance(obj, Mapping) and obj.get("face_down") is True and not name:
            name = "face-down card"
        if name:
            out.append(name)
    return out[:_MAX_NAMES]


def _state_summary(pilot_state: Mapping[str, object]) -> str:
    """Render only what the redacted actor view carries: no ids, opponents anonymised."""
    labels: dict[str, str] = {}
    opp_n = 0
    players = [p for p in _seq_of(pilot_state.get("players")) if isinstance(p, Mapping)]
    actor_id = pilot_state.get("actor_id")
    for row in players:
        pid = _text(row.get("player_id"))
        if row.get("is_actor") is True or (actor_id is not None and pid == str(actor_id)):
            label = "You"
        else:
            opp_n += 1
            label = f"Opponent {opp_n}"
        if pid:
            labels[pid] = label
    parts: list[str] = []
    head: list[str] = []
    turn = _as_int(pilot_state.get("turn_number"))
    if turn is not None:
        head.append(f"turn {turn}")
    for field in ("phase", "step"):
        value = _text(pilot_state.get(field))
        if value:
            head.append(value)
    active = labels.get(_text(pilot_state.get("active_player_id")))
    if active:
        head.append(f"active: {active}")
    priority = labels.get(_text(pilot_state.get("priority_player_id")))
    if priority:
        head.append(f"priority: {priority}")
    if head:
        parts.append(", ".join(head))
    for row in players:
        label = labels.get(_text(row.get("player_id")), "Player")
        bits: list[str] = []
        life = _as_int(row.get("life"))
        if life is not None:
            bits.append(f"life {life}")
        poison = _as_int(row.get("poison_counters"))
        if poison:
            bits.append(f"poison {poison}")
        if "hand" in row:
            names = _card_names(row["hand"])
            bits.append(f"hand: {', '.join(names)}" if names else "hand empty")
        elif _as_int(row.get("hand_count")) is not None:
            bits.append(f"hand {_as_int(row.get('hand_count'))} cards")
        mana = row.get("mana_pool")
        if isinstance(mana, Mapping):
            pool = [f"{_as_int(mana.get(m))} {m}" for m in _MANA if _as_int(mana.get(m))]
            if pool:
                bits.append(f"mana pool {', '.join(pool)}")
        if _as_int(row.get("library_count")) is not None:
            bits.append(f"library {_as_int(row.get('library_count'))}")
        top = row.get("library_top_revealed")
        if isinstance(top, Mapping) and _text(top.get("name")):
            bits.append(f"library top revealed: {_text(top.get('name'))}")
        perms = [
            _permanent_text(x) for x in _seq_of(row.get("battlefield")) if isinstance(x, Mapping)
        ]
        if perms:
            bits.append(f"battlefield: {', '.join(perms[:_MAX_NAMES])}")
        for zone, count_key in (("graveyard", "graveyard_count"), ("exile", "exile_count")):
            names = _card_names(row.get(zone))
            count = _as_int(row.get(count_key))
            if names:
                bits.append(
                    f"{zone} ({count if count is not None else len(names)}): {', '.join(names)}"
                )
            elif count:
                bits.append(f"{zone} {count} cards")
        command = _card_names(row.get("command"))
        if command:
            bits.append(f"command: {', '.join(command)}")
        parts.append(f"{label} [{'; '.join(bits)}]" if bits else label)
    stack: list[str] = []
    for obj in _seq_of(pilot_state.get("stack")):
        if not isinstance(obj, Mapping):
            continue
        name = _text(obj.get("name"))
        if obj.get("face_down") is True and not name:
            name = "face-down spell"
        owner = labels.get(_text(obj.get("controller_id")))
        stack.append(f"{name or 'stack object'}" + (f" ({owner})" if owner else ""))
    parts.append("stack: " + (", ".join(stack) if stack else "empty"))
    return _clean_cell(" | ".join(parts))


def _analyse_decision(entry: Mapping[str, object]) -> tuple[list[str], list[str]] | None:
    """Return ``(option_labels, chosen_labels)`` for a rateable decision, else ``None``."""
    if entry.get("decision_class") == "mana_payment":
        return None
    response = entry.get("response")
    if not isinstance(response, Mapping):
        return None
    options = [o for o in _seq_of(entry.get("legal_options")) if isinstance(o, Mapping)]
    ids = [str(o["option_id"]) if o.get("option_id") is not None else "" for o in options]
    selected = [str(s) for s in _seq_of(response.get("selected_option_ids")) if s is not None]
    if not selected or any(s not in ids for s in selected):
        return None
    signatures = {_option_signature(o, i) for i, o in enumerate(options)}
    if len(signatures) < 2:
        return None
    minimum = _as_int(entry.get("minimum_selections"))
    if (minimum if minimum is not None else 1) >= len(signatures):
        return None
    labels = [_option_label(o, i) for i, o in enumerate(options)]
    chosen = [labels[ids.index(s)] for s in selected]
    return labels, chosen


def is_rateable(entry: Mapping[str, object]) -> bool:
    """Documented rateable rule (see module docstring)."""
    return entry.get("kind") == "decision" and _analyse_decision(entry) is not None


# --------------------------------------------------------------------------- loading


def _audit_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise AuditSampleError(f"audit folder not found: {folder}")
    files = sorted(
        p for p in folder.iterdir() if p.name.endswith((".audit.jsonl.gz", ".audit.jsonl"))
    )
    if not files:
        raise AuditSampleError(f"no *.audit.jsonl[.gz] files in {folder}")
    return files


def _tested_seat(header_body: Mapping[str, object], deck_id: str) -> int:
    matches = [
        _as_int(row.get("seat"))
        for row in _seq_of(header_body.get("seats"))
        if isinstance(row, Mapping) and row.get("deck_id") == deck_id
    ]
    seats = [m for m in matches if m is not None]
    if len(seats) != 1:
        raise AuditSampleError(f"tested deck_id {deck_id!r} must match exactly one seat per game")
    return seats[0]


# --------------------------------------------------------------------------- plan


def make_plan(
    *,
    seed: int,
    tested_deck_id: str,
    strata: Mapping[str, int] | None = None,
    size: int = DEFAULT_SAMPLE_SIZE,
    calibration: int = DEFAULT_CALIBRATION_SIZE,
    min_games: int = DEFAULT_MIN_GAMES,
    created_at: str | None = None,
) -> dict[str, object]:
    """Build the pre-series plan (seed, tested deck, strata and quotas). Floors are hard."""
    plan: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "label": LABEL,
        "seed": seed,
        "tested_deck_id": tested_deck_id,
        "sample_size": size,
        "calibration_size": calibration,
        "min_games": min_games,
        "strata_per_half": dict(strata if strata is not None else DEFAULT_STRATA),
        "created_at": created_at or now_utc(),
    }
    return validate_plan(plan)


def validate_plan(plan: Mapping[str, object]) -> dict[str, object]:
    """Fail closed unless the plan meets the binding minimums."""
    if plan.get("schema") != PLAN_SCHEMA:
        raise AuditSampleError(f"not a {PLAN_SCHEMA} plan")
    seed = plan.get("seed")
    deck = plan.get("tested_deck_id")
    size = plan.get("sample_size")
    cal = plan.get("calibration_size")
    games = plan.get("min_games")
    created = plan.get("created_at")
    strata_raw = plan.get("strata_per_half")
    if type(seed) is not int:
        raise AuditSampleError("plan needs an integer seed")
    if not isinstance(deck, str) or not deck.strip():
        raise AuditSampleError("plan needs tested_deck_id")
    if not isinstance(created, str) or not created:
        raise AuditSampleError("plan needs created_at")
    if type(size) is not int or size < DEFAULT_SAMPLE_SIZE or size % 2:
        raise AuditSampleError(f"sample_size must be an even integer >= {DEFAULT_SAMPLE_SIZE}")
    if type(cal) is not int or cal < DEFAULT_CALIBRATION_SIZE:
        raise AuditSampleError(f"calibration_size must be >= {DEFAULT_CALIBRATION_SIZE}")
    if type(games) is not int or games < DEFAULT_MIN_GAMES:
        raise AuditSampleError(f"min_games must be >= {DEFAULT_MIN_GAMES}")
    if not isinstance(strata_raw, Mapping) or not strata_raw:
        raise AuditSampleError("plan needs strata_per_half")
    strata: dict[str, int] = {}
    for kind, quota in strata_raw.items():
        if not isinstance(kind, str) or not kind or type(quota) is not int or quota < 1:
            raise AuditSampleError("strata_per_half needs class -> positive integer quota")
        strata[kind] = quota
    if sum(strata.values()) != size // 2:
        raise AuditSampleError(f"strata quotas must sum to {size // 2} per half")
    return {
        "schema": PLAN_SCHEMA,
        "label": LABEL,
        "seed": seed,
        "tested_deck_id": deck,
        "sample_size": size,
        "calibration_size": cal,
        "min_games": games,
        "strata_per_half": strata,
        "created_at": created,
    }


def load_candidates(
    folder: Path, plan: Mapping[str, object]
) -> tuple[list[Candidate], dict[str, object]]:
    """Read all audit files fail-closed; return rateable candidates and pool metadata."""
    plan = validate_plan(plan)
    deck_id = str(plan["tested_deck_id"])
    created_at = str(plan["created_at"])
    candidates: list[Candidate] = []
    fingerprints: set[str] = set()
    game_ids: set[str] = set()
    tested_seats: set[int] = set()
    for path in _audit_files(folder):
        digest = _sha256_file(path)
        header: Mapping[str, object] | None = None
        game_id = path.name.split(".audit.")[0]
        game_tested = -1
        for entry in read_audit_entries(path):
            kind = entry.get("kind")
            if kind == "header":
                if entry.get("schema") != AUDIT_SCHEMA:
                    raise AuditSampleError(f"{path.name}: unsupported schema")
                body = entry.get("header")
                if not isinstance(body, Mapping):
                    raise AuditSampleError(f"{path.name}: header body missing")
                if body.get("data_class") != LABEL:
                    raise AuditSampleError(f"{path.name}: data_class is not {LABEL}")
                if body.get("human_seats"):
                    raise AuditSampleError(f"{path.name}: human seats present")
                for row in _seq_of(body.get("seats")):
                    if isinstance(row, Mapping) and (
                        row.get("is_human") is True
                        or row.get("human") is True
                        or row.get("pilot") == "human"
                    ):
                        raise AuditSampleError(f"{path.name}: human seat present")
                fingerprint = _text(body.get("pilot_fingerprint"))
                if not fingerprint:
                    raise AuditSampleError(f"{path.name}: pilot_fingerprint missing")
                fingerprints.add(fingerprint)
                recorded = _text(entry.get("recorded_at"))
                if not recorded or recorded < created_at:
                    raise AuditSampleError(
                        f"{path.name}: recorded before the plan was created (or no recorded_at); "
                        "strata and seed must be fixed before the games"
                    )
                header = body
                game_id = _text(entry.get("game_id")) or game_id
                game_tested = _tested_seat(body, deck_id)
                tested_seats.add(game_tested)
                continue
            if header is None:
                raise AuditSampleError(f"{path.name}: entry before header")
            if kind != "decision":
                continue
            analysed = _analyse_decision(entry)
            seat = _as_int(entry.get("seat"))
            seq = _as_int(entry.get("seq"))
            if analysed is None or seat is None or seq is None:
                continue
            raw_state = redact_engine_keys(entry.get("pilot_state"))
            state = raw_state if isinstance(raw_state, Mapping) else {}
            decision_kind = _text(entry.get("decision_class")) or "unknown"

            def scrub(text: str, actor_seat: int = seat) -> str:
                return _clean_cell(_scrub_seats(text, actor_seat))

            candidates.append(
                Candidate(
                    game_id=game_id,
                    seq=seq,
                    seat=seat,
                    tested=seat == game_tested,
                    kind=decision_kind,
                    turn=_as_int(state.get("turn_number")),
                    prompt=scrub(_text(entry.get("prompt"))),
                    state_summary=scrub(_state_summary(state)),
                    option_labels=tuple(scrub(x) for x in analysed[0]),
                    chosen_labels=tuple(scrub(x) for x in analysed[1]),
                    source_sha256=digest,
                )
            )
        if header is None:
            raise AuditSampleError(f"{path.name}: no header entry")
        if game_id in game_ids:
            raise AuditSampleError(f"duplicate game_id {game_id!r}")
        game_ids.add(game_id)
    if len(fingerprints) != 1:
        raise AuditSampleError(
            f"mixed or missing pilot fingerprints ({len(fingerprints)} distinct); one is required"
        )
    if len(tested_seats) < 2:
        raise AuditSampleError("no seat rotation: tested deck always sits in the same seat")
    meta: dict[str, object] = {
        "pilot_fingerprint": next(iter(fingerprints)),
        "games_in_pool": len(game_ids),
        "rateable_in_pool": len(candidates),
        "tested_seats_seen": sorted(tested_seats),
    }
    return candidates, meta


# --------------------------------------------------------------------------- sampling


def _allocate(sizes: Mapping[str, int], total: int) -> dict[str, int]:
    """Proportional allocation (largest remainder, >=1 per non-empty stratum when possible)."""
    pool = sum(sizes.values())
    if pool < total:
        raise AuditSampleError(f"stratum pool {pool} smaller than requested {total}")
    kinds = sorted(k for k, v in sizes.items() if v > 0)
    alloc = {k: 0 for k in kinds}
    if total >= len(kinds):
        for k in kinds:
            alloc[k] = 1
    remaining = total - sum(alloc.values())
    exact = {k: remaining * sizes[k] / pool for k in kinds}
    for k in kinds:
        alloc[k] += min(int(exact[k]), sizes[k] - alloc[k])
    order = sorted(kinds, key=lambda k: (-(exact[k] - int(exact[k])), k))
    while sum(alloc.values()) < total:
        progressed = False
        for k in order:
            if sum(alloc.values()) >= total:
                break
            if alloc[k] < sizes[k]:
                alloc[k] += 1
                progressed = True
        if not progressed:
            break
    if sum(alloc.values()) != total:
        raise AuditSampleError("allocation failed")
    return alloc


def _draw(items: Sequence[Candidate], count: int, rng: random.Random) -> list[Candidate]:
    """Seeded draw that round-robins across games to spread the sample."""
    by_game: dict[str, list[Candidate]] = {}
    for item in sorted(items, key=lambda c: (c.game_id, c.seq)):
        by_game.setdefault(item.game_id, []).append(item)
    for lst in by_game.values():
        rng.shuffle(lst)
    order = sorted(by_game)
    rng.shuffle(order)
    picked: list[Candidate] = []
    while len(picked) < count:
        for gid in order:
            if by_game[gid] and len(picked) < count:
                picked.append(by_game[gid].pop())
    return picked


def _half_allocation(
    quotas: Mapping[str, int], available: Mapping[str, int], name: str
) -> tuple[dict[str, int], dict[str, object]]:
    """Planned quota per class; a shortfall moves proportionally to classes with spare items."""
    alloc = {k: min(q, available.get(k, 0)) for k, q in quotas.items()}
    shortfall = sum(quotas.values()) - sum(alloc.values())
    report: dict[str, object] = {"planned": dict(quotas), "shortfall_redistributed": shortfall}
    if shortfall:
        spare = {
            k: available.get(k, 0) - alloc[k] for k in quotas if available.get(k, 0) > alloc[k]
        }
        if sum(spare.values()) < shortfall:
            raise AuditSampleError(
                f"{name}: planned classes offer only {sum(alloc.values()) + sum(spare.values())} "
                f"rateable decisions, {sum(quotas.values())} needed"
            )
        for kind, extra in _allocate(spare, shortfall).items():
            alloc[kind] += extra
    report["drawn"] = dict(alloc)
    return alloc, report


def build_sample(
    candidates: Sequence[Candidate], plan: Mapping[str, object]
) -> tuple[list[Candidate], list[bool], dict[str, object]]:
    """Draw the stratified sample; returns items (shuffled), calibration flags and the report."""
    plan = validate_plan(plan)
    seed = int(str(plan["seed"]))
    size = int(str(plan["sample_size"]))
    calibration = int(str(plan["calibration_size"]))
    min_games = int(str(plan["min_games"]))
    strata_raw = plan["strata_per_half"]
    if not isinstance(strata_raw, Mapping):
        raise AuditSampleError("plan strata missing")
    strata = {str(k): int(v) for k, v in strata_raw.items()}
    pool_all = [c for c in candidates if c.kind in strata]
    games = {c.game_id for c in pool_all}
    if len(games) < min_games:
        raise AuditSampleError(f"only {len(games)} games, at least {min_games} required")
    if len(pool_all) < size:
        raise AuditSampleError(f"only {len(pool_all)} rateable decisions, {size} required")
    half = size // 2
    report: dict[str, object] = {
        "excluded_classes_not_in_plan": sorted({c.kind for c in candidates} - set(strata))
    }
    chosen: list[Candidate] = []
    for tested in (True, False):
        pool = [c for c in pool_all if c.tested is tested]
        name = "tested_seat" if tested else "other_seats"
        if len(pool) < half:
            raise AuditSampleError(f"only {len(pool)} rateable decisions in {name}, {half} needed")
        avail: dict[str, int] = {}
        for c in pool:
            avail[c.kind] = avail.get(c.kind, 0) + 1
        alloc, half_report = _half_allocation(strata, avail, name)
        report[name] = half_report
        for kind in sorted(alloc):
            rng = random.Random(f"{seed}:{name}:{kind}")
            chosen.extend(_draw([c for c in pool if c.kind == kind], alloc[kind], rng))
    sampled_games = {c.game_id for c in chosen}
    if len(sampled_games) < min_games:
        raise AuditSampleError(
            f"sample covers only {len(sampled_games)} games, at least {min_games} required"
        )
    rng = random.Random(f"{seed}:order")
    chosen.sort(key=lambda c: (c.game_id, c.seq))
    rng.shuffle(chosen)
    flags = [False] * len(chosen)
    cal_rng = random.Random(f"{seed}:calibration")
    tested_idx = [i for i, c in enumerate(chosen) if c.tested]
    other_idx = [i for i, c in enumerate(chosen) if not c.tested]
    cal_rng.shuffle(tested_idx)
    cal_rng.shuffle(other_idx)
    take_t = calibration // 2
    take_o = calibration - take_t
    for i in tested_idx[:take_t] + other_idx[:take_o]:
        flags[i] = True
    report["games_sampled"] = len(sampled_games)
    return chosen, flags, report


def _game_hash(seed: int, game_id: str) -> str:
    return hashlib.sha256(f"{seed}:{game_id}".encode()).hexdigest()[:10]


def _item_id(index: int) -> str:
    return f"I{index + 1:03d}"


def _write_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SHEET_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def write_sample(
    candidates: Sequence[Candidate],
    meta: Mapping[str, object],
    out_dir: Path,
    plan: Mapping[str, object],
) -> dict[str, Path]:
    """Write sheets A/B, the owner calibration sheet and the key into ``out_dir``."""
    plan = validate_plan(plan)
    seed = int(str(plan["seed"]))
    for parent in (out_dir.resolve(), *out_dir.resolve().parents):
        if (parent / ".git").exists():
            raise AuditSampleError(f"output folder {out_dir} is inside a git checkout; refused")
    items, flags, report = build_sample(candidates, plan)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    key_items: list[dict[str, object]] = []
    for idx, (item, is_cal) in enumerate(zip(items, flags, strict=True)):
        iid = _item_id(idx)
        rows.append(
            {
                "item_id": iid,
                "game_hash": _game_hash(seed, item.game_id),
                "turn": "" if item.turn is None else str(item.turn),
                "decision_kind": item.kind,
                "prompt": item.prompt,
                "state_summary": item.state_summary,
                "options": " || ".join(
                    f"{chr(65 + i) if i < 26 else i + 1}) {lab}"
                    for i, lab in enumerate(item.option_labels)
                ),
                "chosen": " || ".join(item.chosen_labels),
                "verdict": "",
                "severity": "",
                "note": "",
            }
        )
        key_items.append(
            {
                "item_id": iid,
                "game_id": item.game_id,
                "seat": item.seat,
                "frame_index": item.seq,
                "tested_seat": item.tested,
                "decision_kind": item.kind,
                "calibration": is_cal,
                "source_sha256": item.source_sha256,
            }
        )
    paths: dict[str, Path] = {}
    for annotator in ("A", "B"):
        path = out_dir / f"annotation_sheet_{annotator}.csv"
        _write_csv(path, rows)
        paths[f"sheet_{annotator}"] = path
    owner_path = out_dir / "owner_calibration_sheet.csv"
    _write_csv(owner_path, [r for r, c in zip(rows, flags, strict=True) if c])
    paths["owner_calibration_sheet"] = owner_path
    key = {
        "schema": KEY_SCHEMA,
        "label": LABEL,
        "weight": WEIGHT,
        "tier_list": False,
        "seed": seed,
        "plan": plan,
        "pilot_fingerprint": meta["pilot_fingerprint"],
        "games_in_pool": meta["games_in_pool"],
        "rateable_in_pool": meta["rateable_in_pool"],
        "sample_size": len(items),
        "tested_seat_items": sum(1 for it in items if it.tested),
        "calibration_size": sum(flags),
        "games_sampled": report["games_sampled"],
        "strata_report": report,
        "items": key_items,
    }
    key_path = out_dir / "sample_key.json"
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["key"] = key_path
    return paths


# --------------------------------------------------------------------------- scoring


@dataclass(frozen=True)
class Annotation:
    verdict: str
    severity: str


def _parse_annotation(row: Mapping[str, str]) -> Annotation | str | None:
    """Return an Annotation, ``None`` when blank, or an error string when invalid."""
    verdict = (row.get("verdict") or "").strip().lower()
    severity = (row.get("severity") or "").strip().lower()
    if not verdict and not severity:
        return None
    if verdict not in VERDICTS:
        return f"invalid verdict {verdict!r}"
    if verdict == "clear_error":
        if severity not in ("minor", "major", "game_deciding"):
            return "clear_error needs severity minor/major/game_deciding"
        return Annotation(verdict, severity)
    if severity not in ("", "none"):
        return f"verdict {verdict} must have severity none"
    return Annotation(verdict, "none")


def read_sheet(path: Path, expected_ids: set[str]) -> tuple[dict[str, Annotation], list[str]]:
    """Read one annotation sheet; returns annotations and problems (invalid/unknown/duplicate)."""
    annotations: dict[str, Annotation] = {}
    problems: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            iid = (row.get("item_id") or "").strip()
            if iid not in expected_ids:
                problems.append(f"{path.name}: unknown item {iid!r}")
                continue
            if iid in seen:
                problems.append(f"{path.name}: duplicate row for {iid}")
                annotations.pop(iid, None)
                continue
            seen.add(iid)
            parsed = _parse_annotation(row)
            if isinstance(parsed, str):
                problems.append(f"{path.name}: {iid}: {parsed}")
            elif parsed is not None:
                annotations[iid] = parsed
    return annotations, problems


def cohens_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Cohen's kappa on verdict pairs; ``None`` without pairs."""
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(1 for a, b in pairs if a == b) / n
    expected = sum(
        (sum(1 for a, _ in pairs if a == v) / n) * (sum(1 for _, b in pairs if b == v) / n)
        for v in VERDICTS
    )
    if expected >= 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def _bound(count: int, total: int, limit: float) -> dict[str, object]:
    if total <= 0:
        return {"n": count, "N": total, "upper95": None, "limit": limit, "ok": False}
    upper = wilson_upper(count, total)
    return {
        "n": count,
        "N": total,
        "upper95": round(upper, 4),
        "limit": limit,
        "ok": upper <= limit,
    }


def key_problems(key: Mapping[str, object]) -> list[str]:
    """Re-check the key against the binding minimums; every hit forces UNKNOWN."""
    problems: list[str] = []
    if key.get("label") != LABEL:
        problems.append(f"key label is not {LABEL}")
    if key.get("tier_list") is not False:
        problems.append("key tier_list is not false")
    if key.get("weight") != WEIGHT:
        problems.append("key weight is not 0")
    if type(key.get("seed")) is not int:
        problems.append("key has no integer seed")
    plan = key.get("plan")
    try:
        validated = validate_plan(plan) if isinstance(plan, Mapping) else None
    except AuditSampleError as exc:
        problems.append(f"key plan invalid: {exc}")
        validated = None
    if validated is None:
        problems.append("key has no valid plan")
    elif validated["seed"] != key.get("seed"):
        problems.append("key seed differs from plan seed")
    items = [i for i in _seq_of(key.get("items")) if isinstance(i, Mapping)]
    ids = [str(i.get("item_id")) for i in items]
    if len(set(ids)) != len(ids):
        problems.append("duplicate item ids in key")
    games = {str(i.get("game_id")) for i in items}
    tested = sum(1 for i in items if i.get("tested_seat") is True)
    cal = sum(1 for i in items if i.get("calibration") is True)
    if len(items) < DEFAULT_SAMPLE_SIZE:
        problems.append(f"only {len(items)} items, {DEFAULT_SAMPLE_SIZE} required")
    if tested < MIN_TESTED_ITEMS:
        problems.append(f"only {tested} tested-seat items, {MIN_TESTED_ITEMS} required")
    if len(games) < DEFAULT_MIN_GAMES:
        problems.append(f"only {len(games)} games, {DEFAULT_MIN_GAMES} required")
    if cal < DEFAULT_CALIBRATION_SIZE:
        problems.append(f"only {cal} calibration items, {DEFAULT_CALIBRATION_SIZE} required")
    if validated is not None and cal < int(str(validated["calibration_size"])):
        problems.append("calibration items fewer than planned")
    return problems


def score(
    key: Mapping[str, object],
    sheet_a: Mapping[str, Annotation],
    sheet_b: Mapping[str, Annotation],
    sheet_owner: Mapping[str, Annotation] | None,
    problems: Sequence[str] = (),
) -> dict[str, object]:
    """Combine annotations into the audit result. Never PASS with any unresolved item."""
    all_problems = [*problems, *key_problems(key)]
    items = [i for i in _seq_of(key.get("items")) if isinstance(i, Mapping)]
    owner = sheet_owner or {}
    final: dict[str, Annotation] = {}
    disputed: list[str] = []
    missing: list[str] = []
    cal_missing_owner: list[str] = []
    pairs: list[tuple[str, str]] = []
    cal_a_owner: list[tuple[str, str]] = []
    cal_b_owner: list[tuple[str, str]] = []
    for item in items:
        iid = str(item["item_id"])
        a, b = sheet_a.get(iid), sheet_b.get(iid)
        if a is not None and b is not None:
            pairs.append((a.verdict, b.verdict))
        if item.get("calibration") is True:
            if iid not in owner:
                cal_missing_owner.append(iid)
            else:
                if a is not None:
                    cal_a_owner.append((a.verdict, owner[iid].verdict))
                if b is not None:
                    cal_b_owner.append((b.verdict, owner[iid].verdict))
        if iid in owner:
            final[iid] = owner[iid]
        elif a is None or b is None:
            missing.append(iid)
        elif a == b:
            final[iid] = a
        else:
            disputed.append(iid)
    n_items = len(items)
    tested_ids = {str(i["item_id"]) for i in items if i.get("tested_seat") is True}
    clear = [i for i, ann in final.items() if ann.verdict == "clear_error"]
    deciding = [i for i in clear if final[i].severity == "game_deciding"]
    tested_clear = [i for i in clear if i in tested_ids]
    bounds = {
        "clear_errors": _bound(len(clear), n_items, MAX_CLEAR_ERROR_UPPER),
        "game_deciding_errors": _bound(len(deciding), n_items, MAX_GAME_DECIDING_UPPER),
        "tested_seat_clear_errors": _bound(
            len(tested_clear), len(tested_ids), MAX_TESTED_SEAT_UPPER
        ),
    }
    unresolved = bool(disputed or missing or cal_missing_owner or all_problems)
    all_ok = all(bool(b["ok"]) for b in bounds.values())
    result = "UNKNOWN" if unresolved else ("PASS" if all_ok else "FAIL")
    return {
        "schema": SCORE_SCHEMA,
        "label": LABEL,
        "weight": WEIGHT,
        "tier_list": False,
        "result": result,
        "scope": "sample part only (b); frozen gold cases (c) are judged separately",
        "valid_for_pilot_fingerprint": key.get("pilot_fingerprint"),
        "seed": key.get("seed"),
        "items": n_items,
        "kappa_verdict_AB": cohens_kappa(pairs),
        "kappa_calibration_A_owner": cohens_kappa(cal_a_owner),
        "kappa_calibration_B_owner": cohens_kappa(cal_b_owner),
        "paired_items": len(pairs),
        "bounds": bounds,
        "disputed_for_owner": sorted(disputed),
        "missing_annotation": sorted(missing),
        "calibration_missing_owner": sorted(cal_missing_owner),
        "problems": all_problems,
    }


def _text_report(result: Mapping[str, object]) -> str:
    bounds = result["bounds"]
    lines = [
        f"{LABEL} (weight 0, never a tier list): pilot audit sample result = {result['result']}",
        f"Valid only for pilot fingerprint {result['valid_for_pilot_fingerprint']}.",
    ]
    if isinstance(bounds, Mapping):
        for name, b in bounds.items():
            if isinstance(b, Mapping):
                lines.append(
                    f"{name}: {b['n']}/{b['N']}, Wilson 95% upper {b['upper95']} "
                    f"(limit {b['limit']}) {'ok' if b['ok'] else 'EXCEEDED'}"
                )
    lines.append(
        f"kappa verdict A-B {result['kappa_verdict_AB']}; calibration A-owner "
        f"{result['kappa_calibration_A_owner']}, B-owner {result['kappa_calibration_B_owner']}"
    )
    for field in ("disputed_for_owner", "missing_annotation", "calibration_missing_owner"):
        value = result[field]
        count = len(value) if isinstance(value, list) else 0
        lines.append(f"{field}: {count}")
    if result["problems"]:
        lines.append(f"problems: {len(_seq_of(result['problems']))} (see JSON)")
    if result["result"] == "UNKNOWN":
        lines.append("UNKNOWN: unresolved items remain; this is never a pass.")
    return "\n".join(lines) + "\n"


def write_owner_template(
    key_sheet_rows: Mapping[str, Mapping[str, str]], ids: Sequence[str], path: Path
) -> None:
    """Blank owner rows (no A/B verdicts) for the given item ids."""
    _write_csv(path, [key_sheet_rows[i] for i in sorted(ids) if i in key_sheet_rows])


# --------------------------------------------------------------------------- CLI


def _cmd_plan(args: argparse.Namespace) -> int:
    strata: dict[str, int] | None = None
    if args.strata:
        strata = {}
        for part in args.strata.split(","):
            kind, _, quota = part.partition("=")
            if not quota.isdigit():
                raise AuditSampleError(f"bad --strata entry {part!r}; use class=quota")
            strata[kind.strip()] = int(quota)
    plan = make_plan(
        seed=args.seed,
        tested_deck_id=args.tested_deck_id,
        strata=strata,
        size=args.size,
        calibration=args.calibration,
        min_games=args.min_games,
    )
    out = Path(args.out)
    if out.exists():
        raise AuditSampleError(f"{out} exists; a plan is written once, before the series")
    out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"plan: {out}  ({LABEL}; run the series only after this file exists)")
    return 0


def _load_plan(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AuditSampleError(f"{path.name}: not a plan file")
    return validate_plan(data)


def _cmd_sample(args: argparse.Namespace) -> int:
    plan = _load_plan(Path(args.plan))
    candidates, meta = load_candidates(Path(args.audit_dir), plan)
    paths = write_sample(candidates, meta, Path(args.out_dir), plan)
    for name, path in sorted(paths.items()):
        print(f"{name}: {path}")
    print(f"{LABEL}: keep the key file away from annotators; never commit these files.")
    return 0


def _load_json_mapping(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != KEY_SCHEMA:
        raise AuditSampleError(f"{path.name}: not a {KEY_SCHEMA} key file")
    return data


def _cmd_score(args: argparse.Namespace) -> int:
    key = _load_json_mapping(Path(args.key))
    expected = {str(i["item_id"]) for i in _seq_of(key.get("items")) if isinstance(i, Mapping)}
    problems: list[str] = []
    a, pa = read_sheet(Path(args.sheet_a), expected)
    b, pb = read_sheet(Path(args.sheet_b), expected)
    problems += pa + pb
    owner: dict[str, Annotation] | None = None
    if args.sheet_owner:
        owner, po = read_sheet(Path(args.sheet_owner), expected)
        problems += po
    result = score(key, a, b, owner, problems)
    if args.owner_template:
        with Path(args.sheet_a).open(encoding="utf-8", newline="") as handle:
            rows = {
                str(r["item_id"]).strip(): {
                    **{c: r.get(c, "") for c in SHEET_COLUMNS},
                    "verdict": "",
                    "severity": "",
                    "note": "",
                }
                for r in csv.DictReader(handle)
            }
        need = [
            *_str_list(result["disputed_for_owner"]),
            *_str_list(result["calibration_missing_owner"]),
        ]
        write_owner_template(rows, sorted(set(need)), Path(args.owner_template))
    text = _text_report(result)
    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    sys.stdout.write(text)
    return {"PASS": 0, "FAIL": 1}.get(str(result["result"]), 2)


def _str_list(value: object) -> list[str]:
    return [str(x) for x in _seq_of(value)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilot_audit_sample", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pl = sub.add_parser("plan", help="fix seed, tested deck and strata BEFORE the series")
    pl.add_argument("--out", required=True)
    pl.add_argument("--seed", type=int, required=True)
    pl.add_argument("--tested-deck-id", required=True)
    pl.add_argument("--strata", default=None, help="class=quota per half, comma separated")
    pl.add_argument("--size", type=int, default=DEFAULT_SAMPLE_SIZE)
    pl.add_argument("--calibration", type=int, default=DEFAULT_CALIBRATION_SIZE)
    pl.add_argument("--min-games", type=int, default=DEFAULT_MIN_GAMES)
    pl.set_defaults(func=_cmd_plan)
    s = sub.add_parser("sample", help="draw the blinded sample")
    s.add_argument("--audit-dir", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--plan", required=True)
    s.set_defaults(func=_cmd_sample)
    c = sub.add_parser("score", help="score the annotation sheets")
    c.add_argument("--key", required=True)
    c.add_argument("--sheet-a", required=True)
    c.add_argument("--sheet-b", required=True)
    c.add_argument("--sheet-owner", default=None)
    c.add_argument("--owner-template", default=None, help="write blank owner rows still needed")
    c.add_argument("--out-json", default=None)
    c.set_defaults(func=_cmd_score)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except AuditSampleError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
