"""Play the 18 owner-collection coverage decks in real XMage full games (#747).

Every deck plays in at least one 4-, 5- and 6-player pod. Each pod is played twice with
the same seed (twin), and both runs must give the same semantic transcript SHA-256. A
game that aborts or a twin pair that diverges is a finding to file, not a flake.

    python scripts/run_collection_coverage_games.py --jar <bridge.jar> --out coverage.json
    python scripts/run_collection_coverage_games.py --jar <bridge.jar> --out c.json \\
        --sizes 4 --seeds 1-2 --workers 2
    python scripts/run_collection_coverage_games.py --jar <bridge.jar> --out c.json \\
        --games-per-jvm 5

With ``--games-per-jvm N`` (N > 1) a worker plays up to N games in one bridge process
(Owner decision 2026-10-15, batch runs only). The two twin runs of a pod then play in
different processes and in reverse order, so state left over from an earlier game would
show up as a diverged twin.

The result class is technical: these games test that the cards run in the engine, never
which deck is stronger. Local runs are measurements, not qualification evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_real_4p_full_game_smoke as smoke  # noqa: E402

from commander_lab.candidates.models import FutureXmageScenario  # noqa: E402
from commander_lab.engine.rules.full_game import (  # noqa: E402
    FullGameConformanceResult,
    XmageFullGameRunner,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402
from commander_lab.models import RulesDeckInput  # noqa: E402

COVERAGE_DIR = ROOT / "data/coverage_decks/collection"
SCENARIO_ID = "collection-coverage-technical-v1"
GAMES_PER_JVM_PROPERTY = "commanderlab.fullGame.gamesPerJvm"


def coverage_pods(deck_count: int, size: int) -> list[tuple[int, ...]]:
    """Consecutive pods over the sorted decks; the last one wraps to the first decks."""
    pods = []
    for start in range(0, deck_count, size):
        pods.append(tuple((start + offset) % deck_count for offset in range(size)))
    return pods


def _seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        low, _, high = part.partition("-")
        seeds.extend(range(int(low), int(high or low) + 1))
    return seeds


def _load_decks() -> list[RulesDeckInput]:
    decks = []
    for path in sorted(COVERAGE_DIR.glob("*.json")):
        deck, _ = smoke._ensure_deck_hash(load_rules_deck_snapshot(path))
        decks.append(deck)
    return decks


def _scenario(decks: tuple[RulesDeckInput, ...], seed: int) -> FutureXmageScenario:
    own = decks[0]
    assert own.deck_hash is not None
    return FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=len(decks),
        seat=1,
        scenario_id=SCENARIO_ID,
        seed=seed,
        xmage_commit=smoke.XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _row(outcome: FullGameConformanceResult | Exception) -> dict[str, Any]:
    if isinstance(outcome, Exception):  # a failed game is a finding, not a crash of the campaign
        return {"status": "failed", "error": f"{type(outcome).__name__}: {outcome}"[:600]}
    return {
        "status": "ok",
        "semantic": outcome.semantic_transcript_sha256,
        "decisions": outcome.decision_count,
        "winners": list(outcome.winner_seats),
    }


def _game(decks: tuple[RulesDeckInput, ...], seed: int) -> tuple[Any, ...]:
    pilots = tuple(smoke._binding(seat, deck) for seat, deck in enumerate(decks, start=1))
    return (_scenario(decks, seed), decks, pilots)


def _play_once(
    command: tuple[str, ...], decks: tuple[RulesDeckInput, ...], seed: int, max_decisions: int
) -> dict[str, Any]:
    scenario, _, pilots = _game(decks, seed)
    runner = XmageFullGameRunner(command, private_card_repository=True, max_decisions=max_decisions)
    started = time.monotonic()
    try:
        row = _row(runner.run(scenario=scenario, decks=decks, pilots=pilots))
    except Exception as exc:
        row = _row(exc)
    row["wall_s"] = round(time.monotonic() - started, 2)
    return row


def _play_batch(
    command: tuple[str, ...],
    jobs: list[tuple[tuple[RulesDeckInput, ...], int]],
    max_decisions: int,
) -> list[dict[str, Any]]:
    """Play ``jobs`` in one bridge process; the wall time is the batch average."""
    runner = XmageFullGameRunner(command, private_card_repository=True, max_decisions=max_decisions)
    started = time.monotonic()
    try:
        outcomes = runner.run_batch([_game(decks, seed) for decks, seed in jobs])
    except Exception as exc:
        outcomes = [exc] * len(jobs)
    wall = round((time.monotonic() - started) / max(1, len(jobs)), 2)
    return [_row(outcome) | {"wall_s": wall} for outcome in outcomes]


def play_pod(
    command: tuple[str, ...],
    decks: tuple[RulesDeckInput, ...],
    seed: int,
    max_decisions: int,
) -> dict[str, Any]:
    first = _play_once(command, decks, seed, max_decisions)
    second = _play_once(command, decks, seed, max_decisions)
    return _pod_row(decks, seed, first, second)


def play_pods_batched(
    command: tuple[str, ...],
    jobs: list[tuple[tuple[RulesDeckInput, ...], int]],
    max_decisions: int,
) -> list[dict[str, Any]]:
    """Twin runs in two processes, the second in reverse order."""
    firsts = _play_batch(command, jobs, max_decisions)
    seconds = _play_batch(command, jobs[::-1], max_decisions)[::-1]
    return [
        _pod_row(decks, seed, first, second)
        for (decks, seed), first, second in zip(jobs, firsts, seconds, strict=True)
    ]


def _pod_row(
    decks: tuple[RulesDeckInput, ...],
    seed: int,
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    if first["status"] == "ok" and second["status"] == "ok":
        twin = "identical" if first["semantic"] == second["semantic"] else "DIVERGED"
    else:
        twin = "not_compared"
    row = {
        "size": len(decks),
        "seed": seed,
        "deck_ids": [deck.deck_id for deck in decks],
        "twin": twin,
        "runs": [first, second],
    }
    print(
        json.dumps(
            {k: row[k] for k in ("size", "seed", "twin")}
            | {
                "status": [run["status"] for run in row["runs"]],
                "decks": [deck.deck_id.rsplit("/", 1)[-1] for deck in decks],
            }
        ),
        flush=True,
    )
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sizes", default="4,5,6")
    parser.add_argument("--seeds", type=_seeds, default=_seeds("1"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=50_000)
    parser.add_argument("--jvm-option", action="append", default=[])
    parser.add_argument("--games-per-jvm", type=int, default=1)
    args = parser.parse_args(argv)
    if args.games_per_jvm < 1:
        parser.error("--games-per-jvm must be positive")
    if args.games_per_jvm > 1:
        args.jvm_option.append(f"-D{GAMES_PER_JVM_PROPERTY}={args.games_per_jvm}")

    # The bridge runs in a private working directory (private card repository), so a
    # relative jar path would not resolve there (as in #776).
    command = ("java", *args.jvm_option, "-jar", str(args.jar.resolve()), "full-game")
    decks = _load_decks()
    jobs = [
        (tuple(decks[index] for index in pod), seed)
        for size in (int(value) for value in args.sizes.split(","))
        for pod in coverage_pods(len(decks), size)
        for seed in args.seeds
    ]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        if args.games_per_jvm == 1:
            pods = list(
                pool.map(lambda job: play_pod(command, job[0], job[1], args.max_decisions), jobs)
            )
        else:
            size = args.games_per_jvm
            chunks = [jobs[start : start + size] for start in range(0, len(jobs), size)]
            pods = [
                pod
                for chunk in pool.map(
                    lambda chunk: play_pods_batched(command, chunk, args.max_decisions), chunks
                )
                for pod in chunk
            ]
    games = [run for pod in pods for run in pod["runs"]]
    covered = sorted({deck_id for pod in pods for deck_id in pod["deck_ids"]})
    report = {
        "result_class": "TECHNICAL_CARD_COVERAGE",
        "xmage_commit": smoke.XMAGE_COMMIT,
        "jar": str(args.jar),
        "games_per_jvm": args.games_per_jvm,
        "decks_covered": len(covered),
        "pods": len(pods),
        "games": len(games),
        "games_ok": sum(run["status"] == "ok" for run in games),
        "twins_identical": sum(pod["twin"] == "identical" for pod in pods),
        "twins_diverged": sum(pod["twin"] == "DIVERGED" for pod in pods),
        "total_wall_s": round(time.monotonic() - started, 2),
        "results": pods,
    }
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(
        f"{report['games_ok']}/{report['games']} games ok, twins identical "
        f"{report['twins_identical']}/{report['pods']}, diverged {report['twins_diverged']}, "
        f"decks covered {report['decks_covered']}"
    )
    ok = report["games_ok"] == report["games"] and report["twins_diverged"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
