package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.constants.MultiAmountType;
import mage.constants.MultiplayerAttackOption;
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
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS229 joint multi_amount seam: ONE joint frame carries the full legs +
 * totals domain (F-RULES-02b closed); the pilot-facing decision is a single
 * vector validated by the exact isGoodValues projection (length, per-leg
 * range, total band). Sequential per-leg frames are gone. No Damage
 * Assignment Order semantics: current CR 510 distributes freely.
 */
class XmageFullGameCombatDamageTest {

    @Test
    void multiAmountJointMinimumsRepairedToFeasibleBand() throws Exception {
        Fixture fixture = liveFixture();
        List<MultiAmountMessage> messages = List.of(
                new MultiAmountMessage("damage to A", 0, 3),
                new MultiAmountMessage("damage to B", 0, 3),
                new MultiAmountMessage("damage to C", 0, 3)
        );
        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        AtomicReference<Integer> framesAnswered = new AtomicReference<>(0);
        Thread responder = answerJointMinimums(fixture, responderFailure, framesAnswered);
        List<Integer> result = fixture.player.getMultiAmountWithIndividualConstraints(
                Outcome.Neutral, messages, 4, 6, MultiAmountType.MANA, fixture.game
        );
        responder.interrupt();
        responder.join(30_000L);
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }
        // Exactly one joint frame served the whole distribution.
        assertEquals(1, framesAnswered.get());
        assertEquals(3, result.size());
        int total = result.stream().mapToInt(Integer::intValue).sum();
        assertTrue(total >= 4 && total <= 6, "total " + total + " must stay feasible");
        for (int index = 0; index < messages.size(); index++) {
            int chosen = result.get(index);
            assertTrue(chosen >= messages.get(index).min && chosen <= messages.get(index).max);
        }
    }

    @Test
    void multiAmountOutOfRangeRejectedThenFeasibleAnswerAccepted() throws Exception {
        Fixture fixture = liveFixture();
        List<MultiAmountMessage> messages = List.of(
                new MultiAmountMessage("damage to A", 1, 3),
                new MultiAmountMessage("damage to B", 1, 3)
        );
        AtomicReference<String> firstRejection = new AtomicReference<>();
        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        Thread responder = new Thread(() -> {
            try {
                boolean rejectedOnce = false;
                boolean answered = false;
                while (!answered && !Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    JsonObject context = pending.getAsJsonObject("context");
                    JsonArray legs = context.getAsJsonArray("numeric_legs");
                    JsonObject response = new JsonObject();
                    response.addProperty("decision_id", id);
                    response.addProperty(
                            "actor_id", pending.get("actor_id").getAsString());
                    response.add("selected_option_ids", new JsonArray());
                    response.add("ordering", new JsonArray());
                    JsonArray vector = new JsonArray();
                    boolean spoilAttempt = !rejectedOnce;
                    for (int index = 0; index < legs.size(); index++) {
                        JsonObject leg = legs.get(index).getAsJsonObject();
                        int legMin = leg.get("min").getAsInt();
                        int legMax = leg.get("max").getAsInt();
                        // Spoil the first leg over its maximum once; the
                        // retry answers per-leg minimums (feasible here).
                        vector.add(spoilAttempt && index == 0 ? legMax + 1 : legMin);
                    }
                    response.add("numeric_choices", vector);
                    try {
                        fixture.controller.submit(response);
                        answered = true;
                        if (spoilAttempt) {
                            firstRejection.set("NO_REJECTION");
                            rejectedOnce = true;
                        }
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        if (!rejectedOnce && exc.getMessage() != null
                                && exc.getMessage().contains("out of range")) {
                            // Expected rejection of the over-maximum spoil;
                            // retry the same joint frame with minimums.
                            firstRejection.set(exc.getMessage());
                            rejectedOnce = true;
                        } else if (exc.getMessage() != null
                                && exc.getMessage().contains("STALE_DECISION")) {
                            // Concurrent advance; re-read the current pending.
                            continue;
                        } else {
                            throw exc;
                        }
                    }
                }
            } catch (InterruptedException exc) {
                // Test-thread shutdown signal after the caller returned.
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                responderFailure.compareAndSet(null, exc);
            }
        });
        responder.setDaemon(true);
        responder.start();
        List<Integer> result = fixture.player.getMultiAmountWithIndividualConstraints(
                Outcome.Neutral, messages, 2, 6, MultiAmountType.MANA, fixture.game
        );
        responder.interrupt();
        responder.join(30_000L);
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }
        assertTrue(firstRejection.get() != null
                && firstRejection.get().contains("out of range"),
                "over-maximum joint leg must be rejected, observed: " + firstRejection.get());
        int total = result.stream().mapToInt(Integer::intValue).sum();
        assertTrue(total >= 2 && total <= 6);
    }

    @Test
    void multiAmountInfeasibleBoundsFailClosed() {
        Fixture fixture = liveFixture();
        // Minimum sum (6) exceeds the allowed total (5): no legal distribution
        // exists, so the joint seam must fail closed before parking any decision.
        List<MultiAmountMessage> messages = List.of(
                new MultiAmountMessage("damage to A", 3, 3),
                new MultiAmountMessage("damage to B", 3, 3)
        );
        XmageFullGameDecisionController.DecisionException failure;
        try {
            fixture.player.getMultiAmountWithIndividualConstraints(
                    Outcome.Neutral, messages, 5, 5, MultiAmountType.MANA, fixture.game
            );
            throw new IllegalStateException("expected infeasible distribution to fail");
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            failure = exc;
        }
        assertTrue(failure.getMessage().contains("infeasible"));
    }

    @Test
    void multiAmountProjectionEnforcesNumericRange() {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "ws213-multi-1");
        pending.addProperty("actor_id", "actor-1");
        pending.addProperty("decision_class", "multi_amount");
        pending.addProperty("decision_offset", 9L);
        pending.addProperty("minimum_selections", 0);
        pending.addProperty("maximum_selections", 0);
        pending.add("legal_options", new JsonArray());
        JsonObject context = new JsonObject();
        context.addProperty("numeric_min", 1);
        context.addProperty("numeric_max", 4);
        pending.add("context", context);

        JsonArray actions = XmageFullGameActionProjection.project(pending);
        assertEquals(1, actions.size());
        assertEquals("structural_decision",
                actions.get(0).getAsJsonObject().get("action_type").getAsString());

        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws213-multi");
        proposal.addProperty("actor_id", "actor-1");
        proposal.addProperty("legal_action_id", "ws213-multi-1:numeric");
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("numeric_choice", 9);
        proposal.add("choices", choices);
        try {
            XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
            throw new IllegalStateException("expected out-of-range numeric to fail");
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            assertTrue(exc.getMessage().contains("out of range"));
        }

        choices.addProperty("numeric_choice", 3);
        JsonObject response =
                XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
        assertEquals(3, response.get("numeric_choice").getAsInt());
    }

    private static Thread answerJointMinimums(
            Fixture fixture,
            AtomicReference<Throwable> failure,
            AtomicReference<Integer> framesAnswered) {
        Thread responder = new Thread(() -> {
            try {
                int answered = 0;
                while (answered < 1 && !Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    JsonObject context = pending.getAsJsonObject("context");
                    JsonArray legs = context.getAsJsonArray("numeric_legs");
                    int totalMin = context.get("numeric_total_min").getAsInt();
                    // Per-leg minimums repaired upward into the total band:
                    // the deterministic joint-minimum strategy.
                    List<Integer> values = new ArrayList<>();
                    int total = 0;
                    for (int index = 0; index < legs.size(); index++) {
                        int legMin = legs.get(index).getAsJsonObject().get("min").getAsInt();
                        values.add(legMin);
                        total += legMin;
                    }
                    for (int index = 0; total < totalMin; index++) {
                        int leg = index % values.size();
                        int legMax = legs.get(leg).getAsJsonObject().get("max").getAsInt();
                        if (values.get(leg) >= legMax) {
                            if (index > values.size() * 1000) {
                                throw new IllegalStateException("joint minimums cannot reach total band");
                            }
                            continue;
                        }
                        values.set(leg, values.get(leg) + 1);
                        total += 1;
                    }
                    JsonObject response = new JsonObject();
                    response.addProperty("decision_id", id);
                    response.addProperty(
                            "actor_id", pending.get("actor_id").getAsString());
                    response.add("selected_option_ids", new JsonArray());
                    response.add("ordering", new JsonArray());
                    JsonArray vector = new JsonArray();
                    values.forEach(vector::add);
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
                    answered++;
                    framesAnswered.set(answered);
                    Thread.sleep(5L);
                }
            } catch (InterruptedException exc) {
                // Test-thread shutdown signal after the caller returned.
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        responder.setDaemon(true);
        responder.start();
        return responder;
    }

    private static Fixture liveFixture() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws213-combat", RangeOfInfluence.ALL, controller
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
