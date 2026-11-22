"""WP-9 of the builder audit (Refs #1404): does the model judgement H order cards by usage
beyond the strength index? T6 deck split and T7 time split, without any model in the target.

The plan with thresholds was committed before any number was computed:
``docs/analysis-reports/validation_plan_h_t6_t7.md``. The result has no effect on product
code, index, tiers or display.

Two stages:

``prepare``  reads a Studio store copy (outside the repository), recomputes the product strength
             index on derived store copies that keep only the training decks (T6) or only the decks
             up to a cut-off date (T7), and writes one intermediate JSON file (scratch, never in the
             repository).
``analyse``  is pure: it reads only the intermediate file and writes the result JSON (aggregates).

Standard library only (plus ``commander_lab`` for ``prepare``). Every split is by SHA-256 of the
deck id; the bootstrap uses ``random.Random`` with a fixed seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import sqlite3
import sys
from collections.abc import Iterable, Mapping, Sequence
from operator import itemgetter
from pathlib import Path
from typing import Any

COMMANDER = "Chulane, Teller of Tales"
FOLDS = 5
FOLD_SALT = "wp9-t6-folds-20261122:"
T6_HALF_SALT = "wp9-t6-halves-20261122:"
T7_HALF_SALT = "wp9-t7-halves-20261122:"
CUTOFFS = ("2026-08-09", "2026-09-30")  # primary, sensitivity
BOOTSTRAP = 1000
SEED = 20261122
MIN_POST_DECKS = 30
MIN_INFORMATIVE_CARDS = 50
MAX_UNDEFINED_SHARE = 0.05
RELEVANT = 0.10
Z95 = 1.959964
COHORT_ALL = "alle"
COHORT_B3 = "bracket:3"
CORPUS_TABLES = (
    "corpus_deck_card",
    "corpus_cohort",
    "corpus_deck_part",
    "corpus_deck_stat",
    "corpus_deck_role",
    "corpus_deck",
)

KEIN_SCHLUSS = "KEIN_SCHLUSS"
NOT_RUN = "NOT_RUN"
MESSBAR_POSITIV = "MESSBAR_POSITIV"
GEGENLAEUFIG = "GEGENLAEUFIG"
KEIN_MESSBARER_NUTZEN = "KEIN_MESSBARER_NUTZEN"


# ---------------------------------------------------------------------------------------------
# Pure statistics
# ---------------------------------------------------------------------------------------------


def midranks(values: Sequence[float]) -> list[float]:
    """Ranks 1..n; tied values share the mean of the ranks they occupy."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        mean = (start + end) / 2 + 1
        for position in range(start, end + 1):
            ranks[order[position]] = mean
        start = end + 1
    return ranks


def centered_group_ranks(groups: Sequence[object], values: Sequence[float]) -> list[float]:
    """Per group g of n cards: (midrank - (n + 1) / 2) / n. A group of one card gives 0."""
    members: dict[object, list[int]] = {}
    for index, group in enumerate(groups):
        members.setdefault(group, []).append(index)
    out = [0.0] * len(values)
    for indices in members.values():
        size = len(indices)
        ranks = midranks([values[i] for i in indices])
        for i, rank in zip(indices, ranks, strict=True):
            out[i] = (rank - (size + 1) / 2) / size
    return out


def correlation(u: Sequence[float], v: Sequence[float]) -> float | None:
    """sum(u v) / sqrt(sum(u^2) sum(v^2)) for already centred values; None if a sum is 0."""
    suv = sum(a * b for a, b in zip(u, v, strict=True))
    suu = sum(a * a for a in u)
    svv = sum(b * b for b in v)
    if suu <= 0 or svv <= 0:
        return None
    return suv / math.sqrt(suu * svv)


def stratified_rank_corr(
    groups: Sequence[object], x: Sequence[float], y: Sequence[float]
) -> float | None:
    """The stratified rank correlation rho_w(x, y | G) of the plan (section 3)."""
    return correlation(centered_group_ranks(groups, x), centered_group_ranks(groups, y))


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Plain Spearman correlation with midranks (one group)."""
    return stratified_rank_corr([0] * len(x), x, y)


def group_signs(
    groups: Sequence[object], x: Sequence[float], y: Sequence[float], min_size: int = 3
) -> tuple[int, int]:
    """(groups with rho_g > 0, groups with a defined rho_g) over groups of >= min_size cards."""
    members: dict[object, list[int]] = {}
    for index, group in enumerate(groups):
        members.setdefault(group, []).append(index)
    positive = defined = 0
    for indices in members.values():
        if len(indices) < min_size:
            continue
        rho = spearman([x[i] for i in indices], [y[i] for i in indices])
        if rho is None:
            continue
        defined += 1
        positive += 1 if rho > 0 else 0
    return positive, defined


def informative_cards(groups: Sequence[object], y: Sequence[float]) -> int:
    """Cards in groups of at least 2 cards whose target is not constant."""
    members: dict[object, list[float]] = {}
    for group, value in zip(groups, y, strict=True):
        members.setdefault(group, []).append(value)
    return sum(len(vals) for vals in members.values() if len(vals) >= 2 and len(set(vals)) > 1)


def wilson(successes: int, total: int, z: float = Z95) -> tuple[float, float] | None:
    """95 % Wilson score interval; None for total 0."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def percentile_interval(values: Sequence[float], replicates: int) -> tuple[float, float] | None:
    """Plan section 6: sorted value at floor(0.025 B) and ceil(0.975 B) - 1 (0-based), B = the
    number of planned replicates. Undefined replicates are dropped before; None if too few."""
    ordered = sorted(values)
    low = math.floor(0.025 * replicates)
    high = math.ceil(0.975 * replicates) - 1
    # dropped replicates shift the positions proportionally
    scale = len(ordered) / replicates if replicates else 0
    lo_i = min(len(ordered) - 1, int(low * scale)) if ordered else -1
    hi_i = min(len(ordered) - 1, int(high * scale)) if ordered else -1
    if lo_i < 0 or hi_i < 0:
        return None
    return (ordered[lo_i], ordered[hi_i])


def hash_order(ids: Iterable[str], salt: str) -> list[str]:
    """Ids sorted by SHA-256 of salt + id (ties, which do not occur, by id)."""
    return sorted(ids, key=lambda i: (hashlib.sha256((salt + i).encode("utf-8")).hexdigest(), i))


def assign_folds(ids: Iterable[str], folds: int, salt: str) -> dict[str, int]:
    return {deck: position % folds for position, deck in enumerate(hash_order(ids, salt))}


def split_halves(ids: Iterable[str], salt: str) -> tuple[list[str], list[str]]:
    ordered = hash_order(ids, salt)
    return ordered[0::2], ordered[1::2]


def verdict(
    *,
    ceiling: tuple[float, float] | None,
    statistic: float | None,
    interval: tuple[float, float] | None,
    informative: int,
    undefined_share: float,
) -> str:
    """Decision table of the plan (section 8)."""
    if (
        informative < MIN_INFORMATIVE_CARDS
        or undefined_share > MAX_UNDEFINED_SHARE
        or ceiling is None
        or statistic is None
        or interval is None
    ):
        return KEIN_SCHLUSS
    if ceiling[0] <= 0:
        return KEIN_SCHLUSS
    if interval[0] > 0:
        return MESSBAR_POSITIV
    if interval[1] < 0:
        return GEGENLAEUFIG
    return KEIN_MESSBARER_NUTZEN


# ---------------------------------------------------------------------------------------------
# Analysis of one test (pure, from the intermediate data)
# ---------------------------------------------------------------------------------------------


class Part:
    """One fold (T6) or one cohort after a cut-off (T7): fixed groups and predictors, the
    held-out decks as positions, per card the positions of the held-out decks that list it."""

    def __init__(
        self,
        *,
        cards: Sequence[str],
        h: Mapping[str, float],
        index: Mapping[str, float],
        is_land: Mapping[str, bool],
        train_count: Mapping[str, int],
        heldout: Sequence[str],
        halves: tuple[Sequence[str], Sequence[str]],
        card_decks: Mapping[str, Iterable[str]],
    ) -> None:
        self.cards = list(cards)
        self.h = [float(h[c]) for c in self.cards]
        self.train = [float(train_count[c]) for c in self.cards]
        self.g1 = [(bool(is_land[c]), round(float(index[c]), 1)) for c in self.cards]
        self.g2 = [(bool(is_land[c]), int(train_count[c])) for c in self.cards]
        self.n_heldout = len(heldout)
        self.positions = self._positions(heldout, card_decks)
        self.half_a = self._positions(halves[0], card_decks)
        self.half_b = self._positions(halves[1], card_decks)
        self.n_a = len(halves[0])
        self.n_b = len(halves[1])
        self.u_h = {
            "G1": centered_group_ranks(self.g1, self.h),
            "G2": centered_group_ranks(self.g2, self.h),
        }
        self.u_train = centered_group_ranks(self.g1, self.train)

    def _positions(
        self, decks: Sequence[str], card_decks: Mapping[str, Iterable[str]]
    ) -> list[list[int]]:
        where = {deck: i for i, deck in enumerate(decks)}
        return [
            sorted(where[d] for d in card_decks.get(card, ()) if d in where) for card in self.cards
        ]

    def groups(self, name: str) -> list[tuple[bool, float]] | list[tuple[bool, int]]:
        return self.g1 if name == "G1" else self.g2


def _counts(positions: Sequence[Sequence[int]], weights: Sequence[int] | None) -> list[float]:
    if weights is None:
        return [float(len(p)) for p in positions]
    out: list[float] = []
    for plist in positions:
        if not plist:
            out.append(0.0)
        elif len(plist) == 1:
            out.append(float(weights[plist[0]]))
        else:
            out.append(float(sum(itemgetter(*plist)(weights))))
    return out


def _draw(rng: random.Random, n: int) -> list[int]:
    weights = [0] * n
    for _ in range(n):
        weights[rng.randrange(n)] += 1
    return weights


def _part_stats(
    part: Part,
    y: Sequence[float],
    ya: Sequence[float],
    yb: Sequence[float],
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for name in ("G1", "G2"):
        groups = part.groups(name)
        v = centered_group_ranks(groups, y)
        out[f"{name}_H"] = correlation(part.u_h[name], v)
        out[f"{name}_ceiling"] = stratified_rank_corr(groups, ya, yb)
        if name == "G1":
            out["G1_train"] = correlation(part.u_train, v)
    return out


def _mean(values: Sequence[float | None]) -> float | None:
    if not values or any(v is None for v in values):
        return None
    return sum(v for v in values if v is not None) / len(values)


STAT_KEYS = ("G1_H", "G1_ceiling", "G1_train", "G2_H", "G2_ceiling")


def analyse_parts(parts: Sequence[Part], *, replicates: int, seed: int) -> dict[str, Any]:
    """Point values, fold spread and bootstrap intervals for a list of parts (mean over parts)."""
    point_by_part = [
        _part_stats(
            p,
            _counts(p.positions, None),
            _counts(p.half_a, None),
            _counts(p.half_b, None),
        )
        for p in parts
    ]
    point = {key: _mean([s[key] for s in point_by_part]) for key in STAT_KEYS}
    spread = {
        key: (
            [min(v for v in vals if v is not None), max(v for v in vals if v is not None)]
            if all(v is not None for v in vals)
            else None
        )
        for key in STAT_KEYS
        for vals in [[s[key] for s in point_by_part]]
    }
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {key: [] for key in STAT_KEYS}
    undefined = dict.fromkeys(STAT_KEYS, 0)
    for _ in range(replicates):
        rep = []
        for p in parts:
            weights = _draw(rng, p.n_heldout)
            wa = _draw(rng, p.n_a)
            wb = _draw(rng, p.n_b)
            rep.append(
                _part_stats(
                    p,
                    _counts(p.positions, weights),
                    _counts(p.half_a, wa),
                    _counts(p.half_b, wb),
                )
            )
        for key in STAT_KEYS:
            value = _mean([s[key] for s in rep])
            if value is None:
                undefined[key] += 1
            else:
                samples[key].append(value)
    intervals = {key: percentile_interval(samples[key], replicates) for key in STAT_KEYS}
    result: dict[str, Any] = {
        "parts": len(parts),
        "heldout_decks": [p.n_heldout for p in parts],
        "cards": [len(p.cards) for p in parts],
        "point": point,
        "part_min_max": spread,
        "interval95": intervals,
        "undefined_replicates": undefined,
        "replicates": replicates,
    }
    for name in ("G1", "G2"):
        informative = min(
            informative_cards(p.groups(name), _counts(p.positions, None)) for p in parts
        )
        positive = defined = 0
        groups_total = 0
        for p in parts:
            k, m = group_signs(p.groups(name), p.h, _counts(p.positions, None))
            positive += k
            defined += m
            groups_total += len(set(p.groups(name)))
        ceiling_point = point[f"{name}_ceiling"]
        statistic_h = point[f"{name}_H"]
        result[name] = {
            "informative_cards_min": informative,
            "groups_mean": groups_total / len(parts),
            "groups_positive": positive,
            "groups_defined": defined,
            "groups_positive_wilson95": wilson(positive, defined),
            "spearman_brown_bound": (
                math.sqrt(2 * ceiling_point / (1 + ceiling_point))
                if ceiling_point is not None and ceiling_point > 0
                else None
            ),
            "verdict": verdict(
                ceiling=intervals[f"{name}_ceiling"],
                statistic=point[f"{name}_H"],
                interval=intervals[f"{name}_H"],
                informative=informative,
                undefined_share=max(undefined[f"{name}_H"], undefined[f"{name}_ceiling"])
                / replicates,
            ),
            "relevant": statistic_h is not None and statistic_h >= RELEVANT,
        }
    # context only (point values over all analysed cards of the first part, never a gate)
    first = parts[0]
    y0 = _counts(first.positions, None)
    result["context"] = {
        "spearman_H_target": spearman(first.h, y0),
        "spearman_train_target": spearman(first.train, y0),
        "spearman_halfA_halfB": spearman(_counts(first.half_a, None), _counts(first.half_b, None)),
    }
    return result


def _part_from(
    raw: Mapping[str, Any],
    h: Mapping[str, float],
    card_decks: Mapping[str, Sequence[str]],
    heldout: Sequence[str],
    salt: str,
) -> Part:
    index: Mapping[str, float] = raw["index"]
    cards = sorted(c for c in index if c in h)
    return Part(
        cards=cards,
        h=h,
        index=index,
        is_land=raw["is_land"],
        train_count=raw["train_count"],
        heldout=heldout,
        halves=split_halves(heldout, salt),
        card_decks=card_decks,
    )


def analyse(
    data: Mapping[str, Any], *, replicates: int = BOOTSTRAP, seed: int = SEED
) -> dict[str, Any]:
    """The whole analysis from the intermediate data (pure)."""
    h: dict[str, float] = {k: float(v) for k, v in data["h"].items()}
    card_decks: dict[str, list[str]] = data["card_decks"]
    universe: list[str] = data["universe"]
    folds = assign_folds(universe, FOLDS, FOLD_SALT)
    out: dict[str, Any] = {"meta": data.get("meta", {}), "T6": None, "T7": {}}
    t6_parts = []
    for fold in range(FOLDS):
        raw = data["t6"][str(fold)]
        heldout = [d for d in universe if folds[d] == fold]
        t6_parts.append(_part_from(raw, h, card_decks, heldout, T6_HALF_SALT))
    out["T6"] = analyse_parts(t6_parts, replicates=replicates, seed=seed)
    dates: dict[str, str] = data["deck_date"]
    bracket3 = set(data["bracket3"])
    for cutoff in data["t7"]:
        raw = data["t7"][cutoff]
        post = [d for d in universe if dates[d] > cutoff]
        out["T7"][cutoff] = {}
        for cohort, decks in (
            (COHORT_ALL, post),
            (COHORT_B3, [d for d in post if d in bracket3]),
        ):
            if len(decks) < MIN_POST_DECKS:
                out["T7"][cutoff][cohort] = {"verdict": NOT_RUN, "post_decks": len(decks)}
                continue
            part = _part_from(raw, h, card_decks, decks, T7_HALF_SALT)
            result = analyse_parts([part], replicates=replicates, seed=seed)
            result["post_decks"] = len(decks)
            result["pre_decks"] = sum(1 for d in universe if dates[d] <= cutoff)
            out["T7"][cutoff][cohort] = result
    return out


# ---------------------------------------------------------------------------------------------
# prepare: read the store copy (needs commander_lab; never part of the tests)
# ---------------------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _derived_store(source: Path, folder: Path, keep: Iterable[str]) -> Path:
    """Copy of the store that keeps only ``keep`` in every corpus table (never ``deck*``)."""
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    target = folder / "studio.sqlite3"
    shutil.copyfile(source, target)
    connection = sqlite3.connect(target)
    try:
        connection.execute("CREATE TEMP TABLE keep(deck_id TEXT PRIMARY KEY)")
        connection.executemany("INSERT INTO keep VALUES (?)", [(d,) for d in keep])
        for table in CORPUS_TABLES:
            connection.execute(
                f"DELETE FROM {table} WHERE deck_id NOT IN (SELECT deck_id FROM keep)"
            )
        connection.commit()
    finally:
        connection.close()
    return folder


def _strength(folder: Path) -> tuple[dict[str, Any], list[str]]:
    from commander_lab.studio import strength, strength_view, universe, universe_choice
    from commander_lab.studio.store import StudioStore

    store = StudioStore.open(folder)
    try:
        settings = strength.StrengthSettings.recommended()
        answer = strength_view.compute(store, COMMANDER, settings)
        decks = universe.resolve_universe(store, universe_choice.local_spec(store, COMMANDER))
    finally:
        store.close()
    return dict(answer), list(decks)


def _index_part(answer: Mapping[str, Any]) -> dict[str, Any]:
    index: dict[str, float] = {}
    is_land: dict[str, bool] = {}
    train: dict[str, int] = {}
    for card in answer["cards"]:
        if card.get("index") is None or card.get("tier") == "N":
            continue
        cid = str(card["card_id"])
        index[cid] = float(card["index"])
        is_land[cid] = bool(card["is_land"])
        hits = 0
        for component in card["components"]:
            if component["component"] == "deck_universe" and component["numerator"] is not None:
                hits = int(component["numerator"])
        train[cid] = hits
    return {"index": index, "is_land": is_land, "train_count": train}


def prepare(store_file: Path, work: Path, out_file: Path) -> dict[str, Any]:
    from commander_lab.studio import (
        card_understanding,
        strength,
        understanding_field,
        universe_choice,
        universe_view,
    )
    from commander_lab.studio.store import StudioStore

    checks: dict[str, object] = {}
    if strength.StrengthSettings.recommended().bracket != "upgraded":
        raise SystemExit("check 1 failed: recommended bracket is not 'upgraded'")
    checks["1_bracket_upgraded"] = True

    full = work / "full"
    full.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(store_file, full / "studio.sqlite3")
    answer, universe = _strength(full)
    base = _index_part(answer)

    store = StudioStore.open(full)
    try:
        ids = [str(c["card_id"]) for c in answer["cards"]]
        oracle = understanding_field._oracle_ids(store, ids)
        rows = card_understanding.load()
        h = {
            cid: float(rows[oid]["scores"]["H"])
            for cid, oid in oracle.items()
            if oid and oid in rows
        }
        spec = universe_choice.local_spec(store, COMMANDER)
        _uni, entries, _params = universe_view._spread_all(store, None, None, [COMMANDER], spec)
        card_decks = {str(spread["card_id"]): sorted(decks) for spread, decks, _keys in entries}
        dates = {
            str(r[0]): str(r[1])
            for r in store.connection.execute("SELECT deck_id, deck_date FROM corpus_deck")
        }
        bracket3 = sorted(
            str(r[0])
            for r in store.connection.execute(
                "SELECT deck_id FROM corpus_cohort WHERE cohort = ?", (COHORT_B3,)
            )
        )
    finally:
        store.close()
    universe_set = set(universe)
    card_decks = {c: [d for d in ds if d in universe_set] for c, ds in card_decks.items()}

    mismatch = [
        c for c in base["train_count"] if len(card_decks.get(c, [])) != base["train_count"][c]
    ]
    if mismatch:
        raise SystemExit(f"check 3 failed: {len(mismatch)} cards differ from the product count")
    checks["3_card_deck_counts_equal_product"] = (
        f"{len(base['train_count'])} von {len(base['train_count'])}"
    )

    only_universe = _derived_store(full / "studio.sqlite3", work / "universe_only", universe)
    answer_u, decks_u = _strength(only_universe)
    if sorted(decks_u) != sorted(universe):
        raise SystemExit("check 4 failed: the universe-only copy is not the universe")
    # Plan section 9 (change before the analysis): the deviation is reported, not an abort; the
    # universe-only copy is the basis of every calculation (no duplicate of a held-out deck).
    base_u = _index_part(answer_u)
    differing = [c for c in base["index"] if base_u["index"].get(c) != base["index"][c]]
    tiers = {str(c["card_id"]): c["tier"] for c in answer["cards"]}
    tiers_u = {str(c["card_id"]): c["tier"] for c in answer_u["cards"]}
    checks["2_universe_only_copy_index_differs"] = f"{len(differing)} von {len(base['index'])}"
    checks["2_universe_only_copy_max_abs_difference"] = max(
        (abs(base_u["index"][c] - base["index"][c]) for c in differing), default=0.0
    )
    checks["2_universe_only_copy_tier_changes"] = sum(
        1 for c in tiers if tiers_u.get(c) != tiers[c]
    )
    checks["2_universe_only_corpus_cohorts"] = {
        "store": [g["denominator"] for g in answer["corpus"]["cohorts"]],
        "universe_only": [g["denominator"] for g in answer_u["corpus"]["cohorts"]],
    }
    if base_u["train_count"] != base["train_count"]:
        raise SystemExit("check 2 failed: the universe-only copy changes the deck counts")
    shutil.rmtree(only_universe)

    folds = assign_folds(universe, FOLDS, FOLD_SALT)
    t6: dict[str, Any] = {}
    for fold in range(FOLDS):
        keep = [d for d in universe if folds[d] != fold]
        folder = _derived_store(full / "studio.sqlite3", work / f"t6_fold{fold}", keep)
        answer_f, decks_f = _strength(folder)
        if sorted(decks_f) != sorted(keep):
            raise SystemExit(f"check 4 failed: fold {fold} universe is not the kept set")
        part = _index_part(answer_f)
        keep_set = set(keep)
        for cid, count in part["train_count"].items():
            if count != sum(1 for d in card_decks.get(cid, []) if d in keep_set):
                raise SystemExit(f"check 4 failed: fold {fold} count differs for a card")
        t6[str(fold)] = part
        shutil.rmtree(folder)
    t7: dict[str, Any] = {}
    for cutoff in CUTOFFS:
        keep = [d for d in universe if dates[d] <= cutoff]
        folder = _derived_store(full / "studio.sqlite3", work / f"t7_{cutoff}", keep)
        answer_c, decks_c = _strength(folder)
        if sorted(decks_c) != sorted(keep):
            raise SystemExit(f"check 4 failed: cut-off {cutoff} universe is not the kept set")
        t7[cutoff] = _index_part(answer_c)
        shutil.rmtree(folder)
    checks["4_derived_universe_equals_kept_set"] = True
    checks["5_cards_with_H_in_pool"] = len(h)
    checks["5_cards_with_H_and_index_full"] = sum(1 for c in base["index"] if c in h)

    data = {
        "meta": {
            "store_sha256": sha256_file(store_file),
            "h_file_sha256": sha256_file(card_understanding.DATASET_PATH),
            "commander": COMMANDER,
            "universe_decks": len(universe),
            "pool_cards": len(answer["cards"]),
            "checks": checks,
        },
        "h": h,
        "universe": sorted(universe),
        "card_decks": card_decks,
        "deck_date": {d: dates[d] for d in universe},
        "bracket3": [d for d in bracket3 if d in universe_set],
        "t6": t6,
        "t7": t7,
    }
    out_file.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="read a store copy, write the intermediate file")
    prep.add_argument("--store", type=Path, required=True, help="studio.sqlite3 (a copy)")
    prep.add_argument("--work", type=Path, required=True, help="scratch folder for store copies")
    prep.add_argument("--out", type=Path, required=True, help="intermediate JSON (scratch)")
    ana = sub.add_parser("analyse", help="pure analysis of the intermediate file")
    ana.add_argument("--data", type=Path, required=True)
    ana.add_argument("--out", type=Path, required=True)
    ana.add_argument("--replicates", type=int, default=BOOTSTRAP)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        data = prepare(args.store, args.work, args.out)
        print(json.dumps(data["meta"], indent=1, ensure_ascii=False))
        return 0
    data = json.loads(args.data.read_text(encoding="utf-8"))
    result = analyse(data, replicates=args.replicates)
    result["meta"]["intermediate_sha256"] = sha256_file(args.data)
    args.out.write_text(
        json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
