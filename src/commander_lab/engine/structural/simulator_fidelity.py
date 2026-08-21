from __future__ import annotations

import hashlib
import random
from pathlib import Path

from commander_lab.agents import build_pilot
from commander_lab.models import PilotConfig, StructuralMatchConfig, StructuralMatchResult

from .simulator import (
    StructuralSimulator as LegacyStructuralSimulator,
    _Commander,
    _EventRecorder,
    _Player,
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
    fixes state/CRN bugs that are mechanically unambiguous and fails closed on aborts in balanced
    decision campaigns. Mechanics that still need tactical/external rules are separately gated.
    """

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

            # CRN contract: paired baseline/variant runs may have different match labels, but
            # stochastic pilot streams must depend only on the paired scenario seed and seat.
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
        decision_campaign = run_id.startswith("balanced")
        effective = config
        if decision_campaign:
            # The legacy no-progress heuristic counts only life loss. Disable it as an earlier
            # decision endpoint; max-turns remains the bounded stop and any abort is censored.
            limits = config.limits.model_copy(
                update={
                    "max_no_progress_turns": min(
                        100,
                        max(config.limits.max_no_progress_turns, config.limits.max_turns),
                    )
                }
            )
            effective = config.model_copy(update={"limits": limits})
        result = super().simulate(
            effective,
            run_id=run_id,
            event_log_path=event_log_path,
            capture_events=capture_events,
        )
        if decision_campaign and result.aborted:
            raise RuntimeError(
                "Structural decision evidence censored: aborted match must not receive a normal "
                f"placement ({result.abort_reason})"
            )
        return result

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
            # A zone change creates a new object. Ishai counters and other temporary power
            # changes must not survive removal/counter/recast.
            commander.power = commander.base_power
        return super()._cast_commander(player, name, players, recorder, score)

    def _attempt_counter(
        self,
        caster: _Player,
        players: list[_Player],
        threat_score: float,
        recorder: _EventRecorder,
    ) -> bool:
        # Target-restricted/alternative-cost counters are not representable by the core stack
        # abstraction. Remove them from this reaction window rather than let them counter an
        # illegal spell. The mechanics gate routes their card-swap decisions to a higher layer.
        held: list[tuple[_Player, int, object]] = []
        for opponent in players:
            for index in range(len(opponent.hand) - 1, -1, -1):
                card = opponent.hand[index]
                if card.oracle_name in _UNSAFE_LEGACY_COUNTERS:
                    held.append((opponent, index, card))
                    opponent.hand.pop(index)
        try:
            return super()._attempt_counter(caster, players, threat_score, recorder)
        finally:
            for opponent, index, raw_card in reversed(held):
                opponent.hand.insert(index, raw_card)  # type: ignore[arg-type]

    @staticmethod
    def _reset_absent_commanders(players: list[_Player]) -> None:
        for player in players:
            for commander in player.commanders.values():
                if not commander.on_battlefield:
                    commander.power = commander.base_power

    def _resolve_removal(
        self,
        player: _Player,
        card: object,
        players: list[_Player],
        recorder: _EventRecorder,
    ) -> None:
        super()._resolve_removal(player, card, players, recorder)  # type: ignore[arg-type]
        self._reset_absent_commanders(players)

    def _resolve_wipe(
        self,
        player: _Player,
        card: object,
        players: list[_Player],
        recorder: _EventRecorder,
    ) -> None:
        super()._resolve_wipe(player, card, players, recorder)  # type: ignore[arg-type]
        self._reset_absent_commanders(players)
