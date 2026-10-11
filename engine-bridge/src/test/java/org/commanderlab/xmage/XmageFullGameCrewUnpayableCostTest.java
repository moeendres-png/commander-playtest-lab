package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.cards.CardSetInfo;
import mage.cards.c.CultivatorsCaravan;
import mage.constants.Rarity;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #715: a Crew activation XMage offers but cannot pay must hand priority back
 * to the same player, not abort the game with XMAGE_ACTION_EXECUTION_FAILED.
 *
 * <p>The engine path, read off the pinned XMage source
 * ({@code Mage/src/main/java/mage/abilities/keyword/CrewAbility.java}):
 * {@code CrewCost.canPay} sums power over
 * {@code game.getBattlefield().getAllActivePermanents(filter, controllerId, game)},
 * and that overload calls {@code filter.match(perm, game)} with no source
 * context ({@code mage/game/permanent/Battlefield.java}: the 3-argument
 * {@code getAllActivePermanents}). {@code AnotherPredicate.apply} compares
 * {@code input.getObject().getId()} with {@code input.getSourceId()} and
 * returns true when they differ; with no source object in the match input
 * the source id is absent, so the predicate matches everything and the
 * ability's own Vehicle is never excluded. A Vehicle that is ALREADY a
 * creature therefore counts its own power toward its crew cost and
 * {@code getPlayable} offers the activation.
 *
 * <p>{@code CrewCost.pay} builds {@code new TargetPermanent(0,
 * Integer.MAX_VALUE, filter, true)} and calls {@code target.choose(Outcome,
 * controllerId, source.getSourceId(), source, game)} WITH the source, so
 * {@code AnotherPredicate} does apply there and correctly excludes the
 * Vehicle. {@code TargetImpl.choose} asks the controller through
 * {@code choose(outcome, this, source, game)} — the NON-target overload — and
 * when nothing else qualifies the legal set is empty.
 *
 * <p>Upstream defect, recorded and not repaired here (the pin is not changed):
 * {@code canPay} evaluates the filter without source context. The bridge fix
 * recognises the engine's REVERSAL, not the cause.
 *
 * <p>Governing chain: CR 118.3 (a cost is a cost, and if it cannot be paid it
 * is not paid), CR 602.2b and CR 601.2h (the costs of an activated ability are
 * paid during its activation, before its effect resolves), so an activation
 * whose cost choice has no legal option is a proposal the game cannot
 * complete. {@code PlayerImpl.playAbility} restores its bookmark, and the same
 * player is asked again.
 *
 * <p>Everything runs on the proven started-game harness
 * ({@link XmageMultiplayerScenario}): a real 2P {@code CommanderFreeForAll} at
 * turn 1 precombat main with P1 holding priority. The engine builds the real
 * crew cost, the real {@code TargetPermanent}, and the real
 * {@code TargetImpl.choose} loop. The Vehicle is genuinely crewed through the
 * lane before the unpayable attempt, so "already a creature" is engine state,
 * not a fabricated one.
 */
class XmageFullGameCrewUnpayableCostTest {

    private static final String CARAVAN = "Cultivator's Caravan";
    private static final String TOR = "Tor Wauki the Younger";
    private static final String BEARS = "Grizzly Bears";
    private static final String CREW = "Crew 3";

    /**
     * Red control. A crewed Cultivator's Caravan (a 5/5 artifact creature)
     * and nothing else that P1 could crew it with: the fixture seats Tor
     * Wauki the Younger on the battlefield but taps him by crewing the Vehicle
     * in the setup (see {@link #crewedCaravan}), and the seat's commander is
     * seated OFF the battlefield at this step, so "another untapped creature
     * you control" is EMPTY. XMage still offers Crew 3 because {@code canPay}
     * counted the Vehicle's own power, and {@code CrewCost.pay} then has no
     * legal option to choose.
     *
     * <p>Red before the fix ({@code XMAGE_ACTION_EXECUTION_FAILED} /
     * "priority activation failed"). Green after: no failure is recorded, the
     * Lab never passes priority on the player's behalf, the same seat is asked
     * again, and nothing was tapped by the reversed activation.
     */
    @Test
    void unpayableCrewIsReversedNotFailed() {
        XmageMultiplayerScenario s = crewedCaravan("issue715-unpayable-crew", List.of());
        Game game = s.session.restorationGame();

        assertEquals("P1", s.actor(), "control: P1 holds priority at turn 1 precombat main");
        // Precondition, read off the engine's own state rather than asserted
        // from prose: the Vehicle is a creature, and nothing else is an
        // untapped creature, so the crew cost's legal set is empty.
        assertTrue(caravan(game).isCreature(game),
                "precondition: " + CARAVAN + " is already crewed, so it is a creature "
                        + "and canPay counts its own power against its crew cost");
        assertTrue(noOtherUntappedP1Creature(game),
                "precondition: nothing but the crewed Vehicle is an untapped creature, so "
                        + "the crew cost's legal set is empty: " + battlefieldSummary(game));

        int turn = game.getTurnNum();
        String step = game.getStep().getType().name();
        List<String> tappedBefore = tappedNames(game);
        int manaBefore = s.seats.get("P1").getManaPool().getMana().count();

        JsonObject activate = s.action("activate_ability", CREW);
        assertNotNull(activate,
                "the engine still offers Crew 3 (canPay overcounted): " + s.labels());

        s.submit(activate);

        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "REGRESSION GUARD: before #715 this frame ended the game with "
                        + "XMAGE_ACTION_EXECUTION_FAILED / 'priority activation failed'. "
                        + "An engine-reversed activation must not fail the game. "
                        + "Observed lane failure: " + after.get("failure"));
        // The lane blocks on the next pending decision, so a choice frame would
        // have surfaced here. Seeing priority proves the engine offered the
        // cost choice with an EMPTY legal set and the bridge asked for nothing.
        assertEquals("priority", s.decisionClass(),
                "the engine had no legal crew option and the same player receives priority "
                        + "again: " + s.labels());
        assertEquals("P1", s.actor(), "the rewind returns priority to the same seat");
        assertFalse(game.getState().isGameOver(), "the game is not over");
        assertFalse(s.seats.get("P1").isPassed(),
                "the lane must not pass priority for the player after a reversal");
        assertTrue(game.getStack().isEmpty(), "a reversed activation puts nothing on the stack");
        assertEquals(turn, game.getTurnNum(), "the rewind returns to the same turn");
        assertEquals(step, game.getStep().getType().name(), "the rewind returns to the same step");
        assertEquals(manaBefore, s.seats.get("P1").getManaPool().getMana().count(),
                "no mana was paid for the reversed activation");
        // The decisive observable: the reversed crew cost tapped nothing.
        assertEquals(tappedBefore, tappedNames(game),
                "the engine paid no part of the cost, so no permanent changed tapped state");
        assertTrue(caravan(game).isCreature(game),
                "the rewind leaves the Vehicle a creature: " + battlefieldSummary(game));
        assertNotNull(s.action("activate_ability", CREW),
                "the reversed action is offered again: the game continues");

        // The game keeps running: the same action reverses again, cleanly.
        s.submit(s.action("activate_ability", CREW));
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the second reversal is equally clean");
        assertEquals("priority", s.decisionClass(), "the game keeps running");
        assertEquals("P1", s.actor());
    }

    /**
     * Positive control: the SAME card, the same lane, with an untapped
     * Tor Wauki the Younger (3 power, exactly the Crew 3 threshold) on the
     * battlefield. Crew 3 must still succeed: the engine asks a
     * {@code choose_object} frame, the pilot picks the creature by label, and
     * the Vehicle becomes a creature.
     *
     * <p>This is what keeps #715 narrow. The legal set is NOT empty, the
     * pilot IS asked, and the activation completes: a successful crew must not
     * be read as a reversal, and the new flag must not be recorded on the
     * ordinary path.
     */
    @Test
    void crewWithASufficientUntappedCreatureStillSucceeds() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "issue715-crew-succeeds", 2, "P1", battlefield(CARAVAN, TOR));
        Game game = s.session.restorationGame();

        assertFalse(caravan(game).isCreature(game),
                "precondition: " + CARAVAN + " is not a creature yet");

        JsonObject activate = s.action("activate_ability", CREW);
        assertNotNull(activate, "Crew 3 is offered: " + s.labels());
        s.submit(activate);

        assertEquals("choose_object", s.decisionClass(),
                "the pilot is asked which creatures tap; the legal set is not empty: "
                        + s.labels());
        assertEquals("P1", s.actor(), "the same seat pays the cost");
        assertTrue(s.labels().stream().anyMatch(label -> label.contains(TOR)),
                "the only crew option is the 3-power creature: " + s.labels());
        s.submit(optionLabelled(s, TOR));
        endCrewCost(s);
        resolveStackThroughTheLane(s);

        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "a payable crew cost never fails: " + s.session.pendingDecisionPayload());
        assertTrue(caravan(game).isCreature(game),
                "the Vehicle became a creature through the lane: " + battlefieldSummary(game));
        assertTrue(permanent(game, TOR).isTapped(), "the chosen creature paid the cost");
        assertFalse(caravan(game).isTapped(), "the Vehicle itself is not tapped by its own crew");
    }

    /**
     * Predicate control (fail-closed): an activation failure with NO empty
     * non-target choice must still abort with XMAGE_ACTION_EXECUTION_FAILED.
     *
     * <p>Same upstream defect, different shape: {@code canPay} still overcounts
     * the crewed Vehicle and offers Crew 3, but here the legal set is NOT empty
     * — an untapped Grizzly Bears (2 power) qualifies — so the engine really
     * does ask the pilot through the lane. The pilot chooses it, and
     * {@code CrewCost.pay} then computes {@code paid = sumPower >= value} as
     * 2 &gt;= 3, i.e. false, and the activation fails with a non-empty choice
     * behind it.
     *
     * <p>Under CR 118.3 the cost still cannot be paid, so a permissive reading
     * would accept this too. The contract is narrower: only an EMPTY legal set
     * is engine evidence of a reversal. With options on the table the pilot
     * made the choice and the shortfall is the engine's own failure, so the
     * bridge must keep failing closed. RED if the {@code emptyNonTargetChoice}
     * term is replaced by anything that accepts a non-empty cost choice, or if
     * the guard itself is removed.
     */
    @Test
    void crewCostTooLowWithAChoiceMadeStillFailsClosed() {
        XmageMultiplayerScenario s = crewedCaravan(
                "issue715-crew-shortfall", List.of(
                        XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.BATTLEFIELD)));
        Game game = s.session.restorationGame();

        assertEquals(2, permanent(game, BEARS).getPower().getValue(),
                "precondition: " + BEARS + " is below the Crew 3 threshold on its own");
        assertTrue(caravan(game).isCreature(game),
                "precondition: " + CARAVAN + " is already crewed, so Crew 3 is offered again");

        s.submit(s.action("activate_ability", CREW));

        assertEquals("choose_object", s.decisionClass(),
                "the legal set is NOT empty here, which is exactly what separates this "
                        + "control from the #715 reversal: " + s.labels());
        assertTrue(s.labels().stream().anyMatch(label -> label.contains(BEARS)),
                "the only crew option is the 2-power creature: " + s.labels());
        s.submit(optionLabelled(s, BEARS));

        JsonObject terminal = s.session.pendingDecisionPayload();
        assertFalse(terminal.get("failure").isJsonNull(),
                "DEFENCE IN DEPTH: an activation failure with a non-empty cost choice is not "
                        + "engine evidence of a reversal; priority() must keep failing closed "
                        + "with XMAGE_ACTION_EXECUTION_FAILED");
        JsonObject failure = terminal.getAsJsonObject("failure");
        assertTrue(failure.get("message").getAsString().contains("XMAGE_ACTION_EXECUTION_FAILED"),
                "the recorded failure is the action-execution guard: " + failure);
        assertTrue(failure.get("message").getAsString().contains("priority activation failed"),
                "it is the activation branch that failed closed, not a projection error: "
                        + failure);
    }

    // ---- #715 round 2: the flag must not mask an unrelated failure ---------

    /**
     * Predicate control, positive: the empty non-targeted choice belonged to
     * the ability now being activated, so the reversal IS recognised. Real
     * engine abilities on both sides; RED if the id comparison in
     * {@code reversedEmptyNonTargetChoice} is removed or replaced by something
     * that never matches (for example instance identity — the engine activates
     * a COPY, so the objects are never {@code ==}).
     */
    @Test
    void emptyCostChoiceOfTheActivatedAbilityIsReversal() {
        XmageMultiplayerScenario s = crewedCaravan("issue715-predicate-same-ability", List.of());
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");

        ActivatedAbility crew = crewAbility(CARAVAN + " on the battlefield",
                caravan(game).getAbilities());
        player.recordEmptyNonTargetChoiceForBoundaryTest(crew);

        assertTrue(player.reversedEmptyNonTargetChoice(crew),
                "the empty cost choice IS this ability's, so this is exactly the "
                        + "engine-evidenced reversal #715 exists to recognise");
    }

    /**
     * THE MASKING CONTROL. In one action an empty optional non-targeted choice
     * is recorded, and then some UNRELATED ability's activation fails. The
     * result must still be XMAGE_ACTION_EXECUTION_FAILED, never a silent
     * rewind.
     *
     * <p>This is the defect the round-1 flag had: "some optional choice came
     * back empty" stayed set for the rest of the action, so any later failure —
     * from any ability — was laundered into a "reversal". The Lab would then
     * swallow a real defect instead of aborting.
     *
     * <p>Both abilities here are real engine {@link ActivatedAbility} objects
     * and their ids are asserted to differ, so the control exercises the id
     * comparison and not a tautology. RED if the source-ability check is
     * dropped from the predicate, if the comparison becomes instance identity,
     * or if the predicate is widened to accept any recorded empty choice.
     */
    @Test
    void emptyCostChoiceOfAnotherAbilityIsNotAReversal() {
        XmageMultiplayerScenario s = crewedCaravan("issue715-predicate-other-ability", List.of());
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");

        // The ability whose cost choice came back empty: the Vehicle's crew.
        ActivatedAbility crew = crewAbility(CARAVAN + " on the battlefield",
                caravan(game).getAbilities());
        // The UNRELATED activation that fails afterwards: a second, independent
        // instance of the same real card, so it is a genuine engine ability
        // that simply is not the one that raised the empty choice.
        ActivatedAbility other = crewAbility("a second " + CARAVAN + " card instance",
                new CultivatorsCaravan(
                        java.util.UUID.randomUUID(),
                        new CardSetInfo(CARAVAN, "OTR", "0", Rarity.RARE)).getAbilities());
        assertNotEquals(crew.getId(), other.getId(),
                "precondition: the two abilities are distinct objects with distinct ids");

        player.recordEmptyNonTargetChoiceForBoundaryTest(crew);

        assertFalse(player.reversedEmptyNonTargetChoice(other),
                "ANTI-MASKING: the empty optional choice belonged to a DIFFERENT ability, so it "
                        + "is not evidence that THIS activation was reversed. priority() must "
                        + "keep failing closed with XMAGE_ACTION_EXECUTION_FAILED rather than "
                        + "silently handing priority back and hiding the defect");
    }

    /**
     * Defence in depth: no evidence at all, and evidence with no ability
     * attached, both fail closed. RED if the predicate stops requiring a
     * recorded source ability.
     */
    @Test
    void emptyCostChoiceWithoutASourceAbilityIsNotAReversal() {
        XmageMultiplayerScenario s = crewedCaravan("issue715-predicate-no-source", List.of());
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");

        ActivatedAbility crew = crewAbility(CARAVAN + " on the battlefield",
                caravan(game).getAbilities());

        player.recordEmptyNonTargetChoiceForBoundaryTest(null);
        assertFalse(player.reversedEmptyNonTargetChoice(crew),
                "a flag with no recorded ability is not evidence of anything");

        player.recordEmptyNonTargetChoiceForBoundaryTest(crew);
        assertFalse(player.reversedEmptyNonTargetChoice(null),
                "there is no activation to attribute the empty choice to");

        // An action in which nothing raised an empty choice at all.
        player.recordEmptyNonTargetChoiceForBoundaryTest(null);
        assertFalse(player.reversedEmptyNonTargetChoice(crew),
                "DEFENCE IN DEPTH: no empty choice means no reversal evidence");
    }

    // ---- fixture ------------------------------------------------------------

    /**
     * A started 2P game in which the Vehicle has been GENUINELY crewed through
     * the lane (a real {@code choose_object} frame, a real tap chosen by label,
     * the engine's own {@code AddCardTypeSourceEffect}), leaving the crewed
     * Vehicle as the only untapped creature P1 controls.
     *
     * <p>The commander is deliberately not used: the harness seats the seat's
     * commander outside the battlefield at this step, so P1 controls exactly
     * the objects the fixture puts down.
     */
    private static XmageMultiplayerScenario crewedCaravan(
            String tag, List<XmageNativeStateRestoration.RequestedObject> others) {
        List<XmageNativeStateRestoration.RequestedObject> objects =
                new ArrayList<>(battlefield(CARAVAN, TOR));
        objects.addAll(others);
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        Game game = s.session.restorationGame();

        // Crew it through the lane exactly as a player would.
        JsonObject activate = s.action("activate_ability", CREW);
        assertNotNull(activate, "precondition: " + CARAVAN + " offers " + CREW + ": " + s.labels());
        s.submit(activate);
        assertEquals("choose_object", s.decisionClass(),
                "precondition: the crew cost asks which creatures tap: " + s.labels());
        s.submit(optionLabelled(s, TOR));
        endCrewCost(s);
        resolveStackThroughTheLane(s);
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "precondition: the crew succeeded: " + s.session.pendingDecisionPayload());
        assertTrue(caravan(game).isCreature(game),
                "precondition: the Vehicle became a creature: " + battlefieldSummary(game)
                        + " | decision=" + s.decisionClass()
                        + " | labels=" + s.labels()
                        + " | stack=" + game.getStack());

        return s;
    }

    /**
     * A crewed ability sits on the stack until every seat has passed since it
     * was put there, and only then does its continuous effect apply. The
     * fixture resolves it the way a game does: through the lane, by passing.
     */
    private static void resolveStackThroughTheLane(XmageMultiplayerScenario s) {
        Game game = s.session.restorationGame();
        for (int i = 0; i < 6 && !game.getStack().isEmpty(); i++) {
            assertEquals("priority", s.decisionClass(),
                    "the stack resolves by priority passing: " + s.labels());
            s.submit(optionLabelled(s, "Pass priority"));
        }
        assertTrue(game.getStack().isEmpty(),
                "the crewed ability resolved: " + game.getStack());
    }

    private static List<XmageNativeStateRestoration.RequestedObject> battlefield(String... names) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int i = 0; i < names.length; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", names[i], i, Zone.BATTLEFIELD));
        }
        return objects;
    }

    /**
     * {@code TargetImpl.choose} loops after a pick (it only stops when the set
     * stops growing or the choice is complete), and the crew target's minimum
     * is zero, so the engine asks again for more creatures to tap. The pilot
     * ends the cost by answering with an empty selection, which is legal
     * exactly because {@code minimum_selections} is 0.
     */
    private static void endCrewCost(XmageMultiplayerScenario s) {
        for (int i = 0; i < 4 && "choose_object".equals(s.decisionClass()); i++) {
            JsonObject pending = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            assertEquals(0, pending.get("minimum_selections").getAsInt(),
                    "precondition: ending the crew cost is legal (minimum_selections 0)");
            JsonObject proposal = new JsonObject();
            proposal.addProperty("proposal_id", "crew-cost-end-" + i);
            proposal.addProperty("actor_id", pending.get("actor_id").getAsString());
            proposal.addProperty("action_type", "structural_decision");
            proposal.add("target_ids", new JsonArray());
            proposal.add("selected_modes", new JsonArray());
            JsonObject choices = new JsonObject();
            choices.addProperty("decision_id", pending.get("decision_id").getAsString());
            choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
            choices.add("selected_option_ids", new JsonArray());
            choices.add("ordering", new JsonArray());
            proposal.add("choices", choices);
            s.session.submitAction(proposal);
        }
    }

    /**
     * The Vehicle is the only untapped creature P1 controls: the state in
     * which the crew cost's legal set ("another untapped creature you
     * control") is empty and {@code CrewCost.canPay} nevertheless returns true
     * because it counts the Vehicle's own power.
     */
    private static boolean noOtherUntappedP1Creature(Game game) {
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents()) {
            if (CARAVAN.equals(permanent.getName())) {
                continue;
            }
            if (permanent.isCreature(game) && !permanent.isTapped()) {
                return false;
            }
        }
        return true;
    }

    private static Permanent permanent(Game game, String name) {
        Permanent found = game.getBattlefield().getAllActivePermanents().stream()
                .filter(candidate -> name.equals(candidate.getName()))
                .findFirst()
                .orElse(null);
        assertNotNull(found, "precondition: " + name + " is on the battlefield: "
                + battlefieldSummary(game));
        return found;
    }

    private static Permanent caravan(Game game) {
        return permanent(game, CARAVAN);
    }

    /**
     * The {@link CREW} activated ability in {@code abilities}, chosen by the
     * engine's own rule text and never by position. Used with two DIFFERENT
     * sources: the Vehicle permanent on the battlefield, and a second
     * independent instance of the same real card built by the engine's card
     * class. The second is never put into play and never influences the game;
     * it exists only to be a genuine "some other ability" in the anti-masking
     * control.
     *
     * <p>Exactly one must match, so the control can never pass by taking the
     * first of several.
     */
    private static ActivatedAbility crewAbility(String described, Iterable<Ability> abilities) {
        List<ActivatedAbility> matched = new ArrayList<>();
        for (Ability ability : abilities) {
            if (ability instanceof ActivatedAbility
                    && ability.getRule() != null
                    && ability.getRule().startsWith(CREW)) {
                matched.add((ActivatedAbility) ability);
            }
        }
        List<String> seen = new ArrayList<>();
        for (Ability ability : abilities) {
            if (ability instanceof ActivatedAbility candidate) {
                seen.add(candidate.getClass().getSimpleName() + "/" + candidate.getRule());
            }
        }
        assertEquals(1, matched.size(),
                "precondition: exactly one activated ability whose rule starts with \"" + CREW
                        + "\" on " + described
                        + " so the control cannot pick by position; activated abilities seen: "
                        + seen);
        // Unique by the rule-text assertion above, so this is a single
        // by-name match and never a positional first-option pick.
        return matched.iterator().next();
    }

    /** Names of every tapped permanent, so "nothing new got tapped" is exact. */
    private static List<String> tappedNames(Game game) {
        return game.getBattlefield().getAllActivePermanents().stream()
                .filter(Permanent::isTapped)
                .map(Permanent::getName)
                .sorted()
                .toList();
    }

    private static String battlefieldSummary(Game game) {
        List<String> names = game.getBattlefield().getAllActivePermanents().stream()
                .map(permanent -> permanent.getName()
                        + (permanent.isTapped() ? " (tapped)" : ""))
                .toList();
        return String.join(", ", names);
    }

    /**
     * The unique option in the current frame whose label contains
     * {@code fragment}. Cost/target options are published with the engine's own
     * object label, so they are chosen by that label and never by position.
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