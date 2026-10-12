package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.cards.CardSetInfo;
import mage.constants.Rarity;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #740: a cast XMage offers but cannot complete because a MANDATORY additional
 * discard cost has no legal choice must hand priority back to the same player,
 * not abort the game with XMAGE_ACTION_EXECUTION_FAILED.
 *
 * <p>The card is the issue's own. Big Score (Oracle): "{@code As an additional
 * cost to cast this spell, discard a card. Draw two cards and create two
 * Treasure tokens.}" In the pinned engine it is a {@code DiscardCardCost} — a
 * {@code DiscardTargetCost} over a {@code TargetCardInHand} with minimum one
 * ({@code Mage.Sets/src/mage/cards/b/BigScore.java}, line 22:
 * {@code getSpellAbility().addCost(new DiscardCardCost(false))}).
 *
 * <p>Why the engine offers a cast it cannot pay, read off the pinned source
 * (1.4.61):
 * <ol>
 *   <li>{@code SpellAbility.canActivate} checks {@code getCosts().canPay(...)}
 *       (SpellAbility.java:207) while the spell is STILL IN HAND, and
 *       {@code TargetCardInHand.possibleTargets} reads the caster's hand
 *       (TargetCardInHand.java:67). The spell itself is therefore a legal
 *       discard and {@code canPay} is true: the cast is offered.</li>
 *   <li>{@code PlayerImpl.cast} puts the spell on the stack
 *       (PlayerImpl.java:1371 {@code card.cast(...)}), which empties the hand.
 *       {@code AbilityImpl.activate} then pays CR 601.2f through the bridge's
 *       real {@code playMana} (AbilityImpl.java:464) and reaches CR 601.2g,
 *       {@code getCosts().pay(...)} (AbilityImpl.java:469).</li>
 *   <li>{@code DiscardTargetCost.pay} asks {@code Targets.choose}, and
 *       {@code Targets.makeChoice} SKIPS a target whose {@code canChoose} is
 *       false (Targets.java:105) without calling the player — the legal set is
 *       now empty — so {@code paid = cards.size() >= amount} is
 *       {@code 0 >= 1}, {@code CostsImpl.pay} returns false at the first
 *       unpaid cost and {@code activate} returns false.</li>
 *   <li>{@code PlayerImpl.cast} runs {@code restoreState(bookmark,
 *       ability.getRule(), game)} (PlayerImpl.java:1426): the CR 601.2e / 727
 *       rewind. The card is back in hand, the payment is rolled back and the
 *       same player is asked again.</li>
 * </ol>
 *
 * <p>Before #740 the bridge read that {@code cast} returning false as a bridge
 * failure and called {@code fail("XMAGE_ACTION_EXECUTION_FAILED", "priority
 * cast failed")}, ending a legal-looking game over an option the ENGINE
 * offered.
 *
 * <p>Upstream defect, recorded and not repaired here (the pin is not changed):
 * the additional cost is priced while the spell is still in hand, so
 * {@code canPay} and the later {@code pay} disagree about the same target. The
 * bridge recognises the engine's REVERSAL, not the cause — the same position
 * taken for #703 and #715.
 *
 * <p>Everything runs on the proven started-game harness
 * ({@link XmageMultiplayerScenario}): a real 2P {@code CommanderFreeForAll} at
 * turn 1 precombat main with P1 holding priority. The engine builds the real
 * spell ability and the real discard target, the pilot funds {3}{R} from real
 * Mountains through real payment frames, and XMage's own {@code Targets}
 * performs the skip.
 */
class XmageFullGameUnpayableDiscardCostTest {

    private static final String BIG_SCORE = "Big Score";

    /** The cost's target: {@code DiscardCardCost(false)} uses a plain card filter. */
    private static final String DISCARD_COST = "discard a card";

    private static final String MOUNTAIN = "Mountain";

    /** The extra card the payable-discard control puts in hand to discard. */
    private static final String FOREST = "Forest";

    /**
     * Red before the fix ({@code XMAGE_ACTION_EXECUTION_FAILED} / "priority
     * cast failed"), green after: the engine reverses the cast, the bridge
     * treats it as a rewind, no failure is recorded, the Lab never passes
     * priority on the player's behalf, and the same seat is asked again with
     * the spell and the mana exactly as they were.
     */
    @Test
    void castWithAnUnpayableDiscardCostIsReversedNotFailed() {
        XmageMultiplayerScenario s = bigScoreAloneInHand("issue740-unpayable-discard");
        Game game = s.session.restorationGame();

        assertEquals("P1", s.actor(), "control: P1 holds priority at turn 1 precombat main");
        // Precondition, read off the engine's own state rather than asserted from
        // prose: the discard cost's legal set is the hand minus the spell, and
        // the spell is on the stack while the cost is paid.
        assertEquals(List.of(BIG_SCORE), handNames(s, game),
                "precondition: " + BIG_SCORE + " is the ONLY card in P1's hand, so once it is "
                        + "on the stack the mandatory discard cost has no legal choice");

        int turn = game.getTurnNum();
        String step = game.getStep().getType().name();
        List<String> tappedBefore = tappedNames(game);
        int poolBefore = s.seats.get("P1").getManaPool().getMana().count();

        JsonObject castOffer = XmageExternalRiskSignalTest.spellOffer(
                s.session.legalActionsPayload(), BIG_SCORE);
        assertNotNull(castOffer,
                "the engine offers the cast (this first frame was priced before the fixture "
                        + "trimmed the hand; the offer rebuilt after the reversal, checked below, "
                        + "is the one priced with " + BIG_SCORE + " alone in hand): " + s.labels());

        // The real cast: the pilot funds {3}{R} through real payment frames,
        // and only then does the engine fail the additional cost.
        s.submit(castOffer);
        assertEquals("mana_payment", s.decisionClass(),
                "the pilot pays the mana cost through the lane before any cost choice: "
                        + s.labels());
        s.payWith(MOUNTAIN);

        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "REGRESSION GUARD: before #740 this frame ended the game with "
                        + "XMAGE_ACTION_EXECUTION_FAILED / 'priority cast failed'. A cast whose "
                        + "mandatory discard cost cannot be paid is a proposal the engine "
                        + "reverses, not a bridge defect. Observed lane failure: "
                        + after.get("failure"));
        // The lane blocks on the next pending decision, so a discard frame would
        // have surfaced here. Seeing priority proves the engine itself skipped
        // the unchoosable cost target without ever asking the bridge for one.
        assertEquals("priority", s.decisionClass(),
                "the engine had no legal discard choice and the same player receives priority "
                        + "again (CR 601.2e / 727): " + s.labels());
        assertEquals("P1", s.actor(), "the rewind returns priority to the same seat");
        assertFalse(game.getState().isGameOver(), "the game is not over");
        assertFalse(s.seats.get("P1").isPassed(),
                "the lane must not pass priority for the player after a reversal");
        assertTrue(game.getStack().isEmpty(), "a reversed cast puts nothing on the stack");
        assertEquals(turn, game.getTurnNum(), "the rewind returns to the same turn");
        assertEquals(step, game.getStep().getType().name(), "the rewind returns to the same step");
        assertEquals(List.of(BIG_SCORE), handNames(s, game),
                "PlayerImpl.cast ran restoreState(bookmark, ...): the spell is back in hand");
        assertEquals(0, graveyardCount(s, game, BIG_SCORE),
                "the reversed cast did not resolve: " + BIG_SCORE + " is in no graveyard");
        assertEquals(poolBefore, s.seats.get("P1").getManaPool().getMana().count(),
                "the payment was rolled back with the bookmark");
        assertEquals(tappedBefore, tappedNames(game),
                "the rollback untaps every land the payment tapped");
        assertNotNull(XmageExternalRiskSignalTest.spellOffer(
                        s.session.legalActionsPayload(), BIG_SCORE),
                "the spell is still castable: the game continues");

        // The game keeps running: the same cast reverses again, cleanly.
        s.submit(XmageExternalRiskSignalTest.spellOffer(
                s.session.legalActionsPayload(), BIG_SCORE));
        s.payWith(MOUNTAIN);
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the second reversal is equally clean");
        assertEquals("priority", s.decisionClass(), "the game keeps running");
        assertEquals("P1", s.actor());
    }

    /**
     * Positive control: the SAME card, the same lane, with one more card in hand
     * so the discard cost is payable. The pilot IS asked which card to discard,
     * the cost is paid, the cast completes and the spell goes on the stack.
     *
     * <p>This is what keeps #740 narrow. A paid discard cost leaves nothing
     * unpaid, so the new term cannot fire on the ordinary path — and, more
     * importantly, it proves the engine still owns the choice rather than the
     * bridge deciding legality: the discard is the pilot's.
     */
    @Test
    void castWithAPayableDiscardCostStillGoesThrough() {
        XmageMultiplayerScenario s = bigScoreAndASpareCard("issue740-payable-discard");
        Game game = s.session.restorationGame();

        JsonObject castOffer = XmageExternalRiskSignalTest.spellOffer(
                s.session.legalActionsPayload(), BIG_SCORE);
        assertNotNull(castOffer, "P1 is offered the {3}{R} instant: " + s.labels());

        s.submit(castOffer);
        assertEquals("mana_payment", s.decisionClass(),
                "the pilot pays the mana cost first: " + s.labels());
        s.payWith(MOUNTAIN);

        // CR 601.2h: the additional cost is paid while the spell is being cast.
        // The legal set is not empty, so the engine asks the pilot.
        assertFalse(s.labels().stream().anyMatch(label -> label.contains(BIG_SCORE)),
                "the spell is on the stack, so the engine's own hand leaves only " + FOREST
                        + " as a legal discard: " + s.labels());
        s.submit(optionLabelled(s, FOREST));

        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "a payable discard cost never fails the cast: " + after.get("failure"));
        assertFalse(game.getStack().isEmpty(),
                "the cast COMPLETED: the spell is on the stack, not reversed");
        assertEquals(0, handCount(s, game, BIG_SCORE),
                BIG_SCORE + " left the hand to be cast");
        assertEquals(1, graveyardCount(s, game, FOREST),
                "the pilot's discard was paid: " + FOREST + " is in P1's graveyard");
        assertEquals(0, graveyardCount(s, game, BIG_SCORE),
                "the spell is still on the stack: " + BIG_SCORE + " resolved neither");
    }

    // ---- predicate controls (white box, on real engine objects) -------------
    //
    // The link back to the real lane is
    // castWithAnUnpayableDiscardCostIsReversedNotFailed above: priority() returns
    // false WITHOUT recording a failure only when the predicate accepts, so that
    // executed run proves these are the field values a real action leaves behind,
    // and these controls prove each guard discriminates.

    /**
     * The accepted shape: this spell's own engine payment completed and the
     * engine's own cost record shows the mandatory discard as the first cost
     * that was never paid, with nothing chosen for it.
     */
    @Test
    void unpayableDiscardCostOfThisSpellIsAReversal() {
        XmageMultiplayerScenario s = bigScoreAloneInHand("issue740-predicate-this-spell");
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility spell = bigScoreSpellAbility(s, game);

        // Exactly what AbilityImpl.activate leaves when CostsImpl.pay returns
        // false at the discard cost: CR 601.2f paid in full, the non-mana cost
        // untouched.
        spell.getManaCostsToPay().setPaid();
        player.recordPaidSpellAbilityForBoundaryTest(spell);

        assertTrue(player.reversedUnpayableDiscardCost(spell, game),
                "the engine paid this spell's mana, then could not pay " + DISCARD_COST
                        + ": this is exactly the engine-evidenced reversal #740 recognises");
    }

    /**
     * Defence in depth, and the guard that keeps a cancelled or abandoned
     * payment out: with no payment recorded, with the mana cost unpaid, or with
     * no cast to attribute the failure to, the result must be false so that
     * priority() keeps failing closed. RED if any guard is dropped.
     */
    @Test
    void unpayableDiscardCostWithoutACompletedPaymentIsNotAReversal() {
        XmageMultiplayerScenario s = bigScoreAloneInHand("issue740-predicate-no-payment");
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility spell = bigScoreSpellAbility(s, game);

        player.recordPaidSpellAbilityForBoundaryTest(null);
        assertFalse(player.reversedUnpayableDiscardCost(spell, game),
                "DEFENCE IN DEPTH: no engine payment means no evidence of a reversal");

        // The CR 601.2f guard: the engine asked for payment and the action ended
        // BEFORE it was complete (the pilot pressed Cancel, or the caster left).
        // CR 601.2g never ran, so the unpaid discard cost proves nothing.
        player.recordPaidSpellAbilityForBoundaryTest(spell);
        assertFalse(player.reversedUnpayableDiscardCost(spell, game),
                "an INCOMPLETE payment never reached the cost that failed: an unrelated abort "
                        + "with an unpaid discard cost on the stack must not be laundered into a "
                        + "reversal");

        spell.getManaCostsToPay().setPaid();
        player.recordPaidSpellAbilityForBoundaryTest(spell);
        assertFalse(player.reversedUnpayableDiscardCost(null, game),
                "there is no cast to attribute the failed payment to");
    }

    /**
     * The three guards that keep an UNRELATED cost failure out, each broken alone
     * on the accepted shape: the discard target was chosen (a replacement effect
     * stopped the discard, not "no legal choice"), the spell card is not back in
     * hand (no bookmark rewind happened), and the first unpaid cost is not the
     * discard cost. RED if the target, zone or cost-type check is dropped.
     */
    @Test
    void unpayableDiscardCostGuardsRejectEachBrokenFact() {
        XmageMultiplayerScenario chosen = bigScoreAloneInHand("issue740-predicate-target-chosen");
        Game game = chosen.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) chosen.seats.get("P1");
        SpellAbility spell = bigScoreSpellAbility(chosen, game);
        spell.getManaCostsToPay().setPaid();
        player.recordPaidSpellAbilityForBoundaryTest(spell);
        mage.abilities.costs.common.DiscardTargetCost discard = spell.getCosts().stream()
                .filter(mage.abilities.costs.common.DiscardTargetCost.class::isInstance)
                .map(mage.abilities.costs.common.DiscardTargetCost.class::cast)
                .findFirst().orElseThrow();
        discard.getTargets().get(0).add(spell.getSourceId(), game);
        assertFalse(player.reversedUnpayableDiscardCost(spell, game),
                "a discard cost with its target CHOSEN did not fail for lack of a legal choice");

        XmageMultiplayerScenario moved = bigScoreAloneInHand("issue740-predicate-not-in-hand");
        game = moved.session.restorationGame();
        player = (XmageFullGamePlayer) moved.seats.get("P1");
        spell = bigScoreSpellAbility(moved, game);
        spell.getManaCostsToPay().setPaid();
        player.recordPaidSpellAbilityForBoundaryTest(spell);
        game.getState().setZone(spell.getSourceId(), Zone.GRAVEYARD);
        assertFalse(player.reversedUnpayableDiscardCost(spell, game),
                "the spell card is not back in hand, so no bookmark rewind is evidenced");

        XmageMultiplayerScenario paid = bigScoreAloneInHand("issue740-predicate-cost-paid");
        game = paid.session.restorationGame();
        player = (XmageFullGamePlayer) paid.seats.get("P1");
        spell = bigScoreSpellAbility(paid, game);
        spell.getManaCostsToPay().setPaid();
        player.recordPaidSpellAbilityForBoundaryTest(spell);
        spell.getCosts().forEach(mage.abilities.costs.Cost::setPaid);
        assertFalse(player.reversedUnpayableDiscardCost(spell, game),
                "with every cost paid there is no unpaid discard cost the engine stopped at");
    }

    /**
     * THE MASKING CONTROL. In one action a payment is recorded for one spell, and
     * then a DIFFERENT spell's cast fails. The result must still be
     * XMAGE_ACTION_EXECUTION_FAILED, never a silent rewind.
     *
     * <p>Both abilities here are real engine objects: the ability of the
     * {@link SpellAbility} of a second, independent instance of the same real
     * card built by the engine's card class, never put into play. RED if the
     * source-card check is dropped from the predicate.
     */
    @Test
    void unpayableDiscardCostPaidForAnotherSpellIsNotAReversal() {
        XmageMultiplayerScenario s = bigScoreAloneInHand("issue740-predicate-other-spell");
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility casting = bigScoreSpellAbility(s, game);

        SpellAbility other = new mage.cards.b.BigScore(
                        UUID.randomUUID(),
                        new CardSetInfo(BIG_SCORE, "JNY", "0", Rarity.RARE))
                .getSpellAbility();
        other.getManaCostsToPay().setPaid();
        assertNotEquals(casting.getSourceId(), other.getSourceId(),
                "precondition: the two abilities belong to distinct cards with distinct ids");

        player.recordPaidSpellAbilityForBoundaryTest(other);

        assertFalse(player.reversedUnpayableDiscardCost(casting, game),
                "ANTI-MASKING: the failed payment belongs to a DIFFERENT card, so it is not "
                        + "evidence that THIS cast was reversed. priority() must keep failing "
                        + "closed with XMAGE_ACTION_EXECUTION_FAILED rather than silently "
                        + "handing priority back and hiding the defect");
    }

    // ---- fixture ------------------------------------------------------------

    /**
     * A real started 2P game in which P1's hand is exactly {@code hand} and the
     * seat holds four untapped Mountains ({@code {3}{R}}).
     *
     * <p>The scaffolding deck is 99 Mountains plus the commander, and the engine
     * deals its natural opening seven on top of whatever the restoration
     * placed — {@code XmageNativeStateRestoration}'s own hand contract says so
     * ("Hands also hold the scaffolding vehicle's opening seven"). The position
     * this issue is about is "Big Score as the ONLY card in hand", so the
     * natural cards go back on top of the library through the engine's own zone
     * objects ({@code Library.putOnTop} / {@code Cards.remove} / {@code
     * Card.setZone} — the same primitives {@code GameImpl.cheat} itself uses to
     * build a restored position). Nothing about the Rules, the cast, the cost
     * payment or the reversal is set up by hand: those are all the engine's.
     */
    private static XmageMultiplayerScenario scenarioWithHand(String tag, String... hand) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int i = 0; i < hand.length; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", hand[i], i, Zone.HAND));
        }
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", MOUNTAIN, i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");
        List<String> wanted = List.of(hand);
        for (Card card : p1.getHand().getCards(game)) {
            if (wanted.contains(card.getName())) {
                continue;
            }
            card.setZone(Zone.LIBRARY, game);
            p1.getLibrary().putOnTop(card, game);
            assertTrue(p1.getHand().remove(card.getId()),
                    "the natural scaffolding card " + card.getName() + " left P1's hand");
        }
        assertEquals(wanted.stream().sorted().toList(), handNames(s, game),
                "precondition: P1's hand is exactly " + wanted);
        return s;
    }

    /** Big Score as the only card in P1's hand, and four untapped Mountains. */
    private static XmageMultiplayerScenario bigScoreAloneInHand(String tag) {
        return scenarioWithHand(tag, BIG_SCORE);
    }

    /** The payable-discard control: one more card to discard. */
    private static XmageMultiplayerScenario bigScoreAndASpareCard(String tag) {
        return scenarioWithHand(tag, BIG_SCORE, FOREST);
    }

    /** P1's real spell ability for {@link #BIG_SCORE}, taken from the card. */
    private static SpellAbility bigScoreSpellAbility(
            XmageMultiplayerScenario s, Game game) {
        for (Card card : s.seats.get("P1").getHand().getCards(game)) {
            if (BIG_SCORE.equals(card.getName())) {
                SpellAbility spell = card.getSpellAbility();
                assertNotNull(spell, BIG_SCORE + " exposes its spell ability");
                return spell;
            }
        }
        throw new AssertionError(BIG_SCORE + " must be in P1's hand");
    }

    /** Names of every card in P1's hand, in engine order. */
    private static List<String> handNames(XmageMultiplayerScenario s, Game game) {
        return s.seats.get("P1").getHand().getCards(game).stream()
                .map(Card::getName)
                .sorted() // the hand is a UUID-keyed set: its iteration order carries no meaning
                .toList();
    }

    private static int handCount(XmageMultiplayerScenario s, Game game, String name) {
        return (int) s.seats.get("P1").getHand().getCards(game).stream()
                .filter(card -> name.equals(card.getName()))
                .count();
    }

    private static int graveyardCount(XmageMultiplayerScenario s, Game game, String name) {
        return (int) s.seats.get("P1").getGraveyard().getCards(game).stream()
                .filter(card -> name.equals(card.getName()))
                .count();
    }

    /** Names of every tapped permanent, so "nothing new got tapped" is exact. */
    private static List<String> tappedNames(Game game) {
        return game.getBattlefield().getAllActivePermanents().stream()
                .filter(Permanent::isTapped)
                .map(Permanent::getName)
                .sorted()
                .toList();
    }

    /**
     * The unique option in the current frame whose label contains
     * {@code fragment}. The discard choice is published with the engine's own
     * object label, so it is chosen by that label and never by position.
     */
    private static JsonObject optionLabelled(XmageMultiplayerScenario s, String fragment) {
        JsonObject match = null;
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.getAsJsonObject("metadata").get("label").getAsString()
                    .contains(fragment)) {
                assertNull(match, "exactly one option labelled *" + fragment + "* is expected: "
                        + s.labels());
                match = candidate;
            }
        }
        assertNotNull(match, "no option labelled *" + fragment + "*: " + s.labels());
        return match;
    }
}