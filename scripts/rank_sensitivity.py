#!/usr/bin/env python3
"""Pilot sensitivity of the deck ranking (S-1): does a pilot variant reorder the decks?

Two steps, one script:

``play``     plays pods of four decks, every deck in every seat (cyclic rotations), over a set of
             seeds, with the pilot of the checkout it runs from, and writes one game table. Run it
             once per pilot variant from a checkout (git worktree) of that variant, with the
             same pods, seeds and rotations.
``analyze``  reads two or more game tables and answers, per pair of variants and per pod:
             is the ranking of the decks by win share the same, within what chance alone moves it?

The summary measure is Kendall's tau-b between the two rankings of the decks of a pod, averaged
over the pods. The verdict does not rest on tau, whose few possible values (four decks) cannot
tell a swap of two close decks from chance, but on the pairs of decks: for every pair the paired
change of "deck i minus deck j" between the variants is tested with a sign-flip test over the
blocks (pod and seed, the unit both variants played), Holm-adjusted over the pairs of a pod. A pair
that stands in the opposite order in the two variants and passes that test is a reversal.
Before that, a split-half check says whether the ranking is resolvable at all at this number of
seeds: if two halves of the SAME variant already disagree, no variant could be told from the other.

Verdicts, fixed before any game (they are not tuned to the data):

``RANK_SENSITIVE``  at least one pair of decks is reversed (opposite order, Holm p below 0.05).
``NOT_DETECTED``    no reversal, and both variants reproduce their own ranking (split-half tau at
                    least 0.5). Absence of evidence at this n, never "stable".
``UNRESOLVED``      no reversal, and a variant's own halves disagree (split-half tau below 0.5):
                    the decks are too close for this many seeds; the sensitivity stays unknown.
``TOO_FEW_BLOCKS``  fewer than 20 paired blocks in a pod.

Per deck, the paired change of the win share is reported too (sign-flip, Holm over the decks of a
pod), so a ``RANK_SENSITIVE`` pair also says which decks moved.

Usage:
    python3 scripts/rank_sensitivity.py play --jar <bridge.jar> --variant NAME --out games.json \\
        --pod a.json,b.json,c.json,d.json [--pod ...] [--seeds hash:MASTER:40] [--workers 4]
    python3 scripts/rank_sensitivity.py analyze games-a.json games-b.json [--json out.json]
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

FLIPS = 2000
SPLIT_ROUNDS = 400
SEED = 20261023
MIN_BLOCKS = 20
RESOLVED_TAU = 0.5
ALPHA = 0.05
RANK_SENSITIVE = "RANK_SENSITIVE"
NOT_DETECTED = "NOT_DETECTED"
UNRESOLVED = "UNRESOLVED"
TOO_FEW_BLOCKS = "TOO_FEW_BLOCKS"

Block = tuple[str, int]  # (pod, seed)


def credit(row: dict[str, Any]) -> dict[str, float]:
    """Win credit of one game per deck: 1 for a sole winner, shared when several won, 0 for none."""
    decks: list[str] = row["decks"]
    winners: list[int] = row["winners"]
    out = dict.fromkeys(decks, 0.0)
    for seat in winners:
        out[decks[seat]] += 1.0 / len(winners)
    return out


def block_scores(rows: list[dict[str, Any]]) -> dict[Block, dict[str, float]]:
    """(pod, seed) -> deck -> mean win credit over the rotations played for that block."""
    sums: dict[Block, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[Block, int] = defaultdict(int)
    for row in rows:
        block = (row["pod"], int(row["seed"]))
        for deck, value in credit(row).items():
            sums[block][deck] += value
        counts[block] += 1
    return {
        block: {deck: total / counts[block] for deck, total in decks.items()}
        for block, decks in sums.items()
    }


def pod_decks(rows: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    """Pod -> its decks (sorted). Every game of a pod must name the same four decks."""
    seen: dict[str, set[str]] = {}
    for row in rows:
        decks = set(row["decks"])
        if seen.setdefault(row["pod"], decks) != decks:
            raise ValueError(f"pod {row['pod']!r} lists different decks in different games")
    return {pod: tuple(sorted(decks)) for pod, decks in seen.items()}


def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Kendall's tau-b (ties corrected); ``None`` when either side ranks nothing (all tied)."""
    concordant = discordant = ties_x = ties_y = 0
    for i, j in itertools.combinations(range(len(x)), 2):
        dx = (x[i] > x[j]) - (x[i] < x[j])
        dy = (y[i] > y[j]) - (y[i] < y[j])
        if dx == 0 and dy == 0:
            continue
        if dx == 0:
            ties_x += 1
        elif dy == 0:
            ties_y += 1
        elif dx == dy:
            concordant += 1
        else:
            discordant += 1
    denominator = math.sqrt((concordant + discordant + ties_x) * (concordant + discordant + ties_y))
    return None if denominator == 0 else (concordant - discordant) / denominator


def _shares(blocks: list[dict[str, float]], decks: tuple[str, ...]) -> list[float]:
    n = len(blocks)
    return [sum(block[d] for block in blocks) / n for d in decks]


def _mean(values: list[float | None]) -> float | None:
    kept = [v for v in values if v is not None]
    return sum(kept) / len(kept) if kept else None


def split_half_tau(
    blocks_by_pod: dict[str, list[dict[str, float]]],
    decks_by_pod: dict[str, tuple[str, ...]],
    *,
    rounds: int = SPLIT_ROUNDS,
    seed: int = SEED,
) -> float | None:
    """Mean tau between the rankings of two random halves of the blocks of the SAME variant."""
    rng = random.Random(seed)
    taus: list[float | None] = []
    for _ in range(rounds):
        per_pod: list[float | None] = []
        for pod, blocks in blocks_by_pod.items():
            order = list(range(len(blocks)))
            rng.shuffle(order)
            half = len(order) // 2
            first = [blocks[i] for i in order[:half]]
            second = [blocks[i] for i in order[half : 2 * half]]
            if not first:
                continue
            per_pod.append(
                kendall_tau_b(_shares(first, decks_by_pod[pod]), _shares(second, decks_by_pod[pod]))
            )
        taus.append(_mean(per_pod))
    return _mean(taus)


def _sign_flip_p(deltas: list[float], rng: random.Random, flips: int = FLIPS) -> float:
    if not any(deltas):
        return 1.0
    observed = abs(sum(deltas))
    threshold = observed - 1e-9 * max(1.0, observed)
    n = len(deltas)
    extreme = 0
    for _ in range(flips):
        bits = rng.getrandbits(n)
        total = sum(d if (bits >> i) & 1 else -d for i, d in enumerate(deltas))
        extreme += abs(total) >= threshold
    return (extreme + 1) / (flips + 1)


def _holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[key] = running
    return adjusted


def compare_pair(
    a: dict[Block, dict[str, float]],
    b: dict[Block, dict[str, float]],
    decks_by_pod: dict[str, tuple[str, ...]],
    *,
    flips: int = FLIPS,
    seed: int = SEED,
) -> dict[str, Any]:
    """Tau between the rankings of two variants on their shared blocks, and the reversed pairs."""
    shared = sorted(set(a) & set(b))
    pods: dict[str, list[Block]] = defaultdict(list)
    for block in shared:
        pods[block[0]].append(block)
    short = sorted(pod for pod in decks_by_pod if len(pods.get(pod, [])) < MIN_BLOCKS)
    if short:
        return {
            "verdict": TOO_FEW_BLOCKS,
            "blocks_per_pod": {pod: len(pods.get(pod, [])) for pod in decks_by_pod},
            "short_pods": short,
        }

    tau_by_pod: dict[str, float | None] = {}
    deck_changes: dict[str, dict[str, Any]] = {}
    reversed_pairs: list[dict[str, Any]] = []
    for pod, blocks in pods.items():
        decks = decks_by_pod[pod]
        share_a = _shares([a[blk] for blk in blocks], decks)
        share_b = _shares([b[blk] for blk in blocks], decks)
        tau_by_pod[pod] = kendall_tau_b(share_a, share_b)

        deck_p = {
            deck: _sign_flip_p(
                [b[blk][deck] - a[blk][deck] for blk in blocks], random.Random(seed), flips
            )
            for deck in decks
        }
        deck_adjusted = _holm(deck_p)
        for deck, sa, sb in zip(decks, share_a, share_b, strict=True):
            deck_changes[f"{pod}/{deck}"] = {
                "share_a": round(sa, 4),
                "share_b": round(sb, 4),
                "mean_delta": round(sb - sa, 4),
                "p_holm": round(deck_adjusted[deck], 4),
            }

        pair_p: dict[str, float] = {}
        for i, j in itertools.combinations(range(len(decks)), 2):
            diffs = [
                (b[blk][decks[i]] - b[blk][decks[j]]) - (a[blk][decks[i]] - a[blk][decks[j]])
                for blk in blocks
            ]
            pair_p[f"{decks[i]}|{decks[j]}"] = _sign_flip_p(diffs, random.Random(seed), flips)
        pair_adjusted = _holm(pair_p)
        for i, j in itertools.combinations(range(len(decks)), 2):
            order_a = (share_a[i] > share_a[j]) - (share_a[i] < share_a[j])
            order_b = (share_b[i] > share_b[j]) - (share_b[i] < share_b[j])
            key = f"{decks[i]}|{decks[j]}"
            if order_a * order_b < 0 and pair_adjusted[key] < ALPHA:
                reversed_pairs.append(
                    {
                        "pod": pod,
                        "decks": [decks[i], decks[j]],
                        "gap_a": round(share_a[i] - share_a[j], 4),
                        "gap_b": round(share_b[i] - share_b[j], 4),
                        "p_holm": round(pair_adjusted[key], 4),
                    }
                )
    observed = _mean(list(tau_by_pod.values()))
    return {
        "blocks_per_pod": {pod: len(blocks) for pod, blocks in pods.items()},
        "tau_by_pod": {pod: None if t is None else round(t, 4) for pod, t in tau_by_pod.items()},
        "tau_observed": None if observed is None else round(observed, 4),
        "reversed_pairs": reversed_pairs,
        "deck_changes": deck_changes,
    }


def analyze(
    variants: dict[str, list[dict[str, Any]]],
    *,
    flips: int = FLIPS,
    split_rounds: int = SPLIT_ROUNDS,
) -> dict[str, Any]:
    """Pairwise comparison of all variants plus the split-half resolution of each one."""
    decks_by_pod: dict[str, tuple[str, ...]] = {}
    for rows in variants.values():
        for pod, decks in pod_decks(rows).items():
            if decks_by_pod.setdefault(pod, decks) != decks:
                raise ValueError(f"pod {pod!r} has different decks in different variants")
    scores = {name: block_scores(rows) for name, rows in variants.items()}

    resolution: dict[str, float | None] = {}
    for name, blocks in scores.items():
        by_pod: dict[str, list[dict[str, float]]] = defaultdict(list)
        for (pod, _seed), shares in sorted(blocks.items()):
            by_pod[pod].append(shares)
        resolution[name] = split_half_tau(by_pod, decks_by_pod, rounds=split_rounds)

    pairs: dict[str, dict[str, Any]] = {}
    for first, second in itertools.combinations(variants, 2):
        result = compare_pair(scores[first], scores[second], decks_by_pod, flips=flips)
        if "verdict" not in result:
            unresolved = [
                name
                for name in (first, second)
                if resolution[name] is None or resolution[name] < RESOLVED_TAU  # type: ignore[operator]
            ]
            if result["reversed_pairs"]:
                result["verdict"] = RANK_SENSITIVE
            elif unresolved:
                result["verdict"] = UNRESOLVED
                result["unresolved_variants"] = unresolved
            else:
                result["verdict"] = NOT_DETECTED
        pairs[f"{first} vs {second}"] = result
    return {
        "variants": {
            name: {
                "games": len(rows),
                "blocks": len(scores[name]),
                "split_half_tau": None if resolution[name] is None else round(resolution[name], 4),  # type: ignore[arg-type]
            }
            for name, rows in variants.items()
        },
        "pods": {pod: list(decks) for pod, decks in decks_by_pod.items()},
        "pairs": pairs,
        "thresholds": {
            "resolved_tau": RESOLVED_TAU,
            "alpha": ALPHA,
            "min_blocks_per_pod": MIN_BLOCKS,
            "flips": flips,
        },
    }


def format_markdown(result: dict[str, Any]) -> list[str]:
    lines = [
        "| Variant | Games | Blocks | Split-half tau |",
        "|---|---:|---:|---:|",
    ]
    for name, row in result["variants"].items():
        lines.append(f"| {name} | {row['games']} | {row['blocks']} | {row['split_half_tau']} |")
    lines += ["", "| Pair | Verdict | tau | Reversed pairs |", "|---|---|---:|---:|"]
    for name, pair in result["pairs"].items():
        lines.append(
            f"| {name} | **{pair['verdict']}** | {pair.get('tau_observed')} | "
            f"{len(pair.get('reversed_pairs', []))} |"
        )
    for name, pair in result["pairs"].items():
        for rev in pair.get("reversed_pairs", []):
            lines.append(
                f"- {name}, {rev['pod']}: {rev['decks'][0]} vs {rev['decks'][1]} "
                f"gap {rev['gap_a']} -> {rev['gap_b']} (Holm p {rev['p_holm']})"
            )
        moved = {k: v for k, v in pair.get("deck_changes", {}).items() if v["p_holm"] < ALPHA}
        if moved:
            lines += ["", f"Decks whose win share moved ({name}, Holm p < {ALPHA}):"]
            lines += [
                f"- {deck}: {v['share_a']} -> {v['share_b']} (p {v['p_holm']})"
                for deck, v in moved.items()
            ]
    return lines


def analyze_command(args: argparse.Namespace) -> int:
    variants: dict[str, list[dict[str, Any]]] = {}
    for path in args.tables:
        table = json.loads(path.read_text(encoding="utf-8"))
        variants[table["variant"]] = [g for g in table["games"] if g.get("status", "ok") == "ok"]
    result = analyze(variants)
    for line in format_markdown(result):
        print(line)
    if args.json:
        args.json.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return 0


def rotations(decks: Sequence[Any], count: int = 4) -> list[tuple[Any, ...]]:
    """Cyclic seat rotations of a pod: every deck sits in every seat once for ``count`` = 4."""
    return [tuple(decks[(i + r) % len(decks)] for i in range(len(decks))) for r in range(count)]


def play_command(args: argparse.Namespace) -> int:
    # Imported here: the analysis needs none of the engine-side modules.
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "scripts"))
    import benchmark_xmage_full_games as bench
    import pilot_decision_report as report

    seeds = bench._seeds(args.seeds)
    jvm_options = list(args.jvm_option)
    if args.games_per_jvm > 1:
        jvm_options.append(f"-Dcommanderlab.fullGame.gamesPerJvm={args.games_per_jvm}")
    command = bench.bridge_command(args.jar, jvm_options)

    pods = [[Path(p) for p in text.split(",")] for text in args.pod]
    jobs: list[tuple[str, Any, int]] = []
    seat_decks: dict[str, list[str]] = {}
    for index, decks in enumerate(pods):
        if len(decks) != 4:
            raise SystemExit("a pod needs exactly four decks")
        for rot, order in enumerate(rotations(decks)):
            name = f"pod{index}-r{rot}"
            seat_decks[name] = [path.stem for path in order]
            setup = bench._setup(tuple(order))
            jobs += [(name, setup, seed) for seed in seeds]
    size = max(1, args.games_per_jvm)
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        if size == 1:
            singles = [pool.submit(report._play, command, *job) for job in jobs]
            rows = [future.result() for future in singles]
        else:
            chunks = [jobs[i : i + size] for i in range(0, len(jobs), size)]
            batches = [pool.submit(report._play_batch, command, chunk) for chunk in chunks]
            rows = [row for future in batches for row in future.result()]
    games = []
    for row in rows:
        pod, _, rot = row["pod"].rpartition("-r")
        games.append(
            {
                "pod": pod,
                "seed": row["seed"],
                "rotation": int(rot),
                "decks": seat_decks[row["pod"]],
                "winners": row.get("winners", []),
                "status": row.get("status", "ok"),
                "semantic": row.get("semantic"),
            }
        )
    table = {"variant": args.variant, "seeds": args.seeds, "games": games}
    args.out.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    bad = [g for g in games if g["status"] != "ok"]
    print(f"{len(games)} games, {len(bad)} not ok -> {args.out}")
    return 0 if not bad else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    play = sub.add_parser("play")
    play.add_argument("--jar", type=Path, required=True)
    play.add_argument("--variant", required=True)
    play.add_argument("--out", type=Path, required=True)
    play.add_argument(
        "--pod", action="append", required=True, help="four deck files, comma-separated"
    )
    play.add_argument("--seeds", default="hash:s1-rank:40")
    play.add_argument("--workers", type=int, default=1)
    play.add_argument("--games-per-jvm", type=int, default=1)
    play.add_argument("--jvm-option", action="append", default=[])
    play.set_defaults(func=play_command)
    ana = sub.add_parser("analyze")
    ana.add_argument("tables", type=Path, nargs="+")
    ana.add_argument("--json", type=Path, default=None)
    ana.set_defaults(func=analyze_command)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
