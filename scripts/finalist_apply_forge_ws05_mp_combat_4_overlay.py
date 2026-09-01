#!/usr/bin/env python3
# Qualification-only exact v1.0.1 WS05-MP-COMBAT-4 overlay for Forge.

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    path = args.provider
    java = path.read_text(encoding="utf-8")

    declare_old = '''        @Override
        public void declareAttackers(Player attacker, Combat combat) {
            String finalistFixture = System.getenv("COMMANDER_LAB_FORGE_FIXTURE_ID");
            if (isPrimitiveAFixture(finalistFixture)
                    && broker.automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) {
                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");
            }
            throw failClosed("declareAttackers:events=" + String.join("|", broker.automatic));
        }'''
    declare_new = '''        @Override
        public void declareAttackers(Player attacker, Combat combat) {
            String fixture = System.getenv("COMMANDER_LAB_FORGE_FIXTURE_ID");
            if (!isWs05MpCombat4Fixture(fixture)) {
                if (isPrimitiveAFixture(fixture)
                        && broker.automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) {
                    throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");
                }
                throw failClosed("declareAttackers:events=" + String.join("|", broker.automatic));
            }
            if (attacker != this.player || attacker != getGame().getPlayers().get(0)) {
                throw failClosed("declareAttackers:WRONG_ACTOR");
            }

            java.util.List<Card> nativeAttackers = new ArrayList<>(forge.game.combat.CombatUtil.getPossibleAttackers(attacker));
            nativeAttackers.sort(java.util.Comparator.comparing(card -> {
                String semantic = broker.qualificationSemanticRef(card);
                return semantic == null ? "~" + card.getId() : semantic;
            }));
            if (nativeAttackers.size() != 2
                    || !"obj:mp-attacker-0".equals(broker.qualificationSemanticRef(nativeAttackers.get(0)))
                    || !"obj:mp-attacker-1".equals(broker.qualificationSemanticRef(nativeAttackers.get(1)))) {
                throw failClosed("declareAttackers:NATIVE_ELIGIBLE_ATTACKER_SET_MISMATCH");
            }

            Player p2 = getGame().getPlayers().get(1);
            Player p3 = getGame().getPlayers().get(2);
            Player p4 = getGame().getPlayers().get(3);
            java.util.List<GameEntity> nativeDefenders = new ArrayList<>(
                forge.game.combat.CombatUtil.getAllPossibleDefenders(attacker)
            );
            if (nativeDefenders.size() != 3
                    || !nativeDefenders.contains(p2)
                    || !nativeDefenders.contains(p3)
                    || !nativeDefenders.contains(p4)) {
                throw failClosed("declareAttackers:NATIVE_DEFENDER_SET_MISMATCH");
            }
            java.util.List<GameEntity> defenders = java.util.List.of(p2, p3, p4);

            java.util.List<java.util.Map<Card, GameEntity>> legalAssignments = new ArrayList<>();
            java.util.List<String> labels = new ArrayList<>();
            for (int first = -1; first < defenders.size(); first++) {
                for (int second = -1; second < defenders.size(); second++) {
                    java.util.Map<Card, GameEntity> candidate = new java.util.LinkedHashMap<>();
                    int[] choices = new int[] {first, second};
                    boolean primitiveLegal = true;
                    for (int i = 0; i < nativeAttackers.size(); i++) {
                        if (choices[i] < 0) continue;
                        Card card = nativeAttackers.get(i);
                        GameEntity defender = defenders.get(choices[i]);
                        if (!forge.game.combat.CombatUtil.canAttack(card, defender)) {
                            primitiveLegal = false;
                            break;
                        }
                        if (forge.game.combat.CombatUtil.getAttackCost(getGame(), card, defender) != null) {
                            throw failClosed("declareAttackers:ATTACK_COST_UNSUPPORTED");
                        }
                        candidate.put(card, defender);
                    }
                    if (!primitiveLegal) continue;
                    Combat trial = new Combat(attacker);
                    for (java.util.Map.Entry<Card, GameEntity> entry : candidate.entrySet()) {
                        trial.addAttacker(entry.getKey(), entry.getValue());
                    }
                    if (!forge.game.combat.CombatUtil.validateAttackers(trial)) continue;
                    legalAssignments.add(candidate);
                    labels.add(ws05AssignmentLabel(getGame(), broker, nativeAttackers, candidate));
                }
            }
            if (legalAssignments.isEmpty()) throw failClosed("declareAttackers:NO_NATIVE_LEGAL_ASSIGNMENTS");

            String selectedId = broker.choose("declareAttackers", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= legalAssignments.size()) {
                throw failClosed("declareAttackers:STALE_SELECTION");
            }
            java.util.Map<Card, GameEntity> selected = legalAssignments.get(selectedIndex);
            combat.clearAttackers();
            for (java.util.Map.Entry<Card, GameEntity> entry : selected.entrySet()) {
                combat.addAttacker(entry.getKey(), entry.getValue());
            }
            if (!forge.game.combat.CombatUtil.validateAttackers(combat)) {
                throw failClosed("declareAttackers:SELECTED_ASSIGNMENT_REJECTED_BY_NATIVE_VALIDATOR");
            }
            broker.recordAutomatic("WS05_SELECTED_ASSIGNMENT:" + labels.get(selectedIndex));
        }'''
    java = replace_once(java, declare_old, declare_new, "WS05 native declareAttackers")

    java = replace_once(
        java,
        '''            if (isMicroReplacementFixture(finalistFixture) && microReplacementTerminal(game, this)) {
                throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_TERMINAL");
            }
            priorityDecisions++;''',
        '''            if (isMicroReplacementFixture(finalistFixture) && microReplacementTerminal(game, this)) {
                throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_TERMINAL");
            }
            if (isWs05MpCombat4Fixture(finalistFixture) && ws05MpCombat4Terminal(game, this)) {
                throw new ControlledStop("FINALIST_WS05_MP_COMBAT_4_TERMINAL");
            }
            priorityDecisions++;''',
        "WS05 terminal priority boundary",
    )

    java = replace_once(
        java,
        '''        @com.google.common.eventbus.Subscribe
        public void onSpellResolved(forge.game.event.GameEventSpellResolved event) {
            broker.recordAutomatic("NATIVE_SPELL_RESOLVED:" + event.spell().getHostCard().getName() + ":fizzled=" + event.hasFizzled());
        }
''',
        '''        @com.google.common.eventbus.Subscribe
        public void onSpellResolved(forge.game.event.GameEventSpellResolved event) {
            broker.recordAutomatic("NATIVE_SPELL_RESOLVED:" + event.spell().getHostCard().getName() + ":fizzled=" + event.hasFizzled());
        }

        @com.google.common.eventbus.Subscribe
        public void onAttackersDeclared(forge.game.event.GameEventAttackersDeclared event) {
            for (java.util.Map.Entry<forge.game.GameEntityView, forge.game.card.CardView> entry : event.attackersMap().entries()) {
                String semanticAttacker = broker.qualificationSemanticRefs.get(entry.getValue().getId());
                if (semanticAttacker == null) continue;
                String defender = null;
                if (entry.getKey() instanceof forge.game.player.PlayerView) {
                    defender = semanticPlayerRef(((forge.game.player.PlayerView) entry.getKey()).getName());
                }
                if (defender == null) {
                    throw new ControlledStop("FINALIST_WS05_NONPLAYER_DEFENDER_IN_NATIVE_EVENT");
                }
                broker.recordAutomatic("NATIVE_ATTACKER_DECLARED:" + semanticAttacker + "->" + defender);
            }
        }
''',
        "native attackers-declared event evidence",
    )

    helper_anchor = '    static boolean isMicroReplacementFixture(String fixtureId) {'
    helper = r'''    static boolean isWs05MpCombat4Fixture(String fixtureId) {
        return "WS05-MP-COMBAT-4".equals(fixtureId);
    }

    static String semanticPlayerRef(String nativeName) {
        if ("seat-1".equals(nativeName)) return "P1";
        if ("seat-2".equals(nativeName)) return "P2";
        if ("seat-3".equals(nativeName)) return "P3";
        if ("seat-4".equals(nativeName)) return "P4";
        return null;
    }

    static Card cardByNativeId(Player player, int id) {
        for (Card card : player.getCardsIn(ZoneType.Battlefield)) {
            if (card.getId() == id) return card;
        }
        throw new ControlledStop("FINALIST_WS05_CARD_ID_MISSING:" + id);
    }

    static Card ws05CardBySemantic(Game game, Broker broker, String semantic) {
        for (Card card : game.getPlayers().get(0).getCardsIn(ZoneType.Battlefield)) {
            if (semantic.equals(broker.qualificationSemanticRef(card))) return card;
        }
        return null;
    }

    static String ws05DefenderRef(Game game, GameEntity defender) {
        for (int i = 0; i < game.getPlayers().size(); i++) {
            if (defender == game.getPlayers().get(i)) return "P" + (i + 1);
        }
        return null;
    }

    static String ws05AssignmentLabel(Game game, Broker broker, java.util.List<Card> orderedAttackers, java.util.Map<Card, GameEntity> assignment) {
        StringBuilder sb = new StringBuilder("ATTACK_ASSIGNMENT:");
        for (int i = 0; i < orderedAttackers.size(); i++) {
            if (i > 0) sb.append(',');
            Card card = orderedAttackers.get(i);
            String semantic = broker.qualificationSemanticRef(card);
            if (semantic == null) throw new ControlledStop("FINALIST_WS05_UNBOUND_ASSIGNMENT_ATTACKER");
            GameEntity defender = assignment.get(card);
            sb.append(semantic).append('=');
            sb.append(defender == null ? "NONE" : ws05DefenderRef(game, defender));
        }
        return sb.toString();
    }

    static boolean ws05MpCombat4Terminal(Game game, Broker broker) {
        Combat combat = game.getCombat();
        if (combat == null) return false;
        Card a0 = ws05CardBySemantic(game, broker, "obj:mp-attacker-0");
        Card a1 = ws05CardBySemantic(game, broker, "obj:mp-attacker-1");
        if (a0 == null || a1 == null) return false;
        if (!combat.isAttacking(a0, game.getPlayers().get(1))) return false;
        if (!combat.isAttacking(a1, game.getPlayers().get(2))) return false;
        if (combat.getAttackers().size() != 2) return false;
        if (!a0.isTapped() || !a1.isTapped()) return false;
        if (!broker.automatic.contains("NATIVE_ATTACKER_DECLARED:obj:mp-attacker-0->P2")) return false;
        if (!broker.automatic.contains("NATIVE_ATTACKER_DECLARED:obj:mp-attacker-1->P3")) return false;
        if (!broker.automatic.contains("WS05_NATIVE_ASSIGNMENT:obj:mp-attacker-0->P2")) {
            broker.recordAutomatic("WS05_NATIVE_ASSIGNMENT:obj:mp-attacker-0->P2");
        }
        if (!broker.automatic.contains("WS05_NATIVE_ASSIGNMENT:obj:mp-attacker-1->P3")) {
            broker.recordAutomatic("WS05_NATIVE_ASSIGNMENT:obj:mp-attacker-1->P3");
        }
        return true;
    }

    static String ws05SetupSnapshot(Game game, Broker broker) {
        java.util.List<String> eligible = new ArrayList<>();
        for (Card card : forge.game.combat.CombatUtil.getPossibleAttackers(game.getPlayers().get(0))) {
            String semantic = broker.qualificationSemanticRef(card);
            if (semantic == null) throw new ControlledStop("FINALIST_WS05_UNBOUND_NATIVE_ELIGIBLE_ATTACKER");
            eligible.add(semantic);
        }
        java.util.Collections.sort(eligible);
        java.util.List<String> defenders = new ArrayList<>();
        for (GameEntity defender : forge.game.combat.CombatUtil.getAllPossibleDefenders(game.getPlayers().get(0))) {
            String semantic = ws05DefenderRef(game, defender);
            if (semantic == null) throw new ControlledStop("FINALIST_WS05_NONPLAYER_NATIVE_DEFENDER");
            defenders.add(semantic);
        }
        java.util.Collections.sort(defenders);
        return "{\"base\":" + sessionSnapshot(game)
            + ",\"eligible_attackers\":" + jsonStringArray(eligible)
            + ",\"native_defenders\":" + jsonStringArray(defenders)
            + ",\"current_attackers\":[]"
            + "}";
    }

    static void applyWs05MpCombat4State(Game game, Broker broker) {
        java.util.List<String> lines = java.util.List.of(
            "turn=1",
            "activeplayer=p0",
            "activephase=MAIN1",
            "p0life=40",
            "p0hand=",
            "p0battlefield=Grizzly Bears|Id:4301;Grizzly Bears|Id:4302;Grizzly Bears|Id:4303",
            "p0library=",
            "p0graveyard=",
            "p0exile=",
            "p0command=Rograkh, Son of Rohgahh|IsCommander",
            "p1life=40",
            "p1hand=",
            "p1battlefield=Grizzly Bears|Id:4311",
            "p1library=",
            "p1graveyard=",
            "p1exile=",
            "p1command=Rograkh, Son of Rohgahh|IsCommander",
            "p2life=40",
            "p2hand=",
            "p2battlefield=Grizzly Bears|Id:4321",
            "p2library=",
            "p2graveyard=",
            "p2exile=",
            "p2command=Rograkh, Son of Rohgahh|IsCommander",
            "p3life=40",
            "p3hand=",
            "p3battlefield=Grizzly Bears|Id:4331",
            "p3library=",
            "p3graveyard=",
            "p3exile=",
            "p3command=Rograkh, Son of Rohgahh|IsCommander"
        );
        GameState state = new GameState();
        state.parse(lines);
        java.util.concurrent.CountDownLatch stateApplied = new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicReference<RuntimeException> stateFailure = new java.util.concurrent.atomic.AtomicReference<>();
        game.getAction().invoke(() -> {
            try {
                state.applyToGame(game);
                Player p1 = game.getPlayers().get(0);
                game.getPhaseHandler().devModeSet(forge.game.phase.PhaseType.COMBAT_DECLARE_ATTACKERS, p1, 1);
                Card baseline = cardByNativeId(p1, 4301);
                Card a0 = cardByNativeId(p1, 4302);
                Card a1 = cardByNativeId(p1, 4303);
                baseline.setSickness(true);
                a0.setSickness(false);
                a1.setSickness(false);
                broker.bindQualificationSemanticRef(baseline, "obj:P1-bears");
                broker.bindQualificationSemanticRef(a0, "obj:mp-attacker-0");
                broker.bindQualificationSemanticRef(a1, "obj:mp-attacker-1");
                broker.bindQualificationSemanticRef(cardByNativeId(game.getPlayers().get(1), 4311), "obj:P2-bears");
                broker.bindQualificationSemanticRef(cardByNativeId(game.getPlayers().get(2), 4321), "obj:P3-bears");
                broker.bindQualificationSemanticRef(cardByNativeId(game.getPlayers().get(3), 4331), "obj:P4-bears");

                java.util.List<Card> eligible = new ArrayList<>(forge.game.combat.CombatUtil.getPossibleAttackers(p1));
                if (eligible.size() != 2 || !eligible.contains(a0) || !eligible.contains(a1)) {
                    throw new ControlledStop("FINALIST_WS05_NATIVE_ELIGIBLE_SET_MISMATCH");
                }
                Combat combat = new Combat(p1);
                if (!combat.getAttackers().isEmpty()) {
                    throw new ControlledStop("FINALIST_WS05_INITIAL_COMBAT_NOT_EMPTY");
                }
                game.getPhaseHandler().setCombat(combat);
                game.updateCombatForView();
                game.getPhaseHandler().setPriority(p1);
            } catch (RuntimeException exc) {
                stateFailure.set(exc);
            } finally {
                stateApplied.countDown();
            }
        });
        try {
            if (!stateApplied.await(30, java.util.concurrent.TimeUnit.SECONDS)) {
                throw new ControlledStop("FINALIST_WS05_STATE_APPLY_TIMEOUT");
            }
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new ControlledStop("FINALIST_WS05_STATE_APPLY_INTERRUPTED");
        }
        if (stateFailure.get() != null) throw stateFailure.get();
        broker.out.println("{\"protocol\":" + esc(PROTOCOL)
            + ",\"message_type\":\"QUALIFICATION_STATE\""
            + ",\"request_id\":\"ws05-mp-combat-4-state\""
            + ",\"session_id\":" + esc(SESSION_ID)
            + ",\"payload\":{\"stage\":\"after_native_setup_validation\",\"snapshot\":"
            + ws05SetupSnapshot(game, broker) + "}}");
        broker.out.flush();
    }

    static boolean isMicroReplacementFixture(String fixtureId) {'''
    java = replace_once(java, helper_anchor, helper, "WS05 helpers")

    java = replace_once(
        java,
        '''            } else if (isMicroReplacementFixture(finalistFixtureId)) {
                match.startGame(game, () -> applyMicroReplacementState(game, broker));
            } else {''',
        '''            } else if (isMicroReplacementFixture(finalistFixtureId)) {
                match.startGame(game, () -> applyMicroReplacementState(game, broker));
            } else if (isWs05MpCombat4Fixture(finalistFixtureId)) {
                match.startGame(game, () -> applyWs05MpCombat4State(game, broker));
            } else {''',
        "WS05 native state hook",
    )

    path.write_text(java, encoding="utf-8")
    print("FORGE_WS05_MP_COMBAT_4_OVERLAY=PASS")


if __name__ == "__main__":
    main()
