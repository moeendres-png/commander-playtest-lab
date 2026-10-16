package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.SpellAbility;
import mage.abilities.costs.Cost;
import mage.abilities.costs.common.PayLifeCost;
import mage.abilities.costs.common.PayVariableLifeCost;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * #747: two casts the engine itself reverses, which the bridge used to report
 * as XMAGE_ACTION_EXECUTION_FAILED and so ended owner-collection coverage games.
 *
 * <p>1. Fire Covenant (Oracle): "As an additional cost to cast this spell, pay X
 * life. Fire Covenant deals X damage divided as you choose among any number of
 * target creatures." X may be announced up to the caster's life total. A
 * painland used to pay the mana ("deals 1 damage to you") lowers the life total
 * below X before the life is paid; CR 119.4 forbids paying more life than you
 * have, the cost is not paid (CR 118.3), and {@code PlayerImpl.cast} restores
 * its bookmark (CR 601.2e).</p>
 *
 * <p>2. Resculpt (Oracle): "Exile target artifact or creature." When no target
 * is legal for the spell on the stack, {@code Targets.chooseTargets} skips the
 * target without asking and the cast is reversed before any choice; XMage's
 * playable check, which reads the card in hand, can still offer it (an
 * opponent's "creatures you control can't be the targets of blue or black
 * spells this turn").</p>
 */
class XmageFullGameEngineReversalTest {

    @Test
    void xLifeThatAPainlandMadeUnpayableIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Fire Covenant", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Sulfurous Springs", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Sulfurous Springs", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Sulfurous Springs", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Hill Giant", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "issue747-x-life-painland", 2, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");
        int life = p1.getLife();
        XmageActualCardCorpusTest.Started started =
                new XmageActualCardCorpusTest.Started(s.session, s.seats, null);

        boolean reachedPayment = false;
        s.submit(s.action("activate_ability", "Cast Fire Covenant"));
        for (int i = 0; i < 40; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(),
                    "the reversal must not end the game: " + payload.get("failure"));
            String cls = s.decisionClass();
            if ("priority".equals(cls)) {
                break;
            }
            switch (cls) {
                case "announce_x", "numeric" ->
                        // all of the caster's life: legal now, unpayable after one point of pain
                        XmageActualCardCorpusTest.submitNumeric(started, "issue747-x-" + i, life);
                case "target_amount" -> {
                    JsonObject context = payload.getAsJsonObject("decision").getAsJsonObject("context");
                    int remaining = context.get("amount_remaining").getAsInt();
                    s.session.submitAction(targetAmountAction(s, remaining));
                }
                case "mana_payment" -> {
                    reachedPayment = true;
                    String unpaid = payload.getAsJsonObject("decision").getAsJsonObject("context")
                            .get("unpaid_mana").getAsString();
                    // Pay {R} and {B} with the painful abilities, the generic {1}
                    // with whatever the pool holds.
                    String colour = unpaid.contains("{R}") ? "{R}" : unpaid.contains("{B}") ? "{B}" : null;
                    // Mana already in the pool is spent first.
                    JsonObject pain = s.action("pay_cost", "from pool");
                    for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
                        if (pain != null) {
                            break;
                        }
                        JsonObject a = e.getAsJsonObject();
                        String label = a.getAsJsonObject("metadata").get("label").getAsString();
                        if (label.contains("Sulfurous Springs") && label.contains("damage")
                                && (colour == null || label.contains("Add " + colour))) {
                            pain = a;
                        }
                    }
                    assertNotNull(pain, "a painful Sulfurous Springs ability is offered: " + s.labels());
                    s.submit(pain);
                }
                default -> fail("unexpected " + cls + " " + s.labels() + " " + s.prompt());
            }
        }
        assertTrue(reachedPayment, "the cast reached its mana payment");
        assertEquals("priority", s.decisionClass(), "the same player is asked again");
        assertEquals("P1", s.actor(), "P1 keeps priority");
        assertEquals(life, p1.getLife(), "the rewind returned the pain and paid no life");
        assertTrue(p1.getHand().getCards(game).stream().anyMatch(c -> "Fire Covenant".equals(c.getName())),
                "Fire Covenant is back in hand");
        assertTrue(game.getStack().isEmpty(), "nothing was left on the stack");
    }

    @Test
    void unpayableXLifeGuardsRejectEachBrokenFact() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue747-x-life-guards", 2, "P1",
                List.of(XmageMultiplayerScenario.obj("P1", "Fire Covenant", 0, Zone.HAND)));
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility spell = spellInHand(s, game, "Fire Covenant");
        // What AbilityImpl.activate leaves when the life cost failed: X announced
        // and the variable cost marked paid, the fixed PayLifeCost before it unpaid,
        // the mana paid.
        int x = player.getLife();
        PayVariableLifeCost variable = null;
        for (Cost cost : spell.getCosts()) {
            if (cost instanceof PayVariableLifeCost v) {
                variable = v;
            }
        }
        assertNotNull(variable, "Fire Covenant has a variable life cost");
        spell.addCost(new PayLifeCost(x), spell.getCosts().indexOf(variable));
        variable.setAmount(x, x, false);
        variable.setPaid();
        spell.getManaCostsToPay().setPaid();
        player.recordPaidSpellAbilityForBoundaryTest(spell);

        player.recordLifeAfterSpellManaPaymentForBoundaryTest(x - 1);
        assertTrue(player.reversedUnpayableLifeCost(spell, game),
                "X above the life left after the mana step is the engine-evidenced reversal");

        player.recordLifeAfterSpellManaPaymentForBoundaryTest(x);
        assertFalse(player.reversedUnpayableLifeCost(spell, game),
                "X the caster could still pay is not this reversal");

        player.recordLifeAfterSpellManaPaymentForBoundaryTest(null);
        assertFalse(player.reversedUnpayableLifeCost(spell, game),
                "no recorded payment-time life, no evidence");

        player.recordLifeAfterSpellManaPaymentForBoundaryTest(x - 1);
        player.recordPaidSpellAbilityForBoundaryTest(null);
        assertFalse(player.reversedUnpayableLifeCost(spell, game),
                "no engine payment of this spell, no evidence");
    }

    @Test
    void aCastRefusedBeforeAnyChoiceIsReversedOnlyWithAllItsFacts() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue747-before-any-choice", 2, "P1",
                List.of(XmageMultiplayerScenario.obj("P1", "Resculpt", 0, Zone.HAND),
                        XmageMultiplayerScenario.obj("P1", "Divination", 1, Zone.HAND)));
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility resculpt = spellInHand(s, game, "Resculpt");
        long decisions = player.decisionCountForBoundaryTest();
        int stack = game.getStack().size();

        assertTrue(player.reversedBeforeAnyChoice(resculpt, game, Zone.HAND, stack, decisions),
                "required target unchosen, nothing asked, card and stack as before: a reversal");
        assertFalse(player.reversedBeforeAnyChoice(resculpt, game, Zone.HAND, stack, decisions - 1),
                "a decision was handed to the pilot during the attempt");
        assertFalse(player.reversedBeforeAnyChoice(resculpt, game, Zone.GRAVEYARD, stack, decisions),
                "the card is not back where the cast started");
        assertFalse(player.reversedBeforeAnyChoice(resculpt, game, Zone.HAND, stack + 1, decisions),
                "the stack is not what it was");
        assertFalse(player.reversedBeforeAnyChoice(
                        spellInHand(s, game, "Divination"), game, Zone.HAND, stack, decisions),
                "a spell without a required target cannot be refused for want of one");
        player.recordPaidSpellAbilityForBoundaryTest(resculpt);
        assertFalse(player.reversedBeforeAnyChoice(resculpt, game, Zone.HAND, stack, decisions),
                "the engine reached the mana step, so it did not stop before any choice");
    }

    /**
     * #815: Blinding Beam with Entwine paid. {@code EntwineAbility.changeModes}
     * forces every mode; with no creature to tap the engine cannot select them
     * and reverses the cast without a mode decision (the bridge only saw the
     * Yes answer, which the test records the way chooseBoolean does).
     */
    @Test
    void anEntwinedCastWithAnUnchoosableModeIsReversedOnlyWithAllItsFacts() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue815-entwine-modes", 2, "P1",
                List.of(XmageMultiplayerScenario.obj("P1", "Blinding Beam", 0, Zone.HAND),
                        XmageMultiplayerScenario.obj("P1", "Resculpt", 1, Zone.HAND)));
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility beam = spellInHand(s, game, "Blinding Beam");
        int stack = game.getStack().size();

        assertFalse(player.reversedUnsatisfiableModeCount(beam, game, Zone.HAND, stack),
                "the pilot accepted no optional cost");
        player.recordAcceptedOptionalCostForBoundaryTest(beam);
        assertTrue(player.reversedUnsatisfiableModeCount(beam, game, Zone.HAND, stack),
                "Entwine accepted, a mode without a choosable target, nothing else asked, card and stack as before");
        assertFalse(player.reversedUnsatisfiableModeCount(beam, game, Zone.GRAVEYARD, stack),
                "the card is not back where the cast started");
        assertFalse(player.reversedUnsatisfiableModeCount(beam, game, Zone.HAND, stack + 1),
                "the stack is not what it was");
        assertFalse(player.reversedUnsatisfiableModeCount(
                        spellInHand(s, game, "Resculpt"), game, Zone.HAND, stack),
                "another card than the one whose prompt was accepted");
        player.recordModeChoiceRequestedForBoundaryTest(true);
        assertFalse(player.reversedUnsatisfiableModeCount(beam, game, Zone.HAND, stack),
                "the pilot was asked for a mode, so the failure is not the engine's own");
        player.recordModeChoiceRequestedForBoundaryTest(false);
        player.recordPaidSpellAbilityForBoundaryTest(beam);
        assertFalse(player.reversedUnsatisfiableModeCount(beam, game, Zone.HAND, stack),
                "the engine reached the mana step");
    }

    private static SpellAbility spellInHand(XmageMultiplayerScenario s, Game game, String name) {
        for (Card card : s.seats.get("P1").getHand().getCards(game)) {
            if (name.equals(card.getName())) {
                return card.getSpellAbility();
            }
        }
        throw new AssertionError(name + " must be in P1's hand");
    }

    /** The only offered target with the whole remaining amount. */
    private static JsonObject targetAmountAction(XmageMultiplayerScenario s, int amount) {
        JsonObject legal = s.session.legalActionsPayload();
        JsonObject pending = s.session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonElement first = legal.getAsJsonArray("actions").get(0);
        String optionId = first.getAsJsonObject().getAsJsonObject("metadata").get("option_id").getAsString();
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "issue747-share");
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + optionId);
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new com.google.gson.JsonArray());
        proposal.add("selected_modes", new com.google.gson.JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        com.google.gson.JsonArray selected = new com.google.gson.JsonArray();
        selected.add(optionId);
        choices.add("selected_option_ids", selected);
        choices.addProperty("numeric_choice", amount);
        choices.add("ordering", new com.google.gson.JsonArray());
        proposal.add("choices", choices);
        return proposal;
    }
}
