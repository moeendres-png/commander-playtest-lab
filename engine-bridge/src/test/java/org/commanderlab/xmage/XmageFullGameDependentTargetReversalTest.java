package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.cards.CardSetInfo;
import mage.constants.Rarity;
import mage.constants.Zone;
import mage.game.Game;
import mage.players.Player;
import mage.target.Target;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #749: a cast whose LATER required target has no legal option because of an
 * EARLIER target the pilot chose must hand priority back to the same player,
 * not abort the game with XMAGE_ACTION_EXECUTION_FAILED.
 *
 * <p>The card is the issue's own. Searing Blaze (Oracle): "Searing Blaze deals
 * 1 damage to target player or planeswalker and 1 damage to target creature
 * that player or that planeswalker's controller controls." In the pinned
 * engine the second target is {@code SearingBlazeTarget}, whose
 * {@code canTarget} reads the first target
 * ({@code Mage.Sets/src/mage/cards/s/SearingBlaze.java}).
 *
 * <p>Read off the pinned source: {@code AbilityImpl.activate} chooses targets
 * before any cost is paid. The pilot is asked for the player. When that player
 * controls no creature, {@code Targets.makeChoice} skips the second target
 * because its {@code canChoose} is false (Targets.java:105), without calling the
 * player. {@code isChosen} is then false, {@code activate} returns false and
 * {@code PlayerImpl.cast} restores its bookmark: the CR 601.2c / 601.2e
 * reversal. Before #749 the bridge read that as a bridge failure.
 *
 * <p>Everything runs on the proven started-game harness
 * ({@link XmageMultiplayerScenario}): a real 2P {@code CommanderFreeForAll} at
 * turn 1 precombat main with P1 holding priority and two untapped Mountains.
 */
class XmageFullGameDependentTargetReversalTest {

    private static final String SEARING_BLAZE = "Searing Blaze";
    private static final String MOUNTAIN = "Mountain";
    private static final String BEARS = "Grizzly Bears";

    /**
     * Red before the fix ("priority cast failed"), green after: the pilot
     * targets P2, who controls no creature, the engine reverses the cast and
     * the same seat is asked again with the spell back in hand.
     */
    @Test
    void castWhoseDependentTargetHasNoLegalOptionIsReversedNotFailed() {
        XmageMultiplayerScenario s = scenario("issue749-dependent-target-empty", false);
        Game game = s.session.restorationGame();
        int turn = game.getTurnNum();
        String step = game.getStep().getType().name();

        s.submit(XmageExternalRiskSignalTest.spellOffer(
                s.session.legalActionsPayload(), SEARING_BLAZE));
        assertEquals("target", s.decisionClass(),
                "the pilot is asked for the first target: " + s.labels());
        s.submit(targetOption(s, s.seats.get("P2").getId()));

        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "REGRESSION GUARD: before #749 this frame ended the game with "
                        + "XMAGE_ACTION_EXECUTION_FAILED / 'priority cast failed'. Observed: "
                        + after.get("failure"));
        assertEquals("priority", s.decisionClass(),
                "the engine skipped the creature target without asking and reversed the cast; "
                        + "the same player receives priority again: " + s.labels());
        assertEquals("P1", s.actor(), "the rewind returns priority to the same seat");
        assertFalse(s.seats.get("P1").isPassed(),
                "the lane must not pass priority for the player after a reversal");
        assertTrue(game.getStack().isEmpty(), "a reversed cast puts nothing on the stack");
        assertEquals(turn, game.getTurnNum());
        assertEquals(step, game.getStep().getType().name());
        assertEquals(1, handCount(s, game), SEARING_BLAZE + " is back in hand");
        assertEquals(40, s.seats.get("P2").getLife(), "nothing resolved");

        // The game keeps running: the same cast reverses again, cleanly.
        s.submit(XmageExternalRiskSignalTest.spellOffer(
                s.session.legalActionsPayload(), SEARING_BLAZE));
        s.submit(targetOption(s, s.seats.get("P2").getId()));
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the second reversal is equally clean");
        assertEquals("priority", s.decisionClass());
        assertEquals("P1", s.actor());
    }

    /**
     * Positive control: P2 controls a creature, so the engine asks for it, the
     * pilot chooses it, the mana is paid and the spell goes on the stack.
     */
    @Test
    void castWhoseDependentTargetIsChoosableStillGoesThrough() {
        XmageMultiplayerScenario s = scenario("issue749-dependent-target-present", true);
        Game game = s.session.restorationGame();

        s.submit(XmageExternalRiskSignalTest.spellOffer(
                s.session.legalActionsPayload(), SEARING_BLAZE));
        s.submit(targetOption(s, s.seats.get("P2").getId()));
        assertEquals("target", s.decisionClass(),
                "the creature target has a legal option, so the engine asks for it: "
                        + s.labels());
        s.submit(labelled(s, BEARS));
        s.payWith(MOUNTAIN);

        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull());
        assertFalse(game.getStack().isEmpty(), "the cast COMPLETED: the spell is on the stack");
        assertEquals(0, handCount(s, game), SEARING_BLAZE + " left the hand to be cast");
    }

    // ---- predicate controls (white box, on real engine objects) -------------

    /** The accepted shape: the offered first target chosen, the second skipped. */
    @Test
    void skippedDependentTargetAfterAChosenTargetIsAReversal() {
        XmageMultiplayerScenario s = scenario("issue749-predicate-accepted", false);
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility spell = spellAbility(s, game);
        Target first = spell.getTargets().get(0);
        first.addTarget(s.seats.get("P2").getId(), spell, game, true);
        player.recordTargetCallbackForBoundaryTest(spell, first);

        assertTrue(player.reversedDependentRequiredTarget(spell, game),
                "the pilot's chosen player left the required creature target unchoosable");
    }

    /**
     * Shapes outside the accepted one: a declined offered target, every target
     * chosen, and no target callback at all. RED if the offered-target check or
     * the callback-presence check is dropped. The skipped-target check is
     * proven by {@link #partlyChosenUnaskedTargetIsNotAReversal} and the
     * source-card check by {@link #dependentTargetOnAnotherCardIsNotAReversal}.
     */
    @Test
    void dependentTargetGuardsRejectEachBrokenFact() {
        // The pilot was asked and chose nothing: a declined target, not a skip.
        XmageMultiplayerScenario declined = scenario("issue749-predicate-declined", false);
        Game game = declined.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) declined.seats.get("P1");
        SpellAbility spell = spellAbility(declined, game);
        player.recordTargetCallbackForBoundaryTest(spell, spell.getTargets().get(0));
        assertFalse(player.reversedDependentRequiredTarget(spell, game),
                "an offered target left unchosen is the pilot's decision, never a reversal");

        // Every target chosen: whatever failed the cast, it was not a skipped target.
        XmageMultiplayerScenario chosen = scenario("issue749-predicate-all-chosen", true);
        game = chosen.session.restorationGame();
        player = (XmageFullGamePlayer) chosen.seats.get("P1");
        spell = spellAbility(chosen, game);
        UUID bears = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> BEARS.equals(p.getName()))
                .filter(p -> p.isControlledBy(chosen.seats.get("P2").getId()))
                .findFirst().orElseThrow().getId();
        spell.getTargets().get(0).addTarget(chosen.seats.get("P2").getId(), spell, game, true);
        spell.getTargets().get(1).addTarget(bears, spell, game, true);
        player.recordTargetCallbackForBoundaryTest(spell, spell.getTargets().get(0));
        player.recordTargetCallbackForBoundaryTest(spell, spell.getTargets().get(1));
        assertFalse(player.reversedDependentRequiredTarget(spell, game),
                "with every target chosen there is no skipped required target");

        // No target callback ran at all: that is #703's shape, not this one.
        XmageMultiplayerScenario none = scenario("issue749-predicate-no-callback", false);
        game = none.session.restorationGame();
        player = (XmageFullGamePlayer) none.seats.get("P1");
        spell = spellAbility(none, game);
        assertFalse(player.reversedDependentRequiredTarget(spell, game),
                "without a target callback in this action there is no evidence");
    }

    /**
     * THE MASKING CONTROL: the target callbacks belong to a DIFFERENT card than
     * the one whose cast failed. RED if the source-card check is dropped.
     */
    @Test
    void dependentTargetOnAnotherCardIsNotAReversal() {
        XmageMultiplayerScenario s = scenario("issue749-predicate-other-card", false);
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility casting = spellAbility(s, game);

        SpellAbility other = new mage.cards.s.SearingBlaze(
                        UUID.randomUUID(),
                        new CardSetInfo(SEARING_BLAZE, "WWK", "0", Rarity.COMMON))
                .getSpellAbility();
        Target first = other.getTargets().get(0);
        first.addTarget(s.seats.get("P2").getId(), other, game, true);
        player.recordTargetCallbackForBoundaryTest(other, first);

        assertFalse(player.reversedDependentRequiredTarget(casting, game),
                "ANTI-MASKING: the skipped target belongs to another card, so it is not "
                        + "evidence that THIS cast was reversed");
    }

    /**
     * A divided-amount target the engine asked about and the bridge left
     * unchosen is the bridge's failure, not an engine skip, even when a later
     * target was chosen (Fiery Justice: damage divided among any targets, then
     * target opponent). RED if the offered-target check is dropped; production
     * records chooseTargetAmount's callbacks through the same helper this test
     * hook calls.
     */
    @Test
    void unchosenOfferedAmountTargetIsNotAReversal() {
        XmageMultiplayerScenario s = scenario("issue749-predicate-amount-declined", false);
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility spell = new mage.cards.f.FieryJustice(
                        s.seats.get("P1").getId(),
                        new CardSetInfo("Fiery Justice", "ALL", "0", Rarity.RARE))
                .getSpellAbility();
        Target amount = spell.getTargets().get(0);
        Target opponent = spell.getTargets().get(1);
        player.recordTargetCallbackForBoundaryTest(spell, amount);
        opponent.addTarget(s.seats.get("P2").getId(), spell, game, true);
        player.recordTargetCallbackForBoundaryTest(spell, opponent);

        assertFalse(player.reversedDependentRequiredTarget(spell, game),
                "the engine asked for the damage division and nothing was chosen: that is not "
                        + "the engine skipping a target");
    }

    /**
     * An unasked required target that is PARTLY chosen was not skipped: the
     * engine only skips a target it cannot choose at all. Magma Opus taps "two
     * target permanents"; with one chosen, isChosen is false, but nothing was
     * skipped. RED if the predicate stops requiring an EMPTY skipped target.
     */
    @Test
    void partlyChosenUnaskedTargetIsNotAReversal() {
        XmageMultiplayerScenario s = scenario("issue749-predicate-partly-chosen", false);
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility spell = new mage.cards.m.MagmaOpus(
                        s.seats.get("P1").getId(),
                        new CardSetInfo("Magma Opus", "STX", "0", Rarity.MYTHIC))
                .getSpellAbility();
        Target damage = spell.getTargets().get(0);
        Target tap = spell.getTargets().get(1);
        damage.addTarget(s.seats.get("P2").getId(), 4, spell, game, true);
        player.recordTargetCallbackForBoundaryTest(spell, damage);
        UUID mountain = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> MOUNTAIN.equals(p.getName())).findFirst().orElseThrow().getId();
        tap.addTarget(mountain, spell, game, true);
        assertTrue(damage.isChosen(game), "precondition: the asked target is chosen");
        assertFalse(spell.getTargets().isChosen(game),
                "precondition: the tap target needs two permanents and holds one");

        assertFalse(player.reversedDependentRequiredTarget(spell, game),
                "a partly chosen target was not skipped by the engine");
    }

    // ---- fixture ------------------------------------------------------------

    /** Searing Blaze alone in P1's hand, two Mountains, P1's bear, optionally P2's bear. */
    private static XmageMultiplayerScenario scenario(String tag, boolean opponentCreature) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SEARING_BLAZE, 0, Zone.HAND));
        for (int i = 0; i < 2; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", MOUNTAIN, i, Zone.BATTLEFIELD));
        }
        // P1's own creature keeps the spell castable: XMage only offers a cast
        // whose targets can all be chosen for SOME first-target choice.
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.BATTLEFIELD));
        if (opponentCreature) {
            objects.add(XmageMultiplayerScenario.obj("P2", BEARS, 1, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        Game game = s.session.restorationGame();
        assertEquals("P1", s.actor(), "control: P1 holds priority");
        assertEquals(opponentCreature ? 1 : 0,
                game.getBattlefield().getAllActivePermanents().stream()
                        .filter(p -> p.isCreature(game))
                        .filter(p -> p.isControlledBy(s.seats.get("P2").getId()))
                        .count(),
                "precondition: P2 controls " + (opponentCreature ? "one creature" : "no creature"));
        return s;
    }

    private static SpellAbility spellAbility(XmageMultiplayerScenario s, Game game) {
        for (Card card : s.seats.get("P1").getHand().getCards(game)) {
            if (SEARING_BLAZE.equals(card.getName())) {
                return card.getSpellAbility();
            }
        }
        throw new AssertionError(SEARING_BLAZE + " must be in P1's hand");
    }

    private static int handCount(XmageMultiplayerScenario s, Game game) {
        Player p1 = s.seats.get("P1");
        return (int) p1.getHand().getCards(game).stream()
                .filter(card -> SEARING_BLAZE.equals(card.getName()))
                .count();
    }

    /** The unique option in the current frame that names {@code objectId}. */
    private static JsonObject targetOption(XmageMultiplayerScenario s, UUID objectId) {
        JsonObject match = null;
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (objectId.toString().equals(
                    candidate.getAsJsonObject("metadata").get("option_id").getAsString())) {
                assertNull(match, "exactly one option names " + objectId + ": " + s.labels());
                match = candidate;
            }
        }
        assertNotNull(match, "no option names " + objectId + ": " + s.labels());
        return match;
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String fragment) {
        JsonObject match = null;
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.getAsJsonObject("metadata").get("label").getAsString().contains(fragment)) {
                assertNull(match, "exactly one option labelled *" + fragment + "*: " + s.labels());
                match = candidate;
            }
        }
        assertNotNull(match, "no option labelled *" + fragment + "*: " + s.labels());
        return match;
    }
}
