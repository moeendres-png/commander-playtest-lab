package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.constants.MultiplayerAttackOption;
import mage.constants.MultiAmountType;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.cards.decks.Deck;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import mage.util.MultiAmountMessage;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS229 numeric decision boundary: live-callback evidence for the S6
 * positive matrix (P-A1/P-A2/P-M1) plus transport/projection negatives
 * (N-14/N-15/N-16/N-22 families).
 *
 * <p>Live tests drive REAL native callbacks on a real game object through
 * the real bridge player, controller transport, and native submission;
 * the responder thread stands in for the Lab/pilot half with Lab-shaped
 * responses (the Lab half is proven separately against captured frames).
 * No legality is computed in the responder: it echoes chosen integers
 * back through the authoritative checks.</p>
 */
class XmageNumericDomainWs229Test {

    // P-A1: announce_x small span + span>16 through the real callback.
    @Test
    void announceXSmallAndLargeSpanSubmitInteriorValuesLive() throws Exception {
        Fixture fixture = liveFixture();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread responder = new Thread(() -> {
            try {
                int answered = 0;
                while (answered < 2 && !Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    JsonObject context = pending.getAsJsonObject("context");
                    int min = context.get("numeric_min").getAsInt();
                    int max = context.get("numeric_max").getAsInt();
                    // Lossless projection: zero options, verbatim bounds.
                    assertEquals(0, pending.getAsJsonArray("legal_options").size());
                    System.out.println("WS229_PENDING_ANNOUNCE " + pending);
                    // Interior values a {min,mid,max} collapse could never offer.
                    int chosen = (max - min) <= 16 ? min + 1 : min + 73;
                    JsonObject response = scalarResponse(pending, id);
                    response.addProperty("numeric_choice", chosen);
                    try {
                        fixture.controller.submit(response);
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        if (exc.getMessage() != null
                                && exc.getMessage().contains("STALE_DECISION")) {
                            continue;
                        }
                        throw exc;
                    }
                    answered++;
                    Thread.sleep(5L);
                }
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        responder.setDaemon(true);
        responder.start();
        int small = fixture.player.announceX(0, 5, "choose X", fixture.game, null, false);
        int large = fixture.player.announceX(0, 100, "choose X", fixture.game, null, false);
        responder.interrupt();
        responder.join(30_000L);
        if (failure.get() != null) {
            throw new IllegalStateException("responder failed", failure.get());
        }
        assertEquals(1, small);
        assertEquals(73, large);
    }

    // P-A2: amount small span + span>16 through the real callback.
    @Test
    void amountSmallAndLargeSpanSubmitInteriorValuesLive() throws Exception {
        Fixture fixture = liveFixture();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread responder = new Thread(() -> {
            try {
                int answered = 0;
                while (answered < 2 && !Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    JsonObject context = pending.getAsJsonObject("context");
                    int min = context.get("numeric_min").getAsInt();
                    int max = context.get("numeric_max").getAsInt();
                    assertEquals(0, pending.getAsJsonArray("legal_options").size());
                    System.out.println("WS229_PENDING_AMOUNT " + pending);
                    int chosen = (max - min) <= 16 ? max - 1 : min + 17;
                    JsonObject response = scalarResponse(pending, id);
                    response.addProperty("numeric_choice", chosen);
                    try {
                        fixture.controller.submit(response);
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        if (exc.getMessage() != null
                                && exc.getMessage().contains("STALE_DECISION")) {
                            continue;
                        }
                        throw exc;
                    }
                    answered++;
                    Thread.sleep(5L);
                }
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        responder.setDaemon(true);
        responder.start();
        int small = fixture.player.getAmount(1, 5, "choose amount", null, fixture.game);
        int large = fixture.player.getAmount(1, 40, "choose amount", null, fixture.game);
        responder.interrupt();
        responder.join(30_000L);
        if (failure.get() != null) {
            throw new IllegalStateException("responder failed", failure.get());
        }
        assertEquals(4, small);
        assertEquals(18, large);
    }

    // P-M1: joint vector with a span>16 leg and a binding total band.
    @Test
    void jointVectorWithLargeLegAndBindingTotalLive() throws Exception {
        Fixture fixture = liveFixture();
        List<MultiAmountMessage> messages = List.of(
                new MultiAmountMessage("damage to A", 0, 100),
                new MultiAmountMessage("damage to B", 0, 3)
        );
        AtomicReference<Throwable> failure = new AtomicReference<>();
        AtomicReference<JsonObject> captured = new AtomicReference<>();
        Thread responder = new Thread(() -> {
            try {
                boolean answered = false;
                while (!answered && !Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    captured.compareAndSet(null, pending.deepCopy());
                    System.out.println("WS229_PENDING_JOINT " + pending);
                    JsonObject response = scalarResponse(pending, id);
                    JsonArray vector = new JsonArray();
                    vector.add(55);
                    vector.add(3);
                    response.add("numeric_choices", vector);
                    try {
                        fixture.controller.submit(response);
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        if (exc.getMessage() != null
                                && exc.getMessage().contains("STALE_DECISION")) {
                            continue;
                        }
                        throw exc;
                    }
                    answered = true;
                    Thread.sleep(5L);
                }
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        responder.setDaemon(true);
        responder.start();
        List<Integer> result = fixture.player.getMultiAmountWithIndividualConstraints(
                Outcome.Neutral, messages, 50, 60, MultiAmountType.DAMAGE, fixture.game
        );
        responder.interrupt();
        responder.join(30_000L);
        if (failure.get() != null) {
            throw new IllegalStateException("responder failed", failure.get());
        }
        assertEquals(List.of(55, 3), result);
        // The parked joint frame carried the full domain, not per-leg scalars.
        JsonObject frame = captured.get();
        assertTrue(frame != null && frame.getAsJsonObject("context").has("numeric_legs"));
        assertEquals(2, frame.getAsJsonObject("context").getAsJsonArray("numeric_legs").size());
    }

    // N-14 live: forged out-of-range scalar rejected, then feasible accepted.
    @Test
    void forgedScalarOutOfRangeRejectedLive() throws Exception {
        Fixture fixture = liveFixture();
        AtomicReference<Integer> result = new AtomicReference<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                result.set(fixture.player.announceX(0, 10, "choose X", fixture.game, null, false));
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        caller.setDaemon(true);
        caller.start();
        JsonObject pending = awaitPending(fixture);
        // Forged max+1.
        XmageFullGameDecisionController.DecisionException rejected = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forgedScalar(pending, 11)));
        assertTrue(rejected.getMessage().contains("out of range"));
        // Forged min-1.
        XmageFullGameDecisionController.DecisionException rejectedLow = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forgedScalar(pending, -1)));
        assertTrue(rejectedLow.getMessage().contains("out of range"));
        // Feasible interior answer accepted and consumed natively.
        fixture.controller.submit(forgedScalar(pending, 7));
        caller.join(30_000L);
        if (failure.get() != null) {
            throw new IllegalStateException("caller failed", failure.get());
        }
        assertEquals(7, result.get());
    }

    // N-16 live: forged joint violations rejected, then feasible accepted.
    @Test
    void forgedJointViolationsRejectedLive() throws Exception {
        Fixture fixture = liveFixture();
        List<MultiAmountMessage> messages = List.of(
                new MultiAmountMessage("damage to A", 1, 3),
                new MultiAmountMessage("damage to B", 1, 3)
        );
        AtomicReference<List<Integer>> result = new AtomicReference<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                result.set(fixture.player.getMultiAmountWithIndividualConstraints(
                        Outcome.Neutral, messages, 5, 6, MultiAmountType.DAMAGE, fixture.game));
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        caller.setDaemon(true);
        caller.start();
        JsonObject pending = awaitPending(fixture);
        // Leg outside its bounds.
        XmageFullGameDecisionController.DecisionException legOut = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forgedVector(pending, List.of(9, 1))));
        assertTrue(legOut.getMessage().contains("out of range"));
        // Wrong vector length.
        XmageFullGameDecisionController.DecisionException lengthOut = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forgedVector(pending, List.of(2))));
        assertTrue(lengthOut.getMessage().contains("differs from legs"));
        // Total outside the band (legs individually fine: 1+1=2 not in 5..6).
        XmageFullGameDecisionController.DecisionException totalOut = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forgedVector(pending, List.of(1, 1))));
        assertTrue(totalOut.getMessage().contains("outside"));
        // Feasible joint answer accepted and consumed natively.
        fixture.controller.submit(forgedVector(pending, List.of(3, 3)));
        caller.join(30_000L);
        if (failure.get() != null) {
            throw new IllegalStateException("caller failed", failure.get());
        }
        assertEquals(List.of(3, 3), result.get());
    }

    // N-22 transport lane: scalar number where no bounds were authorized.
    @Test
    void scalarNumberWithoutAuthorizedBoundsRejectedAtTransport() throws Exception {
        Fixture fixture = liveFixture();
        AtomicReference<Boolean> result = new AtomicReference<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                result.set(fixture.player.chooseMulligan(fixture.game));
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        caller.setDaemon(true);
        caller.start();
        JsonObject pending = awaitPending(fixture);
        // The mulligan frame authorizes no numeric bounds.
        assertTrue(!pending.getAsJsonObject("context").has("numeric_min"));
        String keepId = null;
        for (int index = 0; index < pending.getAsJsonArray("legal_options").size(); index++) {
            JsonObject option = pending.getAsJsonArray("legal_options").get(index).getAsJsonObject();
            if ("keep".equals(option.get("option_type").getAsString())) {
                keepId = option.get("option_id").getAsString();
            }
        }
        assertTrue(keepId != null);
        // A lawful selection plus a schema-confused number must still fail
        // closed on the number (count/option checks pass; numeric check bites).
        JsonObject forged = scalarResponse(pending, pending.get("decision_id").getAsString());
        JsonArray forgedSelected = new JsonArray();
        forgedSelected.add(keepId);
        forged.add("selected_option_ids", forgedSelected);
        forged.addProperty("numeric_choice", 3);
        XmageFullGameDecisionController.DecisionException rejected = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forged));
        assertTrue(rejected.getMessage().contains("not authorized by decision schema"));
        // The lawful keep answer still settles the parked frame.
        JsonObject lawful = scalarResponse(pending, pending.get("decision_id").getAsString());
        JsonArray selected = new JsonArray();
        selected.add(keepId);
        lawful.add("selected_option_ids", selected);
        fixture.controller.submit(lawful);
        caller.join(30_000L);
        if (failure.get() != null) {
            throw new IllegalStateException("caller failed", failure.get());
        }
        assertEquals(false, result.get());
        assertNull(fixture.controller.terminalFailure());
    }

    // N-22 projection lane: numeric_choice where no bounds were authorized.
    @Test
    void scalarNumberWithoutAuthorizedBoundsRejectedAtProjection() {
        JsonObject pending = optionPending("priority");
        JsonObject proposal = baseProposal(pending, "priority");
        proposal.getAsJsonObject("choices").addProperty("numeric_choice", 3);
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal));
        assertTrue(failure.getMessage().contains("not authorized by decision schema"));
    }

    // N-16 projection lane: joint vector violations.
    @Test
    void jointVectorViolationsRejectedAtProjection() {
        JsonObject pending = jointPending();
        // Leg out of range.
        assertRejectsJoint(pending, "[9,1]", "out of range");
        // Wrong length.
        assertRejectsJoint(pending, "[2]", "differs from legs");
        // Total out of band.
        assertRejectsJoint(pending, "[1,1]", "outside");
        // Non-integer element.
        JsonObject proposal = baseJointProposal(pending);
        JsonArray bad = new JsonArray();
        bad.add("two");
        bad.add(1);
        proposal.getAsJsonObject("choices").add("numeric_choices", bad);
        XmageFullGameActionProjection.ProjectionException malformed = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal));
        assertTrue(malformed.getMessage().contains("non-integer element"));
        // Missing vector on a joint frame.
        JsonObject missing = baseJointProposal(pending);
        XmageFullGameActionProjection.ProjectionException absent = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, missing));
        assertTrue(absent.getMessage().contains("joint numeric choices required"));
        // Scalar confusion on a joint frame.
        JsonObject confused = baseJointProposal(pending);
        confused.getAsJsonObject("choices").addProperty("numeric_choice", 2);
        XmageFullGameActionProjection.ProjectionException confusion = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, confused));
        assertTrue(confusion.getMessage().contains("mutually exclusive")
                || confusion.getMessage().contains("not authorized")
                || confusion.getMessage().contains("required"));
        // Feasible vector accepted with exact passthrough.
        JsonObject ok = baseJointProposal(pending);
        JsonArray vector = new JsonArray();
        vector.add(3);
        vector.add(3);
        ok.getAsJsonObject("choices").add("numeric_choices", vector);
        JsonObject response = XmageFullGameActionProjection.toDecisionResponse(pending, ok);
        assertEquals(2, response.getAsJsonArray("numeric_choices").size());
        assertEquals(3, response.getAsJsonArray("numeric_choices").get(0).getAsInt());
        assertTrue(response.get("numeric_choice").isJsonNull());
    }

    // F-RULES-03: forced-move records are observable in the transcript.
    @Test
    void forcedMoveRecordedInTranscript() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        controller.recordForcedMove("choice", "Choose how to cast Blaze", "single castable ability: Blaze");
        boolean found = false;
        for (int index = 0; index < controller.transcript().size(); index++) {
            JsonObject event = controller.transcript().get(index).getAsJsonObject();
            if (event.has("event_type")
                    && "forced_move".equals(event.get("event_type").getAsString())
                    && event.getAsJsonObject("payload").get("detail").getAsString()
                            .contains("single castable ability")) {
                found = true;
            }
        }
        assertTrue(found, "forced_move record must be observable in the transcript");
        assertNull(controller.terminalFailure());
    }

    // Reversed scalar bounds fail closed before parking any decision.
    @Test
    void reversedScalarBoundsFailClosed() {
        Fixture fixture = liveFixture();
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.player.announceX(5, 0, "choose X", fixture.game, null, false));
        assertTrue(failure.getMessage().contains("BRIDGE_PROTOCOL_ERROR"));
    }

    private static void assertRejectsJoint(JsonObject pending, String vectorJson, String fragment) {
        JsonObject proposal = baseJointProposal(pending);
        JsonArray vector = new JsonArray();
        for (String part : vectorJson.substring(1, vectorJson.length() - 1).split(",")) {
            vector.add(Integer.parseInt(part.trim()));
        }
        proposal.getAsJsonObject("choices").add("numeric_choices", vector);
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal));
        assertTrue(failure.getMessage().contains(fragment),
                "expected '" + fragment + "' in: " + failure.getMessage());
    }

    private static JsonObject jointPending() {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "ws229-joint-1");
        pending.addProperty("actor_id", "actor-1");
        pending.addProperty("decision_class", "multi_amount");
        pending.addProperty("decision_offset", 9L);
        pending.addProperty("minimum_selections", 0);
        pending.addProperty("maximum_selections", 0);
        pending.add("legal_options", new JsonArray());
        JsonObject context = new JsonObject();
        JsonArray legs = new JsonArray();
        JsonObject first = new JsonObject();
        first.addProperty("min", 1);
        first.addProperty("max", 3);
        first.addProperty("prompt", "damage to A");
        legs.add(first);
        JsonObject second = new JsonObject();
        second.addProperty("min", 1);
        second.addProperty("max", 3);
        second.addProperty("prompt", "damage to B");
        legs.add(second);
        context.add("numeric_legs", legs);
        context.addProperty("numeric_total_min", 5);
        context.addProperty("numeric_total_max", 6);
        context.addProperty("outcome", "neutral");
        pending.add("context", context);
        return pending;
    }

    private static JsonObject baseJointProposal(JsonObject pending) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws229-joint");
        proposal.addProperty("actor_id", "actor-1");
        proposal.addProperty("legal_action_id", "ws229-joint-1:numeric");
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        return proposal;
    }

    private static JsonObject optionPending(String decisionClass) {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "ws229-opt-1");
        pending.addProperty("actor_id", "actor-1");
        pending.addProperty("decision_class", decisionClass);
        pending.addProperty("decision_offset", 3L);
        pending.addProperty("minimum_selections", 1);
        pending.addProperty("maximum_selections", 1);
        JsonArray options = new JsonArray();
        JsonObject option = new JsonObject();
        option.addProperty("option_id", "pass");
        option.addProperty("label", "Pass priority");
        option.addProperty("option_type", "pass_priority");
        option.add("metadata", new JsonObject());
        options.add(option);
        pending.add("legal_options", options);
        pending.add("context", new JsonObject());
        return pending;
    }

    private static JsonObject baseProposal(JsonObject pending, String decisionClass) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws229-opt");
        proposal.addProperty("actor_id", "actor-1");
        proposal.addProperty("legal_action_id", "ws229-opt-1:pass");
        proposal.addProperty("action_type",
                "priority".equals(decisionClass) ? "pass_priority" : "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        JsonArray selected = new JsonArray();
        selected.add("pass");
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        return proposal;
    }

    private static JsonObject scalarResponse(JsonObject pending, String id) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", id);
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        response.add("selected_option_ids", new JsonArray());
        response.add("ordering", new JsonArray());
        return response;
    }

    private static JsonObject forgedScalar(JsonObject pending, int value) {
        JsonObject response = scalarResponse(pending, pending.get("decision_id").getAsString());
        response.addProperty("numeric_choice", value);
        return response;
    }

    private static JsonObject forgedVector(JsonObject pending, List<Integer> values) {
        JsonObject response = scalarResponse(pending, pending.get("decision_id").getAsString());
        JsonArray vector = new JsonArray();
        values.forEach(vector::add);
        response.add("numeric_choices", vector);
        return response;
    }

    private static JsonObject awaitPending(Fixture fixture) throws InterruptedException {
        for (int attempt = 0; attempt < 2000; attempt++) {
            JsonObject pending = fixture.controller.pendingDecision();
            if (pending != null) {
                return pending;
            }
            Thread.sleep(5L);
        }
        throw new IllegalStateException("no pending decision parked");
    }

    private static Fixture liveFixture() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws229-numeric", RangeOfInfluence.ALL, controller
        );
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                40,
                7
        );
        game.setRulesSeed(4242L);
        game.addPlayer(player, new Deck());
        return new Fixture(game, controller, player);
    }

    private record Fixture(
            Game game,
            XmageFullGameDecisionController controller,
            XmageFullGamePlayer player
    ) {
    }
}
