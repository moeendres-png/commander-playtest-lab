#!/usr/bin/env python3
"""Qualification-only exact MICRO_REPLACEMENT native-state overlay for XMage.

Adds only the frozen v1.0.1 replacement fixture surface: controlled-since-turn-
began, combat damage temporal state, native combat membership, and execution
through XMage CombatDamageStep. The adapter never computes or applies damage.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
SESSION = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java"
CANONICAL = ROOT / "candidate-qualification/finalist-convergence-xmage/canonical_v101.py"


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor in {path}, observed {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    # Carry the exact rules-relevant state facts into the qualification scenario.
    replace_exact(
        CANONICAL,
        '                    "face": "main",\n',
        '                    "face": "main",\n'
        '                    "controlled_since_turn_began": bool(item.get("controlled_since_turn_began", False)),\n',
        "canonical controlled-since-turn-began",
    )
    replace_exact(
        CANONICAL,
        '        "stack_state": record.get("stack_state", []),\n    }\n',
        '        "stack_state": record.get("stack_state", []),\n'
        '        "combat_state": record.get("combat_state"),\n    }\n',
        "canonical combat state",
    )

    # Native combat imports and schema.
    replace_exact(
        SCENARIO,
        'import mage.game.stack.StackObject;\n',
        'import mage.game.stack.StackObject;\n'
        'import mage.game.combat.Combat;\n'
        'import mage.game.turn.CombatDamageStep;\n'
        'import mage.game.turn.CombatPhase;\n',
        "combat imports",
    )
    replace_exact(
        SCENARIO,
        '            "execution_entry_mode", "temporal_state", "stack_state"\n',
        '            "execution_entry_mode", "temporal_state", "stack_state", "combat_state"\n',
        "top-level combat state",
    )
    replace_exact(
        SCENARIO,
        '    private static final Set<String> CARD = Set.of("semantic_id", "card_name", "tapped", "controller_seat", "face", "face_down");\n',
        '    private static final Set<String> CARD = Set.of(\n'
        '            "semantic_id", "card_name", "tapped", "controller_seat", "face", "face_down",\n'
        '            "controlled_since_turn_began"\n'
        '    );\n',
        "card temporal state field",
    )
    replace_exact(
        SCENARIO,
        '    private static final Set<String> STACK_ITEM = Set.of(\n'
        '            "semantic_stack_id", "source_object", "controller", "targets", "modes", "cast_complete"\n'
        '    );\n',
        '    private static final Set<String> STACK_ITEM = Set.of(\n'
        '            "semantic_stack_id", "source_object", "controller", "targets", "modes", "cast_complete"\n'
        '    );\n'
        '    private static final Set<String> COMBAT_STATE = Set.of("attackers", "blockers", "unblocked_attackers");\n',
        "combat schema",
    )
    replace_exact(
        SCENARIO,
        '''                    if (!"battlefield".equals(zone) && booleanValue(card, "face_down", false)) {
                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield");
                    }
''',
        '''                    if (!"battlefield".equals(zone) && booleanValue(card, "face_down", false)) {
                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield");
                    }
                    if (!"battlefield".equals(zone) && booleanValue(card, "controlled_since_turn_began", false)) {
                        throw fail("INVALID_SCENARIO: controlled_since_turn_began only applies to battlefield");
                    }
''',
        "controlled state validation",
    )

    # Support exactly the two temporal states already qualified plus combat damage.
    replace_exact(
        SCENARIO,
        '''        if (!"precombat_main".equals(phaseName) || !"main".equals(stepName)) {
            throw fail("UNSUPPORTED_SCENARIO_DIMENSION: temporal phase/step " + phaseName + "/" + stepName);
        }
        if (turn < 1) throw fail("INVALID_SCENARIO: turn_number must be positive");

        PreCombatMainPhase phase = new PreCombatMainPhase();
        phase.setStep(new PreCombatMainStep());
        game.getState().getTurn().setPhase(phase);
''',
        '''        boolean precombatMain = "precombat_main".equals(phaseName) && "main".equals(stepName);
        boolean combatDamage = "combat".equals(phaseName) && "combat_damage".equals(stepName);
        if (!precombatMain && !combatDamage) {
            throw fail("UNSUPPORTED_SCENARIO_DIMENSION: temporal phase/step " + phaseName + "/" + stepName);
        }
        if (turn < 1) throw fail("INVALID_SCENARIO: turn_number must be positive");

        if (precombatMain) {
            PreCombatMainPhase phase = new PreCombatMainPhase();
            phase.setStep(new PreCombatMainStep());
            game.getState().getTurn().setPhase(phase);
        } else {
            CombatPhase phase = new CombatPhase();
            phase.setStep(new CombatDamageStep(false));
            game.getState().getTurn().setPhase(phase);
        }
''',
        "combat temporal materialization",
    )
    replace_exact(
        SCENARIO,
        '''        requireNative(game.getTurnPhaseType() != null && "PRECOMBAT_MAIN".equals(game.getTurnPhaseType().name()), "temporal-phase");
        requireNative(game.getTurnStepType() != null && "PRECOMBAT_MAIN".equals(game.getTurnStepType().name()), "temporal-step");
''',
        '''        if (precombatMain) {
            requireNative(game.getTurnPhaseType() != null && "PRECOMBAT_MAIN".equals(game.getTurnPhaseType().name()), "temporal-phase");
            requireNative(game.getTurnStepType() != null && "PRECOMBAT_MAIN".equals(game.getTurnStepType().name()), "temporal-step");
        } else {
            requireNative(game.getTurnPhaseType() != null && "COMBAT".equals(game.getTurnPhaseType().name()), "temporal-phase");
            requireNative(game.getTurnStepType() != null && "COMBAT_DAMAGE".equals(game.getTurnStepType().name()), "temporal-step");
        }
''',
        "combat temporal validation",
    )

    # Add native combat setup/execution helpers immediately before the existing stack helper.
    anchor = '''    private static void applyStackState(
'''
    helper = '''    static JsonObject applyCombatStateAfterTemporal(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        if (!scenario.has("combat_state") || scenario.get("combat_state").isJsonNull()) {
            return null;
        }
        JsonObject spec = object(scenario, "combat_state");
        rejectUnknown(spec, COMBAT_STATE, "combat_state");
        JsonObject attackers = object(spec, "attackers");
        JsonObject blockers = object(spec, "blockers");
        JsonArray unblocked = array(spec, "unblocked_attackers");
        if (!blockers.entrySet().isEmpty()) {
            throw fail("UNSUPPORTED_SCENARIO_DIMENSION: replacement fixture blockers");
        }
        if (attackers.entrySet().size() != 1 || unblocked.size() != 1) {
            throw fail("UNSUPPORTED_SCENARIO_DIMENSION: replacement fixture combat cardinality");
        }

        String attackerSemantic = attackers.entrySet().iterator().next().getKey();
        String defenderRef = attackers.get(attackerSemantic).getAsString();
        if (!unblocked.get(0).getAsString().equals(attackerSemantic)) {
            throw fail("NATIVE_VALIDATION_FAILED: unblocked attacker mismatch");
        }
        UUID attackerId = nativeId(semanticMap, attackerSemantic);
        Permanent attacker = game.getPermanent(attackerId);
        if (attacker == null) throw fail("NATIVE_VALIDATION_FAILED: combat attacker " + attackerSemantic);
        int defenderSeat = playerSeatValue(defenderRef, players.size());
        Player defender = players.get(defenderSeat - 1);
        Player active = game.getPlayer(game.getActivePlayerId());
        if (active == null || !active.getId().equals(attacker.getControllerId())) {
            throw fail("NATIVE_VALIDATION_FAILED: attacker is not controlled by active player");
        }

        JsonObject attackerCardSpec = findCardSpec(scenario, attackerSemantic);
        if (booleanValue(attackerCardSpec, "controlled_since_turn_began", false)) {
            attacker.beginningOfTurn(game);
        }
        requireNative(
                attacker.wasControlledFromStartOfControllerTurn()
                        == booleanValue(attackerCardSpec, "controlled_since_turn_began", false),
                "controlled-since-turn-began:" + attackerSemantic
        );

        Combat combat = game.getCombat();
        combat.clear();
        combat.setAttacker(active.getId());
        combat.setDefenders(game);
        if (!combat.addAttackingCreature(attackerId, game, defender.getId())) {
            throw fail("NATIVE_VALIDATION_FAILED: native combat add attacker failed");
        }
        requireNative(combat.getAttackingPlayerId().equals(active.getId()), "combat-attacking-player");
        requireNative(combat.isAttacker(attackerId), "combat-attacker:" + attackerSemantic);
        requireNative(combat.getDefenderId(attackerId).equals(defender.getId()), "combat-defender:" + defenderRef);
        requireNative(combat.getGroups().size() == 1, "combat-group-cardinality");
        requireNative(combat.getGroups().get(0).getBlockers().isEmpty(), "combat-unblocked");

        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-combat-state/1.0.0");
        result.addProperty("attacker_semantic_id", attackerSemantic);
        result.addProperty("defender", defenderRef);
        result.addProperty("attacker_power", attacker.getPower().getValue());
        result.addProperty("controlled_since_turn_began", attacker.wasControlledFromStartOfControllerTurn());
        result.addProperty("pre_damage_defender_life", defender.getLife());
        result.addProperty("unblocked", true);
        result.addProperty("valid", true);
        return result;
    }

    static boolean executeNativeCombatDamageIfRequested(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap,
            JsonObject validation
    ) {
        if (!scenario.has("combat_state") || scenario.get("combat_state").isJsonNull()) return false;
        JsonObject temporal = object(scenario, "temporal_state");
        if (!"combat".equals(text(temporal, "phase")) || !"combat_damage".equals(text(temporal, "step"))) {
            throw fail("NATIVE_VALIDATION_FAILED: combat_state outside combat damage step");
        }
        JsonObject spec = object(scenario, "combat_state");
        JsonObject attackers = object(spec, "attackers");
        String attackerSemantic = attackers.entrySet().iterator().next().getKey();
        String defenderRef = attackers.get(attackerSemantic).getAsString();
        Permanent attacker = game.getPermanent(nativeId(semanticMap, attackerSemantic));
        if (attacker == null) throw fail("NATIVE_VALIDATION_FAILED: missing damage attacker");
        Player defender = players.get(playerSeatValue(defenderRef, players.size()) - 1);
        requireNative(attacker.getPower().getValue() == 3, "replacement-raw-power");
        requireNative(defender.getLife() == 40, "replacement-pre-damage-life");

        boolean violencePresent = false;
        for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
            if (permanent.getControllerId().equals(attacker.getControllerId())
                    && "Gratuitous Violence".equals(permanent.getName())) {
                violencePresent = true;
                break;
            }
        }
        requireNative(violencePresent, "replacement-effect-permanent");

        // Rules Core owns assignment, replacement, prevention and life change.
        // This is XMage's native combat-damage step implementation.
        new CombatDamageStep(false).beginStep(game, game.getActivePlayerId());
        game.processAction();
        requireNative(defender.getLife() == 34, "replacement-native-terminal-life");

        JsonObject execution = new JsonObject();
        execution.addProperty("executor", "mage.game.turn.CombatDamageStep.beginStep");
        execution.addProperty("raw_attacker_power", 3);
        execution.addProperty("post_damage_defender_life", defender.getLife());
        execution.addProperty("native_damage_amount", 40 - defender.getLife());
        execution.addProperty("replacement_effect_present", true);
        execution.addProperty("adapter_damage_applied", false);
        execution.addProperty("valid", true);
        validation.add("combat_damage_execution", execution);
        return true;
    }

    private static JsonObject findCardSpec(JsonObject scenario, String semantic) {
        for (JsonElement playerElement : array(scenario, "players")) {
            JsonObject zones = object(playerElement.getAsJsonObject(), "zones");
            for (String zone : ZONES) {
                for (JsonElement cardElement : optionalArray(zones, zone)) {
                    JsonObject card = cardElement.getAsJsonObject();
                    if (semantic.equals(text(card, "semantic_id"))) return card;
                }
            }
        }
        throw fail("NATIVE_VALIDATION_FAILED: missing semantic card spec " + semantic);
    }

    private static void applyStackState(
'''
    replace_exact(SCENARIO, anchor, helper, "native combat helpers")

    # Wire setup after temporal materialization, then execute the native combat
    # damage step before entering priority for this no-decision fixture.
    replace_exact(
        SESSION,
        '''                JsonObject temporal = XmageWs26Scenario.applyTemporalState(configuredScenario, game, players);
                appliedScenario.validation().add("temporal_state", temporal);
                replayRecorder = new XmageWs26ReplayRecorder(
''',
        '''                JsonObject temporal = XmageWs26Scenario.applyTemporalState(configuredScenario, game, players);
                appliedScenario.validation().add("temporal_state", temporal);
                JsonObject combatValidation = XmageWs26Scenario.applyCombatStateAfterTemporal(
                        configuredScenario, game, players, appliedScenario.semanticObjectIds()
                );
                if (combatValidation != null) appliedScenario.validation().add("combat_state", combatValidation);
                replayRecorder = new XmageWs26ReplayRecorder(
''',
        "session native combat setup",
    )
    replace_exact(
        SESSION,
        '''                replayRecorder.checkpoint("after_native_setup_validation");
                int prioritySeat = XmageWs26Scenario.requestedPrioritySeat(configuredScenario, players.size());
                game.resumeNativePriority(players.get(prioritySeat - 1).getId());
''',
        '''                replayRecorder.checkpoint("after_native_setup_validation");
                if (XmageWs26Scenario.executeNativeCombatDamageIfRequested(
                        configuredScenario, game, players, appliedScenario.semanticObjectIds(), appliedScenario.validation()
                )) {
                    replayRecorder.checkpoint("after_native_combat_damage");
                    return;
                }
                int prioritySeat = XmageWs26Scenario.requestedPrioritySeat(configuredScenario, players.size());
                game.resumeNativePriority(players.get(prioritySeat - 1).getId());
''',
        "session native combat execution",
    )

    print("XMAGE_MICRO_REPLACEMENT_OVERLAY=PASS")


if __name__ == "__main__":
    main()
