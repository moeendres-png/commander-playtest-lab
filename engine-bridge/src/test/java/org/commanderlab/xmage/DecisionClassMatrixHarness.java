package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.players.Player;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.function.Predicate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * #662 SLOT-06 decision-class matrix harness (test support).
 *
 * <p>A scenario is a native-restored 2P Commander game at turn 1, precombat main,
 * P1 active with priority, plus objects placed in hand or on the battlefield, and a
 * declared script of test-pilot answers that drives the game to one pending
 * decision of the class under test. The harness never chooses on its own: every
 * submitted action is named by the script, and a frame the script does not cover
 * fails the test.</p>
 */
final class DecisionClassMatrixHarness {

    private DecisionClassMatrixHarness() {
    }

    /** One placed object: seat P1/P2, zone HAND or BATTLEFIELD, card name. */
    record Placed(String seat, Zone zone, String card) {
        static Placed hand(String seat, String card) {
            return new Placed(seat, Zone.HAND, card);
        }

        static Placed battlefield(String seat, String card) {
            return new Placed(seat, Zone.BATTLEFIELD, card);
        }
    }

    /** One declared script step: the expected class and seat, and the action to take. */
    record Step(String decisionClass, String seat, String description, Predicate<JsonObject> pick) {
    }

    static Step step(String decisionClass, String seat, String labelPart) {
        return new Step(decisionClass, seat, labelPart,
                action -> label(action).contains(labelPart));
    }

    /**
     * Declared pass-through: every priority frame is answered with pass until the
     * engine asks {@code decisionClass} of {@code seat}; that frame is left for
     * the next step (or is the target). Any other non-priority frame fails.
     */
    static Step passUntil(String decisionClass, String seat) {
        return new Step(PASS_UNTIL + decisionClass, seat, "pass until " + decisionClass, action -> false);
    }

    static final String PASS_UNTIL = "pass-until:";

    /** Pass and pay until the next frame that is neither priority nor mana payment. */
    static Step passUntilAny() {
        return new Step(PASS_UNTIL + "*", "*", "pass until any decision", action -> false);
    }

    /** Development aid: fail at the next non-priority frame and print it. */
    static Step probe() {
        return new Step("probe", "?", "probe", action -> false);
    }

    static Step pass(String seat) {
        return new Step("priority", seat, "pass",
                action -> "pass_priority".equals(optionType(action)));
    }

    record Scenario(String id, long seed, List<Placed> objects, List<Step> script,
                    String targetClass, String targetSeat) {
    }

    /** A live session plus its seat map. */
    record Live(XmageFullGameSession session, Map<String, Player> seats) {
        String seatOf(String actorId) {
            for (Map.Entry<String, Player> entry : seats.entrySet()) {
                if (entry.getValue().getId().toString().equals(actorId)) {
                    return entry.getKey();
                }
            }
            return "?";
        }
    }

    static Live open(Scenario scenario) {
        if (scenario.objects() == null) {
            // Pregame scenario: a plain 2P game from its first decision (starting
            // player, mulligans, London bottom), no restoration.
            XmageFullGameSession session = XmageFullGameCancelRewindTest.unstarted(
                    scenario.id(), scenario.seed());
            session.start();
            Map<String, Player> seats = new LinkedHashMap<>();
            com.google.gson.JsonArray outcomes = session.pendingDecisionPayload().getAsJsonArray("outcomes");
            for (int seat = 0; seat < outcomes.size(); seat++) {
                String id = outcomes.get(seat).getAsJsonObject().get("player_id").getAsString();
                seats.put("P" + (seat + 1), session.restorationGame().getPlayer(java.util.UUID.fromString(id)));
            }
            return new Live(session, seats);
        }
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        int index = 0;
        for (Placed placed : scenario.objects()) {
            if (placed.zone() == Zone.LIBRARY) {
                continue;
            }
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    scenario.id() + "-o" + index++, placed.card(), placed.seat(), placed.seat(),
                    placed.zone(), false));
        }
        Map<String, Boolean> sinceTurnBegan = new LinkedHashMap<>();
        for (XmageNativeStateRestoration.RequestedObject object : objects) {
            if (object.zone() == Zone.BATTLEFIELD) {
                sinceTurnBegan.put(object.semanticId(), true);
            }
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                scenario.id(),
                2,
                scenario.seed(),
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(new XmageNativeStateRestoration.RequestedCommander(
                                "C1", "Esika, God of the Tree", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "C2", "Esika, God of the Tree", "P2", 0)),
                List.of(),
                objects,
                1,
                TurnPhase.PRECOMBAT_MAIN,
                PhaseStep.PRECOMBAT_MAIN,
                "P1",
                "P1",
                Map.of(),
                sinceTurnBegan);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = XmageNativeStateRestorationTest.importScaffolding(importer, plan, scenario.id());
        XmageFullGameSession session = new XmageFullGameSession(
                scenario.id(), handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict constructed = restoration.compare(
                XmageNativeStateRestoration.readback(session.restorationGame(), seats), seats);
        assertTrue(constructed.match(), scenario.id() + " construction: " + constructed.mismatches());
        // Test-only setup the restoration plan does not cover: a named card on top of
        // a library, placed while the engine is parked on its first decision.
        for (Placed placed : scenario.objects()) {
            if (placed.zone() != Zone.LIBRARY) {
                continue;
            }
            mage.game.Game game = session.restorationGame();
            Player owner = seats.get(placed.seat());
            mage.cards.Card card = XmageNativeStateRestoration.materializeCards(List.of(placed.card()))
                    .getCards().iterator().next();
            card.setOwnerId(owner.getId());
            game.loadCards(new java.util.HashSet<>(List.of(card)), owner.getId());
            owner.getLibrary().putOnTop(card, game);
        }
        return new Live(session, seats);
    }

    /**
     * Drive the declared script and return the frame of the class under test.
     * A frame that is neither the next scripted step nor the target fails.
     */
    static JsonObject driveToTarget(Live live, Scenario scenario) {
        List<Step> script = scenario.script();
        int cursor = 0;
        List<String> trace = new ArrayList<>();
        for (int guard = 0; guard < 200; guard++) {
            JsonObject frame = live.session().legalActionsPayload();
            String cls = frame.get("decision_class").getAsString();
            String seat = live.seatOf(frame.get("actor_id").getAsString());
            trace.add(cls + "/" + seat + (live.session().restorationGame().getStep() == null ? ""
                    : "@" + live.session().restorationGame().getTurnNum() + ":"
                    + live.session().restorationGame().getStep().getType()));
            if (cursor == script.size()) {
                assertEquals(scenario.targetClass(), cls,
                        scenario.id() + ": script ended at an unexpected frame " + labels(frame));
                assertEquals(scenario.targetSeat(), seat, scenario.id() + ": target actor");
                return frame;
            }
            Step next = script.get(cursor);
            if ("probe".equals(next.decisionClass())) {
                fail("PROBE " + cls + "/" + seat + " " + labels(frame) + " decision "
                        + frame.getAsJsonObject("decision").get("prompt") + " trace " + trace);
            }
            if (next.decisionClass().startsWith(PASS_UNTIL)) {
                String until = next.decisionClass().substring(PASS_UNTIL.length());
                if (until.equals(cls) && next.seat().equals(seat)
                        || "*".equals(until) && !"priority".equals(cls) && !"mana_payment".equals(cls)) {
                    cursor++;
                    continue;
                }
                if ("mana_payment".equals(cls)) {
                    // Declared test-pilot payment: spend pool mana first, else the first
                    // engine-offered mana ability.
                    JsonObject first = null;
                    for (String type : List.of("mana_pool", "mana_ability")) {
                        for (JsonObject action : actions(frame)) {
                            boolean advances = !"mana_pool".equals(type)
                                    || "true".equals(nativeField(action, "advances_payment"));
                            if (first == null && advances && type.equals(optionType(action))) {
                                first = action;
                            }
                        }
                    }
                    if (first == null) {
                        fail(scenario.id() + ": mana payment without a mana ability " + labels(frame));
                    }
                    live.session().submitAction(proposal(frame, first));
                    continue;
                }
                if (!"priority".equals(cls)) {
                    fail(scenario.id() + ": while passing until " + until + "/" + next.seat()
                            + " the engine asks " + cls + "/" + seat + " " + labels(frame));
                }
                JsonObject passAction = single(frame,
                        action -> "pass_priority".equals(optionType(action)), scenario.id() + " pass");
                live.session().submitAction(proposal(frame, passAction));
                continue;
            }
            if (!next.decisionClass().equals(cls) || !next.seat().equals(seat)) {
                fail(scenario.id() + ": step " + cursor + " expects " + next.decisionClass() + "/"
                        + next.seat() + " (" + next.description() + ") but the engine asks "
                        + cls + "/" + seat + " " + labels(frame));
            }
            if (next.pick() == null) {
                live.session().submitAction(emptySelection(frame));
                cursor++;
                continue;
            }
            if (next.description().startsWith(NUMERIC)) {
                JsonObject numericProposal = proposal(frame, actions(frame).get(0));
                numericProposal.getAsJsonObject("choices").addProperty("numeric_choice",
                        Integer.parseInt(next.description().substring(NUMERIC.length())));
                live.session().submitAction(numericProposal);
                cursor++;
                continue;
            }
            JsonObject chosen = FIRST.equals(next.description())
                    ? actions(frame).get(0)
                    : TAP_LAND.equals(next.description())
                    ? firstMatching(frame, next.pick(), scenario.id() + " step " + cursor)
                    : single(frame, next.pick(), scenario.id() + " step " + cursor);
            live.session().submitAction(proposal(frame, chosen));
            cursor++;
        }
        throw new AssertionError(scenario.id() + ": no target frame within 200 frames; trace "
                + trace.subList(0, Math.min(40, trace.size())));
    }

    /**
 * The first offered action matching {@code pick}, failing when none matches.
 * Used where several actions of the same class are equally valid answers and
 * the script names the kind rather than a unique label (several untapped
 * lands are all correct answers to "tap a land for mana").
 */
    static JsonObject firstMatching(JsonObject frame, Predicate<JsonObject> pick, String where) {
        for (JsonElement element : frame.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (pick.test(action)) {
                return action;
            }
        }
        return fail(where + ": no offered action matched " + labels(frame));
    }

    static JsonObject single(JsonObject frame, Predicate<JsonObject> pick, String where) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : frame.getAsJsonArray("actions")) {
            if (pick.test(element.getAsJsonObject())) {
                matches.add(element.getAsJsonObject());
            }
        }
        if (matches.size() != 1) {
            fail(where + ": expected exactly one matching action, got " + matches.size() + " in "
                    + labels(frame));
        }
        return matches.get(0);
    }

    static JsonObject proposal(JsonObject frame, JsonObject action) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "matrix-" + frame.get("decision_offset").getAsLong());
        proposal.addProperty("actor_id", action.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", frame.get("decision_id").getAsString());
        choices.addProperty("decision_offset", frame.get("decision_offset").getAsLong());
        proposal.add("choices", choices);
        return proposal;
    }

    static final String FIRST = "first offered";
    static final String NUMERIC = "numeric:";

    /** Declared numeric answer for a numeric frame (a test-pilot declaration). */
    static Step numeric(String decisionClass, String seat, int value) {
        return new Step(decisionClass, seat, NUMERIC + value, action -> true);
    }

    /** Declared step: the first offered action of this class (a test-pilot declaration). */
    static Step chooseFirst(String decisionClass, String seat) {
        return new Step(decisionClass, seat, FIRST, action -> true);
    }

    /** Declared empty selection, valid only where the engine allows zero selections. */
    static Step selectNone(String decisionClass, String seat) {
        return new Step(decisionClass, seat, "select none", null);
    }

    /**
     * Declared payment step that floats mana: tap the first offered mana ability
     * of this payment frame and answer nothing else.
     *
     * <p>{@code autoPayment} is off for this player
     * ({@code userData.setManaPoolAutomatic(false)}), so
     * {@code ManaCostsImpl.pay} keeps asking {@code playMana} after a land is
     * tapped: the engine's own {@code assignPayment} returns immediately while
     * no mana type is unlocked. The second {@code playMana} frame therefore
     * carries the tapped mana in the pool and offers it as {@code mana_pool}
     * options — the only shape in which the pool branch is reachable at all.</p>
     */
    static Step tapLand(String decisionClass, String seat) {
        return new Step(decisionClass, seat, TAP_LAND,
                action -> "mana_ability".equals(optionType(action)));
    }

    static final String TAP_LAND = "tap a land for mana";

    static JsonObject emptySelection(JsonObject frame) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "matrix-none-" + frame.get("decision_offset").getAsLong());
        proposal.addProperty("actor_id", frame.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", "");
        proposal.addProperty("action_type", "structural_decision");
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", frame.get("decision_id").getAsString());
        choices.addProperty("decision_offset", frame.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        proposal.add("choices", choices);
        return proposal;
    }

    static List<JsonObject> actions(JsonObject frame) {
        List<JsonObject> list = new ArrayList<>();
        frame.getAsJsonArray("actions").forEach(element -> list.add(element.getAsJsonObject()));
        return list;
    }

    static JsonObject metadata(JsonObject action) {
        return action.getAsJsonObject("metadata");
    }

    static String label(JsonObject action) {
        JsonObject metadata = metadata(action);
        return metadata.has("label") && !metadata.get("label").isJsonNull()
                ? metadata.get("label").getAsString() : "";
    }

    static String optionType(JsonObject action) {
        JsonObject metadata = metadata(action);
        return metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                ? metadata.get("option_type").getAsString() : "";
    }

    static JsonObject nativeMetadata(JsonObject action) {
        JsonObject metadata = metadata(action);
        return metadata.has("xmage_option_metadata") && metadata.get("xmage_option_metadata").isJsonObject()
                ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
    }

    static String nativeField(JsonObject action, String field) {
        JsonObject nativeMetadata = nativeMetadata(action);
        return nativeMetadata.has(field) && !nativeMetadata.get(field).isJsonNull()
                ? nativeMetadata.get(field).getAsString() : null;
    }

    static List<String> labels(JsonObject frame) {
        List<String> labels = new ArrayList<>();
        actions(frame).forEach(action -> labels.add(optionType(action) + ":" + label(action)));
        return labels;
    }

    static Set<String> sorted(Iterable<String> values) {
        Set<String> set = new TreeSet<>();
        values.forEach(set::add);
        return set;
    }

    static JsonArray empty() {
        return new JsonArray();
    }
}
