package org.commanderlab.xmage;

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
 * DR-CLOSURE-01 Phase 3: exact micro-mechanism execution for the two
 * restorable UNKNOWN cells.
 *
 * <p>{@code MICRO_LAYERS} (4P, seed 424242): Humility + Glorious Anthem layer
 * authority over restored Grizzly Bears — abilities removed engine-wide, P1's
 * Bears 2/2 (Anthem), all other Bears 1/1. Promoted to DIRECT.</p>
 *
 * <p>{@code MICRO_TARGETS} (4P, seed 424242): Lightning Bolt cast from the
 * restored hand through engine legality, engine-owned {R} payment, the
 * engine-offered legal target set (exactly 3 creatures + 4 players, no
 * filtering, no fabrication), P2 selected by exact engine-issued player
 * identity, resolution dealing 3 to P2. Promoted to DIRECT.</p>
 */
class XmageFullGameMicroExecutionTest {

    @Test
    void microLayersAppliesHumilityThenAnthem() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("MICRO_LAYERS"),
                        "exec-layers", 424242L);
        assertEquals(4, plan.playerCount());
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "exec-layers");
        XmageFullGameSession session = new XmageFullGameSession(
                "MICRO_LAYERS", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict constructed = restoration.compare(
                XmageNativeStateRestoration.readback(
                        session.restorationGame(), seats), seats);
        assertTrue(constructed.match(),
                "construction must match before execution: " + constructed.mismatches());

        int bears = 0;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (!permanent.getName().equals("Grizzly Bears")) {
                continue;
            }
            bears++;
            String ownerPid =
                    XmageNativeStateRestorationTest.pidOf(seats, permanent.getOwnerId().toString());
            int expected = ownerPid.equals("P1") ? 2 : 1;
            assertEquals(expected, permanent.getPower().getValue(),
                    "layer 7b/7c power for " + ownerPid);
            assertEquals(expected, permanent.getToughness().getValue(),
                    "layer 7b/7c toughness for " + ownerPid);
            assertTrue(permanent.getAbilities(session.restorationGame()).isEmpty(),
                    "Humility layer 6 removes abilities for " + ownerPid);
        }
        assertEquals(4, bears, "four restored Bears under layer authority");
    }

    @Test
    void microTargetsOffersLegalSetAndStrikesP2() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("MICRO_TARGETS"),
                        "exec-targets", 424242L);
        assertEquals(4, plan.playerCount());
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "exec-targets");
        XmageFullGameSession session = new XmageFullGameSession(
                "MICRO_TARGETS", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Player p1 = seats.get("P1");
        Player p2 = seats.get("P2");
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict constructed = restoration.compare(
                XmageNativeStateRestoration.readback(
                        session.restorationGame(), seats), seats);
        assertTrue(constructed.match(),
                "construction must match before execution: " + constructed.mismatches());

        JsonObject castLegal = session.legalActionsPayload();
        assertEquals("priority", castLegal.get("decision_class").getAsString());
        JsonObject bolt = null;
        for (JsonElement element : castLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject engine = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (engine.has("ability_type")
                    && "spell".equals(engine.get("ability_type").getAsString())
                    && engine.has("source_name")
                    && "Lightning Bolt".equals(engine.get("source_name").getAsString())) {
                bolt = action;
            }
        }
        assertTrue(bolt != null, "engine must offer the restored Bolt through its legality");
        XmageFullGameTaxExecutionTest.submit(session, "exec-targets-cast", bolt);

        // Per CR 601.2 errata order the engine requests targets before
        // payment; the harness follows the engine's decision order, never its
        // own script order.
        JsonObject targetLegal = session.legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        List<JsonObject> options = new ArrayList<>();
        for (JsonElement element : targetLegal.getAsJsonArray("actions")) {
            options.add(element.getAsJsonObject());
        }
        assertEquals(7, options.size(),
                "exactly 3 creatures + 4 players: no filtering, no fabrication");
        JsonObject p2Option = null;
        for (JsonObject option : options) {
            String objectId = option.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString();
            if (objectId.equals(p2.getId().toString())) {
                p2Option = option;
            }
        }
        assertTrue(p2Option != null, "P2 must be engine-offered by exact identity");
        XmageFullGameTaxExecutionTest.submit(session, "exec-targets-p2", p2Option);

        // Payment follows target selection (engine order): single {R}.
        JsonObject afterTarget =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        if ("mana_payment".equals(afterTarget.get("decision_class").getAsString())) {
            XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                    session, "exec-targets", "Mountain \u2014 {T}: Add {R}.");
        }
        int tappedMountains = 0;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Mountain")
                    && p1.getId().equals(permanent.getControllerId())
                    && permanent.isTapped()) {
                tappedMountains++;
            }
        }
        assertEquals(1, tappedMountains, "{R} must come from the restored Mountain");

        boolean struck = false;
        for (int step = 0; step < 40; step++) {
            if (p2.getLife() == 37) {
                struck = true;
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before Bolt resolution");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            assertEquals("priority", pending.get("decision_class").getAsString(),
                    "only priority passes during resolution, step " + step);
            XmageFullGameTaxExecutionTest.submit(session, "exec-targets-resolve-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        assertTrue(struck, "terminal postcondition: Bolt deals 3 to P2 (40 → 37)");
        assertEquals(40, p1.getLife());
        assertEquals(40, seats.get("P3").getLife());
        assertEquals(40, seats.get("P4").getLife());
    }
}
