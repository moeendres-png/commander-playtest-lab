package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * RG-05: causal multiplayer elimination. Loss is caused by real native card
 * transactions; no player lost/left flag or terminal result is injected.
 */
class XmageCausalEliminationReconstructionTest {

    private static final long SEED = 424242L;

    @Test
    void lethalBoltCausesNativeThreePlayerLossAndOwnedObjectCleanup() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-owned-3", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("leave-owned", "Sol Ring", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P1", "P2", "bolt",
                        List.of(arrived.seats().get("P2").getId()),
                        List.of("red"), "red");

        assertEquals(Set.of("P1", "P3"), result.survivingPlayers());
        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft());
        assertNull(arrived.session().restorationGame().getPermanent(
                arrived.restoration().injectedObjectId("leave-owned")),
                "object owned by eliminated P2 must leave the battlefield");
        for (Permanent permanent
                : arrived.session().restorationGame().getBattlefield().getAllPermanents()) {
            assertNotEquals(arrived.seats().get("P2").getId(), permanent.getOwnerId(),
                    "no P2-owned permanent may remain after native cleanup");
        }
    }

    @Test
    void priorityRingExcludesEliminatedPlayerAndSurvivorContinues() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-priority-3", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        eliminateWithSpell(
                arrived, "P1", "P2", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");

        JsonObject pending = arrived.session().pendingDecisionPayload();
        assertFalse(pending.get("decision").isJsonNull());
        String nativeActor =
                pending.getAsJsonObject("decision").get("actor_id").getAsString();
        assertNotEquals(arrived.seats().get("P2").getId().toString(), nativeActor,
                "eliminated P2 must never receive priority again");

        JsonObject legal = arrived.session().legalActionsPayload();
        assertEquals(nativeActor, legal.get("actor_id").getAsString());
        assertFalse(legal.getAsJsonArray("actions").isEmpty(),
                "a surviving player must continue with an authoritative offer");
    }

    @Test
    void activePlayerSelfLossEndsItsTurnAndNextLivePlayerBecomesActive() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-active-turn-3", 3, 2,
                List.of(
                        object("sign", "Sign in Blood", "P2", Zone.HAND),
                        object("b1", "Swamp", "P2", Zone.BATTLEFIELD),
                        object("b2", "Swamp", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 2);

        advanceToOwnPrecombatMain(arrived, "P2");
        assertEquals("P2", XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats())
                .get("active_player").getAsString());

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P2", "P2", "sign",
                        List.of(arrived.seats().get("P2").getId()),
                        List.of("b1", "b2"), "black");
        assertEquals(Set.of("P1", "P3"), result.survivingPlayers());

        // A: genuine self-loss through Sign in Blood (draw 2, lose 2 at life 2).
        assertEquals(0, arrived.seats().get("P2").getLife());
        // B: P2 leaves the game (CR 104.5/800.4 operative transition).
        assertTrue(arrived.seats().get("P2").hasLeft(),
                "P2 must leave the game after losing on its own turn");

        // C: the current turn is NOT silently reassigned (CR 800.4j): XMage
        // keeps the departed slot as active while routing priority onward.
        JsonObject atLoss = XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats());
        assertEquals(3, atLoss.get("turn_number").getAsInt());
        assertEquals("P2", atLoss.get("active_player").getAsString(),
                "the turn must continue under the departed slot, not jump to P3");

        // D/E: the turn completes natively with decisions flowing only to
        // survivors. Transition frames may still name departed P2 once (its
        // own cleanup discard on the continuing turn); those are answered by
        // the deterministic transport, but once priority has moved on, P2
        // must never decide again.
        String departedId = arrived.seats().get("P2").getId().toString();
        boolean[] handoff = {false};
        // Transition-frame rule (800.4a/800.4j-adjacent, falsifiable): the
        // engine parks exactly one pass-only priority frame on the departed
        // slot before routing onward (observed: 1 option). It is answered
        // with an explicit pass — the sole offered option, no discretion for
        // P2. Any multi-option frame for P2, any non-priority/non-discard
        // class, or any P2 frame after handoff fails closed. A cleanup
        // discard naming P2 is answered only through the deterministic
        // helper (P2's zones were cleared on leave; no live card is at stake).
        XmageTemporalProgressionDriver.DecisionSource guarded = (pending, legal, index) -> {
            String actor = pending.get("actor_id").getAsString();
            String dc = pending.get("decision_class").getAsString();
            if (departedId.equals(actor)) {
                if (handoff[0]) {
                    throw new AssertionError(
                            "departed P2 decided again after handoff at index " + index);
                }
                if ("priority".equals(dc)) {
                    assertEquals(1, legal.getAsJsonArray("actions").size(),
                            "departed-actor priority frame must offer exactly one option");
                } else if (!"choose_object".equals(dc)) {
                    throw new AssertionError(
                            "unexpected departed-actor transition frame: " + dc);
                }
            } else {
                handoff[0] = true;
            }
            return progressionScript().choose(pending, legal, index);
        };
        // Rotation from here is P1 (T4) -> P3 (T5) -> P1 (T6, P2's slot skipped).
        driveToPrecombat(arrived, "P1", 4, guarded);
        driveToPrecombat(arrived, "P3", 5, guarded);
        // G: P2's scheduled turn does not begin (CR 800.4k).
        driveToPrecombat(arrived, "P1", 6, guarded);
        JsonObject observed = XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats());
        assertEquals(6, observed.get("turn_number").getAsInt());
        assertEquals("P1", observed.get("active_player").getAsString());
        assertEquals("P1", observed.get("priority_player").getAsString(),
                "a surviving player must hold authoritative continuation");
        assertFalse(arrived.seats().get("P1").hasLost());
        assertFalse(arrived.seats().get("P3").hasLost());
    }

    private static void driveToPrecombat(
            Arrived arrived,
            String actor,
            int turn,
            XmageTemporalProgressionDriver.DecisionSource decisions
    ) {
        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(),
                arrived.seats(),
                (session, seats, observed) ->
                        observed.get("turn_number").getAsInt() == turn
                                && actor.equals(observed.get("active_player").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("phase").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("step").getAsString())
                                && actor.equals(observed.get("priority_player").getAsString()),
                decisions,
                600);
    }

    @Test
    void fivePlayerLiveRingExcludesEliminatedMiddleSeat() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-five", 5, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P1", "P3", "bolt",
                        List.of(arrived.seats().get("P3").getId()),
                        List.of("red"), "red");
        assertEquals(Set.of("P1", "P2", "P4", "P5"), result.survivingPlayers());
        assertTrue(arrived.seats().get("P3").hasLost() || arrived.seats().get("P3").hasLeft());

        JsonObject pending = arrived.session().pendingDecisionPayload();
        if (!pending.get("decision").isJsonNull()) {
            String actor = pending.getAsJsonObject("decision").get("actor_id").getAsString();
            assertNotEquals(arrived.seats().get("P3").getId().toString(), actor);
        }
    }

    @Test
    void twoPlayerNativeLossEndsGameWithWinnerAndNoFurtherDecisions() {
        // Distinct 2P terminal boundary (not multiplayer continuation): both
        // start at the bounded initial life 3, P1's genuine Bolt removes the
        // last 3 life, P2 loses, P1 wins natively and the decided game
        // exposes no further survivor decision loop.
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-terminal-2", 2, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P1", "P2", "bolt",
                        List.of(arrived.seats().get("P2").getId()),
                        List.of("red"), "red");

        assertEquals(Set.of("P1"), result.survivingPlayers());
        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft());
        assertTrue(arrived.seats().get("P1").hasWon(),
                "native two-player semantics must award the win to the survivor");
        JsonObject terminal = arrived.session().pendingDecisionPayload();
        assertTrue(terminal.get("decision").isJsonNull(),
                "the decided two-player game exposes no further decisions");
    }

    @Test
    void sameSeedFreshSessionsReproduceEliminationAndSurvivorSet() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-replay", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("owned", "Sol Ring", "P2", Zone.BATTLEFIELD)));
        Arrived first = arrive(plan, 3);
        Arrived second = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result a =
                eliminateWithSpell(first, "P1", "P2", "bolt",
                        List.of(first.seats().get("P2").getId()),
                        List.of("red"), "red");
        XmageCausalEliminationReconstruction.Result b =
                eliminateWithSpell(second, "P1", "P2", "bolt",
                        List.of(second.seats().get("P2").getId()),
                        List.of("red"), "red");

        assertEquals(a.survivingPlayers(), b.survivingPlayers());
        assertEquals(a.eliminatedPlayer(), b.eliminatedPlayer());
        assertEquals(first.seats().get("P2").hasLost(), second.seats().get("P2").hasLost());
        assertNull(first.session().restorationGame()
                .getPermanent(first.restoration().injectedObjectId("owned")));
        assertNull(second.session().restorationGame()
                .getPermanent(second.restoration().injectedObjectId("owned")));
    }



    @Test
    void nineteenCommanderDamagePlusRealHastyCommanderCombatCausesLossAndCleanup() {
        List<XmageNativeStateRestoration.RequestedPlayer> players = List.of(
                new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40),
                new XmageNativeStateRestoration.RequestedPlayer("P3", 3, 40));
        List<XmageNativeStateRestoration.RequestedCommander> commanders = List.of(
                new XmageNativeStateRestoration.RequestedCommander(
                        "cmd:P1-A", "Isamaru, Hound of Konda", "P1", 0),
                new XmageNativeStateRestoration.RequestedCommander(
                        "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0),
                new XmageNativeStateRestoration.RequestedCommander(
                        "cmd:P3-A", "Rograkh, Son of Rohgahh", "P3", 0));
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "rg05-commander-combat", 3, SEED, players, commanders,
                List.of(new XmageNativeStateRestoration.RequestedCommanderDamage(
                        "cmd:P1-A", "P2", 19)),
                List.of(
                        object("white", "Plains", "P1", Zone.BATTLEFIELD),
                        object("haste", "Fervor", "P1", Zone.BATTLEFIELD),
                        object("leave-owned-cmd", "Sol Ring", "P2", Zone.BATTLEFIELD)),
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        Arrived arrived = arrive(plan, 40);

        UUID commanderId = arrived.session().restorationGame()
                .getCommandersIds(arrived.seats().get("P1"), CommanderCardType.ANY, false)
                .stream()
                .filter(id -> {
                    var card = arrived.session().restorationGame().getCard(id);
                    return card != null && "Isamaru, Hound of Konda".equals(card.getName());
                })
                .findFirst()
                .orElseThrow(() -> new AssertionError("native Isamaru Commander id missing"));

        XmageControlDivergenceReconstruction.castAndResolve(
                arrived.session(), arrived.seats(), "P1", commanderId,
                new Script(List.of(),
                        List.of(arrived.restoration().injectedObjectId("white")), "white"),
                120);
        assertNotNull(arrived.session().restorationGame().getPermanent(commanderId),
                "genuine Commander cast must resolve to the battlefield");

        AtomicBoolean declared = new AtomicBoolean(false);
        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(), arrived.seats(),
                (session, seats, observed) ->
                        seats.get("P2").hasLost() || seats.get("P2").hasLeft(),
                (pending, legal, index) -> {
                    String dc = pending.get("decision_class").getAsString();
                    if ("priority".equals(dc)) {
                        return proposal("rg05-cmd-pass-" + index, legal,
                                XmageFullGameTaxExecutionTest.singleActionOfType(
                                        legal, "pass_priority", null));
                    }
                    if ("declare_attacker".equals(dc)) {
                        if (!declared.get()) {
                            JsonObject attack = exactAttack(
                                    legal, commanderId, arrived.seats().get("P2").getId());
                            declared.set(true);
                            return proposal("rg05-cmd-attack-" + index, legal, attack);
                        }
                        return proposal("rg05-cmd-hold-" + index, legal,
                                XmageFullGameTaxExecutionTest.singleActionOfType(
                                        legal, "declare_attackers", "hold_attacker"));
                    }
                    if ("declare_blocker".equals(dc)) {
                        return emptyStructuralProposal(
                                "rg05-cmd-no-block-" + index,
                                legal.get("actor_id").getAsString());
                    }
                    return null;
                },
                220);

        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft());
        assertNull(arrived.session().restorationGame().getPermanent(
                arrived.restoration().injectedObjectId("leave-owned-cmd")),
                "Commander-damage elimination must invoke normal owned-object cleanup");
    }

    @Test
    void eliminatedOwnersPermanentLeavesEvenWhileControlledByOpponent() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-control-cleanup", 3, 3,
                List.of(
                        object("control", "Control Magic", "P1", Zone.HAND),
                        object("u1", "Island", "P1", Zone.BATTLEFIELD),
                        object("u2", "Island", "P1", Zone.BATTLEFIELD),
                        object("u3", "Island", "P1", Zone.BATTLEFIELD),
                        object("u4", "Island", "P1", Zone.BATTLEFIELD),
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("victim-bear", "Grizzly Bears", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);
        UUID bearId = arrived.restoration().injectedObjectId("victim-bear");

        castSpell(arrived, "P1", "control", List.of(bearId),
                List.of("u1", "u2", "u3", "u4"), "blue");
        Permanent stolen = arrived.session().restorationGame().getPermanent(bearId);
        assertNotNull(stolen);
        assertEquals(arrived.seats().get("P2").getId(), stolen.getOwnerId());
        assertEquals(arrived.seats().get("P1").getId(), stolen.getControllerId());

        eliminateWithSpell(arrived, "P1", "P2", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");

        assertNull(arrived.session().restorationGame().getPermanent(bearId),
                "an object owned by the departing player must leave even under opponent control");
    }

    @Test
    void departingPlayersOwnedSpellIsRemovedFromStackBeforeItCanResolve() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-stack-cleanup", 3, 3,
                List.of(
                        object("p1-bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("p1-red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("p2-bolt", "Lightning Bolt", "P2", Zone.HAND),
                        object("p2-red", "Mountain", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        XmageExternalRiskSignalTest.passToActor(
                arrived.session(), "rg05-stack-cleanup", arrived.seats(), "P2");
        JsonObject p2CastLegal = arrived.session().legalActionsPayload();
        arrived.session().submitAction(proposal(
                "rg05-stack-p2-bolt",
                p2CastLegal,
                XmageExternalRiskSignalTest.spellOffer(p2CastLegal, "Lightning Bolt")));

        JsonObject p2TargetLegal = arrived.session().legalActionsPayload();
        arrived.session().submitAction(multiSelectProposal(
                "rg05-stack-p2-target",
                p2TargetLegal,
                List.of(exactNativeObject(
                        p2TargetLegal, arrived.seats().get("P1").getId())),
                "choose_targets"));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                arrived.session(), "rg05-stack-p2-pay", "Mountain — {T}: Add {R}.");

        UUID p2BoltId = arrived.restoration().injectedObjectId("p2-bolt");
        assertTrue(arrived.session().restorationGame().getStack().stream()
                .anyMatch(stackObject -> stackObject.getSourceId().equals(p2BoltId)),
                "P2 Lightning Bolt must genuinely exist on the stack before elimination");

        XmageExternalRiskSignalTest.passToActor(
                arrived.session(), "rg05-stack-cleanup", arrived.seats(), "P1");
        eliminateWithSpell(
                arrived, "P1", "P2", "p1-bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("p1-red"), "red");

        assertFalse(arrived.session().restorationGame().getStack().stream()
                        .anyMatch(stackObject -> stackObject.getSourceId().equals(p2BoltId)),
                "departing player's owned stack object must be removed, not resolved");
    }

    @Test
    void worshipReplacementPreventsLethalDamageWithoutFabricatedPrevention() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-worship", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("worship", "Worship", "P2", Zone.BATTLEFIELD),
                        object("worship-creature", "Grizzly Bears", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        castSpell(
                arrived, "P1", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");

        assertEquals(1, arrived.seats().get("P2").getLife(),
                "Worship must replace lethal damage with a life total of 1");
        assertFalse(arrived.seats().get("P2").hasLost());
    }

    @Test
    void platinumAngelCanPreventLossUntilActualAngelRemoval() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-cant-lose", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("doom", "Doom Blade", "P1", Zone.HAND),
                        object("black1", "Swamp", "P1", Zone.BATTLEFIELD),
                        object("black2", "Swamp", "P1", Zone.BATTLEFIELD),
                        object("angel", "Platinum Angel", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        castSpell(
                arrived, "P1", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");
        assertEquals(0, arrived.seats().get("P2").getLife());
        assertFalse(arrived.seats().get("P2").hasLost(),
                "Platinum Angel must keep its controller in the game at 0 life");

        castSpell(
                arrived, "P1", "doom",
                List.of(arrived.restoration().injectedObjectId("angel")),
                List.of("black1", "black2"), "black");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());
        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft(),
                "after native removal of Platinum Angel, native SBA must eliminate P2");
    }

    @Test
    void worshipLetsSoleSurvivorWinFourPlayerGame() {
        // Genuine 4P primary cell: all four start at the bounded initial life
        // 4 (uniform authorized configuration, no post-start mutation).
        // P1's Flame Rift deals 4 to every player; P2/P3/P4 fall to 0 while
        // P1's Worship (controlling a creature) replaces its own lethal
        // damage with life total 1. Sole survivor must win natively.
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-worship-4", 4, 4,
                List.of(
                        object("rift", "Flame Rift", "P1", Zone.HAND),
                        object("r1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("r2", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("worship", "Worship", "P1", Zone.BATTLEFIELD),
                        object("worship-creature", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("m2", "Mountain", "P2", Zone.BATTLEFIELD),
                        object("m3", "Mountain", "P3", Zone.BATTLEFIELD),
                        object("m4", "Mountain", "P4", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 4);

        castSpell(arrived, "P1", "rift", List.of(), List.of("r1", "r2"), "red");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        assertEquals(1, arrived.seats().get("P1").getLife(),
                "Worship must replace P1's lethal damage with life total 1");
        assertFalse(arrived.seats().get("P1").hasLost());
        for (String pid : List.of("P2", "P3", "P4")) {
            assertTrue(arrived.seats().get(pid).hasLost() || arrived.seats().get(pid).hasLeft(),
                    pid + " must be eliminated by the same resolving Flame Rift");
        }
        // Owned-object cleanup is proven where the game continues (3P Bolt
        // cells and the 4P single-victim cell below): this terminal winner
        // state is asserted without requiring post-terminal battlefield
        // sterility, which the native engine does not complete after deciding
        // the game (victim Mountains may linger in the frozen terminal state;
        // no continuing game is affected).
        assertTrue(arrived.seats().get("P1").hasWon(),
                "sole surviving player must receive the native winner state");
        JsonObject terminal = arrived.session().pendingDecisionPayload();
        assertTrue(terminal.get("decision").isJsonNull(),
                "the decided game exposes no further decisions");
    }

    @Test
    void doubleBoltEliminatesExactlyOneVictimInContinuingFourPlayerGame() {
        // 4P cleanup in a CONTINUING game: P2 alone is eliminated by two
        // genuine Bolts while P3/P4 survive, so native leave-game cleanup is
        // observably complete (contrast the terminal winner cell above).
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-cleanup-4", 4, 4,
                List.of(
                        object("bolt1", "Lightning Bolt", "P1", Zone.HAND),
                        object("bolt2", "Lightning Bolt", "P1", Zone.HAND),
                        object("r1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("r2", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("m2", "Mountain", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 4);

        castSpell(arrived, "P1", "bolt1",
                List.of(arrived.seats().get("P2").getId()), List.of("r1"), "red");
        castSpell(arrived, "P1", "bolt2",
                List.of(arrived.seats().get("P2").getId()), List.of("r2"), "red");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft());
        assertFalse(arrived.seats().get("P1").hasWon(),
                "with three survivors the game must continue, not decide");
        for (Permanent permanent
                : arrived.session().restorationGame().getBattlefield().getAllPermanents()) {
            assertNotEquals(arrived.seats().get("P2").getId(), permanent.getOwnerId(),
                    "no P2-owned permanent may remain after native cleanup");
        }
        JsonObject pending = arrived.session().pendingDecisionPayload();
        assertFalse(pending.get("decision").isJsonNull(),
                "survivors must continue with an authoritative decision");
        String actor = pending.getAsJsonObject("decision").get("actor_id").getAsString();
        assertNotEquals(arrived.seats().get("P2").getId().toString(), actor,
                "eliminated P2 must never receive priority again");
    }

    @Test
    void flameRiftCanProduceNativeDrawWhenAllPlayersLoseSimultaneously() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-simultaneous-draw", 3, 4,
                List.of(
                        object("rift", "Flame Rift", "P1", Zone.HAND),
                        object("r1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("r2", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 4);

        castSpell(arrived, "P1", "rift", List.of(), List.of("r1", "r2"), "red");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        for (String pid : List.of("P1", "P2", "P3")) {
            assertTrue(arrived.seats().get(pid).hasLost() || arrived.seats().get(pid).hasLeft(),
                    pid + " must lose in the simultaneous native SBA batch");
            assertFalse(arrived.seats().get(pid).hasWon());
        }
    }


    private static JsonObject exactAttack(JsonObject legal, UUID attacker, UUID defender) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject nativeMetadata = nativeMeta(action);
            if ("declare_attacker".equals(text(metadata, "option_type"))
                    && attacker.toString().equals(text(nativeMetadata, "object_id"))
                    && defender.toString().equals(text(nativeMetadata, "defender_id"))) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact Commander attack option");
        return matches.get(0);
    }

    private static JsonObject emptyStructuralProposal(String id, String actor) {
        JsonObject proposal = XmageFullGameTaxExecutionTest.genericProposal(
                id, actor, "", "structural_decision");
        proposal.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
        proposal.getAsJsonObject("choices")
                .add("selected_option_ids", new com.google.gson.JsonArray());
        return proposal;
    }

    private static void passPriorityUntil(Arrived arrived, String actorPid, int bound) {
        for (int index = 0; index < bound; index++) {
            JsonObject payload = arrived.session().pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                throw new AssertionError("engine terminated while passing priority to " + actorPid);
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String nativeActor = pending.get("actor_id").getAsString();
            if (arrived.seats().get(actorPid).getId().toString().equals(nativeActor)) {
                return;
            }
            assertEquals("priority", pending.get("decision_class").getAsString());
            JsonObject legal = arrived.session().legalActionsPayload();
            arrived.session().submitAction(proposal(
                    "rg05-stack-pass-" + index,
                    legal,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            legal, "pass_priority", null)));
        }
        throw new AssertionError("priority did not reach " + actorPid);
    }

    private static void castAndLeaveOnStack(
            Arrived arrived,
            String actorPid,
            UUID sourceId,
            XmageControlDivergenceReconstruction.DecisionSource decisionSource,
            int bound
    ) {
        JsonObject legal = arrived.session().legalActionsPayload();
        assertEquals(arrived.seats().get(actorPid).getId().toString(),
                legal.get("actor_id").getAsString());
        JsonObject cast = exactSourceCast(legal, sourceId);
        arrived.session().submitAction(proposal(
                "rg05-stack-cast", legal, cast));

        for (int index = 0; index < bound; index++) {
            JsonObject payload = arrived.session().pendingDecisionPayload();
            boolean sourceOnStack = arrived.session().restorationGame().getStack().stream()
                    .anyMatch(stackObject -> stackObject.getSourceId().equals(sourceId));
            if (sourceOnStack && !payload.get("decision").isJsonNull()
                    && "priority".equals(payload.getAsJsonObject("decision")
                    .get("decision_class").getAsString())) {
                return;
            }
            if (payload.get("decision").isJsonNull()) {
                throw new AssertionError("engine terminated during stack cast");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            JsonObject currentLegal = arrived.session().legalActionsPayload();
            JsonObject selected = decisionSource.choose(
                    pending.deepCopy(), currentLegal.deepCopy(), index);
            if (selected == null) {
                throw new AssertionError(
                        "unscripted stack-cast decision "
                                + pending.get("decision_class").getAsString());
            }
            arrived.session().submitAction(selected);
        }
        throw new AssertionError("source did not reach completed native stack state");
    }

    private static JsonObject exactSourceCast(JsonObject legal, UUID sourceId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = nativeMeta(action);
            String source = text(metadata, "source_object_id");
            if (source.isBlank()) {
                source = text(metadata, "object_id");
            }
            if (sourceId.toString().equals(source)
                    && "cast_spell".equals(action.get("action_type").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact source cast option");
        return matches.get(0);
    }

    private static XmageControlDivergenceReconstruction.Result castSpell(
            Arrived arrived,
            String actor,
            String sourceSemanticId,
            List<UUID> targets,
            List<String> manaSemanticIds,
            String manaType
    ) {
        List<UUID> manaIds = manaSemanticIds.stream()
                .map(arrived.restoration()::injectedObjectId)
                .toList();
        return XmageControlDivergenceReconstruction.castAndResolve(
                arrived.session(),
                arrived.seats(),
                actor,
                arrived.restoration().injectedObjectId(sourceSemanticId),
                new Script(targets, manaIds, manaType),
                180);
    }

    private static XmageCausalEliminationReconstruction.Result eliminateWithSpell(
            Arrived arrived,
            String actor,
            String victim,
            String sourceSemanticId,
            List<UUID> targets,
            List<String> manaSemanticIds,
            String manaType
    ) {
        List<UUID> manaIds = manaSemanticIds.stream()
                .map(arrived.restoration()::injectedObjectId)
                .toList();
        return XmageCausalEliminationReconstruction.castNativeCauseAndRequireElimination(
                arrived.session(),
                arrived.seats(),
                actor,
                victim,
                arrived.restoration().injectedObjectId(sourceSemanticId),
                new Script(targets, manaIds, manaType),
                120);
    }

    private static Arrived arrive(
            XmageNativeStateRestoration.Plan plan,
            int startingLife
    ) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, plan.planId());
        XmageFullGameSession session = new XmageFullGameSession(
                plan.planId(), handles, 0, startingLife, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    private static XmageNativeStateRestoration.Plan plan(
            String id,
            int count,
            int life,
            List<XmageNativeStateRestoration.RequestedObject> objects
    ) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int i = 1; i <= count; i++) {
            String pid = "P" + i;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, i, life));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", "Rograkh, Son of Rohgahh", pid, 0));
        }
        return new XmageNativeStateRestoration.Plan(
                id, count, SEED, players, commanders, List.of(), objects,
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static XmageNativeStateRestoration.RequestedObject object(
            String id, String name, String owner, Zone zone
    ) {
        return new XmageNativeStateRestoration.RequestedObject(
                id, name, owner, owner, zone, false);
    }

    private static void advanceToOwnPrecombatMain(Arrived arrived, String actor) {
        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(),
                arrived.seats(),
                (session, seats, observed) ->
                        actor.equals(observed.get("active_player").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("phase").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("step").getAsString())
                                && actor.equals(observed.get("priority_player").getAsString()),
                progressionScript(),
                520);
    }

    private static XmageTemporalProgressionDriver.DecisionSource progressionScript() {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            if ("priority".equals(dc)) {
                return proposal("rg05-progress-pass-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(dc)) {
                return proposal("rg05-progress-hold-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            if ("declare_blocker".equals(dc)) {
                JsonObject p = XmageFullGameTaxExecutionTest.genericProposal(
                        "rg05-progress-no-block-" + index,
                        legal.get("actor_id").getAsString(), "", "structural_decision");
                p.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
                return p;
            }
            if ("choose_object".equals(dc)) {
                JsonObject context = pending.has("context")
                        && pending.get("context").isJsonObject()
                        ? pending.getAsJsonObject("context") : new JsonObject();
                String targetName = context.has("target_name")
                        && !context.get("target_name").isJsonNull()
                        ? context.get("target_name").getAsString() : "";
                if (!targetName.endsWith("to discard")) {
                    return null;
                }
                List<JsonObject> picked = resolveDiscardSelection(pending, legal);
                if (picked == null) {
                    return null;
                }
                return multiSelectProposal(
                        "rg05-discard-" + index,
                        legal,
                        picked,
                        "choose_targets");
            }
            return null;
        };
    }

    /**
     * Deterministic cleanup-discard transport.
     *
     * <p>The intended qualification choice is explicit: discard exactly the
     * native required count, preferring the highest stable semantic key
     * ({@code name|zone_index} from the authoritative offer, descending).
     * Fixture boards place expendable filler lands so needed spells sort
     * below the discard line, and each test asserts its needed cards
     * survive. Returns {@code null} (fail closed) when the pending decision
     * is not an exact-count discard. Throws when the semantic identity is
     * ambiguous or the keyed offer cannot satisfy the native cardinality.
     * Never a positional default: every selected option is bound by its
     * engine-exposed semantic key.</p>
     */
    static List<JsonObject> resolveDiscardSelection(JsonObject pending, JsonObject legal) {
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : new JsonObject();
        String targetName = context.has("target_name") && !context.get("target_name").isJsonNull()
                ? context.get("target_name").getAsString() : "";
        if (!targetName.endsWith("to discard")) {
            return null;
        }
        int min = pending.has("minimum_selections") && !pending.get("minimum_selections").isJsonNull()
                ? pending.get("minimum_selections").getAsInt() : -1;
        int max = pending.has("maximum_selections") && !pending.get("maximum_selections").isJsonNull()
                ? pending.get("maximum_selections").getAsInt() : -1;
        if (min < 0 || min != max) {
            return null;
        }
        List<DiscardOption> keyed = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject nativeMeta = nativeMeta(action);
            if (!nativeMeta.has("name") || !nativeMeta.has("zone_index")) {
                continue;
            }
            JsonElement zoneIndex = nativeMeta.get("zone_index");
            if (!zoneIndex.isJsonPrimitive() || !zoneIndex.getAsJsonPrimitive().isNumber()) {
                continue;
            }
            keyed.add(new DiscardOption(
                    nativeMeta.get("name").getAsString() + "|"
                            + zoneIndex.getAsJsonPrimitive().getAsInt(),
                    action));
        }
        keyed.sort((left, right) -> right.key().compareTo(left.key()));
        for (int i = 1; i < keyed.size(); i++) {
            if (keyed.get(i - 1).key().equals(keyed.get(i).key())) {
                throw new AssertionError(
                        "cleanup discard semantic key is ambiguous: " + keyed.get(i).key());
            }
        }
        if (keyed.size() < min) {
            throw new AssertionError("cleanup discard cannot satisfy exact native cardinality "
                    + min + " from " + keyed.size() + " semantically keyed options");
        }
        List<JsonObject> picked = new ArrayList<>();
        for (int i = 0; i < min; i++) {
            picked.add(keyed.get(i).action());
        }
        return picked;
    }

    private record DiscardOption(String key, JsonObject action) {}

    private static final class Script
            implements XmageControlDivergenceReconstruction.DecisionSource {
        private final List<UUID> targets;
        private final List<UUID> manaSources;
        private final String manaType;
        private int targetIndex;
        private int manaIndex;

        Script(List<UUID> targets, List<UUID> manaSources, String manaType) {
            this.targets = List.copyOf(targets);
            this.manaSources = List.copyOf(manaSources);
            this.manaType = manaType;
        }

        @Override
        public JsonObject choose(JsonObject pending, JsonObject legal, int decisionIndex) {
            String dc = pending.get("decision_class").getAsString();
            if ("target".equals(dc)) {
                int required = pending.has("minimum_selections")
                        ? pending.get("minimum_selections").getAsInt() : 1;
                List<JsonObject> selected = new ArrayList<>();
                for (int i = 0; i < required; i++) {
                    if (targetIndex >= targets.size()) {
                        throw new AssertionError("scripted target underflow");
                    }
                    selected.add(exactNativeObject(legal, targets.get(targetIndex++)));
                }
                return multiSelectProposal(
                        "rg05-target-" + decisionIndex, legal, selected, "choose_targets");
            }
            if ("mana_payment".equals(dc)) {
                JsonObject pool = exactManaPoolIfPresent(legal, manaType);
                if (pool != null) {
                    return proposal("rg05-pool-" + decisionIndex, legal, pool);
                }
                if (manaIndex >= manaSources.size()) {
                    throw new AssertionError("scripted mana-source underflow");
                }
                return proposal(
                        "rg05-mana-" + decisionIndex,
                        legal,
                        exactManaSource(legal, manaSources.get(manaIndex++)));
            }
            return null;
        }
    }

    private static JsonObject exactNativeObject(JsonObject legal, UUID wanted) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            if (wanted.toString().equals(text(nativeMeta(action), "object_id"))) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact target option");
        return matches.get(0);
    }

    private static JsonObject exactManaSource(JsonObject legal, UUID wanted) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if ("mana_ability".equals(text(metadata, "option_type"))
                    && wanted.toString().equals(text(nativeMeta(action), "source_object_id"))) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact mana source");
        return matches.get(0);
    }

    private static JsonObject exactManaPoolIfPresent(JsonObject legal, String manaType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if ("mana_pool".equals(text(metadata, "option_type"))
                    && manaType.equalsIgnoreCase(text(nativeMeta(action), "mana_type"))) {
                matches.add(action);
            }
        }
        return matches.size() == 1 ? matches.get(0) : null;
    }

    private static JsonObject multiSelectProposal(
            String id,
            JsonObject legal,
            List<JsonObject> selected,
            String actionType
    ) {
        JsonObject proposal = XmageFullGameTaxExecutionTest.genericProposal(
                id,
                legal.get("actor_id").getAsString(),
                selected.get(0).get("action_id").getAsString(),
                actionType);
        com.google.gson.JsonArray optionIds = new com.google.gson.JsonArray();
        for (JsonObject action : selected) {
            String actionId = action.get("action_id").getAsString();
            int split = actionId.indexOf(':');
            optionIds.add(actionId.substring(split + 1));
        }
        proposal.getAsJsonObject("choices").add("selected_option_ids", optionIds);
        return proposal;
    }

    @Test
    void discardSelectionPrefersHighestSemanticKey() {
        JsonObject pending = discardFrame(2, 2, "card to discard");
        JsonObject legal = discardLegal(
                discardOption("a1", "Mountain", 5),
                discardOption("a2", "Mountain", 3),
                discardOption("a3", "Control Magic", 1));
        List<JsonObject> picked = resolveDiscardSelection(pending, legal);
        assertNotNull(picked);
        assertEquals(2, picked.size());
        assertEquals("a1", picked.get(0).get("action_id").getAsString());
        assertEquals("a2", picked.get(1).get("action_id").getAsString());
    }

    @Test
    void discardSelectionFailsClosedOnAmbiguousKey() {
        JsonObject pending = discardFrame(1, 1, "card to discard");
        JsonObject legal = discardLegal(
                discardOption("a1", "Mountain", 5),
                discardOption("a2", "Mountain", 5));
        try {
            resolveDiscardSelection(pending, legal);
            throw new AssertionError("ambiguous semantic identity must fail closed");
        } catch (AssertionError expected) {
            assertTrue(expected.getMessage().contains("ambiguous"),
                    "unexpected failure: " + expected.getMessage());
        }
    }

    @Test
    void discardSelectionFailsClosedOnInsufficientCardinality() {
        JsonObject pending = discardFrame(2, 2, "card to discard");
        JsonObject legal = discardLegal(discardOption("a1", "Mountain", 5));
        try {
            resolveDiscardSelection(pending, legal);
            throw new AssertionError("insufficient cardinality must fail closed");
        } catch (AssertionError expected) {
            assertTrue(expected.getMessage().contains("cardinality"),
                    "unexpected failure: " + expected.getMessage());
        }
    }

    @Test
    void discardSelectionFailsClosedOnNonExactShape() {
        assertNull(resolveDiscardSelection(discardFrame(0, 2, "card to discard"),
                discardLegal(discardOption("a1", "Mountain", 5))));
        assertNull(resolveDiscardSelection(discardFrame(1, 1, "something else"),
                discardLegal(discardOption("a1", "Mountain", 5))));
    }

    private static JsonObject discardFrame(int min, int max, String targetName) {
        JsonObject pending = new JsonObject();
        pending.addProperty("minimum_selections", min);
        pending.addProperty("maximum_selections", max);
        JsonObject context = new JsonObject();
        context.addProperty("target_name", targetName);
        pending.add("context", context);
        return pending;
    }

    private static JsonObject discardLegal(JsonObject... actions) {
        JsonObject legal = new JsonObject();
        JsonArray array = new JsonArray();
        for (JsonObject action : actions) {
            array.add(action);
        }
        legal.add("actions", array);
        return legal;
    }

    private static JsonObject discardOption(String actionId, String name, int zoneIndex) {
        JsonObject action = new JsonObject();
        action.addProperty("action_id", actionId);
        JsonObject metadata = new JsonObject();
        metadata.addProperty("option_id", actionId);
        JsonObject nativeMeta = new JsonObject();
        nativeMeta.addProperty("name", name);
        nativeMeta.addProperty("zone_index", zoneIndex);
        metadata.add("xmage_option_metadata", nativeMeta);
        action.add("metadata", metadata);
        return action;
    }

    private static JsonObject nativeMeta(JsonObject action) {
        JsonObject metadata = action.has("metadata") && action.get("metadata").isJsonObject()
                ? action.getAsJsonObject("metadata") : new JsonObject();
        return metadata.has("xmage_option_metadata")
                && metadata.get("xmage_option_metadata").isJsonObject()
                ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
    }

    private static String text(JsonObject object, String key) {
        return object != null && object.has(key) && !object.get(key).isJsonNull()
                ? object.get(key).getAsString() : "";
    }

    private static JsonObject proposal(String id, JsonObject legal, JsonObject action) {
        return XmageCausalStackReconstruction.proposal(
                id, legal.get("actor_id").getAsString(), action);
    }

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
    }
}
