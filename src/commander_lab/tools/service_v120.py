from __future__ import annotations

from typing import Any

from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.repositories.opponents import CurrentOpponentRepository

from .service import CommanderToolService as LegacyCommanderToolService
from .whole_deck_prepare import prepare_whole_deck
from .whole_deck_run import run_whole_deck


class CommanderToolService(LegacyCommanderToolService):
    """Explicit 1.20 public service wiring without import-time monkeypatching.

    The legacy service remains the implementation of low-level expert tools. This adapter owns the
    small amount of public workflow routing and current-opponent selection introduced by 1.20.
    """

    def _current_opponent_repository(self) -> CurrentOpponentRepository:
        return CurrentOpponentRepository(self.root)

    def _opponent_pod_for_size(self, requested: tuple[str, ...], pod_size: int) -> tuple[str, ...]:
        needed = pod_size - 1
        if needed < 1:
            raise ValueError("Commander robustness pods require at least two players")
        ordered: list[str] = []
        for deck_id in (*requested, *self._current_opponent_repository().current_deck_ids()):
            if deck_id not in ordered:
                ordered.append(deck_id)
        if len(ordered) < needed:
            return super()._opponent_pod_for_size(tuple(ordered), pod_size)
        return tuple(ordered[:needed])

    def _balanced_reference_opponents(
        self, requested: tuple[str, ...] = (), *, seed: int
    ) -> tuple[str, ...]:
        if requested:
            if len(requested) != len(set(requested)):
                raise ValueError("opponent deck ids must be unique")
            return requested
        repository = self._current_opponent_repository()
        scheduler = BalancedPodScenarioScheduler(
            repository.records(), opponent_registry_hash=repository.registry_hash
        )
        return scheduler.schedule(1, seed=seed)[0].opponent_deck_ids

    def _resolve_pilot_request(self, request: Any) -> Any:
        resolved = self._balanced_reference_opponents(
            tuple(request.opponent_deck_ids), seed=int(request.seed)
        )
        return request.model_copy(update={"opponent_deck_ids": resolved})

    def run_pilot_benchmark(self, request: Any):  # type: ignore[no-untyped-def]
        return super().run_pilot_benchmark(self._resolve_pilot_request(request))

    def compare_pilots(self, request: Any):  # type: ignore[no-untyped-def]
        return super().compare_pilots(self._resolve_pilot_request(request))

    def run_pilot_ensemble(self, request: Any):  # type: ignore[no-untyped-def]
        return super().run_pilot_ensemble(self._resolve_pilot_request(request))

    def test_variant_across_pilots(self, request: Any):  # type: ignore[no-untyped-def]
        return super().test_variant_across_pilots(self._resolve_pilot_request(request))

    def deck_decision_prepare(self, request: Any):  # type: ignore[no-untyped-def]
        if getattr(request, "design_mode", "swap") != "whole_deck":
            return super().deck_decision_prepare(request)
        return self._invoke(
            "deck_decision_prepare",
            request,
            lambda: prepare_whole_deck(self, request),
            deck_ids=(request.deck_id,),
        )

    def deck_decision_run(self, request: Any):  # type: ignore[no-untyped-def]
        if getattr(request, "comparison_mode", "swap") != "whole_deck":
            return super().deck_decision_run(request)
        return self._invoke(
            "deck_decision_run",
            request,
            lambda: run_whole_deck(self, request),
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
        )
