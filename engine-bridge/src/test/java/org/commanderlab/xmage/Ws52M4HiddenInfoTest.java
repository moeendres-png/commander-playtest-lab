package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS52 M4 — principal-scoped hidden information.
 *
 * <p>Disjoint sentinel decks (seat 0: Islands; seat 1: Mountains) give
 * black-box ground truth without engine access: before any reveal, viewer
 * 0 must see Island identities and no Mountain identity, mirrored for
 * viewer 1. A planted-leak control at the exact enforcement point
 * ({@link XmageFullGameObservationGateway}) proves the detector fires, and
 * a cross-viewer positive control proves the string checks are live, not
 * vacuous.</p>
 */
class Ws52M4HiddenInfoTest {

    @Test
    void sentinelHandsLibrariesAndZonesArePrincipalScoped() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        String handleA = Ws52.importDeck(bridge, Ws52.sentinelDeckA());
        String handleB = Ws52.importDeck(bridge, Ws52.sentinelDeckB());
        Ws52.createFullGame(bridge, "ws52-m4-scoped", List.of(handleA, handleB), Ws52.SEED_A);
        Ws52.startFullGame(bridge);
        Ws52.Opening opening = Ws52.pilotOpening(bridge);
        assertEquals(1, opening.startingPlayerChoices());
        assertEquals(2, opening.mulligans());

        JsonObject obs0 = Ws52.getObservation(bridge, 0);
        JsonObject obs1 = Ws52.getObservation(bridge, 1);

        // Own hand: 7 named Islands for viewer 0; no hand key for the opponent.
        JsonObject self0 = playerView(obs0, 0);
        JsonObject opp0 = playerView(obs0, 1);
        assertTrue(self0.has("hand"), "viewer must see their own hand");
        assertEquals(7, self0.getAsJsonArray("hand").size());
        for (JsonElement element : self0.getAsJsonArray("hand")) {
            assertEquals("Island", element.getAsJsonObject().get("name").getAsString());
        }
        assertFalse(opp0.has("hand"), "opponent hand must be absent, not merely redacted");
        assertEquals(7, opp0.get("hand_count").getAsInt());

        // Opponent hand/library identities are hidden; own library order is hidden too.
        String text0 = obs0.toString();
        assertTrue(text0.contains("Island"), "own hand identities must be visible");
        assertFalse(text0.contains("Mountain"),
                () -> "opponent private identity leaked to viewer 0: " + text0);
        assertTrue(knownLibraryNames(obs0, 0).isEmpty());
        assertTrue(knownLibraryNames(obs0, 1).isEmpty());

        // Mirror for viewer 1.
        String text1 = obs1.toString();
        assertTrue(text1.contains("Mountain"), "own hand identities must be visible");
        assertFalse(text1.contains("Island"),
                () -> "opponent private identity leaked to viewer 1: " + text1);

        // Cross-viewer positive control: the checks above are live — the
        // forbidden name DOES appear in the other principal's view.
        assertTrue(text1.contains("Mountain") && text0.contains("Island"),
                "positive control: sentinel names must be visible to their owners");

        // Public zones stay public: both commanders visible to every viewer.
        assertTrue(text0.contains("Ishai, Ojutai Dragonspeaker"));
        assertTrue(text0.contains("Rograkh, Son of Rohgahh"));
        assertTrue(text1.contains("Ishai, Ojutai Dragonspeaker"));
        assertTrue(text1.contains("Rograkh, Son of Rohgahh"));

        // Pending decision frame for the actor carries no opponent identity.
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        int actorSeat = decision.get("seat").getAsInt();
        String forbiddenForActor = actorSeat == 0 ? "Mountain" : "Island";
        assertFalse(decision.toString().contains(forbiddenForActor),
                () -> "opponent identity in actor " + actorSeat + " decision frame");

        // Full transport audit: every observed response is checked against
        // the forbidden name of the principal that received it.
        assertFalse(text0.contains("Mountain"), "transport audit viewer 0");
        assertFalse(text1.contains("Island"), "transport audit viewer 1");
    }

    @Test
    void plantedLeakAtEnforcementPointFailsClosed() {
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(2);
            // Engine is now parked at a priority decision; the test thread
            // only reads live state and exercises the gateway (no mutation).
            Game game = harness.game;
            Player viewer = harness.players().get(0);
            Player opponent = harness.players().get(1);

            // Ground truth from live engine state (harness privilege, never pilot-visible).
            List<String> opponentHandNames = new ArrayList<>();
            for (Card card : opponent.getHand().getCards(game)) {
                opponentHandNames.add(card.getName());
            }
            assertEquals(7, opponentHandNames.size(),
                    "London keep must deal 7 lands, observed " + opponentHandNames.size());
            assertTrue(opponentHandNames.stream().allMatch("Mountain"::equals));
            String leakedName = opponentHandNames.get(0);

            // Sanity: the clean gateway path accepts neutral material.
            XmageFullGameObservationGateway.SafeDecision clean =
                    XmageFullGameObservationGateway.validate(
                            game, viewer, "Choose an option", new JsonObject(),
                            new JsonArray(), null);
            assertTrue(clean.prompt().equals("Choose an option"));

            // Planted leak: opponent private identity smuggled into the prompt.
            IllegalStateException leak = assertThrows(IllegalStateException.class,
                    () -> XmageFullGameObservationGateway.validate(
                            game, viewer, "Choose " + leakedName + " now", new JsonObject(),
                            new JsonArray(), null));
            assertTrue(leak.getMessage().contains("HIDDEN_INFORMATION_LEAK"),
                    () -> "planted leak must trip the detector: " + leak.getMessage());

            // Same name in the OWNER's view is authorized (no false positive).
            XmageFullGameObservationGateway.SafeDecision ownerClean =
                    XmageFullGameObservationGateway.validate(
                            game, opponent, "Choose " + leakedName + " now", new JsonObject(),
                            new JsonArray(), null);
            assertTrue(ownerClean.prompt().contains(leakedName));
        }
    }

    // ------------------------------------------------------------------

    private static JsonObject playerView(JsonObject observation, int seat) {
        JsonObject pilotState = observation.getAsJsonObject("observation");
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (player.get("seat").getAsInt() == seat) {
                return player;
            }
        }
        throw new IllegalStateException("no player view for seat " + seat);
    }

    private static List<String> knownLibraryNames(JsonObject observation, int seat) {
        JsonObject view = playerView(observation, seat);
        List<String> names = new ArrayList<>();
        if (view.has("known_library") && view.get("known_library").isJsonArray()) {
            for (JsonElement element : view.getAsJsonArray("known_library")) {
                names.add(element.getAsJsonObject().get("name").getAsString());
            }
        }
        return names;
    }
}
