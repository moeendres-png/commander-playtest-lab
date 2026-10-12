#!/usr/bin/env python3
"""Replay finished XMage full games in the Structural simulator and compare (#733).

    python scripts/calibrate_structural_vs_xmage.py \\
        --games-dir <full-game batch games dir> [--games-dir ...] \\
        --deck data/coverage_decks/collection/agrus.json [--deck ...] \\
        --seeds-per-pod 40 --out structural_vs_xmage.json

Every deck that appears in a game needs a deck file (``--deck``; the repo's Rogshai,
Kaervek, Hosts of Mordor and Lorehold lists are added by default). Two profile sets are
compared when available: ``legacy`` (the profiles the optimizer uses today; only for decks
that have one) and ``facts`` (curated profiles plus pinned XMage card facts for every
other card, see ``engine/structural/xmage_calibration.py``).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from run_full_game_deck_comparison import load_deck  # noqa: E402

from commander_lab.engine.structural.card_facts import load_card_facts  # noqa: E402
from commander_lab.engine.structural.project import load_project_structural_decks  # noqa: E402
from commander_lab.engine.structural.simulator import (  # noqa: E402
    DEFAULT_TUNING,
    StructuralTuning,
)
from commander_lab.engine.structural.simulator_fidelity import StructuralSimulator  # noqa: E402
from commander_lab.engine.structural.xmage_calibration import (  # noqa: E402
    XmagePod,
    calibration_metrics,
    fact_deck_profile,
    known_card_profiles,
    load_xmage_pods,
    split_pods,
    structural_win_probabilities,
)
from commander_lab.models import StructuralDeckProfile  # noqa: E402
from commander_lab.repositories.opponents import CurrentOpponentRepository  # noqa: E402
from commander_lab.whole_deck.search_context import WholeDeckSearchContext  # noqa: E402

DEFAULT_DECKS = (
    "data/decks/rogshai_current.json",
    "data/decks/opponents/kaervek/current/deck.json",
    "data/opponents/hosts_of_mordor_precon.json",
    "data/opponents/lorehold_spirit_precon.json",
)


def _legacy_profiles(context: WholeDeckSearchContext) -> dict[str, StructuralDeckProfile]:
    profiles = dict(CurrentOpponentRepository(ROOT).profiles())
    rogshai = load_deck(ROOT / DEFAULT_DECKS[0])
    profiles[rogshai.deck_id] = context.materialize(tuple(rogshai.mainboard), label="legacy")
    return profiles


def _evaluate(
    pods: list[XmagePod],
    profiles: dict[str, StructuralDeckProfile],
    seeds: int,
    tuning: StructuralTuning = DEFAULT_TUNING,
) -> dict[str, Any]:
    usable = [pod for pod in pods if all(deck_id in profiles for deck_id in pod.deck_ids)]
    probabilities: list[list[float]] = []
    turns: list[float] = []
    aborts: list[float] = []
    factory = partial(StructuralSimulator, tuning=tuning)
    for pod in usable:
        row, abort_rate, mean_turns = structural_win_probabilities(
            pod,
            profiles,
            seeds=range(1, seeds + 1),
            simulator_factory=factory,
        )
        probabilities.append(row)
        turns.append(mean_turns)
        aborts.append(abort_rate)
    metrics = calibration_metrics(usable, probabilities, turns)
    metrics["structural_abort_rate"] = sum(aborts) / len(aborts) if aborts else None
    halves = split_pods(usable)
    index = {pod.game_key: position for position, pod in enumerate(usable)}
    metrics["halves"] = [
        {
            key: value
            for key, value in calibration_metrics(
                half,
                [probabilities[index[pod.game_key]] for pod in half],
                [turns[index[pod.game_key]] for pod in half],
            ).items()
            if key != "decks"
        }
        for half in halves
    ]
    return metrics


def _summary(name: str, metrics: dict[str, Any]) -> list[str]:
    def number(value: object) -> str:
        return f"{value:.3f}" if isinstance(value, float) else str(value)

    lines = [
        f"[{name}] pods {metrics['pods']} (decided {metrics['decided_pods']}), "
        f"spearman {number(metrics['spearman_deck_strength'])} over {metrics['decks_ranked']} "
        f"decks, log-loss {number(metrics['log_loss'])} vs uniform "
        f"{number(metrics['log_loss_uniform'])}, rounds xmage "
        f"{number(metrics['xmage_mean_rounds'])} / structural "
        f"{number(metrics['structural_mean_rounds'])}"
    ]
    for row in sorted(metrics["decks"], key=lambda item: -item["xmage_win_share"])[:12]:
        lines.append(
            f"  {row['deck_id']:<40} n={row['games']:<3} xmage {row['xmage_win_share']:.2f}"
            f"  structural {row['structural_win_share']:.2f}"
        )
    return lines


FIT_STEPS = (0.0, 0.5, 0.75, 1.0, 1.5, 2.0)


def _fit(
    pods: list[XmagePod],
    profiles: dict[str, StructuralDeckProfile],
    seeds: int,
    rounds: int,
) -> tuple[StructuralTuning, list[str]]:
    """Coordinate search of the damage scales on one half of the pods (log-loss)."""
    train, _held_out = split_pods(
        [pod for pod in pods if all(deck_id in profiles for deck_id in pod.deck_ids)]
    )

    def loss(tuning: StructuralTuning) -> float:
        value = _evaluate(train, profiles, seeds, tuning)["log_loss"]
        return float(value) if value is not None else math.inf

    best = DEFAULT_TUNING
    best_loss = loss(best)
    log = [f"fit start log-loss {best_loss:.4f} on {len(train)} pods"]
    for _round in range(rounds):
        improved = False
        for name in DEFAULT_TUNING.as_dict():
            base = getattr(DEFAULT_TUNING, name)
            for step in FIT_STEPS:
                candidate = replace(best, **{name: base * step})
                if candidate == best:
                    continue
                value = loss(candidate)
                if value < best_loss - 1e-4:
                    best, best_loss, improved = candidate, value, True
                    log.append(f"  {name}={base * step:.3f} -> {value:.4f}")
        if not improved:
            break
    return best, log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games-dir", type=Path, action="append", required=True)
    parser.add_argument("--deck", type=Path, action="append", default=[])
    parser.add_argument("--seeds-per-pod", type=int, default=40)
    parser.add_argument("--profiles", choices=("both", "facts", "legacy"), default="both")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--fit", action="store_true", help="fit the damage scales on half the pods (facts)"
    )
    parser.add_argument("--fit-seeds", type=int, default=12)
    parser.add_argument("--fit-rounds", type=int, default=2)
    args = parser.parse_args(argv)

    facts = load_card_facts(ROOT)
    if facts is None:
        print("data/cards/xmage_card_facts.json is missing", file=sys.stderr)
        return 2
    pods = list(load_xmage_pods(args.games_dir))
    if not pods:
        print("no completed XMage games found", file=sys.stderr)
        return 2
    context = WholeDeckSearchContext.from_project(ROOT)
    project_decks = load_project_structural_decks(ROOT, include_current_opponents=True)
    known = known_card_profiles(project_decks.values())
    known.update(
        {name: card.profile for name, card in context.cards.items() if card.semantic_known}
    )
    deck_files = [ROOT / path for path in DEFAULT_DECKS] + list(args.deck)
    fact_profiles: dict[str, StructuralDeckProfile] = {}
    reports = []
    for path in deck_files:
        deck = load_deck(path)
        profile, report = fact_deck_profile(
            deck, known=known, facts=facts, snapshot_hash=context.snapshot_hash
        )
        fact_profiles[deck.deck_id] = profile
        reports.append(report)
    result: dict[str, Any] = {
        "profile_reports": [
            {
                "deck_id": report.deck_id,
                "curated": report.curated,
                "inferred_from_facts": report.inferred_from_facts,
                "without_facts": report.without_facts,
            }
            for report in reports
        ]
    }
    lines: list[str] = []
    if args.profiles in ("both", "legacy"):
        result["legacy"] = _evaluate(pods, _legacy_profiles(context), args.seeds_per_pod)
        lines += _summary("legacy", result["legacy"])
    if args.profiles in ("both", "facts"):
        result["facts"] = _evaluate(pods, fact_profiles, args.seeds_per_pod)
        lines += _summary("facts", result["facts"])
    if args.fit:
        tuning, log = _fit(pods, fact_profiles, args.fit_seeds, args.fit_rounds)
        result["fitted_tuning"] = tuning.as_dict()
        result["facts_fitted"] = _evaluate(pods, fact_profiles, args.seeds_per_pod, tuning)
        lines += log
        lines += _summary("facts+fitted", result["facts_fitted"])
        lines.append(
            f"held-out half log-loss: default {result['facts']['halves'][1]['log_loss']:.4f}"
            if "facts" in result
            else "held-out half:"
        )
        lines.append(f"  fitted {result['facts_fitted']['halves'][1]['log_loss']:.4f}")
        lines.append(f"fitted tuning: {json.dumps(tuning.as_dict())}")
    missing = sum(len(report.without_facts) for report in reports)
    lines.append(f"cards without XMage facts across {len(reports)} decks: {missing}")
    print("\n".join(lines))
    if args.out:
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
