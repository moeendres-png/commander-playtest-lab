"""A corpus of real pilot requests: record it from real games, replay it without a JVM.

The pilot unit tests answer hand-built request dicts. A hand-built dict shows the keys its
author remembered, so a pilot that reads a field the bridge never sends, or a bridge that
renames one, stays green (#787, #862). This script keeps a small, stratified sample of the
requests that real XMage games put to the policy, in the shape the bridge produced them.

    # once per bridge change: play real games and keep a stratified sample
    python scripts/pilot_request_corpus.py record --jar bridge.jar --seeds 1-2 \\
        --out tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz

    # after a pilot change: how many real decisions would it answer differently?
    python scripts/pilot_request_corpus.py diff

``diff`` needs no JVM. It answers every corpus request with a fresh policy and counts the
answers that differ from the recorded ones, per decision class. That is the behaviour
footprint of a pilot change on real inputs, to quote next to the report comparison of a PR.
Only requests that a fresh policy reproduced when they were recorded (``stateless``) count:
a request that depends on what the same seat was asked earlier cannot be replayed alone.

The corpus is a sample of the pod, not a game. It proves that real shapes are answered
legally; it does not rank pilots.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_CORPUS = ROOT / "tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz"
CORPUS_VERSION = 1
# Priority and mana payment are 91 % of the decisions of a game; the others are rare and
# strategic, so they are kept nearly whole.
CAP_BY_CLASS = {"priority": 80, "mana_payment": 60}
DEFAULT_CAP = 40


def _bucket(request: dict[str, Any]) -> str:
    """The shape of a request that decides which part of the pilot answers it."""
    options = [o for o in request.get("legal_options") or [] if isinstance(o, dict)]
    if request.get("decision_class") != "priority":
        return "one" if len(options) <= 1 else ("few" if len(options) <= 3 else "many")
    kinds = set()
    for option in options:
        meta = option.get("metadata") if isinstance(option.get("metadata"), dict) else {}
        if option.get("option_type") == "pass_priority":
            continue
        ability = str(meta.get("ability_type", ""))
        if ability == "spell":
            kinds.add("spell")
        elif ability == "play_land" or option.get("option_type") == "play_land":
            kinds.add("land")
        elif option.get("option_type") == "mana_ability":
            kinds.add("mana")
        else:
            kinds.add("ability")
    if not kinds:
        return "pass_only"
    # A window with a spell is the strategic one; keep every flavour of it apart.
    return "+".join(sorted(kinds))


def select_corpus(
    records: Sequence[dict[str, Any]],
    *,
    caps: dict[str, int] | None = None,
    default_cap: int = DEFAULT_CAP,
) -> list[dict[str, Any]]:
    """A deterministic, stratified sample of ``records`` (each ``{"seed", "request", "answer"}``).

    Per decision class at most ``cap`` records, and all of them when the class is smaller.
    Within a class the records are split by ``_bucket`` and taken round-robin from evenly
    spaced positions, so a rare shape (a window with a castable spell) is kept before a
    common one (a pass-only window) fills the quota.
    """
    limits = {**CAP_BY_CLASS, **(caps or {})}
    by_class: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for index, record in enumerate(records):
        request = record["request"]
        by_class[str(request["decision_class"])][_bucket(request)].append(index)

    chosen: list[int] = []
    for decision_class in sorted(by_class):
        cap = limits.get(decision_class, default_cap)
        buckets = by_class[decision_class]
        total = sum(len(v) for v in buckets.values())
        if total <= cap:
            chosen.extend(i for v in buckets.values() for i in v)
            continue
        # Evenly spaced picks inside each bucket, then round-robin over the buckets from the
        # rarest to the most common until the quota is full.
        picks = {
            name: [
                members[int(k * len(members) / min(len(members), cap))]
                for k in range(min(len(members), cap))
            ]
            for name, members in buckets.items()
        }
        order = sorted(picks, key=lambda name: (len(buckets[name]), name))
        taken: list[int] = []
        depth = 0
        while len(taken) < cap and any(depth < len(picks[n]) for n in order):
            for name in order:
                if depth < len(picks[name]) and len(taken) < cap:
                    taken.append(picks[name][depth])
            depth += 1
        chosen.extend(taken)
    return [records[i] for i in sorted(set(chosen))]


def load_corpus(path: Path = DEFAULT_CORPUS) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The header and the rows of a corpus file."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle if line.strip()]
    header, rows = lines[0], lines[1:]
    if header.get("corpus_version") != CORPUS_VERSION:
        raise ValueError(f"unsupported corpus version in {path}: {header.get('corpus_version')}")
    return header, rows


def write_corpus(path: Path, header: dict[str, Any], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 and no file name in the header: the same corpus is the same bytes.
    with (
        path.open("wb") as handle,
        gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as raw,
    ):
        for item in (header, *rows):
            raw.write((json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n").encode())


def answer_key(answer: dict[str, Any]) -> str:
    """What an answer chose, without the ids that identify the request."""
    return json.dumps(
        {
            k: answer.get(k)
            for k in ("selected_option_ids", "numeric_choice", "numeric_choices", "ordering")
        },
        sort_keys=True,
    )


def legality_problems(request: dict[str, Any], answer: dict[str, Any]) -> list[str]:
    """Reasons an answer is not a legal answer to the request (empty when it is legal)."""
    problems: list[str] = []
    ids = {o.get("option_id") for o in request.get("legal_options") or [] if isinstance(o, dict)}
    selected = list(answer.get("selected_option_ids") or [])
    unknown = [s for s in selected if s not in ids]
    if unknown:
        problems.append(f"selected ids that were not offered: {unknown[:3]}")
    if len(set(selected)) != len(selected):
        problems.append("the same option selected twice")
    minimum = request.get("minimum_selections", request.get("min_selections"))
    maximum = request.get("maximum_selections", request.get("max_selections"))
    if isinstance(minimum, int) and len(selected) < minimum:
        problems.append(f"{len(selected)} selected, minimum is {minimum}")
    if isinstance(maximum, int) and maximum > 0 and len(selected) > maximum:
        problems.append(f"{len(selected)} selected, maximum is {maximum}")
    if answer.get("decision_id") != request.get("decision_id"):
        problems.append("answer names another decision id")
    if answer.get("actor_id") != request.get("actor_id"):
        problems.append("answer names another actor id")
    return problems


def fresh_policy(seed: int) -> Any:
    """A policy for the real pod, as the full-game runner builds it, without starting a JVM."""
    import benchmark_xmage_full_games as bench

    from commander_lab.engine.rules.full_game import XmageFullGameRunner

    scenario, decks, pilots = bench._setup(tuple(bench.smoke.REAL_DECK_PATHS))
    runner = XmageFullGameRunner(("java",), private_card_repository=True)
    return runner._validated_policy(scenario.model_copy(update={"seed": seed}), decks, pilots)


def replay(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Answer every row with a fresh policy; ``answer`` is None when the policy raised."""
    results = []
    for row in rows:
        policy = fresh_policy(int(row["seed"]))
        try:
            answer = policy.decide(copy.deepcopy(row["request"]))
            error = None
        except Exception as exc:  # a raise is a result of the replay, not a crash of it
            answer, error = None, f"{type(exc).__name__}: {exc}"[:300]
        results.append({"answer": answer, "error": error})
    return results


def record(args: argparse.Namespace) -> int:
    import benchmark_xmage_full_games as bench
    import pilot_decision_report as pdr

    from commander_lab.engine.rules.full_game import XmageFullGameRunner

    command = bench.bridge_command(args.jar, [])
    scenario, decks, pilots = bench._setup(tuple(bench.smoke.REAL_DECK_PATHS))
    records: list[dict[str, Any]] = []
    for seed in bench._seeds(args.seeds):
        sink: list[dict[str, Any]] = []
        runner = XmageFullGameRunner(command, private_card_repository=True)
        with pdr.recording(sink):
            result = runner.run(
                scenario=scenario.model_copy(update={"seed": seed}), decks=decks, pilots=pilots
            )
        print(f"seed {seed}: {len(sink)} decisions, semantic {result.semantic_transcript_sha256}")
        records += [
            {"seed": seed, "request": item["request"], "answer": item["answer"]} for item in sink
        ]
    rows = select_corpus(records)
    replayed = replay(rows)
    for row, outcome in zip(rows, replayed, strict=True):
        answer = outcome["answer"]
        row["stateless"] = answer is not None and answer_key(answer) == answer_key(row["answer"])
        row["class"] = row["request"]["decision_class"]
    header = {
        "corpus_version": CORPUS_VERSION,
        "pod": "real",
        "seeds": bench._seeds(args.seeds),
        "games_decisions": len(records),
        "jar_sha256": hashlib.sha256(args.jar.read_bytes()).hexdigest(),
        "classes": dict(sorted(Counter(r["class"] for r in rows).items())),
        "stateless": sum(1 for r in rows if r["stateless"]),
    }
    write_corpus(args.out, header, rows)
    print(json.dumps(header, indent=1))
    return 0


def diff(args: argparse.Namespace) -> int:
    header, rows = load_corpus(args.corpus)
    replayed = replay(rows)
    changed: Counter[str] = Counter()
    total: Counter[str] = Counter()
    errors = illegal = 0
    for row, outcome in zip(rows, replayed, strict=True):
        if outcome["answer"] is None:
            errors += 1
            continue
        if legality_problems(row["request"], outcome["answer"]):
            illegal += 1
        if not row["stateless"]:
            continue
        total[row["class"]] += 1
        if answer_key(outcome["answer"]) != answer_key(row["answer"]):
            changed[row["class"]] += 1
    print(f"corpus: {len(rows)} requests, {header['stateless']} replayable alone")
    print(f"raised: {errors}, illegal answers: {illegal}")
    for name in sorted(total):
        print(f"  {name:18s} {changed[name]:4d} of {total[name]:4d} answers changed")
    print(f"changed in total: {sum(changed.values())} of {sum(total.values())}")
    return 1 if errors or illegal else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="play real games and keep a stratified sample")
    rec.add_argument("--jar", type=Path, required=True)
    rec.add_argument("--seeds", default="1-2")
    rec.add_argument("--out", type=Path, default=DEFAULT_CORPUS)
    rec.set_defaults(func=record)
    dif = sub.add_parser("diff", help="answers the current pilot changes on the corpus")
    dif.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    dif.set_defaults(func=diff)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
