package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Assist (CR 702.132a) at 3–6 players, with an actual card on the full-game
 * lane.
 *
 * <p>P1 casts Gang Up (Oracle: "{X}{B} Instant. Assist. Destroy target creature
 * with power X or less.") with X = 3 against P2's Hill Giant. P1 has only two
 * Swamps. Every opponent has three Islands.</p>
 *
 * <ul>
 *   <li>The engine offers assist as a payment action to the caster. The
 *       assisting player may be any other player, and only other players are
 *       offered.</li>
 *   <li>P1 chooses P3. P3, and not P1, announces how much to pay. The maximum is
 *       the generic part of the total cost, 3. P3 pays 2 with its own Islands.</li>
 *   <li>P1 pays the rest ({B} and 1 generic) with its Swamps. The spell resolves
 *       and destroys the 3-power Hill Giant.</li>
 *   <li>No other player's lands are touched.</li>
 * </ul>
 */
class XmageMultiplayerAssistTest {

    private static final String GANG_UP = "Gang Up";
    private static final String SWAMP_LABEL = "Swamp — {T}: Add {B}.";
    private static final String ISLAND_LABEL = "Island — {T}: Add {U}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void anotherPlayerPaysPartOfTheGenericCostWithTheirOwnMana(int playerCount) {
        String tag = "assist-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", GANG_UP, 0));
        objects.add(obj("bf", "P1", "Swamp", 0));
        objects.add(obj("bf", "P1", "Swamp", 1));
        for (int seat = 2; seat <= playerCount; seat++) {
            for (int index = 0; index < 3; index++) {
                objects.add(obj("bf", "P" + seat, "Island", index));
            }
        }
        objects.add(obj("bf", "P2", "Hill Giant", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", GANG_UP);
        List<String> frames = new ArrayList<>();
        boolean[] assisted = {false};
        XmageActualCardCorpusTest.resolveAll(started, tag, null, (cls, step) -> {
            String actor = XmageActualCardCorpusTest.actorPid(started);
            String prompt = started.session().pendingDecisionPayload()
                    .getAsJsonObject("decision").get("prompt").getAsString();
            List<String> labels = labels(started);
            frames.add(actor + "|" + cls);
            switch (cls) {
                case "announce_x" -> {
                    if ("P1".equals(actor)) {
                        XmageActualCardCorpusTest.submitNumeric(started, tag + "-x", 3);
                    } else {
                        assertEquals("P3", actor, "the chosen player announces the assist amount");
                        assertTrue(prompt.contains("assist"), prompt);
                        JsonObject context = started.session().pendingDecisionPayload()
                                .getAsJsonObject("decision").getAsJsonObject("context");
                        assertEquals(0, context.get("numeric_min").getAsInt());
                        assertEquals(3, context.get("numeric_max").getAsInt(),
                                "assist covers at most the generic part of the total cost");
                        XmageActualCardCorpusTest.submitNumeric(started, tag + "-assist-x", 2);
                    }
                }
                case "target" -> {
                    if (labels.stream().anyMatch(label -> label.startsWith("Hill Giant"))) {
                        XmageActualCardCorpusTest.chooseByExactName(started, tag + "-giant", "Hill Giant", 1);
                    } else {
                        assertTrue(prompt.contains("another player"), prompt);
                        assertEquals(playerCount - 1, labels.size(),
                                "every other player, and only other players, may assist: " + labels);
                        String self = started.seats().get("P1").getId().toString();
                        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                    .getAsJsonObject("xmage_option_metadata");
                            assertTrue(!self.equals(meta.get("object_id").getAsString()),
                                    "the caster cannot assist itself");
                        }
                        XmageActualCardCorpusTest.submit(started, tag + "-helper",
                                XmageActualCardCorpusTest.playerTarget(started, "P3"));
                    }
                }
                case "mana_payment" -> {
                    if ("P1".equals(actor) && !assisted[0]) {
                        assisted[0] = true;
                        XmageActualCardCorpusTest.submit(started, tag + "-assist",
                                XmageActualCardCorpusTest.labelled(started, "Assist"));
                    } else if ("P1".equals(actor)) {
                        if (labels.stream().anyMatch(label -> label.equals("Spend colorless mana from pool"))
                                && !unpaid(started).contains("{B}")) {
                            // The assist payment sits in P1's pool as generic-only mana.
                            XmageActualCardCorpusTest.submit(started, tag + "-spend-assist-" + step,
                                    XmageActualCardCorpusTest.labelled(started, "Spend colorless mana from pool"));
                        } else {
                            XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-pay-" + step,
                                    List.of("Swamp"), Set.of(SWAMP_LABEL));
                        }
                    } else {
                        assertEquals("P3", actor, "only the chosen player pays the assist");
                        XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-assist-pay-" + step,
                                List.of("Island"), Set.of(ISLAND_LABEL));
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        });

        assertTrue(assisted[0], "assist must be engine-offered to the caster: " + frames);
        assertTrue(frames.contains("P3|announce_x"), "P3 announced its own assist: " + frames);
        assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P2", "Hill Giant"),
                "Gang Up with X=3 destroys the 3-power Hill Giant");
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P2", "Hill Giant"));
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", GANG_UP));
        assertEquals(2, tapped(started, game, "P1", "Swamp"), "P1 paid {B} and 1 generic");
        for (int seat = 2; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            assertEquals("P3".equals(pid) ? 2 : 0, tapped(started, game, pid, "Island"),
                    pid + ": only the assisting player's lands pay, exactly the assisted amount");
        }
        for (String pid : started.seats().keySet()) {
            assertEquals(0, started.seats().get(pid).getManaPool().getMana().count(),
                    pid + ": no mana left floating");
        }
    }

    private static String unpaid(XmageActualCardCorpusTest.Started started) {
        return started.session().pendingDecisionPayload().getAsJsonObject("decision")
                .getAsJsonObject("context").get("unpaid_mana").getAsString();
    }

    private static List<String> labels(XmageActualCardCorpusTest.Started started) {
        List<String> labels = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
            labels.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        return labels;
    }

    private static int tapped(XmageActualCardCorpusTest.Started started, Game game, String pid, String name) {
        int tapped = 0;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(started.seats().get(pid).getId())) {
            if (name.equals(permanent.getName()) && permanent.isTapped()) {
                tapped++;
            }
        }
        return tapped;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}
