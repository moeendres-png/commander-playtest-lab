#!/usr/bin/env python3
"""Qualification-only Forge AF05 hidden-information overlay.

Applied after the existing Primitive-A overlay to the generated GPL-side provider.
Forge remains the Rules Core. The overlay uses Forge GameState for the exact canonical
state, Card.mayPlayerLook/CardView.canFaceDownBeShownTo for native visibility facts,
and viewer-scoped opaque handles for actor-facing object identity.
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
        '        final java.util.List<String> automatic = new ArrayList<>();\n',
        '        final java.util.List<String> automatic = new ArrayList<>();\n'
        '        final java.util.Map<String, String> actorOpaqueRefs = new java.util.HashMap<>();\n',
        "opaque actor identity map",
    )
    java = replace_once(
        java,
        '        void recordAutomatic(String name) { automatic.add(name); }\n',
        '        void recordAutomatic(String name) { automatic.add(name); }\n\n'
        '        String opaqueCardRef(Player viewer, Card card) {\n'
        '            String key = viewer.getName() + ":" + card.getId();\n'
        '            return actorOpaqueRefs.computeIfAbsent(key, ignored -> "obj-" + java.util.UUID.randomUUID());\n'
        '        }\n',
        "opaque actor identity helper",
    )

    java = replace_once(
        java,
        '                + ",\\\"options_digest\\\":" + esc(digest(ids))\n'
        '                + ",\\\"options\\\":[" + opts + "]}}");',
        '                + ",\\\"options_digest\\\":" + esc(digest(ids))\n'
        '                + ",\\\"options\\\":[" + opts + "]"\n'
        '                + ",\\\"observation\\\":" + actorSnapshot(actor.getGame(), actor, this) + "}}");',
        "actor observation on decision frame",
    )

    java = replace_once(
        java,
        '            if (isPrimitiveAFixture(finalistFixture)\n'
        '                    && automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) {\n'
        '                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");\n'
        '            }\n'
        '            priorityDecisions++;',
        '            if (isPrimitiveAFixture(finalistFixture)\n'
        '                    && automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) {\n'
        '                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");\n'
        '            }\n'
        '            if (isAf05Fixture(finalistFixture) && priorityDecisions >= 1) {\n'
        '                throw new ControlledStop("FINALIST_AF05_TERMINAL");\n'
        '            }\n'
        '            priorityDecisions++;',
        "AF05 terminal stop",
    )

    java = replace_once(
        java,
        '        forge.StaticData.instance().getCommonCards().addCard(finalistBearsCard);',
        '        forge.StaticData.instance().getCommonCards().addCard(finalistBearsCard);\n'
        '        forge.card.CardRules finalistDemonicRules = finalistReader.attemptToLoadCard("Demonic Tutor");\n'
        '        forge.card.CardRules finalistVampiricRules = finalistReader.attemptToLoadCard("Vampiric Tutor");\n'
        '        forge.card.CardRules finalistSolRingRules = finalistReader.attemptToLoadCard("Sol Ring");\n'
        '        if (finalistDemonicRules == null || finalistVampiricRules == null || finalistSolRingRules == null) throw new ControlledStop("FINALIST_AF05_CARD_RULES_MISSING");\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistDemonicRules, "UMA", forge.card.CardRarity.Rare));\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistVampiricRules, "CMR", forge.card.CardRarity.Rare));\n'
        '        forge.StaticData.instance().getCommonCards().addCard(new PaperCard(finalistSolRingRules, "C21", forge.card.CardRarity.Uncommon));',
        "AF05 headless card registration",
    )

    helper_anchor = '    static boolean isPrimitiveAFixture(String fixtureId) {'
    helper = r'''    static boolean isAf05Fixture(String fixtureId) {
        return "HIDDEN_01".equals(fixtureId) || "HIDDEN_02".equals(fixtureId);
    }

    static String seatRef(Game game, Player player) {
        int index = game.getPlayers().indexOf(player);
        return index < 0 ? null : "P" + (index + 1);
    }

    static String originalCardName(Card card) {
        return card.getPaperCard() == null ? card.getName() : card.getPaperCard().getName();
    }

    static boolean forgeMayRevealIdentity(Card card, Player viewer, ZoneType zone) {
        if (zone == ZoneType.Hand) {
            return card.getOwner() == viewer || card.mayPlayerLook(viewer);
        }
        if (zone == ZoneType.Library) {
            return card.mayPlayerLook(viewer);
        }
        if (card.isFaceDown()) {
            return card.getView().canFaceDownBeShownTo(viewer.getView()) || card.mayPlayerLook(viewer);
        }
        return zone == ZoneType.Battlefield || zone == ZoneType.Graveyard
            || zone == ZoneType.Exile || zone == ZoneType.Command;
    }

    static String actorCard(Card card, Player viewer, ZoneType zone, Broker broker) {
        boolean reveal = forgeMayRevealIdentity(card, viewer, zone);
        return "{\"object_id\":" + esc(broker.opaqueCardRef(viewer, card))
            + ",\"face_down\":" + card.isFaceDown()
            + ",\"name\":" + esc(reveal ? originalCardName(card) : "Hidden card") + "}";
    }

    static String actorCards(Player subject, Player viewer, ZoneType zone, Broker broker, boolean includeOnlyVisible) {
        StringBuilder sb = new StringBuilder("[");
        int n = 0;
        for (Card card : subject.getCardsIn(zone)) {
            if (includeOnlyVisible && !forgeMayRevealIdentity(card, viewer, zone)) continue;
            if (n++ > 0) sb.append(',');
            sb.append(actorCard(card, viewer, zone, broker));
        }
        return sb.append(']').toString();
    }

    static String actorBattlefield(Player subject, Player viewer, Broker broker) {
        StringBuilder sb = new StringBuilder("[");
        int n = 0;
        for (Card card : subject.getCardsIn(ZoneType.Battlefield)) {
            if (n++ > 0) sb.append(',');
            sb.append(actorCard(card, viewer, ZoneType.Battlefield, broker));
        }
        return sb.append(']').toString();
    }

    static String actorSnapshot(Game game, Player viewer, Broker broker) {
        StringBuilder players = new StringBuilder();
        int n = 0;
        for (Player subject : game.getPlayers()) {
            if (n++ > 0) players.append(',');
            players.append("{\"player_id\":").append(esc(seatRef(game, subject)))
                .append(",\"life\":").append(subject.getLife())
                .append(",\"hand_count\":").append(subject.getCardsIn(ZoneType.Hand).size())
                .append(",\"library_count\":").append(subject.getCardsIn(ZoneType.Library).size())
                .append(",\"graveyard_count\":").append(subject.getCardsIn(ZoneType.Graveyard).size())
                .append(",\"battlefield\":").append(actorBattlefield(subject, viewer, broker))
                .append(",\"graveyard\":").append(actorCards(subject, viewer, ZoneType.Graveyard, broker, true))
                .append(",\"command\":").append(actorCards(subject, viewer, ZoneType.Command, broker, true))
                .append(",\"exile\":").append(actorCards(subject, viewer, ZoneType.Exile, broker, true));
            if (subject == viewer || !actorCards(subject, viewer, ZoneType.Hand, broker, true).equals("[]")) {
                players.append(",\"hand\":").append(actorCards(subject, viewer, ZoneType.Hand, broker, true));
            }
            players.append(",\"known_library\":").append(actorCards(subject, viewer, ZoneType.Library, broker, true))
                .append('}');
        }
        return "{\"viewer_player_id\":" + esc(seatRef(game, viewer))
            + ",\"player_count\":" + game.getPlayers().size()
            + ",\"players\":[" + players + "]}";
    }

    static String af05PrivilegedSnapshot(Game game) {
        StringBuilder players = new StringBuilder();
        int n = 0;
        for (Player p : game.getPlayers()) {
            if (n++ > 0) players.append(',');
            players.append("{\"player_id\":").append(esc(seatRef(game, p)))
                .append(",\"life\":").append(p.getLife())
                .append(",\"commander\":").append(esc(singleCommanderName(p)))
                .append(",\"hand_names\":").append(esc(zoneNames(p, ZoneType.Hand)))
                .append(",\"library_names\":").append(esc(zoneNames(p, ZoneType.Library)))
                .append(",\"exile_names\":").append(esc(zoneNames(p, ZoneType.Exile)))
                .append(",\"battlefield\":").append(actorCards(p, p, ZoneType.Battlefield, new Broker(new BufferedReader(new java.io.StringReader("")), new PrintWriter(new java.io.StringWriter()), 1), false))
                .append('}');
        }
        return "{\"turn\":" + game.getPhaseHandler().getTurn()
            + ",\"phase\":" + esc(String.valueOf(game.getPhaseHandler().getPhase()))
            + ",\"active_actor\":" + esc(game.getPhaseHandler().getPlayerTurn() == null ? null : game.getPhaseHandler().getPlayerTurn().getName())
            + ",\"priority_actor\":" + esc(game.getPhaseHandler().getPriorityPlayer() == null ? null : game.getPhaseHandler().getPriorityPlayer().getName())
            + ",\"players\":[" + players + "]}";
    }

    static void applyAf05State(Game game, String fixtureId, Broker broker) {
        if (!isAf05Fixture(fixtureId)) return;
        java.util.List<String> lines = java.util.List.of(
            "turn=1",
            "activeplayer=p0",
            "activephase=MAIN1",
            "p0life=40",
            "p0hand=",
            "p0battlefield=Grizzly Bears|FaceDown",
            "p0library=",
            "p0graveyard=",
            "p0exile=",
            "p0command=Rograkh, Son of Rohgahh|IsCommander",
            "p1life=40",
            "p1hand=Demonic Tutor",
            "p1battlefield=",
            "p1library=Vampiric Tutor",
            "p1graveyard=",
            "p1exile=Sol Ring",
            "p1command=Rograkh, Son of Rohgahh|IsCommander",
            "p2life=40",
            "p2hand=",
            "p2battlefield=",
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
        java.util.concurrent.atomic.AtomicReference<RuntimeException> stateFailure =
            new java.util.concurrent.atomic.AtomicReference<>();
        game.getAction().invoke(() -> {
            try {
                state.applyToGame(game);
                game.getPhaseHandler().setPriority(game.getPlayers().get(0));
            } catch (RuntimeException exc) {
                stateFailure.set(exc);
            } finally {
                stateApplied.countDown();
            }
        });
        try {
            if (!stateApplied.await(30, java.util.concurrent.TimeUnit.SECONDS)) {
                throw new ControlledStop("FINALIST_AF05_STATE_APPLY_TIMEOUT");
            }
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new ControlledStop("FINALIST_AF05_STATE_APPLY_INTERRUPTED");
        }
        if (stateFailure.get() != null) throw stateFailure.get();
        broker.out.println("{\"protocol\":" + esc(PROTOCOL)
            + ",\"message_type\":\"QUALIFICATION_STATE\""
            + ",\"request_id\":\"af05-state\""
            + ",\"session_id\":" + esc(SESSION_ID)
            + ",\"payload\":{\"stage\":\"after_native_setup_validation\",\"snapshot\":" + af05PrivilegedSnapshot(game) + "}}");
        broker.out.flush();
    }

    static boolean isPrimitiveAFixture(String fixtureId) {'''
    java = replace_once(java, helper_anchor, helper, "AF05 state and projection helpers")

    java = replace_once(
        java,
        '            if (isPrimitiveAFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyPrimitiveAState(game, finalistFixtureId, broker));\n'
        '            } else {\n'
        '                match.startGame(game);\n'
        '            }',
        '            if (isPrimitiveAFixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyPrimitiveAState(game, finalistFixtureId, broker));\n'
        '            } else if (isAf05Fixture(finalistFixtureId)) {\n'
        '                match.startGame(game, () -> applyAf05State(game, finalistFixtureId, broker));\n'
        '            } else {\n'
        '                match.startGame(game);\n'
        '            }',
        "AF05 native state hook",
    )

    path.write_text(java, encoding="utf-8")
    print("FORGE_AF05_OVERLAY=PASS")


if __name__ == "__main__":
    main()
