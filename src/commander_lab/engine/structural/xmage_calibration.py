"""How well does the Structural model reproduce XMage full games? (#733)

The Structural simulator ranks deck changes cheaply; XMage decides real games. This module
replays the pods of finished XMage games in the Structural simulator and compares the two
on the same seats: per-deck win share, the rank correlation of deck strength, and the
log-loss of the XMage winner under the Structural win probabilities.

Deck profiles for the replay come from ``fact_deck_profile``: a card keeps its curated
Structural profile when the project has one, and every other card is inferred from the
pinned XMage card facts instead of being an inert filler. ``legacy`` profiles (what the
optimizer uses today) can be passed in to measure the gap.
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.models import (
    PilotConfig,
    RulesDeckInput,
    StructuralAbortLimits,
    StructuralCardProfile,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.storage import sha256_value

from .card_facts import CardFactsCatalog, apply_card_facts, commander_stats, profile_from_facts
from .fact_fidelity import simple_color_requirements

_PLACEHOLDER_MARK = " role card "


@dataclass(frozen=True)
class XmagePod:
    """One finished XMage game: deck ids in seat order and the winning seat (0-based)."""

    game_key: str
    seed: int
    deck_ids: tuple[str, ...]
    winner_seat: int | None
    turn_number: int


@dataclass
class DeckProfileReport:
    deck_id: str
    curated: int = 0
    inferred_from_facts: int = 0
    without_facts: list[str] = field(default_factory=list)


def load_xmage_pods(directories: Iterable[Path]) -> tuple[XmagePod, ...]:
    """Completed games from full-game batch directories, one pod per game record."""
    pods: list[XmagePod] = []
    for directory in directories:
        for path in sorted(Path(directory).glob("*.json")):
            pod = pod_from_record(json.loads(path.read_text(encoding="utf-8")))
            if pod is not None:
                pods.append(pod)
    return tuple(pods)


def load_pod_summary(path: Path) -> tuple[XmagePod, ...]:
    """Pods from a committed summary (``data/calibration/xmage_reference_pods_*.json``).

    The summary names a game by ``run_sha256``: the secret scan reads a 64-hex value under
    a field name containing "key" as a credential.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(
        XmagePod(
            game_key=str(row["run_sha256"]),
            seed=int(row["seed"]),
            deck_ids=tuple(str(deck_id) for deck_id in row["deck_ids"]),
            winner_seat=None if row["winner_seat"] is None else int(row["winner_seat"]),
            turn_number=int(row["turn_number"]),
        )
        for row in payload["pods"]
    )


def pod_from_record(record: Mapping[str, Any]) -> XmagePod | None:
    if record.get("status") != "completed":
        return None
    result = record.get("result") or {}
    payload = result.get("result_payload") or {}
    scenario = result.get("scenario") or {}
    if not payload.get("terminal"):
        return None
    seat = int(scenario["seat"]) - 1
    deck_ids = [str(deck_id) for deck_id in scenario["opponent_deck_ids"]]
    deck_ids.insert(seat, str(scenario["candidate_id"]))
    winners = [int(row["seat"]) for row in payload.get("outcomes", []) if row.get("won")]
    return XmagePod(
        game_key=str(record.get("run_key", record.get("case_id", ""))),
        seed=int(scenario["seed"]),
        deck_ids=tuple(deck_ids),
        winner_seat=winners[0] if len(winners) == 1 else None,
        turn_number=int(payload.get("turn_number", 0)),
    )


def known_card_profiles(decks: Iterable[StructuralDeckProfile]) -> dict[str, StructuralCardProfile]:
    """Curated card profiles found in project decks (placeholder role cards excluded)."""
    known: dict[str, StructuralCardProfile] = {}
    for deck in decks:
        for card in deck.cards:
            if _PLACEHOLDER_MARK not in card.oracle_name:
                known.setdefault(card.oracle_name, card)
    return known


def fact_deck_profile(
    deck: RulesDeckInput,
    *,
    known: Mapping[str, StructuralCardProfile],
    facts: CardFactsCatalog,
    snapshot_hash: str,
) -> tuple[StructuralDeckProfile, DeckProfileReport]:
    """A Structural profile for any deck: curated profiles first, XMage facts for the rest."""
    report = DeckProfileReport(deck_id=deck.deck_id)
    cards: list[StructuralCardProfile] = []
    for name in (*deck.mainboard, *deck.commander_names):
        card_facts = facts.get(name)
        card_profile = known.get(name)
        if card_profile is not None:
            report.curated += 1
        elif card_facts is not None:
            card_profile = profile_from_facts(name, card_facts)
            report.inferred_from_facts += 1
        else:
            report.without_facts.append(name)
            card_profile = StructuralCardProfile(oracle_name=name, roles=frozenset())
        if card_facts is not None:
            card_profile = apply_card_facts(card_profile, card_facts)
            if name in deck.commander_names and not card_profile.color_requirements:
                # A curated profile taken from a deck where the card was not the commander can
                # carry no colour cost; the castability of a commander needs its coloured pips.
                pips = simple_color_requirements(card_facts.mana_cost)
                if pips:
                    card_profile = card_profile.model_copy(update={"color_requirements": pips})
        if card_profile.oracle_name != name:
            card_profile = card_profile.model_copy(update={"oracle_name": name})
        cards.append(card_profile)
    costs: dict[str, float] = {}
    powers: dict[str, float] = {}
    for name in deck.commander_names:
        stats = commander_stats(name, facts)
        costs[name] = stats[0] if stats is not None else 4.0
        powers[name] = stats[1] if stats is not None else 2.0
    deck_profile = StructuralDeckProfile(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash or sha256_value([*deck.commander_names, *deck.mainboard]),
        commander_names=tuple(deck.commander_names),
        cards=tuple(cards),
        commander_base_costs=costs,
        commander_base_power=powers,
        commander_strategy="generic",
        data_snapshot_hash=snapshot_hash,
    )
    return deck_profile, report


SimulatorFactory = Callable[[dict[str, StructuralDeckProfile]], Any]


def structural_win_probabilities(
    pod: XmagePod,
    profiles: Mapping[str, StructuralDeckProfile],
    *,
    seeds: Sequence[int],
    simulator_factory: SimulatorFactory,
    max_turns: int = 30,
) -> tuple[list[float], float, float]:
    """Per-seat Structural win share over ``seeds``, the abort rate and mean turns."""
    seat_ids = [f"s{seat}" for seat in range(len(pod.deck_ids))]
    decks = {
        seat_id: profiles[deck_id].model_copy(update={"deck_id": seat_id})
        for seat_id, deck_id in zip(seat_ids, pod.deck_ids, strict=True)
    }
    wins = [0.0] * len(seat_ids)
    aborted = 0
    turns: list[float] = []
    for seed in seeds:
        result = simulator_factory(decks).simulate(
            StructuralMatchConfig(
                match_id=f"calibration-{pod.game_key[:12]}-{seed}",
                deck_ids=tuple(seat_ids),
                seed=seed,
                starting_player_seat=0,
                limits=StructuralAbortLimits(max_turns=max_turns),
                pilot_configs=(PilotConfig(),) * len(seat_ids),
            ),
            run_id="structural-xmage-calibration",
        )
        aborted += bool(result.aborted)
        turns.append(float(result.turns))
        winners = [int(player_id[1:]) - 1 for player_id in result.winner_ids]
        for seat in winners:
            wins[seat] += 1.0 / len(winners)
    return [value / len(seeds) for value in wins], aborted / len(seeds), fmean(turns)


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None

    def ranks(values: Sequence[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda index: values[index])
        result = [0.0] * len(values)
        start = 0
        while start < len(order):
            end = start
            while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
                end += 1
            for position in range(start, end + 1):
                result[order[position]] = (start + end) / 2 + 1
            start = end + 1
        return result

    a, b = ranks(left), ranks(right)
    mean_a, mean_b = fmean(a), fmean(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    denominator = math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))
    return numerator / denominator if denominator else None


def calibration_metrics(
    pods: Sequence[XmagePod],
    probabilities: Sequence[Sequence[float]],
    structural_turns: Sequence[float],
    *,
    min_games: int = 5,
) -> dict[str, Any]:
    """Compare XMage outcomes with Structural win probabilities pod by pod."""
    xmage_wins: Counter[str] = Counter()
    structural_wins: defaultdict[str, float] = defaultdict(float)
    games: Counter[str] = Counter()
    losses: list[float] = []
    for pod, row in zip(pods, probabilities, strict=True):
        for seat, deck_id in enumerate(pod.deck_ids):
            games[deck_id] += 1
            structural_wins[deck_id] += row[seat]
            if pod.winner_seat == seat:
                xmage_wins[deck_id] += 1
        if pod.winner_seat is not None:
            losses.append(-math.log(max(0.01, row[pod.winner_seat])))
    decks = sorted(games)
    rows: list[dict[str, Any]] = [
        {
            "deck_id": deck_id,
            "games": games[deck_id],
            "xmage_win_share": xmage_wins[deck_id] / games[deck_id],
            "structural_win_share": structural_wins[deck_id] / games[deck_id],
        }
        for deck_id in decks
    ]
    ranked = [row for row in rows if row["games"] >= min_games]
    rho = spearman(
        [row["xmage_win_share"] for row in ranked],
        [row["structural_win_share"] for row in ranked],
    )
    players = [len(pod.deck_ids) for pod in pods]
    return {
        "pods": len(pods),
        "decided_pods": len(losses),
        "spearman_deck_strength": rho,
        "decks_ranked": len(ranked),
        "log_loss": fmean(losses) if losses else None,
        "log_loss_uniform": fmean(-math.log(1 / n) for n in players) if players else None,
        "xmage_mean_rounds": fmean(pod.turn_number / len(pod.deck_ids) for pod in pods)
        if pods
        else None,
        "structural_mean_rounds": fmean(structural_turns) if structural_turns else None,
        "decks": rows,
    }


def split_pods(pods: Sequence[XmagePod], *, seed: int = 0) -> tuple[list[XmagePod], ...]:
    """A fixed half/half split for held-out checks of anything fitted on one half."""
    order = sorted(pods, key=lambda pod: pod.game_key)
    random.Random(seed).shuffle(order)
    half = len(order) // 2
    return order[:half], order[half:]


__all__ = [
    "DeckProfileReport",
    "XmagePod",
    "calibration_metrics",
    "fact_deck_profile",
    "known_card_profiles",
    "load_pod_summary",
    "load_xmage_pods",
    "pod_from_record",
    "spearman",
    "split_pods",
    "structural_win_probabilities",
]
