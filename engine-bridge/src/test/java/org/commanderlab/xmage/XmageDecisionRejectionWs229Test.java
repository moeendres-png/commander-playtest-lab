package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.cards.decks.Deck;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS229 S6 negative matrix, transport lane (N-01..N-06, N-09, N-11..N-13,
 * N-17..N-21): forged submissions against REAL parked controller frames
 * for every non-numeric decision class. Each invalid submission is
 * constructed FORGED (never pilot-generated) and must fail closed with
 * the exact protocol error family; nothing falls back.
 *
 * <p>Frames park through the real {@code request()} transport (reached via
 * the same reflective seam the hidden-information tests use) with
 * engine-shaped bytes, plus one live-callback parking (N-09 mulligan).
 * Option offering stays engine-owned in production; these rows prove the
 * transport rejects forgeries per class.</p>
 */
class XmageDecisionRejectionWs229Test {

    // N-01: priority + unknown option id.
    @Test
    void priorityUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "priority", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("not-offered"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-02: stale decision id (replayed foreign id).
    @Test
    void staleDecisionIdRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "priority", 1, 1);
        JsonObject forged = forgedSelection(parked.pending(), List.of("t-1"));
        forged.addProperty("decision_id", "deadbeef-stale");
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forged));
        assertTrue(failure.getMessage().contains("STALE_DECISION"));
        parked.settle(List.of("t-1"));
    }

    // N-03: wrong actor_id.
    @Test
    void wrongActorRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "priority", 1, 1);
        JsonObject forged = forgedSelection(parked.pending(), List.of("t-1"));
        forged.addProperty("actor_id", "intruder");
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forged));
        assertTrue(failure.getMessage().contains("wrong actor"));
        parked.settle(List.of("t-1"));
    }

    // N-04: target + unknown option id.
    @Test
    void targetUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "target", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-target"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-05: selection count above max / below min.
    @Test
    void targetCountViolationsRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked over = park(fixture, "target", 1, 1);
        XmageFullGameDecisionController.DecisionException tooMany = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(over.pending(), List.of("t-1", "t-2"))));
        assertTrue(tooMany.getMessage().contains("expected 1..1"));
        over.settle(List.of("t-1"));
        Fixture second = liveFixture();
        Parked under = park(second, "target", 1, 2);
        XmageFullGameDecisionController.DecisionException tooFew = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> second.controller.submit(forgedSelection(under.pending(), List.of())));
        assertTrue(tooFew.getMessage().contains("expected 1..2"));
        under.settle(List.of("t-1"));
    }

    // N-06: choose_object + unknown option id.
    @Test
    void chooseObjectUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "choose_object", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-object"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-09: mulligan + unknown option id, live-parked via the real callback.
    @Test
    void mulliganUnknownOptionRejectedLive() throws Exception {
        Fixture fixture = liveFixture();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                fixture.player.chooseMulligan(fixture.game);
            } catch (Throwable exc) {
                callerFailure.compareAndSet(null, exc);
            }
        });
        caller.setDaemon(true);
        caller.start();
        JsonObject pending = awaitPending(fixture);
        JsonObject forged = forgedSelection(pending, List.of("third-option"));
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(forged));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        // Lawful keep answer settles the live frame; the callback returns.
        String keepId = keepOptionId(pending);
        JsonObject lawful = forgedSelection(pending, List.of(keepId));
        fixture.controller.submit(lawful);
        caller.join(30_000L);
        if (callerFailure.get() != null) {
            throw new IllegalStateException("caller failed", callerFailure.get());
        }
        assertNull(fixture.controller.terminalFailure());
    }

    // N-11: choice (incl cast_ability domain) + unknown option id.
    @Test
    void choiceUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "choice", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-choice"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-12: pile + unknown pile option.
    @Test
    void pileUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "pile", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("pile-c"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-13: mana_payment + unknown mana option.
    @Test
    void manaPaymentUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "mana_payment", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-mana"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-17: replacement_effect + unknown option.
    @Test
    void replacementEffectUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "replacement_effect", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-effect"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-18: trigger_order + unknown trigger option.
    @Test
    void triggerOrderUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "trigger_order", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-trigger"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-19: mode + unknown mode id.
    @Test
    void modeUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "mode", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-mode"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-20: declare_attacker + unknown attack option.
    @Test
    void declareAttackerUnknownOptionRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "declare_attacker", 1, 1);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-attack"))));
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-21: declare_blocker duplicate + unknown block option.
    @Test
    void declareBlockerDuplicateAndUnknownRejected() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = park(fixture, "declare_blocker", 0, 2);
        XmageFullGameDecisionController.DecisionException duplicate = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("t-1", "t-1"))));
        assertTrue(duplicate.getMessage().contains("duplicate option id"));
        XmageFullGameDecisionController.DecisionException unknown = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> fixture.controller.submit(
                        forgedSelection(parked.pending(), List.of("ghost-block"))));
        assertTrue(unknown.getMessage().contains("ILLEGAL_ACTION"));
        parked.settle(List.of("t-1"));
    }

    // N-07/N-08 live variants: target_amount-shaped frame, missing and
    // out-of-range companion numbers.
    @Test
    void targetAmountCompanionViolationsRejectedLive() throws Exception {
        Fixture fixture = liveFixture();
        Parked parked = parkTargetAmount(fixture);
        // Missing companion passes transport structurally and fails closed
        // at the player requireNumericChoice gate (pinned by
        // XmageFullGamePlayerBoundaryTest
        // .targetAmountMissingNumericChoiceFailsClosedInsteadOfDefaultingToOne):
        // the transport never defaults it to one.
        XmageFullGamePlayer probe = new XmageFullGamePlayer(
                "ws229-probe", RangeOfInfluence.ALL, new XmageFullGameDecisionController());
        XmageFullGameDecisionController.DecisionResponse absent =
                new XmageFullGameDecisionController.DecisionResponse(
                        "decision", "actor", List.of("t-1"), List.of(), null, null);
        XmageFullGameDecisionController.DecisionException missing = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> probe.requireNumericChoice(absent, "target_amount"));
        assertTrue(missing.getMessage().contains("numeric choice required for target_amount"));
        // Out-of-range companion (remaining+1, plus 0 and negative: the
        // same inclusive-range predicate rejects all three).
        for (int forged : new int[]{99, 0, -1}) {
            JsonObject attempt = forgedSelection(parked.pending(), List.of("t-1"));
            attempt.addProperty("numeric_choice", forged);
            XmageFullGameDecisionController.DecisionException over = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> fixture.controller.submit(attempt));
            assertTrue(over.getMessage().contains("out of range"),
                    "value " + forged + " must be out of range");
        }
        parked.settleNumeric(List.of("t-1"), 2);
    }

    private static Parked parkTargetAmount(Fixture fixture) throws Exception {
        JsonObject context = new JsonObject();
        context.addProperty("numeric_min", 1);
        context.addProperty("numeric_max", 3);
        context.addProperty("outcome", "neutral");
        return parkWith(fixture, "target_amount", 1, 1, context);
    }

    private static Parked park(Fixture fixture, String decisionClass, int min, int max)
            throws Exception {
        JsonObject context = new JsonObject();
        context.addProperty("outcome", "neutral");
        return parkWith(fixture, decisionClass, min, max, context);
    }

    private static Parked parkWith(
            Fixture fixture, String decisionClass, int min, int max, JsonObject context)
            throws Exception {
        JsonArray options = new JsonArray();
        for (String id : new String[]{"t-1", "t-2"}) {
            JsonObject option = new JsonObject();
            option.addProperty("option_id", id);
            option.addProperty("label", "probe " + id);
            option.addProperty("option_type", decisionClass);
            option.add("metadata", new JsonObject());
            options.add(option);
        }
        Method request = XmageFullGameDecisionController.class.getDeclaredMethod(
                "request",
                Game.class,
                mage.players.Player.class,
                String.class,
                String.class,
                int.class,
                int.class,
                JsonArray.class,
                JsonObject.class,
                JsonObject.class);
        request.setAccessible(true);
        AtomicReference<Object> response = new AtomicReference<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread parker = new Thread(() -> {
            try {
                response.set(request.invoke(
                        fixture.controller, fixture.game, fixture.player, decisionClass,
                        "ws229 rejection probe", min, max, options, context, null));
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        parker.setDaemon(true);
        parker.start();
        JsonObject pending = awaitPending(fixture);
        return new Parked(fixture, pending, parker, response, failure);
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

    private static JsonObject forgedSelection(JsonObject pending, List<String> selected) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        JsonArray ids = new JsonArray();
        selected.forEach(ids::add);
        response.add("selected_option_ids", ids);
        response.add("ordering", new JsonArray());
        return response;
    }

    private static String keepOptionId(JsonObject pending) {
        for (int index = 0; index < pending.getAsJsonArray("legal_options").size(); index++) {
            JsonObject option = pending.getAsJsonArray("legal_options")
                    .get(index).getAsJsonObject();
            if ("keep".equals(option.get("option_type").getAsString())) {
                return option.get("option_id").getAsString();
            }
        }
        throw new IllegalStateException("keep option absent");
    }

    private static Fixture liveFixture() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws229-reject", RangeOfInfluence.ALL, controller
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

    private record Parked(
            Fixture fixture,
            JsonObject pending,
            Thread parker,
            AtomicReference<Object> response,
            AtomicReference<Throwable> failure
    ) {
        void settle(List<String> selected) throws Exception {
            fixture.controller.submit(forgedSelection(pending, selected));
            parker.join(30_000L);
            if (failure.get() != null) {
                throw new IllegalStateException("parker failed", failure.get());
            }
            assertNull(fixture.controller.terminalFailure());
        }

        void settleNumeric(List<String> selected, int numeric) throws Exception {
            JsonObject lawful = forgedSelection(pending, selected);
            lawful.addProperty("numeric_choice", numeric);
            fixture.controller.submit(lawful);
            parker.join(30_000L);
            if (failure.get() != null) {
                throw new IllegalStateException("parker failed", failure.get());
            }
            assertNull(fixture.controller.terminalFailure());
        }
    }
}
