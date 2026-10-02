package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.GameCommanderImpl;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * HIDDEN_11 systemic qualification: a native library shuffle invalidates
 * ordering of an earlier Rules-entitled look without erasing identity memory.
 *
 * <p>The actual-card route is Orcish Spy -> Elixir of Immortality. No bridge
 * helper fabricates either rules event: Spy's native effect performs the look
 * and Elixir's native effect calls {@code Player.shuffleLibrary}.</p>
 */
class XmageKnowledgeShuffleInvalidationTest {

    @Test
    void nativeShuffleInvalidatesEarlierLookOrderButRetainsPrivateIdentityMemory() throws Exception {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Orcish Spy", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Elixir of Immortality", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 2, Zone.BATTLEFIELD));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "hidden11-look-shuffle",
                4,
                "P1",
                objects,
                Map.of("P2", List.of("Vampiric Tutor", "Mystical Tutor", "Enlightened Tutor"))
        );
        GameCommanderImpl game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");
        Player p2 = s.seats.get("P2");

        // Losslessly choose a deliberately non-canonical top-three order so
        // retaining the old order is observable after the shuffle.
        List<String> current = libraryNames(p2, game);
        removeOnce(current, "Vampiric Tutor");
        removeOnce(current, "Mystical Tutor");
        removeOnce(current, "Enlightened Tutor");
        List<String> requested = new ArrayList<>(List.of(
                "Vampiric Tutor", "Mystical Tutor", "Enlightened Tutor"));
        requested.addAll(current);
        XmageHiddenStateRestoration.apply(
                game,
                s.seats,
                restoration(s.session),
                new XmageHiddenStateRestoration.Request(
                        List.of(new XmageHiddenStateRestoration.LibraryOrder("P2", requested)),
                        List.of())
        );
        assertEquals(
                List.of("Vampiric Tutor", "Mystical Tutor", "Enlightened Tutor"),
                libraryNames(p2, game).subList(0, 3)
        );

        JsonObject spy = s.action("activate_ability", "Orcish Spy");
        assertNotNull(spy, "native engine must offer Orcish Spy activation");
        s.submit(spy);
        assertEquals("target", s.decisionClass());
        JsonObject target = s.action("choose_targets", "Seat 2");
        assertNotNull(target, "native engine must offer P2 as Spy target");
        s.submit(target);
        resolveToEmptyStackPriority(s, game, "P1");

        JsonObject before = lastLook(XmageFullGameStateRedactor.actorView(game, p1));
        assertNotNull(before, "Spy must create a real principal-scoped look observation");
        assertFalse(before.has("order_invalidated_by_shuffle"));
        assertEquals(
                List.of("Vampiric Tutor", "Mystical Tutor", "Enlightened Tutor"),
                names(before)
        );
        for (String pid : List.of("P2", "P3", "P4")) {
            assertEquals(
                    0,
                    XmageFullGameStateRedactor.actorView(game, s.seats.get(pid))
                            .getAsJsonArray("looked_at").size(),
                    pid + " must not receive P1's private Spy look"
            );
        }

        XmageExternalRiskSignalTest.passToActor(s.session, "hidden11-pass", s.seats, "P2");
        JsonObject elixir = s.action("activate_ability", "Elixir of Immortality");
        assertNotNull(elixir, "native engine must offer Elixir activation");
        s.submit(elixir);
        while ("mana_payment".equals(s.decisionClass())) {
            s.payWith("Mountain");
        }
        resolveToEmptyStackPriority(s, game, "P2");

        JsonObject after = lastLook(XmageFullGameStateRedactor.actorView(game, p1));
        assertNotNull(after);
        assertTrue(
                after.has("order_invalidated_by_shuffle")
                        && after.get("order_invalidated_by_shuffle").getAsBoolean(),
                "a later native shuffle must explicitly invalidate the earlier order"
        );
        List<String> remembered = names(after);
        assertEquals(
                List.of("Enlightened Tutor", "Mystical Tutor", "Vampiric Tutor"),
                remembered,
                "identity memory remains, but only in deterministic non-order form"
        );
        assertNotEquals(
                List.of("Vampiric Tutor", "Mystical Tutor", "Enlightened Tutor"),
                remembered,
                "pre-shuffle engine order must not survive as current-order knowledge"
        );
        for (String pid : List.of("P2", "P3", "P4")) {
            assertEquals(
                    0,
                    XmageFullGameStateRedactor.actorView(game, s.seats.get(pid))
                            .getAsJsonArray("looked_at").size(),
                    pid + " must still not inherit P1's remembered identities"
            );
        }
    }

    private static void resolveToEmptyStackPriority(
            XmageMultiplayerScenario s, GameCommanderImpl game, String expectedActor) {
        boolean sawStack = !game.getStack().isEmpty();
        for (int i = 0; i < 40; i++) {
            if ("priority".equals(s.decisionClass())
                    && game.getStack().isEmpty()
                    && sawStack
                    && expectedActor.equals(s.actor())) {
                return;
            }
            if (!game.getStack().isEmpty()) {
                sawStack = true;
            }
            if (!"priority".equals(s.decisionClass())) {
                fail("unexpected decision while resolving actual-card event: "
                        + s.decisionClass() + " " + s.labels());
            }
            JsonObject pass = s.action("pass_priority", "Pass");
            assertNotNull(pass);
            s.submit(pass);
        }
        fail("actual-card event did not resolve within bound");
    }

    private static XmageNativeStateRestoration restoration(XmageFullGameSession session)
            throws Exception {
        Field field = XmageFullGameSession.class.getDeclaredField("restoration");
        field.setAccessible(true);
        return (XmageNativeStateRestoration) field.get(session);
    }

    private static List<String> libraryNames(Player player, GameCommanderImpl game) {
        List<String> names = new ArrayList<>();
        for (Card card : player.getLibrary().getCards(game)) {
            names.add(card.getName());
        }
        return names;
    }

    private static void removeOnce(List<String> names, String wanted) {
        assertTrue(names.remove(wanted), "library must contain " + wanted);
    }

    private static JsonObject lastLook(JsonObject view) {
        JsonArray looked = view.getAsJsonArray("looked_at");
        return looked == null || looked.size() == 0
                ? null
                : looked.get(looked.size() - 1).getAsJsonObject();
    }

    private static List<String> names(JsonObject observation) {
        List<String> result = new ArrayList<>();
        for (JsonElement element : observation.getAsJsonArray("cards")) {
            result.add(element.getAsJsonObject().get("name").getAsString());
        }
        return result;
    }
}
