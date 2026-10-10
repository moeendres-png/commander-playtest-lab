package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
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
    private static final String COMMANDER = "Rograkh, Son of Rohgahh";
    private static final String CREW = "Crew 3";

    /**
     * Red control. A crewed Cultivator's Caravan (a 5/5 artifact creature)
     * whose only other untapped creature would be the seat's commander; the
     * commander is tapped by the fixture, so "another untapped creature you
     * control" is EMPTY. XMage still offers Crew 3 because {@code canPay}
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
        assertTrue(anyTappedP1CreatureApartFromCaravan(s, game),
                "precondition: every other creature P1 controls is tapped, so the crew "
                        + "cost's legal set is empty: " + battlefieldSummary(game));

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
        tapCommander(s, game);

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

    // ---- fixture ------------------------------------------------------------

    /**
     * A started 2P game in which the Vehicle has been GENUINELY crewed through
     * the lane (a real {@code choose_object} frame, a real tap, the engine's own
     * {@code AddCardTypeSourceEffect}), with the seat's commander tapped so that
     * nothing but the Vehicle is an untapped creature.
     *
     * <p>The commander tap is fixture setup performed through the engine's own
     * {@code Permanent.tap}, the same call {@code CrewCost.pay} makes when it
     * pays. It is not a decision the Lab makes: it happens before the action
     * under test and is asserted explicitly, so a reader can see exactly what
     * the battlefield was.
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
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "precondition: the crew succeeded: " + s.session.pendingDecisionPayload());
        assertTrue(caravan(game).isCreature(game),
                "precondition: the Vehicle became a creature: " + battlefieldSummary(game));

        tapCommander(s, game);
        return s;
    }

    private static List<XmageNativeStateRestoration.RequestedObject> battlefield(String... names) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int i = 0; i < names.length; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", names[i], i, Zone.BATTLEFIELD));
        }
        return objects;
    }

    /**
     * Fixture setup: tap the seat's commander so that "another untapped
     * creature you control" has no member. Done through the engine's own
     * {@code Permanent.tap}, never through a lane decision.
     */
    private static void tapCommander(XmageMultiplayerScenario s, Game game) {
        Permanent commander = permanent(game, COMMANDER);
        if (!commander.isTapped()) {
            commander.tap(null, game);
        }
        assertTrue(commander.isTapped(),
                "fixture: " + COMMANDER + " is tapped, so it cannot crew or be crewed");
    }

    /**
     * Every P1 creature other than the Vehicle is tapped: the precondition the
     * upstream canPay overcount and the real crew target disagree about.
     */
    private static boolean anyTappedP1CreatureApartFromCaravan(
            XmageMultiplayerScenario s, Game game) {
        List<UUID> controller = List.of(s.seats.get("P1").getId());
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents()) {
            if (CARAVAN.equals(permanent.getName())) {
                continue;
            }
            if (controller.contains(permanent.getControllerId())
                    && permanent.isCreature(game)
                    && !permanent.isTapped()) {
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