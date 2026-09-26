from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial

from commander_lab.repositories.opponents import CurrentOpponentRecord


def _digest_int_5p(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def _five_player_assignment_score(
    order: tuple[str, str, str, str],
    *,
    seat_counts: Counter[tuple[str, int]],
    opponent_ids: tuple[str, ...],
    available_seats: tuple[int, int, int, int],
    seed: int,
    cycle: int,
    index: int,
) -> tuple[int, int, int]:
    projected = seat_counts.copy()
    for seat, deck_id in zip(available_seats, order, strict=True):
        projected[(deck_id, seat)] += 1
    values = [projected[(deck_id, seat)] for deck_id in opponent_ids for seat in range(1, 6)]
    return (
        max(values) - min(values),
        sum(value * value for value in values),
        _digest_int_5p(seed, cycle, index, order),
    )


@dataclass(frozen=True, slots=True)
class FivePlayerPodScenario:
    """Deterministic 5-player sensitivity scenario: one own deck plus four opponents."""

    scenario_id: str
    cycle_id: int
    opponent_deck_ids: tuple[str, str, str, str]
    own_seat: int
    opponent_seat_assignment: tuple[tuple[int, str], ...]
    seed: int
    opponent_registry_hash: str

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "cycle_id": self.cycle_id,
            "opponent_deck_ids": list(self.opponent_deck_ids),
            "own_seat": self.own_seat,
            "opponent_seat_assignment": {
                str(seat): deck_id for seat, deck_id in self.opponent_seat_assignment
            },
            "seed": self.seed,
            "coverage_metadata": {
                "sensitivity_pod_size": 5,
                "own_deck_count": 1,
                "opponent_count": 4,
                "evidence_axis": "five_player_sensitivity",
            },
            "source_opponent_registry_hash": self.opponent_registry_hash,
        }


class BalancedFivePlayerSensitivityScheduler:
    """Balanced deterministic 5P sensitivity scheduler over the current opponent pool.

    This scheduler is intentionally separate from ``BalancedPodScenarioScheduler`` so the
    primary 4-player contract cannot be widened accidentally. Frequencies are experimental
    equal-coverage frequencies, never observations of the local meta.
    """

    def __init__(
        self,
        opponent_records: Iterable[CurrentOpponentRecord],
        *,
        opponent_registry_hash: str,
    ) -> None:
        records = tuple(opponent_records)
        ids = tuple(sorted(record.deck_id for record in records))
        if len(ids) < 4:
            raise ValueError("balanced 5P sensitivity scheduling requires at least four opponents")
        if len(ids) != len(set(ids)):
            raise ValueError("current opponent repository contains duplicate deck ids")
        self.opponent_ids = ids
        self.registry_hash = opponent_registry_hash
        self.evidence = {
            record.deck_id: tuple(kind.value for kind in record.evidence_kinds)
            for record in records
        }
        self._all_combinations = tuple(itertools.combinations(ids, 4))

    @property
    def combinations_per_cycle(self) -> int:
        return len(self._all_combinations)

    def _balanced_subset(
        self,
        combinations: tuple[tuple[str, str, str, str], ...],
        count: int,
        *,
        seed: int,
        cycle: int,
    ) -> list[tuple[str, str, str, str]]:
        remaining = set(combinations)
        selected: list[tuple[str, str, str, str]] = []
        opponent_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()
        pair_universe = tuple(itertools.combinations(self.opponent_ids, 2))
        while remaining and len(selected) < count:
            scored: list[tuple[tuple[int, int, int, int], tuple[str, str, str, str]]] = []
            for combo in remaining:
                projected_opponents = opponent_counts.copy()
                projected_opponents.update(combo)
                projected_pairs = pair_counts.copy()
                projected_pairs.update(itertools.combinations(combo, 2))
                exposure_values = [projected_opponents[deck_id] for deck_id in self.opponent_ids]
                pair_values = [projected_pairs[pair] for pair in pair_universe]
                score = (
                    max(exposure_values) - min(exposure_values),
                    sum(value * value for value in exposure_values),
                    max(pair_values) - min(pair_values),
                    _digest_int_5p(seed, cycle, combo),
                )
                scored.append((score, combo))
            _, chosen = min(scored, key=lambda row: row[0])
            selected.append(chosen)
            opponent_counts.update(chosen)
            pair_counts.update(itertools.combinations(chosen, 2))
            remaining.remove(chosen)
        return selected

    def schedule(self, game_count: int, *, seed: int) -> tuple[FivePlayerPodScenario, ...]:
        if game_count < 1:
            raise ValueError("game_count must be positive")
        per_cycle = self.combinations_per_cycle
        full_cycles, remainder = divmod(game_count, per_cycle)
        combos_by_cycle: list[tuple[int, tuple[str, str, str, str]]] = []
        for cycle in range(full_cycles):
            ordered = sorted(
                self._all_combinations,
                key=lambda combo: _digest_int_5p(seed, cycle, combo),
            )
            combos_by_cycle.extend((cycle, combo) for combo in ordered)
        if remainder:
            cycle = full_cycles
            partial_combos = self._balanced_subset(
                self._all_combinations, remainder, seed=seed, cycle=cycle
            )
            combos_by_cycle.extend((cycle, combo) for combo in partial_combos)

        seat_counts: Counter[tuple[str, int]] = Counter()
        scenarios: list[FivePlayerPodScenario] = []
        own_offset = _digest_int_5p(seed, "five-player-own-seat-offset") % 5
        for index, (cycle, combo) in enumerate(combos_by_cycle):
            own_seat = ((index + own_offset) % 5) + 1
            seat_slots = [seat for seat in range(1, 6) if seat != own_seat]
            available_seats = (seat_slots[0], seat_slots[1], seat_slots[2], seat_slots[3])
            permutations: tuple[tuple[str, str, str, str], ...] = tuple(
                (order[0], order[1], order[2], order[3]) for order in itertools.permutations(combo)
            )
            score_order = partial(
                _five_player_assignment_score,
                seat_counts=seat_counts,
                opponent_ids=self.opponent_ids,
                available_seats=available_seats,
                seed=seed,
                cycle=cycle,
                index=index,
            )
            order = min(permutations, key=score_order)
            assignment = tuple(zip(available_seats, order, strict=True))
            for seat, deck_id in assignment:
                seat_counts[(deck_id, seat)] += 1
            scenario_seed = _digest_int_5p(seed, "five-player-game", cycle, index, combo) % (
                2**31 - 1
            )
            scenario_id = hashlib.sha256(
                f"{self.registry_hash}|5p|{cycle}|{index}|{combo}|{own_seat}|{scenario_seed}".encode()
            ).hexdigest()[:20]
            scenarios.append(
                FivePlayerPodScenario(
                    scenario_id=f"balanced5p-{scenario_id}",
                    cycle_id=cycle,
                    opponent_deck_ids=combo,
                    own_seat=own_seat,
                    opponent_seat_assignment=assignment,
                    seed=scenario_seed,
                    opponent_registry_hash=self.registry_hash,
                )
            )
        return tuple(scenarios)

    def coverage_report(self, scenarios: Iterable[FivePlayerPodScenario]) -> dict[str, object]:
        rows = tuple(scenarios)
        opponent_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()
        quadruple_counts: Counter[tuple[str, str, str, str]] = Counter()
        seat_counts: Counter[int] = Counter()
        opponent_seat_counts: Counter[tuple[str, int]] = Counter()
        for scenario in rows:
            opponent_counts.update(scenario.opponent_deck_ids)
            pair_counts.update(itertools.combinations(sorted(scenario.opponent_deck_ids), 2))
            sorted_ids = sorted(scenario.opponent_deck_ids)
            group = (sorted_ids[0], sorted_ids[1], sorted_ids[2], sorted_ids[3])
            quadruple_counts[group] += 1
            seat_counts[scenario.own_seat] += 1
            opponent_seat_counts.update(
                (deck_id, seat) for seat, deck_id in scenario.opponent_seat_assignment
            )
        full_cycles, remainder = divmod(len(rows), self.combinations_per_cycle)
        exposure = [opponent_counts[deck_id] for deck_id in self.opponent_ids]
        return {
            "available_opponents": list(self.opponent_ids),
            "used_opponents": sorted(
                deck_id for deck_id, count in opponent_counts.items() if count
            ),
            "games": len(rows),
            "pod_size": 5,
            "evidence_axis": "five_player_sensitivity",
            "games_per_opponent": dict(sorted(opponent_counts.items())),
            "games_per_opponent_pair": {
                "|".join(pair): count for pair, count in sorted(pair_counts.items())
            },
            "games_per_opponent_quadruple": {
                "|".join(group): count for group, count in sorted(quadruple_counts.items())
            },
            "rogshai_seat_counts": {str(seat): seat_counts[seat] for seat in range(1, 6)},
            "opponent_seat_counts": {
                f"{deck_id}|seat{seat}": opponent_seat_counts[(deck_id, seat)]
                for deck_id in self.opponent_ids
                for seat in range(1, 6)
            },
            "complete_coverage_cycles": full_cycles,
            "incomplete_remainder_games": remainder,
            "combinations_per_full_cycle": self.combinations_per_cycle,
            "opponent_exposure_imbalance": max(exposure) - min(exposure) if exposure else 0,
            "opponent_evidence_classes": {
                deck_id: list(self.evidence.get(deck_id, ("unknown",)))
                for deck_id in self.opponent_ids
            },
            "frequency_interpretation": "experimental_equal_coverage_not_real_meta_frequency",
            "source_opponent_registry_hash": self.registry_hash,
            "primary_evidence": False,
        }
