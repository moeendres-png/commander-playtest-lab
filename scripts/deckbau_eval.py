"""Run complete 4-player XMage games for an unregistered deckbau candidate.

Reuses the authoritative full-game setup and decision telemetry. The candidate
always occupies seat 1; only the engine determines legal play and game outcome.
This is an exploratory, fixed-seat evaluation, not a balanced seat-rotated claim.

    python scripts/deckbau_eval.py --deck data/decks/deckbau/example.json \\
      --pod precon --seeds 1-4 --out artifacts/deckbau/example-precon.json
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
import pilot_decision_report as decisions  # noqa: E402
import run_real_4p_full_game_smoke as smoke  # noqa: E402

from commander_lab.deck_readiness import check_deck, format_deck_report  # noqa: E402

BRIDGE_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"

# Deliberately fixed, repository-owned deck files. No collection inputs.
PODS: dict[str, tuple[Path, Path, Path]] = {
    "precon": (
        Path("data/decks/precons/2026_lorehold_spirit.json"),
        Path("data/decks/precons/2024_animated_army.json"),
        Path("data/decks/precons/2022_token_triumph.json"),
    ),
    "mixed": (
        Path("data/decks/opponents/kaervek/current/deck.json"),
        Path("data/decks/precons/2024_animated_army.json"),
        Path("data/decks/precons/2026_lorehold_spirit.json"),
    ),
    "optimized": (
        Path("data/decks/precons/2023_eldrazi_unbound.json"),
        Path("data/decks/opponents/kaervek/current/deck.json"),
        Path("data/opponents/hosts_of_mordor_precon.json"),
    ),
}


def seed_list(value: str) -> list[int]:
    """Use the existing game-seed parser but reject ambiguous/duplicate seeds."""
    seeds = bench._seeds(value)
    if not seeds or any(seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be distinct non-negative integers")
    return seeds


def build_setup(paths: tuple[Path, Path, Path, Path]) -> tuple[Any, Any, Any]:
    """Reuse the full-game bridge setup without permanently changing its smoke pod."""
    previous = smoke.REAL_DECK_PATHS
    try:
        smoke.REAL_DECK_PATHS = paths
        scenario, decks, pilots, _ = smoke.build_real_4p_setup(ROOT)
        return scenario, decks, pilots
    finally:
        smoke.REAL_DECK_PATHS = previous


def summarize_candidate(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Candidate-only metrics. Absent measurements are explicit, not estimated."""
    successful = [game for game in games if game.get("status") == "ok"]
    report: dict[str, Any] = {"games": games}
    seat_totals = decisions.totals_by_seat(report).get("1", {})
    seat_cards = decisions.aggregate_cards(report).get("by_seat", {}).get("1", {})
    wins = sum(
        1.0 / len(winners)
        for game in successful
        if (winners := game.get("winners") or []) and 1 in winners
    )
    own_turns = float(seat_totals.get("own_turns", 0))
    spells = float(seat_totals.get("spells_cast", 0))
    return {
        "status": "ok" if len(successful) == len(games) and games else "failed",
        "games_completed": len(successful),
        "games_failed": len(games) - len(successful),
        "wins_fractional": round(wins, 4),
        "win_rate_completed_games": round(wins / len(successful), 4) if successful else None,
        "candidate_seat": 1,
        "mean_rounds": decisions.totals(report).get("mean_rounds"),
        "mana_efficiency": {
            "status": "NOT_MEASURED",
            "spells_cast_per_own_turn_proxy": round(spells / own_turns, 3) if own_turns else None,
            "cancelled_mana_payments": int(seat_totals.get("mana_payments_cancelled", 0)),
        },
        "hand_residence_turns": {
            "status": "NOT_MEASURED",
            "reason": "The current observer records cast opportunities, not exact hand entry/exit turns.",
            "castable_but_uncast": seat_cards.get("rotting", []),
            "per_card_cast_opportunities": seat_cards.get("cards", []),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deck", type=Path, required=True, help="normalized deck snapshot JSON")
    parser.add_argument("--pod", choices=tuple(PODS), required=True)
    parser.add_argument("--seeds", default="1-4", help="e.g. 1-4 or 3,7,9")
    parser.add_argument("--out", type=Path, required=True, help="new JSON report path")
    parser.add_argument("--jar", type=Path, default=BRIDGE_JAR)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        seeds = seed_list(args.seeds)
        deck_path = args.deck.resolve(strict=True)
        paths = (deck_path, *PODS[args.pod])
        setup = build_setup(paths)
        _, decks, _ = setup
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    ids = [deck.deck_id for deck in decks]
    if len(set(ids)) != 4:
        parser.error("pod and candidate have duplicate deck IDs; choose another pod")
    for source, deck in zip(paths, decks, strict=True):
        readiness = check_deck(deck)
        print(format_deck_report(str(source), readiness))
        if not readiness.ready:
            print("Refusing full game: every deck must be READY.", file=sys.stderr)
            return 1

    plan = {
        "deck": str(deck_path),
        "deck_id": decks[0].deck_id,
        "pod": args.pod,
        "opponents": [str(path) for path in PODS[args.pod]],
        "seeds": seeds,
        "games_planned": len(seeds),
        "candidate_seat": 1,
        "rules_authority": "XMage",
        "evaluation_class": "exploratory_fixed_seat",
    }
    if args.plan_only:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if not args.jar.is_file():
        parser.error(f"bridge JAR not found: {args.jar}")
    if args.out.exists():
        parser.error(f"report already exists (not overwriting): {args.out}")

    command = bench.bridge_command(args.jar.resolve(), [])
    games = [decisions._play(command, args.pod, setup, seed) for seed in seeds]
    result = {"plan": plan, "summary": summarize_candidate(games), "games": games}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(f"Report: {args.out}")
    return 0 if result["summary"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
