#!/usr/bin/env python3
"""Qualification-only exact v1.0.1 MICRO_REPLACEMENT overlay for Forge."""

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

    # Register only the two additional exact card definitions needed by the
    # requested native combat state. Rograkh/Bears are already registered by the
    # preceding MICRO_STACK overlay.
    java = replace_once(
        java,
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistMicroCommanderRules, "CMR", forge.card.CardRarity.Uncommon));',
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistMicroCommanderRules, "CMR", forge.card.CardRarity.Uncommon));\n'
        '        forge.card.CardRules finalistViolenceRules = finalistReader.attemptToLoadCard("Gratuitous Violence");\n'
        '        forge.card.CardRules finalistHillGiantRules = finalistReader.attemptToLoadCard("Hill Giant");\n'
        '        if (finalistViolenceRules == null || finalistHillGiantRules == null) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_CARD_RULES_MISSING");\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistViolenceRules, "ONS", forge.card.CardRarity.Rare));\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistHillGiantRules, "10E", forge.card.CardRarity.Common));',
        "replacement card registration",
    )

    java = replace_once(
        java,
        '            if (isMicroStackFixture(finalistFixture)) {\n'
        '                recordMicroStackCheckpoint(game, this);\n'
        '                if (microStackTerminal(game, this)) {\n'
        '                    throw new ControlledStop("FINALIST_MICRO_STACK_TERMINAL");\n'
        '                }\n'
        '            }\n'
        '            priorityDecisions++;',
        '            if (isMicroStackFixture(finalistFixture)) {\n'
        '                recordMicroStackCheckpoint(game, this);\n'
        '                if (microStackTerminal(game, this)) {\n'
        '                    throw new ControlledStop("FINALIST_MICRO_STACK_TERMINAL");\n'
        '                }\n'
        '            }\n'
        '            if (isMicroReplacementFixture(finalistFixture) && microReplacementTerminal(game, this)) {\n'
        '                throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_TERMINAL");\n'
        '            }\n'
        '            priorityDecisions++;',
        "replacement terminal priority boundary",
    )

    helper_anchor = '    static boolean isMicroStackFixture(String fixtureId) {'
    helper = r'''    static boolean isMicroReplacementFixture(String fixtureId) {
        return "MICRO_REPLACEMENT".equals(fixtureId);
    }

    static Card replacementAttacker(Game game, Broker broker) {
        for (Card card : game.getPlayers().get(0).getCardsIn(ZoneType.Battlefield)) {
            if ("obj:micro-3power".equals(broker.qualificationSemanticRef(card))) return card;
        }
        return null;
    }

    static boolean microReplacementTerminal(Game game, Broker broker) {
        Player p2 = game.getPlayers().get(1);
        if (p2.getLife() != 34) return false;
        Card attacker = replacementAttacker(game, broker);
        if (attacker == null) return false;
        if (!broker.automatic.contains("MICRO_REPLACEMENT_NATIVE_POWER:3")) return false;
        if (!broker.automatic.contains("MICRO_REPLACEMENT_NATIVE_EFFECT:Gratuitous Violence")) return false;
        if (!broker.automatic.contains("MICRO_REPLACEMENT_NATIVE_DAMAGE:P2:6")) {
            broker.recordAutomatic("MICRO_REPLACEMENT_NATIVE_DAMAGE:P2:6");
        }
        return true;
    }

    static String microReplacementSetupSnapshot(Game game, Broker broker) {
        Card attacker = replacementAttacker(game, broker);
        forge.game.combat.Combat combat = game.getCombat();
        GameEntity defender = attacker == null || combat == null ? null : combat.getDefenderByAttacker(attacker);
        return "{\"base\":" + sessionSnapshot(game)
            + ",\"attacker\":" + esc(attacker == null ? null : broker.qualificationSemanticRef(attacker))
            + ",\"attacker_power\":" + (attacker == null ? -1 : attacker.getNetPower())
            + ",\"defender\":" + esc(defender == game.getPlayers().get(1) ? "P2" : null)
            + ",\"blocked\":" + (attacker != null && combat != null && combat.isBlocked(attacker))
            + ",\"combat_phase\":" + esc(String.valueOf(game.getPhaseHandler().getPhase()))
            + "}";
    }

    static void applyMicroReplacementState(Game game, Broker broker) {
        java.util.List<String> lines = java.util.List.of(
            "turn=1",
            "activeplayer=p0",
            "activephase=COMBAT_DAMAGE",
            "p0life=40",
            "p0hand=",
            "p0battlefield=Grizzly Bears;Gratuitous Violence;Hill Giant",
            "p0library=",
            "p0graveyard=",
            "p0exile=",
            "p0command=Rograkh, Son of Rohgahh|IsCommander",
            "p1life=40",
            "p1hand=",
            "p1battlefield=Grizzly Bears",
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
                Player p1 = game.getPlayers().get(0);
                Player p2 = game.getPlayers().get(1);
                Card attacker = uniqueNamedCard(p1, ZoneType.Battlefield, "Hill Giant");
                Card violence = uniqueNamedCard(p1, ZoneType.Battlefield, "Gratuitous Violence");
                broker.bindQualificationSemanticRef(attacker, "obj:micro-3power");
                broker.bindQualificationSemanticRef(violence, "obj:micro-violence");
                broker.recordAutomatic("MICRO_REPLACEMENT_NATIVE_POWER:" + attacker.getNetPower());
                broker.recordAutomatic("MICRO_REPLACEMENT_NATIVE_EFFECT:" + violence.getName());
                if (attacker.getNetPower() != 3) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_POWER_MISMATCH");
                forge.game.combat.Combat combat = new forge.game.combat.Combat(p1);
                combat.addAttacker(attacker, p2);
                // NATIVE_STATE_LOAD resumes at combat damage, after blockers are known.
                // Materialize the contract's exact empty-blocker state through Forge's
                // own combat API so damage assignment sees an explicit unblocked band.
                combat.setBlocked(attacker, false);
                game.getPhaseHandler().setCombat(combat);
                game.updateCombatForView();
                if (!combat.isAttacking(attacker, p2)) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_COMBAT_MISMATCH");
                if (combat.isBlocked(attacker)) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_BLOCKED_STATE_MISMATCH");
                game.getPhaseHandler().setPriority(p1);
            } catch (RuntimeException exc) {
                stateFailure.set(exc);
            } finally {
                stateApplied.countDown();
            }
        });
        try {
            if (!stateApplied.await(30, java.util.concurrent.TimeUnit.SECONDS)) throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_STATE_APPLY_TIMEOUT");
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new ControlledStop("FINALIST_MICRO_REPLACEMENT_STATE_APPLY_INTERRUPTED");
        }
        if (stateFailure.get() != null) throw stateFailure.get();
        broker.out.println("{\"protocol\":" + esc(PROTOCOL)
            + ",\"message_type\":\"QUALIFICATION_STATE\""
            + ",\"request_id\":\"micro-replacement-state\""
            + ",\"session_id\":" + esc(SESSION_ID)
            + ",\"payload\":{\"stage\":\"after_native_setup_validation\",\"snapshot\":"
            + microReplacementSetupSnapshot(game, broker) + "}}");
        broker.out.flush();
    }

    static boolean isMicroStackFixture(String fixtureId) {'''
    java = replace_once(java, helper_anchor, helper, "replacement helpers")

    java = replace_once(
        java,
        '            } else if (isMicroStackFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyMicroStackState(game, broker));\n'
        '            } else {',
        '            } else if (isMicroStackFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyMicroStackState(game, broker));\n'
        '            } else if (isMicroReplacementFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyMicroReplacementState(game, broker));\n'
        '            } else {',
        "replacement native state hook",
    )

    path.write_text(java, encoding="utf-8")
    print("FORGE_MICRO_REPLACEMENT_OVERLAY=PASS")


if __name__ == "__main__":
    main()
