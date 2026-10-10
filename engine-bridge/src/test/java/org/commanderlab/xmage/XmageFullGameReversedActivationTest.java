package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.constants.ComparisonType;
import mage.constants.Zone;
import mage.filter.common.FilterCreatureCard;
import mage.filter.predicate.mageobject.ManaValuePredicate;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.target.Target;
import mage.target.Targets;
import mage.target.common.TargetCardInExile;
import mage.util.CardUtil;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #703: an activation XMage itself reverses because the announced X left a
 * REQUIRED target with no legal choice must not abort the game.
 *
 * <p>The engine path, read off the pinned XMage source (b479fe74 / 1.4.61):
 * {@code AbilityImpl.activate} calls {@code adjustX},
 * {@code handleManaXCosts} (the only caller of {@code announceX} for a {X} mana
 * cost), {@code getModes().choose}, and then {@code adjustTargets(game)} and
 * {@code getTargets().chooseTargets(...)} — targets are chosen BEFORE any cost
 * is paid (AbilityImpl.java:353-435). A card whose target filter depends on the
 * announced X narrows to an empty legal set; {@code Targets.makeChoice} then
 * skips a target whose {@code canChoose} is false (Targets.java:105, reached
 * through {@code TargetCard.canChoose} -&gt;
 * {@code canChooseFromPossibleTargets}) <em>without calling the player</em>, so
 * the bridge's own target callback never runs and {@code emptyRequiredTarget}
 * stays false. {@code makeChoice} returns {@code isChosen(game)}, false for a
 * required target, so {@code activate} returns false and
 * {@code PlayerImpl.playAbility} restores its bookmark. That is the CR
 * 601.2e / 727 rewind. Before the fix the bridge fell through to
 * {@code fail("XMAGE_ACTION_EXECUTION_FAILED", "priority activation failed")}.
 *
 * <p>The card is the issue's own card. Shelob, Dread Weaver (Oracle): "{X}{1}{B}:
 * Put target creature card with mana value X exiled with {this} onto the
 * battlefield tapped under your control." Its {@code TargetAdjuster} clears and
 * rebuilds the target as a creature card in the source's own exile zone with a
 * {@code ManaValuePredicate} on the announced X, so with nothing eligible exiled
 * there is no legal choice for ANY announced value.
 *
 * <p>Everything runs on the proven started-game harness
 * ({@link XmageMultiplayerScenario}): a real 2P {@code CommanderFreeForAll} at
 * turn 1 precombat main with P1 holding priority. The engine activates the real
 * ability on the real battlefield permanent, the bridge's real {@code announceX}
 * callback is answered through the real decision lane, and XMage's own
 * {@code Targets.makeChoice} performs the skip.
 */
class XmageFullGameReversedActivationTest {

    private static final String SHELOB = "Shelob, Dread Weaver";

    /**
     * Red before the fix ({@code XMAGE_ACTION_EXECUTION_FAILED} /
     * "priority activation failed"), green after: the engine reverses the
     * activation, the bridge treats it as a rewind, no failure is recorded, the
     * Lab never passes priority on the player's behalf, and the same seat is
     * asked again with the source untouched.
     */
    @Test
    void activationWithNoLegalXTargetIsReversedNotFailed() {
        XmageMultiplayerScenario s = shelobInPlay("issue703-reversed-x");
        Game game = s.session.restorationGame();

        // Precondition: nothing is exiled with Shelob, so the X-dependent
        // target has no legal choice for ANY announced value.
        assertTrue(game.getExile().getAllCards(game).isEmpty(),
                "precondition: no card is exiled with the source");
        assertEquals("P1", s.actor(), "control: P1 holds priority at turn 1 precombat main");

        JsonObject activate = s.action("activate_ability", SHELOB);
        assertNotNull(activate, "P1 is offered the {X}{1}{B} ability: " + s.labels());

        int turn = game.getTurnNum();
        String step = game.getStep().getType().name();
        String digest = s.session.privilegedStateDigest();

        // The real engine announces X for the real activated ability through the
        // bridge's real announceX callback. X = 0 leaves the required target
        // with no legal choice.
        s.submit(activate);
        assertEquals("announce_x", s.decisionClass(),
                "the {X} cost is announced before targets are chosen: " + s.prompt());
        assertEquals("P1", s.actor(), "the same seat announces the value");
        announceX(s, "issue703-reversed-x-announce", 0);

        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "REGRESSION GUARD: before #703 this frame ended the game with "
                        + "XMAGE_ACTION_EXECUTION_FAILED / 'priority activation failed'. "
                        + "An engine-reversed activation must not fail the game.");
        // The lane blocks on the next pending decision, so a target frame would
        // have surfaced here. Seeing priority proves the engine itself skipped
        // the unchoosable required target without ever asking the bridge for one.
        assertEquals("priority", s.decisionClass(),
                "the engine never asked the bridge for a target, and the same player receives "
                        + "priority again (CR 601.2e / 727): " + s.labels());
        assertEquals("P1", s.actor(), "the rewind returns priority to the same seat");
        assertFalse(after.get("game_over").getAsBoolean(), "the game is not over");
        assertFalse(s.seats.get("P1").isPassed(),
                "the lane must not pass priority for the player after a reversal");
        assertTrue(game.getStack().isEmpty(), "a reversed activation puts nothing on the stack");
        assertEquals(turn, game.getTurnNum(), "the rewind returns to the same turn");
        assertEquals(step, game.getStep().getType().name(), "the rewind returns to the same step");
        assertNotNull(shelobPermanent(game), "the rewind leaves the source untouched");
        assertEquals(0, s.seats.get("P1").getManaPool().getMana().count(),
                "no mana was paid for the reversed activation");
        assertEquals(digest, s.session.privilegedStateDigest(),
                "the whole proposal is reversed to the pre-activation state");
        assertNotNull(s.action("activate_ability", SHELOB),
                "the reversed action is offered again: the game continues");

        // The game keeps running: the same action reverses again, cleanly.
        s.submit(s.action("activate_ability", SHELOB));
        assertEquals("announce_x", s.decisionClass(), "the re-offered ability announces X again");
        announceX(s, "issue703-reversed-x-announce-2", 0);
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the second reversal is equally clean");
        assertEquals("priority", s.decisionClass(), "the game keeps running");
        assertEquals("P1", s.actor());
    }

    /**
     * Fail-closed control on the production predicate, driven with real engine
     * objects on the real started game.
     *
     * <p>The #703 flag is engine-evidenced only when BOTH halves hold: an X was
     * announced for the ability the engine activated, AND that ability still
     * carries a required target with nothing chosen, AND the bridge's own target
     * callback never ran. This control keeps the real post-attempt target state
     * a real activation produces — a required exile target with a
     * {@code ManaValuePredicate} and nothing chosen — and removes only the
     * cost-announcement half, so {@code priority()} keeps its pre-#703 behaviour
     * and the activation still fails closed with XMAGE_ACTION_EXECUTION_FAILED
     * instead of being silently rewound.
     */
    @Test
    void anActivationWithoutTheAnnouncedXEvidenceIsNotReadAsAReversal() {
        XmageMultiplayerScenario s = shelobInPlay("issue703-fail-closed");
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        ActivatedAbility ability = shelobXAbility(shelobPermanent(game), game);

        setTargets(ability, new Targets(requiredExileTarget(game, ability, 0)));
        assertTrue(isUnchosenRequired(ability),
                "precondition: the engine's own required target is left unchosen");
        assertFalse(ability.getTargets().isChosen(game),
                "precondition: Targets.makeChoice returns isChosen(game) == false, which is "
                        + "exactly what makes AbilityImpl.activate return false");
        assertFalse(player.reversedRequiredXTarget(game),
                "an unchosen required target with no announced X is not an engine-reversed "
                        + "activation; priority() must keep failing closed with "
                        + "XMAGE_ACTION_EXECUTION_FAILED");
    }

    // ---- fixture ------------------------------------------------------------

    /**
     * A real started 2P game with Shelob and four untapped Mountains on P1's
     * battlefield: enough to offer and pay {X}{1}{B}.
     */
    private static XmageMultiplayerScenario shelobInPlay(String tag) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SHELOB, 0, Zone.BATTLEFIELD));
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        return XmageMultiplayerScenario.start(tag, 2, "P1", objects);
    }

    private static Permanent shelobPermanent(Game game) {
        Permanent shelob = game.getBattlefield().getAllActivePermanents().stream()
                .filter(permanent -> SHELOB.equals(permanent.getName()))
                .findFirst()
                .orElse(null);
        assertNotNull(shelob, "precondition: " + SHELOB + " is on P1's battlefield");
        return shelob;
    }

    /** The card's real X-cost exile-target ability. */
    private static ActivatedAbility shelobXAbility(Permanent shelob, Game game) {
        for (Ability ability : shelob.getAbilities(game)) {
            if (ability instanceof ActivatedAbility activated
                    && activated.getManaCosts().getText().contains("X")) {
                return activated;
            }
        }
        throw new AssertionError(SHELOB + " exposes no X-cost activated ability");
    }

    /** The adjuster's own target shape for the announced X, left unchosen. */
    private static Target requiredExileTarget(Game game, Ability ability, int manaValue) {
        FilterCreatureCard filter = new FilterCreatureCard("creature card with mana value " + manaValue);
        filter.add(new ManaValuePredicate(ComparisonType.EQUAL_TO, manaValue));
        return new TargetCardInExile(filter, CardUtil.getExileZoneId(game, ability));
    }

    private static void setTargets(Ability ability, Targets targets) {
        ability.getModes().clear();
        for (Target target : List.copyOf(targets)) {
            ability.addTarget(target);
        }
    }

    private static boolean isUnchosenRequired(Ability ability) {
        for (Target target : ability.getTargets()) {
            if (target.getMinNumberOfTargets() > 0 && target.getSize() == 0) {
                return true;
            }
        }
        return false;
    }

    // ---- lane helpers -------------------------------------------------------

    /** Answers the pending numeric frame (announce X) through the real lane. */
    private static void announceX(XmageMultiplayerScenario s, String tag, int value) {
        XmageActualCardCorpusTest.submitNumeric(
                new XmageActualCardCorpusTest.Started(s.session, s.seats, null), tag, value);
    }

}
