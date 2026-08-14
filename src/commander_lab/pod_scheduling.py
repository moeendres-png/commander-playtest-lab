from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial

from commander_lab.repositories.opponents import CurrentOpponentRecord


def _digest_int(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def _opponent_assignment_score(
    order: tuple[str, str, str],
    *,
    seat_counts: Counter[tuple[str, int]],
    opponent_ids: tuple[str, ...],
    available_seats: tuple[int, int, int],
    seed: int,
    cycle: int,
    index: int,
) -> tuple[int, int, int]:
    projected = seat_counts.copy()
    for seat, deck_id in zip(available_seats, order, strict=True):
        projected[(deck_id, seat)] += 1
    values = [
        projected[(deck_id, seat)]
        for deck_id in opponent_ids
        for seat in range(1, 5)
    ]
    return (
        max(values) - min(values),
        sum(value * value for value in values),
        _digest_int(seed, cycle, index, order),
    )


@dataclass(frozen=True, slots=True)
class PodScenario:
    scenario_id: str
    cycle_id: int
    opponent_deck_ids: tuple[str, str, str]
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
            "coverage_metadata": {"primary_pod_size": 4, "own_deck_count": 1},
            "source_opponent_registry_hash": self.opponent_registry_hash,
        }


class BalancedPodScenarioScheduler:
    """Deterministic balanced experimental scheduler for primary 4-player Commander pods."""

    def __init__(
        self,
        opponent_records: Iterable[CurrentOpponentRecord],
        *,
        opponent_registry_hash: str,
    ) -> None:
        records = tuple(opponent_records)
        ids = tuple(sorted(record.deck_id for record in records))
        if len(ids) < 3:
            raise ValueError("balanced 4P scheduling requires at least three current opponents")
        if len(ids) != len(set(ids)):
            raise ValueError("current opponent repository contains duplicate deck ids")
        self.opponent_ids = ids
        self.registry_hash = opponent_registry_hash
        self.evidence = {
            record.deck_id: tuple(kind.value for kind in record.evidence_kinds)
            for record in records
        }
        self._all_combinations = tuple(itertools.combinations(ids, 3))

    @property
    def combinations_per_cycle(self) -> int:
        return len(self._all_combinations)

    def _balanced_subset(
        self, combinations: tuple[tuple[str, str, str], ...], count: int, *, seed: int, cycle: int
    ) -> list[tuple[str, str, str]]:
        remaining = set(combinations)
        selected: list[tuple[str, str, str]] = []
        opponent_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()
        while remaining and len(selected) < count:
            scored: list[tuple[tuple[int, int, int, int], tuple[str, str, str]]] = []
            for combo in remaining:
                o = opponent_counts.copy()
                o.update(combo)
                p = pair_counts.copy()
                p.update(itertools.combinations(combo, 2))
                exposure_values = [o[deck_id] for deck_id in self.opponent_ids]
                pair_universe = tuple(itertools.combinations(self.opponent_ids, 2))
                pair_values = [p[pair] for pair in pair_universe]
                score = (
                    max(exposure_values) - min(exposure_values),
                    sum(value * value for value in exposure_values),
                    max(pair_values) - min(pair_values),
                    _digest_int(seed, cycle, combo),
                )
                scored.append((score, combo))
            _, chosen = min(scored, key=lambda row: row[0])
            selected.append(chosen)
            opponent_counts.update(chosen)
            pair_counts.update(itertools.combinations(chosen, 2))
            remaining.remove(chosen)
        return selected

    def schedule(self, game_count: int, *, seed: int) -> tuple[PodScenario, ...]:
        if game_count < 1:
            raise ValueError("game_count must be positive")
        per_cycle = self.combinations_per_cycle
        full_cycles, remainder = divmod(game_count, per_cycle)
        combos_by_cycle: list[tuple[int, tuple[str, str, str]]] = []
        for cycle in range(full_cycles):
            ordered = sorted(
                self._all_combinations,
                key=lambda combo: _digest_int(seed, cycle, combo),
            )
            combos_by_cycle.extend((cycle, combo) for combo in ordered)
        if remainder:
            cycle = full_cycles
            partial_combos = self._balanced_subset(
                self._all_combinations, remainder, seed=seed, cycle=cycle
            )
            combos_by_cycle.extend((cycle, combo) for combo in partial_combos)

        seat_counts: Counter[tuple[str, int]] = Counter()
        scenarios: list[PodScenario] = []
        own_offset = _digest_int(seed, "own-seat-offset") % 4
        for index, (cycle, combo) in enumerate(combos_by_cycle):
            own_seat = ((index + own_offset) % 4) + 1
            seat_slots = [seat for seat in range(1, 5) if seat != own_seat]
            available_seats = (seat_slots[0], seat_slots[1], seat_slots[2])
            permutations: tuple[tuple[str, str, str], ...] = tuple(
                (order[0], order[1], order[2]) for order in itertools.permutations(combo)
            )
            score_order = partial(
                _opponent_assignment_score,
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
            scenario_seed = _digest_int(seed, "game", cycle, index, combo) % (2**31 - 1)
            scenario_id = hashlib.sha256(
                f"{self.registry_hash}|{cycle}|{index}|{combo}|{own_seat}|{scenario_seed}".encode()
            ).hexdigest()[:20]
            scenarios.append(
                PodScenario(
                    scenario_id=f"balanced4p-{scenario_id}",
                    cycle_id=cycle,
                    opponent_deck_ids=combo,
                    own_seat=own_seat,
                    opponent_seat_assignment=assignment,
                    seed=scenario_seed,
                    opponent_registry_hash=self.registry_hash,
                )
            )
        return tuple(scenarios)

    def coverage_report(self, scenarios: Iterable[PodScenario]) -> dict[str, object]:
        rows = tuple(scenarios)
        opponent_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()
        triple_counts: Counter[tuple[str, str, str]] = Counter()
        seat_counts: Counter[int] = Counter()
        opponent_seat_counts: Counter[tuple[str, int]] = Counter()
        for scenario in rows:
            opponent_counts.update(scenario.opponent_deck_ids)
            pair_counts.update(itertools.combinations(sorted(scenario.opponent_deck_ids), 2))
            sorted_ids = sorted(scenario.opponent_deck_ids)
            triple = (sorted_ids[0], sorted_ids[1], sorted_ids[2])
            triple_counts[triple] += 1
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
            "games_per_opponent": dict(sorted(opponent_counts.items())),
            "games_per_opponent_pair": {
                "|".join(pair): count for pair, count in sorted(pair_counts.items())
            },
            "games_per_opponent_triple": {
                "|".join(triple_key): count
                for triple_key, count in sorted(triple_counts.items())
            },
            "rogshai_seat_counts": {str(seat): seat_counts[seat] for seat in range(1, 5)},
            "opponent_seat_counts": {
                f"{deck_id}|seat{seat}": opponent_seat_counts[(deck_id, seat)]
                for deck_id in self.opponent_ids
                for seat in range(1, 5)
            },
            "complete_coverage_cycles": full_cycles,
            "incomplete_remainder_games": remainder,
            "combinations_per_full_cycle": self.combinations_per_cycle,
            "opponent_exposure_imbalance": max(exposure) - min(exposure),
            "holdout_opponents": [],
            "opponent_evidence_classes": {
                deck_id: list(self.evidence.get(deck_id, ("unknown",)))
                for deck_id in self.opponent_ids
            },
            "frequency_interpretation": "experimental_equal_coverage_not_real_meta_frequency",
            "source_opponent_registry_hash": self.registry_hash,
        }
