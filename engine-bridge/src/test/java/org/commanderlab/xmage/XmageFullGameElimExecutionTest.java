package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * DR-CLOSURE-01 Phase 2: elimination-state blocker characterization.
 *
 * <p>Execution proved the four life-0 elimination fixtures are NOT restorable
 * through pre-start {@code setLife(0)}: the engine re-derives starting life
 * (40) during game start, so the life-0 player arrives alive at 40 with no
 * elimination and no cleanup. The lab must not fake elimination states, so
 * these cells stay {@code NOT_RUN_BLOCKED} with this exact mechanism as the
 * reason (genuine loss causation via real damage is executor scope, not
 * restoration scope). These tests pin the fail-closed behavior so any future
 * engine/pin change that alters it is caught.</p>
 */
class XmageFullGameElimExecutionTest {

    @Test
    void elimLifeZeroResetsToStartingLife3P() {
        characterizeElimBlocker("WS05-MP-ELIM-OWNED-3", "exec-elim-owned-3", "P2", 3);
    }

    @Test
    void elimLifeZeroResetsToStartingLife5P() {
        characterizeElimBlocker("WS05-MP-ELIM-5", "exec-elim-5", "P3", 5);
    }

    static void characterizeElimBlocker(
            String fixtureId, String gameTag, String zeroLifePid, int playerCount) {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord(fixtureId),
                        gameTag, 424242L);
        assertEquals(playerCount, plan.playerCount(), "exact count for " + fixtureId);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, gameTag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);

        // Exact mechanism: engine re-derives starting life; no elimination.
        Player zeroed = seats.get(zeroLifePid);
        assertFalse(zeroed.hasLost() || zeroed.hasLeft(),
                "the lab must not manufacture elimination: " + zeroLifePid + " arrives alive");
        for (JsonElement seatElement : observed.getAsJsonArray("seats")) {
            JsonObject seat = seatElement.getAsJsonObject();
            if (seat.get("player_id").getAsString().equals(zeroLifePid)) {
                assertEquals(40, seat.get("life").getAsInt(),
                        "engine resets starting life during game start");
            }
        }
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoration.compare(observed, seats);
        assertFalse(verdict.match(), "life pin must mismatch (requested 0, engine 40)");
        boolean lifePinFound = false;
        for (String mismatch : verdict.mismatches()) {
            if (mismatch.startsWith("life " + zeroLifePid)) {
                lifePinFound = true;
            }
        }
        assertTrue(lifePinFound, "mismatch must name the life pin: " + verdict.mismatches());
        // No fake cleanup either: the departed-owned Sol Ring stays put.
        if (fixtureId.equals("WS05-MP-ELIM-OWNED-3")) {
            boolean ringPresent = false;
            for (Permanent permanent : session.restorationGame()
                    .getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals("Sol Ring")
                        && zeroed.getId().equals(permanent.getOwnerId())) {
                    ringPresent = true;
                }
            }
            assertTrue(ringPresent, "no elimination means no cleanup may be faked");
        }
    }
}
