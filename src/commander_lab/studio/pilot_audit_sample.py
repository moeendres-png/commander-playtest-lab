"""Sampling, blinding and scoring for the manual 240-decision pilot audit (#1524, G-SIM point 2).

This module never judges a decision. It only (1) draws a stratified, seeded sample of
rateable decisions from ``studio-pilot-audit-1`` recordings, (2) writes blinded annotation
sheets plus a separate key, and (3) scores the human annotations (two annotators, Owner as
reference for a calibration subset and every disputed item). All output is
``SIMULATED_RESULT``, weight 0, and is never an input to a tier list.

Rateable rule (exact): a ``decision`` entry is rateable when ALL hold:

* ``decision_class`` is not ``mana_payment``;
* it has a ``response`` whose ``selected_option_ids`` are all among the legal option ids;
* after merging options with the same ``(option_type, normalised label)`` signature there are
  at least two distinct options (so duplicate pass entries or a single forced choice do not
  count);
* it is not forced: ``minimum_selections`` (default 1) is smaller than the number of
  distinct options.

Usage: ``python -m commander_lab.studio.pilot_audit_sample sample|score ...``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .pilot_audit import AUDIT_SCHEMA, read_audit_entries, redact_engine_keys

LABEL = "SIMULATED_RESULT"
WEIGHT = 0
KEY_SCHEMA = "studio-pilot-audit-sample-key-1"
SCORE_SCHEMA = "studio-pilot-audit-score-1"
DEFAULT_SAMPLE_SIZE = 240
DEFAULT_CALIBRATION_SIZE = 40
DEFAULT_MIN_GAMES = 24
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
_ZONES = ("hand", "battlefield", "graveyard", "command", "exile")
_MAX_NAMES = 40
_NOTE_MAX = 500


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


def _names(zone: object) -> list[str]:
    out: list[str] = []
    for obj in _seq_of(zone):
        name = _text(obj.get("name")) if isinstance(obj, Mapping) else _text(obj)
        if name:
            out.append(name)
    return out[:_MAX_NAMES]


def _state_summary(pilot_state: Mapping[str, object]) -> str:
    """Render only what the deciding seat sees: no deck names, no ids, opponents anonymised."""
    parts: list[str] = []
    turn = _as_int(pilot_state.get("turn_number"))
    phase = _text(pilot_state.get("phase")) or _text(pilot_state.get("step"))
    head = []
    if turn is not None:
        head.append(f"turn {turn}")
    if phase:
        head.append(phase)
    if head:
        parts.append(", ".join(head))
    actor_id = pilot_state.get("actor_id")
    opp_n = 0
    for row in _seq_of(pilot_state.get("players")):
        if not isinstance(row, Mapping):
            continue
        is_actor = row.get("is_actor") is True or (
            actor_id is not None and row.get("player_id") == actor_id
        )
        if is_actor:
            who = "You"
        else:
            opp_n += 1
            who = f"Opponent {opp_n}"
        bits: list[str] = []
        life = _as_int(row.get("life"))
        if life is not None:
            bits.append(f"life {life}")
        for zone in _ZONES:
            if zone not in row:
                continue
            names = _names(row[zone])
            if zone == "hand" and not is_actor:
                count = len(_seq_of(row[zone]))
                bits.append(f"hand {count} cards")
            elif names:
                bits.append(f"{zone}: {', '.join(names)}")
        parts.append(f"{who} [{'; '.join(bits)}]" if bits else who)
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


def _tested_seat(header_body: Mapping[str, object], *, deck_id: str | None, fixed: int) -> int:
    if deck_id is None:
        return fixed
    matches = [
        _as_int(row.get("seat"))
        for row in _seq_of(header_body.get("seats"))
        if isinstance(row, Mapping) and row.get("deck_id") == deck_id
    ]
    seats = [m for m in matches if m is not None]
    if len(seats) != 1:
        raise AuditSampleError(f"tested deck_id {deck_id!r} must match exactly one seat per game")
    return seats[0]


def load_candidates(
    folder: Path, *, tested_seat: int = 0, tested_deck_id: str | None = None
) -> tuple[list[Candidate], dict[str, object]]:
    """Read all audit files fail-closed; return rateable candidates and pool metadata."""
    candidates: list[Candidate] = []
    fingerprints: set[str] = set()
    game_ids: set[str] = set()
    tested_seats: set[int] = set()
    for path in _audit_files(folder):
        digest = _sha256_file(path)
        header: Mapping[str, object] | None = None
        game_id = path.name.split(".audit.")[0]
        game_tested = tested_seat
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
                humans = body.get("human_seats")
                if humans:
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
                header = body
                game_id = _text(entry.get("game_id")) or game_id
                game_tested = _tested_seat(body, deck_id=tested_deck_id, fixed=tested_seat)
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
            candidates.append(
                Candidate(
                    game_id=game_id,
                    seq=seq,
                    seat=seat,
                    tested=seat == game_tested,
                    kind=decision_kind,
                    turn=_as_int(state.get("turn_number")),
                    prompt=_clean_cell(_text(entry.get("prompt"))),
                    state_summary=_state_summary(state),
                    option_labels=tuple(_clean_cell(x) for x in analysed[0]),
                    chosen_labels=tuple(_clean_cell(x) for x in analysed[1]),
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
    if tested_deck_id is not None and len(tested_seats) < 2:
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


def build_sample(
    candidates: Sequence[Candidate],
    *,
    seed: int,
    size: int = DEFAULT_SAMPLE_SIZE,
    calibration: int = DEFAULT_CALIBRATION_SIZE,
    min_games: int = DEFAULT_MIN_GAMES,
) -> tuple[list[Candidate], list[bool], dict[str, object]]:
    """Draw the stratified sample; returns items (shuffled), calibration flags and the plan."""
    games = {c.game_id for c in candidates}
    if len(games) < min_games:
        raise AuditSampleError(f"only {len(games)} games, at least {min_games} required")
    if len(candidates) < size:
        raise AuditSampleError(f"only {len(candidates)} rateable decisions, {size} required")
    half = size // 2
    plan: dict[str, object] = {}
    chosen: list[Candidate] = []
    for tested, quota in ((True, half), (False, size - half)):
        pool = [c for c in candidates if c.tested is tested]
        name = "tested_seat" if tested else "other_seats"
        if len(pool) < quota:
            raise AuditSampleError(f"only {len(pool)} rateable decisions in {name}, {quota} needed")
        sizes: dict[str, int] = {}
        for c in pool:
            sizes[c.kind] = sizes.get(c.kind, 0) + 1
        alloc = _allocate(sizes, quota)
        plan[name] = alloc
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
    if calibration > 0:
        if calibration > len(chosen):
            raise AuditSampleError("calibration subset larger than sample")
        cal_rng = random.Random(f"{seed}:calibration")
        tested_idx = [i for i, c in enumerate(chosen) if c.tested]
        other_idx = [i for i, c in enumerate(chosen) if not c.tested]
        cal_rng.shuffle(tested_idx)
        cal_rng.shuffle(other_idx)
        take_t = min(calibration // 2, len(tested_idx))
        take_o = min(calibration - take_t, len(other_idx))
        for i in tested_idx[:take_t] + other_idx[:take_o]:
            flags[i] = True
    plan["games_sampled"] = len(sampled_games)
    return chosen, flags, plan


def _game_hash(seed: int, game_id: str) -> str:
    return hashlib.sha256(f"{seed}:{game_id}".encode()).hexdigest()[:10]


def _item_id(index: int) -> str:
    return f"I{index + 1:03d}"


def write_sample(
    candidates: Sequence[Candidate],
    meta: Mapping[str, object],
    out_dir: Path,
    *,
    seed: int,
    size: int = DEFAULT_SAMPLE_SIZE,
    calibration: int = DEFAULT_CALIBRATION_SIZE,
    min_games: int = DEFAULT_MIN_GAMES,
) -> dict[str, Path]:
    """Write sheets A/B and the key file into ``out_dir`` (must be outside any git checkout)."""
    for parent in (out_dir.resolve(), *out_dir.resolve().parents):
        if (parent / ".git").exists():
            raise AuditSampleError(f"output folder {out_dir} is inside a git checkout; refused")
    items, flags, plan = build_sample(
        candidates, seed=seed, size=size, calibration=calibration, min_games=min_games
    )
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
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(SHEET_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
        paths[f"sheet_{annotator}"] = path
    key = {
        "schema": KEY_SCHEMA,
        "label": LABEL,
        "weight": WEIGHT,
        "tier_list": False,
        "seed": seed,
        "pilot_fingerprint": meta["pilot_fingerprint"],
        "games_in_pool": meta["games_in_pool"],
        "rateable_in_pool": meta["rateable_in_pool"],
        "sample_size": len(items),
        "tested_seat_items": sum(1 for it in items if it.tested),
        "calibration_size": sum(flags),
        "strata_plan": plan,
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
    """Read one annotation sheet; returns annotations and problems (invalid/unknown rows)."""
    annotations: dict[str, Annotation] = {}
    problems: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            iid = (row.get("item_id") or "").strip()
            if iid not in expected_ids:
                problems.append(f"{path.name}: unknown item {iid!r}")
                continue
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


def score(
    key: Mapping[str, object],
    sheet_a: Mapping[str, Annotation],
    sheet_b: Mapping[str, Annotation],
    sheet_owner: Mapping[str, Annotation] | None,
    problems: Sequence[str] = (),
) -> dict[str, object]:
    """Combine annotations into the audit result. Never PASS with any unresolved item."""
    items = [i for i in _seq_of(key.get("items")) if isinstance(i, Mapping)]
    owner = sheet_owner or {}
    final: dict[str, Annotation] = {}
    disputed: list[str] = []
    missing: list[str] = []
    cal_missing_owner: list[str] = []
    pairs: list[tuple[str, str]] = []
    for item in items:
        iid = str(item["item_id"])
        a, b = sheet_a.get(iid), sheet_b.get(iid)
        if a is not None and b is not None:
            pairs.append((a.verdict, b.verdict))
        if item.get("calibration") is True and iid not in owner:
            cal_missing_owner.append(iid)
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
    size_ok = n_items >= DEFAULT_SAMPLE_SIZE and len(tested_ids) * 2 >= DEFAULT_SAMPLE_SIZE
    unresolved = bool(disputed or missing or cal_missing_owner or problems or not size_ok)
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
        "sample_size_ok": size_ok,
        "kappa_verdict_AB": cohens_kappa(pairs),
        "paired_items": len(pairs),
        "bounds": bounds,
        "disputed_for_owner": sorted(disputed),
        "missing_annotation": sorted(missing),
        "calibration_missing_owner": sorted(cal_missing_owner),
        "problems": list(problems),
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
    lines.append(f"kappa (verdict A vs B): {result['kappa_verdict_AB']}")
    for field in ("disputed_for_owner", "missing_annotation", "calibration_missing_owner"):
        value = result[field]
        count = len(value) if isinstance(value, list) else 0
        lines.append(f"{field}: {count}")
    if result["problems"]:
        lines.append(f"problems: {len(_seq_of(result['problems']))} (see JSON)")
    if result["result"] == "UNKNOWN":
        lines.append("UNKNOWN: unresolved items remain; this is never a pass.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- CLI


def _cmd_sample(args: argparse.Namespace) -> int:
    candidates, meta = load_candidates(
        Path(args.audit_dir), tested_seat=args.tested_seat, tested_deck_id=args.tested_deck_id
    )
    paths = write_sample(
        candidates,
        meta,
        Path(args.out_dir),
        seed=args.seed,
        size=args.size,
        calibration=args.calibration,
        min_games=args.min_games,
    )
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
    text = _text_report(result)
    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    sys.stdout.write(text)
    return {"PASS": 0, "FAIL": 1}.get(str(result["result"]), 2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilot_audit_sample", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sample", help="draw the blinded sample")
    s.add_argument("--audit-dir", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--size", type=int, default=DEFAULT_SAMPLE_SIZE)
    s.add_argument("--calibration", type=int, default=DEFAULT_CALIBRATION_SIZE)
    s.add_argument("--min-games", type=int, default=DEFAULT_MIN_GAMES)
    s.add_argument("--tested-seat", type=int, default=0)
    s.add_argument("--tested-deck-id", default=None)
    s.set_defaults(func=_cmd_sample)
    c = sub.add_parser("score", help="score the annotation sheets")
    c.add_argument("--key", required=True)
    c.add_argument("--sheet-a", required=True)
    c.add_argument("--sheet-b", required=True)
    c.add_argument("--sheet-owner", default=None)
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
