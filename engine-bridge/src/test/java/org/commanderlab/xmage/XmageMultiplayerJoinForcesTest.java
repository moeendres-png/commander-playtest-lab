package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Join forces at 3–6 players, with an actual card on the full-game lane.
 *
 * <p>P1 casts Minds Aglow (Oracle: "Join forces — Starting with you, each
 * player may pay any amount of mana. Each player draws X cards, where X is the
 * total amount of mana paid this way.").</p>
 *
 * <ul>
 *   <li>Every player, the non-active ones included, announces and pays their own
 *       amount through the external surface. The order is P1, then the engine's
 *       turn order: P2, …, PN.</li>
 *   <li>P1 pays 1 and PN pays 2. P(N−1) has no lands: it announces 2, can only
 *       cancel the payment, and contributes 0. Every other player pays 1.</li>
 *   <li>Each player draws exactly X, the total mana actually paid. An announced
 *       but unpaid amount does not count.</li>
 * </ul>
 */
class XmageMultiplayerJoinForcesTest {

    private static final String AGLOW = "Minds Aglow";
    private static final String ISLAND_LABEL = "Island — {T}: Add {U}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void eachPlayerPaysTheirOwnShareInOrderAndEveryoneDrawsTheTotal(int playerCount) {
        String tag = "aglow-" + playerCount + "p";
        String pn = "P" + playerCount;
        String broke = "P" + (playerCount - 1);
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-MindsAglow", AGLOW, "P1", "P1", mage.constants.Zone.HAND, false));
        Map<String, Integer> planned = new LinkedHashMap<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            if (!pid.equals(broke)) {
                for (int index = 0; index < 3; index++) {
                    objects.add(new XmageNativeStateRestoration.RequestedObject(
                            "obj:bf-" + pid + "-" + index + "-Island", "Island", pid, pid,
                            mage.constants.Zone.BATTLEFIELD, false));
                }
            }
            planned.put(pid, pid.equals(pn) ? 2 : pid.equals(broke) ? 2 : 1);
        }
        int paidTotal = 0;
        for (Map.Entry<String, Integer> entry : planned.entrySet()) {
            paidTotal += entry.getKey().equals(broke) ? 0 : entry.getValue();
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", AGLOW);
        Map<String, Integer> handBefore = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> handBefore.put(pid, player.getHand().size()));

        List<String> announcers = new ArrayList<>();
        final int total = paidTotal;
        XmageActualCardCorpusTest.resolveAll(started, tag, null, (cls, step) -> {
            String actor = XmageActualCardCorpusTest.actorPid(started);
            switch (cls) {
                case "announce_x" -> {
                    announcers.add(actor);
                    XmageActualCardCorpusTest.submitNumeric(started, tag + "-x-" + actor,
                            planned.get(actor));
                }
                case "mana_payment" -> {
                    if (actor.equals(broke)) {
                        JsonObject cancel = null;
                        for (JsonElement element : started.session().legalActionsPayload()
                                .getAsJsonArray("actions")) {
                            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                            if ("cancel_mana_payment".equals(meta.get("option_type").getAsString())) {
                                cancel = element.getAsJsonObject();
                            }
                        }
                        assertNotNull(cancel, "an unpayable announcement can be cancelled");
                        XmageActualCardCorpusTest.submit(started, tag + "-cancel-" + step, cancel);
                    } else {
                        XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-pay-" + step,
                                List.of("Island"), Set.of(ISLAND_LABEL));
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        });

        List<String> expectedOrder = new ArrayList<>();
        expectedOrder.add("P1");
        for (int seat = 2; seat <= playerCount; seat++) {
            expectedOrder.add("P" + seat);
        }
        assertEquals(expectedOrder, announcers,
                "join forces: starting with the caster, then turn order; every player once");
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            int tapped = 0;
            for (Permanent permanent : game.getBattlefield()
                    .getAllActivePermanents(started.seats().get(pid).getId())) {
                tapped += "Island".equals(permanent.getName()) && permanent.isTapped() ? 1 : 0;
            }
            int expectedTapped = pid.equals(broke) ? 0 : planned.get(pid) + ("P1".equals(pid) ? 1 : 0);
            assertEquals(expectedTapped, tapped, pid + " paid exactly its own share");
            assertEquals(handBefore.get(pid) + total, started.seats().get(pid).getHand().size(),
                    pid + " draws X = " + total + " (unpaid announcements don't count)");
        }
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", AGLOW));
        if (!game.getStack().isEmpty()) {
            fail("the stack should be empty");
        }
    }
}
