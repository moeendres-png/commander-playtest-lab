package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * DR-CLOSURE-01 Phase 2: exact N-scoped execution of the two hand-restored
 * trigger fixtures newly unblocked by the Phase 1 hand dimension.
 *
 * <p>Each run restores the frozen record at the exact player count and seed
 * (424242), arrives naturally, casts the restored Grizzly Bears from P1's
 * hand through the engine's own legality pipeline (paying {1}{G} via the two
 * restored Forests only — homogeneity-gated), resolves it through real
 * priority passes, and asserts the native facts: Bears on P1's battlefield
 * plus one life gained by each Soul Warden controller (simultaneous triggers,
 * no fabricated generation order asserted).</p>
 */
class XmageFullGameTrigExecutionTest {

    private static final String FOREST_MANA_LABEL = "Forest \u2014 {T}: Add {G}.";

    @Test
    void trig3CastsBearsAndTriggersSoulWardens() {
        executeTrig("WS05-MP-TRIG-3", "exec-trig-3", 3);
    }

    @Test
    void trig5CastsBearsAndTriggersSoulWardens() {
        executeTrig("WS05-MP-TRIG-5", "exec-trig-5", 5);
    }

    static void executeTrig(String fixtureId, String gameTag, int playerCount) {
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
        Player p1 = seats.get("P1");
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict constructed = restoration.compare(
                XmageNativeStateRestoration.readback(
                        session.restorationGame(), seats), seats);
        assertTrue(constructed.match(),
                "construction must match before execution: " + constructed.mismatches());

        JsonObject castLegal = session.legalActionsPayload();
        assertEquals("priority", castLegal.get("decision_class").getAsString());
        XmageFullGameTaxExecutionTest.submit(session, gameTag + "-cast",
                XmageFullGameTaxExecutionTest.castOffer(castLegal, "Grizzly Bears"));

        // Engine-owned {1}{G} payment: two restored Forests, homogeneity-gated.
        for (int round = 0; round < 6; round++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal during payment");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            if ("priority".equals(pending.get("decision_class").getAsString())) {
                break;
            }
            assertEquals("mana_payment", pending.get("decision_class").getAsString(),
                    "only engine-driven mana payment may follow the cast, round " + round);
            JsonObject legal = session.legalActionsPayload();
            List<JsonObject> mana = new ArrayList<>();
            List<JsonObject> pool = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                JsonObject metadata = action.getAsJsonObject("metadata");
                String optionType = metadata.has("option_type")
                        && !metadata.get("option_type").isJsonNull()
                        ? metadata.get("option_type").getAsString() : "";
                if ("mana_ability".equals(optionType)) {
                    mana.add(action);
                } else if ("mana_pool".equals(optionType)) {
                    pool.add(action);
                }
            }
            if (!mana.isEmpty()) {
                String label = null;
                for (JsonObject action : mana) {
                    String candidate = action.getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (label == null) {
                        label = candidate;
                    } else {
                        assertEquals(label, candidate, "heterogeneous mana fails closed");
                    }
                }
                assertEquals(FOREST_MANA_LABEL, label, "only Forest mana expected");
                mana.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                XmageFullGameTaxExecutionTest.submit(
                        session, gameTag + "-pay-" + round, mana.get(0));
            } else if (pool.size() == 1) {
                XmageFullGameTaxExecutionTest.submit(
                        session, gameTag + "-spend-" + round, pool.get(0));
            } else {
                fail("payment round " + round + " offers neither mana abilities ("
                        + mana.size() + ") nor exactly one pool spend (" + pool.size() + ")");
            }
        }

        boolean bearsOnStack = false;
        for (mage.game.stack.StackObject stackObject
                : session.restorationGame().getStack()) {
            if (stackObject.getName().equals("Grizzly Bears")) {
                bearsOnStack = true;
            }
        }
        assertTrue(bearsOnStack, "restored Bears must be cast onto the stack");

        // Resolve through real priority passes: Bears ETB, then the three
        // simultaneous Soul Warden triggers resolve (each controller +1 life).
        boolean bearsResolved = false;
        for (int step = 0; step < 60; step++) {
            for (Permanent permanent : session.restorationGame()
                    .getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals("Grizzly Bears")
                        && p1.getId().equals(permanent.getControllerId())) {
                    bearsResolved = true;
                }
            }
            if (bearsResolved
                    && session.restorationGame().getStack().isEmpty()) {
                break;
            }
            bearsResolved = false;
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before trigger resolution");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            if (!"priority".equals(pending.get("decision_class").getAsString())) {
                fail("unexpected decision class during resolution: "
                        + pending.get("decision_class").getAsString());
            }
            XmageFullGameTaxExecutionTest.submit(session, gameTag + "-resolve-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
            if (step == 59) {
                fail("resolution bound breached");
            }
        }
        assertTrue(bearsResolved, "Bears must resolve onto P1's battlefield");
        assertTrue(session.restorationGame().getStack().isEmpty(),
                "stack must empty after trigger resolution");
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            assertEquals(41, entry.getValue().getLife(),
                    entry.getKey() + " gains 1 from its Soul Warden trigger");
        }
    }
}
