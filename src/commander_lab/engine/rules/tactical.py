from __future__ import annotations

import hashlib
import random
import uuid
from collections.abc import Callable
from typing import Any

from commander_lab.engine.action_validation import validate_action_proposal
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameEvent,
    GameState,
    GameStatus,
    InteractionSpec,
    InteractionValidation,
    LegalAction,
    PlayerState,
    RulesBackend,
    RulesDeckHandle,
    RulesDeckInput,
    RulesEngineAvailability,
    RulesEngineCapabilities,
    RulesEngineLog,
    RulesEngineProbe,
    RulesEngineResult,
    RulesGameRequest,
    RulesSession,
    TacticalScenario,
    TurnPhase,
    ValidationLevel,
    ZoneState,
)
from commander_lab.storage.hashing import sha256_value

from .base import RulesEngineAdapter, RulesEngineError


class TacticalRuleError(RulesEngineError):
    pass


def _bool(value: Any) -> bool:
    return bool(value)


def _commander_damage_result(damage: dict[str, int]) -> dict[str, Any]:
    maximum = max(damage.values(), default=0)
    loses = maximum >= 21
    return {
        "player_loses": loses,
        "loss_reason": "commander_damage" if loses else None,
        "maximum_single_commander_damage": maximum,
    }


class TacticalRuleOracle:
    """Deterministic, deliberately bounded tactical rule oracle.

    It implements only explicitly registered rule primitives. Passing a tactical case
    proves that the local model follows the encoded expected semantics; it is never
    promoted to ``external_rules_engine`` without an XMage or Forge observation.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "commander_tax": self._commander_tax,
            "commander_damage_check": self._commander_damage_check,
            "normal_damage_check": self._normal_damage_check,
            "combat_damage": self._combat_damage,
            "kediss_trigger": self._kediss_trigger,
            "jeska_triple": self._jeska_triple,
            "double_strike": self._double_strike,
            "cast_trigger_survives_counter": self._cast_trigger_survives_counter,
            "silence_restriction": self._silence_restriction,
            "indestructible_interaction": self._indestructible_interaction,
            "boros_charm_wipe": self._boros_charm_wipe,
            "toxic_deluge": self._toxic_deluge,
            "fire_covenant": self._fire_covenant,
            "massacre_wurm": self._massacre_wurm,
            "culling_ritual": self._culling_ritual,
            "farewell": self._farewell,
            "vandalblast": self._vandalblast,
            "wear_tear": self._wear_tear,
            "counter_commander": self._counter_commander,
            "commander_zone_change": self._commander_zone_change,
            "korvold_sacrifice": self._korvold_sacrifice,
            "sacrifice_cost": self._sacrifice_cost,
            "academy_manufactor": self._academy_manufactor,
            "killer_service": self._killer_service,
            "ophiomancer": self._ophiomancer,
            "idol_of_oblivion": self._idol_of_oblivion,
            "titania": self._titania,
            "ramunap": self._ramunap,
            "splendid_reclamation": self._splendid_reclamation,
            "aftermath_analyst": self._aftermath_analyst,
            "tireless_provisioner": self._tireless_provisioner,
            "tireless_tracker": self._tireless_tracker,
            "mirkwood_bats": self._mirkwood_bats,
            "mayhem_devil": self._mayhem_devil,
            "mazirek": self._mazirek,
            "braids": self._braids,
            "bontu": self._bontu,
            "pitiless_plunderer": self._pitiless_plunderer,
            "goblin_bombardment": self._goblin_bombardment,
            "rakdos_charm": self._rakdos_charm,
            "soul_guide_lantern": self._soul_guide_lantern,
            "bojuka_bog": self._bojuka_bog,
            "combat_draw": self._combat_draw,
            "ishai_trigger": self._ishai_trigger,
            "veyran_trigger": self._veyran_trigger,
            "guttersnipe": self._guttersnipe,
            "kykar": self._kykar,
            "storm_kiln_artist": self._storm_kiln_artist,
            "archmage_emeritus": self._archmage_emeritus,
            "whirlwind_of_thought": self._whirlwind_of_thought,
            "narset_draw_limit": self._narset_draw_limit,
            "esior_tax": self._esior_tax,
            "phase_out": self._phase_out,
            "lofty_denial": self._lofty_denial,
            "wash_away": self._wash_away,
            "offer": self._offer,
            "dovins_veto": self._dovins_veto,
            "winds_of_rath": self._winds_of_rath,
            "lorans_escape": self._lorans_escape,
            "equipment_shroud_hexproof": self._equipment_shroud_hexproof,
            "apnap_trigger_order": self._apnap_trigger_order,
            "stack_lifo": self._stack_lifo,
            "zero_toughness": self._zero_toughness,
            "token_zone_change": self._token_zone_change,
        }

    @property
    def supported_rules(self) -> frozenset[str]:
        return frozenset(self._handlers)

    def evaluate(self, rule: str, input_state: dict[str, Any]) -> dict[str, Any]:
        try:
            handler = self._handlers[rule]
        except KeyError as exc:
            raise TacticalRuleError(f"unsupported tactical rule primitive: {rule}") from exc
        return handler(dict(input_state))

    def validate(self, spec: InteractionSpec) -> InteractionValidation:
        observed = self.evaluate(spec.rule, spec.input_state)
        mismatches = tuple(
            f"{key}: expected {spec.expected_normalized.get(key)!r}, observed {observed.get(key)!r}"
            for key in spec.comparison_keys
            if spec.expected_normalized.get(key) != observed.get(key)
        )
        return InteractionValidation(
            interaction_id=spec.interaction_id,
            level=ValidationLevel.TACTICAL_ORACLE,
            passed=not mismatches,
            backend=RulesBackend.TACTICAL,
            expected={key: spec.expected_normalized.get(key) for key in spec.comparison_keys},
            observed={key: observed.get(key) for key in spec.comparison_keys},
            comparison_keys=spec.comparison_keys,
            mismatches=mismatches,
            backend_version="tactical-0.8.0",
        )

    @staticmethod
    def _commander_tax(s: dict[str, Any]) -> dict[str, Any]:
        tax = 2 * int(s.get("prior_command_zone_casts", 0))
        base = int(s.get("printed_generic_cost", s.get("printed_mana_value", 0)))
        return {"commander_tax": tax, "total_cast_cost": base + tax, "legal": True}

    @staticmethod
    def _commander_damage_check(s: dict[str, Any]) -> dict[str, Any]:
        return _commander_damage_result({str(k): int(v) for k, v in s["commander_damage"].items()})

    @staticmethod
    def _normal_damage_check(s: dict[str, Any]) -> dict[str, Any]:
        life_after = int(s["life_before"]) - int(s["damage"])
        return {
            "life_after": life_after,
            "player_loses": life_after <= 0,
            "loss_reason": "life_total" if life_after <= 0 else None,
        }

    @staticmethod
    def _combat_damage(s: dict[str, Any]) -> dict[str, Any]:
        power = int(s["power"])
        multiplier = int(s.get("multiplier", 1))
        strikes = 2 if s.get("double_strike") else 1
        damage = power * multiplier * strikes
        is_commander = _bool(s.get("is_commander"))
        return {
            "normal_damage": damage,
            "commander_damage": damage if is_commander else 0,
            "damage_events": strikes,
        }

    @staticmethod
    def _kediss_trigger(s: dict[str, Any]) -> dict[str, Any]:
        combat_damage = int(s["commander_combat_damage"])
        other_opponents = max(0, int(s["opponent_count"]) - 1)
        triggered = combat_damage > 0
        return {
            "triggered": triggered,
            "other_opponents_hit": other_opponents if triggered else 0,
            "normal_damage_each": combat_damage if triggered else 0,
            "additional_commander_damage": 0,
        }

    @staticmethod
    def _jeska_triple(s: dict[str, Any]) -> dict[str, Any]:
        base = int(s["combat_damage"])
        is_commander = _bool(s.get("is_commander"))
        return {
            "damage": base * 3,
            "commander_damage": base * 3 if is_commander else 0,
        }

    @staticmethod
    def _double_strike(s: dict[str, Any]) -> dict[str, Any]:
        power = int(s["power"])
        blocked_first = _bool(s.get("blocked_first_strike"))
        survives = _bool(s.get("survives_first_strike", True))
        first = 0 if blocked_first else power
        regular = power if survives and not _bool(s.get("blocked_regular")) else 0
        total = first + regular
        return {
            "first_strike_damage": first,
            "regular_damage": regular,
            "total_damage": total,
            "commander_damage": total if s.get("is_commander") else 0,
        }

    @staticmethod
    def _cast_trigger_survives_counter(s: dict[str, Any]) -> dict[str, Any]:
        trigger_created = _bool(s.get("trigger_on_cast", True))
        spell_countered = _bool(s.get("spell_countered", True))
        return {
            "trigger_created": trigger_created,
            "spell_countered": spell_countered,
            "trigger_remains_on_stack": trigger_created,
        }

    @staticmethod
    def _silence_restriction(s: dict[str, Any]) -> dict[str, Any]:
        affected = _bool(s.get("silence_resolved")) and _bool(s.get("same_turn", True))
        return {
            "can_cast_spell": not affected,
            "can_activate_ability": True,
            "can_play_land": True,
        }

    @staticmethod
    def _indestructible_interaction(s: dict[str, Any]) -> dict[str, Any]:
        effect = str(s["effect"])
        indestructible = _bool(s.get("indestructible"))
        toughness = int(s.get("toughness", 1))
        minus = int(s.get("minus_toughness", 0))
        lethal_damage = _bool(s.get("lethal_damage"))
        if effect == "destroy":
            survives = indestructible
        elif effect == "damage":
            survives = indestructible if lethal_damage else True
        elif effect == "minus":
            survives = toughness - minus > 0
        elif effect in {"exile", "sacrifice", "bounce"}:
            survives = False
        else:
            raise TacticalRuleError(f"unknown indestructible interaction effect: {effect}")
        return {"survives": survives, "destination": "battlefield" if survives else effect}

    @staticmethod
    def _boros_charm_wipe(s: dict[str, Any]) -> dict[str, Any]:
        own = int(s["own_creatures"])
        opponent = int(s["opponent_creatures"])
        return {
            "own_creatures_survive": own if s.get("boros_charm_resolved") else 0,
            "opponent_creatures_survive": 0,
            "creatures_destroyed": opponent + (0 if s.get("boros_charm_resolved") else own),
        }

    @staticmethod
    def _toxic_deluge(s: dict[str, Any]) -> dict[str, Any]:
        x = int(s["x"])
        toughnesses = [int(v) for v in s["toughnesses"]]
        survivors = [value for value in toughnesses if value - x > 0]
        return {
            "life_paid": x,
            "creatures_died": len(toughnesses) - len(survivors),
            "survivor_toughnesses": [value - x for value in survivors],
            "indestructible_relevant": False,
        }

    @staticmethod
    def _fire_covenant(s: dict[str, Any]) -> dict[str, Any]:
        assignments = [int(v) for v in s["damage_assignments"]]
        toughnesses = [int(v) for v in s["toughnesses"]]
        indestructible = [bool(v) for v in s.get("indestructible", [False] * len(toughnesses))]
        dead = sum(
            1
            for damage, toughness, protected in zip(
                assignments, toughnesses, indestructible, strict=True
            )
            if damage >= toughness and not protected
        )
        return {"life_paid": sum(assignments), "creatures_died": dead}

    @staticmethod
    def _massacre_wurm(s: dict[str, Any]) -> dict[str, Any]:
        toughnesses = [int(v) for v in s["opponent_toughnesses"]]
        died = sum(1 for value in toughnesses if value - 2 <= 0)
        return {"creatures_died": died, "controller_life_loss": died * 2}

    @staticmethod
    def _culling_ritual(s: dict[str, Any]) -> dict[str, Any]:
        permanents = list(s["permanents"])
        destroyed = [
            item
            for item in permanents
            if not item.get("is_land", False) and int(item.get("mana_value", 0)) <= 2
        ]
        return {"destroyed": len(destroyed), "mana_generated": len(destroyed)}

    @staticmethod
    def _farewell(s: dict[str, Any]) -> dict[str, Any]:
        modes = set(s["modes"])
        return {
            "creatures_exiled": int(s.get("creatures", 0)) if "creatures" in modes else 0,
            "artifacts_exiled": int(s.get("artifacts", 0)) if "artifacts" in modes else 0,
            "enchantments_exiled": int(s.get("enchantments", 0)) if "enchantments" in modes else 0,
            "graveyards_exiled": int(s.get("graveyard_cards", 0)) if "graveyards" in modes else 0,
            "indestructible_relevant": False,
        }

    @staticmethod
    def _vandalblast(s: dict[str, Any]) -> dict[str, Any]:
        overloaded = _bool(s.get("overloaded"))
        opponent_artifacts = int(s.get("opponent_artifacts", 0))
        return {
            "destroyed": opponent_artifacts if overloaded else min(1, opponent_artifacts),
            "own_artifacts_destroyed": 0,
            "uses_targets": not overloaded,
        }

    @staticmethod
    def _wear_tear(s: dict[str, Any]) -> dict[str, Any]:
        fused = _bool(s.get("fused"))
        cast_from_hand = _bool(s.get("cast_from_hand", True))
        return {
            "legal": not fused or cast_from_hand,
            "artifact_destroyed": _bool(s.get("artifact_target")),
            "enchantment_destroyed": _bool(s.get("enchantment_target"))
            and (fused or not s.get("artifact_target")),
            "spells_cast": 1,
        }

    @staticmethod
    def _counter_commander(s: dict[str, Any]) -> dict[str, Any]:
        move_to_command = _bool(s.get("move_to_command_zone", True))
        return {
            "spell_countered": True,
            "graveyard_entry": True,
            "final_zone": "command" if move_to_command else "graveyard",
            "commander_tax_increments": False,
        }

    @staticmethod
    def _commander_zone_change(s: dict[str, Any]) -> dict[str, Any]:
        origin = str(s["from_zone"])
        destination = str(s["to_zone"])
        choose_command = _bool(s.get("choose_command_zone", True))
        dies_trigger = origin == "battlefield" and destination == "graveyard"
        method = "replacement" if destination in {"hand", "library"} else "state_based_action"
        return {
            "dies_triggered": dies_trigger,
            "final_zone": "command" if choose_command else destination,
            "command_move_method": method if choose_command else None,
        }

    @staticmethod
    def _korvold_sacrifice(s: dict[str, Any]) -> dict[str, Any]:
        available = int(s.get("other_permanents", 0))
        sacrifices = 1 if available > 0 else 0
        return {
            "permanents_sacrificed": sacrifices,
            "cards_drawn": sacrifices,
            "counters_added": sacrifices,
            "trigger_fizzles": False,
        }

    @staticmethod
    def _sacrifice_cost(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "cost_paid_before_priority": True,
            "sacrificed_permanent_zone": "graveyard",
            "ability_on_stack": True,
            "can_prevent_cost_with_response": False,
        }

    @staticmethod
    def _academy_manufactor(s: dict[str, Any]) -> dict[str, Any]:
        quantity = int(s.get("quantity", 1))
        return {"clues": quantity, "foods": quantity, "treasures": quantity}

    @staticmethod
    def _killer_service(s: dict[str, Any]) -> dict[str, Any]:
        opponents = int(s["opponent_count"])
        manufactor = _bool(s.get("academy_manufactor"))
        return {
            "foods": opponents,
            "clues": opponents if manufactor else 0,
            "treasures": opponents if manufactor else 0,
            "total_tokens": opponents * (3 if manufactor else 1),
        }

    @staticmethod
    def _ophiomancer(s: dict[str, Any]) -> dict[str, Any]:
        has_snake = _bool(s.get("has_snake"))
        return {"snakes_created": 0 if has_snake else 1}

    @staticmethod
    def _idol_of_oblivion(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "can_activate_draw": _bool(s.get("created_token_this_turn")),
            "cards_drawn": 1 if s.get("created_token_this_turn") else 0,
        }

    @staticmethod
    def _titania(s: dict[str, Any]) -> dict[str, Any]:
        lands_died = int(s.get("lands_from_battlefield_to_graveyard", 0))
        return {
            "land_returned": 1 if s.get("land_in_graveyard") else 0,
            "elementals_created": lands_died,
            "elemental_power": 5,
            "elemental_toughness": 3,
        }

    @staticmethod
    def _ramunap(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "can_play_land_from_graveyard": _bool(s.get("land_in_graveyard"))
            and int(s.get("land_plays_remaining", 1)) > 0,
            "uses_land_play": True,
        }

    @staticmethod
    def _splendid_reclamation(s: dict[str, Any]) -> dict[str, Any]:
        lands = int(s.get("lands_in_graveyard", 0))
        return {"lands_returned": lands, "enter_tapped": True}

    @staticmethod
    def _aftermath_analyst(s: dict[str, Any]) -> dict[str, Any]:
        lands = int(s.get("lands_in_graveyard", 0))
        return {"analyst_sacrificed": True, "lands_returned": lands, "enter_tapped": True}

    @staticmethod
    def _tireless_provisioner(s: dict[str, Any]) -> dict[str, Any]:
        landfall = int(s.get("landfall_events", 1))
        choice = str(s.get("choice", "treasure"))
        return {
            "foods": landfall if choice == "food" else 0,
            "treasures": landfall if choice == "treasure" else 0,
        }

    @staticmethod
    def _tireless_tracker(s: dict[str, Any]) -> dict[str, Any]:
        landfall = int(s.get("landfall_events", 1))
        clues_sacrificed = int(s.get("clues_sacrificed", 0))
        return {
            "clues_created": landfall,
            "counters_added": clues_sacrificed,
            "cards_drawn": clues_sacrificed,
        }

    @staticmethod
    def _mirkwood_bats(s: dict[str, Any]) -> dict[str, Any]:
        events = int(s.get("tokens_created", 0)) + int(s.get("tokens_sacrificed", 0))
        opponents = int(s.get("opponent_count", 0))
        return {
            "triggers": events,
            "life_loss_each_opponent": events,
            "total_life_loss": events * opponents,
        }

    @staticmethod
    def _mayhem_devil(s: dict[str, Any]) -> dict[str, Any]:
        sacrifices = int(s.get("permanents_sacrificed", 0))
        return {"triggers": sacrifices, "damage_available": sacrifices}

    @staticmethod
    def _mazirek(s: dict[str, Any]) -> dict[str, Any]:
        sacrifices = int(s.get("sacrifice_events", 0))
        creatures = int(s.get("creatures_controlled", 0))
        return {
            "triggers": sacrifices,
            "counters_each": sacrifices,
            "total_counters": sacrifices * creatures,
        }

    @staticmethod
    def _braids(s: dict[str, Any]) -> dict[str, Any]:
        declines = sum(1 for value in s.get("opponents_sacrifice_same_type", []) if not value)
        return {"opponents_lost_life": declines, "life_loss_each": 2, "cards_drawn": declines}

    @staticmethod
    def _bontu(s: dict[str, Any]) -> dict[str, Any]:
        count = int(s.get("permanents_sacrificed", 0))
        return {"permanents_sacrificed": count, "cards_drawn": count}

    @staticmethod
    def _pitiless_plunderer(s: dict[str, Any]) -> dict[str, Any]:
        deaths = int(s.get("other_nontoken_creatures_you_control_died", 0))
        return {"treasures_created": deaths}

    @staticmethod
    def _goblin_bombardment(s: dict[str, Any]) -> dict[str, Any]:
        creatures = int(s.get("creatures_sacrificed", 1))
        return {"creatures_sacrificed": creatures, "damage": creatures, "targets": creatures}

    @staticmethod
    def _rakdos_charm(s: dict[str, Any]) -> dict[str, Any]:
        mode = str(s["mode"])
        return {
            "artifact_destroyed": mode == "artifact",
            "graveyard_cards_exiled": int(s.get("graveyard_cards", 0))
            if mode == "graveyard"
            else 0,
            "creature_damage_to_controller": int(s.get("creatures_controlled", 0))
            if mode == "creatures"
            else 0,
        }

    @staticmethod
    def _soul_guide_lantern(s: dict[str, Any]) -> dict[str, Any]:
        mode = str(s["mode"])
        return {
            "single_card_exiled": 1 if mode == "etb" and s.get("target_available", True) else 0,
            "opponent_graveyards_exiled": int(s.get("opponent_graveyard_cards", 0))
            if mode == "mass_exile"
            else 0,
            "cards_drawn": 1 if mode == "draw" else 0,
            "lantern_sacrificed": mode in {"mass_exile", "draw"},
        }

    @staticmethod
    def _bojuka_bog(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "enters_tapped": True,
            "graveyard_cards_exiled": int(s.get("target_graveyard_cards", 0)),
        }

    @staticmethod
    def _combat_draw(s: dict[str, Any]) -> dict[str, Any]:
        events = int(s.get("combat_damage_events_to_player", 0))
        return {
            "cards_drawn": events,
            "life_gained": int(s.get("damage", 0)) if s.get("lifelink") else 0,
        }

    @staticmethod
    def _ishai_trigger(s: dict[str, Any]) -> dict[str, Any]:
        opponent_spells = int(s.get("opponent_spells_cast", 0))
        own_spells = int(s.get("own_spells_cast", 0))
        return {"counters_added": opponent_spells, "own_spells_trigger": own_spells > 0 and False}

    @staticmethod
    def _veyran_trigger(s: dict[str, Any]) -> dict[str, Any]:
        base_triggers = int(s.get("base_triggers", 1))
        events = int(s.get("instant_sorcery_cast_or_copied", 1))
        return {"total_triggers": base_triggers * events * 2}

    @staticmethod
    def _guttersnipe(s: dict[str, Any]) -> dict[str, Any]:
        casts = int(s.get("instant_sorcery_casts", 0))
        opponents = int(s.get("opponent_count", 0))
        return {"damage_each_opponent": 2 * casts, "total_damage": 2 * casts * opponents}

    @staticmethod
    def _kykar(s: dict[str, Any]) -> dict[str, Any]:
        spells = int(s.get("noncreature_spells_cast", 0))
        sacrificed = min(
            int(s.get("spirits_sacrificed", 0)), int(s.get("spirits_available", spells))
        )
        return {"spirits_created": spells, "red_mana_generated": sacrificed}

    @staticmethod
    def _storm_kiln_artist(s: dict[str, Any]) -> dict[str, Any]:
        events = int(s.get("instant_sorcery_cast_or_copied", 0))
        return {"treasures_created": events}

    @staticmethod
    def _archmage_emeritus(s: dict[str, Any]) -> dict[str, Any]:
        events = int(s.get("instant_sorcery_cast_or_copied", 0))
        return {"cards_drawn": events}

    @staticmethod
    def _whirlwind_of_thought(s: dict[str, Any]) -> dict[str, Any]:
        casts = int(s.get("noncreature_spells_cast", 0))
        copies = int(s.get("spell_copies", 0))
        return {"cards_drawn": casts, "copies_trigger": copies > 0 and False}

    @staticmethod
    def _narset_draw_limit(s: dict[str, Any]) -> dict[str, Any]:
        already = int(s.get("cards_drawn_this_turn", 0))
        attempted = int(s.get("attempted_additional_draws", 0))
        allowed = max(0, min(attempted, 1 - already))
        return {
            "additional_draws_allowed": allowed,
            "additional_draws_prevented": attempted - allowed,
        }

    @staticmethod
    def _esior_tax(s: dict[str, Any]) -> dict[str, Any]:
        opponent = _bool(s.get("source_controlled_by_opponent", True))
        targets_commander = _bool(s.get("targets_your_commander", True))
        tax = 3 if opponent and targets_commander else 0
        return {"additional_cost": tax, "legal_if_paid": True}

    @staticmethod
    def _phase_out(s: dict[str, Any]) -> dict[str, Any]:
        wipe = _bool(s.get("wipe_resolves", True))
        return {
            "affected_by_wipe": False if wipe else False,
            "returns_next_untap": True,
            "attachments_phase_out": True,
        }

    @staticmethod
    def _lofty_denial(s: dict[str, Any]) -> dict[str, Any]:
        tax = 4 if s.get("control_flying_creature") else 1
        paid = int(s.get("mana_paid", 0)) >= tax
        return {"tax": tax, "spell_countered": not paid}

    @staticmethod
    def _wash_away(s: dict[str, Any]) -> dict[str, Any]:
        cleaved = _bool(s.get("cleaved"))
        cast_from_hand = _bool(s.get("target_cast_from_hand"))
        legal = cleaved or not cast_from_hand
        return {"legal_target": legal, "spell_countered": legal}

    @staticmethod
    def _offer(s: dict[str, Any]) -> dict[str, Any]:
        noncreature = _bool(s.get("target_is_noncreature_spell", True))
        return {
            "spell_countered": noncreature,
            "treasures_created_for_controller": 2 if noncreature else 0,
        }

    @staticmethod
    def _dovins_veto(s: dict[str, Any]) -> dict[str, Any]:
        noncreature = _bool(s.get("target_is_noncreature_spell", True))
        return {
            "legal_target": noncreature,
            "spell_countered": noncreature,
            "veto_can_be_countered": False,
        }

    @staticmethod
    def _winds_of_rath(s: dict[str, Any]) -> dict[str, Any]:
        enchanted = int(s.get("enchanted_creatures", 0))
        unenchanted = int(s.get("unenchanted_creatures", 0))
        return {"enchanted_survive": enchanted, "unenchanted_destroyed": unenchanted}

    @staticmethod
    def _lorans_escape(s: dict[str, Any]) -> dict[str, Any]:
        return {"hexproof": True, "indestructible": True, "scry": 1, "counter_added": 0}

    @staticmethod
    def _equipment_shroud_hexproof(s: dict[str, Any]) -> dict[str, Any]:
        equipment = str(s["equipment"])
        own_targeted_spell = _bool(s.get("own_targeted_spell", True))
        if equipment == "Lightning Greaves":
            can_target = False
            protection = "shroud"
            equip_cost = 0
        elif equipment == "Swiftfoot Boots":
            can_target = own_targeted_spell
            protection = "hexproof"
            equip_cost = 1
        else:
            raise TacticalRuleError(f"unsupported equipment: {equipment}")
        return {
            "can_target_with_own_spell": can_target,
            "protection": protection,
            "equip_cost": equip_cost,
        }

    @staticmethod
    def _apnap_trigger_order(s: dict[str, Any]) -> dict[str, Any]:
        active = list(s.get("active_player_triggers", []))
        nonactive = [list(group) for group in s.get("nonactive_player_triggers_in_turn_order", [])]
        stack_bottom_to_top = active + [item for group in nonactive for item in group]
        return {
            "stack_bottom_to_top": stack_bottom_to_top,
            "resolves_first": stack_bottom_to_top[-1] if stack_bottom_to_top else None,
        }

    @staticmethod
    def _stack_lifo(s: dict[str, Any]) -> dict[str, Any]:
        stack_bottom_to_top = list(s.get("stack_bottom_to_top", []))
        return {"resolution_order": list(reversed(stack_bottom_to_top))}

    @staticmethod
    def _zero_toughness(s: dict[str, Any]) -> dict[str, Any]:
        toughness = int(s["toughness"])
        return {
            "put_into_graveyard": toughness <= 0,
            "is_destroyed": False,
            "indestructible_relevant": False,
        }

    @staticmethod
    def _token_zone_change(s: dict[str, Any]) -> dict[str, Any]:
        destination = str(s["destination"])
        return {
            "enters_destination": True,
            "ceases_to_exist_next_sba": destination != "battlefield",
        }


class TacticalRulesAdapter(RulesEngineAdapter):
    """Local deterministic tactical adapter for bounded rules-critical scenarios."""

    def __init__(self) -> None:
        self.oracle = TacticalRuleOracle()
        self._decks: dict[str, RulesDeckInput] = {}
        self._sessions: dict[str, RulesSession] = {}
        self._scenarios: dict[str, TacticalScenario] = {}
        self._logs: dict[str, list[GameEvent]] = {}

    def probe(self) -> RulesEngineProbe:
        return RulesEngineProbe(
            backend=RulesBackend.TACTICAL,
            availability=RulesEngineAvailability.AVAILABLE,
            backend_version="tactical-0.8.0",
            capabilities=RulesEngineCapabilities(
                deck_loading=True,
                commander_games=True,
                deterministic_seed=True,
                reproducible_starting_state=True,
                scenario_injection=True,
                legal_action_query=True,
                action_submission=True,
                event_logs=True,
                game_logs=True,
                multiplayer=True,
                maximum_players=10,
                notes=(
                    "bounded tactical oracle; not a complete Magic rules engine",
                    "passing cases are tactical_oracle, never external_rules_engine",
                ),
            ),
        )

    def load_deck(self, deck: RulesDeckInput) -> RulesDeckHandle:
        deck_hash = deck.deck_hash or sha256_value(deck.model_dump(mode="json", exclude_none=True))
        handle_id = f"tactical-deck-{deck_hash[:16]}"
        self._decks[handle_id] = deck.model_copy(update={"deck_hash": deck_hash})
        return RulesDeckHandle(
            backend=RulesBackend.TACTICAL,
            handle_id=handle_id,
            deck_id=deck.deck_id,
            deck_hash=deck_hash,
            commander_names=deck.commander_names,
            accepted_cards=len(deck.mainboard) + len(deck.commander_names),
        )

    def start_commander_game(self, request: RulesGameRequest) -> RulesSession:
        missing = [handle for handle in request.deck_handles if handle not in self._decks]
        if missing:
            raise TacticalRuleError(f"unknown tactical deck handles: {missing}")
        rng = random.Random(request.seed or 0)
        players: list[PlayerState] = []
        for seat, handle in enumerate(request.deck_handles):
            deck = self._decks[handle]
            library = list(deck.mainboard)
            rng.shuffle(library)
            hand = tuple(library[:7])
            remaining = tuple(library[7:])
            players.append(
                PlayerState(
                    player_id=f"p{seat + 1}",
                    seat=seat,
                    life=request.starting_life,
                    zones=ZoneState(
                        library=remaining,
                        hand=hand,
                        command=deck.commander_names,
                    ),
                )
            )
        active = players[request.starting_player_seat].player_id
        pass_action = LegalAction(
            action_id="pass-priority",
            actor_id=active,
            action_type=ActionType.PASS_PRIORITY,
        )
        state = GameState(
            game_id=request.game_id,
            seed=request.seed or 0,
            status=GameStatus.IN_PROGRESS,
            turn_number=1,
            active_player_id=active,
            priority_player_id=active,
            phase=TurnPhase.PRECOMBAT_MAIN,
            players=tuple(players),
            legal_actions=(pass_action,),
        )
        session_id = f"tactical-{uuid.uuid4()}"
        session = RulesSession(
            backend=RulesBackend.TACTICAL,
            session_id=session_id,
            game_id=request.game_id,
            state=state,
            seed=request.seed,
            deck_handles=request.deck_handles,
            created_from="game",
        )
        self._sessions[session_id] = session
        self._logs[session_id] = [
            self._event(
                state,
                0,
                "game_started",
                None,
                {"seed": request.seed, "decks": list(request.deck_handles)},
            )
        ]
        return session

    def create_scenario(self, scenario: TacticalScenario) -> RulesSession:
        session_id = f"tactical-scenario-{uuid.uuid4()}"
        self._scenarios[session_id] = scenario
        session = RulesSession(
            backend=RulesBackend.TACTICAL,
            session_id=session_id,
            game_id=scenario.state.game_id,
            state=scenario.state,
            seed=scenario.state.seed,
            scenario_id=scenario.scenario_id,
            created_from="scenario",
        )
        self._sessions[session_id] = session
        self._logs[session_id] = [
            self._event(
                scenario.state,
                0,
                "scenario_created",
                None,
                {"scenario_id": scenario.scenario_id, "rule": scenario.rule},
            )
        ]
        return session

    def get_state(self, session_id: str) -> GameState:
        return self._require_session(session_id).state

    def get_legal_actions(self, session_id: str) -> tuple[LegalAction, ...]:
        return self.get_state(session_id).legal_actions

    def submit_action(self, session_id: str, proposal: ActionProposal) -> GameState:
        session = self._require_session(session_id)
        legal = validate_action_proposal(session.state, proposal)
        pre_hash = sha256_value(session.state)
        next_state = self._apply_action(session_id, session.state, legal, proposal)
        post_hash = sha256_value(next_state)
        sequence = len(self._logs[session_id])
        self._logs[session_id].append(
            GameEvent(
                event_id=f"{session.state.game_id}:{sequence}",
                game_id=session.state.game_id,
                sequence=sequence,
                event_type="action_submitted",
                actor_id=proposal.actor_id,
                payload={
                    "legal_action_id": legal.action_id,
                    "action_type": legal.action_type.value,
                    "proposal": proposal.model_dump(mode="json", exclude_none=True),
                },
                pre_state_hash=pre_hash,
                post_state_hash=post_hash,
            )
        )
        self._sessions[session_id] = session.model_copy(update={"state": next_state})
        return next_state

    def get_logs(self, session_id: str) -> RulesEngineLog:
        events = tuple(self._logs.get(session_id, ()))
        digest = hashlib.sha256(
            "\n".join(event.model_dump_json(exclude_none=True) for event in events).encode()
        ).hexdigest()
        return RulesEngineLog(
            backend=RulesBackend.TACTICAL,
            session_id=session_id,
            events=events,
            log_sha256=digest,
        )

    def get_result(self, session_id: str) -> RulesEngineResult:
        session = self._require_session(session_id)
        scenario = self._scenarios.get(session_id)
        normalized: dict[str, Any] = {}
        if scenario is not None and scenario.rule is not None:
            normalized = self.oracle.evaluate(scenario.rule, scenario.input_state)
        return RulesEngineResult(
            backend=RulesBackend.TACTICAL,
            session_id=session_id,
            completed=session.state.status in {GameStatus.COMPLETED, GameStatus.ABORTED}
            or scenario is not None,
            final_state=session.state,
            normalized_result=normalized,
            validation_level=ValidationLevel.TACTICAL_ORACLE,
            backend_version="tactical-0.8.0",
            warnings=("bounded tactical oracle; not a complete rules engine",),
        )

    def _apply_action(
        self,
        session_id: str,
        state: GameState,
        legal: LegalAction,
        proposal: ActionProposal,
    ) -> GameState:
        scenario = self._scenarios.get(session_id)
        effect = {} if scenario is None else scenario.action_effects.get(legal.action_id, {})
        if effect:
            updates: dict[str, Any] = {}
            for key in (
                "status",
                "turn_number",
                "active_player_id",
                "priority_player_id",
                "phase",
                "step",
                "winner_ids",
            ):
                if key in effect:
                    updates[key] = effect[key]
            if "legal_actions" in effect:
                updates["legal_actions"] = tuple(
                    LegalAction.model_validate(item) for item in effect["legal_actions"]
                )
            else:
                updates["legal_actions"] = ()
            return state.model_copy(update=updates)
        if legal.action_type == ActionType.PASS_PRIORITY:
            living = [player for player in state.players if not player.has_lost]
            current_index = next(
                index
                for index, player in enumerate(living)
                if player.player_id == proposal.actor_id
            )
            next_player = living[(current_index + 1) % len(living)].player_id
            return state.model_copy(
                update={
                    "priority_player_id": next_player,
                    "legal_actions": (
                        LegalAction(
                            action_id="pass-priority",
                            actor_id=next_player,
                            action_type=ActionType.PASS_PRIORITY,
                        ),
                    ),
                }
            )
        return state.model_copy(update={"legal_actions": ()})

    def _require_session(self, session_id: str) -> RulesSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise TacticalRuleError(f"unknown tactical session: {session_id}") from exc

    @staticmethod
    def _event(
        state: GameState,
        sequence: int,
        event_type: str,
        actor_id: str | None,
        payload: dict[str, Any],
    ) -> GameEvent:
        return GameEvent(
            event_id=f"{state.game_id}:{sequence}",
            game_id=state.game_id,
            sequence=sequence,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
            post_state_hash=sha256_value(state),
        )


__all__ = ["TacticalRuleError", "TacticalRuleOracle", "TacticalRulesAdapter"]
