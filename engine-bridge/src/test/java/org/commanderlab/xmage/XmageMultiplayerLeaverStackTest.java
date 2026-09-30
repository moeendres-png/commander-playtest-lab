package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-39: a player who leaves while holding priority, with actual cards at 4P
 * and 5P on the full-game lane.
 *
 * <p>On P1's turn P2 casts Lightning Bolt ("Lightning Bolt deals 3 damage to
 * any target.") at P3, keeps priority with a second Lightning Bolt castable,
 * and concedes. CR 800.4a: P2's objects leave the game and its spell on the
 * stack ceases to exist, so P3 takes no damage, and a player who left takes
 * no actions.</p>
 *
 * <p>P2's unanswered priority frame is re-issued with only the pass option.
 * Before the fix it still offered "Cast Lightning Bolt", which the engine no
 * longer executes, so picking it failed the lane with
 * {@code XMAGE_ACTION_EXECUTION_FAILED}.</p>
 *
 * <p>Mid-cast: P2 concedes while its own Bolt's target or payment frame is
 * open. XMage's native concede signal retires that frame immediately; P2
 * never answers it. The engine then unwinds the cast and the remaining
 * players continue.</p>
 */
class XmageMultiplayerLeaverStackTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aPlayerWhoLeftWhileHoldingPriorityIsOfferedNoAction(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P2", "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P2", "Lightning Bolt", 1, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 3, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("leaver-stack-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String p2 = s.seats.get("P2").getId().toString();
        boolean cast = false;
        for (int i = 0; i < 40; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            if (cast && "P2".equals(actor) && "priority".equals(cls)) {
                assertEquals(1, game.getStack().size(), "control: P2's Bolt is on the stack");
                assertTrue(s.labels().contains("Lightning Bolt — Cast Lightning Bolt"),
                        "control: P2 could cast its second Bolt");
                concedeAndCheck(s, game, p2);
                return;
            }
            switch (cls) {
                case "priority" -> s.submit(!cast && "P2".equals(actor)
                        ? s.action("activate_ability", "Cast Lightning Bolt")
                        : s.action("pass_priority", "Pass"));
                case "target" -> {
                    s.submit(s.action("choose_targets", "Seat 3"));
                    cast = true;
                }
                case "mana_payment" -> s.payWith("Mountain");
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("P2 never held priority over its Bolt");
    }

    private static void concedeAndCheck(XmageMultiplayerScenario s, Game game, String p2) {
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "p2-concede");
        concede.addProperty("actor_id", p2);
        concede.addProperty("player_id", p2);
        JsonObject result = s.session.submitConcede(concede);
        assertFalse(s.seats.get("P2").isInGame(), "P2 left the game");
        assertTrue(game.getStack().isEmpty(), "P2's Bolt ceased to exist (800.4a)");
        assertTrue(result.get("failure").isJsonNull(), "the lane goes on: " + result.get("failure"));

        JsonObject frame = result.getAsJsonObject("decision");
        assertEquals(p2, frame.get("actor_id").getAsString(), "P2 still answers its own frame");
        assertEquals("priority", frame.get("decision_class").getAsString());
        JsonArray options = frame.getAsJsonArray("legal_options");
        assertEquals(1, options.size(), "only the pass option remains: " + options);
        assertEquals("pass_priority", options.get(0).getAsJsonObject().get("option_type").getAsString());
        assertTrue(frame.getAsJsonObject("context").get("actor_left_game").getAsBoolean());

        s.submit(s.action("pass_priority", "Pass"));
        for (int i = 0; i < 2 * s.seats.size(); i++) {
            JsonObject next = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            assertFalse(p2.equals(next.get("actor_id").getAsString()), "P2 is never asked again");
            s.submit(s.action("pass_priority", "Pass"));
        }
        assertEquals(40, s.seats.get("P3").getLife(), "P3 took no damage from the departed Bolt");
    }

    @ParameterizedTest(name = "{0} players, concede at {1}")
    @CsvSource({"4,target", "4,mana_payment", "5,target", "5,mana_payment"})
    void aCastInProgressUnwindsWhenItsCasterLeaves(int playerCount, String concedeAt)
            throws Exception {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P2", "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 1, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "midcast-" + concedeAt + "-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String p2 = s.seats.get("P2").getId().toString();
        boolean conceded = false;
        int afterLeave = 0;
        for (int i = 0; i < 60 && afterLeave < 2 * playerCount; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            if (!conceded && "P2".equals(actor) && concedeAt.equals(cls)) {
                JsonObject before = s.session.pendingDecisionPayload().getAsJsonObject("decision");
                String staleDecisionId = before.get("decision_id").getAsString();
                int p2Seat = s.session.seatOrder().get(p2);
                int transcriptBefore = controller(s).transcript().size();

                JsonObject concede = new JsonObject();
                concede.addProperty("proposal_id", "p2-concede-" + concedeAt);
                concede.addProperty("actor_id", p2);
                concede.addProperty("player_id", p2);
                JsonObject result = s.session.submitConcede(concede);
                assertTrue(result.get("failure").isJsonNull());
                assertFalse(s.seats.get("P2").isInGame(), "P2 left the game");
                assertFalse(result.get("decision").isJsonNull(),
                        "remaining players must receive the next engine decision");
                JsonObject next = result.getAsJsonObject("decision");
                assertFalse(staleDecisionId.equals(next.get("decision_id").getAsString()),
                        "the pre-concession frame was retired, not answered");
                assertFalse(p2.equals(next.get("actor_id").getAsString()),
                        "P2 receives no decision after leaving");

                // The retirement must be an observable engine cancellation, and it must never be
                // represented as an accepted pilot response to the retired frame. Checking only
                // that this test does not submit is not sufficient: a bridge that fabricated or
                // defaulted an answer would record engine_decision_cancelled-less acceptance and
                // still leave every assertion above satisfied.
                int cancellations = 0;
                JsonArray transcript = controller(s).transcript();
                for (int index = transcriptBefore; index < transcript.size(); index++) {
                    JsonObject event = transcript.get(index).getAsJsonObject();
                    if ("engine_decision_cancelled".equals(text(event, "event_type"))) {
                        JsonObject payload = event.getAsJsonObject("payload");
                        if (staleDecisionId.equals(text(payload, "decision_id"))) {
                            cancellations++;
                            assertEquals(concedeAt, text(payload, "decision_class"),
                                    "the retired frame is the one P2 was actually asked for");
                            assertEquals("native_player_concede_signal", text(payload, "reason"),
                                    "the retirement came from the engine signal");
                            assertEquals(p2Seat, payload.get("actor_seat").getAsInt(),
                                    "the retired frame belonged to the conceding seat");
                        }
                    }
                    if ("decision_accepted".equals(text(event, "kind"))
                            && event.has("actor_seat")
                            && event.get("actor_seat").getAsInt() == p2Seat
                            && concedeAt.equals(text(event, "decision_class"))) {
                        fail("a decision_accepted must not represent a response to the retired "
                                + concedeAt + " frame of the departed player");
                    }
                }
                assertEquals(1, cancellations,
                        "the native concede cancellation is recorded exactly once");

                conceded = true;
                continue; // critically: no submit() for the stale target/payment frame
            } else if (conceded && !"P2".equals(actor)) {
                afterLeave++;
            }
            switch (cls) {
                case "priority" -> s.submit("P2".equals(actor) && !conceded
                        ? s.action("activate_ability", "Cast Lightning Bolt") : s.action("pass_priority", "Pass"));
                case "target" -> s.submit(s.action("choose_targets", "Seat 3"));
                case "mana_payment" -> s.submit(s.action("pay_cost", "Mountain"));
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
            assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                    "the lane goes on after the native concede cancellation");
            if (conceded && afterLeave > 0) {
                assertFalse(p2.equals(s.session.pendingDecisionPayload().getAsJsonObject("decision")
                        .get("actor_id").getAsString()), "P2 is never asked again");
            }
        }
        assertTrue(conceded, "control: P2 reached its " + concedeAt + " frame");
        assertTrue(game.getStack().isEmpty(), "the departed Bolt never reached the stack for good");
        assertEquals(40, s.seats.get("P3").getLife(), "P3 took no damage from the departed caster");
    }

    /** String value of a key, or empty when absent/null. Keeps transcript scans readable. */
    private static String text(JsonObject object, String key) {
        return object.has(key) && !object.get(key).isJsonNull() ? object.get(key).getAsString() : "";
    }

    private static XmageFullGameDecisionController controller(XmageMultiplayerScenario scenario)
            throws Exception {
        return field(scenario.session, "controller", XmageFullGameDecisionController.class);
    }

    private static <T> T field(Object target, String name, Class<T> type) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        Object value = field.get(target);
        if (!type.isInstance(value)) {
            throw new IllegalStateException("field " + name + " is not a " + type);
        }
        return type.cast(value);
    }
}
