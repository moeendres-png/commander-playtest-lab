#!/usr/bin/env python3
"""Qualification-only Forge v1.0.1 Primitive-A overlay.

This patches only the generated GPL-side provider. It does not modify pinned Forge
source and it never moves Forge code into the proprietary process. The overlay adds:
- headless real-card registration for the two canonical Bolt fixtures;
- exact NATIVE_STATE_LOAD materialization through Forge GameState;
- semantic labels for engine-generated priority actions;
- engine-first single-target routing from TargetRestrictions.getAllCandidates;
- engine-native mana-ability activation/payment without Forge AI or GUI defaults;
- direct Forge event-bus evidence for cast and resolution.

Every discretionary selection remains external and fail-closed.
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
        '        forge.card.CardRules finalistMountainRules = finalistReader.attemptToLoadCard("Mountain");\n'
        '        forge.card.CardRules finalistCommanderRules = finalistReader.attemptToLoadCard("Rograkh, Son of Rohgahh");\n'
        '        if (finalistMountainRules == null || finalistCommanderRules == null) throw new ControlledStop("FINALIST_CANONICAL_DECK_RULES_MISSING");',
        '        forge.card.CardRules finalistMountainRules = finalistReader.attemptToLoadCard("Mountain");\n'
        '        forge.card.CardRules finalistCommanderRules = finalistReader.attemptToLoadCard("Rograkh, Son of Rohgahh");\n'
        '        forge.card.CardRules finalistBoltRules = finalistReader.attemptToLoadCard("Lightning Bolt");\n'
        '        forge.card.CardRules finalistBearsRules = finalistReader.attemptToLoadCard("Grizzly Bears");\n'
        '        if (finalistMountainRules == null || finalistCommanderRules == null || finalistBoltRules == null || finalistBearsRules == null) throw new ControlledStop("FINALIST_CANONICAL_DECK_RULES_MISSING");\n'
        '        PaperCard finalistBoltCard = new PaperCard(finalistBoltRules, "M11", forge.card.CardRarity.Common);\n'
        '        PaperCard finalistBearsCard = new PaperCard(finalistBearsRules, "10E", forge.card.CardRarity.Common);\n'
        '        forge.StaticData.instance().getCommonCards().addCard(finalistBoltCard);\n'
        '        forge.StaticData.instance().getCommonCards().addCard(finalistBearsCard);',
        "headless Primitive-A card registration",
    )

    java = replace_once(
        java,
        '        java.util.List<SpellAbility> choosePriority(Player actor, Game game) {\n            priorityDecisions++;',
        '        java.util.List<SpellAbility> choosePriority(Player actor, Game game) {\n'
        '            String finalistFixture = System.getenv("COMMANDER_LAB_FORGE_FIXTURE_ID");\n'
        '            if (isPrimitiveAFixture(finalistFixture) && primitiveATerminal(game)) {\n'
        '                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");\n'
        '            }\n'
        '            priorityDecisions++;',
        "Primitive-A terminal stop",
    )
    java = replace_once(
        java,
        '                            labels.add("FORGE_LEGAL_ACTION");',
        '                            labels.add("FORGE_LEGAL_ACTION:" + c.getName() + ":" + String.valueOf(sa));',
        "semantic priority action labels",
    )

    target_old = '''        @Override
        public boolean chooseTargetsFor(SpellAbility currentAbility) {
            throw failClosed("chooseTargetsFor");
        }'''
    target_new = '''        @Override
        public boolean chooseTargetsFor(SpellAbility currentAbility) {
            TargetRestrictions restrictions = currentAbility.getTargetRestrictions();
            if (restrictions == null) {
                broker.recordAutomatic("chooseTargetsFor:NO_TARGETS");
                return true;
            }
            if (currentAbility.getMinTargets() != 1 || currentAbility.getMaxTargets() != 1) {
                throw failClosed("chooseTargetsFor:ONLY_SINGLE_TARGET_SUPPORTED");
            }
            java.util.List<GameEntity> nativeTargets = new ArrayList<>();
            java.util.List<String> labels = new ArrayList<>();
            for (GameEntity candidate : restrictions.getAllCandidates(currentAbility)) {
                if (!currentAbility.canTarget(candidate)) continue;
                nativeTargets.add(candidate);
                if (candidate instanceof Player) {
                    labels.add("TARGET_PLAYER:" + ((Player) candidate).getName());
                } else if (candidate instanceof Card) {
                    labels.add("TARGET_CARD:" + ((Card) candidate).getName());
                } else {
                    labels.add("TARGET_ENTITY:" + candidate.getName());
                }
            }
            if (nativeTargets.isEmpty()) return false;
            String selectedId = broker.choose("target", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= nativeTargets.size()) {
                throw failClosed("chooseTargetsFor:STALE_SELECTION");
            }
            return currentAbility.getTargets().add(nativeTargets.get(selectedIndex));
        }'''
    java = replace_once(java, target_old, target_new, "engine-first chooseTargetsFor")

    pay_old = '''        @Override
        public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
            throw failClosed("payManaCost");
        }'''
    pay_new = '''        @Override
        public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
            return PlaySpellAbility.payManaCost(this, toPay, costPartMana, sa, this.player, prompt, matrix, effect);
        }'''
    java = replace_once(java, pay_old, pay_new, "native payManaCost delegation")

    apply_old = '''        @Override
        public boolean applyManaToCost(ManaCostBeingPaid toPay, SpellAbility ability, String prompt, ManaConversionMatrix matrix, boolean effect) {
            throw failClosed("applyManaToCost");
        }'''
    apply_new = '''        @Override
        public boolean applyManaToCost(ManaCostBeingPaid toPay, SpellAbility ability, String prompt, ManaConversionMatrix matrix, boolean effect) {
            int guard = 0;
            while (!toPay.isPaid()) {
                if (++guard > 16) throw failClosed("applyManaToCost:GUARD");
                java.util.List<SpellAbility> nativeMana = new ArrayList<>();
                java.util.List<String> labels = new ArrayList<>();
                ZoneType[] zones = new ZoneType[] {ZoneType.Battlefield, ZoneType.Hand, ZoneType.Graveyard, ZoneType.Exile, ZoneType.Command};
                for (ZoneType zone : zones) {
                    for (Card card : this.player.getCardsIn(zone)) {
                        for (SpellAbility manaAbility : card.getAllPossibleAbilities(this.player, true)) {
                            if (!manaAbility.isManaAbility()) continue;
                            manaAbility.setActivatingPlayer(this.player);
                            nativeMana.add(manaAbility);
                            labels.add("MANA_ABILITY:" + card.getName() + ":" + String.valueOf(manaAbility));
                        }
                    }
                }
                if (nativeMana.isEmpty()) return false;
                String selectedId = broker.choose("mana_payment", this.player, labels);
                int selectedIndex = Integer.parseInt(selectedId.substring(1));
                if (selectedIndex < 0 || selectedIndex >= nativeMana.size()) throw failClosed("applyManaToCost:STALE_SELECTION");
                SpellAbility chosen = nativeMana.get(selectedIndex);
                if (!PlaySpellAbility.playSpellAbility(this, this.player, chosen)) return false;
                boolean restrictionsMet = true;
                for (AbilityManaPart manaPart : chosen.getAllManaParts()) {
                    if (!manaPart.meetsManaRestrictions(ability)) {
                        restrictionsMet = false;
                        break;
                    }
                }
                if (!restrictionsMet) return false;
                this.player.getManaPool().payManaFromAbility(ability, toPay, chosen);
            }
            return true;
        }'''
    java = replace_once(java, apply_old, apply_new, "engine-native applyManaToCost")

    helper_anchor = '''    static String singleCommanderName(Player player) {'''
    helper = '''    static boolean isPrimitiveAFixture(String fixtureId) {
        return "PILOT_PRIORITY".equals(fixtureId) || "PILOT_TARGET".equals(fixtureId);
    }

    static boolean primitiveATerminal(Game game) {
        if (game.getPlayers().size() != 4) return false;
        Player p1 = game.getPlayers().get(0);
        Player p2 = game.getPlayers().get(1);
        boolean boltInGraveyard = false;
        for (Card card : p1.getCardsIn(ZoneType.Graveyard)) {
            if ("Lightning Bolt".equals(card.getName())) boltInGraveyard = true;
        }
        return boltInGraveyard && p2.getLife() == 37;
    }

    static void applyPrimitiveAState(Game game, String fixtureId, Broker broker) {
        if (!isPrimitiveAFixture(fixtureId)) return;
        java.util.List<String> lines = java.util.List.of(
            "turn=1",
            "activeplayer=p0",
            "activephase=MAIN1",
            "p0life=40",
            "p0hand=Lightning Bolt",
            "p0battlefield=Mountain;Grizzly Bears",
            "p0library=",
            "p0graveyard=",
            "p0exile=",
            "p0command=",
            "p1life=40",
            "p1hand=",
            "p1battlefield=Grizzly Bears",
            "p1library=",
            "p1graveyard=",
            "p1exile=",
            "p1command=",
            "p2life=40",
            "p2hand=",
            "p2battlefield=Grizzly Bears",
            "p2library=",
            "p2graveyard=",
            "p2exile=",
            "p2command=",
            "p3life=40",
            "p3hand=",
            "p3battlefield=",
            "p3library=",
            "p3graveyard=",
            "p3exile=",
            "p3command="
        );
        GameState state = new GameState();
        state.parse(lines);
        state.applyToGame(game);
        game.getPhaseHandler().setPriority(game.getPlayers().get(0));
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)
            + ",\\\"message_type\\\":\\\"QUALIFICATION_STATE\\\""
            + ",\\\"request_id\\\":\\\"primitive-a-state\\\""
            + ",\\\"session_id\\\":" + esc(SESSION_ID)
            + ",\\\"payload\\\":{\\\"stage\\\":\\\"after_native_setup_validation\\\",\\\"snapshot\\\":" + sessionSnapshot(game) + "}}");
        broker.out.flush();
    }

    static String zoneNames(Player player, ZoneType zone) {
        java.util.List<String> names = new ArrayList<>();
        for (Card card : player.getCardsIn(zone)) names.add(card.getName());
        java.util.Collections.sort(names);
        return String.join("|", names);
    }

    static String jsonStringArray(java.util.List<String> values) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(esc(values.get(i)));
        }
        return sb.append(']').toString();
    }

    static final class FinalistEvidenceEvents {
        final Broker broker;
        FinalistEvidenceEvents(Broker broker) { this.broker = broker; }

        @com.google.common.eventbus.Subscribe
        public void onSpellCast(forge.game.event.GameEventSpellAbilityCast event) {
            broker.recordAutomatic("NATIVE_SPELL_CAST:" + event.sa().getHostCard().getName());
        }

        @com.google.common.eventbus.Subscribe
        public void onSpellResolved(forge.game.event.GameEventSpellResolved event) {
            broker.recordAutomatic("NATIVE_SPELL_RESOLVED:" + event.spell().getHostCard().getName() + ":fizzled=" + event.hasFizzled());
        }
    }

    static String singleCommanderName(Player player) {'''
    java = replace_once(java, helper_anchor, helper, "Primitive-A state/evidence helpers")

    java = replace_once(
        java,
        '        return "{\\\"player_count\\\":" + game.getPlayers().size()\n'
        '            + ",\\\"turn\\\":" + esc(turn)\n'
        '            + ",\\\"phase\\\":" + esc(phase)\n'
        '            + ",\\\"players\\\":[" + players + "]}";',
        '        return "{\\\"player_count\\\":" + game.getPlayers().size()\n'
        '            + ",\\\"turn\\\":" + esc(turn)\n'
        '            + ",\\\"phase\\\":" + esc(phase)\n'
        '            + ",\\\"active_actor\\\":" + esc(game.getPhaseHandler().getPlayerTurn() == null ? null : game.getPhaseHandler().getPlayerTurn().getName())\n'
        '            + ",\\\"priority_actor\\\":" + esc(game.getPhaseHandler().getPriorityPlayer() == null ? null : game.getPhaseHandler().getPriorityPlayer().getName())\n'
        '            + ",\\\"players\\\":[" + players + "]}";',
        "active/priority semantic snapshot",
    )
    java = replace_once(
        java,
        '                .append(",\\\"commander\\\":").append(esc(singleCommanderName(p)))\n'
        '                .append("}");',
        '                .append(",\\\"commander\\\":").append(esc(singleCommanderName(p)))\n'
        '                .append(",\\\"hand_names\\\":").append(esc(zoneNames(p, ZoneType.Hand)))\n'
        '                .append(",\\\"battlefield_names\\\":").append(esc(zoneNames(p, ZoneType.Battlefield)))\n'
        '                .append(",\\\"graveyard_names\\\":").append(esc(zoneNames(p, ZoneType.Graveyard)))\n'
        '                .append("}");',
        "Primitive-A semantic zone snapshot",
    )

    java = replace_once(
        java,
        '        Game game = match.createGame();\n        out.println("{\\\"protocol\\\":" + esc(PROTOCOL)',
        '        Game game = match.createGame();\n'
        '        game.subscribeToEvents(new FinalistEvidenceEvents(broker));\n'
        '        out.println("{\\\"protocol\\\":" + esc(PROTOCOL)',
        "native event subscription",
    )

    java = replace_once(
        java,
        '        try {\n            match.startGame(game);\n            stopReason = "FORGE_GAME_RETURNED";',
        '        try {\n'
        '            String finalistFixtureId = System.getenv("COMMANDER_LAB_FORGE_FIXTURE_ID");\n'
        '            if (isPrimitiveAFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyPrimitiveAState(game, finalistFixtureId, broker));\n'
        '            } else {\n'
        '                match.startGame(game);\n'
        '            }\n'
        '            stopReason = "FORGE_GAME_RETURNED";',
        "qualification native-state hook",
    )

    java = replace_once(
        java,
        '            + ",\\\"priority_decisions\\\":" + broker.priorityDecisions\n'
        '            + ",\\\"snapshot\\\":" + sessionSnapshot(game) + "}}");',
        '            + ",\\\"priority_decisions\\\":" + broker.priorityDecisions\n'
        '            + ",\\\"native_events\\\":" + jsonStringArray(broker.automatic)\n'
        '            + ",\\\"snapshot\\\":" + sessionSnapshot(game) + "}}");',
        "native event evidence in result",
    )

    path.write_text(java, encoding="utf-8")
    print("FORGE_PRIMITIVE_A_OVERLAY=PASS")


if __name__ == "__main__":
    main()
