package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.commanderlab.xmage.XmageFullGameUnchoosableCostTest.Answers;
import static org.commanderlab.xmage.XmageFullGameUnchoosableCostTest.drive;
import static org.commanderlab.xmage.XmageFullGameUnchoosableCostTest.onBattlefield;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * A second 46-pod precon sweep (plan seed 2, game seed 1) ended three pods on
 * choices the engine offered and then refused. Each is a game that used to end
 * with XMAGE_ACTION_EXECUTION_FAILED and must now hand priority back to the
 * same player (or never offer the choice).
 *
 * <p>The cards are real, the engine is the pinned one and the lane is the real
 * decision lane ({@link XmageMultiplayerScenario}).
 */
class XmageFullGameRefusedChoiceTest {

    private static final String SEER = "Atzocan Seer";
    private static final String GROUND_SEAL = "Ground Seal";
    private static final String DINOSAUR = "Temple Altisaur";
    private static final String SCHOLAR = "Scholar of New Horizons";
    private static final String LASHWRITHE = "Lashwrithe";
    private static final String BEARS = "Grizzly Bears";

    /**
     * Atzocan Seer, "sacrifice this: return target Dinosaur card from your
     * graveyard to your hand", under Ground Seal ("cards in graveyards can't be
     * the targets of spells or abilities"). The engine's target set still held
     * the Dinosaur card; {@code TargetImpl.addTarget} dropped the pick.
     */
    @Test
    void graveyardTargetForbiddenByARuleModifyingEffectIsNotOfferedAndTheActivationIsReversed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SEER, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", DINOSAUR, 0, Zone.GRAVEYARD));
        objects.add(XmageMultiplayerScenario.obj("P2", GROUND_SEAL, 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("refused-seer", 2, "P1", objects);
        Game game = s.session.restorationGame();

        JsonObject activate = s.action("activate_ability", "Return target Dinosaur card");
        assertNotNull(activate, "P1 is offered the ability: " + s.labels());
        s.submit(activate);
        drive(s, new Answers());

        assertReversedAtPriority(s, game, "the activation");
        assertNotNull(onBattlefield(game, SEER), "the sacrifice cost was rewound");
        assertEquals(1, s.seats.get("P1").getGraveyard().size(), "the graveyard is untouched");
    }

    /** Control: without Ground Seal the same activation completes. */
    @Test
    void graveyardTargetWithoutTheRuleModifyingEffectStillWorks() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SEER, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", DINOSAUR, 0, Zone.GRAVEYARD));
        objects.add(XmageMultiplayerScenario.obj("P2", BEARS, 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("refused-seer-control", 2, "P1", objects);
        Game game = s.session.restorationGame();

        JsonObject activate = s.action("activate_ability", "Return target Dinosaur card");
        assertNotNull(activate, "P1 is offered the ability: " + s.labels());
        s.submit(activate);
        drive(s, new Answers());

        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull());
        assertFalse(game.getStack().isEmpty() && onBattlefield(game, SEER) != null,
                "the activation went through: the Seer was sacrificed or its ability is on the stack");
    }

    /**
     * Scholar of New Horizons, "{T}, remove a counter from a permanent you
     * control": with no counter anywhere the cost cannot be paid. The engine
     * offered every permanent; the cost skipped the pick.
     */
    @Test
    void removeCounterCostWithNoCounterAnywhereIsReversedNotFailed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SCHOLAR, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", BEARS, 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("refused-scholar", 2, "P1", objects);
        Game game = s.session.restorationGame();
        readyScholar(game);
        XmageFullGameUnchoosableCostTest.refreshOffers(s);

        JsonObject activate = s.action("activate_ability", "Remove a counter");
        assertNotNull(activate, "P1 is offered the ability: " + s.labels());
        s.submit(activate);
        drive(s, new Answers());

        assertReversedAtPriority(s, game, "the activation");
        assertFalse(onBattlefield(game, SCHOLAR).isTapped(), "the {T} cost was rewound");
    }

    /**
     * Control: the cost target set holds only permanents WITH a counter, so the
     * pilot cannot pick the one that cannot pay.
     */
    @Test
    void removeCounterCostOffersOnlyPermanentsWithACounter() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", SCHOLAR, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("refused-scholar-control", 2, "P1", objects);
        Game game = s.session.restorationGame();
        readyScholar(game);
        Permanent bears = onBattlefield(game, BEARS);
        bears.addCounters(CounterType.P1P1.createInstance(), s.seats.get("P1").getId(), null, game);
        XmageFullGameUnchoosableCostTest.refreshOffers(s);

        JsonObject activate = s.action("activate_ability", "Remove a counter");
        assertNotNull(activate, "P1 is offered the ability: " + s.labels());
        s.submit(activate);
        assertEquals("choose_object", s.decisionClass(), s.prompt());
        List<String> labels = s.labels();
        assertEquals(1, labels.size(), "only the permanent with a counter is offered: " + labels);
        assertTrue(labels.get(0).contains(BEARS), labels.toString());
    }

    /**
     * Lashwrithe, "Equip {B/P}{B/P}" with 2 life: two Yes answers promise 4
     * life. The engine paid the first and could not pay the second.
     */
    @Test
    void twoPhyrexianLifePaymentsWithTooLittleLifeAreReversedNotFailed() {
        XmageMultiplayerScenario s = lashwritheScenario("refused-lashwrithe", 2);
        Game game = s.session.restorationGame();

        JsonObject equip = s.action("activate_ability", "Equip");
        assertNotNull(equip, "P1 is offered Equip: " + s.labels());
        s.submit(equip);
        drive(s, new Answers().use("Yes").use("Yes"));

        assertReversedAtPriority(s, game, "the equip");
        assertEquals(2, s.seats.get("P1").getLife(), "the life the first payment took was given back");
    }

    /** Control: with 5 life both payments go through. */
    @Test
    void twoPhyrexianLifePaymentsWithEnoughLifeComplete() {
        XmageMultiplayerScenario s = lashwritheScenario("refused-lashwrithe-control", 5);
        Game game = s.session.restorationGame();

        JsonObject equip = s.action("activate_ability", "Equip");
        assertNotNull(equip, "P1 is offered Equip: " + s.labels());
        s.submit(equip);
        drive(s, new Answers().use("Yes").use("Yes"));

        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull());
        assertEquals(1, s.seats.get("P1").getLife(), "both payments were made");
        assertFalse(game.getStack().isEmpty(), "the Equip ability is on the stack");
    }

    /** The Scholar enters with counters of its own: strip them, and its summoning sickness. */
    private static void readyScholar(Game game) {
        Permanent scholar = onBattlefield(game, SCHOLAR);
        ((mage.game.permanent.PermanentImpl) scholar).removeSummoningSickness();
        for (String name : new ArrayList<>(scholar.getCounters(game).keySet())) {
            scholar.removeCounters(name, scholar.getCounters(game).getCount(name), null, game);
        }
        assertTrue(scholar.getCounters(game).isEmpty(), "precondition: the Scholar has no counter");
    }

    private static XmageMultiplayerScenario lashwritheScenario(String tag, int life) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", LASHWRITHE, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", BEARS, 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        s.seats.get("P1").setLife(life, s.session.restorationGame(), null);
        XmageFullGameUnchoosableCostTest.refreshOffers(s);
        return s;
    }

    /** No failure, same seat at priority, nothing on the stack, nothing tapped. */
    private static void assertReversedAtPriority(XmageMultiplayerScenario s, Game game, String what) {
        JsonObject after = s.session.pendingDecisionPayload();
        assertTrue(after.get("failure").isJsonNull(),
                "REGRESSION GUARD: this frame ended the game with XMAGE_ACTION_EXECUTION_FAILED: "
                        + after.get("failure"));
        assertEquals("priority", s.decisionClass(),
                "the engine reversed " + what + " and the same player receives priority again: "
                        + s.labels());
        assertEquals("P1", s.actor(), "the rewind returns priority to the same seat");
        assertFalse(game.getState().isGameOver(), "the game is not over");
        assertFalse(s.seats.get("P1").isPassed(), "the lane must not pass priority after a reversal");
        assertTrue(game.getStack().isEmpty(), "a reversed action puts nothing on the stack");
    }
}
