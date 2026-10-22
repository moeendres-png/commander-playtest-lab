"""Find where two games of one seed part ways, and whether the JVM's identity hashes cause it.

The same seed must give the same semantic hash. When it does not, the transcript hash only
says that something differs. This tool plays the pod twice, the second time with the JVM's
identity hash function replaced by another one, and prints the first request on which the
two games disagree:

    # one pod, two games (about a minute each): does the identity-hash order change it?
    python scripts/determinism_probe.py locate --jar bridge.jar --real-pod --seed 1
    python scripts/determinism_probe.py locate --jar bridge.jar --seed 22 \\
        --decks 2018_nature_s_vengeance 2018_built_from_scratch 2020_arcane_maelstrom \\
        2016_breed_lethality

    # keep a game's normalised requests to compare with a dump from another machine
    python scripts/determinism_probe.py play --jar bridge.jar --real-pod --seed 1 --out a.jsonl.gz
    python scripts/determinism_probe.py compare a.jsonl.gz b.jsonl.gz

Why the identity hash: ``Object.hashCode()`` of an object without its own ``hashCode`` (a
token, a permanent, an ability) is an identity hash. HotSpot draws it from a per-thread
xorshift whose start depends on how many threads the JVM created before (core count, JDK
major), so a ``HashSet``/``HashMap`` over such objects iterates in a machine-dependent order.
``-XX:hashCode=N`` (N = 0 Park-Miller, 1 address with randomness, 2 constant, 3 counter,
4 address) replaces the draw; a game that changes under it depends on iteration order.
The flag is experimental and slows the JVM; it is a probe, never a production option.

A game that is identical under modes 0 and 2 is not proven order-independent: a card that
never came into play cannot show. Run the probe over many pods and seeds
(``docs/performance/DETERMINISM_PROBE.md``); every hash difference of a perturbed sweep
(``precon_sweep_compare.py``) is a case for ``locate``.

``locate`` compares what the pilot was asked, not what the engine logged: requests and
answers with the ids that identify a game (UUIDs, 64-hex hashes, the ``[abc]`` fragments in
prompts, state references) replaced by counters in order of first appearance. A request that
differs only by a relabelled id is the same request. The verdict says how the games relate:

- ``IDENTICAL`` (exit 0): same requests, same answers.
- ``REQUESTS_DIFFER_ANSWERS_SAME`` (exit 2): the pilot saw something in another order or form
  but chose the same everywhere. The game is unchanged; a dependency on order is latent, and
  on a machine with another identity-hash sequence the same list could tip a tie-break.
- ``ANSWERS_DIFFER`` (exit 1): the games part at ``first_answer``; the cause is at or before
  the first request difference. A different semantic hash also exits 1.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

PRECON_DIR = ROOT / "data/decks/precons"
# Keys whose value is built from process-local ids; they carry no rules information.
IGNORED_KEYS = frozenset(
    {"decision_id", "private_actor_state_reference", "public_state_reference", "game_id"}
)
# A UUID, a 64-hex hash, or the 3-hex fragment of an object id that XMage prints in prompts.
_IDENTITY = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{64}|\[[0-9a-f]{3}\]"
)
HASH_MODES = {
    0: "Park-Miller generator",
    1: "object address with randomness",
    2: "constant",
    3: "counter",
    4: "object address",
}


def perturbation_options(mode: int) -> list[str]:
    """JVM options that replace the identity hash function by ``-XX:hashCode=mode``."""
    if mode not in HASH_MODES:
        raise ValueError(f"identity hash mode must be one of {sorted(HASH_MODES)}, got {mode}")
    return ["-XX:+UnlockExperimentalVMOptions", f"-XX:hashCode={mode}"]


# Lists the bridge fills from UUID- or identity-keyed collections, so their order differs from
# game to game without meaning anything. Sorted by the field that names an element before two
# games are compared; every other list keeps its order and a changed order is a difference.
KNOWN_ORDER_NOISE = {
    "commander_status": "name",
    "commander_damage_to_player": "player_id",
    "command": "name",
    "exile": "name",
}


def _strip(value: Any, *, sort_noise: bool = True) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in IGNORED_KEYS:
                continue
            item = _strip(item, sort_noise=sort_noise)
            field = KNOWN_ORDER_NOISE.get(key)
            if sort_noise and field and isinstance(item, list):
                item = sorted(
                    item,
                    key=lambda e: (
                        str(e.get(field)) if isinstance(e, dict) else "",
                        json.dumps(e, sort_keys=True),
                    ),
                )
            out[key] = item
        return out
    if isinstance(value, list):
        return [_strip(v, sort_noise=sort_noise) for v in value]
    return value


def normalise(value: Any, *, sort_noise: bool = True) -> Any:
    """``value`` without process-local ids: ids become ``u0``, ``u1`` ... by first appearance."""
    table: dict[str, str] = {}

    def label(match: re.Match[str]) -> str:
        text = match.group(0)
        if text.startswith("["):
            # Three hex digits of an object id: two objects of one game can share them by
            # chance, so a counter would tie them together in one run and not in the other.
            return "[#]"
        return table.setdefault(text, f"u{len(table)}")

    text = json.dumps(_strip(value, sort_noise=sort_noise), sort_keys=True)
    return json.loads(_IDENTITY.sub(label, text))


def _mask(text: str) -> str:
    return _IDENTITY.sub("<id>", text)


def answer_signature(request: dict[str, Any], answer: dict[str, Any]) -> list[str]:
    """What an answer chose, as content: the selected options themselves, ids masked.

    Two games that offered the same options in another order, or under other ids, and chose the
    same thing have the same signature.
    """
    options = {
        o.get("option_id"): o for o in request.get("legal_options") or [] if isinstance(o, dict)
    }
    parts = []
    for option_id in answer.get("selected_option_ids") or []:
        chosen = options.get(option_id, {"unlisted": option_id})
        parts.append(_mask(json.dumps(chosen, sort_keys=True)))
    for key in ("numeric_choice", "numeric_choices", "ordering"):
        if answer.get(key):
            parts.append(_mask(f"{key}={json.dumps(answer[key], sort_keys=True)}"))
    return parts


def rows_of(records: Iterable[dict[str, Any]], *, sort_noise: bool = True) -> list[dict[str, Any]]:
    """Rows ``{"i", "req", "ans", "sig"}`` of the ``{"request", "answer"}`` records of a game.

    Request and answer are normalised together, so an id means the same in both.
    """
    rows = []
    for index, record in enumerate(records):
        joint = normalise(
            {"req": record["request"], "ans": record["answer"]}, sort_noise=sort_noise
        )
        rows.append(
            {
                "i": index,
                "req": joint["req"],
                "ans": joint["ans"],
                "sig": answer_signature(record["request"], record["answer"]),
            }
        )
    return rows


def write_dump(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """A gzip file of one JSON row per line; the same rows are the same bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        path.open("wb") as handle,
        gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as raw,
    ):
        for row in rows:
            raw.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())


def read_dump(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def diff_paths(a: Any, b: Any, path: str = "") -> Iterator[tuple[str, Any, Any]]:
    """Every place where two JSON values differ, as ``(path, left, right)``."""
    if type(a) is not type(b):
        yield path, a, b
    elif isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                yield f"{path}.{key}", "<absent>", b[key]
            elif key not in b:
                yield f"{path}.{key}", a[key], "<absent>"
            else:
                yield from diff_paths(a[key], b[key], f"{path}.{key}")
    elif isinstance(a, list):
        if len(a) != len(b):
            yield f"{path}[len]", len(a), len(b)
        for index, (x, y) in enumerate(zip(a, b, strict=False)):
            yield from diff_paths(x, y, f"{path}[{index}]")
    elif a != b:
        yield path, a, b


def _differs(a: dict[str, Any], b: dict[str, Any], *, answers_only: bool) -> bool:
    if answers_only:
        return bool(a["sig"] != b["sig"])
    return bool(a["req"] != b["req"] or a["ans"] != b["ans"])


def first_difference(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
    *,
    answers_only: bool = False,
    max_paths: int = 25,
    context: int = 3,
) -> dict[str, Any] | None:
    """The first decision on which two games disagree, or None when they are the same game.

    By default a request or an answer that differs counts; with ``answers_only`` only a
    different choice (``sig``) does. Two games of different length that agree on the common
    prefix differ at the first decision only one of them has (``paths`` is empty).
    """
    for index, (a, b) in enumerate(zip(left, right, strict=False)):
        if not _differs(a, b, answers_only=answers_only):
            continue
        pilot_state = a["req"].get("pilot_state")
        turn = pilot_state.get("turn_number") if isinstance(pilot_state, dict) else None
        paths = []
        for path, va, vb in diff_paths(
            {"req": a["req"], "ans": a["ans"], "sig": a["sig"]},
            {"req": b["req"], "ans": b["ans"], "sig": b["sig"]},
        ):
            paths.append({"path": path, "left": va, "right": vb})
            if len(paths) >= max_paths:
                break
        return {
            "decision": index,
            "decision_class": a["req"].get("decision_class"),
            "turn": turn,
            "paths": paths,
            "context": [
                {
                    "decision": j,
                    "decision_class": left[j]["req"].get("decision_class"),
                    "selected": left[j]["sig"],
                }
                for j in range(max(0, index - context), index)
            ],
        }
    if len(left) != len(right):
        return {
            "decision": min(len(left), len(right)),
            "decision_class": None,
            "turn": None,
            "paths": [],
            "context": [],
        }
    return None


IDENTICAL = "IDENTICAL"
REQUESTS_DIFFER = "REQUESTS_DIFFER_ANSWERS_SAME"
ANSWERS_DIFFER = "ANSWERS_DIFFER"
_INDEX = re.compile(r"\[\d+\]")


def compare_games(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
    *,
    max_paths: int = 25,
    context: int = 3,
) -> dict[str, Any]:
    """How two games of one seed relate, and where they first part.

    ``verdict``: ``IDENTICAL``; ``REQUESTS_DIFFER_ANSWERS_SAME`` (the pilot was shown something
    in another order or form but chose the same everywhere: the game is unchanged, a
    dependency on order is latent); ``ANSWERS_DIFFER`` (the games part at ``first_answer``;
    a different length counts). ``patterns`` counts the kinds of request difference (list
    positions folded to ``[]``) over the decisions on which the requests differ.
    """
    common = min(len(left), len(right))
    requests_differing = answers_differing = 0
    patterns: Counter[str] = Counter()
    for a, b in zip(left, right, strict=False):
        if a["sig"] != b["sig"]:
            answers_differing += 1
        if a["req"] != b["req"]:
            requests_differing += 1
            seen = {
                _INDEX.sub("[]", path)
                for path, _, _ in _bounded(diff_paths(a["req"], b["req"]), 200)
            }
            patterns.update(seen)
    if len(left) != len(right) or answers_differing:
        verdict = ANSWERS_DIFFER
    elif requests_differing:
        verdict = REQUESTS_DIFFER
    else:
        verdict = IDENTICAL
    return {
        "verdict": verdict,
        "decisions": [len(left), len(right)],
        "compared": common,
        "requests_differing": requests_differing,
        "answers_differing": answers_differing,
        "patterns": patterns.most_common(10),
        "pattern_counts": dict(patterns),
        "first_request": first_difference(left, right, max_paths=max_paths, context=context),
        "first_answer": first_difference(
            left, right, answers_only=True, max_paths=max_paths, context=context
        ),
    }


def _bounded(items: Iterator[Any], limit: int) -> Iterator[Any]:
    for count, item in enumerate(items):
        if count >= limit:
            return
        yield item


def _describe(difference: dict[str, Any]) -> list[str]:
    lines = [
        f"  at decision {difference['decision']} "
        f"(class {difference['decision_class']}, turn {difference['turn']})"
    ]
    for item in difference["paths"]:
        lines.append(
            f"    {item['path']} | {json.dumps(item['left'])[:150]} | "
            f"{json.dumps(item['right'])[:150]}"
        )
    for item in difference["context"]:
        lines.append(
            f"    before: decision {item['decision']} {item['decision_class']} "
            f"{json.dumps(item['selected'])[:80]}"
        )
    return lines


def report(comparison: dict[str, Any], *, label_left: str, label_right: str) -> str:
    left, right = comparison["decisions"]
    lines = [
        f"{comparison['verdict']}: decisions {label_left} {left}, {label_right} {right}; "
        f"requests differing {comparison['requests_differing']} of {comparison['compared']}, "
        f"answers differing {comparison['answers_differing']}"
    ]
    if comparison["verdict"] == IDENTICAL:
        return lines[0]
    if comparison["patterns"]:
        lines.append("  kinds of request difference (decisions affected):")
        lines.extend(f"    {count:5d}  {pattern}" for pattern, count in comparison["patterns"])
    if comparison["first_request"]:
        lines.append("first request difference:")
        lines.extend(_describe(comparison["first_request"]))
    if comparison["first_answer"]:
        lines.append("first answer difference (the games part here):")
        lines.extend(_describe(comparison["first_answer"]))
    return "\n".join(lines)


def exit_code(comparison: dict[str, Any], *, hashes_equal: bool | None) -> int:
    """0 same game and same requests; 2 same game, requests differ; 1 the games differ."""
    if comparison["verdict"] == ANSWERS_DIFFER or hashes_equal is False:
        return 1
    return 0 if comparison["verdict"] == IDENTICAL else 2


def play_game(
    jar: Path,
    deck_paths: Sequence[Path],
    seed: int,
    jvm_options: Sequence[str],
    *,
    sort_noise: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """Play one game in its own bridge JVM; its semantic hash and normalised request rows."""
    import benchmark_xmage_full_games as bench
    import pilot_decision_report as pdr

    from commander_lab.engine.rules.full_game import XmageFullGameRunner

    scenario, decks, pilots = bench._setup(tuple(deck_paths))
    command = bench.bridge_command(jar, list(jvm_options))
    sink: list[dict[str, Any]] = []
    runner = XmageFullGameRunner(command, private_card_repository=True)
    with pdr.recording(sink):
        result = runner.run(
            scenario=scenario.model_copy(update={"seed": seed}),
            decks=decks,
            pilots=pilots,
        )
    return result.semantic_transcript_sha256, rows_of(sink, sort_noise=sort_noise)


def _deck_paths(args: argparse.Namespace) -> list[Path]:
    if args.real_pod:
        import benchmark_xmage_full_games as bench

        return list(bench.smoke.REAL_DECK_PATHS)
    if not args.decks or len(args.decks) != 4:
        raise SystemExit("give --real-pod or exactly four precon names with --decks")
    paths = [PRECON_DIR / f"{name}.json" for name in args.decks]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(f"unknown precon deck file(s): {missing}")
    return paths


def _fast(jar: Path) -> list[str]:
    import benchmark_xmage_full_games as bench

    return list(bench.fast_jvm_options(jar))


def _options(args: argparse.Namespace, extra: Sequence[str]) -> list[str]:
    base = _fast(args.jar) if args.fast else []
    return [*base, *extra]


def cmd_play(args: argparse.Namespace) -> int:
    semantic, rows = play_game(
        args.jar,
        _deck_paths(args),
        args.seed,
        _options(args, args.jvm_option),
        sort_noise=not args.raw_order,
    )
    write_dump(args.out, rows)
    print(f"semantic {semantic} decisions {len(rows)} -> {args.out}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    comparison = compare_games(
        read_dump(args.a), read_dump(args.b), max_paths=args.max, context=args.context
    )
    print(report(comparison, label_left=str(args.a), label_right=str(args.b)))
    return exit_code(comparison, hashes_equal=None)


def cmd_locate(args: argparse.Namespace) -> int:
    paths = _deck_paths(args)
    right_extra = [] if args.mode is None else perturbation_options(args.mode)
    sort_noise = not args.raw_order
    standard = _options(args, args.left_option)
    left_hash, left = play_game(args.jar, paths, args.seed, standard, sort_noise=sort_noise)
    print(f"standard         semantic {left_hash} decisions {len(left)}", flush=True)
    noise: set[str] | None = None
    if args.baseline:
        twin_hash, twin = play_game(args.jar, paths, args.seed, standard, sort_noise=sort_noise)
        print(f"standard again   semantic {twin_hash} decisions {len(twin)}", flush=True)
        baseline = compare_games(left, twin, max_paths=args.max, context=args.context)
        print(report(baseline, label_left="standard", label_right="standard again"))
        noise = set(baseline["pattern_counts"])
    label = "standard again" if args.mode is None else f"hashCode={args.mode}"
    shown = label if args.mode is None else f"{label} ({HASH_MODES[args.mode]})"
    for attempt in range(1, args.runs + 1):
        right_hash, right = play_game(
            args.jar,
            paths,
            args.seed,
            _options(args, [*right_extra, *args.jvm_option]),
            sort_noise=sort_noise,
        )
        print(f"{shown:16s} semantic {right_hash} decisions {len(right)}", flush=True)
        if args.save_dir:
            write_dump(args.save_dir / "standard.jsonl.gz", left)
            write_dump(args.save_dir / f"{label.replace(' ', '-')}-run{attempt}.jsonl.gz", right)
        comparison = compare_games(left, right, max_paths=args.max, context=args.context)
        hashes_equal = left_hash == right_hash
        if comparison["verdict"] != IDENTICAL or not hashes_equal or attempt == args.runs:
            break
    print(report(comparison, label_left="standard", label_right=label))
    if comparison["verdict"] != ANSWERS_DIFFER and not hashes_equal:
        print("the answers agree but the semantic hashes differ: look beyond the pilot")
    if comparison["verdict"] == ANSWERS_DIFFER and hashes_equal:
        print("the answers differ but the semantic hashes agree: the hash does not see this")
    if noise is not None and comparison["verdict"] == REQUESTS_DIFFER and hashes_equal:
        extra = sorted(set(comparison["pattern_counts"]) - noise)
        if not extra:
            print("every request difference also appears between two plain games: order noise")
            return 0
        print("request differences that two plain games do not show:")
        for pattern in extra:
            print(f"  {comparison['pattern_counts'][pattern]:5d}  {pattern}")
    return exit_code(comparison, hashes_equal=hashes_equal)


def _mode(text: str) -> int | None:
    if text == "none":
        return None
    refusal = argparse.ArgumentTypeError(f"mode must be none or one of {sorted(HASH_MODES)}")
    try:
        mode = int(text)
    except ValueError:
        raise refusal from None
    if mode not in HASH_MODES:
        raise refusal
    return mode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def game_arguments(p: argparse.ArgumentParser) -> None:
        p.add_argument("--jar", type=Path, required=True)
        p.add_argument("--seed", type=int, required=True)
        p.add_argument("--real-pod", action="store_true", help="the pod of the real-game smoke")
        p.add_argument("--decks", nargs="+", help="four precon names (data/decks/precons)")
        p.add_argument("--fast", action="store_true", help="serial GC + AppCDS archive")
        p.add_argument(
            "--raw-order",
            action="store_true",
            help="do not sort the lists that are known to come in a random order",
        )
        p.add_argument("--max", type=int, default=25, help="differing paths to print")
        p.add_argument("--context", type=int, default=3, help="earlier decisions to print")

    play = sub.add_parser("play", help="play one game, keep its normalised requests")
    game_arguments(play)
    play.add_argument("--out", type=Path, required=True)
    play.add_argument("--jvm-option", action="append", default=[], help="extra JVM option (=-form)")
    play.set_defaults(func=cmd_play)

    compare = sub.add_parser("compare", help="first difference of two dumps")
    compare.add_argument("a", type=Path)
    compare.add_argument("b", type=Path)
    compare.add_argument("--max", type=int, default=25)
    compare.add_argument("--context", type=int, default=3)
    compare.set_defaults(func=cmd_compare)

    locate = sub.add_parser("locate", help="standard game against a perturbed one")
    game_arguments(locate)
    locate.add_argument(
        "--mode",
        type=_mode,
        default=0,
        help="identity hash mode of the second game: 0-4, or none to repeat the standard "
        "game (a plain run that changes its hash is nondeterminism without any perturbation)",
    )
    locate.add_argument(
        "--runs",
        type=int,
        default=1,
        help="perturbed games to try (mode 0 draws from one generator all threads share, "
        "so a divergence can need more than one run); stops at the first difference",
    )
    locate.add_argument(
        "--baseline",
        action="store_true",
        help="also play the standard game twice: request differences between two plain games "
        "are order noise (UUID-keyed collections) and are not charged to the hash mode",
    )
    locate.add_argument("--left-option", action="append", default=[], help="JVM option, left game")
    locate.add_argument("--jvm-option", action="append", default=[], help="JVM option, right game")
    locate.add_argument("--save-dir", type=Path, help="keep both games' normalised requests")
    locate.set_defaults(func=cmd_locate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
