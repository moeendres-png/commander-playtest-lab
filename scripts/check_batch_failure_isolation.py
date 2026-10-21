"""Check that a game failing inside a batched bridge JVM leaves its neighbours' games unchanged.

Plays two batches on the real bridge, each with one game whose deck names a card XMage does
not have, and compares every good game with its single-game hash from a reference report of
``benchmark_xmage_full_games.py run`` (one game per JVM):

    python scripts/check_batch_failure_isolation.py --jar bridge.jar --reference single.json

Batch one is [seed 1, broken, seed 2], batch two is [broken, seed 3]. The broken game must
fail, the games before it must keep their hash (they rest on a graceful shutdown), and the
games after it run in a fresh JVM and must keep theirs. Exit 0 only if all of that holds.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_xmage_full_games as bench  # noqa: E402

from commander_lab.engine.rules.full_game import XmageFullGameRunner  # noqa: E402

BROKEN_CARD = "Zzyzx Nonexistent Card"
PLANS = {
    "good-bad-good": [(1, False), (5, True), (2, False)],
    "bad-good": [(5, True), (3, False)],
}


def reference_hashes(path: Path) -> dict[int, str]:
    games = json.loads(path.read_text(encoding="utf-8"))["games"]
    return {row["seed"]: row["semantic"] for row in games if row["status"] == "ok"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True, help="single-game run report")
    args = parser.parse_args(argv)
    expected = reference_hashes(args.reference)

    options = [*bench.fast_jvm_options(args.jar), f"-D{bench.GAMES_PER_JVM_PROPERTY}=3"]
    command = bench.bridge_command(args.jar, options)
    scenario, decks, pilots = bench._setup(tuple(bench.smoke.REAL_DECK_PATHS))
    broken = list(decks)
    mainboard = list(broken[1].mainboard)
    mainboard[10] = BROKEN_CARD
    broken[1] = broken[1].model_copy(update={"mainboard": tuple(mainboard), "card_printings": ()})

    def game(seed: int, bad: bool) -> tuple[Any, Any, Any]:
        return scenario.model_copy(update={"seed": seed}), tuple(broken) if bad else decks, pilots

    ok = True
    for label, plan in PLANS.items():
        runner = XmageFullGameRunner(command, private_card_repository=True)
        outcomes = runner.run_batch([game(seed, bad) for seed, bad in plan])
        for (seed, bad), outcome in zip(plan, outcomes, strict=True):
            if bad:
                passed = isinstance(outcome, Exception)
                print(f"{label} seed {seed} broken: {'failed as expected' if passed else 'PLAYED'}")
            else:
                passed = not isinstance(
                    outcome, Exception
                ) and outcome.semantic_transcript_sha256 == expected.get(seed)
                print(f"{label} seed {seed}: {'identical' if passed else f'DIFFERENT ({outcome})'}")
            ok = ok and passed
    print("FAILURE ISOLATION", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
