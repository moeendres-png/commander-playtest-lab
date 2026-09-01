#!/usr/bin/env python3
"""Qualification-only exact v1.0.1 MICRO_STACK overlay for Forge.

Applied after Primitive-A sync and AF05 overlays. The initial Lightning Bolt is
materialized as a fully cast native Forge stack object through GameState.putonstack;
Giant Growth is then cast only through Forge-provided legal priority/target/mana
options. No engine source, AI, GUI, or pilot-side legality is used.
"""

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

    java = replace_once(
        java,
        '        final java.util.Map<String, String> actorOpaqueRefs = new java.util.HashMap<>();\n',
        '        final java.util.Map<String, String> actorOpaqueRefs = new java.util.HashMap<>();\n'
        '        final java.util.Map<Integer, String> qualificationSemanticRefs = new java.util.HashMap<>();\n',
        "qualification semantic identity map",
    )
    java = replace_once(
        java,
        '        String opaqueCardRef(Player viewer, Card card) {\n'
        '            String key = viewer.getName() + ":" + card.getId();\n'
        '            return actorOpaqueRefs.computeIfAbsent(key, ignored -> "obj-" + java.util.UUID.randomUUID());\n'
        '        }\n',
        '        String opaqueCardRef(Player viewer, Card card) {\n'
        '            String key = viewer.getName() + ":" + card.getId();\n'
        '            return actorOpaqueRefs.computeIfAbsent(key, ignored -> "obj-" + java.util.UUID.randomUUID());\n'
        '        }\n\n'
        '        void bindQualificationSemanticRef(Card card, String semanticRef) {\n'
        '            String prior = qualificationSemanticRefs.put(card.getId(), semanticRef);\n'
        '            if (prior != null && !prior.equals(semanticRef)) throw new ControlledStop("FINALIST_SEMANTIC_REF_COLLISION");\n'
        '        }\n\n'
        '        String qualificationSemanticRef(Card card) {\n'
        '            return qualificationSemanticRefs.get(card.getId());\n'
        '        }\n',
        "qualification semantic identity helper",
    )

    java = replace_once(
        java,
        '                } else if (candidate instanceof Card) {\n'
        '                    labels.add("TARGET_CARD:" + ((Card) candidate).getName());\n'
        '                } else {',
        '                } else if (candidate instanceof Card) {\n'
        '                    Card candidateCard = (Card) candidate;\n'
        '                    String semanticRef = broker.qualificationSemanticRef(candidateCard);\n'
        '                    labels.add(semanticRef == null\n'
        '                        ? "TARGET_CARD:" + candidateCard.getName()\n'
        '                        : "TARGET_CARD_SEMANTIC:" + semanticRef);\n'
        '                } else {',
        "semantic target option label",
    )

    java = replace_once(
        java,
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistSolRingRules, "C21", forge.card.CardRarity.Uncommon));',
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistSolRingRules, "C21", forge.card.CardRarity.Uncommon));\n'
        '        forge.card.CardRules finalistGrowthRules = finalistReader.attemptToLoadCard("Giant Growth");\n'
        '        forge.card.CardRules finalistForestRules = finalistReader.attemptToLoadCard("Forest");\n'
        '        if (finalistGrowthRules == null || finalistForestRules == null) throw new ControlledStop("FINALIST_MICRO_STACK_CARD_RULES_MISSING");\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistGrowthRules, "M11", forge.card.CardRarity.Common));\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistForestRules, "10E", forge.card.CardRarity.BasicLand));',
        "MICRO_STACK headless card registration",
    )

    java = replace_once(
        java,
        '            if (isAf05Fixture(finalistFixture) && priorityDecisions >= 1) {\n'
        '                throw new ControlledStop("FINALIST_AF05_TERMINAL");\n'
        '            }\n'
        '            priorityDecisions++;',
        '            if (isAf05Fixture(finalistFixture) && priorityDecisions >= 1) {\n'
        '                throw new ControlledStop("FINALIST_AF05_TERMINAL");\n'
        '            }\n'
        '            if (isMicroStackFixture(finalistFixture)) {\n'
        '                recordMicroStackCheckpoint(game, this);\n'
        '                if (microStackTerminal(game, this)) {\n'
        '                    throw new ControlledStop("FINALIST_MICRO_STACK_TERMINAL");\n'
        '                }\n'
        '            }\n'
        '            priorityDecisions++;',
        "MICRO_STACK priority checkpoints and terminal stop",
    )

    helper_anchor = '    static boolean isAf05Fixture(String fixtureId) {'
    helper = r'''    static boolean isMicroStackFixture(String fixtureId) {
        return "MICRO_STACK".equals(fixtureId);
    }

    static Card uniqueNamedCard(Player player, ZoneType zone, String name) {
        Card found = null;
        for (Card card : player.getCardsIn(zone)) {
            if (!name.equals(card.getName())) continue;
            if (found != null) throw new ControlledStop("FINALIST_MICRO_STACK_NON_UNIQUE_CARD:" + name);
            found = card;
        }
        if (found == null) throw new ControlledStop("FINALIST_MICRO_STACK_CARD_MISSING:" + name);
        return found;
    }

    static Card microTarget(Game game, Broker broker) {
        Player p2 = game.getPlayers().get(1);
        for (Card card : p2.getCardsIn(ZoneType.Battlefield)) {
            if ("obj:micro-target".equals(broker.qualificationSemanticRef(card))) return card;
        }
        return null;
    }

    static String microStackTop(Game game) {
        if (game.getStack().isEmpty()) return null;
        SpellAbility top = game.getStack().peekAbility();
        return top == null || top.getHostCard() == null ? null : top.getHostCard().getName();
    }

    static void recordMicroStackCheckpoint(Game game, Broker broker) {
        int size = game.getStack().size();
        String top = microStackTop(game);
        String marker = "MICRO_STACK_NATIVE:size=" + size + ":top=" + String.valueOf(top);
        if (!broker.automatic.contains(marker)) broker.recordAutomatic(marker);
    }

    static boolean microStackTerminal(Game game, Broker broker) {
        if (!game.getStack().isEmpty()) return false;
        if (!broker.automatic.contains("NATIVE_SPELL_RESOLVED:Giant Growth:fizzled=false")) return false;
        if (!broker.automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) return false;
        Card target = microTarget(game, broker);
        if (target == null || target.getDamage() != 3 || target.getNetToughness() < 5) return false;
        Player p1 = game.getPlayers().get(0);
        Player p2 = game.getPlayers().get(1);
        return p1.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> "Lightning Bolt".equals(c.getName()))
            && p2.getCardsIn(ZoneType.Graveyard).stream().anyMatch(c -> "Giant Growth".equals(c.getName()));
    }

    static String microStackSetupSnapshot(Game game, Broker broker) {
        Card target = microTarget(game, broker);
        SpellAbility top = game.getStack().peekAbility();
        java.util.List<Card> targets = top == null ? java.util.List.of() : top.getTargets().getTargetCards();
        String stackTarget = targets.size() == 1 ? broker.qualificationSemanticRef(targets.get(0)) : null;
        return "{\"base\":" + sessionSnapshot(game)
            + ",\"stack_size\":" + game.getStack().size()
            + ",\"stack_top_source\":" + esc(microStackTop(game))
            + ",\"stack_top_target\":" + esc(stackTarget)
            + ",\"semantic_target_present\":" + (target != null) + "}";
    }

    static void applyMicroStackState(Game game, Broker broker) {
        java.util.List<String> lines = java.util.List.of(
            "turn=1",
            "activeplayer=p0",
            "activephase=MAIN1",
            "p0life=40",
            "p0hand=",
            "p0battlefield=Grizzly Bears",
            "p0library=",
            "p0graveyard=",
            "p0exile=",
            "p0command=Rograkh, Son of Rohgahh|IsCommander",
            "p0putonstack=Lightning Bolt->4202",
            "p1life=40",
            "p1hand=Giant Growth",
            "p1battlefield=Grizzly Bears;Grizzly Bears|Id:4202;Forest",
            "p1library=",
            "p1graveyard=",
            "p1exile=",
            "p1command=Rograkh, Son of Rohgahh|IsCommander",
            "p2life=40",
            "p2hand=",
            "p2battlefield=Grizzly Bears",
            "p2library=",
            "p2graveyard=",
            "p2exile=",
            "p2command=Rograkh, Son of Rohgahh|IsCommander",
            "p3life=40",
            "p3hand=",
            "p3battlefield=",
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
                if (game.getStack().size() != 1 || !"Lightning Bolt".equals(microStackTop(game))) {
                    throw new ControlledStop("FINALIST_MICRO_STACK_INITIAL_STACK_MISMATCH");
                }
                SpellAbility bolt = game.getStack().peekAbility();
                java.util.List<Card> targets = bolt.getTargets().getTargetCards();
                if (targets.size() != 1 || targets.get(0).getOwner() != game.getPlayers().get(1)
                        || !"Grizzly Bears".equals(targets.get(0).getName())) {
                    throw new ControlledStop("FINALIST_MICRO_STACK_INITIAL_TARGET_MISMATCH");
                }
                broker.bindQualificationSemanticRef(targets.get(0), "obj:micro-target");
                broker.bindQualificationSemanticRef(uniqueNamedCard(game.getPlayers().get(1), ZoneType.Hand, "Giant Growth"), "obj:micro-growth");
                broker.bindQualificationSemanticRef(uniqueNamedCard(game.getPlayers().get(1), ZoneType.Battlefield, "Forest"), "obj:micro-forest");
                game.getPhaseHandler().setPriority(game.getPlayers().get(1));
            } catch (RuntimeException exc) {
                stateFailure.set(exc);
            } finally {
                stateApplied.countDown();
            }
        });
        try {
            if (!stateApplied.await(30, java.util.concurrent.TimeUnit.SECONDS)) throw new ControlledStop("FINALIST_MICRO_STACK_STATE_APPLY_TIMEOUT");
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new ControlledStop("FINALIST_MICRO_STACK_STATE_APPLY_INTERRUPTED");
        }
        if (stateFailure.get() != null) throw stateFailure.get();
        broker.out.println("{\"protocol\":" + esc(PROTOCOL)
            + ",\"message_type\":\"QUALIFICATION_STATE\""
            + ",\"request_id\":\"micro-stack-state\""
            + ",\"session_id\":" + esc(SESSION_ID)
            + ",\"payload\":{\"stage\":\"after_native_setup_validation\",\"snapshot\":" + microStackSetupSnapshot(game, broker) + "}}");
        broker.out.flush();
    }

    static boolean isAf05Fixture(String fixtureId) {'''
    java = replace_once(java, helper_anchor, helper, "MICRO_STACK helpers")

    java = replace_once(
        java,
        '            } else if (isAf05Fixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyAf05State(game, finalistFixtureId, broker));\n'
        '            } else {',
        '            } else if (isAf05Fixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyAf05State(game, finalistFixtureId, broker));\n'
        '            } else if (isMicroStackFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyMicroStackState(game, broker));\n'
        '            } else {',
        "MICRO_STACK native state hook",
    )

    path.write_text(java, encoding="utf-8")
    print("FORGE_MICRO_STACK_OVERLAY=PASS")


if __name__ == "__main__":
    main()
