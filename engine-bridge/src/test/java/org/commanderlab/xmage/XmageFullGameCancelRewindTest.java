package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Predicate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 S3 and L3 (facts 8 and 9 of the ruling).
 *
 * <p>S3: a cast the pilot cancels during mana payment is reversed (CR 601.2,
 * illegal or abandoned actions are rewound), and the same player receives a new
 * priority frame in the same step. The lane must not pass priority for the player:
 * before #662 it called {@code pass(game)} here, which is the Lab choosing for the
 * player.</p>
 *
 * <p>The partial-payment cases compare the privileged state digest before the
 * proposal and after the cancel: any residue of the cancelled proposal (a tapped
 * land, mana in the pool, an object on the stack, a moved card) makes them differ.</p>
 *
 * <p>L3: a pending decision with no offered option and no numeric domain cannot
 * be answered through the generic API, so its projection fails closed instead of
 * reporting an empty, "complete" action list.</p>
 */
class XmageFullGameCancelRewindTest {

    @Test
    void cancelledCastIsReversedAndTheSamePlayerKeepsPriority() {
        XmageFullGameSession session = started("issue662-cancel-rewind", 6621L);
        String starter = seatPlayer(session, 0);

        // Declared path: play the land, then cast the commander and cancel its payment.
        answer(session, "priority", starter, label -> label.contains("Play Plains"), 40);
        answer(session, "priority", starter, label -> label.contains("Isamaru"), 10);
        JsonObject payment = session.legalActionsPayload();
        assertEquals("mana_payment", payment.get("decision_class").getAsString(),
                "casting the commander with an untapped Plains must ask for payment");
        assertEquals(starter, payment.get("actor_id").getAsString());

        Game game = session.restorationGame();
        int turn = game.getTurnNum();
        String step = game.getStep().getType().name();

        JsonObject cancel = find(payment, "cancel_mana_payment", null);
        session.submitAction(proposal(payment, cancel));

        JsonObject after = session.legalActionsPayload();
        assertEquals("priority", after.get("decision_class").getAsString(),
                "a cancelled cast must return a priority frame, not advance the game");
        assertEquals(starter, after.get("actor_id").getAsString(),
                "the same player keeps priority after the reversal");
        assertEquals(turn, game.getTurnNum());
        assertEquals(step, game.getStep().getType().name());
        assertFalse(game.getPlayer(java.util.UUID.fromString(starter)).isPassed(),
                "the lane must not pass priority for the player");
        assertTrue(game.getStack().isEmpty(), "the cancelled spell is not on the stack");
        Permanent plains = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> p.getName().equals("Plains"))
                .findFirst().orElse(null);
        assertNotNull(plains);
        assertFalse(plains.isTapped(), "the payment of the reversed cast is undone");
        assertTrue(labels(after).stream().anyMatch(l -> l.contains("Isamaru")),
                "the commander can be cast again: the reversal left it in the command zone");
    }

    /**
     * S3 with a partial payment: one of two mana is paid, then the cast is
     * cancelled. The whole cast, the paid mana included, is reversed: the
     * privileged state digest equals the one before the cast was proposed, and the
     * caster gets priority again. A lane that left the land tapped, the mana in the
     * pool or the spell on the stack fails the digest equality.
     */
    @Test
    void partiallyPaidCastIsReversedToThePreCastState() {
        assertCancelRewinds(new DecisionClassMatrixHarness.Scenario("s3-partial-cast", 66231L,
                List.of(DecisionClassMatrixHarness.Placed.hand("P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.Placed.battlefield("P1", "Forest"),
                        DecisionClassMatrixHarness.Placed.battlefield("P1", "Forest")),
                List.of(), "priority", "P1"), "Cast Grizzly Bears", List.of());
    }

    /**
     * S3 for an activated ability: target chosen, one of three generic mana paid,
     * then cancelled. The activation is reversed to the pre-activation state.
     */
    @Test
    void partiallyPaidActivationIsReversedToThePreActivationState() {
        assertCancelRewinds(new DecisionClassMatrixHarness.Scenario("s3-partial-activation", 66232L,
                List.of(DecisionClassMatrixHarness.Placed.battlefield("P1", "Rod of Ruin"),
                        DecisionClassMatrixHarness.Placed.battlefield("P1", "Mountain"),
                        DecisionClassMatrixHarness.Placed.battlefield("P1", "Mountain"),
                        DecisionClassMatrixHarness.Placed.battlefield("P1", "Mountain")),
                List.of(), "priority", "P1"), "Rod of Ruin", List.of("Full Game Seat 2"));
    }

    private static void assertCancelRewinds(DecisionClassMatrixHarness.Scenario scenario,
                                            String proposeLabel, List<String> targetLabels) {
        XmageRulesRngResultTape.keyForTests(new byte[32]);
        try {
            DecisionClassMatrixHarness.Live live = DecisionClassMatrixHarness.open(scenario);
            XmageFullGameSession session = live.session();
            JsonObject before = DecisionClassMatrixHarness.driveToTarget(live, scenario);
            String actor = before.get("actor_id").getAsString();
            String digest = session.privilegedStateDigest();
            String readback = XmageNativeStateRestoration.readback(session.restorationGame(), live.seats()).toString();

            JsonObject propose = DecisionClassMatrixHarness.actions(before).stream()
                    .filter(action -> label(action).contains(proposeLabel)).findFirst()
                    .orElseThrow(() -> new AssertionError("not offered: " + proposeLabel + " in " + labels(before)));
            session.submitAction(proposal(before, propose));
            for (String target : targetLabels) {
                JsonObject frame = session.legalActionsPayload();
                assertEquals("target", frame.get("decision_class").getAsString(), labels(frame).toString());
                JsonObject chosen = DecisionClassMatrixHarness.actions(frame).stream()
                        .filter(action -> label(action).equals(target)).findFirst().orElseThrow();
                session.submitAction(proposal(frame, chosen));
            }

            JsonObject payment = session.legalActionsPayload();
            assertEquals("mana_payment", payment.get("decision_class").getAsString(), labels(payment).toString());
            session.submitAction(proposal(payment, find(payment, "mana_ability", null)));
            JsonObject partial = session.legalActionsPayload();
            assertEquals("mana_payment", partial.get("decision_class").getAsString(),
                    "one mana paid, more is due: " + labels(partial));
            assertFalse(digest.equals(session.privilegedStateDigest()),
                    "the partial payment changed the game (a land is tapped): the control is not vacuous");

            session.submitAction(proposal(partial, find(partial, "cancel_mana_payment", null)));
            JsonObject after = session.legalActionsPayload();
            assertEquals("priority", after.get("decision_class").getAsString());
            assertEquals(actor, after.get("actor_id").getAsString(), "the same player keeps priority");
            assertEquals(digest, session.privilegedStateDigest(),
                    "the cancelled proposal, its partial payment included, is fully reversed");
            assertEquals(readback,
                    XmageNativeStateRestoration.readback(session.restorationGame(), live.seats()).toString());
            assertTrue(labels(after).stream().anyMatch(l -> l.contains(proposeLabel)),
                    "the reversed proposal is offered again");
        } finally {
            XmageRulesRngResultTape.keyForTests(null);
        }
    }

    @Test
    void decisionWithoutOptionsOrNumericDomainFailsClosed() {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", "d".repeat(64));
        pending.addProperty("actor_id", "actor");
        pending.addProperty("decision_class", "choice");
        pending.addProperty("decision_offset", 7L);
        pending.addProperty("minimum_selections", 0);
        pending.addProperty("maximum_selections", 1);
        pending.add("legal_options", new JsonArray());
        pending.add("context", new JsonObject());
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.project(pending));
        assertTrue(failure.getMessage().startsWith("UNPROJECTABLE_DECISION"), failure.getMessage());
        JsonObject next = XmageFullGameSession.nextActionsPayload(pending);
        assertEquals("projection_failed", next.get("next_actions_status").getAsString());
    }

    // ---- helpers ------------------------------------------------------------

    static XmageFullGameSession unstarted(String gameId, long seed) {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        List<String> main = new ArrayList<>();
        for (int i = 0; i < 99; i++) {
            main.add("Plains");
        }
        for (int seat = 0; seat < 2; seat++) {
            handles.add(importer.importCommanderDeck(
                    "issue662-" + seat, "0".repeat(64), main, List.of("Isamaru, Hound of Konda")
            ).deckHandle());
        }
        return new XmageFullGameSession(gameId, handles, 0, 40, seed, importer);
    }

    static XmageFullGameSession started(String gameId, long seed) {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        List<String> main = new ArrayList<>();
        for (int i = 0; i < 99; i++) {
            main.add("Plains");
        }
        for (int seat = 0; seat < 2; seat++) {
            handles.add(importer.importCommanderDeck(
                    "issue662-" + seat, "0".repeat(64), main, List.of("Isamaru, Hound of Konda")
            ).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(gameId, handles, 0, 40, seed, importer);
        session.start();
        // Declared pregame: seat 0 starts, everyone keeps.
        String seat0 = seatPlayer(session, 0);
        for (int step = 0; step < 8; step++) {
            JsonObject legal = session.legalActionsPayload();
            String cls = legal.get("decision_class").getAsString();
            if ("choose_object".equals(cls)) {
                session.submitAction(proposal(legal, find(legal, null, seat0)));
            } else if ("mulligan".equals(cls)) {
                JsonObject keep = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if ("keep".equals(action.getAsJsonObject("metadata").get("option_type").getAsString())) {
                        keep = action;
                    }
                }
                session.submitAction(proposal(legal, keep));
            } else {
                return session;
            }
        }
        return session;
    }

    static String seatPlayer(XmageFullGameSession session, int seat) {
        return session.pendingDecisionPayload().getAsJsonArray("outcomes").get(seat)
                .getAsJsonObject().get("player_id").getAsString();
    }

    /** Pass priority until the wanted option is offered to {@code actor}, then take it. */
    static void answer(XmageFullGameSession session, String cls, String actor,
                       Predicate<String> wanted, int budget) {
        for (int step = 0; step < budget; step++) {
            JsonObject legal = session.legalActionsPayload();
            assertEquals(cls, legal.get("decision_class").getAsString(), "unexpected frame " + labels(legal));
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                if (legal.get("actor_id").getAsString().equals(actor) && wanted.test(label(action))) {
                    session.submitAction(proposal(legal, action));
                    return;
                }
            }
            session.submitAction(proposal(legal, find(legal, "pass_priority", null)));
        }
        throw new AssertionError("wanted option never offered within " + budget + " frames");
    }

    static JsonObject find(JsonObject legal, String optionType, String optionId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (optionType != null && optionType.equals(metadata.get("option_type").getAsString())) {
                return action;
            }
            if (optionId != null && optionId.equals(metadata.get("option_id").getAsString())) {
                return action;
            }
        }
        throw new AssertionError("no offered action " + optionType + "/" + optionId + " in " + labels(legal));
    }

    static JsonObject proposal(JsonObject legal, JsonObject action) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "issue662-" + legal.get("decision_offset").getAsLong());
        proposal.addProperty("actor_id", action.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", legal.get("decision_id").getAsString());
        choices.addProperty("decision_offset", legal.get("decision_offset").getAsLong());
        proposal.add("choices", choices);
        return proposal;
    }

    static String label(JsonObject action) {
        JsonObject metadata = action.getAsJsonObject("metadata");
        return metadata.has("label") ? metadata.get("label").getAsString() : "";
    }

    static List<String> labels(JsonObject legal) {
        List<String> labels = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            labels.add(label(element.getAsJsonObject()));
        }
        return labels;
    }
}
