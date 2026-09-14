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
 * WS213 combat damage assignment through the authoritative native
 * multi_amount seam (WS206 engine path): sequential per-message numeric
 * decisions with propagated feasibility bounds, exact range validation, and
 * fail-closed infeasible distributions. No Damage Assignment Order semantics:
 * current CR 510 distributes freely.
 */
class XmageFullGameCombatDamageTest {

    @Test
    void multiAmountGreedyMinimumStaysFeasible() throws Exception {
        Fixture fixture = liveFixture();
        List<MultiAmountMessage> messages = List.of(
                new MultiAmountMessage("damage to A", 0, 3),
                new MultiAmountMessage("damage to B", 0, 3),
                new MultiAmountMessage("damage to C", 0, 3)
        );
        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        Thread responder = answerMinimums(fixture, responderFailure);
        List<Integer> result = fixture.player.getMultiAmountWithIndividualConstraints(
                Outcome.Neutral, messages, 4, 6, MultiAmountType.MANA, fixture.game
        );
        responder.interrupt();
        responder.join(30_000L);
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }
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
                java.util.Set<String> answeredIds = new java.util.HashSet<>();
                boolean rejectedOnce = false;
                while (!Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    if (answeredIds.contains(id)) {
                        Thread.sleep(5L);
                        continue;
                    }
                    JsonObject context = pending.getAsJsonObject("context");
                    int min = context.get("numeric_min").getAsInt();
                    int max = context.get("numeric_max").getAsInt();
                    JsonObject response = new JsonObject();
                    response.addProperty("decision_id", id);
                    response.addProperty(
                            "actor_id", pending.get("actor_id").getAsString());
                    response.add("selected_option_ids", new JsonArray());
                    response.add("ordering", new JsonArray());
                    boolean spoilAttempt = !rejectedOnce;
                    response.addProperty(
                            "numeric_choice", spoilAttempt ? max + 1 : min);
                    try {
                        fixture.controller.submit(response);
                        answeredIds.add(id);
                        if (spoilAttempt) {
                            firstRejection.set("NO_REJECTION");
                            rejectedOnce = true;
                        }
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        if (!rejectedOnce && exc.getMessage() != null
                                && exc.getMessage().contains("out of range")) {
                            // Expected rejection of the over-maximum spoil;
                            // retry the same decision with the minimum.
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
                "over-maximum numeric must be rejected, observed: " + firstRejection.get());
        int total = result.stream().mapToInt(Integer::intValue).sum();
        assertTrue(total >= 2 && total <= 6);
    }

    @Test
    void multiAmountInfeasibleBoundsFailClosed() {
        Fixture fixture = liveFixture();
        // Minimum sum (6) exceeds the allowed total (5): no legal distribution
        // exists, so the seam must fail closed before parking any decision.
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
        assertTrue(failure.getMessage().contains("numeric bounds reversed"));
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

    private static Thread answerMinimums(
            Fixture fixture, AtomicReference<Throwable> failure) {
        Thread responder = new Thread(() -> {
            try {
                java.util.Set<String> answeredIds = new java.util.HashSet<>();
                int answered = 0;
                while (answered < 16 && !Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String id = pending.get("decision_id").getAsString();
                    if (answeredIds.contains(id)) {
                        Thread.sleep(5L);
                        continue;
                    }
                    JsonObject context = pending.getAsJsonObject("context");
                    int min = context.get("numeric_min").getAsInt();
                    JsonObject response = new JsonObject();
                    response.addProperty("decision_id", id);
                    response.addProperty(
                            "actor_id", pending.get("actor_id").getAsString());
                    response.add("selected_option_ids", new JsonArray());
                    response.add("ordering", new JsonArray());
                    response.addProperty("numeric_choice", min);
                    try {
                        fixture.controller.submit(response);
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        if (exc.getMessage() != null
                                && exc.getMessage().contains("STALE_DECISION")) {
                            continue;
                        }
                        throw exc;
                    }
                    answeredIds.add(id);
                    answered++;
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
