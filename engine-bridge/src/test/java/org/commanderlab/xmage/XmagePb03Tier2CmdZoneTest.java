package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PB-03 Wave 2a: genuine-causal commander zone-choice rows (Muse XHIGH).
 *
 * <p>Each method loads its own frozen record, constructs the pre-cause state
 * (record objects minus the stack causal step, plus documented casting-fuel
 * lands), performs the record's own causal spell genuinely (real cast, real
 * targets, real payment), answers the row's decision_script selection among
 * engine-offered options only, and asserts the required events and terminal
 * postconditions as game facts.</p>
 *
 * <p>Documented deviations from the frozen record (and why they preserve the
 * obligation): (1) the stack causal step is performed, not placed, because
 * the seam fail-closes on stack spells and only genuine casting reproduces
 * them; (2) casting-fuel lands are harness scaffolding (like the
 * materialization vehicle), never fixture content and never asserted upon;
 * (3) no digest equality is claimed — obligation facts are.</p>
 */
class XmagePb03Tier2CmdZoneTest {

    private static final long SEED = 424242L;

    /** Casting fuel: harness scaffolding, never fixture content. */
    record FuelLand(String semanticId, String cardName, String owner) {
    }

    /**
     * Precondition plan for one row: record players, commanders and
     * non-stack objects plus fuel lands, arriving at turn-1 precombat main
     * (the cast point for the genuine causes, which precede any later
     * record checkpoint).
     */
    static XmageNativeStateRestoration.Plan preconditionPlan(
            JsonObject record, String planId, List<FuelLand> fuel) {
        return preconditionPlanForTest(record, planId, fuel, Map.of(), Map.of());
    }

    /**
     * Precondition plan with object relocations (semantic id to zone name) and
     * controller overrides (semantic id to controller pid) for the pre-cause
     * state. Used when the genuine cause needs a record object in a castable
     * zone or with pre-effect control. Relocations are documented per row and
     * never asserted upon.
     */
    static XmageNativeStateRestoration.Plan preconditionPlanForTest(
            JsonObject record,
            String planId,
            List<FuelLand> fuel,
            Map<String, String> relocations) {
        return preconditionPlanForTest(record, planId, fuel, relocations, Map.of());
    }

    static XmageNativeStateRestoration.Plan preconditionPlanForTest(
            JsonObject record,
            String planId,
            List<FuelLand> fuel,
            Map<String, String> relocations,
            Map<String, String> controllerOverrides) {
        JsonObject temporal = record.getAsJsonObject("temporal_state");
        assertEquals(1, temporal.get("turn_number").getAsInt(), "turn 1");
        assertEquals("P1", temporal.get("active_player").getAsString(), "P1 active");
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        for (JsonElement element : record.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            players.add(new XmageNativeStateRestoration.RequestedPlayer(
                    player.get("player_id").getAsString(),
                    player.get("seat").getAsInt(),
                    player.get("life").getAsInt()));
        }
        JsonObject commanderState = record.getAsJsonObject("commander_state");
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        Map<String, Integer> commanderIndex = new java.util.HashMap<>();
        for (JsonElement element : commanderState.getAsJsonArray("commanders")) {
            JsonObject commander = element.getAsJsonObject();
            commanderIndex.put(commander.get("commander_id").getAsString(), commanders.size());
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    commander.get("commander_id").getAsString(),
                    commander.get("card_identity").getAsString(),
                    commander.get("owner").getAsString(),
                    commander.get("prior_command_zone_cast_count").getAsInt()));
        }
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // The record's stack causal steps are performed, not placed: their
        // source cards enter the caster's hand so the genuine cast can begin.
        java.util.Set<String> causalSources = new java.util.HashSet<>();
        for (JsonElement frame : record.getAsJsonArray("stack_state")) {
            causalSources.add(frame.getAsJsonObject()
                    .get("source_semantic_id").getAsString());
        }
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            String zone = object.get("zone").getAsString();
            String semanticId = object.get("semantic_id").getAsString();
            if ("stack".equals(zone) && !causalSources.contains(semanticId)) {
                throw new IllegalArgumentException(
                        "non-causal stack object has no genuine path: " + semanticId);
            }
            if ("command".equals(zone)) {
                continue;
            }
            String commanderId = object.has("commander_id") && !object.get("commander_id").isJsonNull()
                    ? object.get("commander_id").getAsString() : null;
            if (commanderId != null && "battlefield".equals(zone)
                    && !relocations.containsKey(semanticId)) {
                // F-38: the genuine commander on the battlefield, never a setup copy.
                int index = commanderIndex.get(commanderId);
                XmageNativeStateRestoration.RequestedCommander requested = commanders.get(index);
                commanders.set(index, new XmageNativeStateRestoration.RequestedCommander(
                        requested.commanderId(), requested.cardIdentity(), requested.owner(),
                        requested.priorCasts(), mage.constants.Zone.BATTLEFIELD, semanticId));
                continue;
            }
            mage.constants.Zone placed;
            if ("stack".equals(zone)) {
                placed = mage.constants.Zone.HAND;
            } else if (relocations.containsKey(semanticId)) {
                String relocated = relocations.get(semanticId);
                placed = switch (relocated) {
                    case "battlefield" -> mage.constants.Zone.BATTLEFIELD;
                    case "graveyard" -> mage.constants.Zone.GRAVEYARD;
                    case "exile" -> mage.constants.Zone.EXILED;
                    case "hand" -> mage.constants.Zone.HAND;
                    default -> throw new IllegalArgumentException(
                            "unsupported relocation " + relocated);
                };
            } else {
                placed = switch (zone) {
                    case "battlefield" -> mage.constants.Zone.BATTLEFIELD;
                    case "graveyard" -> mage.constants.Zone.GRAVEYARD;
                    case "exile" -> mage.constants.Zone.EXILED;
                    case "hand" -> mage.constants.Zone.HAND;
                    default -> throw new IllegalArgumentException(
                            "unsupported zone " + zone);
                };
            }
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    semanticId,
                    object.get("card_identity").getAsString(),
                    object.get("owner").getAsString(),
                    controllerOverrides.getOrDefault(
                            semanticId, object.get("controller").getAsString()),
                    placed,
                    false));
        }
        for (FuelLand land : fuel) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    land.semanticId(), land.cardName(), land.owner(), land.owner(),
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        return new XmageNativeStateRestoration.Plan(
                planId,
                players.size(),
                SEED,
                List.copyOf(players),
                List.copyOf(commanders),
                List.of(),
                List.copyOf(objects),
                1,
                mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN,
                "P1",
                temporal.get("priority_player").getAsString());
    }

    @Test
    void cmdZoneGyYesChoosesCommandZone() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-GY-YES",
                "pb03-gy-yes",
                "Doom Blade",
                List.of(new FuelLand("obj:fuel-swamp-a", "Swamp", "P2"),
                        new FuelLand("obj:fuel-swamp-b", "Swamp", "P2")),
                "Swamp — {T}: Add {B}.",
                "graveyard");
    }

    @Test
    void cmdZoneGyNoStaysInGraveyard() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-GY-NO",
                "pb03-gy-no",
                "Doom Blade",
                List.of(new FuelLand("obj:fuel-swamp-a", "Swamp", "P2"),
                        new FuelLand("obj:fuel-swamp-b", "Swamp", "P2")),
                "Swamp — {T}: Add {B}.",
                "graveyard");
    }

    @Test
    void cmdZoneExileYesChoosesCommandZone() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-EXILE-YES",
                "pb03-exile-yes",
                "Swords to Plowshares",
                List.of(new FuelLand("obj:fuel-plains-a", "Plains", "P2")),
                "Plains — {T}: Add {W}.",
                "exile");
    }

    @Test
    void cmdZoneExileNoStaysInExile() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-EXILE-NO",
                "pb03-exile-no",
                "Swords to Plowshares",
                List.of(new FuelLand("obj:fuel-plains-a", "Plains", "P2")),
                "Plains — {T}: Add {W}.",
                "exile");
    }

    @Test
    void cmdZoneHandYesChoosesCommandZone() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-HAND-YES",
                "pb03-hand-yes",
                "Unsummon",
                List.of(new FuelLand("obj:fuel-island-a", "Island", "P2")),
                "Island — {T}: Add {U}.",
                "hand");
    }

    @Test
    void cmdZoneHandNoStaysInHand() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-HAND-NO",
                "pb03-hand-no",
                "Unsummon",
                List.of(new FuelLand("obj:fuel-island-a", "Island", "P2")),
                "Island — {T}: Add {U}.",
                "hand");
    }

    @Test
    void cmdZoneLibYesChoosesCommandZone() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-LIB-YES",
                "pb03-lib-yes",
                "Bant Charm",
                List.of(new FuelLand("obj:fuel-forest-a", "Forest", "P2"),
                        new FuelLand("obj:fuel-plains-a", "Plains", "P2"),
                        new FuelLand("obj:fuel-island-a", "Island", "P2")),
                null,
                "library");
    }

    @Test
    void cmdZoneLibNoStaysInLibrary() {
        executeCommanderZoneChoice(
                "WS05-CMD-ZONE-LIB-NO",
                "pb03-lib-no",
                "Bant Charm",
                List.of(new FuelLand("obj:fuel-forest-a", "Forest", "P2"),
                        new FuelLand("obj:fuel-plains-a", "Plains", "P2"),
                        new FuelLand("obj:fuel-island-a", "Island", "P2")),
                null,
                "library");
    }

    /**
     * Executes the row's commander zone-choice obligation on the genuine
     * commander (F-38): the record's battlefield commander is the engine's own
     * commander, the record's cause is cast for real, the engine's zone choice
     * is answered with the decision_script's boolean among the engine-offered
     * options only, and the commander's terminal zone is asserted as a game
     * fact: the command zone for yes, the cause's destination for no.
     */
    static void executeCommanderZoneChoice(
            String fixtureId,
            String tag,
            String causeCard,
            List<FuelLand> fuel,
            String fuelLabel,
            String expectedTerminalZone) {
        JsonObject record = XmageNativeStateRestorationTest.frozenRecord(fixtureId);
        XmageNativeStateRestoration.Plan plan = preconditionPlan(record, tag, fuel);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict precondition =
                restoration.compare(
                        XmageNativeStateRestoration.readback(
                                session.restorationGame(), seats),
                        seats);
        assertTrue(precondition.match(),
                fixtureId + " precondition must match before the genuine cause: "
                        + precondition.mismatches());

        XmagePb03Tier1RowsTest.castSpellAs(session, seats, tag, causeCard, "P2");
        JsonArray stack = record.getAsJsonArray("stack_state");
        assertEquals(1, stack.size(), fixtureId + " has exactly one causal frame");
        JsonObject frame = stack.get(0).getAsJsonObject();
        // Engine casting order (CR 601.2): modes, then targets, then payment.
        // Follow the engine: answer mode, then targets, then pay.
        for (int step = 0; step < 10; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail(tag + ": engine terminal seeking mode decision");
            }
            String decisionClass = payload.getAsJsonObject("decision")
                    .get("decision_class").getAsString();
            if (!"mode".equals(decisionClass)) {
                break;
            }
            JsonArray modes = frame.has("modes") ? frame.getAsJsonArray("modes")
                    : new JsonArray();
            assertEquals(1, modes.size(), fixtureId + " names exactly one mode");
            XmagePb03Tier1RowsTest.submit(session, tag + "-mode-" + step,
                    findRecordModeOffer(session, modes.get(0).getAsString(), fixtureId));
        }
        for (JsonElement target : frame.getAsJsonArray("targets")) {
            UUID targetId = restoration.injectedObjectId(target.getAsString());
            for (int step = 0; step < 10; step++) {
                JsonObject payload = session.pendingDecisionPayload();
                if (payload.get("decision").isJsonNull()) {
                    fail(tag + ": engine terminal seeking target decision");
                }
                String decisionClass = payload.getAsJsonObject("decision")
                        .get("decision_class").getAsString();
                if (!"target".equals(decisionClass)) {
                    break;
                }
                XmagePb03Tier1RowsTest.submit(session, tag + "-target-" + step,
                        XmagePb03Tier1RowsTest.findTargetOffer(
                                session, targetId.toString(), target.getAsString()));
            }
        }
        List<String> fuelOrder = fuel.stream().map(FuelLand::semanticId).toList();
        if (fuelLabel != null) {
            XmagePb03Tier1RowsTest.payFromSemanticSources(
                    session,
                    restoration,
                    tag,
                    fuelOrder,
                    java.util.Set.of(fuelLabel));
        } else {
            XmagePb03Tier1RowsTest.payFromSemanticSources(
                    session,
                    restoration,
                    tag,
                    fuelOrder,
                    java.util.Set.of(
                            "Forest \u2014 {T}: Add {G}.",
                            "Plains \u2014 {T}: Add {W}.",
                            "Island \u2014 {T}: Add {U}."),
                    List.of("GREEN", "WHITE", "BLUE"));
        }
        assertSpellOnStack(session, causeCard, tag);

        UUID commanderId = restoration.injectedObjectId("obj:cmd-zone-test");
        mage.game.GameCommanderImpl game = session.restorationGame();
        assertTrue(game.getCommandersIds(seats.get("P1"), mage.constants.CommanderCardType.ANY, false)
                .contains(commanderId), fixtureId + ": the target is the genuine commander");
        JsonObject selection = record.getAsJsonArray("decision_script").get(0).getAsJsonObject()
                .getAsJsonObject("selection");
        assertEquals("boolean", selection.get("selector_kind").getAsString());
        boolean toCommandZone = selection.get("semantic_value").getAsBoolean();

        // Resolve, answering only priority passes, until the engine asks P1.
        List<String> trace = new ArrayList<>();
        boolean answered = false;
        for (int step = 0; step < 40 && !answered; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail(tag + ": engine terminal before the zone choice; trace=" + trace);
            }
            JsonObject decision = payload.getAsJsonObject("decision");
            String decisionClass = decision.get("decision_class").getAsString();
            trace.add(decisionClass);
            if ("priority".equals(decisionClass)) {
                XmagePb03Tier1RowsTest.passPriority(session, tag + "-pass-" + step);
                continue;
            }
            assertEquals("choose_use", decisionClass, fixtureId + ": trace=" + trace);
            assertEquals(seats.get("P1").getId().toString(),
                    decision.get("actor_id").getAsString(), fixtureId + ": the owner decides");
            List<JsonObject> matches = new ArrayList<>();
            for (JsonElement element : session.legalActionsPayload().getAsJsonArray("actions")) {
                JsonObject metadata = element.getAsJsonObject().getAsJsonObject("metadata");
                JsonObject option = metadata.has("xmage_option_metadata")
                        ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
                if (option.has("value") && option.get("value").getAsBoolean() == toCommandZone) {
                    matches.add(element.getAsJsonObject());
                }
            }
            assertEquals(1, matches.size(), fixtureId + ": exactly one offered answer");
            XmagePb03Tier1RowsTest.submit(session, tag + "-zone-choice", matches.get(0));
            answered = true;
        }
        assertTrue(answered, fixtureId + ": the engine must ask for the zone; trace=" + trace);
        assertEquals(toCommandZone ? mage.constants.Zone.COMMAND : zoneOf(expectedTerminalZone),
                game.getState().getZone(commanderId),
                fixtureId + ": terminal zone of the genuine commander");
        if (!toCommandZone) {
            assertTerminalCommanderZone(session, seats, expectedTerminalZone, fixtureId, causeCard);
        }

        // One choice per zone change: the game proceeds to cleanup without asking again.
        boolean reachedCleanupDiscard = false;
        for (int step = 0; step < 120 && !reachedCleanupDiscard; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject decision = payload.getAsJsonObject("decision");
            String decisionClass = decision.get("decision_class").getAsString();
            trace.add(decisionClass);
            switch (decisionClass) {
                case "priority" -> XmagePb03Tier1RowsTest.passPriority(session, tag + "-after-" + step);
                case "declare_attacker" -> XmagePb03Tier1RowsTest.submit(session, tag + "-hold-" + step,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                session.legalActionsPayload(), "declare_attackers", "hold_attacker"));
                case "declare_blocker" -> XmagePb03Tier1RowsTest.submitProposal(
                        session, tag + "-noblock-" + step, XmagePb03Tier1RowsTest.emptyBlockProposal(
                                tag + "-noblock-" + step, session.legalActionsPayload()));
                case "choose_object" -> {
                    assertTrue(decision.has("prompt") && decision.get("prompt").getAsString().contains("discard"),
                            fixtureId + ": unexpected choose_object " + decision);
                    reachedCleanupDiscard = true;
                }
                default -> fail(fixtureId + ": unexpected " + decisionClass + " after the zone choice; trace="
                        + trace);
            }
        }
        assertTrue(reachedCleanupDiscard, fixtureId + ": the game must reach cleanup; trace=" + trace);
        assertEquals(toCommandZone ? mage.constants.Zone.COMMAND : zoneOf(expectedTerminalZone),
                game.getState().getZone(commanderId), fixtureId + ": the zone is stable");
    }

    static mage.constants.Zone zoneOf(String name) {
        return switch (name) {
            case "graveyard" -> mage.constants.Zone.GRAVEYARD;
            case "exile" -> mage.constants.Zone.EXILED;
            case "hand" -> mage.constants.Zone.HAND;
            case "library" -> mage.constants.Zone.LIBRARY;
            default -> throw new IllegalArgumentException(name);
        };
    }

    static JsonObject findRecordModeOffer(
            XmageFullGameSession session, String modeKey, String tag) {
        JsonObject legal = session.legalActionsPayload();
        assertEquals("mode", legal.get("decision_class").getAsString());
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"choose_mode".equals(action.get("action_type").getAsString())) {
                continue;
            }
            String label = action.getAsJsonObject("metadata").get("label").getAsString();
            // Keyword match tolerant to punctuation/plurals ("owner's" vs
            // "owners"): compare alpha cores.
            String normalized = label.toLowerCase(java.util.Locale.ROOT)
                    .replace("'", "").replaceAll("[^a-z ]", " ");
            boolean hits = true;
            for (String word : modeKey.split("_")) {
                String core = word.toLowerCase(java.util.Locale.ROOT);
                if (core.endsWith("s") && core.length() > 3) {
                    core = core.substring(0, core.length() - 1);
                }
                if (!normalized.contains(core)) {
                    hits = false;
                }
            }
            if (hits) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                tag + ": exactly one engine mode must match " + modeKey);
        return matches.get(0);
    }

    static void assertTerminalCommanderZone(
            XmageFullGameSession session,
            Map<String, Player> seats,
            String expectedTerminalZone,
            String fixtureId,
            String causeCard) {
        mage.game.Game game = session.restorationGame();
        Player p1 = seats.get("P1");
        boolean found = false;
        switch (expectedTerminalZone) {
            case "graveyard" -> {
                for (mage.cards.Card card : p1.getGraveyard().getCards(game)) {
                    if ("Rograkh, Son of Rohgahh".equals(card.getName())) {
                        found = true;
                    }
                }
            }
            case "exile" -> {
                for (mage.cards.Card card : game.getExile()
                        .getCardsOwned(game, p1.getId())) {
                    if ("Rograkh, Son of Rohgahh".equals(card.getName())) {
                        found = true;
                    }
                }
            }
            case "hand" -> {
                for (mage.cards.Card card : p1.getHand().getCards(game)) {
                    if ("Rograkh, Son of Rohgahh".equals(card.getName())) {
                        found = true;
                    }
                }
            }
            case "library" -> {
                for (mage.cards.Card card : p1.getLibrary().getCards(game)) {
                    if ("Rograkh, Son of Rohgahh".equals(card.getName())) {
                        found = true;
                    }
                }
            }
            default -> fail("unknown terminal zone " + expectedTerminalZone);
        }
        assertTrue(found, fixtureId + ": genuine " + causeCard
                + " must move the test commander to " + expectedTerminalZone);
    }

    static void assertSpellOnStack(
            XmageFullGameSession session, String cardName, String tag) {
        boolean found = false;
        for (mage.game.stack.StackObject stackObject
                : session.restorationGame().getStack()) {
            if (cardName.equals(stackObject.getName())) {
                found = true;
            }
        }
        assertTrue(found, tag + ": " + cardName + " must be on the stack after payment");
    }
}
