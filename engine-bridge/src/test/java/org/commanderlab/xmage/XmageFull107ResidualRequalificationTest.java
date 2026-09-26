package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.game.CommanderFreeForAll;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Final residual FULL107 requalification.
 *
 * <p>These are exact frozen-fixture executions, not mechanism-level credit.
 * Every promoted cell is bound to its frozen record, seed 424242, native
 * construction/readback and frozen requested_state_digest. Residual cells not
 * covered here remain UNKNOWN/NOT_RUN_BLOCKED.</p>
 */
class XmageFull107ResidualRequalificationTest {

    private static final long SEED = 424242L;

    @Test
    void exactSplitCommanderDamageRemainsPerCommanderAndDigestMatches() {
        Arrived arrived = arrivePrecombat("WS05-CMD-DMG-SPLIT", "full107-dmg-split");
        Player p2 = arrived.seats().get("P2");

        assertFalse(p2.hasLost(),
                "11 + 10 from distinct commanders must not aggregate to the 21-damage loss");
        assertEquals(11, commanderDamage(arrived, "P1",
                "Rograkh, Son of Rohgahh", "P2"));
        assertEquals(10, commanderDamage(arrived, "P1",
                "Kediss, Emberclaw Familiar", "P2"));

        XmageNativeStateRestoration.revalidate(arrived.game());
        assertFalse(p2.hasLost(), "repeated native SBA checks must remain idempotent");
        verifyFrozenDigestWithCommanderDamage(arrived, Set.of(
                "Rograkh, Son of Rohgahh",
                "Kediss, Emberclaw Familiar",
                "Grizzly Bears"));
    }

    @Test
    void exactPartnerCommanderDamageRemainsIndependentAndDigestMatches() {
        Arrived arrived = arrivePrecombat("WS05-CMD-PARTNER-DMG", "full107-partner-dmg");
        Player p2 = arrived.seats().get("P2");

        assertFalse(p2.hasLost(),
                "12 + 9 from Partner commanders must remain distinct Commander damage");
        assertEquals(12, commanderDamage(arrived, "P1",
                "Rograkh, Son of Rohgahh", "P2"));
        assertEquals(9, commanderDamage(arrived, "P1",
                "Kediss, Emberclaw Familiar", "P2"));
        verifyFrozenDigestWithCommanderDamage(arrived, Set.of(
                "Rograkh, Son of Rohgahh",
                "Kediss, Emberclaw Familiar",
                "Grizzly Bears"));
    }

    @Test
    void exactThreePlayerStartingPlayerDrawOccursAndDigestMatches() {
        JsonObject requested = XmageNativeStateRestorationTest.frozenRecord("WS05-CMD-START-3");
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        requested, "full107-start3", SEED);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(
                        importer, plan, "full107-start3");
        XmageFullGameSession session = new XmageFullGameSession(
                "WS05-CMD-START-3", handles, 0, 40, SEED, importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        int p1HandBefore = seats.get("P1").getHand().size();

        XmageTemporalProgressionDriver.ProgressionResult result =
                XmageTemporalProgressionDriver.driveToPlanTarget(
                        session, seats, plan, arrivalSource("full107-start3"), 80);
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());

        assertEquals("P1", result.observed().get("active_player").getAsString());
        assertEquals("DRAW", result.observed().get("step").getAsString());
        assertEquals(p1HandBefore + 1, seats.get("P1").getHand().size(),
                "3P starting player must actually take the first-turn draw");
        assertEquals(p1HandBefore, seats.get("P2").getHand().size(),
                "P2 has not reached its draw step at the frozen checkpoint");

        Arrived arrived = new Arrived(
                "WS05-CMD-START-3", requested, plan, session, restoration, seats);
        verifyFrozenDigestWithoutCommanderDamage(arrived, Set.of(
                "Rograkh, Son of Rohgahh", "Grizzly Bears"));
    }

    private static Arrived arrivePrecombat(String fixtureId, String tag) {
        JsonObject requested = XmageNativeStateRestorationTest.frozenRecord(fixtureId);
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(requested, tag, SEED);
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
        return new Arrived(fixtureId, requested, plan, session, restoration, seats);
    }

    private static int commanderDamage(
            Arrived arrived,
            String ownerPid,
            String commanderName,
            String damagedPid
    ) {
        Player owner = arrived.seats().get(ownerPid);
        Player damaged = arrived.seats().get(damagedPid);
        List<UUID> matches = new ArrayList<>();
        for (UUID id : arrived.game().getCommandersIds(
                owner, CommanderCardType.ANY, false)) {
            Card card = arrived.game().getCard(id);
            if (card != null && commanderName.equals(card.getName())) {
                matches.add(id);
            }
        }
        assertEquals(1, matches.size(),
                "exact native Commander binding for " + ownerPid + "/" + commanderName);
        CommanderInfoWatcher watcher = arrived.game().getState().getWatcher(
                CommanderInfoWatcher.class, matches.get(0));
        assertNotNull(watcher, "native CommanderInfoWatcher must exist");
        return watcher.getDamageToPlayer().getOrDefault(damaged.getId(), 0);
    }

    private static void verifyFrozenDigestWithCommanderDamage(
            Arrived arrived,
            Set<String> allowedCards
    ) {
        JsonObject observed = XmageNativeStateRestoration.readback(
                arrived.game(), arrived.seats());
        XmageNativeStateRestoration.CompareVerdict fieldCheck =
                arrived.restoration().compare(observed, arrived.seats());
        assertTrue(fieldCheck.match(),
                "native field match precedes digest: " + fieldCheck.mismatches());

        JsonObject projection = baseProjection(arrived, observed, allowedCards);
        projection.add("commander_state",
                commanderStateProjectionWithDamage(arrived));
        finishProjectionAndAssertDigest(arrived, observed, projection);
    }

    private static void verifyFrozenDigestWithoutCommanderDamage(
            Arrived arrived,
            Set<String> allowedCards
    ) {
        JsonObject observed = XmageNativeStateRestoration.readback(
                arrived.game(), arrived.seats());
        XmageNativeStateRestoration.CompareVerdict fieldCheck =
                arrived.restoration().compare(observed, arrived.seats());
        assertTrue(fieldCheck.match(),
                "native field match precedes digest: " + fieldCheck.mismatches());

        JsonObject projection = baseProjection(arrived, observed, allowedCards);
        projection.add("commander_state",
                XmageDigestCreditTest.commanderStateProjection(
                        arrived.requested(), observed, arrived.plan()));
        finishProjectionAndAssertDigest(arrived, observed, projection);
    }

    private static JsonObject baseProjection(
            Arrived arrived,
            JsonObject observed,
            Set<String> allowedCards
    ) {
        JsonObject requested = arrived.requested();
        JsonObject projection = new JsonObject();
        projection.addProperty("execution_entry_mode", "NATIVE_STATE_LOAD");
        projection.add("players", XmageDigestCreditTest.playersProjection(
                arrived.plan().players(), observed, 40, requested));
        projection.add("semantic_objects",
                XmageDigestCreditTest.transferBattlefieldIds(requested, observed));

        JsonObject temporal = requested.getAsJsonObject("temporal_state").deepCopy();
        assertEquals(temporal.get("turn_number").getAsInt(),
                observed.get("turn_number").getAsInt());
        assertEquals(nativePhase(temporal.get("phase").getAsString()),
                observed.get("phase").getAsString());
        assertEquals(nativeStep(temporal.get("step").getAsString()),
                observed.get("step").getAsString());
        assertEquals(temporal.get("active_player").getAsString(),
                observed.get("active_player").getAsString());
        assertEquals(temporal.get("priority_player").getAsString(),
                observed.get("priority_player").getAsString());
        assertFalse(observed.get("has_extra_turn").getAsBoolean());
        projection.add("temporal_state", temporal);

        projection.add("knowledge_state", XmageDigestCreditTest.knowledgeProjection(
                requested, new ArrayList<>(arrived.seats().keySet()),
                allowedCards, Set.of()));
        assertEquals(SEED, observed.get("rules_seed").getAsLong());
        assertTrue(observed.get("rules_seed_explicit").getAsBoolean());
        projection.add("rules_randomness", requested.get("rules_randomness"));
        assertTrue(requested.getAsJsonArray("stack_state").isEmpty());
        assertTrue(arrived.game().getStack().isEmpty());
        projection.add("stack_state", new JsonArray());
        projection.add("setup_validation", requested.get("setup_validation"));
        return projection;
    }

    private static void finishProjectionAndAssertDigest(
            Arrived arrived,
            JsonObject observed,
            JsonObject projection
    ) {
        XmageDigestCreditTest.assertProjectionKeys(projection, arrived.requested());
        assertEquals(arrived.requested().get("requested_state_digest").getAsString(),
                XmageNativeStateRestoration.constructedDigest(projection),
                "constructed digest must equal frozen requested_state_digest for "
                        + arrived.fixtureId());
    }

    private static JsonObject commanderStateProjectionWithDamage(Arrived arrived) {
        JsonObject requested =
                arrived.requested().getAsJsonObject("commander_state");
        JsonObject state = requested.deepCopy();

        Map<String, XmageNativeStateRestoration.RequestedCommander> planned =
                new HashMap<>();
        for (XmageNativeStateRestoration.RequestedCommander commander
                : arrived.plan().commanders()) {
            planned.put(commander.commanderId(), commander);
        }

        for (JsonElement element : requested.getAsJsonArray("commanders")) {
            JsonObject want = element.getAsJsonObject();
            XmageNativeStateRestoration.RequestedCommander commander =
                    planned.get(want.get("commander_id").getAsString());
            assertNotNull(commander, "commander must be present in native plan");
            assertEquals(want.get("card_identity").getAsString(),
                    commander.cardIdentity());
            assertEquals(want.get("owner").getAsString(), commander.owner());
            assertEquals(want.get("prior_command_zone_cast_count").getAsInt(),
                    commander.priorCasts());
        }

        for (JsonElement element : requested.getAsJsonArray("commander_damage_matrix")) {
            JsonObject edge = element.getAsJsonObject();
            String commanderId = edge.get("source_commander_id").getAsString();
            XmageNativeStateRestoration.RequestedCommander commander =
                    planned.get(commanderId);
            assertNotNull(commander, "damage edge commander must bind");
            assertEquals(edge.get("combat_damage").getAsInt(),
                    commanderDamage(arrived, commander.owner(), commander.cardIdentity(),
                            edge.get("damaged_player").getAsString()));
        }
        return state;
    }

    private static XmageTemporalProgressionDriver.DecisionSource arrivalSource(String tag) {
        return (pending, legal, index) -> {
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                return XmageCausalStackReconstruction.proposal(
                        tag + "-keep-" + index, actor,
                        exactOption(legal, "mulligan", "keep"));
            }
            if ("choose_object".equals(decisionClass)
                    && pending.has("prompt")
                    && pending.get("prompt").getAsString().contains("starting player")) {
                JsonObject self = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if (action.get("action_id").getAsString().endsWith(":" + actor)) {
                        assertTrue(self == null, "starting-player self option ambiguous");
                        self = action;
                    }
                }
                assertNotNull(self, "starting-player self option missing");
                return XmageCausalStackReconstruction.proposal(
                        tag + "-start-" + index, actor, self);
            }
            if ("priority".equals(decisionClass)) {
                return XmageCausalStackReconstruction.proposal(
                        tag + "-pass-" + index, actor,
                        exactAction(legal, "pass_priority"));
            }
            return null;
        };
    }

    private static JsonObject exactAction(JsonObject legal, String actionType) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (actionType.equals(action.get("action_type").getAsString())) {
                assertTrue(match == null, actionType + " offer ambiguous");
                match = action;
            }
        }
        assertNotNull(match, actionType + " offer missing");
        return match;
    }

    private static JsonObject exactOption(
            JsonObject legal, String actionType, String optionType) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (optionType.equals(metadata.get("option_type").getAsString())) {
                assertTrue(match == null,
                        actionType + "/" + optionType + " offer ambiguous");
                match = action;
            }
        }
        assertNotNull(match, actionType + "/" + optionType + " offer missing");
        return match;
    }

    private static String nativePhase(String frozen) {
        return switch (frozen) {
            case "beginning" -> "BEGINNING";
            case "precombat_main" -> "PRECOMBAT_MAIN";
            case "combat" -> "COMBAT";
            case "postcombat_main" -> "POSTCOMBAT_MAIN";
            case "ending" -> "ENDING";
            default -> throw new AssertionError("unknown frozen phase " + frozen);
        };
    }

    private static String nativeStep(String frozen) {
        return switch (frozen) {
            case "upkeep" -> "UPKEEP";
            case "draw" -> "DRAW";
            case "main" -> "PRECOMBAT_MAIN";
            case "declare_attackers" -> "DECLARE_ATTACKERS";
            case "declare_blockers" -> "DECLARE_BLOCKERS";
            case "combat_damage" -> "COMBAT_DAMAGE";
            default -> throw new AssertionError("unknown frozen step " + frozen);
        };
    }

    private record Arrived(
            String fixtureId,
            JsonObject requested,
            XmageNativeStateRestoration.Plan plan,
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
        CommanderFreeForAll game() {
            return session.restorationGame();
        }
    }
}
