#!/usr/bin/env python3
"""Qualification-only native WS05-MP-COMBAT-4 overlay for pinned XMage."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("COMMANDER_LAB_OVERLAY_ROOT", Path(__file__).resolve().parents[2]))
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
SESSION = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java"


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor in {path}, observed {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: Path, start: str, end: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"{label}: non-unique boundary")
    left, tail = text.split(start, 1)
    _, right = tail.split(end, 1)
    path.write_text(left + replacement + end + right, encoding="utf-8")


def main() -> None:
    replace_exact(
        SCENARIO,
        "import mage.game.turn.CombatDamageStep;\n",
        "import mage.game.turn.BeginCombatStep;\n"
        "import mage.game.turn.CombatDamageStep;\n"
        "import mage.game.turn.DeclareAttackersStep;\n",
        "declare attackers imports",
    )
    replace_exact(
        SCENARIO,
        '    private static final Set<String> COMBAT_STATE = Set.of("attackers", "blockers", "unblocked_attackers");\n',
        '    private static final Set<String> COMBAT_STATE = Set.of(\n'
        '            "attackers", "blockers", "unblocked_attackers", "eligible_attackers"\n'
        '    );\n',
        "eligible attackers schema",
    )
    replace_exact(
        SCENARIO,
        '        boolean combatDamage = "combat".equals(phaseName) && "combat_damage".equals(stepName);\n'
        '        if (!precombatMain && !combatDamage) {\n',
        '        boolean combatDamage = "combat".equals(phaseName) && "combat_damage".equals(stepName);\n'
        '        boolean declareAttackers = "combat".equals(phaseName) && "declare_attackers".equals(stepName);\n'
        '        if (!precombatMain && !combatDamage && !declareAttackers) {\n',
        "declare attackers temporal support",
    )
    replace_exact(
        SCENARIO,
        '''        } else {
            CombatPhase phase = new CombatPhase();
            phase.setStep(new CombatDamageStep(false));
            game.getState().getTurn().setPhase(phase);
        }
''',
        '''        } else {
            CombatPhase phase = new CombatPhase();
            phase.setStep(declareAttackers ? new DeclareAttackersStep() : new CombatDamageStep(false));
            game.getState().getTurn().setPhase(phase);
        }
''',
        "declare attackers phase construction",
    )
    replace_exact(
        SCENARIO,
        '''        } else {
            requireNative(game.getTurnPhaseType() != null && "COMBAT".equals(game.getTurnPhaseType().name()), "temporal-phase");
            requireNative(game.getTurnStepType() != null && "COMBAT_DAMAGE".equals(game.getTurnStepType().name()), "temporal-step");
        }
''',
        '''        } else {
            requireNative(game.getTurnPhaseType() != null && "COMBAT".equals(game.getTurnPhaseType().name()), "temporal-phase");
            String expectedStep = declareAttackers ? "DECLARE_ATTACKERS" : "COMBAT_DAMAGE";
            requireNative(game.getTurnStepType() != null && expectedStep.equals(game.getTurnStepType().name()), "temporal-step");
        }
''',
        "declare attackers temporal validation",
    )

    combat_helpers = '''    static JsonObject applyCombatStateAfterTemporal(
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
        JsonObject temporal = object(scenario, "temporal_state");
        if ("declare_attackers".equals(text(temporal, "step"))) {
            JsonObject attackers = object(spec, "attackers");
            JsonArray eligible = array(spec, "eligible_attackers");
            if (!attackers.entrySet().isEmpty() || eligible.size() != 2) {
                throw fail("NATIVE_VALIDATION_FAILED: declare attackers initial combat cardinality");
            }
            Player active = game.getPlayer(game.getActivePlayerId());
            if (active == null) throw fail("NATIVE_VALIDATION_FAILED: active player missing");
            JsonArray eligibleSemantic = new JsonArray();
            for (JsonElement item : eligible) {
                String semantic = item.getAsString();
                Permanent permanent = game.getPermanent(nativeId(semanticMap, semantic));
                if (permanent == null || !active.getId().equals(permanent.getControllerId())) {
                    throw fail("NATIVE_VALIDATION_FAILED: eligible attacker " + semantic);
                }
                permanent.beginningOfTurn(game);
                requireNative(permanent.wasControlledFromStartOfControllerTurn(), "attack-eligibility:" + semantic);
                eligibleSemantic.add(semantic);
            }

            new BeginCombatStep().beginStep(game, active.getId());
            CombatPhase phase = new CombatPhase();
            phase.setStep(new DeclareAttackersStep());
            game.getState().getTurn().setPhase(phase);
            Combat combat = game.getCombat();
            requireNative(combat.getAttackers().isEmpty(), "declare-attackers-entry-empty");
            requireNative(combat.getDefenders().contains(players.get(1).getId()), "defender:P2");
            requireNative(combat.getDefenders().contains(players.get(2).getId()), "defender:P3");
            requireNative(combat.getDefenders().contains(players.get(3).getId()), "defender:P4");
            Set<UUID> available = active.getAvailableAttackers(game).stream()
                    .map(Permanent::getId).collect(java.util.stream.Collectors.toSet());
            Set<UUID> expected = new java.util.LinkedHashSet<>();
            for (JsonElement item : eligible) expected.add(nativeId(semanticMap, item.getAsString()));
            requireNative(available.equals(expected), "eligible-attacker-set");

            JsonObject result = new JsonObject();
            result.addProperty("validator", "xmage-native-declare-attackers-state/1.0.0");
            result.add("eligible_attackers", eligibleSemantic);
            result.addProperty("initial_attackers", 0);
            result.addProperty("native_player_defenders", 3);
            result.addProperty("valid", true);
            return result;
        }

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
        if (booleanValue(attackerCardSpec, "controlled_since_turn_began", false)) attacker.beginningOfTurn(game);
        requireNative(attacker.wasControlledFromStartOfControllerTurn()
                        == booleanValue(attackerCardSpec, "controlled_since_turn_began", false),
                "controlled-since-turn-began:" + attackerSemantic);

        Combat combat = game.getCombat();
        combat.clear();
        combat.setAttacker(active.getId());
        combat.setDefenders(game);
        if (!combat.addAttackingCreature(attackerId, game, defender.getId())) {
            throw fail("NATIVE_VALIDATION_FAILED: native combat add attacker failed");
        }
        requireNative(combat.getAttackingPlayerId().equals(active.getId()), "combat-attacking-player");
        requireNative(combat.getAttackers().contains(attackerId), "combat-attacker:" + attackerSemantic);
        requireNative(combat.getGroups().size() == 1, "combat-group-cardinality");
        requireNative(combat.getGroups().get(0).getDefenderId().equals(defender.getId()), "combat-defender:" + defenderRef);
        requireNative(combat.getGroups().get(0).getAttackers().contains(attackerId), "combat-group-attacker");
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

    static boolean executeNativeDeclareAttackersIfRequested(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap,
            JsonObject validation
    ) {
        JsonObject temporal = object(scenario, "temporal_state");
        if (!"declare_attackers".equals(text(temporal, "step"))) return false;
        new DeclareAttackersStep().beginStep(game, game.getActivePlayerId());
        Combat combat = game.getCombat();
        UUID first = nativeId(semanticMap, "obj:mp-attacker-0");
        UUID second = nativeId(semanticMap, "obj:mp-attacker-1");
        requireNative(combat.getAttackers().size() == 2, "declared-attacker-cardinality");
        requireNative(players.get(1).getId().equals(combat.getDefenderId(first)), "assignment:obj:mp-attacker-0->P2");
        requireNative(players.get(2).getId().equals(combat.getDefenderId(second)), "assignment:obj:mp-attacker-1->P3");
        JsonObject execution = new JsonObject();
        execution.addProperty("executor", "mage.game.turn.DeclareAttackersStep.beginStep");
        execution.addProperty("obj:mp-attacker-0", "P2");
        execution.addProperty("obj:mp-attacker-1", "P3");
        execution.addProperty("adapter_assignment_applied", false);
        execution.addProperty("valid", true);
        validation.add("native_declare_attackers_execution", execution);
        return true;
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
        if ("declare_attackers".equals(text(temporal, "step"))) return false;
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

'''
    replace_between(
        SCENARIO,
        "    static JsonObject applyCombatStateAfterTemporal(\n",
        "    private static JsonObject findCardSpec(",
        combat_helpers,
        "combat helpers",
    )

    replace_exact(
        SESSION,
        '''                replayRecorder.checkpoint("after_native_setup_validation");
                if (XmageWs26Scenario.executeNativeCombatDamageIfRequested(
''',
        '''                replayRecorder.checkpoint("after_native_setup_validation");
                if (XmageWs26Scenario.executeNativeDeclareAttackersIfRequested(
                        configuredScenario, game, players, appliedScenario.semanticObjectIds(), appliedScenario.validation()
                )) {
                    replayRecorder.checkpoint("after_native_declare_attackers");
                    return;
                }
                if (XmageWs26Scenario.executeNativeCombatDamageIfRequested(
''',
        "session native declare attackers execution",
    )
    print("XMAGE_WS05_MP_COMBAT_4_OVERLAY=PASS")


if __name__ == "__main__":
    main()
