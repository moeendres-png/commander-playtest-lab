"""Seat bookkeeping, request accessors and the pilot's views of the game state."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from collections.abc import Mapping
from typing import Any, Literal, cast

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotCommanderView,
    PilotOpponentView,
    PilotStateView,
)

from ..full_game_pilot_views import (
    archenemy,
    board_summary,
    boardwipe_risk,
    card_view_fields,
    creature_power,
    entry_value,
    hand_role_counts,
    player_threat,
    priority_view_fields,
    resolve_player,
    stack_pressure,
)
from .common import (
    FullGameProtocolError,
    _RuntimePilot,
)


class _PolicyState:
    # #732: own stack objects, colour picks and other named choices.
    _OWN_CAST_MEMORY = 16
    # Same-named spells cast more than this in one turn are rare; repeated
    # activations (sacrifice outlets, pingers) legitimately go further.
    _TURN_SPELL_CAP = 3
    _TURN_ABILITY_CAP = 8
    # #802: distinct block declarations one engine frame (this blocker, these
    # attackers) is answered with before the pilot fails closed. See
    # ``_decide_blocks``: 1 = declare what pays, 2 = declare every block the
    # frame offers, 3 = declare nothing. An accepted declaration ends the
    # round (see ``_block_frame_asks``), so the ladder restarts per combat.
    _BLOCK_DECLARATION_ASK_LIMIT = 3

    # Most distinct priority windows remembered per seat per step for the
    # #718 recurrence bound. Bounded so the guard cannot itself grow without
    # limit inside a long step; the two-window ping-pong it exists for keeps
    # far fewer than this.
    _PRIORITY_STEP_WINDOW_LIMIT = 64

    def __init__(self, runtime_pilots: tuple[_RuntimePilot, ...], scenario_seed: int) -> None:
        if len(runtime_pilots) < 2 or len(runtime_pilots) > 6:
            raise ValueError("full-game policy requires two to six pilot bindings")
        seats = {item.binding.seat for item in runtime_pilots}
        if seats != set(range(1, len(runtime_pilots) + 1)):
            raise ValueError("full-game pilot bindings must cover seats 1..N exactly")
        self._pilots = {item.binding.seat: item for item in runtime_pilots}
        self._player_count = len(runtime_pilots)
        self.scenario_seed = scenario_seed
        # Per-state object index cache (initialized lazily in _find_object). The
        # indexed state is kept by reference: an id() is unique only among live
        # objects, so keying on it could serve the index of an already freed state.
        self._object_index: dict[str, dict[str, object]] = {}
        self._object_index_state: dict[str, object] | None = None
        self._mulligan_count: dict[int, int] = {
            seat: 0 for seat in range(1, len(runtime_pilots) + 1)
        }
        # No-progress guard memory for mana payments (per seat): last
        # decision fingerprint plus consecutive-repeat count. A mana
        # payment whose full offer (unpaid requirement, options, pool
        # amounts) repeats identically means no selection advanced it;
        # the guard then takes the engine-offered cancel (graceful abort).
        self._mana_last_fingerprint: dict[
            int, tuple[int, str, tuple[tuple[str, str, str], ...]]
        ] = {}
        self._mana_repeat_count: dict[int, int] = {}
        # Seats whose last mana-payment choice was a special mana action
        # (Delve, Convoke, Improvise): the next card choice pays for it.
        self._special_mana_pending: dict[int, bool] = {}
        # #920: the permanent whose activation the seat is paying for right now, from the last
        # mana_payment frame's source. A "sacrifice another creature" cost of a mana ability
        # inside that payment must not take it (Necron Overlord, plan seed 1, game seed 101).
        self._payment_source: dict[int, str] = {}
        # No-progress guard memory for priority windows (per seat): free
        # repeatable actions (Equip {0}, untap loops) can re-offer
        # identically forever with zero game-state progress. An identical
        # priority window (turn/phase/step/stack/pool/offer) repeating
        # consecutively means no selection advanced the game; the guard
        # then passes priority (always legal) so phases advance. #718 adds
        # the same bound for an identical window that RECURS inside one step
        # with a different window in between (see `_priority_step_windows`).
        self._priority_last_fingerprint: dict[
            int,
            tuple[
                int,
                object,
                object,
                object,
                tuple[str, ...],
                tuple[tuple[str, str], ...],
                tuple[tuple[str, str], ...],
            ],
        ] = {}
        self._priority_repeat_count: dict[int, int] = {}
        # #718: recurrence memory for priority windows (per seat). The
        # consecutive counter above only sees a window repeated back to back.
        # A free stack-using action (Equip {0}) instead alternates between two
        # windows -- empty stack, then the ability on the stack -- so the
        # consecutive guard never trips while the seat loops until the step
        # ends. These count occurrences of the SAME window fingerprint inside
        # the current (turn_number, phase, step) and reset when that key
        # changes, so a genuine change of step, stack, pool or offer still
        # starts a fresh window. Same fingerprint as the consecutive guard:
        # no observation the seat cannot already see enters the key.
        self._priority_step_key: dict[int, tuple[object, object, object]] = {}
        self._priority_step_windows: dict[int, list[tuple[object, int]]] = {}
        # Liveness guard memory for the repeating multikicker offer (per seat):
        # (source key, outcome, ordinal of the offer last answered, consecutive
        # Yes answers paid for it). A prompt with no "Pay N times" ordinal is
        # never capped and clears this memory, so an ordinary may-trigger
        # cannot inherit a chain it never took part in.
        self._boolean_repeat: dict[int, tuple[tuple[str, str], int, int]] = {}
        # #920: life the seat's Yes answers to the consecutive "Pay N life
        # instead of {X}?" asks of one Phyrexian payment have promised so far.
        self._phyrexian_life_promised: dict[int, int] = {}
        self._free_cast_failed: dict[int, tuple[object, set[str]]] = {}
        self._free_cast_last_yes: dict[int, str | None] = {}
        self._free_cast_refused: dict[int, object] = {}
        # Seats whose last "copied card to cast" choice (Mizzix's Mastery) picked nothing.
        self._copy_cast_declined: set[int] = set()
        # Slaughter the Strong asks for one creature at a time and toggles a creature that is
        # picked again: per seat, the engine ids picked so far in the running selection, and
        # the seats whose selection just ended (their next may-prompt must end it too).
        self._running_selection: dict[int, set[str]] = {}
        # Lim-Dul's Vault: per seat, the ability that asked and how many times in a row the seat
        # has paid a life to look at five more cards.
        self._life_dig_yes: dict[int, tuple[str, int]] = {}
        self._selection_ended: set[int] = set()
        # A "remove N counters from ..." cost being paid: per seat, the permanents chosen so far
        # and the counters each of them can give.
        self._counter_cost_progress: dict[int, dict[str, int]] = {}
        # Latch: once tripped, the seat keeps passing while the window
        # stays identical (a single forced pass would just resume the
        # loop). Any window change unlatches and resumes normal choice.
        self._priority_latched: dict[
            int,
            tuple[
                int,
                object,
                object,
                object,
                tuple[str, ...],
                tuple[tuple[str, str], ...],
                tuple[tuple[str, str], ...],
            ],
        ] = {}
        # #700: what the seat's last priority selection cost, as that option's
        # non-X mana value, keyed by the option's engine ``source_object_id``.
        # The ``announce_x`` frame the engine raises for the cast or activation
        # that follows carries no cost at all, so this is where that cost
        # survives the hop. It is consumed by the announce it was kept for.
        self._priority_cost_facts: dict[int, dict[str, int]] = {}
        # #920: the counters the seat's chosen activation can still remove, or
        # the untapped permanents it can still tap, for its X (see
        # ``option_x_counter_cap`` and ``option_x_tap_cap``), same key and
        # lifetime as ``_priority_cost_facts``.
        self._priority_x_counter_caps: dict[int, dict[str, int]] = {}
        # #815: X values this seat announced that the engine then refused to
        # let it pay (reversed over-announced X). Keyed by seat and the
        # announce frame's ``source_object_id``; the next announce for the
        # same source caps its band below the failed X, so the pilot cannot
        # re-announce the same unpayable value forever. Cleared on the seat's
        # next priority decision (a different action) like _priority_cost_facts.
        self._failed_x_announcements: dict[int, dict[str, int]] = {}
        # #732: names of the spells each seat itself cast recently, so the
        # pilot does not counter or target its own stack objects, and the
        # mana this seat's current payment still needs (for colour picks).
        self._own_cast_names: dict[int, list[str]] = {}
        self._last_unpaid_mana: dict[int, str] = {}
        self._turn_actions: dict[int, tuple[object, Counter[str]]] = {}
        # A cast whose payment this seat cancelled is not retried in the same
        # turn until more mana is visible: label -> mana visible at the cancel.
        self._last_priority_label: dict[int, str] = {}
        # The source of that action, for the mana abilities that must not pay for it (#920).
        self._last_priority_source: dict[int, str] = {}
        self._last_priority_visible_mana: dict[int, int] = {}
        self._failed_payments: dict[int, tuple[object, dict[str, int]]] = {}
        # #802: per seat, the turn it belongs to and how often the engine asked
        # each block frame (blocker -> offered attackers) within that turn. The
        # engine re-asks the whole declaration when its own check rejects the
        # configuration, so the count is what lets the pilot answer with a
        # different legal declaration instead of repeating a rejected one. The
        # bridge exposes no per-combat id (step and turn repeat across extra
        # combat phases), so the entry is cleared by the seat's next decision
        # of any other class -- the priority window that follows an ACCEPTED
        # declaration -- and by every new turn, or extra combats would read as
        # rejections (review P1).
        self._block_frame_asks: dict[int, tuple[object, dict[tuple[str, ...], int]]] = {}

    def _turn_action_cap(self, option: dict[str, Any]) -> int:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        return (
            self._TURN_SPELL_CAP if meta.get("ability_type") == "spell" else self._TURN_ABILITY_CAP
        )

    def _own_stack_names(self, seat: int) -> frozenset[str]:
        return frozenset(self._own_cast_names.get(seat, ()))

    def _remember_own_cast(
        self,
        seat: int,
        options: list[dict[str, Any]],
        selected: list[str],
        turn: object = None,
    ) -> None:
        chosen = set(selected)
        for option in options:
            if str(option.get("option_id")) not in chosen:
                continue
            if str(option.get("option_type")) not in {"pass_priority", "mana_ability"}:
                self._last_priority_label[seat] = str(option.get("label", ""))
                chosen_meta = option.get("metadata")
                source_id = (
                    str(chosen_meta.get("source_object_id") or "")
                    if isinstance(chosen_meta, dict)
                    else ""
                )
                if source_id:
                    self._last_priority_source[seat] = source_id
                else:
                    self._last_priority_source.pop(seat, None)
                tried = self._turn_actions.get(seat)
                if tried is None or tried[0] != turn:
                    tried = (turn, Counter())
                    self._turn_actions[seat] = tried
                tried[1][str(option.get("label", ""))] += 1
            metadata = option.get("metadata")
            meta = metadata if isinstance(metadata, dict) else {}
            if meta.get("ability_type") != "spell":
                continue
            name = str(meta.get("source_name") or "").strip().casefold()
            if not name:
                continue
            names = self._own_cast_names.setdefault(seat, [])
            names.append(name)
            del names[: -self._OWN_CAST_MEMORY]

    def _pilot_state(self, runtime: _RuntimePilot, state: dict[str, Any]) -> PilotStateView:
        actor = self._actor(state)
        actor_id = self._required_text(state, "actor_id")
        opponents: list[PilotOpponentView] = []
        players = state.get("players")
        if not isinstance(players, list):
            raise FullGameProtocolError("pilot_state.players must be an array")
        for raw in players:
            if not isinstance(raw, dict) or raw.get("player_id") == actor_id:
                continue
            # Threat assessment the way a Commander player does it: board
            # value (commanders, engines, big creatures), attacking power,
            # cards in hand and mana, discounted for a player near death.
            summary = board_summary(raw)
            graveyard_count = int(raw.get("graveyard_count", 0))
            life = float(raw.get("life", 40))
            threat = player_threat(raw, state)
            opponents.append(
                PilotOpponentView(
                    player_id=self._required_text(raw, "player_id"),
                    life=life,
                    threat=max(0.0, threat),
                    board_power=summary["creature_power"],
                    engine_value=summary["nonland_permanents"] * 0.35,
                    graveyard_size=graveyard_count,
                    hand_size=int(raw.get("hand_count", 0)),
                )
            )
        battlefield = actor.get("battlefield")
        battlefield_items = battlefield if isinstance(battlefield, list) else []
        hand = actor.get("hand")
        hand_items = hand if isinstance(hand, list) else []
        mana_pool = actor.get("mana_pool")
        mana = (
            sum(float(value) for value in mana_pool.values() if isinstance(value, (int, float)))
            if isinstance(mana_pool, dict)
            else 0.0
        )
        command = actor.get("command")
        command_items = command if isinstance(command, list) else []
        # #732: a commander is online when it is on its controller's
        # battlefield; the command zone alone no longer hides that.
        own_battlefield = {
            str(item.get("name", "")).casefold(): item
            for item in battlefield_items
            if isinstance(item, dict) and item.get("name")
        }
        status = state.get("commander_status")
        commander_entries = [
            entry
            for entry in (status if isinstance(status, list) else ())
            if isinstance(entry, dict) and str(entry.get("owner_id")) == actor_id
        ]
        commander_views: dict[str, PilotCommanderView] = {}
        for item in [*command_items, *commander_entries]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "Unknown commander"))
            if name.casefold() in commander_views:
                continue
            on_board = own_battlefield.get(name.casefold())
            facts = card_facts(name)
            base_cost = facts.mana_value if facts is not None else 0.0
            casts = int(item.get("casts_from_command", 0) or 0)
            commander_views[name.casefold()] = PilotCommanderView(
                name=name,
                base_cost=base_cost,
                next_cost=base_cost + 2.0 * casts,
                casts=casts,
                on_battlefield=on_board is not None,
                power=float(creature_power(on_board)) if on_board is not None else 0.0,
            )
        commanders = tuple(commander_views.values())
        own_summary = board_summary(actor)
        hand_name_list = [
            str(item.get("name", ""))
            for item in hand_items
            if isinstance(item, dict) and item.get("name")
        ]
        return PilotStateView(
            player_id=actor_id,
            deck_id=runtime.binding.deck_id,
            strategy=runtime.binding.strategy,
            turn=max(1, int(state.get("turn_number", 1))),
            pod_size=self._player_count,
            seat_position=runtime.binding.seat,
            life=float(actor.get("life", 40)),
            hand_size=int(actor.get("hand_count", len(hand_items))),
            mana_available=max(0.0, mana),
            lands=int(own_summary["lands"]),
            ramp_mana=0.0,
            resources=float(len(battlefield_items)),
            tokens=0.0,
            board_power=own_summary["creature_power"],
            engine_value=own_summary["nonland_permanents"] * 0.35,
            graveyard_size=int(actor.get("graveyard_count", 0)),
            battlefield_names=tuple(
                str(item.get("name", ""))
                for item in battlefield_items
                if isinstance(item, dict) and item.get("name")
            ),
            hand_names=tuple(hand_name_list),
            role_counts=hand_role_counts(hand_name_list),
            commanders=commanders,
            opponents=tuple(opponents),
            hidden_information_uncertainty=1.0,
            opponent_intent_uncertainty=1.0,
            unknown_opponent_fraction=1.0,
            opponents_to_act_before_next_turn=self._player_count - 1,
            archenemy_player_id=archenemy(state),
            boardwipe_risk=boardwipe_risk(state),
            stack_pressure=stack_pressure(state, self._own_stack_names(runtime.binding.seat)),
        )

    def _priority_action(self, option: dict[str, Any], state: dict[str, Any]) -> PilotActionView:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        source_name = str(meta.get("source_name") or option.get("label") or "XMage action")
        source_id = str(meta.get("source_object_id") or "")
        actor = self._actor(state)
        command = actor.get("command")
        command_items = command if isinstance(command, list) else []
        command_ids = {
            str(item.get("object_id")) for item in command_items if isinstance(item, dict)
        }
        action_kind: Literal["card", "commander"] = (
            "commander" if source_id in command_ids else "card"
        )
        fields, _withhold = priority_view_fields(
            option,
            state,
            own_stack_names=self._own_stack_names(int(state.get("seat", -1)) + 1),
        )
        view_metadata: dict[str, float | int | str | bool] = {
            **fields.pop("metadata", {}),
            "xmage_option_type": self._required_text(option, "option_type"),
        }
        view: dict[str, Any] = {
            "mana_cost": 0.0,
            "floor_value": 0.65,
            "immediate_impact": 0.45,
            **fields,
        }
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind=action_kind,
            card_name=source_name,
            commander_synergy=0.6 if action_kind == "commander" else 0.15,
            remaining_mana=self._actor_mana(actor),
            metadata=view_metadata,
            **view,
        )

    def _target_action(
        self,
        option: dict[str, Any],
        state: dict[str, Any],
        outcome: str,
    ) -> PilotActionView:
        option_id = self._required_text(option, "option_id")
        owner_id = self._object_owner(option_id, state)
        if owner_id is None:
            # A player target: the option carries the engine's player id, the
            # state the seat token; the seat in the label joins them.
            player = resolve_player(option_id, str(option.get("label", "")), state)
            owner_id = str(player.get("player_id")) if player is not None else None
        actor_id = self._required_text(state, "actor_id")
        target_threat = self._player_threat(owner_id, state)
        # Card-level threat: how dangerous is this specific permanent?
        # Combines player threat (context) with card threat (specific).
        # A high-value permanent controlled by a low-threat player is still
        # worth removing; a low-value permanent by a high-threat player less so.
        card_threat = self._card_threat(option_id, state)
        # Weighted combination: 70% card, 30% player (card matters more for removal)
        combined_threat = card_threat * 0.7 + target_threat * 0.3
        beneficial = outcome in {"benefit", "benefit_to_controller"}
        roles = frozenset({CardRole.PROTECTION}) if beneficial else frozenset({CardRole.REMOVAL})
        return PilotActionView(
            action_id=option_id,
            action_kind="protection" if beneficial else "removal_target",
            card_name=str(option.get("label", option_id)),
            roles=roles,
            role_strengths={role: 1.0 for role in roles},
            floor_value=0.3,
            immediate_impact=0.6,
            target_player_id=owner_id,
            target_threat=target_threat,
            threat_score=combined_threat,
            metadata={"target_is_actor_controlled": owner_id == actor_id},
        )

    def _combat_action(self, option: dict[str, Any], state: dict[str, Any]) -> PilotActionView:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        target_id = str(meta.get("defender_id") or meta.get("attacker_id") or "") or None
        player = resolve_player(target_id, str(option.get("label", "")), state)
        if player is not None:
            target_id = str(player.get("player_id"))
        target_threat = self._player_threat(target_id, state)
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind="combat_target",
            card_name=str(option.get("label", "Combat")),
            floor_value=0.35,
            immediate_impact=0.8,
            target_player_id=target_id,
            target_threat=target_threat,
            threat_score=target_threat,
            metadata={"target_life": self._player_life(target_id, state)},
        )

    def _semantic_action(self, option: dict[str, Any]) -> PilotActionView:
        label = str(option.get("label", "XMage option"))
        normalized = label.casefold()
        roles: set[CardRole] = set()
        if any(word in normalized for word in ("draw", "card advantage")):
            roles.add(CardRole.DRAW)
        if any(word in normalized for word in ("destroy", "exile", "damage", "counter target")):
            roles.add(CardRole.REMOVAL)
        if any(word in normalized for word in ("create", "token")):
            roles.add(CardRole.TOKEN_SOURCE)
        if any(word in normalized for word in ("return", "graveyard")):
            roles.add(CardRole.RECURSION)
        role_set = frozenset(roles)
        return PilotActionView(
            action_id=self._required_text(option, "option_id"),
            action_kind="card",
            card_name=label,
            roles=role_set,
            role_strengths={role: 1.0 for role in role_set},
            floor_value=0.4,
            immediate_impact=0.4 + min(0.5, len(role_set) * 0.15),
        )

    def _hand_action(self, card: dict[str, Any]) -> PilotActionView:
        name = self._required_text(card, "name")
        # #732: printed facts (land or not, mana value, roles) from the public
        # card catalog; a card the catalog does not know keeps the old
        # basic-land-name fallback.
        return PilotActionView(
            action_id=self._required_text(card, "object_id"),
            action_kind="card",
            card_name=name,
            floor_value=0.5,
            immediate_impact=0.3,
            **card_view_fields(name),
        )

    def _target_alignment(
        self,
        action: PilotActionView,
        state: dict[str, Any],
        outcome: str,
    ) -> float:
        actor_id = self._required_text(state, "actor_id")
        same = action.target_player_id == actor_id
        if outcome in {"benefit", "benefit_to_controller"}:
            return 8.0 if same else -8.0
        if outcome in {"detriment", "detriment_to_controller"}:
            return -8.0 if same else 8.0
        return 0.0

    def _object_owner(self, object_id: str, state: dict[str, Any]) -> str | None:
        players = state.get("players")
        if not isinstance(players, list):
            return None
        for raw in players:
            if not isinstance(raw, dict):
                continue
            player_id = str(raw.get("player_id", ""))
            if player_id == object_id:
                return player_id
            for zone in ("battlefield", "graveyard", "command", "hand"):
                items = raw.get(zone)
                if not isinstance(items, list):
                    continue
                if any(
                    isinstance(item, dict) and str(item.get("object_id", "")) == object_id
                    for item in items
                ):
                    return player_id
        return None

    def _find_object(self, object_id: str, state: dict[str, object]) -> dict[str, object] | None:
        """Find a card/permanent object by ID in any player's zones.

        Uses a per-state cache: the state dict identifies the game state, and
        the object index is rebuilt only when a different state dict arrives.
        """
        # Cache the object index per state to avoid O(n) search per lookup
        if self._object_index_state is not state:
            index: dict[str, dict[str, object]] = {}
            players = state.get("players")
            if isinstance(players, list):
                for raw in players:
                    if not isinstance(raw, dict):
                        continue
                    for zone in ("battlefield", "graveyard", "command", "hand", "stack"):
                        items = raw.get(zone)
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            if isinstance(item, dict):
                                oid = str(item.get("object_id", ""))
                                if oid:
                                    index[oid] = item
            self._object_index = index
            self._object_index_state = state
        return self._object_index.get(object_id)

    def _card_threat(self, object_id: str, state: dict[str, object]) -> float:
        """Threat score of a specific card/permanent (0.0 if not found)."""
        obj = self._find_object(object_id, state)
        if obj is None:
            return 0.0
        try:
            return float(entry_value(obj, state))
        except Exception:
            return 0.0

    def _player_threat(self, player_id: str | None, state: dict[str, Any]) -> float:
        if player_id is None:
            return 0.0
        player = self._player(player_id, state)
        return 0.0 if player is None else player_threat(player, state)

    def _player_life(self, player_id: str | None, state: dict[str, Any]) -> float:
        if player_id is None:
            return 40.0
        player = self._player(player_id, state)
        return 40.0 if player is None else float(player.get("life", 40))

    def _player(self, player_id: str, state: dict[str, Any]) -> dict[str, Any] | None:
        players = state.get("players")
        if not isinstance(players, list):
            return None
        return next(
            (
                raw
                for raw in players
                if isinstance(raw, dict) and str(raw.get("player_id")) == player_id
            ),
            None,
        )

    def _actor(self, state: dict[str, Any]) -> dict[str, Any]:
        actor_id = self._required_text(state, "actor_id")
        actor = self._player(actor_id, state)
        if actor is None:
            raise FullGameProtocolError("actor is absent from actor-scoped state")
        return actor

    def _without_payment_source(
        self,
        seat: int,
        decision_class: str,
        context: Mapping[str, object],
        options: list[dict[str, object]],
        *,
        asking: str,
        minimum: int,
    ) -> list[dict[str, object]]:
        """The sacrifice options, minus the permanent whose activation is being paid for.

        A mana ability that sacrifices another creature (Illuminor Szeras) asked inside the
        payment of an activation of Necron Overlord, and the pilot sacrificed the Overlord: its
        own {T} cost then found nothing to tap, the activation was reversed and the game
        stopped (plan seed 1, game seed 101, pod 024). The payment's source is kept whenever the
        rest cannot fill the choice (the only creature on offer, or fewer than the minimum:
        Breya, Etherium Shaper's "Sacrifice two artifacts" with one Thopter, plan seed 4, game
        seed 104, pod 014). A sacrifice that is the activation's own cost (`asking` is the
        payment's source) is an ordinary choice.
        """
        paying = self._payment_source.get(seat)
        if decision_class != "choose_object" or not paying or asking == paying:
            return options
        if str(context.get("outcome", "")).casefold() != "sacrifice":
            return options
        kept = []
        for option in options:
            metadata = option.get("metadata")
            if isinstance(metadata, dict) and str(metadata.get("object_id", "")) == paying:
                continue
            kept.append(option)
        return kept if kept and len(kept) >= minimum else options

    def _cheapest_object(self, options: list[dict[str, Any]]) -> str:
        def key(option: dict[str, Any]) -> tuple[float, str]:
            facts = card_facts(str(option.get("label", "")))
            return (facts.mana_value if facts is not None else 0.0, str(option.get("label", "")))

        return self._required_text(min(options, key=key), "option_id")

    @staticmethod
    def _actor_mana(actor: dict[str, Any]) -> float:
        mana = actor.get("mana_pool")
        if not isinstance(mana, dict):
            return 0.0
        return max(
            0.0,
            sum(float(value) for value in mana.values() if isinstance(value, (int, float))),
        )

    def _rng(self, decision_offset: int, decision_class: str, seat: int) -> random.Random:
        material = f"{self.scenario_seed}:{seat}:{decision_offset}:{decision_class}"
        digest = hashlib.sha256(material.encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    @staticmethod
    def _looks_like_basic_land(name: str) -> bool:
        return name.casefold() in {
            "plains",
            "island",
            "swamp",
            "mountain",
            "forest",
            "wastes",
        }

    @staticmethod
    def _legal_options(request: dict[str, Any]) -> list[dict[str, Any]]:
        raw = request.get("legal_options")
        if not isinstance(raw, list):
            raise FullGameProtocolError("decision legal_options must be an array")
        if not all(isinstance(item, dict) for item in raw):
            raise FullGameProtocolError("decision legal_options contains non-object entries")
        return cast(list[dict[str, Any]], raw)

    @staticmethod
    def _option_by_type(options: list[dict[str, Any]], option_type: str) -> dict[str, Any]:
        matches = [option for option in options if option.get("option_type") == option_type]
        if len(matches) != 1:
            raise FullGameProtocolError(
                f"expected exactly one {option_type!r} option; observed {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _require_offered(selected_id: str, options: list[dict[str, Any]], kind: str) -> str:
        """Fail closed when the pilot returns an unoffered option id."""
        offered = {str(option.get("option_id")) for option in options if isinstance(option, dict)}
        if selected_id not in offered:
            raise FullGameProtocolError(f"pilot returned unknown {kind}")
        return selected_id

    @staticmethod
    def _required_text(value: dict[str, Any], key: str) -> str:
        raw = value.get(key)
        text = "" if raw is None else str(raw).strip()
        if not text:
            raise FullGameProtocolError(f"required text field is blank: {key}")
        return text

    @staticmethod
    def _required_object(value: dict[str, Any], key: str) -> dict[str, Any]:
        raw = value.get(key)
        if not isinstance(raw, dict):
            raise FullGameProtocolError(f"required object field missing: {key}")
        return raw
