from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from commander_lab.agents import BasePilot, build_pilot
from commander_lab.models import (
    CardRole,
    Color,
    PilotActionView,
    PilotCommanderView,
    PilotConfig,
    PilotDecision,
    PilotOpponentView,
    PilotStateView,
    StructuralCardProfile,
    StructuralDeckProfile,
    StructuralMatchConfig,
    StructuralMatchResult,
    StructuralPlayerMetrics,
)
from commander_lab.storage import atomic_write_text, canonical_json_bytes


ENGINE_VERSION = "structural-0.6.0"


def commander_cast_cost(base_cost: float, prior_casts: int) -> int:
    """Return structural commander cost including two generic mana per prior cast."""
    if base_cost < 0 or prior_casts < 0:
        raise ValueError("base_cost and prior_casts must be non-negative")
    return int(math.ceil(base_cost + 2 * prior_casts))


def commander_damage_is_lethal(
    damage_received: dict[str, float] | Iterable[float],
    *,
    threshold: float = 21.0,
) -> bool:
    """Return whether one commander has individually reached the lethal threshold."""
    values = damage_received.values() if isinstance(damage_received, dict) else damage_received
    return any(float(value) >= threshold for value in values)


@dataclass(slots=True)
class _Commander:
    name: str
    base_cost: float
    base_power: float
    casts: int = 0
    on_battlefield: bool = False
    power: float = 0.0

    @property
    def next_cost(self) -> int:
        return commander_cast_cost(self.base_cost, self.casts)


@dataclass(slots=True)
class _Player:
    player_id: str
    seat: int
    deck: StructuralDeckProfile
    pilot: BasePilot
    pilot_rng: random.Random
    library: list[StructuralCardProfile]
    hand: list[StructuralCardProfile] = field(default_factory=list)
    battlefield: list[StructuralCardProfile] = field(default_factory=list)
    graveyard: list[StructuralCardProfile] = field(default_factory=list)
    exile: list[StructuralCardProfile] = field(default_factory=list)
    commanders: dict[str, _Commander] = field(default_factory=dict)
    life: float = 40.0
    alive: bool = True
    placement: int | None = None
    eliminated_turn: int | None = None
    elimination_reason: str | None = None
    lands: int = 0
    ramp_mana: float = 0.0
    temporary_mana: float = 0.0
    mana_spent: float = 0.0
    available_colors: set[Color] = field(default_factory=set)
    resources: float = 0.0
    tokens: float = 0.0
    board_power: float = 0.0
    engine_value: float = 0.0
    commander_damage_received: dict[str, float] = field(default_factory=dict)
    mulligans: int = 0
    lands_played: int = 0
    ramp_resolved: int = 0
    cards_drawn: int = 0
    commander_casts: int = 0
    commander_tax_paid: int = 0
    first_commander_cast_turn: int | None = None
    commander_peak_power: dict[str, float] = field(default_factory=dict)
    ishai_peak_power: float = 0.0
    korvold_cards_drawn: int = 0
    hostile_target_events: int = 0
    archenemy_turns: int = 0
    removals_resolved: int = 0
    counters_resolved: int = 0
    protections_resolved: int = 0
    wipes_resolved: int = 0
    graveyard_hate_resolved: int = 0
    recursions_resolved: int = 0
    resources_generated: float = 0.0
    normal_damage_dealt: float = 0.0
    commander_damage_dealt: float = 0.0
    spell_count: int = 0
    mana_available: float = 0.0
    pending_direct_damage: float = 0.0
    current_turn: int = 1

    def threat(self) -> float:
        commander_power = sum(commander.power for commander in self.commanders.values() if commander.on_battlefield)
        return self.board_power + commander_power + self.engine_value * 1.5 + self.resources * 0.35

    def commander_online(self) -> bool:
        return any(commander.on_battlefield for commander in self.commanders.values())

    def role_count(self, role: CardRole, *, battlefield_only: bool = True) -> int:
        cards = self.battlefield if battlefield_only else self.battlefield + self.graveyard
        return sum(1 for card in cards if role in card.roles)


class _EventRecorder:
    def __init__(self, game_id: str, *, capture: bool) -> None:
        self.game_id = game_id
        self.capture = capture
        self.events: list[dict[str, Any]] = []
        self.sequence = 0
        self._hash = hashlib.sha256()

    def emit(self, event_type: str, *, actor_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
        event = {
            "event_id": f"{self.game_id}:{self.sequence:06d}",
            "game_id": self.game_id,
            "sequence": self.sequence,
            "event_type": event_type,
            "actor_id": actor_id,
            "payload": payload or {},
            "estimate_type": "structural_model_estimates",
            "engine_version": ENGINE_VERSION,
        }
        raw = canonical_json_bytes(event)
        self._hash.update(raw)
        self._hash.update(b"\n")
        if self.capture:
            self.events.append(event)
        self.sequence += 1

    @property
    def sha256(self) -> str:
        return self._hash.hexdigest()

    def write(self, path: str | Path) -> None:
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for event in self.events
        )
        atomic_write_text(path_obj, payload)


class StructuralSimulator:
    """Fast role-based Commander simulator.

    This engine deliberately models deck structure rather than comprehensive Magic rules.
    Every returned result is labelled ``structural_model_estimates``.
    """

    def __init__(self, decks: dict[str, StructuralDeckProfile]) -> None:
        self.decks = decks

    def simulate(
        self,
        config: StructuralMatchConfig,
        *,
        run_id: str = "structural-run",
        event_log_path: str | Path | None = None,
        capture_events: bool | None = None,
    ) -> StructuralMatchResult:
        missing = set(config.deck_ids) - set(self.decks)
        if missing:
            raise KeyError(f"missing deck profiles: {sorted(missing)}")
        capture = bool(event_log_path) if capture_events is None else capture_events
        rng = random.Random(config.seed)
        recorder = _EventRecorder(config.match_id, capture=capture)
        players = self._initialize_players(config, rng, recorder)
        starting_seat = config.starting_player_seat
        if starting_seat is None:
            starting_seat = rng.randrange(len(players))
        order = players[starting_seat:] + players[:starting_seat]
        recorder.emit(
            "game_started",
            payload={
                "seed": config.seed,
                "turn_order": [player.player_id for player in order],
                "pod_size": len(players),
                "pilots": [
                    {
                        "player_id": player.player_id,
                        "pilot_name": player.pilot.pilot_name,
                        "strength": player.pilot.config.strength.value,
                        "mode": player.pilot.config.mode.value,
                    }
                    for player in players
                ],
                "estimate_type": config.estimate_type,
            },
        )
        self._emit_state_checkpoint(players, recorder, reason="post_mulligan")

        goldfish_life = 40.0
        goldfish_commander_damage: dict[str, float] = {}
        global_turn = 0
        rounds_without_damage = 0
        previous_total_life = sum(player.life for player in players) + goldfish_life
        aborted = False
        abort_reason: str | None = None
        end_reason = "last_player_standing"

        while True:
            living = [player for player in players if player.alive]
            if len(players) == 1:
                if goldfish_life <= 0 or any(value >= 21 for value in goldfish_commander_damage.values()):
                    players[0].placement = 1
                    end_reason = "goldfish_lethal"
                    break
            elif len(living) <= 1:
                if living:
                    living[0].placement = 1
                break
            if global_turn >= config.limits.max_turns * max(1, len(players)):
                aborted = True
                abort_reason = "max_turns"
                end_reason = "aborted_max_turns"
                break
            if recorder.sequence >= config.limits.max_events:
                aborted = True
                abort_reason = "max_events"
                end_reason = "aborted_max_events"
                break

            active = order[global_turn % len(order)]
            global_turn += 1
            if not active.alive:
                continue
            turn_number = (global_turn - 1) // len(order) + 1
            active.current_turn = turn_number
            before = self._snapshot_metrics(active)
            recorder.emit(
                "turn_started",
                actor_id=active.player_id,
                payload={"turn": turn_number, "global_turn": global_turn, "life": active.life},
            )
            active.temporary_mana = 0.0
            active.mana_spent = 0.0
            self._upkeep(active, players, recorder, turn_number)
            self._draw(active, 1, recorder, reason="turn_draw")
            self._play_land(active, recorder)
            active.mana_available = active.lands + active.ramp_mana + active.temporary_mana + min(3.0, active.resources * 0.25)
            spells_cast = 0
            while spells_cast < config.limits.max_spells_per_turn:
                action = self._choose_action(active, players, turn_number, recorder)
                if action is None:
                    break
                kind, card_or_name, score = action
                if kind == "commander":
                    resolved = self._cast_commander(active, str(card_or_name), players, recorder, score)
                else:
                    resolved = self._cast_card(active, card_or_name, players, recorder, score)
                spells_cast += 1
                if not resolved and active.mana_available < 1:
                    break
                if recorder.sequence >= config.limits.max_events:
                    break
            dealt, goldfish_life = self._combat(
                active,
                players,
                recorder,
                turn_number,
                goldfish_life,
                goldfish_commander_damage,
            )
            self._end_step(active, players, recorder, turn_number)
            self._check_eliminations(players, turn_number, recorder)
            self._record_archenemy_state(players, recorder, turn_number)
            after = self._snapshot_metrics(active)
            recorder.emit(
                "turn_summary",
                actor_id=active.player_id,
                payload={
                    "turn": turn_number,
                    "global_turn": global_turn,
                    "spells_cast": spells_cast,
                    "combat_damage": round(dealt, 4),
                    "before": before,
                    "after": after,
                },
            )
            self._emit_state_checkpoint(
                players,
                recorder,
                reason="turn_end",
                turn=turn_number,
                global_turn=global_turn,
            )

            total_life = sum(player.life for player in players if player.alive) + goldfish_life
            if total_life < previous_total_life - 0.01:
                rounds_without_damage = 0
            elif global_turn % len(order) == 0:
                rounds_without_damage += 1
            previous_total_life = total_life
            if rounds_without_damage >= config.limits.max_no_progress_turns:
                aborted = True
                abort_reason = "max_no_progress_turns"
                end_reason = "aborted_no_progress"
                break

        if aborted:
            self._assign_abort_placements(players)
        winner_ids = tuple(player.player_id for player in players if player.placement == 1)
        if len(players) == 1 and not winner_ids and not aborted:
            players[0].placement = 1
            winner_ids = (players[0].player_id,)
        self._emit_state_checkpoint(
            players,
            recorder,
            reason="game_end",
            turn=math.ceil(global_turn / max(1, len(order))),
            global_turn=global_turn,
        )
        recorder.emit(
            "game_ended",
            payload={
                "completed": not aborted,
                "aborted": aborted,
                "abort_reason": abort_reason,
                "winner_ids": list(winner_ids),
                "end_reason": end_reason,
                "turns": math.ceil(global_turn / max(1, len(order))),
            },
        )

        log_path: str | None = None
        if event_log_path is not None:
            recorder.write(event_log_path)
            log_path = str(event_log_path)
        metrics = {player.player_id: self._final_metrics(player) for player in players}
        return StructuralMatchResult(
            run_id=run_id,
            match_id=config.match_id,
            seed=config.seed,
            completed=not aborted,
            aborted=aborted,
            abort_reason=abort_reason,
            turns=math.ceil(global_turn / max(1, len(order))),
            winner_ids=winner_ids,
            placements={player.player_id: player.placement or len(players) for player in players},
            end_reason=end_reason,
            player_metrics=metrics,
            event_count=recorder.sequence,
            event_log_path=log_path,
            log_sha256=recorder.sha256,
        )

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
                f"{ENGINE_VERSION}|{config.seed}|{config.match_id}|pilot|{seat}".encode("utf-8")
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
            self._london_mulligan(player, rng, recorder, config.free_multiplayer_mulligan and len(config.deck_ids) >= 3)
            players.append(player)
        return players

    def _london_mulligan(
        self,
        player: _Player,
        rng: random.Random,
        recorder: _EventRecorder,
        free_first: bool,
    ) -> None:
        original = list(player.library)
        accepted: list[StructuralCardProfile] = []
        accepted_views: list[PilotActionView] = []
        max_mulligans = 4
        mulligans = 0
        hand_score = 0.0
        while mulligans <= max_mulligans:
            trial = list(original)
            rng.shuffle(trial)
            hand = trial[:7]
            views = [
                self._opening_hand_action(card, index)
                for index, card in enumerate(hand)
            ]
            keep, hand_score = player.pilot.should_keep_opening_hand(
                views,
                mulligans=mulligans,
                free_first=free_first,
                commander_names=player.deck.commander_names,
                rng=player.pilot_rng,
            )
            if keep or mulligans == max_mulligans:
                accepted = hand
                accepted_views = views
                player.library = trial[7:]
                break
            mulligans += 1
        bottom_count = max(0, mulligans - (1 if free_first and mulligans > 0 else 0))
        bottom_ids = set(
            player.pilot.choose_bottom_cards(
                accepted_views,
                bottom_count,
                commander_names=player.deck.commander_names,
            )
        )
        bottomed = [
            card
            for card, view in zip(accepted, accepted_views, strict=True)
            if view.action_id in bottom_ids
        ]
        player.hand = [
            card
            for card, view in zip(accepted, accepted_views, strict=True)
            if view.action_id not in bottom_ids
        ]
        player.library.extend(bottomed)
        player.mulligans = mulligans
        recorder.emit(
            "london_mulligan",
            actor_id=player.player_id,
            payload={
                "pilot_name": player.pilot.pilot_name,
                "pilot_strength": player.pilot.config.strength.value,
                "pilot_mode": player.pilot.config.mode.value,
                "mulligans": mulligans,
                "free_first": free_first,
                "hand_score": round(hand_score, 6),
                "bottomed": [card.oracle_name for card in bottomed],
                "kept_hand_size": len(player.hand),
                "land_count": sum(card.is_land for card in player.hand),
            },
        )

    @staticmethod
    def _opening_hand_action(
        card: StructuralCardProfile,
        index: int,
    ) -> PilotActionView:
        return PilotActionView(
            action_id=f"opening:{index}:{card.oracle_name}",
            action_kind="card",
            card_name=card.oracle_name,
            mana_cost=card.mana_value,
            roles=card.roles,
            role_strengths=card.role_strengths,
            floor_value=card.floor_value,
            immediate_impact=card.immediate_impact,
            turn_cycle_risk=card.turn_cycle_risk,
            multiplayer_scaling=card.multiplayer_scaling,
            commander_synergy=card.commander_synergy,
            base_power=card.base_power,
            metadata={
                "is_land": card.is_land,
                "is_creature": card.is_creature,
                "produces_colors": "".join(
                    sorted(color.value for color in card.produces_colors)
                ),
                "package_ids": "|".join(sorted(card.package_ids)),
            },
        )

    @staticmethod
    def _opening_hand_value(card: StructuralCardProfile) -> float:
        if card.is_land:
            return 4.0
        value = card.floor_value + card.immediate_impact
        if CardRole.RAMP in card.roles and card.mana_value <= 2:
            value += 3.0
        if card.roles.intersection({CardRole.DRAW, CardRole.SELECTION}) and card.mana_value <= 2:
            value += 2.0
        value -= max(0.0, card.mana_value - 4) * 0.4
        return value

    def _upkeep(
        self,
        player: _Player,
        players: list[_Player],
        recorder: _EventRecorder,
        turn_number: int,
    ) -> None:
        draw_strength = sum(card.strength(CardRole.DRAW) for card in player.battlefield)
        engine_strength = sum(card.strength(CardRole.ENGINE) for card in player.battlefield)
        token_strength = sum(card.strength(CardRole.TOKEN_SOURCE) for card in player.battlefield)
        extra_draw = int((draw_strength * 0.35 + engine_strength * 0.12) // 1)
        if extra_draw:
            self._draw(player, min(3, extra_draw), recorder, reason="engine_draw")
        generated = engine_strength * 0.18 + token_strength * 0.22
        if generated > 0:
            player.resources += generated
            player.resources_generated += generated
            player.tokens += token_strength * 0.15
            player.board_power += token_strength * 0.12
            recorder.emit(
                "engine_upkeep",
                actor_id=player.player_id,
                payload={"turn": turn_number, "resources": round(generated, 4), "extra_draw": extra_draw},
            )
        payoff = sum(card.strength(CardRole.PAYOFF) * card.multiplayer_scaling for card in player.battlefield)
        if payoff > 0.4:
            damage = payoff * 0.45
            for opponent in players:
                if opponent.alive and opponent.player_id != player.player_id:
                    opponent.life -= damage
                    player.normal_damage_dealt += damage
            recorder.emit(
                "payoff_trigger",
                actor_id=player.player_id,
                payload={"damage_each_opponent": round(damage, 4)},
            )

    def _draw(self, player: _Player, count: int, recorder: _EventRecorder, *, reason: str) -> None:
        drawn: list[str] = []
        for _ in range(count):
            if not player.library:
                player.alive = False
                player.elimination_reason = "empty_library"
                break
            card = player.library.pop(0)
            player.hand.append(card)
            player.cards_drawn += 1
            drawn.append(card.oracle_name)
        if drawn:
            recorder.emit("cards_drawn", actor_id=player.player_id, payload={"reason": reason, "cards": drawn})

    def _play_land(self, player: _Player, recorder: _EventRecorder) -> None:
        lands = [card for card in player.hand if card.is_land]
        if not lands:
            return
        missing_colors = self._needed_colors(player) - player.available_colors
        land = max(
            lands,
            key=lambda card: (
                len(card.produces_colors & missing_colors),
                len(card.produces_colors),
                CardRole.GRAVEYARD_HATE in card.roles,
                card.oracle_name,
            ),
        )
        player.hand.remove(land)
        player.battlefield.append(land)
        player.lands += 1
        player.lands_played += 1
        player.available_colors.update(land.produces_colors)
        if CardRole.TOKEN_SOURCE in land.roles:
            player.tokens += 0.25
        if CardRole.GRAVEYARD_HATE in land.roles:
            player.graveyard_hate_resolved += 1
        recorder.emit(
            "land_played",
            actor_id=player.player_id,
            payload={"card": land.oracle_name, "lands": player.lands, "colors": sorted(color.value for color in player.available_colors)},
        )

    @staticmethod
    def _needed_colors(player: _Player) -> set[Color]:
        needed: set[Color] = set()
        for card in player.hand:
            needed.update(card.color_requirements)
        return needed

    def _choose_action(
        self,
        player: _Player,
        players: list[_Player],
        turn_number: int,
        recorder: _EventRecorder,
    ) -> tuple[str, StructuralCardProfile | str, float] | None:
        actions: list[PilotActionView] = []
        mapping: dict[str, tuple[str, StructuralCardProfile | str]] = {}
        state = self._pilot_state(player, players, turn_number)
        for index, card in enumerate(player.hand):
            if card.is_land or not self._can_pay(player, card.mana_value, card.color_requirements):
                continue
            if (
                not card.is_permanent
                and card.roles
                and card.roles.issubset({CardRole.COUNTER, CardRole.PROTECTION})
            ):
                continue
            action_id = f"card:{index}:{card.oracle_name}"
            action = self._pilot_action_for_card(
                player,
                players,
                card,
                action_id=action_id,
                action_kind="card",
            )
            actions.append(action)
            mapping[action_id] = ("card", card)
        for commander in player.commanders.values():
            requirements = self._commander_color_requirements(player, commander.name)
            if commander.on_battlefield or not self._can_pay(player, commander.next_cost, requirements):
                continue
            card = next((item for item in player.deck.cards if item.oracle_name == commander.name), None)
            action_id = f"commander:{commander.name}"
            action = PilotActionView(
                action_id=action_id,
                action_kind="commander",
                card_name=commander.name,
                mana_cost=float(commander.next_cost),
                roles=card.roles if card else frozenset({CardRole.ENGINE, CardRole.PAYOFF}),
                role_strengths=card.role_strengths if card else {},
                floor_value=card.floor_value if card else 0.8,
                immediate_impact=card.immediate_impact if card else 0.6,
                turn_cycle_risk=card.turn_cycle_risk if card else 0.55,
                multiplayer_scaling=card.multiplayer_scaling if card else 0.0,
                commander_synergy=max(1.0, card.commander_synergy if card else 1.0),
                base_power=commander.base_power,
                target_threat=state.max_opponent_threat,
                remaining_mana=max(0.0, player.mana_available - commander.next_cost),
                metadata={"prior_casts": commander.casts},
            )
            actions.append(action)
            mapping[action_id] = ("commander", commander.name)
        pass_action = PilotActionView(
            action_id="pass",
            action_kind="pass",
            card_name="Pass priority window",
            remaining_mana=player.mana_available,
            immediate_impact=0.15,
            floor_value=0.2,
            metadata={"reactive_cards_held": sum(
                1
                for card in player.hand
                if card.roles.intersection({CardRole.COUNTER, CardRole.PROTECTION, CardRole.REMOVAL})
            )},
        )
        actions.append(pass_action)
        decision = player.pilot.choose_action(state, actions, player.pilot_rng)
        self._record_pilot_decision(player, decision, recorder, phase="main")
        if decision.selected_action_id in {None, "pass"}:
            return None
        kind, item = mapping[decision.selected_action_id]
        return kind, item, float(decision.selected_utility or 0.0)

    @staticmethod
    def _record_pilot_decision(
        player: _Player,
        decision: PilotDecision,
        recorder: _EventRecorder,
        *,
        phase: str,
    ) -> None:
        recorder.emit(
            "pilot_decision",
            actor_id=player.player_id,
            payload={
                "phase": phase,
                "pilot_name": decision.pilot_name,
                "strength": decision.strength.value,
                "mode": decision.mode.value,
                "selected_action_id": decision.selected_action_id,
                "selected_utility": decision.selected_utility,
                "candidates": [list(item) for item in decision.candidates],
                "breakdown": (
                    decision.selected_breakdown.model_dump(mode="json")
                    if decision.selected_breakdown is not None
                    else None
                ),
            },
        )

    def _pilot_state(
        self,
        player: _Player,
        players: list[_Player],
        turn_number: int,
    ) -> PilotStateView:
        role_counts: dict[CardRole, int] = {}
        for card in player.hand + player.battlefield:
            for role in card.roles:
                role_counts[role] = role_counts.get(role, 0) + 1
        commanders = tuple(
            PilotCommanderView(
                name=commander.name,
                base_cost=commander.base_cost,
                next_cost=commander.next_cost,
                casts=commander.casts,
                on_battlefield=commander.on_battlefield,
                power=commander.power,
            )
            for commander in player.commanders.values()
        )
        opponents: list[PilotOpponentView] = []
        prefix = f"{player.player_id}:"
        for opponent in players:
            if opponent.player_id == player.player_id or not opponent.alive:
                continue
            outgoing = {
                key.removeprefix(prefix): value
                for key, value in opponent.commander_damage_received.items()
                if key.startswith(prefix)
            }
            opponents.append(
                PilotOpponentView(
                    player_id=opponent.player_id,
                    life=opponent.life,
                    threat=opponent.threat(),
                    board_power=opponent.board_power,
                    engine_value=opponent.engine_value,
                    graveyard_size=len(opponent.graveyard),
                    hand_size=len(opponent.hand),
                    commander_damage_from_actor=outgoing,
                )
            )
        return PilotStateView(
            player_id=player.player_id,
            deck_id=player.deck.deck_id,
            strategy=player.deck.commander_strategy,
            turn=turn_number,
            pod_size=len(players),
            life=player.life,
            hand_size=len(player.hand),
            mana_available=max(0.0, player.mana_available),
            lands=player.lands,
            ramp_mana=player.ramp_mana,
            resources=player.resources,
            tokens=player.tokens,
            board_power=player.board_power,
            engine_value=player.engine_value,
            graveyard_size=len(player.graveyard),
            battlefield_names=tuple(card.oracle_name for card in player.battlefield),
            hand_names=tuple(card.oracle_name for card in player.hand),
            role_counts=role_counts,
            commanders=commanders,
            opponents=tuple(opponents),
        )

    def _pilot_action_for_card(
        self,
        player: _Player,
        players: list[_Player],
        card: StructuralCardProfile,
        *,
        action_id: str,
        action_kind: str,
        threat_score: float = 0.0,
        target_player_id: str | None = None,
    ) -> PilotActionView:
        opponents = [item for item in players if item.alive and item.player_id != player.player_id]
        target_threat = max((item.threat() for item in opponents), default=0.0)
        conditional_multiplier = self._conditional_multiplier(player, card)
        adjusted_strengths = {
            role: strength * conditional_multiplier
            for role, strength in card.role_strengths.items()
        }
        return PilotActionView(
            action_id=action_id,
            action_kind=action_kind,  # type: ignore[arg-type]
            card_name=card.oracle_name,
            mana_cost=card.mana_value,
            roles=card.roles,
            role_strengths=adjusted_strengths,
            floor_value=min(3.0, card.floor_value * conditional_multiplier),
            immediate_impact=min(2.0, card.immediate_impact * conditional_multiplier),
            turn_cycle_risk=card.turn_cycle_risk,
            multiplayer_scaling=card.multiplayer_scaling,
            commander_synergy=card.commander_synergy,
            base_power=card.base_power,
            target_player_id=target_player_id,
            target_threat=target_threat,
            threat_score=threat_score,
            remaining_mana=max(0.0, player.mana_available - card.mana_value),
            metadata={
                "conditional_multiplier": round(conditional_multiplier, 6),
                "package_ids": "|".join(sorted(card.package_ids)),
            },
        )

    @staticmethod
    def _conditional_multiplier(player: _Player, card: StructuralCardProfile) -> float:
        multiplier = 1.0
        for conditional in card.conditional_strength:
            if conditional.condition == "sacrifice_package_online":
                material = player.tokens + player.resources * 0.5
                material += player.role_count(CardRole.TOKEN_SOURCE) * 0.5
                material += player.role_count(CardRole.SACRIFICE_OUTLET) * 0.7
                probability = min(1.0, material / 3.0)
            elif conditional.condition == "land_engine_online":
                density = player.role_count(CardRole.LAND_SYNERGY) + max(0, player.lands - 2) * 0.25
                probability = min(1.0, density / 2.5)
            elif conditional.condition == "commander_attacking":
                probability = 1.0 if player.commander_online() else 0.1
            elif conditional.condition == "survives_turn_cycle":
                probability = max(0.05, 1.0 - card.turn_cycle_risk)
            else:
                probability = 0.5
            multiplier *= 1.0 + (conditional.multiplier - 1.0) * probability
        return max(0.2, min(3.0, multiplier))

    @staticmethod
    def _commander_color_requirements(player: _Player, name: str) -> dict[Color, int]:
        card = next((card for card in player.deck.cards if card.oracle_name == name), None)
        return card.color_requirements if card is not None else {}

    @staticmethod
    def _can_pay(player: _Player, cost: float, color_requirements: dict[Color, int]) -> bool:
        if player.mana_available + 1e-9 < cost:
            return False
        return all(color in player.available_colors for color in color_requirements)

    def _pay(self, player: _Player, cost: float) -> None:
        player.mana_available = max(0.0, player.mana_available - cost)
        player.mana_spent += cost

    def _cast_commander(
        self,
        player: _Player,
        name: str,
        players: list[_Player],
        recorder: _EventRecorder,
        score: float,
    ) -> bool:
        commander = player.commanders[name]
        cost = commander.next_cost
        self._pay(player, cost)
        tax = commander.casts * 2
        commander.casts += 1
        player.commander_casts += 1
        player.commander_tax_paid += tax
        if player.first_commander_cast_turn is None:
            player.first_commander_cast_turn = player.current_turn
        self._notify_spell_cast(player, players)
        recorder.emit("commander_cast", actor_id=player.player_id, payload={"card": name, "cost": cost, "tax": tax})
        if self._attempt_counter(player, players, score + 1.0, recorder):
            recorder.emit("commander_countered", actor_id=player.player_id, payload={"card": name})
            return False
        commander.on_battlefield = True
        commander.power = max(commander.base_power, commander.power)
        player.commander_peak_power[name] = max(
            player.commander_peak_power.get(name, 0.0), commander.power
        )
        if name == "Ishai, Ojutai Dragonspeaker":
            player.ishai_peak_power = max(player.ishai_peak_power, commander.power)
        if name == "Korvold, Fae-Cursed King":
            self._sacrifice_trigger(player, 1.0, recorder, reason="korvold_cast")
        recorder.emit("commander_resolved", actor_id=player.player_id, payload={"card": name, "power": commander.power})
        return True

    def _cast_card(
        self,
        player: _Player,
        card: StructuralCardProfile,
        players: list[_Player],
        recorder: _EventRecorder,
        score: float,
    ) -> bool:
        player.hand.remove(card)
        self._pay(player, card.mana_value)
        player.spell_count += 1
        self._notify_spell_cast(player, players)
        recorder.emit(
            "spell_cast",
            actor_id=player.player_id,
            payload={"card": card.oracle_name, "mana_value": card.mana_value, "roles": sorted(role.value for role in card.roles)},
        )
        if self._attempt_counter(player, players, score, recorder):
            player.graveyard.append(card)
            recorder.emit("spell_countered", actor_id=player.player_id, payload={"card": card.oracle_name})
            return False
        self._resolve_card(player, card, players, recorder)
        return True

    def _notify_spell_cast(self, actor: _Player, players: Iterable[_Player]) -> None:
        for player in players:
            if player.player_id == actor.player_id or not player.alive:
                continue
            ishai = player.commanders.get("Ishai, Ojutai Dragonspeaker")
            if ishai is not None and ishai.on_battlefield:
                ishai.power += 1.0
                player.ishai_peak_power = max(player.ishai_peak_power, ishai.power)
                player.commander_peak_power[ishai.name] = max(
                    player.commander_peak_power.get(ishai.name, 0.0), ishai.power
                )

    def _attempt_counter(
        self,
        caster: _Player,
        players: list[_Player],
        threat_score: float,
        recorder: _EventRecorder,
    ) -> bool:
        if threat_score < 3.6:
            return False
        opponents = sorted(
            (player for player in players if player.alive and player.player_id != caster.player_id),
            key=lambda player: ((player.seat - caster.seat) % len(players), player.player_id),
        )
        for opponent in opponents:
            counters = [
                card
                for card in opponent.hand
                if CardRole.COUNTER in card.roles
                and self._can_pay(opponent, card.mana_value, card.color_requirements)
            ]
            if not counters:
                continue
            state = self._pilot_state(opponent, players, max(1, opponent.current_turn))
            actions: list[PilotActionView] = []
            mapping: dict[str, StructuralCardProfile] = {}
            for index, card in enumerate(counters):
                action_id = f"counter:{index}:{card.oracle_name}"
                action = self._pilot_action_for_card(
                    opponent,
                    players,
                    card,
                    action_id=action_id,
                    action_kind="counter",
                    threat_score=threat_score,
                    target_player_id=caster.player_id,
                )
                actions.append(action)
                mapping[action_id] = card
            actions.append(
                PilotActionView(
                    action_id="pass",
                    action_kind="pass",
                    card_name="Decline counter",
                    remaining_mana=opponent.mana_available,
                    immediate_impact=0.1,
                    floor_value=0.2,
                    threat_score=threat_score,
                )
            )
            decision = opponent.pilot.choose_action(state, actions, opponent.pilot_rng)
            self._record_pilot_decision(opponent, decision, recorder, phase="counter")
            if decision.selected_action_id in {None, "pass"}:
                continue
            counter = mapping[decision.selected_action_id]
            opponent.hand.remove(counter)
            caster.hostile_target_events += 1
            self._pay(opponent, counter.mana_value)
            opponent.graveyard.append(counter)
            opponent.counters_resolved += 1
            recorder.emit(
                "counter_resolved",
                actor_id=opponent.player_id,
                payload={
                    "card": counter.oracle_name,
                    "against": caster.player_id,
                    "threat_score": round(threat_score, 4),
                },
            )
            return True
        return False

    def _resolve_card(
        self,
        player: _Player,
        card: StructuralCardProfile,
        players: list[_Player],
        recorder: _EventRecorder,
    ) -> None:
        if CardRole.WIPE in card.roles:
            self._resolve_wipe(player, card, players, recorder)
        elif CardRole.REMOVAL in card.roles:
            self._resolve_removal(player, card, players, recorder)
        if CardRole.GRAVEYARD_HATE in card.roles:
            self._resolve_graveyard_hate(player, card, players, recorder)
        if CardRole.RECURSION in card.roles:
            self._resolve_recursion(player, card, recorder)
        if CardRole.RAMP in card.roles:
            strength = card.strength(CardRole.RAMP)
            if card.oracle_name in {"Dark Ritual", "Orcish Lumberjack", "Tinder Wall"}:
                player.temporary_mana += strength * 1.5
                player.mana_available += strength * 1.5
            else:
                player.ramp_mana += max(0.5, strength * 0.75)
            player.ramp_resolved += 1
            recorder.emit("ramp_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "strength": strength})
        if CardRole.SELECTION in card.roles:
            self._resolve_selection(player, recorder, card)
        if CardRole.DRAW in card.roles:
            amount = max(1, int(math.ceil(card.strength(CardRole.DRAW))))
            if card.oracle_name == "Korvold, Fae-Cursed King":
                amount = 0
            if amount:
                self._draw(player, min(3, amount), recorder, reason=f"{card.oracle_name}:draw")
        if CardRole.SACRIFICE_OUTLET in card.roles or card.oracle_name in {"Harrow", "Deadly Dispute"}:
            self._sacrifice_trigger(player, 1.0, recorder, reason=card.oracle_name)
        if CardRole.FINISHER in card.roles and not card.is_permanent:
            self._resolve_finisher(player, card, players, recorder)
        if card.is_permanent:
            player.battlefield.append(card)
            if card.is_creature:
                player.board_power += card.base_power
            if CardRole.ENGINE in card.roles:
                player.engine_value += card.strength(CardRole.ENGINE) * (1.0 - card.turn_cycle_risk * 0.25)
            if CardRole.TOKEN_SOURCE in card.roles:
                tokens = card.strength(CardRole.TOKEN_SOURCE) * 0.8
                player.tokens += tokens
                player.board_power += tokens
            if CardRole.PROTECTION in card.roles:
                player.protections_resolved += 1
            recorder.emit("permanent_resolved", actor_id=player.player_id, payload={"card": card.oracle_name})
        else:
            player.graveyard.append(card)
        self._trigger_spellslinger(player, players, card, recorder)

    def _resolve_selection(self, player: _Player, recorder: _EventRecorder, card: StructuralCardProfile) -> None:
        if not player.library:
            return
        look = player.library[: min(3, len(player.library))]
        chosen = max(look, key=self._opening_hand_value)
        player.library.remove(chosen)
        player.hand.append(chosen)
        player.cards_drawn += 1
        recorder.emit("selection_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "selected": chosen.oracle_name})

    def _resolve_removal(self, player: _Player, card: StructuralCardProfile, players: list[_Player], recorder: _EventRecorder) -> None:
        targets = [
            opponent
            for opponent in players
            if opponent.alive and opponent.player_id != player.player_id
        ]
        if not targets:
            return
        state = self._pilot_state(player, players, max(1, player.current_turn))
        target_actions: list[PilotActionView] = []
        target_mapping: dict[str, _Player] = {}
        for opponent in targets:
            commander_value = max(
                (
                    commander.power + 3.0
                    for commander in opponent.commanders.values()
                    if commander.on_battlefield
                ),
                default=0.0,
            )
            permanent_value = max(
                (self._permanent_value(permanent) for permanent in opponent.battlefield),
                default=0.0,
            )
            object_value = max(commander_value, permanent_value)
            action_id = f"removal_target:{opponent.player_id}"
            target_actions.append(
                PilotActionView(
                    action_id=action_id,
                    action_kind="removal_target",
                    card_name=f"{card.oracle_name} -> {opponent.player_id}",
                    roles=frozenset({CardRole.REMOVAL}),
                    role_strengths={CardRole.REMOVAL: card.strength(CardRole.REMOVAL)},
                    immediate_impact=card.immediate_impact,
                    floor_value=card.floor_value,
                    target_player_id=opponent.player_id,
                    target_threat=opponent.threat() + object_value * 0.35,
                    threat_score=object_value,
                    remaining_mana=player.mana_available,
                    metadata={
                        "target_life": opponent.life,
                        "commander_value": commander_value,
                        "permanent_value": permanent_value,
                    },
                )
            )
            target_mapping[action_id] = opponent
        decision = player.pilot.choose_target(state, target_actions, player.pilot_rng)
        self._record_pilot_decision(player, decision, recorder, phase="removal_target")
        target = target_mapping.get(decision.selected_action_id or "", targets[0])
        target.hostile_target_events += 1
        if self._attempt_protection(target, players, recorder, against=card.oracle_name):
            recorder.emit("removal_prevented", actor_id=target.player_id, payload={"against": card.oracle_name})
            return
        commanders = [commander for commander in target.commanders.values() if commander.on_battlefield]
        permanent = max(target.battlefield, key=self._permanent_value, default=None)
        commander_value = max((commander.power + 3 for commander in commanders), default=-1)
        permanent_value = self._permanent_value(permanent) if permanent is not None else -1
        if commanders and commander_value >= permanent_value:
            commander = max(commanders, key=lambda item: item.power)
            commander.on_battlefield = False
            recorder.emit("commander_removed", actor_id=player.player_id, payload={"target": target.player_id, "commander": commander.name})
        elif permanent is not None:
            target.battlefield.remove(permanent)
            target.graveyard.append(permanent)
            self._remove_permanent_value(target, permanent)
            recorder.emit("permanent_removed", actor_id=player.player_id, payload={"target": target.player_id, "card": permanent.oracle_name})
        else:
            return
        player.removals_resolved += 1

    @staticmethod
    def _permanent_value(card: StructuralCardProfile | None) -> float:
        if card is None:
            return 0.0
        return (
            card.base_power
            + card.strength(CardRole.ENGINE) * 3
            + card.strength(CardRole.PAYOFF) * 2.5
            + card.strength(CardRole.FINISHER) * 4
            + card.strength(CardRole.PROTECTION) * 2
        )

    @staticmethod
    def _remove_permanent_value(player: _Player, card: StructuralCardProfile) -> None:
        if card.is_creature:
            player.board_power = max(0.0, player.board_power - card.base_power)
        if CardRole.ENGINE in card.roles:
            player.engine_value = max(0.0, player.engine_value - card.strength(CardRole.ENGINE) * (1.0 - card.turn_cycle_risk * 0.25))

    def _attempt_protection(
        self,
        target: _Player,
        players: list[_Player],
        recorder: _EventRecorder,
        *,
        against: str,
    ) -> bool:
        protections = [
            card
            for card in target.hand
            if CardRole.PROTECTION in card.roles
            and self._can_pay(target, card.mana_value, card.color_requirements)
        ]
        if not protections:
            return False
        state = self._pilot_state(target, players, max(1, target.current_turn))
        threat_score = max(4.0, target.threat() * 0.65)
        actions: list[PilotActionView] = []
        mapping: dict[str, StructuralCardProfile] = {}
        for index, card in enumerate(protections):
            action_id = f"protection:{index}:{card.oracle_name}"
            action = self._pilot_action_for_card(
                target,
                players,
                card,
                action_id=action_id,
                action_kind="protection",
                threat_score=threat_score,
                target_player_id=target.player_id,
            )
            actions.append(action)
            mapping[action_id] = card
        actions.append(
            PilotActionView(
                action_id="pass",
                action_kind="pass",
                card_name="Decline protection",
                remaining_mana=target.mana_available,
                immediate_impact=0.1,
                floor_value=0.15,
                threat_score=threat_score,
            )
        )
        decision = target.pilot.choose_action(state, actions, target.pilot_rng)
        self._record_pilot_decision(target, decision, recorder, phase="protection")
        if decision.selected_action_id in {None, "pass"}:
            return False
        protection = mapping[decision.selected_action_id]
        target.hand.remove(protection)
        self._pay(target, protection.mana_value)
        target.graveyard.append(protection)
        target.protections_resolved += 1
        recorder.emit(
            "protection_resolved",
            actor_id=target.player_id,
            payload={"card": protection.oracle_name, "against": against},
        )
        return True

    def _resolve_wipe(self, player: _Player, card: StructuralCardProfile, players: list[_Player], recorder: _EventRecorder) -> None:
        affected = 0
        for target in players:
            if not target.alive:
                continue
            if self._attempt_board_protection(target, players, recorder, against=card.oracle_name):
                continue
            removable = [permanent for permanent in target.battlefield if not permanent.is_land]
            if not removable:
                continue
            survival_fraction = 0.15 if card.strength(CardRole.WIPE) >= 1.5 else 0.28
            keep_count = int(len(removable) * survival_fraction)
            removable.sort(key=self._permanent_value, reverse=True)
            destroyed = removable[keep_count:]
            for permanent in destroyed:
                target.battlefield.remove(permanent)
                target.graveyard.append(permanent)
                self._remove_permanent_value(target, permanent)
            target.board_power *= survival_fraction
            target.tokens *= survival_fraction
            for commander in target.commanders.values():
                if commander.on_battlefield and card.oracle_name not in {"Winds of Rath"}:
                    commander.on_battlefield = False
            affected += len(destroyed)
        player.wipes_resolved += 1
        recorder.emit("boardwipe_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "destroyed_permanents": affected})

    def _attempt_board_protection(
        self,
        target: _Player,
        players: list[_Player],
        recorder: _EventRecorder,
        *,
        against: str,
    ) -> bool:
        broad = [
            card
            for card in target.hand
            if card.oracle_name == "Boros Charm"
            and self._can_pay(target, card.mana_value, card.color_requirements)
        ]
        if not broad:
            return False
        card = broad[0]
        state = self._pilot_state(target, players, max(1, target.current_turn))
        threat_score = max(5.0, target.threat())
        action = self._pilot_action_for_card(
            target,
            players,
            card,
            action_id=f"protection:board:{card.oracle_name}",
            action_kind="protection",
            threat_score=threat_score,
            target_player_id=target.player_id,
        )
        take, breakdown = target.pilot.should_take_reaction(
            state, action, target.pilot_rng, threshold=0.25
        )
        decision = PilotDecision(
            pilot_name=target.pilot.pilot_name,
            strength=target.pilot.config.strength,
            mode=target.pilot.config.mode,
            selected_action_id=action.action_id if take else "pass",
            selected_utility=breakdown.total_utility,
            candidates=((action.action_id, breakdown.total_utility),),
            selected_breakdown=breakdown,
        )
        self._record_pilot_decision(target, decision, recorder, phase="board_protection")
        if not take:
            return False
        target.hand.remove(card)
        self._pay(target, card.mana_value)
        target.graveyard.append(card)
        target.protections_resolved += 1
        recorder.emit(
            "board_protected",
            actor_id=target.player_id,
            payload={"card": card.oracle_name, "against": against},
        )
        return True

    def _resolve_graveyard_hate(self, player: _Player, card: StructuralCardProfile, players: list[_Player], recorder: _EventRecorder) -> None:
        targets = [
            opponent
            for opponent in players
            if opponent.alive and opponent.player_id != player.player_id
        ]
        if not targets:
            return
        state = self._pilot_state(player, players, max(1, player.current_turn))
        target_actions: list[PilotActionView] = []
        target_mapping: dict[str, _Player] = {}
        for opponent in targets:
            action_id = f"graveyard_target:{opponent.player_id}"
            target_actions.append(
                PilotActionView(
                    action_id=action_id,
                    action_kind="graveyard_target",
                    card_name=f"{card.oracle_name} -> {opponent.player_id}",
                    roles=frozenset({CardRole.GRAVEYARD_HATE}),
                    role_strengths={
                        CardRole.GRAVEYARD_HATE: card.strength(CardRole.GRAVEYARD_HATE)
                    },
                    immediate_impact=card.immediate_impact,
                    floor_value=card.floor_value,
                    target_player_id=opponent.player_id,
                    target_threat=opponent.threat(),
                    threat_score=float(len(opponent.graveyard)),
                    remaining_mana=player.mana_available,
                    metadata={"graveyard_size": len(opponent.graveyard)},
                )
            )
            target_mapping[action_id] = opponent
        decision = player.pilot.choose_target(state, target_actions, player.pilot_rng)
        self._record_pilot_decision(player, decision, recorder, phase="graveyard_target")
        target = target_mapping.get(decision.selected_action_id or "", targets[0])
        count = min(
            len(target.graveyard),
            max(2, int(4 * card.strength(CardRole.GRAVEYARD_HATE))),
        )
        exiled = target.graveyard[-count:]
        del target.graveyard[-count:]
        target.exile.extend(exiled)
        player.graveyard_hate_resolved += 1
        recorder.emit("graveyard_hate_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "target": target.player_id, "exiled": count})

    def _resolve_recursion(self, player: _Player, card: StructuralCardProfile, recorder: _EventRecorder) -> None:
        candidates = [item for item in player.graveyard if not item.is_land]
        if not candidates:
            return
        recovered = max(candidates, key=self._opening_hand_value)
        player.graveyard.remove(recovered)
        player.hand.append(recovered)
        player.recursions_resolved += 1
        recorder.emit("recursion_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "recovered": recovered.oracle_name})

    def _resolve_finisher(self, player: _Player, card: StructuralCardProfile, players: list[_Player], recorder: _EventRecorder) -> None:
        opponents = [opponent for opponent in players if opponent.alive and opponent.player_id != player.player_id]
        strength = card.strength(CardRole.FINISHER)
        if not opponents:
            damage = (3.0 + max(0.0, player.mana_spent - card.mana_value) * 0.7 + player.resources * 0.2) * strength
            player.pending_direct_damage += damage
            recorder.emit("finisher_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "goldfish_damage": round(damage, 4)})
            return
        damage = (3.0 + max(0.0, player.mana_spent - card.mana_value) * 0.7 + player.resources * 0.2) * strength
        damage *= 1.0 + card.multiplayer_scaling * 0.1 * max(0, len(opponents) - 1)
        for opponent in opponents:
            opponent.life -= damage
            player.normal_damage_dealt += damage
        recorder.emit("finisher_resolved", actor_id=player.player_id, payload={"card": card.oracle_name, "damage_each_opponent": round(damage, 4)})

    def _trigger_spellslinger(self, player: _Player, players: list[_Player], card: StructuralCardProfile, recorder: _EventRecorder) -> None:
        if card.is_permanent:
            return
        guttersnipe = sum(1 for permanent in player.battlefield if permanent.oracle_name == "Guttersnipe")
        whirlwind = sum(1 for permanent in player.battlefield if permanent.oracle_name == "Whirlwind of Thought")
        stormkiln = sum(1 for permanent in player.battlefield if permanent.oracle_name == "Storm-Kiln Artist")
        kykar = sum(1 for permanent in player.battlefield if permanent.oracle_name == "Kykar, Wind's Fury")
        if whirlwind:
            self._draw(player, whirlwind, recorder, reason="whirlwind_of_thought")
        if stormkiln:
            generated = float(stormkiln)
            player.resources += generated
            player.resources_generated += generated
        if kykar:
            player.tokens += kykar
            player.board_power += kykar
        if guttersnipe:
            damage = 2.0 * guttersnipe
            for opponent in players:
                if opponent.alive and opponent.player_id != player.player_id:
                    opponent.life -= damage
                    player.normal_damage_dealt += damage
            recorder.emit("spellslinger_payoff", actor_id=player.player_id, payload={"damage_each_opponent": damage})

    def _sacrifice_trigger(self, player: _Player, count: float, recorder: _EventRecorder, *, reason: str) -> None:
        korvold = player.commanders.get("Korvold, Fae-Cursed King")
        if korvold is not None and korvold.on_battlefield:
            korvold.power += count
            draw_count = max(1, int(count))
            player.korvold_cards_drawn += draw_count
            player.commander_peak_power[korvold.name] = max(
                player.commander_peak_power.get(korvold.name, 0.0), korvold.power
            )
            self._draw(player, draw_count, recorder, reason="korvold_trigger")
        bats = sum(card.strength(CardRole.PAYOFF) for card in player.battlefield if card.oracle_name == "Mirkwood Bats")
        hearthhull = sum(card.strength(CardRole.PAYOFF) for card in player.battlefield if card.oracle_name == "Hearthhull, the Worldseed")
        player.resources += count * 0.25
        player.resources_generated += count * 0.25
        recorder.emit("sacrifice_event", actor_id=player.player_id, payload={"reason": reason, "count": count, "bats": bats, "hearthhull": hearthhull})

    def _combat(
        self,
        player: _Player,
        players: list[_Player],
        recorder: _EventRecorder,
        turn: int,
        goldfish_life: float,
        goldfish_commander_damage: dict[str, float],
    ) -> tuple[float, float]:
        commander_attackers = [commander for commander in player.commanders.values() if commander.on_battlefield]
        combat_multiplier = 1.0
        if any(card.oracle_name in {"Duelist's Heritage", "Psychotic Fury"} for card in player.battlefield):
            combat_multiplier *= 1.75
        if any(card.oracle_name == "Jeska, Thrice Reborn" for card in player.battlefield):
            combat_multiplier *= 3.0
        attack = max(0.0, player.board_power * 0.62 + player.tokens * 0.35)
        commander_attack = sum(commander.power for commander in commander_attackers)
        total_attack = (attack + commander_attack) * combat_multiplier
        if total_attack <= 0.1:
            return 0.0, goldfish_life
        if len(players) == 1:
            damage = total_attack + player.pending_direct_damage
            player.pending_direct_damage = 0.0
            goldfish_life -= damage
            player.normal_damage_dealt += max(0.0, attack * combat_multiplier)
            for commander in commander_attackers:
                amount = commander.power * combat_multiplier
                goldfish_commander_damage[commander.name] = goldfish_commander_damage.get(commander.name, 0.0) + amount
                player.commander_damage_dealt += amount
            recorder.emit("combat_damage", actor_id=player.player_id, payload={"target": "goldfish", "damage": round(damage, 4), "target_life": round(goldfish_life, 4)})
            return damage, goldfish_life
        targets = [opponent for opponent in players if opponent.alive and opponent.player_id != player.player_id]
        state = self._pilot_state(player, players, turn)
        target_actions: list[PilotActionView] = []
        target_mapping: dict[str, _Player] = {}
        for opponent in targets:
            key_prefix = f"{player.player_id}:"
            commander_pressure = max(
                (
                    value
                    for key, value in opponent.commander_damage_received.items()
                    if key.startswith(key_prefix)
                ),
                default=0.0,
            )
            action_id = f"combat_target:{opponent.player_id}"
            target_actions.append(
                PilotActionView(
                    action_id=action_id,
                    action_kind="combat_target",
                    card_name=f"Attack {opponent.player_id}",
                    immediate_impact=1.0,
                    floor_value=0.4,
                    base_power=total_attack,
                    target_player_id=opponent.player_id,
                    target_threat=opponent.threat(),
                    remaining_mana=player.mana_available,
                    metadata={
                        "target_life": opponent.life,
                        "commander_damage_pressure": commander_pressure,
                        "blockers": opponent.board_power * 0.35 + opponent.tokens * 0.25,
                    },
                )
            )
            target_mapping[action_id] = opponent
        decision = player.pilot.choose_combat_target(state, target_actions, player.pilot_rng)
        self._record_pilot_decision(player, decision, recorder, phase="combat")
        target = target_mapping.get(decision.selected_action_id or "", targets[0])
        target.hostile_target_events += 1
        blockers = target.board_power * 0.35 + target.tokens * 0.25
        damage = max(0.0, total_attack - blockers)
        target.life -= damage
        player.normal_damage_dealt += max(0.0, damage - commander_attack * combat_multiplier)
        for commander in commander_attackers:
            amount = max(0.0, commander.power * combat_multiplier - blockers / max(1, len(commander_attackers) + 1))
            key = f"{player.player_id}:{commander.name}"
            target.commander_damage_received[key] = target.commander_damage_received.get(key, 0.0) + amount
            player.commander_damage_dealt += amount
        if any(card.oracle_name == "Kediss, Emberclaw Familiar" for card in player.battlefield) and commander_attackers:
            splash = max(commander.power for commander in commander_attackers) * combat_multiplier
            for opponent in targets:
                if opponent.player_id != target.player_id:
                    opponent.life -= splash
                    player.normal_damage_dealt += splash
            recorder.emit("kediss_splash", actor_id=player.player_id, payload={"damage_each_other_opponent": round(splash, 4)})
        recorder.emit("combat_damage", actor_id=player.player_id, payload={"target": target.player_id, "damage": round(damage, 4), "target_life": round(target.life, 4)})
        return damage, goldfish_life

    def _end_step(self, player: _Player, players: list[_Player], recorder: _EventRecorder, turn: int) -> None:
        if player.tokens > 0:
            conversion = min(player.tokens * 0.08, 1.5)
            player.resources += conversion
            player.resources_generated += conversion
        recorder.emit("end_step", actor_id=player.player_id, payload={"turn": turn, "hand_size": len(player.hand), "resources": round(player.resources, 4)})

    def _check_eliminations(self, players: list[_Player], turn: int, recorder: _EventRecorder) -> None:
        for player in players:
            if not player.alive:
                continue
            commander_lethal = commander_damage_is_lethal(player.commander_damage_received)
            if player.life <= 0 or commander_lethal or player.elimination_reason == "empty_library":
                alive_before = sum(item.alive for item in players)
                player.alive = False
                player.placement = alive_before
                player.eliminated_turn = turn
                if player.elimination_reason is None:
                    player.elimination_reason = "commander_damage" if commander_lethal else "life_total"
                recorder.emit("player_eliminated", actor_id=player.player_id, payload={"placement": player.placement, "reason": player.elimination_reason, "turn": turn})

    @staticmethod
    def _assign_abort_placements(players: list[_Player]) -> None:
        remaining = [player for player in players if player.placement is None]
        remaining.sort(key=lambda player: (player.life, player.threat(), len(player.hand)), reverse=True)
        for placement, player in enumerate(remaining, start=1):
            player.placement = placement

    @staticmethod
    def _card_multiset_hash(cards: Iterable[str]) -> str:
        payload = sorted(cards)
        return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()

    @classmethod
    def _zone_checkpoint(cls, player: _Player) -> dict[str, Any]:
        zone_cards = [
            *(card.oracle_name for card in player.library),
            *(card.oracle_name for card in player.hand),
            *(card.oracle_name for card in player.battlefield),
            *(card.oracle_name for card in player.graveyard),
            *(card.oracle_name for card in player.exile),
            *player.commanders.keys(),
        ]
        expected_cards = [card.oracle_name for card in player.deck.cards]
        commander_battlefield = sum(
            commander.on_battlefield for commander in player.commanders.values()
        )
        commander_command = len(player.commanders) - commander_battlefield
        counts = {
            "library": len(player.library),
            "hand": len(player.hand),
            "battlefield": len(player.battlefield),
            "graveyard": len(player.graveyard),
            "exile": len(player.exile),
            "command": commander_command,
            "commander_battlefield": commander_battlefield,
        }
        return {
            "player_id": player.player_id,
            "alive": player.alive,
            "counts": counts,
            "total_physical_cards": sum(counts.values()),
            "expected_deck_cards": len(expected_cards),
            "current_multiset_hash": cls._card_multiset_hash(zone_cards),
            "expected_multiset_hash": cls._card_multiset_hash(expected_cards),
        }

    @classmethod
    def _emit_state_checkpoint(
        cls,
        players: Iterable[_Player],
        recorder: _EventRecorder,
        *,
        reason: str,
        turn: int | None = None,
        global_turn: int | None = None,
    ) -> None:
        snapshots = [cls._zone_checkpoint(player) for player in players]
        recorder.emit(
            "state_checkpoint",
            payload={
                "reason": reason,
                "turn": turn,
                "global_turn": global_turn,
                "players": snapshots,
            },
        )

    @staticmethod
    def _record_archenemy_state(
        players: list[_Player],
        recorder: _EventRecorder,
        turn: int,
    ) -> None:
        living = [player for player in players if player.alive]
        if len(living) < 3:
            return
        ranked = sorted(living, key=lambda item: (item.threat(), item.player_id), reverse=True)
        leader, runner_up = ranked[0], ranked[1]
        if leader.threat() >= 6.0 and leader.threat() >= runner_up.threat() * 1.25:
            leader.archenemy_turns += 1
            recorder.emit(
                "archenemy_state",
                actor_id=leader.player_id,
                payload={
                    "turn": turn,
                    "threat": round(leader.threat(), 4),
                    "runner_up_threat": round(runner_up.threat(), 4),
                },
            )

    @staticmethod
    def _snapshot_metrics(player: _Player) -> dict[str, Any]:
        return {
            "life": round(player.life, 4),
            "hand": len(player.hand),
            "library": len(player.library),
            "lands": player.lands,
            "ramp": round(player.ramp_mana, 4),
            "board_power": round(player.board_power, 4),
            "engine_value": round(player.engine_value, 4),
            "resources": round(player.resources, 4),
            "threat": round(player.threat(), 4),
        }

    @staticmethod
    def _final_metrics(player: _Player) -> StructuralPlayerMetrics:
        return StructuralPlayerMetrics(
            player_id=player.player_id,
            deck_id=player.deck.deck_id,
            pilot_name=player.pilot.pilot_name,
            pilot_strength=player.pilot.config.strength.value,
            pilot_mode=player.pilot.config.mode.value,
            placement=player.placement or 1,
            life=player.life,
            mulligans=player.mulligans,
            lands_played=player.lands_played,
            ramp_resolved=player.ramp_resolved,
            cards_drawn=player.cards_drawn,
            commander_casts=player.commander_casts,
            commander_tax_paid=player.commander_tax_paid,
            first_commander_cast_turn=player.first_commander_cast_turn,
            commander_peak_power=dict(sorted(player.commander_peak_power.items())),
            ishai_peak_power=player.ishai_peak_power,
            korvold_cards_drawn=player.korvold_cards_drawn,
            hostile_target_events=player.hostile_target_events,
            archenemy_turns=player.archenemy_turns,
            was_archenemy=player.archenemy_turns > 0,
            removals_resolved=player.removals_resolved,
            counters_resolved=player.counters_resolved,
            protections_resolved=player.protections_resolved,
            wipes_resolved=player.wipes_resolved,
            graveyard_hate_resolved=player.graveyard_hate_resolved,
            recursions_resolved=player.recursions_resolved,
            engine_value=player.engine_value,
            resources_generated=player.resources_generated,
            normal_damage_dealt=player.normal_damage_dealt,
            commander_damage_dealt=player.commander_damage_dealt,
            eliminated_turn=player.eliminated_turn,
            elimination_reason=player.elimination_reason,
        )
