package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.MageObject;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.constants.Zone;
import mage.cards.decks.Deck;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Two engine aborts the owner-collection coverage pods surfaced (#747).
 *
 * <p>1. ContinuousEffects.replaceEvent asks for a replacement-effect choice even
 * when its only applicable effect carries no source ability, so the map it
 * hands over is empty. There is nothing to choose; the bridge used to abort the
 * game with BRIDGE_PROTOCOL_ERROR.</p>
 *
 * <p>2. Fire Covenant divides X damage among any number of target creatures
 * (CR 601.2d: the whole amount is divided). The bridge offered every target
 * share in [1, remaining], so the pilot could give the last possible target
 * less than the rest; the leftover had no target and the engine refused the
 * cast, which the bridge reported as XMAGE_ACTION_EXECUTION_FAILED.</p>
 */
class XmageFullGameCoverageAbortTest {

    @Test
    void anEmptyReplacementChoiceIsTheOnlyEffectAndAsksNobody() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "issue747-replacement", RangeOfInfluence.ALL, controller
        );
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                40,
                7
        );
        game.addPlayer(player, new Deck());
        Map<String, String> effects = new LinkedHashMap<>();
        Map<String, MageObject> objects = new LinkedHashMap<>();
        assertEquals(0, player.chooseReplacementEffect(effects, objects, game));
        assertNull(controller.pendingDecision(), "no decision is handed to the pilot");
    }

    @Test
    void theLastPossibleTargetOfADivisionMustTakeTheRest() {
        int x = 3;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Fire Covenant", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Hill Giant", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "issue747-fire-covenant", 2, "P1", objects);
        Game game = s.session.restorationGame();
        XmageActualCardCorpusTest.Started started =
                new XmageActualCardCorpusTest.Started(s.session, s.seats, null);
        String giant = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> "Hill Giant".equals(p.getName()))
                .findFirst().orElseThrow().getId().toString();

        boolean divided = false;
        boolean cast = false;
        s.submit(s.action("activate_ability", "Cast Fire Covenant"));
        for (int i = 0; i < 80; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            if ("priority".equals(cls) && game.getStack().isEmpty() && cast) {
                break;
            }
            switch (cls) {
                case "announce_x", "numeric" -> {
                    cast = true;
                    XmageActualCardCorpusTest.submitNumeric(started, "issue747-x-" + i, x);
                }
                case "target_amount" -> {
                    cast = true;
                    JsonObject context = payload.getAsJsonObject("decision").getAsJsonObject("context");
                    int remaining = context.get("amount_remaining").getAsInt();
                    assertEquals(remaining, context.get("numeric_min").getAsInt(),
                            "the only target left must take the whole remaining amount");
                    assertEquals(remaining, context.get("numeric_max").getAsInt());
                    submitTargetAmount(s, "issue747-share-" + i, giant, remaining);
                    divided = true;
                }
                case "mana_payment" -> {
                    JsonObject pay = s.action("pay_cost", "Spend ");
                    if (pay == null) {
                        pay = s.action("pay_cost", "Swamp");
                    }
                    if (pay == null) {
                        pay = s.action("pay_cost", "Mountain");
                    }
                    assertNotNull(pay, "a land pays the cost: " + s.labels());
                    s.submit(pay);
                }
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels() + " " + s.prompt());
            }
        }
        assertTrue(divided, "the division was announced");
        assertEquals(40 - x, s.seats.get("P1").getLife(), "X life was paid");
        assertTrue(game.getBattlefield().getAllActivePermanents().stream()
                .noneMatch(p -> "Hill Giant".equals(p.getName())), "3 damage destroyed the 3/3");
    }

    @Test
    void aCardWithNoCastableAbilityIsNotCastAndNotAnAbort() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Wear // Tear", 0, Zone.HAND));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "issue747-wear-tear", 2, "P1", objects);
        Game game = s.session.restorationGame();
        mage.cards.Card card = game.getPlayer(s.seats.get("P1").getId()).getHand().getCards(game).stream()
                .filter(c -> "Wear // Tear".equals(c.getName()))
                .findFirst().orElseThrow();
        // No artifact and no enchantment: neither half has a legal target.
        assertTrue(mage.players.PlayerImpl.getCastableSpellAbilities(
                game, s.seats.get("P1").getId(), card, Zone.HAND, true).isEmpty());
        assertNull(s.seats.get("P1").chooseAbilityForCast(card, game, true),
                "nothing is castable, so nothing is cast");
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the game goes on");
    }

    @Test
    void anOverAnnouncedXSpellThePilotCancelsAtPaymentReturnsPriorityInsteadOfAborting() {
        // #815: Blue Sun's Zenith with X announced higher than the pilot can
        // pay. With the Islands spent the bridge offers only "Cancel mana
        // payment"; the pilot cancels, the engine reverses the cast (CR 601.2e)
        // and priority returns instead of XMAGE_ACTION_EXECUTION_FAILED.
        //
        // The cancel sets paymentCancelled, the first clause of the cast-failure
        // chain in XmageFullGamePlayer. A predicate for a payment that fails
        // without a pilot cancel (reversedOverAnnouncedX) was removed in #846:
        // no real-engine path reaches it.
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Blue Sun's Zenith", 0, Zone.HAND));
        // Three Islands: X=0 ({U}{U}{U}) is payable, X=1 ({1}{U}{U}{U}) is not.
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 2, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "issue815-zenith", 2, "P1", objects);
        boolean castAttempted = false;
        boolean reversed = false;
        for (int i = 0; i < 40; i++) {
            JsonObject pending = s.session.pendingDecisionPayload();
            if (!pending.get("failure").isJsonNull()) {
                fail("no failure expected, got: " + pending.get("failure"));
            }
            JsonObject decision = pending.getAsJsonObject("decision");
            if (decision == null || decision.isJsonNull()) {
                break;
            }
            String cls = decision.get("decision_class").getAsString();
            switch (cls) {
                case "priority" -> {
                    if (!castAttempted) {
                        JsonObject cast = s.action("activate_ability", "Cast Blue Sun's Zenith");
                        assertNotNull(cast, "zenith must be offered: " + s.labels());
                        s.submit(cast);
                        castAttempted = true;
                    } else {
                        // After the reversal, priority returns to the same player.
                        reversed = true;
                        s.submit(s.action("pass_priority", "Pass"));
                    }
                }
                case "announce_x" -> {
                    // Announce X=1, which the three Islands cannot pay. X is a
                    // structural numeric decision answered with numeric_choice.
                    JsonObject legal = s.session.legalActionsPayload();
                    JsonObject announce = legal.getAsJsonArray("actions").get(0).getAsJsonObject();
                    assertEquals("structural_decision", announce.get("action_type").getAsString());
                    JsonObject proposal = FullGameTestPilot.proposal(legal, announce);
                    proposal.getAsJsonObject("choices").addProperty("numeric_choice", 1);
                    s.session.submitAction(proposal);
                }
                case "target" -> {
                    // Target the opponent seat (a player).
                    JsonObject target = s.action("choose_targets", "Full Game Seat 2");
                    assertNotNull(target, "target must be offered: " + s.labels());
                    s.submit(target);
                }
                case "mana_payment" -> {
                    // Pay with all three Islands; the 4th mana is missing.
                    JsonObject pay = s.action("pay_cost", "Spend ");
                    if (pay == null) {
                        pay = s.action("pay_cost", "Island");
                    }
                    if (pay == null) {
                        // Every Island is spent and the 4th mana is still owed: the
                        // bridge offers only the cancel, so the pilot takes it.
                        pay = s.action("pay_cost", "Cancel mana payment");
                    }
                    assertNotNull(pay, "mana still owed and nothing to pay with: " + s.labels());
                    s.submit(pay);
                }
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels());
            }
            if (reversed) {
                break;
            }
        }
        assertTrue(castAttempted, "the cast was attempted");
        assertTrue(reversed, "priority returned after the reversal");
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the game goes on after an over-announced X");
    }

    /** One target by engine id plus its share, as one response. */
    private static void submitTargetAmount(XmageMultiplayerScenario s, String tag, String objectId, int amount) {
        JsonObject pending = s.session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = s.session.legalActionsPayload();
        String optionId = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            if (engine != null && engine.has("object_id") && objectId.equals(engine.get("object_id").getAsString())) {
                optionId = meta.get("option_id").getAsString();
            }
        }
        assertNotNull(optionId, "target must be engine-offered: " + objectId + " " + s.labels());
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + optionId);
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        choices.add("selected_option_ids", selected);
        choices.addProperty("numeric_choice", amount);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = s.session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }
}
