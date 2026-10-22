package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #961 D-3: the lists a view takes from hash collections keyed by random UUIDs (a player's
 * command zone, the commanders of the commander status) come out in Rules-visible order, so the
 * state the pilot sees is the same in every replay of one seed. A partner pair is the smallest
 * state where the order can differ; each game draws new UUIDs, so several games are played.
 */
class XmageFullGameViewOrderTest {

    private static final int GAMES = 8;

    private static List<String> names(JsonArray items) {
        List<String> names = new ArrayList<>();
        for (JsonElement item : items) {
            names.add(item.getAsJsonObject().get("name").getAsString());
        }
        return names;
    }

    private static void assertSorted(List<String> names, String what) {
        List<String> sorted = new ArrayList<>(names);
        sorted.sort(String::compareTo);
        assertEquals(sorted, names, what + " must follow the commanders' names, not their UUIDs");
    }

    @Test
    void commandZoneAndCommanderStatusAreOrderedByName() {
        boolean sawPartnerPair = false;
        for (int game = 0; game < GAMES; game++) {
            XmageFullGamePartnerExecutionTest.Arrived arrived =
                    XmageFullGamePartnerExecutionTest.restoreAndArrive(
                            "WS05-CMD-PARTNER-ZONE", "view-order-" + game);
            Game engine = arrived.session().restorationGame();
            Player actor = arrived.seats().get("P1");
            JsonObject view = XmageFullGameStateRedactor.actorView(engine, actor);
            for (JsonElement playerElement : view.getAsJsonArray("players")) {
                JsonArray command = playerElement.getAsJsonObject().getAsJsonArray("command");
                assertSorted(names(command), "players[].command");
                sawPartnerPair |= command.size() >= 2;
            }
            // Per player the commanders of the status are consecutive; each run of one owner is sorted.
            List<String> run = new ArrayList<>();
            String owner = null;
            for (JsonElement statusElement : view.getAsJsonArray("commander_status")) {
                JsonObject status = statusElement.getAsJsonObject();
                String statusOwner = status.get("owner_id").getAsString();
                if (!statusOwner.equals(owner)) {
                    assertSorted(run, "commander_status of " + owner);
                    run.clear();
                    owner = statusOwner;
                }
                run.add(status.get("name").getAsString());
            }
            assertSorted(run, "commander_status of " + owner);
        }
        assertTrue(sawPartnerPair, "the fixture must put two commanders in one command zone");
    }
}
