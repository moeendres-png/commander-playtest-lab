"""Play optimizer-v2's routed hypotheses as paired XMage full games (#733).

Optimizer-v2 routes candidates whose changed cards need tactical or external
rules evidence to hypothesis queues (``ROUTED_HYPOTHESIS_QUEUES.json``). This
command takes the top hypotheses of an optimizer run, rebuilds each exact deck
from the candidate ledger, and plays it against the control deck on the same
seeds, seats and opponents. XMage decides every game.

    export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
    python scripts/run_optimizer_v2_full_game_route.py \\
        --run-dir <optimizer-v2 run directory> --seeds 1-10 --limit 3

The report (``FULL_GAME_ROUTE_REPORT.json``) is exploratory full-game evidence
per hypothesis. It does not make a hypothesis Structural-confirmatory and does
not change any deck.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from run_full_game_deck_comparison import (
    _available_memory_gb,
    _summary_lines,
    default_workers,
    load_deck,
    parse_seeds,
)

from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import XmageFullGameBatchRunner
from commander_lab.engine.rules.full_game_comparison import (
    aggregate_comparison,
    plan_comparison_cases,
)
from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.whole_deck.optimizer_v2_full_game import (
    OPTIONAL_ROUTE_GROUPS,
    ROUTE_GROUPS,
    FullGameRouteError,
    build_route_spec,
    route_report,
    select_route_hypotheses,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTROL = Path("data/decks/rogshai_current.json")
DEFAULT_OPPONENTS = (
    Path("data/decks/opponents/kaervek/current/deck.json"),
    Path("data/opponents/hosts_of_mordor_precon.json"),
    Path("data/opponents/lorehold_spirit_precon.json"),
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FullGameRouteError(f"{path.name} is not a JSON object")
    return payload


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--control", type=Path, default=DEFAULT_CONTROL)
    parser.add_argument("--opponent", type=Path, action="append", default=None)
    parser.add_argument("--queue", action="append", choices=OPTIONAL_ROUTE_GROUPS, default=None)
    parser.add_argument("--limit", type=int, default=3, help="hypotheses to play")
    parser.add_argument("--seeds", required=True, help="e.g. 1-10 or 3,7,9")
    parser.add_argument("--no-rotate", action="store_true", help="test seat 1 only")
    parser.add_argument("--out", type=Path, default=None, help="default: <run-dir>/full-game-route")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--parallelism", choices=("thread", "process"), default="thread")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-decisions", type=int, default=50_000)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv)

    queues_used = tuple(args.queue or ROUTE_GROUPS)
    control = load_deck(_resolve(args.control))
    opponents = tuple(load_deck(_resolve(path)) for path in (args.opponent or DEFAULT_OPPONENTS))
    try:
        ledger = _load_json(args.run_dir / "ALL_CANDIDATE_LEDGER.json")
        queues = _load_json(args.run_dir / "ROUTED_HYPOTHESIS_QUEUES.json")
        hypotheses = select_route_hypotheses(
            queues, ledger, control, groups=queues_used, limit=args.limit
        )
        spec = build_route_spec(
            control,
            hypotheses,
            opponents,
            seeds=parse_seeds(args.seeds),
            xmage_commit=canonical_xmage_engine_pin(),
            rotate_seats=not args.no_rotate,
        )
    except (OSError, FullGameRouteError) as exc:
        print(f"cannot build the full-game route: {exc}", file=sys.stderr)
        return 2
    cases = plan_comparison_cases(spec)
    workers = args.workers or default_workers(memory_gb=_available_memory_gb())
    print(
        f"{len(hypotheses)} hypotheses from {', '.join(queues_used)}; {len(cases)} games, "
        f"{spec.player_count} players, {workers} workers"
    )
    for hypothesis in hypotheses:
        print(
            f"  {hypothesis.deck.deck_id}: -{', '.join(hypothesis.removed_cards) or 'nothing'} "
            f"+{', '.join(hypothesis.added_cards) or 'nothing'}"
        )
    if args.plan_only:
        return 0

    command = XmageFullGameRunner.command_from_environment()
    if command is None:
        print("set COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD first", file=sys.stderr)
        return 2
    out = args.out or args.run_dir / "full-game-route"
    runner = XmageFullGameRunner(
        command,
        max_decisions=args.max_decisions,
        request_timeout_seconds=args.request_timeout,
    )
    batch = XmageFullGameBatchRunner(runner, out / "games").run(
        cases, retry_failed=args.retry_failed, workers=workers, parallelism=args.parallelism
    )
    comparison = aggregate_comparison(spec, batch)
    report = route_report(
        control=control,
        hypotheses=hypotheses,
        comparison=comparison,
        candidate_ledger_hash=str(ledger.get("ledger_hash")),
        queues=queues_used,
    )
    payload = report.model_dump(mode="json")
    out.mkdir(parents=True, exist_ok=True)
    (out / "FULL_GAME_ROUTE_REPORT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for line in _summary_lines(payload["comparison"]):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
