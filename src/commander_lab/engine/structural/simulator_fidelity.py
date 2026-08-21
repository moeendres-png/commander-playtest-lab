from __future__ import annotations

import hashlib
import random
from pathlib import Path

from commander_lab.agents import build_pilot
from commander_lab.models import (
    PilotConfig,
    StructuralCardProfile,
    StructuralDeckProfile,
    StructuralMatchConfig,
    StructuralMatchResult,
    StructuralPlayerMetrics,
)

from .simulator import (
    StructuralSimulator as LegacyStructuralSimulator,
)
from .simulator import (
    _Commander,
    _EventRecorder,
    _Player,
)
from .telemetry import (
    T1TelemetryAccumulator,
    classify_payment_blocker,
    is_structural_reaction_only,
)

FIDELITY_ENGINE_VERSION = "structural-fidelity-overlay-2026-08-21-v1"
_UNSAFE_LEGACY_COUNTERS = frozenset(
    {
        "Silence",
        "Dispel",
        "Negate",
        "Dovin's Veto",
        "Wash Away",
        "Louisoix's Sacrifice",
    }
)


class StructuralSimulator(LegacyStructuralSimulator):
    """Decision-safety overlay for the legacy Structural core.

    The core remains a Structural model, not a comprehensive Magic rules engine. This overlay
    fixes state/CRN bugs that are mechanically unambiguous. Aborted games remain observable in
    the raw Structural result so exploratory and regression callers can inspect them; strong
    decision consumers must censor them rather than treating their provisional placements as
    ordinary evidence. Mechanics that still need tactical/external rules are separately gated.

    T1 fidelity telemetry is observation-only. It reads the same state Structural already uses for
    action legality and never changes RNG, action choice, scoring, search rewards, or advancement.
    """

    def __init__(self, decks: dict[str, StructuralDeckProfile]) -> None:
        super().__init__(decks)
        self._t1_telemetry: dict[str, T1TelemetryAccumulator] = {}

    def _initialize_players(
        self,
        config: StructuralMatchConfig,
        rng: random.Random,
        recorder: _EventRecorder,
    ) -> list[_Player]:
        players: list[_Player] = []
        for seat, deck_id in enumerate(config.deck_ids):
            deck = self.decks[deck_id]
            commander_names = set(deck.commander_names)
            library = [card for card in deck.cards if card.oracle_name not in commander_names]
            rng.shuffle(library)
            pilot_config = config.pilot_configs[seat] if config.pilot_configs else PilotConfig()
            pilot = build_pilot(pilot_config, strategy=deck.commander_strategy)
            pilot_seed_raw = hashlib.sha256(
                f"{FIDELITY_ENGINE_VERSION}|{config.seed}|pilot|{seat}".encode()
            ).digest()
            player = _Player(
                player_id=f"p{seat + 1}",
                seat=seat,
                deck=deck,
                pilot=pilot,
                pilot_rng=random.Random(int.from_bytes(pilot_seed_raw[:8], "big")),
                library=library,
                commanders={
                    name: _Commander(
                        name=name,
                        base_cost=deck.commander_base_costs[name],
                        base_power=deck.commander_base_power.get(name, 2.0),
                        power=deck.commander_base_power.get(name, 2.0),
                    )
                    for name in deck.commander_names
                },
            )
            if config.opening_hand_overrides and config.opening_hand_overrides[seat] is not None:
                self._apply_opening_hand_override(
                    player, config.opening_hand_overrides[seat] or (), rng, recorder
                )
            else:
                self._london_mulligan(
                    player,
                    rng,
                    recorder,
                    config.free_multiplayer_mulligan and len(config.deck_ids) >= 3,
                )
            players.append(player)
        return players

    def simulate(
        self,
        config: StructuralMatchConfig,
        *,
        run_id: str = "structural-run",
        event_log_path: str | Path | None = None,
        capture_events: bool | None = None,
    ) -> StructuralMatchResult:
        self._t1_telemetry = {}
        decision_campaign = run_id.startswith("balanced")
        effective = config
        if decision_campaign:
            limits = config.limits.model_copy(
                update={
                    "max_no_progress_turns": min(
                        100,
                        max(config.limits.max_no_progress_turns, config.limits.max_turns),
                    )
                }
            )
            effective = config.model_copy(update={"limits": limits})
        return super().simulate(
            effective,
            run_id=run_id,
            event_log_path=event_log_path,
            capture_events=capture_events,
        )

    def _telemetry_for(self, player: _Player) -> T1TelemetryAccumulator:
        return self._t1_telemetry.setdefault(player.player_id, T1TelemetryAccumulator())

    def _choose_action(
        self,
        player: _Player,
        players: list[_Player],
        turn_number: int,
        recorder: _EventRecorder,
    ) -> tuple[str, StructuralCardProfile | str, float] | None:
        selected = super()._choose_action(player, players, turn_number, recorder)
        if selected is None:
            accumulator = self._telemetry_for(player)
            accumulator.decision_windows += 1
            for card in player.hand:
                if card.is_land or is_structural_reaction_only(card):
                    continue
                blocker = classify_payment_blocker(
                    mana_available=player.mana_available,
                    available_colors=player.available_colors,
                    card=card,
                )
                if blocker is None:
                    continue
                accumulator.stranded_spells += 1
                accumulator.stranded_reasons[blocker] += 1
                if blocker == "missing_color":
                    accumulator.colored_mana_failures += 1
        return selected

    def _end_step(
        self, player: _Player, players: list[_Player], recorder: _EventRecorder, turn: int
    ) -> None:
        accumulator = self._telemetry_for(player)
        accumulator.unused_mana += max(0.0, player.mana_available)
        for commander in player.commanders.values():
            if commander.casts <= 0 or commander.on_battlefield:
                continue
            requirements = self._commander_color_requirements(player, commander.name)
            accumulator.record_recast(
                commander.name,
                affordable=self._can_pay(player, commander.next_cost, requirements),
            )
        super()._end_step(player, players, recorder, turn)

    def _final_metrics(self, player: _Player) -> StructuralPlayerMetrics:
        metrics = super()._final_metrics(player)
        accumulator = self._telemetry_for(player)
        measured = accumulator.decision_windows > 0
        return metrics.model_copy(
            update={
                "unused_mana": accumulator.unused_mana if measured else None,
                "colored_mana_failures": (
                    accumulator.colored_mana_failures if measured else None
                ),
                "stranded_spells": accumulator.stranded_spells if measured else None,
                "stranded_reasons": (
                    dict(sorted(accumulator.stranded_reasons.items())) if measured else None
                ),
                "commander_recast_affordability": accumulator.recast_affordability(),
                "fidelity_telemetry_status": "PARTIAL" if measured else "NOT_MEASURED",
            }
        )

    def _cast_commander(
        self,
        player: _Player,
        name: str,
        players: list[_Player],
        recorder: _EventRecorder,
        score: float,
    ) -> bool:
        commander = player.commanders[name]
        if not commander.on_battlefield:
            commander.power = commander.base_power
        return super()._cast_commander(player, name, players, recorder, score)

    def _attempt_counter(
        self,
        caster: _Player,
        players: list[_Player],
        threat_score: float,
        recorder: _EventRecorder,
    ) -> bool:
        held: list[tuple[_Player, int, StructuralCardProfile]] = []
        for opponent in players:
            for index in range(len(opponent.hand) - 1, -1, -1):
                card = opponent.hand[index]
                if card.oracle_name in _UNSAFE_LEGACY_COUNTERS:
                    held.append((opponent, index, card))
                    opponent.hand.pop(index)
        try:
            return super()._attempt_counter(caster, players, threat_score, recorder)
        finally:
            for opponent, index, card in reversed(held):
                opponent.hand.insert(index, card)

    @staticmethod
    def _reset_absent_commanders(players: list[_Player]) -> None:
        for player in players:
            for commander in player.commanders.values():
                if not commander.on_battlefield:
                    commander.power = commander.base_power

    def _resolve_removal(
        self,
        player: _Player,
        card: StructuralCardProfile,
        players: list[_Player],
        recorder: _EventRecorder,
    ) -> None:
        super()._resolve_removal(player, card, players, recorder)
        self._reset_absent_commanders(players)

    def _resolve_wipe(
        self,
        player: _Player,
        card: StructuralCardProfile,
        players: list[_Player],
        recorder: _EventRecorder,
    ) -> None:
        super()._resolve_wipe(player, card, players, recorder)
        self._reset_absent_commanders(players)
