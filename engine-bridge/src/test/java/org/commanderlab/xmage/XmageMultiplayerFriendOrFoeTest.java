package org.commanderlab.xmage;

import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Friend or foe at 3–6 players, with an actual card on the full-game lane.
 *
 * <p>P1 casts Pir's Whim (Oracle: "For each player, choose friend or foe. Each
 * friend searches their library for a land card, puts it onto the battlefield
 * tapped, then shuffles. Each foe sacrifices an artifact or enchantment they
 * control."). Every player controls a Mind Stone.</p>
 *
 * <ul>
 *   <li>P1 makes the choice for every player, itself included, in APNAP order
 *       (P1, P2, …, PN). P1 picks friend for odd seats and foe for even ones.</li>
 *   <li>Each friend, and nobody else, searches its own library, in APNAP order. It
 *       puts a Mountain onto the battlefield tapped and keeps its Mind Stone.</li>
 *   <li>Each foe, and nobody else, chooses its own sacrifice, in APNAP order, and
 *       gets no land.</li>
 * </ul>
 */
class XmageMultiplayerFriendOrFoeTest {

    private static final String WHIM = "Pir's Whim";
    private static final String STONE = "Mind Stone";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void theCasterLabelsEveryPlayerAndEachSideActsForItself(int playerCount) {
        String tag = "pir-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", WHIM, 0));
        for (int index = 0; index < 4; index++) {
            objects.add(obj("bf", "P1", "Forest", index));
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            objects.add(obj("bf", "P" + seat, STONE, 0));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        List<String> apnap = new ArrayList<>(List.of("P1"));
        for (int seat = 2; seat <= playerCount; seat++) {
            apnap.add("P" + seat);
        }

        XmageActualCardCorpusTest.cast(started, tag + "-cast", WHIM);
        List<String> labelled = new ArrayList<>();
        List<String> searchers = new ArrayList<>();
        List<String> sacrificers = new ArrayList<>();
        XmageActualCardCorpusTest.resolveAll(started, tag, "Forest — {T}: Add {G}.", (cls, step) -> {
            String actor = XmageActualCardCorpusTest.actorPid(started);
            String prompt = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                    .get("prompt").getAsString();
            switch (cls) {
                case "choose_use" -> {
                    assertEquals("P1", actor, "the caster chooses friend or foe for every player");
                    String subject = null;
                    for (String pid : apnap) {
                        if (prompt.equals("Is " + started.seats().get(pid).getName() + " friend or foe?")) {
                            subject = pid;
                        }
                    }
                    assertTrue(subject != null, prompt);
                    labelled.add(subject);
                    boolean friend = Integer.parseInt(subject.substring(1)) % 2 == 1;
                    XmageActualCardCorpusTest.submit(started, tag + "-ff-" + subject,
                            XmageActualCardCorpusTest.labelled(started, friend ? "Friend" : "Foe"));
                }
                case "target" -> {
                    assertTrue(prompt.contains("land card"), prompt);
                    searchers.add(actor);
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-search-" + actor, "Mountain", 1);
                }
                case "choose_object" -> {
                    assertTrue(prompt.contains("sacrifice"), prompt);
                    sacrificers.add(actor);
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-sac-" + actor, STONE, 1);
                }
                default -> {
                    return false;
                }
            }
            return true;
        });

        assertEquals(apnap, labelled, "every player is labelled once, in APNAP order");
        List<String> friends = apnap.stream().filter(pid -> Integer.parseInt(pid.substring(1)) % 2 == 1).toList();
        List<String> foes = apnap.stream().filter(pid -> Integer.parseInt(pid.substring(1)) % 2 == 0).toList();
        assertEquals(friends, searchers, "each friend searches its own library, in APNAP order");
        assertEquals(foes, sacrificers, "each foe chooses its own sacrifice, in APNAP order");
        for (String pid : apnap) {
            boolean friend = friends.contains(pid);
            assertEquals(friend ? 1 : 0, XmageActualCardCorpusTest.onBattlefield(started, pid, STONE), pid);
            assertEquals(friend ? 0 : 1, XmageActualCardCorpusTest.inGraveyard(started, pid, STONE), pid);
            List<Permanent> mountains = new ArrayList<>();
            for (Permanent permanent : game.getBattlefield().getAllActivePermanents(started.seats().get(pid).getId())) {
                if ("Mountain".equals(permanent.getName())) {
                    mountains.add(permanent);
                }
            }
            assertEquals(friend ? 1 : 0, mountains.size(), pid + ": a friend gets exactly one land");
            mountains.forEach(mountain -> assertTrue(mountain.isTapped(), pid + ": the land enters tapped"));
        }
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}
