package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.SpellAbility;
import mage.abilities.costs.common.ExileFromGraveCost;
import mage.abilities.costs.common.PayLifeCost;
import mage.cards.Card;
import mage.cards.CardSetInfo;
import mage.constants.Rarity;
import mage.constants.Zone;
import mage.filter.StaticFilters;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.permanent.token.TreasureToken;
import mage.target.Target;
import mage.target.common.TargetCardInYourGraveyard;
import org.junit.jupiter.api.Test;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #920: a cast or an activation whose COST needs a choice the engine cannot
 * offer must hand priority back to the same player, not abort the game with
 * XMAGE_ACTION_EXECUTION_FAILED.
 *
 * <p>The cards are the ones a 46-pod precon sweep at the 1.4.62 pin ended on.
 * Read off the pinned source: {@code AbilityImpl.activate} announces X and
 * chooses the ability's targets, pays the mana (CR 601.2f) and then
 * {@code getCosts().pay(...)} (CR 601.2g, "activate failed - non mana costs").
 * {@code CostsImpl.pay} stops at the first cost whose {@code pay} fails. For
 * {@code ExileFromGraveCost}, {@code SacrificeTargetCost} and the other
 * target costs, {@code Targets.makeChoice} skips a target whose
 * {@code canChoose} is false without calling the player (Targets.java:105);
 * {@code TapTargetCost} calls {@code target.choose} itself and gets an empty
 * callback. Either way the cost stays unpaid, {@code activate} returns false
 * and {@code PlayerImpl.cast} / {@code playAbility} restore their bookmark
 * (CR 601.2e / 727). Before #920 no predicate recognised it and the bridge
 * reported "priority cast failed" / "priority activation failed".
 *
 * <p>Every positive control runs on the proven started-game harness
 * ({@link XmageMultiplayerScenario}): a real 2P {@code CommanderFreeForAll} at
 * turn 1 precombat main, the real card, the real engine and the real decision
 * lane. The white-box controls then break one engine-held fact at a time.
 */
class XmageFullGameUnchoosableCostTest {

    private static final String SKELETAL = "Skeletal Scrying";
    private static final String OSGIR = "Osgir, the Reconstructor";
    private static final String HIRELING = "Grim Hireling";
    private static final String PEERLESS = "Peerless Recycling";
    private static final String RADRAT = "Ruthless Radrat";
    private static final String EFFORT = "Collective Effort";
    private static final String BEARS = "Grizzly Bears";

    // ---- the real cards, through the real lane --------------------------------

    /**
     * Skeletal Scrying, "exile X cards from your graveyard" with nothing in the
     * graveyard. The pilot announces X = 1, pays {1}{B}; the engine cannot
     * choose the card to exile and reverses the cast.
     */
    @Test
    void exileXFromGraveyardWithAnEmptyGraveyardIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SKELETAL, 0, Zone.HAND));
        for (int i = 0; i < 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-skeletal", 2, "P1", objects);
        Game game = s.session.restorationGame();
        assertEquals(0, s.seats.get("P1").getGraveyard().size(), "precondition: empty graveyard");

        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), SKELETAL));
        assertEquals("announce_x", s.decisionClass(), s.prompt());
        announceX(s, "issue920-skeletal-x", 1);
        drive(s, new Answers().pay("Swamp"));

        assertReversed(s, game, "the cast");
        assertTrue(inHand(game, s, SKELETAL), "the spell is back in hand");
        assertNotNull(XmageExternalRiskSignalTest.spellOffer(
                        s.session.legalActionsPayload(), SKELETAL),
                "the spell is offered again: the game continues");
    }

    /**
     * Osgir, "{X}, {T}, exile an artifact card with mana value X from your
     * graveyard": the engine offers the ability because SOME artifact card is
     * in the graveyard, the pilot announces X = 0, and no artifact card there
     * has mana value 0.
     */
    @Test
    void osgirWhoseAnnouncedXMatchesNoGraveyardArtifactIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", OSGIR, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Sol Ring", 0, Zone.GRAVEYARD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-osgir", 2, "P1", objects);
        Game game = s.session.restorationGame();
        // The harness places Osgir this turn; the {T} cost needs it to have
        // been under P1's control since the turn began.
        ((mage.game.permanent.PermanentImpl) onBattlefield(game, OSGIR)).removeSummoningSickness();
        refreshOffers(s);

        JsonObject activate = s.action("activate_ability", "Exile an artifact card");
        assertNotNull(activate, "P1 is offered the {X} ability: " + s.labels());
        s.submit(activate);
        assertEquals("announce_x", s.decisionClass(), s.prompt());
        announceX(s, "issue920-osgir-x", 0);
        drive(s, new Answers());

        assertReversed(s, game, "the activation");
        Permanent osgir = onBattlefield(game, OSGIR);
        assertNotNull(osgir, "the source is untouched");
        assertEquals(1, s.seats.get("P1").getGraveyard().size(), "the graveyard is untouched");
        assertFalse(osgir.isTapped(), "the {T} cost was rewound with everything else");
    }

    /**
     * Grim Hireling, "{B}, sacrifice X Treasures": with exactly two Treasures
     * the pilot announces X = 2 and pays {B} with one of them, so the cost has
     * one Treasure left to sacrifice.
     */
    @Test
    void sacrificingMoreTreasuresThanLeftAfterPayingWithOneIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", HIRELING, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", BEARS, 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-hireling", 2, "P1", objects);
        Game game = s.session.restorationGame();
        Permanent hireling = onBattlefield(game, HIRELING);
        new TreasureToken().putOntoBattlefield(
                2, game, hireling.getAbilities(game).get(0), s.seats.get("P1").getId());
        assertEquals(2, count(game, "Treasure Token"), "precondition: two Treasures");
        refreshOffers(s);

        JsonObject activate = s.action("activate_ability", "Sacrifice X Treasures");
        assertNotNull(activate, "P1 is offered the ability: " + s.labels());
        s.submit(activate);
        assertEquals("announce_x", s.decisionClass(), s.prompt());
        announceX(s, "issue920-hireling-x", 2);
        drive(s, new Answers().pay("Treasure"));

        assertReversed(s, game, "the activation");
        assertEquals(2, count(game, "Treasure Token"),
                "the Treasure that paid {B} was given back by the rewind");
    }

    /**
     * Peerless Recycling: answering Yes to the gift turns the target into
     * "two target permanent cards from your graveyard", and the graveyard holds
     * one. The ability target is skipped by the engine and the cast reversed.
     */
    @Test
    void giftPromiseThatLeavesTheTargetUnchoosableIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", PEERLESS, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.GRAVEYARD));
        for (int i = 0; i < 2; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-peerless", 2, "P1", objects);
        Game game = s.session.restorationGame();

        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), PEERLESS));
        assertEquals("choose_use", s.decisionClass(),
                "the gift is promised through the engine's own yes/no prompt: " + s.prompt());
        drive(s, new Answers().use("Yes").pay("Forest"));

        assertReversed(s, game, "the cast");
        assertTrue(inHand(game, s, PEERLESS), "the spell is back in hand");
        assertEquals(1, s.seats.get("P1").getGraveyard().size(), "the graveyard is untouched");
    }

    /**
     * Control for the one above: declining the gift leaves a target that CAN be
     * chosen, so the engine asks for it and the cast completes.
     */
    @Test
    void declinedGiftStillCastsAndAsksForTheTarget() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", PEERLESS, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.GRAVEYARD));
        for (int i = 0; i < 2; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-peerless-no", 2, "P1", objects);
        Game game = s.session.restorationGame();

        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), PEERLESS));
        drive(s, new Answers().use("No").pay("Forest"));

        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull());
        assertFalse(game.getStack().isEmpty(), "the cast COMPLETED: the spell is on the stack");
        assertFalse(inHand(game, s, PEERLESS), PEERLESS + " left the hand to be cast");
    }

    /**
     * Ruthless Radrat, Squad "exile four cards from your graveyard": the pilot
     * promises two squad payments with five cards in the graveyard; the first
     * cost takes four, the second has one card left.
     */
    @Test
    void secondSquadPaymentWithTooFewGraveyardCardsIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", RADRAT, 0, Zone.HAND));
        for (int i = 0; i < 5; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", BEARS, i, Zone.GRAVEYARD));
        }
        for (int i = 0; i < 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-radrat", 2, "P1", objects);
        Game game = s.session.restorationGame();

        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), RADRAT));
        drive(s, new Answers().use("Yes").use("Yes").use("No").pay("Swamp").pick(4, BEARS));

        assertReversed(s, game, "the cast");
        assertTrue(inHand(game, s, RADRAT), "the spell is back in hand");
        assertEquals(5, s.seats.get("P1").getGraveyard().size(),
                "the four cards the first payment exiled are back in the graveyard");
    }

    /**
     * Collective Effort with all three modes needs two Escalate taps; the
     * second {@code TapTargetCost} finds no untapped creature.
     */
    @Test
    void secondEscalateTapWithoutAnUntappedCreatureIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", EFFORT, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Craw Wurm", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Glorious Anthem", 0, Zone.BATTLEFIELD));
        for (int i = 0; i < 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Plains", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-effort", 2, "P1", objects);
        Game game = s.session.restorationGame();

        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), EFFORT));
        drive(s, new Answers().pay("Plains"));

        assertReversed(s, game, "the cast");
        assertTrue(inHand(game, s, EFFORT), "the spell is back in hand");
        assertFalse(onBattlefield(game, s, BEARS, "P1").isTapped(),
                "the tap the first Escalate payment made was rewound");
    }

    // ---- white-box controls: break one engine-held fact at a time --------------

    /** The accepted cost shape, then each fact broken on its own. */
    @Test
    void costTargetGuardsRejectEachBrokenFact() {
        XmageMultiplayerScenario s = skeletalHand("issue920-guard-cost");
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility acting = spellAbility(s, game, SKELETAL);
        String before = XmageStateFingerprint.of(game);

        SpellAbility engine = withUnpaidExileCost(acting, 1, 1);
        Target costTarget = engine.getCosts().get(0).getTargets().get(0);
        player.recordEngineActionForBoundaryTest(acting, engine);
        assertTrue(player.reversedUnchoosableCostTarget(acting, game, before),
                "ACCEPTED SHAPE: mana paid, the first unpaid cost is an exile cost whose required "
                        + "target is empty and was never asked, and the game is as it was");

        // The pilot was sent a decision for that target: not an engine skip.
        player.recordEngineActionForBoundaryTest(acting, engine, costTarget);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "a target the pilot was asked about is the pilot's decision");

        // The game is not where it was: something the action did is still changed.
        player.recordEngineActionForBoundaryTest(acting, engine);
        Permanent swamp = onBattlefield(game, s, "Swamp", "P1");
        swamp.tap(null, game);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "ANTI-MASKING: a tapped land means the rewind did not happen");
        swamp.untap(game);
        assertTrue(player.reversedUnchoosableCostTarget(acting, game, before), "control restored");

        // The mana was never paid: CR 601.2g was not reached.
        SpellAbility unpaidMana = withUnpaidExileCost(acting, 1, 1);
        unpaidMana.getManaCostsToPay().clearPaid();
        player.recordEngineActionForBoundaryTest(acting, unpaidMana);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "an unpaid mana cost proves nothing about the non-mana costs");

        // The cost target is optional (minimum zero).
        player.recordEngineActionForBoundaryTest(acting, withUnpaidExileCost(acting, 0, 1));
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "a cost that needs nothing chosen was not blocked by an empty choice");

        // The first unpaid cost has no target at all (a Crew-like cost).
        SpellAbility noTarget = (SpellAbility) acting.copy();
        noTarget.getManaCostsToPay().setPaid();
        noTarget.addCost(new PayLifeCost(3));
        player.recordEngineActionForBoundaryTest(acting, noTarget);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "only a cost with an empty required target is covered");

        // Nothing is unpaid.
        SpellAbility allPaid = withUnpaidExileCost(acting, 1, 1);
        allPaid.getCosts().setPaid();
        player.recordEngineActionForBoundaryTest(acting, allPaid);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "with every cost paid there is no cost the engine could not pay");

        // The target is filled.
        SpellAbility filled = withUnpaidExileCost(acting, 1, 1);
        filled.getCosts().get(0).getTargets().get(0).add(swamp.getId(), game);
        player.recordEngineActionForBoundaryTest(acting, filled);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "a cost whose target holds a choice failed for another reason");

        // No engine callback left a trace.
        player.recordEngineActionForBoundaryTest(acting, null);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "without an engine ability instance there is no evidence");

        // The same fact with no start state to compare to.
        player.recordEngineActionForBoundaryTest(acting, engine);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, null),
                "without the state taken before the action the rewind cannot be proven");
    }

    /** THE MASKING CONTROL: the engine's ability belongs to another card. */
    @Test
    void costTargetOnAnotherCardIsNotAReversal() {
        XmageMultiplayerScenario s = skeletalHand("issue920-guard-other-card");
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility acting = spellAbility(s, game, SKELETAL);
        String before = XmageStateFingerprint.of(game);

        SpellAbility other = new mage.cards.s.SkeletalScrying(
                        UUID.randomUUID(), new CardSetInfo(SKELETAL, "ODY", "0", Rarity.RARE))
                .getSpellAbility();
        other = withUnpaidExileCost(other, 1, 1);
        player.recordEngineActionForBoundaryTest(acting, other);
        assertFalse(player.reversedUnchoosableCostTarget(acting, game, before),
                "ANTI-MASKING: a cost on another card is not evidence about THIS cast");
    }

    /** The ability-target shape (Peerless Recycling), then each fact broken. */
    @Test
    void abilityTargetGuardsRejectEachBrokenFact() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", PEERLESS, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.GRAVEYARD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue920-guard-ability", 2, "P1", objects);
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        SpellAbility acting = spellAbility(s, game, PEERLESS);
        String before = XmageStateFingerprint.of(game);

        SpellAbility engine = (SpellAbility) acting.copy();
        Target required = engine.getTargets().get(0);
        player.recordEngineActionForBoundaryTest(acting, engine);
        assertTrue(player.reversedUnchoosableAbilityTarget(acting, game, before),
                "ACCEPTED SHAPE: a required target is empty, was never asked, and the game is as it was");

        player.recordEngineActionForBoundaryTest(acting, engine, required);
        assertFalse(player.reversedUnchoosableAbilityTarget(acting, game, before),
                "a target the pilot was asked about and left unchosen is not an engine skip");

        player.recordEngineActionForBoundaryTest(acting, engine);
        Permanent forest = onBattlefield(game, s, "Forest", "P1");
        forest.tap(null, game);
        assertFalse(player.reversedUnchoosableAbilityTarget(acting, game, before),
                "ANTI-MASKING: a tapped land means the rewind did not happen");
        forest.untap(game);

        SpellAbility chosen = (SpellAbility) acting.copy();
        UUID bears = s.seats.get("P1").getGraveyard().iterator().next();
        chosen.getTargets().get(0).add(bears, game);
        player.recordEngineActionForBoundaryTest(acting, chosen);
        assertFalse(player.reversedUnchoosableAbilityTarget(acting, game, before),
                "with every target chosen the ability target did not fail the action");

        SpellAbility other = new mage.cards.p.PeerlessRecycling(
                        UUID.randomUUID(), new CardSetInfo(PEERLESS, "BLB", "0", Rarity.UNCOMMON))
                .getSpellAbility();
        player.recordEngineActionForBoundaryTest(acting, other);
        assertFalse(player.reversedUnchoosableAbilityTarget(acting, game, before),
                "ANTI-MASKING: a target on another card is not evidence about THIS cast");

        player.recordEngineActionForBoundaryTest(acting, null);
        assertFalse(player.reversedUnchoosableAbilityTarget(acting, game, before),
                "without an engine ability instance there is no evidence");
    }

    // ---- fixture ------------------------------------------------------------

    private static XmageMultiplayerScenario skeletalHand(String tag) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SKELETAL, 0, Zone.HAND));
        for (int i = 0; i < 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", i, Zone.BATTLEFIELD));
        }
        return XmageMultiplayerScenario.start(tag, 2, "P1", objects);
    }

    /**
     * A copy of {@code spell} the way the engine holds it once the mana step is
     * over: mana costs paid and one exile-from-graveyard cost still unpaid.
     */
    private static SpellAbility withUnpaidExileCost(SpellAbility spell, int min, int max) {
        SpellAbility engine = (SpellAbility) spell.copy();
        engine.getManaCostsToPay().setPaid();
        engine.addCost(new ExileFromGraveCost(new TargetCardInYourGraveyard(
                min, max, StaticFilters.FILTER_CARDS_FROM_YOUR_GRAVEYARD)));
        return engine;
    }

    private static SpellAbility spellAbility(XmageMultiplayerScenario s, Game game, String name) {
        for (Card card : s.seats.get("P1").getHand().getCards(game)) {
            if (name.equals(card.getName())) {
                return card.getSpellAbility();
            }
        }
        throw new AssertionError(name + " must be in P1's hand");
    }

    /** Scripted answers for the decisions a cost raises, by decision class. */
    static final class Answers {
        private final Deque<String> uses = new ArrayDeque<>();
        private String land;
        private String pickName;
        private int pickCount;

        Answers use(String label) {
            uses.add(label);
            return this;
        }

        Answers pay(String landName) {
            land = landName;
            return this;
        }

        /** Selects {@code count} cards named {@code name} when a multi-select object choice comes. */
        Answers pick(int count, String name) {
            pickCount = count;
            pickName = name;
            return this;
        }
    }

    /**
     * Answers whatever the engine asks, with the first option unless scripted,
     * until the lane is back at a priority decision or the loop bound is hit.
     */
    static void drive(XmageMultiplayerScenario s, Answers answers) {
        for (int i = 0; i < 40; i++) {
            String decisionClass = s.decisionClass();
            if ("priority".equals(decisionClass)) {
                return;
            }
            assertNotNull(decisionClass, "the lane has no pending decision");
            switch (decisionClass) {
                case "mana_payment" -> s.payWith(answers.land == null ? "" : answers.land);
                case "choose_use" -> s.submit(optionLabelled(s,
                        answers.uses.isEmpty() ? "Yes" : answers.uses.poll()));
                case "announce_x" -> announceX(s, "issue920-drive-x-" + i, 1);
                case "choose_object" -> {
                    if (answers.pickName != null) {
                        XmageActualCardCorpusTest.chooseNamed(
                                new XmageActualCardCorpusTest.Started(s.session, s.seats, null),
                                "issue920-drive-pick-" + i, answers.pickName, answers.pickCount);
                    } else {
                        s.submit(firstOption(s));
                    }
                }
                default -> s.submit(firstOption(s));
            }
        }
        throw new AssertionError("the lane never returned to priority: "
                + s.decisionClass() + " " + s.prompt() + " " + s.labels());
    }

    /**
     * The common outcome of every positive control: no failure, the same seat
     * holds priority, nothing on the stack, no mana, nothing tapped, life as it
     * was. Together these are the rewind, observed from outside the bridge.
     */
    private static void assertReversed(XmageMultiplayerScenario s, Game game, String what) {
        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "REGRESSION GUARD: before #920 this frame ended the game with "
                        + "XMAGE_ACTION_EXECUTION_FAILED. An engine-reversed action must not fail "
                        + "the game. Observed lane failure: " + after.get("failure"));
        assertEquals("priority", s.decisionClass(),
                "the engine reversed " + what + " and the same player receives priority again: "
                        + s.labels());
        assertEquals("P1", s.actor(), "the rewind returns priority to the same seat");
        assertFalse(game.getState().isGameOver(), "the game is not over");
        assertFalse(s.seats.get("P1").isPassed(),
                "the lane must not pass priority for the player after a reversal");
        assertTrue(game.getStack().isEmpty(), "a reversed action puts nothing on the stack");
        assertEquals(0, s.seats.get("P1").getManaPool().getMana().count(), "no mana is left over");
        assertEquals(40, s.seats.get("P1").getLife(), "nothing resolved");
        assertTrue(game.getBattlefield().getAllActivePermanents().stream()
                        .noneMatch(Permanent::isTapped),
                "the rewind untapped everything the action tapped");
    }

    /**
     * The priority frame is built when the engine asks for it, so a change the
     * test makes to the board afterwards is not in its offers. Playing a land
     * returns priority to the same seat with a freshly built frame.
     */
    static void refreshOffers(XmageMultiplayerScenario s) {
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.getAsJsonObject("metadata").get("label").getAsString()
                    .contains("Play Mountain")) {
                s.submit(candidate);
                assertEquals("priority", s.decisionClass());
                assertEquals("P1", s.actor());
                return;
            }
        }
        throw new AssertionError("no land to play in " + s.labels());
    }

    private static void announceX(XmageMultiplayerScenario s, String tag, int value) {
        XmageActualCardCorpusTest.submitNumeric(
                new XmageActualCardCorpusTest.Started(s.session, s.seats, null), tag, value);
    }

    static boolean inHand(Game game, XmageMultiplayerScenario s, String name) {
        return s.seats.get("P1").getHand().getCards(game).stream()
                .anyMatch(card -> name.equals(card.getName()));
    }

    static Permanent onBattlefield(Game game, String name) {
        return game.getBattlefield().getAllActivePermanents().stream()
                .filter(permanent -> name.equals(permanent.getName()))
                .findFirst()
                .orElse(null);
    }

    private static Permanent onBattlefield(
            Game game, XmageMultiplayerScenario s, String name, String pid) {
        return game.getBattlefield().getAllActivePermanents().stream()
                .filter(permanent -> name.equals(permanent.getName()))
                .filter(permanent -> permanent.isControlledBy(s.seats.get(pid).getId()))
                .findFirst()
                .orElse(null);
    }

    private static long count(Game game, String name) {
        return game.getBattlefield().getAllActivePermanents().stream()
                .filter(permanent -> name.equals(permanent.getName()))
                .count();
    }

    private static JsonObject firstOption(XmageMultiplayerScenario s) {
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            return element.getAsJsonObject();
        }
        throw new AssertionError("no option in " + s.decisionClass() + ": " + s.prompt());
    }

    private static JsonObject optionLabelled(XmageMultiplayerScenario s, String fragment) {
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
