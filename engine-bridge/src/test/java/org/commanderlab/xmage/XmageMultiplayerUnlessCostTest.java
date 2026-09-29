package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * "You may draw a card unless that player pays {1}" in multiplayer, with an
 * actual card on the full-game lane.
 *
 * <p>P1 controls Rhystic Study (Oracle: "Whenever an opponent casts a spell,
 * you may draw a card unless that player pays {1}."). On P1's turn,
 * non-active P3 gets priority and casts Shock at P2, with a second Mountain
 * available to pay. Both decisions reach the right principal through the
 * external surface: P1 for "draw", P3 for "pay". Each outcome is honoured.</p>
 *
 * <p><b>F-19 (engine, pinned and upstream):</b> the official ruling says P3 decides
 * whether to pay first, and P1 decides whether to draw only after that. XMage
 * asks P1 first. The payer-first order was pinned by a disabled test (fixed in the XMage multiplayer candidate f79e4168 (moeendres-png/mage#24) and enabled by the 2026-09-29 successor repin)
 * until the Rules Core fix (Mage fork branch
 * {@code claude/f19-unless-pays-order-20260929}) is admitted by a Lab repin.</p>
 */
class XmageMultiplayerUnlessCostTest {

    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";

    @ParameterizedTest(name = "{0} players, P3 pays: {1}")
    @CsvSource({"4, true", "4, false", "5, true", "5, false"})
    void theCasterDecidesThePaymentAndTheControllerTheDraw(int playerCount, boolean pays) {
        Run run = run(playerCount, pays);
        assertTrue(run.asks.contains("P3:pay"), "the paying player decides: " + run.asks);
        assertEquals(!pays, run.asks.contains("P1:draw"),
                "the controller decides whether to draw only if the cost was not paid: " + run.asks);
        for (String ask : run.asks) {
            assertTrue(ask.equals("P1:draw") || ask.equals("P3:pay"),
                    "no other player is asked: " + run.asks);
        }
        assertEquals(pays ? run.p1HandBefore : run.p1HandBefore + 1, run.p1HandAfter,
                pays ? "P3 paid: no card" : "P3 declined: P1 draws");
        assertEquals(38, run.p2Life, "Shock resolves");
    }

    @ParameterizedTest(name = "{0} players, P3 pays: {1}")
    @CsvSource({"4, true", "4, false", "5, true", "5, false"})
    void thePayingPlayerDecidesBeforeTheController(int playerCount, boolean pays) {
        Run run = run(playerCount, pays);
        assertEquals(pays ? List.of("P3:pay") : List.of("P3:pay", "P1:draw"), run.asks);
    }

    private record Run(List<String> asks, int p1HandBefore, int p1HandAfter, int p2Life) {
    }

    private static Run run(int playerCount, boolean pays) {
        String tag = "rhystic-" + playerCount + "p-" + pays;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("bf", "P1", "Rhystic Study", 0, mage.constants.Zone.BATTLEFIELD));
        objects.add(obj("hand", "P3", "Shock", 0, mage.constants.Zone.HAND));
        objects.add(obj("bf", "P3", "Mountain", 0, mage.constants.Zone.BATTLEFIELD));
        objects.add(obj("bf", "P3", "Mountain", 1, mage.constants.Zone.BATTLEFIELD));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        int handBefore = started.seats().get("P1").getHand().size();
        List<String> asks = new ArrayList<>();
        boolean cast = false;
        for (int step = 0; step < 100; step++) {
            JsonObject decision = started.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            String cls = decision.get("decision_class").getAsString();
            String actor = XmageActualCardCorpusTest.actorPid(started);
            if ("priority".equals(cls) && cast && game.getStack().isEmpty()) {
                break;
            }
            if ("priority".equals(cls) && "P3".equals(actor) && !cast) {
                XmageActualCardCorpusTest.cast(started, tag + "-shock", "Shock");
                cast = true;
                continue;
            }
            String prompt = decision.get("prompt").getAsString().toLowerCase(Locale.ROOT);
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "target" -> XmageActualCardCorpusTest.submit(started, tag + "-t",
                        XmageActualCardCorpusTest.playerTarget(started, "P2"));
                case "mana_payment" -> XmageActualCardCorpusTest.payOneFromRestoredMana(started,
                        tag + "-pay-" + step, List.of("Mountain"), Set.of(MOUNTAIN_LABEL));
                case "choose_use" -> {
                    boolean draw = prompt.startsWith("draw a card");
                    boolean pay = prompt.startsWith("pay {1}");
                    if (!draw && !pay) {
                        fail("unexpected yes/no question: " + prompt);
                    }
                    asks.add(actor + (draw ? ":draw" : ":pay"));
                    XmageActualCardCorpusTest.submit(started, tag + "-use-" + step,
                            XmageActualCardCorpusTest.labelled(started, draw || pays ? "Yes" : "No"));
                }
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertTrue(cast, "P3 cast Shock");
        return new Run(asks, handBefore, started.seats().get("P1").getHand().size(),
                started.seats().get("P2").getLife());
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index, mage.constants.Zone zone) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, zone, false);
    }
}
