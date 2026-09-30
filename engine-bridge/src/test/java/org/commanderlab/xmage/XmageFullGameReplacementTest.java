package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.counters.CounterType;
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
 * RG-08 Lab closure: general replacement-effect timing through the bridge.
 *
 * <p>Reuse classification: {@code ENGINE_NATIVE_REUSE} (new qualification,
 * no Rules change). The engine owns discovery, consumed/already-applied
 * tracking, affected-player choice, and iteration safety
 * ({@code ContinuousEffects.replaceEvent}, runtime-qualified engine-side by
 * RG-08). The bridge only projects the native {@code replacement_effect} and
 * {@code choose_use} decisions and submits the pilot's explicit selection.
 * Every test below drives a real card through the native replacement path and
 * asserts native postconditions.</p>
 */
class XmageFullGameReplacementTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String BEARS = "Grizzly Bears";
    private static final String MOUNTAIN_LABEL = "Mountain \u2014 {T}: Add {R}.";
    private static final String PLAINS_LABEL = "Plains \u2014 {T}: Add {W}.";
    private static final String FOREST_LABEL = "Forest \u2014 {T}: Add {G}.";

    record Started(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageNativeStateRestoration restoration) {
    }

    private static String semanticKey(String prefix, String pid, String name, int index) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        if (slug.length() > 24) {
            slug = slug.substring(0, 24);
        }
        return "obj:" + prefix + "-" + pid + "-" + index + "-" + slug;
    }

    private static XmageNativeStateRestoration.RequestedObject battlefield(
            String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                semanticKey("bf", pid, name, index), name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }

    private static XmageNativeStateRestoration.RequestedObject graveyard(
            String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                semanticKey("gy", pid, name, index), name, pid, pid,
                mage.constants.Zone.GRAVEYARD, false);
    }

    private static XmageNativeStateRestoration.RequestedObject handCard(
            String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                semanticKey("hand", pid, name, index), name, pid, pid,
                mage.constants.Zone.HAND, false);
    }

    private static Started startReplacement(
            String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        return startReplacement(tag, playerCount, objects, false);
    }

    /**
     * Arrival that declines every optional Dredge use question (transport:
     * opening draws must not consume the fixture dredgers). A multi-dredger
     * replacement_effect during arrival explicitly selects Stinkweed Imp and
     * records the forced mill in the post-arrival baseline taken by callers.
     */
    private static Started startReplacement(
            String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects,
            boolean declineDredgeArrival) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, playerCount, 424242L, List.copyOf(players), List.copyOf(commanders),
                List.copyOf(objects),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(
                    tag + "-" + player.playerId(), tag + "-hash",
                    mainboard, List.of(ROGRAKH)).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        if (declineDredgeArrival) {
            driveArrivalDecliningDredge(session, restoration, seats, tag);
            restoration.restoreAfterArrival(session.restorationGame(), seats);
            XmageNativeStateRestoration.revalidate(session.restorationGame());
        } else {
            XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        }
        return new Started(session, seats, restoration);
    }

    private static void driveArrivalDecliningDredge(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats,
            String tag) {
        for (int step = 0; step < 120; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")
                    && readback.get("step").getAsString().equals("PRECOMBAT_MAIN")) {
                return;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("[RG-08] engine terminal before arrival at step " + step);
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            JsonObject action;
            if ("mulligan".equals(decisionClass)) {
                action = XmageNativeStateRestorationTest.singleActionOfType(
                        legal, "mulligan", "keep");
            } else if ("choose_object".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                action = XmageNativeStateRestorationTest.singleSelfAction(legal, actorId);
            } else if ("priority".equals(decisionClass)) {
                action = XmageNativeStateRestorationTest.singleActionOfType(
                        legal, "pass_priority", null);
            } else if ("choose_use".equals(decisionClass)) {
                // Opening-draw Dredge: decline (No) so the fixture dredger
                // survives to the fixture draw.
                action = booleanOption(legal, false);
            } else if ("replacement_effect".equals(decisionClass)) {
                // Multi-dredger opening draw: explicitly take the Imp so the
                // Troll survives to the fixture draw; callers baseline after
                // arrival, absorbing the forced mill.
                action = replacementOptionByFragment(legal, "Stinkweed Imp");
            } else {
                fail("[RG-08] unexpected decision class during arrival: " + decisionClass
                        + " prompt=" + pending.get("prompt").getAsString()
                        + " at step " + step);
                return;
            }
            JsonObject after = session.submitAction(
                    XmageNativeStateRestorationTest.genericProposal(
                            tag + "-arrival-" + step, actorId,
                            action.get("action_id").getAsString(),
                            action.get("action_type").getAsString()));
            assertEquals(pending.get("decision_id").getAsString(),
                    after.get("executed_decision_id").getAsString());
        }
        fail("[RG-08] arrival bound breached");
    }

    private static JsonObject booleanOption(JsonObject legal, boolean value) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta.has("value") && !meta.get("value").isJsonNull()
                    && meta.get("value").getAsBoolean() == value) {
                assertTrue(match == null, "[RG-08] unique boolean option expected");
                match = action;
            }
        }
        assertTrue(match != null, "[RG-08] boolean option must be offered: " + value);
        return match;
    }

    static JsonObject replacementOptionByFragment(JsonObject legal, String fragment) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.toString().contains(fragment)) {
                assertTrue(match == null,
                        "[RG-08] unique replacement option expected for " + fragment);
                match = action;
            }
        }
        assertTrue(match != null,
                "[RG-08] replacement option must be offered for " + fragment
                        + " in " + legal.getAsJsonArray("actions").size() + " options");
        return match;
    }

    /**
     * Cost-aware land tapping: taps sources with the given labels in order,
     * then spends pool mana. Labels must match engine mana-ability labels
     * exactly; any missing source fails closed (never substitutes).
     */
    static void payLands(
            XmageFullGameSession session, String tag, List<String> tapLabels, int rounds) {
        int tapsDone = 0;
        for (int round = 0; round < rounds; round++) {
            JsonObject pending =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            if (pending.isJsonNull()
                    || !"mana_payment".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            JsonObject legal = session.legalActionsPayload();
            if (tapsDone < tapLabels.size()) {
                String want = tapLabels.get(tapsDone);
                JsonObject tap = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    String optionType = action.getAsJsonObject("metadata")
                            .get("option_type").getAsString();
                    String label = action.getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if ("mana_ability".equals(optionType) && want.equals(label)) {
                        if (tap != null) {
                            // Deterministic: least action id among identical labels.
                            if (action.get("action_id").getAsString().compareTo(
                                    tap.get("action_id").getAsString()) < 0) {
                                tap = action;
                            }
                        } else {
                            tap = action;
                        }
                    }
                }
                assertTrue(tap != null,
                        "[RG-08] required mana source missing: " + want);
                XmageFullGameTaxExecutionTest.submit(session, tag + "-tap-" + round, tap);
                tapsDone++;
            } else {
                List<JsonObject> pool = new ArrayList<>();
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if ("mana_pool".equals(action.getAsJsonObject("metadata")
                            .get("option_type").getAsString())) {
                        pool.add(action);
                    }
                }
                assertTrue(!pool.isEmpty(), "[RG-08] pool spend must be offered");
                pool.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                XmageFullGameTaxExecutionTest.submit(session, tag + "-spend-" + round, pool.get(0));
            }
        }
    }

    /**
     * Resolution loop that additionally answers single-Furnace-style
     * replacement choices explicitly by source fragment. choose_use is out
     * of scope here and fails closed for callers to handle.
     */
    static void resolveWithReplacement(
            XmageFullGameSession session, String tag, String replacementFragment) {
        for (int step = 0; step < 60; step++) {
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            if (pending.isJsonNull()) {
                fail("[RG-08] engine terminal during resolution");
            }
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)
                    && session.restorationGame().getStack().isEmpty()) {
                return;
            }
            if ("priority".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-resolve-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                session.legalActionsPayload(), "pass_priority", null));
            } else if ("replacement_effect".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-repl-" + step,
                        replacementOptionByFragment(
                                session.legalActionsPayload(), replacementFragment));
            } else {
                fail("[RG-08] unexpected class during resolution: " + decisionClass);
            }
        }
        fail("[RG-08] resolution bound breached");
    }

    private static void passPriority(Started started, String tag) {
        XmageFullGameTaxExecutionTest.submit(started.session(), tag,
                XmageFullGameTaxExecutionTest.singleActionOfType(
                        started.session().legalActionsPayload(), "pass_priority", null));
    }

    private static int graveyardCount(Started started, String pid, String cardName) {
        int count = 0;
        Player player = started.seats().get(pid);
        for (Card card : player.getGraveyard()
                .getCards(started.session().restorationGame())) {
            if (cardName.equals(card.getName())) {
                count++;
            }
        }
        return count;
    }

    private static int handCount(Started started, String pid, String cardName) {
        int count = 0;
        Player player = started.seats().get(pid);
        for (Card card : player.getHand()
                .getCards(started.session().restorationGame())) {
            if (cardName.equals(card.getName())) {
                count++;
            }
        }
        return count;
    }

    private static JsonObject submitYes(Started started, String tag) {
        XmageFullGameSession session = started.session();
        JsonObject legal = session.legalActionsPayload();
        JsonObject yes = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta.has("value") && !meta.get("value").isJsonNull()
                    && meta.get("value").getAsBoolean()) {
                assertTrue(yes == null, "[RG-08] unique Yes option expected");
                yes = action;
            }
        }
        assertTrue(yes != null, "[RG-08] Yes must be explicitly offered");
        return XmageFullGameTaxExecutionTest.submit(session, tag, yes);
    }

    private static void submitTargets(Started started, String tag, List<String> optionIds) {
        XmageFullGameSession session = started.session();
        JsonObject targetLegal = session.legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        String decisionId = targetLegal.get("decision_id").getAsString();
        String actorId = targetLegal.get("actor_id").getAsString();
        long offset = targetLegal.get("decision_offset").getAsLong();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", decisionId + ":" + optionIds.get(0));
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", offset);
        JsonArray selected = new JsonArray();
        optionIds.forEach(selected::add);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }

    /**
     * Advances P1's turn-1 into P1's turn-2 draw step, answering only
     * priority/hold/empty-block/exact-discard transport. Stops at the first
     * non-transport decision (the replacement question) and returns it.
     */
    private static JsonObject advanceToFirstReplacementQuestion(Started started, String tag) {
        return advanceCountingP1Discards(started, tag).question();
    }

    /**
     * Replacement question plus the number of cards P1 discarded to hand size
     * on the way there. Hand/graveyard expectations are derived from this
     * observed count instead of assuming a cleanup discard: in a two-player
     * game the starting player skips their first draw step (CR 103.8a), so P1
     * enters their next turn at seven cards and discards nothing.
     */
    private record Advance(JsonObject question, int p1Discards) {
    }

    private static Advance advanceCountingP1Discards(Started started, String tag) {
        XmageFullGameSession session = started.session();
        int p1Discards = 0;
        for (int step = 0; step < 300; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("[RG-08] engine terminal before the replacement question");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            switch (decisionClass) {
                case "priority" -> passPriority(started, tag + "-pass-" + step);
                case "declare_attacker" -> XmageFullGameTaxExecutionTest.submit(session,
                        tag + "-hold-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                session.legalActionsPayload(), "declare_attackers",
                                "hold_attacker"));
                case "declare_blocker" -> submitEmptyChoice(session,
                        tag + "-block-" + step, pending, "declare_blocker");
                case "choose_object" -> {
                    // Transport only: opening-hand-plus-draw cleanup discards
                    // select exactly the required amount, deterministically
                    // first in offered order. A non-discard choose_object
                    // shape fails closed below via the bounds check.
                    String chooser = XmageNativeStateRestorationTest.pidOf(
                            started.seats(),
                            session.legalActionsPayload().get("actor_id").getAsString());
                    int discarded = submitFirstMaxChoice(
                            session, tag + "-discard-" + step, pending);
                    if ("P1".equals(chooser)) {
                        p1Discards += discarded;
                    }
                }
                case "choose_use", "replacement_effect" -> {
                    return new Advance(pending, p1Discards);
                }
                default -> fail("[RG-08] unexpected class before replacement: " + decisionClass);
            }
        }
        fail("[RG-08] replacement question never arrived");
        return null;
    }

    private static void submitEmptyChoice(
            XmageFullGameSession session, String tag, JsonObject pending, String decisionClass) {
        int min = pending.get("minimum_selections").getAsInt();
        if (min != 0) {
            fail("[RG-08] required " + decisionClass + " is out of transport scope");
        }
        JsonObject legal = session.legalActionsPayload();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", "");
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(pending.get("decision_id").getAsString(),
                after.get("executed_decision_id").getAsString());
    }

    private static int submitFirstMaxChoice(
            XmageFullGameSession session, String tag, JsonObject pending) {
        int min = pending.get("minimum_selections").getAsInt();
        int max = pending.get("maximum_selections").getAsInt();
        if (min == 0) {
            submitEmptyChoice(session, tag, pending, "choose_object");
            return 0;
        }
        JsonObject legal = session.legalActionsPayload();
        List<String> offered = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            offered.add(element.getAsJsonObject().getAsJsonObject("metadata")
                    .get("option_id").getAsString());
        }
        offered.sort(String::compareTo);
        if (offered.size() < max) {
            fail("[RG-08] choose_object offers fewer options than required");
        }
        List<String> selected = offered.subList(0, max);
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + selected.get(0));
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selectedJson = new JsonArray();
        selected.forEach(selectedJson::add);
        choices.add("selected_option_ids", selectedJson);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
        return selected.size();
    }

    private static void assertTwoPlayerStarterDidNotDiscard(Advance advance) {
        assertEquals(0, advance.p1Discards(),
                "[RG-08] CR 103.8a: the 2P starting player skips their first draw, so P1 "
                        + "reaches cleanup at seven cards and discards nothing");
    }

    @Test
    void replacementDredgeAcceptedReplacesDrawWithMill() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(graveyard("P1", "Stinkweed Imp", 0));
        Started started = startReplacement("rg08-dredge-yes", 2, objects, true);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();
        int handBefore = seats.get("P1").getHand().size();
        int graveBefore = seats.get("P1").getGraveyard().size();

        Advance advance = advanceCountingP1Discards(started, "rg08-dredge-yes");
        assertTwoPlayerStarterDidNotDiscard(advance);
        int discarded = advance.p1Discards();
        JsonObject question = advance.question();
        assertEquals("choose_use", question.get("decision_class").getAsString(),
                "[RG-08] Dredge must surface as an explicit use choice, not a silent skip");
        submitYes(started, "rg08-dredge-yes-accept");

        // Rider as part of the same replacement: Imp to hand AND mill five.
        assertEquals(1, handCount(started, "P1", "Stinkweed Imp"),
                "[RG-08] accepted Dredge must return the Imp to hand");
        // The Imp returning is the only hand gain: no card is also drawn.
        assertEquals(handBefore - discarded + 1, seats.get("P1").getHand().size(),
                "[RG-08] the replaced draw must not also draw a card");
        // Discards in, the Imp out, five milled.
        assertEquals(graveBefore + discarded - 1 + 5, seats.get("P1").getGraveyard().size(),
                "[RG-08] Dredge 5 must mill exactly five as the same replacement");
        // No loop: the game continues to a normal priority decision.
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        assertTrue(!pending.isJsonNull(), "[RG-08] game must continue after Dredge");
    }

    @Test
    void replacementDredgeDeclinedDrawsNormallyOnce() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(graveyard("P1", "Stinkweed Imp", 0));
        Started started = startReplacement("rg08-dredge-no", 2, objects, true);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();
        int handBefore = seats.get("P1").getHand().size();
        int graveBefore = seats.get("P1").getGraveyard().size();
        int libBefore = seats.get("P1").getLibrary().size();
        Advance advance = advanceCountingP1Discards(started, "rg08-dredge-no");
        assertTwoPlayerStarterDidNotDiscard(advance);
        int discarded = advance.p1Discards();
        JsonObject question = advance.question();
        assertEquals("choose_use", question.get("decision_class").getAsString());
        JsonObject legal = session.legalActionsPayload();
        JsonObject no = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta.has("value") && !meta.get("value").isJsonNull()
                    && !meta.get("value").getAsBoolean()) {
                assertTrue(no == null);
                no = action;
            }
        }
        assertTrue(no != null, "[RG-08] No must be explicitly offered");
        XmageFullGameTaxExecutionTest.submit(session, "rg08-dredge-no-decline", no);
        assertEquals(0, handCount(started, "P1", "Stinkweed Imp"),
                "[RG-08] declined Dredge must leave the Imp in the graveyard");
        // Exactly one normal draw (+1) after any observed transport discard;
        // the library delta proves a single draw left it.
        assertEquals(handBefore - discarded + 1, seats.get("P1").getHand().size(),
                "[RG-08] declined Dredge must draw exactly one card");
        assertEquals(graveBefore + discarded, seats.get("P1").getGraveyard().size(),
                "[RG-08] only transport discards may enter the graveyard");
        assertEquals(libBefore - 1, seats.get("P1").getLibrary().size(),
                "[RG-08] exactly one drawn card may leave the library: no mill, no loop");
    }

    @Test
    void replacementTwoDredgersOfferExplicitChoice() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(graveyard("P1", "Stinkweed Imp", 0));
        objects.add(graveyard("P1", "Golgari Grave-Troll", 0));
        Started started = startReplacement("rg08-dredge-two", 2, objects, true);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();
        int graveBefore = seats.get("P1").getGraveyard().size();
        int impHandBefore = handCount(started, "P1", "Stinkweed Imp");

        Advance advance = advanceCountingP1Discards(started, "rg08-dredge-two");
        assertTwoPlayerStarterDidNotDiscard(advance);
        int discarded = advance.p1Discards();
        JsonObject question = advance.question();
        // Two applicable replacements: the engine offers the affected player
        // an explicit selection (choose_use per dredger or one
        // replacement_effect choice). Either native shape is accepted; what
        // matters is explicit selection, never positional default.
        String decisionClass = question.get("decision_class").getAsString();
        assertTrue("choose_use".equals(decisionClass)
                        || "replacement_effect".equals(decisionClass),
                "[RG-08] two dredgers must offer an explicit selection, observed "
                        + decisionClass);
        if ("replacement_effect".equals(decisionClass)) {
            JsonObject legal = session.legalActionsPayload();
            assertEquals(2, legal.getAsJsonArray("actions").size(),
                    "[RG-08] both dredgers must be offered");
            JsonObject troll = null;
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                if (action.toString().contains("Grave-Troll")) {
                    troll = action;
                }
            }
            assertTrue(troll != null, "[RG-08] Grave-Troll option must be identifiable");
            XmageFullGameTaxExecutionTest.submit(session, "rg08-dredge-two-troll", troll);
            // Native two-step dance: the chosen effect confirms via its own
            // Dredge use question.
            JsonObject confirm =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            assertEquals("choose_use", confirm.get("decision_class").getAsString(),
                    "[RG-08] chosen Dredge must confirm via an explicit use choice");
            assertTrue(confirm.get("prompt").getAsString().contains("Grave-Troll"),
                    "[RG-08] confirmation must name the Troll: "
                            + confirm.get("prompt").getAsString());
            submitYes(started, "rg08-dredge-two-confirm");
        } else {
            // Sequential per-dredger use choices: decline Imp, accept Troll.
            // First question: determine which dredger it names.
            String firstPrompt = question.get("prompt").getAsString();
            if (firstPrompt.contains("Stinkweed Imp")) {
                JsonObject legal = session.legalActionsPayload();
                JsonObject no = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    JsonObject meta = action.getAsJsonObject("metadata")
                            .getAsJsonObject("xmage_option_metadata");
                    if (meta.has("value") && !meta.get("value").isJsonNull()
                            && !meta.get("value").getAsBoolean()) {
                        no = action;
                    }
                }
                assertTrue(no != null);
                XmageFullGameTaxExecutionTest.submit(session, "rg08-dredge-two-noimp", no);
                JsonObject second =
                        session.pendingDecisionPayload().getAsJsonObject("decision");
                assertEquals("choose_use", second.get("decision_class").getAsString());
                assertTrue(second.get("prompt").getAsString().contains("Grave-Troll"),
                        "[RG-08] second question must name the Troll: "
                                + second.get("prompt").getAsString());
                submitYes(started, "rg08-dredge-two-yestroll");
            } else {
                submitYes(started, "rg08-dredge-two-yestroll");
            }
        }
        assertEquals(1, handCount(started, "P1", "Golgari Grave-Troll"),
                "[RG-08] chosen Troll must return to hand");
        assertEquals(impHandBefore, handCount(started, "P1", "Stinkweed Imp"),
                "[RG-08] the unchosen dredger must stay where arrival left it");
        // Discards in, the Troll out, six milled.
        assertEquals(graveBefore + discarded - 1 + 6, seats.get("P1").getGraveyard().size(),
                "[RG-08] Dredge 6 must mill exactly six");
    }

    @Test
    void replacementRestInPeaceChangesDestinationForAllOwners() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P2", "Rest in Peace", 0));
        objects.add(battlefield("P1", "Plains", 0));
        objects.add(battlefield("P1", "Plains", 1));
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(battlefield("P1", "Mountain", 1));
        objects.add(handCard("P1", "Wrath of God", 0));
        objects.add(battlefield("P1", BEARS, 0));
        objects.add(battlefield("P1", BEARS, 1));
        objects.add(battlefield("P2", BEARS, 0));
        Started started = startReplacement("rg08-rip-2p", 2, objects);
        XmageFullGameSession session = started.session();

        XmageFullGameTaxExecutionTest.submit(session, "rg08-rip-cast",
                XmageExternalRiskSignalTest.spellOffer(
                        session.legalActionsPayload(), "Wrath of God"));
        payLands(session, "rg08-rip-pay",
                List.of(PLAINS_LABEL, PLAINS_LABEL, MOUNTAIN_LABEL, MOUNTAIN_LABEL), 12);
        XmageExternalRiskSignalTest.resolveStackEmpty(session, "rg08-rip");

        assertTrue(session.restorationGame().getStack().isEmpty());
        int exiledBears = 0;
        for (Player player : started.seats().values()) {
            for (Card card : session.restorationGame().getExile()
                    .getCardsOwned(session.restorationGame(), player.getId())) {
                if (BEARS.equals(card.getName())) {
                    exiledBears++;
                }
            }
        }
        assertEquals(3, exiledBears,
                "[RG-08] all three destroyed bears (both owners) must be exiled");
        assertEquals(0, graveyardCount(started, "P1", BEARS));
        assertEquals(0, graveyardCount(started, "P2", BEARS));
    }

    @Test
    void replacementCommanderZoneChoiceMovesToCommand() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P2", "Mountain", 0));
        objects.add(handCard("P2", "Lightning Bolt", 0));
        Started started = startReplacement("rg08-cmdzone-2p", 2, objects);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();

        // Genuine commander onto P1's battlefield (Rograkh costs {0}).
        XmageFullGameTaxExecutionTest.submit(session, "rg08-cmdzone-castcmd",
                XmageFullGameTaxExecutionTest.castOffer(
                        session.legalActionsPayload(), "Rograkh, Son of Rohgahh"));
        XmageExternalRiskSignalTest.resolveStackEmpty(session, "rg08-cmdzone-cmd");
        String commanderId = null;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if ("Rograkh, Son of Rohgahh".equals(permanent.getName())
                    && seats.get("P1").getId().equals(permanent.getControllerId())) {
                commanderId = permanent.getId().toString();
            }
        }
        assertTrue(commanderId != null, "[RG-08] genuine commander must resolve");

        XmageExternalRiskSignalTest.passToActor(session, "rg08-cmdzone", seats, "P2");
        XmageFullGameTaxExecutionTest.submit(session, "rg08-cmdzone-bolt",
                XmageExternalRiskSignalTest.spellOffer(
                        session.legalActionsPayload(), "Lightning Bolt"));
        submitTargets(started, "rg08-cmdzone-targets", List.of(commanderId));
        XmageExternalRiskSignalTest.payHomogeneous(
                session, "rg08-cmdzone-pay", MOUNTAIN_LABEL, 4);

        // Lethal damage resolves; the commander-zone replacement choice must
        // be offered to the owner at the correct Rules point and answered
        // explicitly by exact label.
        boolean zoneChoiceSeen = false;
        for (int step = 0; step < 40; step++) {
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)
                    && session.restorationGame().getStack().isEmpty()) {
                break;
            }
            if ("priority".equals(decisionClass)) {
                passPriority(started, "rg08-cmdzone-resolve-" + step);
            } else if ("choose_use".equals(decisionClass)) {
                JsonObject legal = session.legalActionsPayload();
                JsonObject moveToCommand = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    String label = action.getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (label.startsWith("Move to command")) {
                        assertTrue(moveToCommand == null);
                        moveToCommand = action;
                    }
                }
                assertTrue(moveToCommand != null,
                        "[RG-08] commander-zone option must be offered");
                String actorPid = XmageNativeStateRestorationTest.pidOf(
                        seats, pending.get("actor_id").getAsString());
                assertEquals("P1", actorPid,
                        "[RG-08] the owner must make the zone choice");
                zoneChoiceSeen = true;
                XmageFullGameTaxExecutionTest.submit(
                        session, "rg08-cmdzone-zone-" + step, moveToCommand);
            } else {
                fail("[RG-08] unexpected class during commander-zone flow: " + decisionClass);
            }
            if (step == 39) {
                fail("[RG-08] commander-zone resolution bound breached");
            }
        }
        assertTrue(zoneChoiceSeen, "[RG-08] the zone replacement must be offered");
        Card homeCommander = null;
        for (Card card : session.restorationGame().getCommanderCardsFromCommandZone(
                seats.get("P1"), mage.constants.CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
            if ("Rograkh, Son of Rohgahh".equals(card.getName())) {
                homeCommander = card;
            }
        }
        assertTrue(homeCommander != null,
                "[RG-08] commander must be in the command zone");
        String cost = XmageNativeStateRestoration.enumerateCommanderCastCost(
                session.restorationGame(), homeCommander);
        assertTrue(cost.contains("{2}"),
                "[RG-08] commander tax must apply after one cast: " + cost);
    }

    /**
     * Ordering variant: accepting the Imp instead of the Troll is a distinct
     * affected-player selection with a distinct outcome (mill five, Imp to
     * hand). Together with the Troll run this proves the Lab surfaces
     * multi-replacement ordering choice with outcome fidelity.
     */
    @Test
    void replacementTwoDredgersAcceptingImpMillsFive() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(graveyard("P1", "Stinkweed Imp", 0));
        objects.add(graveyard("P1", "Golgari Grave-Troll", 0));
        Started started = startReplacement("rg08-dredge-imp", 2, objects, true);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();
        int graveBefore = seats.get("P1").getGraveyard().size();
        int trollHandBefore = handCount(started, "P1", "Golgari Grave-Troll");

        Advance advance = advanceCountingP1Discards(started, "rg08-dredge-imp");
        assertTwoPlayerStarterDidNotDiscard(advance);
        int discarded = advance.p1Discards();
        JsonObject question = advance.question();
        assertEquals("replacement_effect", question.get("decision_class").getAsString(),
                "[RG-08] two dredgers must offer an explicit replacement selection");
        JsonObject legal = session.legalActionsPayload();
        assertEquals(2, legal.getAsJsonArray("actions").size());
        XmageFullGameTaxExecutionTest.submit(session, "rg08-dredge-imp-pick",
                replacementOptionByFragment(legal, "Stinkweed Imp"));
        JsonObject confirm =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals("choose_use", confirm.get("decision_class").getAsString());
        submitYes(started, "rg08-dredge-imp-confirm");

        assertEquals(1, handCount(started, "P1", "Stinkweed Imp"),
                "[RG-08] chosen Imp must return to hand");
        assertEquals(trollHandBefore, handCount(started, "P1", "Golgari Grave-Troll"));
        // Discards in, the Imp out, five milled.
        assertEquals(graveBefore + discarded - 1 + 5, seats.get("P1").getGraveyard().size(),
                "[RG-08] Dredge 5 mills five while the Imp leaves the graveyard");
    }

    @Test
    void replacementAffectedPlayerChoosesInMultiplayer() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(graveyard("P1", "Stinkweed Imp", 0));
        Started started = startReplacement("rg08-dredge-3p", 3, objects, true);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();

        JsonObject question = advanceToFirstReplacementQuestion(started, "rg08-dredge-3p");
        assertEquals("choose_use", question.get("decision_class").getAsString());
        String actorPid = XmageNativeStateRestorationTest.pidOf(
                seats, question.get("actor_id").getAsString());
        assertEquals("P1", actorPid,
                "[RG-08] the drawing player must decide, even with two opponents");
        submitYes(started, "rg08-dredge-3p-accept");
        assertEquals(1, handCount(started, "P1", "Stinkweed Imp"),
                "[RG-08] 3P Dredge must return the Imp to the drawer's hand");
    }

    @Test
    void replacementDamageThenPreventionUsesModifiedEvent() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Furnace of Rath", 0));
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(battlefield("P1", "Mountain", 1));
        objects.add(handCard("P1", "Shock", 0));
        objects.add(battlefield("P2", "Plains", 0));
        objects.add(battlefield("P2", "Plains", 1));
        objects.add(handCard("P2", "Test of Faith", 0));
        objects.add(battlefield("P2", BEARS, 0));
        Started started = startReplacement("rg08-furnace-2p", 2, objects);
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();

        String bearId = null;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (BEARS.equals(permanent.getName())) {
                bearId = permanent.getId().toString();
            }
        }
        assertTrue(bearId != null);
        XmageFullGameTaxExecutionTest.submit(session, "rg08-furnace-shock",
                XmageExternalRiskSignalTest.spellOffer(
                        session.legalActionsPayload(), "Shock"));
        submitTargets(started, "rg08-furnace-targets", List.of(bearId));
        XmageExternalRiskSignalTest.payHomogeneous(
                session, "rg08-furnace-pay", MOUNTAIN_LABEL, 6);
        XmageExternalRiskSignalTest.passToActor(session, "rg08-furnace", seats, "P2");
        XmageFullGameTaxExecutionTest.submit(session, "rg08-furnace-test",
                XmageExternalRiskSignalTest.spellOffer(
                        session.legalActionsPayload(), "Test of Faith"));
        submitTargets(started, "rg08-furnace-testtargets", List.of(bearId));
        XmageExternalRiskSignalTest.payHomogeneous(
                session, "rg08-furnace-testpay", PLAINS_LABEL, 6);
        resolveWithReplacement(session, "rg08-furnace", "Furnace of Rath");

        Permanent survivor = null;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (BEARS.equals(permanent.getName())) {
                survivor = permanent;
            }
        }
        assertTrue(survivor != null,
                "[RG-08] prevention must save the bear from doubled Shock");
        assertEquals(3, survivor.getCounters(session.restorationGame())
                        .getCount(CounterType.P1P1),
                "[RG-08] three prevented damage must yield three +1/+1 counters");
        assertEquals(1, graveyardCount(started, "P1", "Shock"));
        assertEquals(1, graveyardCount(started, "P2", "Test of Faith"));
    }
}
