package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.combat.CombatGroup;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PB-03 exact runtime closure for the two frozen pilot combat obligations.
 *
 * <p>The canonical records provide the objects and principals. The harness
 * reconstructs only an earlier engine-native precombat checkpoint, then reaches
 * the declared combat frame through normal priority and submits only exact
 * provider-offered legal actions. No combat outcome is injected.</p>
 */
class XmagePb03RuntimeGapClosureTest {

    private static final long SEED = 424242L;

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats) {
    }

    @Test
    void pilotDeclareAttackerUsesExactFrozenRecordAndProviderOffer() {
        Arrived arrived = arriveFromFrozenPrecombat(
                "PILOT_DECLARE_ATTACKER", "pb03-pilot-attacker");
        UUID attacker = arrived.restoration().injectedObjectId("obj:p1-bears");
        UUID defender = arrived.seats().get("P2").getId();

        seekDecision(arrived, "declare_attacker", "pb03-pilot-attacker");
        JsonObject offer = exactAttackOffer(
                arrived.session().legalActionsPayload(), attacker, defender);
        XmagePb03Tier1RowsTest.submit(
                arrived.session(), "pb03-pilot-attacker-submit", offer);

        CombatGroup group = arrived.session().restorationGame().getCombat().findGroup(attacker);
        assertNotNull(group, "declared attacker must enter an engine combat group");
        assertEquals(defender, group.getDefenderId(), "attacker must attack P2");
        assertTrue(
                arrived.session().restorationGame().getPermanent(attacker).isTapped(),
                "Grizzly Bears must be tapped by the genuine attack declaration");
    }

    @Test
    void pilotDeclareBlockerUsesExactFrozenRecordAndProviderOffer() {
        Arrived arrived = arriveFromFrozenPrecombat(
                "PILOT_DECLARE_BLOCKER", "pb03-pilot-blocker");
        UUID attacker = arrived.restoration().injectedObjectId("obj:p1-bears");
        UUID blocker = arrived.restoration().injectedObjectId("obj:p2-bears");
        UUID defender = arrived.seats().get("P2").getId();

        seekDecision(arrived, "declare_attacker", "pb03-pilot-blocker-attack");
        XmagePb03Tier1RowsTest.submit(
                arrived.session(),
                "pb03-pilot-blocker-attack-submit",
                exactAttackOffer(arrived.session().legalActionsPayload(), attacker, defender));

        seekDecision(arrived, "declare_blocker", "pb03-pilot-blocker-block");
        JsonObject legal = arrived.session().legalActionsPayload();
        assertEquals(
                arrived.seats().get("P2").getId().toString(),
                legal.get("actor_id").getAsString(),
                "only the defending principal P2 may make the obligated block");
        XmagePb03Tier1RowsTest.submit(
                arrived.session(),
                "pb03-pilot-blocker-submit",
                exactBlockOffer(legal, blocker, attacker));

        CombatGroup group = arrived.session().restorationGame().getCombat().findGroup(attacker);
        assertNotNull(group, "attacker combat group must remain live");
        assertEquals(defender, group.getDefenderId(), "group must be defended by P2");
        assertTrue(group.getBlockers().contains(blocker), "P2 Bears must block the exact attacker");
    }

    private static Arrived arriveFromFrozenPrecombat(String fixtureId, String tag) {
        JsonObject record = XmageNativeStateRestorationTest.frozenRecord(fixtureId);
        JsonObject causalPrecondition = record.deepCopy();
        causalPrecondition.getAsJsonObject("temporal_state")
                .addProperty("priority_player", "P1");
        XmageNativeStateRestoration.Plan plan =
                XmagePb03Tier2CmdZoneTest.preconditionPlanForTest(
                        causalPrecondition, tag, List.of(), Map.of(), Map.of());
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, SEED, importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoration.compare(
                        XmageNativeStateRestoration.readback(
                                session.restorationGame(), seats),
                        seats);
        assertTrue(verdict.match(), fixtureId + " precondition mismatch: " + verdict.mismatches());
        return new Arrived(session, restoration, seats);
    }

    private static void seekDecision(Arrived arrived, String wanted, String tag) {
        for (int step = 0; step < 120; step++) {
            String pending = XmagePb03Tier1RowsTest.pendingClass(arrived.session());
            if (wanted.equals(pending)) {
                return;
            }
            if (pending == null) {
                fail(tag + ": engine terminated before " + wanted);
            }
            if ("priority".equals(pending)) {
                XmagePb03Tier1RowsTest.passPriority(
                        arrived.session(), tag + "-pass-" + step);
                continue;
            }
            if ("declare_attacker".equals(pending)) {
                XmagePb03Tier1RowsTest.submit(
                        arrived.session(),
                        tag + "-hold-" + step,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                arrived.session().legalActionsPayload(),
                                "declare_attackers",
                                "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(pending)) {
                XmagePb03Tier1RowsTest.submitProposal(
                        arrived.session(),
                        tag + "-noblock-" + step,
                        XmagePb03Tier1RowsTest.emptyBlockProposal(
                                tag + "-noblock-" + step,
                                arrived.session().legalActionsPayload()));
                continue;
            }
            fail(tag + ": unexpected decision class " + pending + " before " + wanted);
        }
        fail(tag + ": decision bound exceeded before " + wanted);
    }

    private static JsonObject exactAttackOffer(
            JsonObject legal, UUID attacker, UUID defender) {
        assertEquals(
                attacker.toString(),
                decisionCreatureId(legal),
                "the declare-attacker frame must be bound to the exact frozen attacker");
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            JsonObject nativeMeta = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata")
                    : new JsonObject();
            String defenderId = string(nativeMeta, "defender_id");
            if (!"declare_attacker".equals(optionType)
                    || !defender.toString().equals(defenderId)
                    || hasConflictingIdentity(nativeMeta, attacker)) {
                continue;
            }
            if (match != null) {
                fail("multiple exact attacker offers for " + attacker + " -> " + defender);
            }
            match = action;
        }
        assertNotNull(match, "exact attacker/defender offer must be engine-authored");
        return match;
    }

    private static String decisionCreatureId(JsonObject legal) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (!("declare_attacker".equals(optionType)
                    || "hold_attacker".equals(optionType))) {
                continue;
            }
            JsonObject nativeMeta = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata")
                    : new JsonObject();
            if (nativeMeta.has("object_id") && !nativeMeta.get("object_id").isJsonNull()) {
                return nativeMeta.get("object_id").getAsString();
            }
        }
        return null;
    }

    private static boolean hasConflictingIdentity(JsonObject nativeMeta, UUID expected) {
        for (Map.Entry<String, JsonElement> entry : nativeMeta.entrySet()) {
            if (!entry.getValue().isJsonPrimitive()) {
                continue;
            }
            String key = entry.getKey();
            String value = entry.getValue().getAsString();
            if (("object_id".equals(key)
                    || "source_object_id".equals(key)
                    || "attacker_id".equals(key))
                    && !value.isEmpty()
                    && !expected.toString().equals(value)) {
                return true;
            }
        }
        return false;
    }

    private static JsonObject exactBlockOffer(
            JsonObject legal, UUID blocker, UUID attacker) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            JsonObject nativeMeta = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata")
                    : new JsonObject();
            if (!"declare_blocker".equals(optionType)) {
                continue;
            }
            boolean hitsBlocker = false;
            boolean hitsAttacker = false;
            for (Map.Entry<String, JsonElement> entry : nativeMeta.entrySet()) {
                if (!entry.getValue().isJsonPrimitive()) {
                    continue;
                }
                String value = entry.getValue().getAsString();
                if (blocker.toString().equals(value)) {
                    hitsBlocker = true;
                }
                if (attacker.toString().equals(value)) {
                    hitsAttacker = true;
                }
            }
            if (hitsBlocker && hitsAttacker) {
                if (match != null) {
                    fail("multiple exact blocker offers for " + blocker + " -> " + attacker);
                }
                match = action;
            }
        }
        assertNotNull(match, "exact blocker/attacker offer must be engine-authored");
        return match;
    }

    private static String string(JsonObject object, String key) {
        return object.has(key) && !object.get(key).isJsonNull()
                ? object.get(key).getAsString() : "";
    }
}
