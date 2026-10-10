package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.MageObject;
import mage.abilities.Ability;
import mage.abilities.keyword.HexproofBaseAbility;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.target.Target;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.commanderlab.xmage.DecisionClassMatrixHarness.actions;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * #704 SLOT-06 follow-up 1b: L1 legal-action set-equality for decisions pending
 * <em>during a controlled turn</em> (CR 723.5), on the real pinned XMage engine
 * on the production full-game lane.
 *
 * <p>Turn control is production-reachable (Mindslaver, Emrakul, Worst Fears). The
 * set-up is genuine: P1 activates an actual Mindslaver naming P2, pays its real
 * {4} with real Islands, and the engine takes P2's next turn. Inside that turn
 * the controller (P1) makes P2's decisions, and every such frame is checked for
 * the full L1 obligation using the matrix oracle
 * {@link XmageFullGameDecisionClassMatrixTest#oracleFor} unchanged, so the
 * expected set comes from the engine's own API and never from the bridge's
 * {@code pending.legal_options}.</p>
 *
 * <h2>What each controlled-turn class must show</h2>
 * <ul>
 *   <li><b>L1 set-equality</b>: {@code get_legal_actions} is non-empty and
 *       set-equal to the engine oracle.</li>
 *   <li><b>Exact bounds</b>: min/max equal the engine's own required cardinality.</li>
 *   <li><b>Identity and revision binding</b>: offered actions and their ids are
 *       bound to this decision's id and offset; the native witness is served for
 *       this offset only; a submission naming a foreign decision id, a foreign
 *       revision or the controlled player's own principal is refused with a
 *       typed error and mutates neither the engine state nor the frame.</li>
 *   <li><b>Addressing</b> (CR 723.5): the frame is addressed to the controller
 *       (P1), names the controlled seat, and the controlled player's own
 *       principal is refused outright with no part of the decision.</li>
 *   <li><b>Engine-witnessed control relationship</b>: the engine itself names the
 *       controller of the controlled player's turn, and still reports turn control
 *       rather than game control, on every asserted frame. The bridge's own
 *       {@code acting_for_seat} is not the only witness of the relationship.</li>
 *   <li><b>CR 723.5 actor boundary</b>: on the controlled player's own targeted
 *       spell the controller's hexproof creature is absent from both the projection
 *       and the engine oracle, while the engine's own CR 509.1b predicate allows
 *       that very creature to that very source object when the controller is the
 *       deciding actor, so the difference is the actor relation and not the card
 *       list.</li>
 * </ul>
 *
 * <h2>Red controls</h2>
 * <p>Two mutated projections must fail the <em>same</em> assertion helper the
 * healthy frame passes, so a weakened helper cannot pass: one frame with a
 * single engine-offered option dropped (run over the priority, target and
 * choice classes) and one frame re-addressed to the controlled player's own
 * principal. Each is asserted to raise.</p>
 *
 * <h2>Oracle transport finding (CODE_DERIVED, observed by this test)</h2>
 * <p>{@link XmageFullGameSession#pendingNativeWitness()} resolves the witness
 * through {@code pending.actor_id}. On a controlled turn {@code actor_id} is
 * the <em>controller</em>, while the native callback that raised the decision
 * ran on the <em>controlled</em> player's {@link XmageFullGamePlayer} instance;
 * that accessor therefore returns an empty array for every controlled-turn
 * frame. The witness is intact and correctly bound to the same decision offset
 * on the controlled player's own instance, so this test reads it there. That is
 * a limitation of the test-only oracle transport under turn control, not a
 * bridge defect: the bridge never reads the witness and no production behaviour
 * depends on it. The matrix oracle remains the only source of the expected set.
 * The accessor is separately asserted to serve a frame of the controlled player's
 * <em>own</em> turn in this same game, so the claim is tied to this run and not
 * to the pin alone. The drive runs past the end of the controlled turn and the
 * number of controlled frames checked is counted and asserted to be greater than
 * one, so the empty-accessor behaviour is asserted on the whole controlled turn
 * and not merely on its first frame.</p>
 */
class XmageFullGameControlledTurnLegalActionsTest {

    private static final String CONTROLLER = "P1";
    private static final String CONTROLLED = "P2";
    private static final int SEATS = 2;

    private static final String CALLBACK_PRIORITY = "priority";
    private static final String CALLBACK_TARGET = "target";
    private static final String CALLBACK_CHOICE = "choice";

    /** The controlled player's own targeted spell, cast by the controller. */
    private static final String TARGETED_SPELL = "Lightning Bolt";
    /**
     * A real hexproof creature at the pin (Carnage Tyrant, {4}{G}{G}, trample,
     * hexproof) on the controller's battlefield. CR 509.1b keeps it out of the
     * controlled player's option set and nothing else does, so it witnesses that
     * the actor relation and not the card list decides the option set.
     */
    private static final String HEXPROOF_CREATURE = "Carnage Tyrant";

    @BeforeEach
    void orchestrationLaunch() {
        XmageRulesRngResultTape.keyForTests(new byte[32]);
    }

    @AfterEach
    void principalLaunch() {
        XmageRulesRngResultTape.keyForTests(null);
    }

    // ---- the three required classes ------------------------------------------

    @Test
    void priorityDuringAControlledTurnIsSetEqualToTheEngineOracle() {
        Frame frame = driveToControlledClass(CALLBACK_PRIORITY, 0);
        assertControlledTurnL1(frame);
    }

    @Test
    void targetedSpellDuringAControlledTurnIsSetEqualToTheEngineOracle() {
        Frame frame = driveToControlledClass(CALLBACK_TARGET, 1);
        assertControlledTurnL1(frame);
    }

    @Test
    void choiceDuringAControlledTurnIsSetEqualToTheEngineOracle() {
        Frame frame = driveToControlledClass(CALLBACK_CHOICE, 2);
        assertControlledTurnL1(frame);
    }

    // ---- red controls --------------------------------------------------------

    /**
     * Red control 1: a projection that drops one engine-offered option must fail
     * the same L1 helper the healthy frame passes. Run over every class this test
     * witnesses, so the helper cannot be weakened for one of them and stay green
     * for the others.
     */
    @ParameterizedTest(name = "{0}: a projection that drops an engine-offered option fails the same helper")
    @CsvSource({"priority, 0", "target, 1", "choice, 2"})
    void aProjectionThatDropsAnEngineOfferedOptionFailsTheSameHelper(
            String callback, int skipControlled) {
        Frame frame = driveToControlledClass(callback, skipControlled);
        assertControlledTurnL1(frame);

        JsonObject mutated = frame.frame.deepCopy();
        JsonArray offered = mutated.getAsJsonArray("actions");
        assertTrue(offered.size() > 1,
                "the red control needs a controlled-turn class with more than one engine option");
        Set<String> healthy = oracleForFrame(frame).projected();
        offered.remove(offered.size() - 1);
        // The dropped option must actually shrink the projection. If it did not,
        // this would be a no-op mutation and the control would prove nothing.
        Set<String> mutatedProjection = oracleForFrame(frame.withFrame(mutated)).projected();
        assertTrue(mutatedProjection.size() < healthy.size(),
                callback + ": dropping the last offered option must shrink the projection; "
                        + "labels " + DecisionClassMatrixHarness.labels(mutated));
        AssertionError dropped = assertThrows(
                AssertionError.class,
                () -> assertL1SetEquality(frame.withFrame(mutated)),
                "a projection missing an engine-offered option must fail L1 set-equality");
        assertTrue(String.valueOf(dropped.getMessage()).contains("engine option set"),
                dropped.getMessage());
    }

    /**
     * Red control 2: the same frame re-addressed to the controlled player's own
     * principal must fail the same helper, even though its option set is
     * unchanged. Set-equality alone cannot see this; CR 723.5 requires the
     * decision to be addressed to the controller.
     */
    @Test
    void aFrameAddressedToTheControlledPlayerFailsTheSameHelper() {
        Frame frame = driveToControlledClass(CALLBACK_TARGET, 1);
        assertControlledTurnL1(frame);

        JsonObject mutated = frame.frame.deepCopy();
        mutated.addProperty("actor_id", frame.controlledId.toString());
        for (JsonObject action : actions(mutated)) {
            action.addProperty("actor_id", frame.controlledId.toString());
        }
        AssertionError misaddressed = assertThrows(
                AssertionError.class,
                () -> assertAddressedToController(frame.withFrame(mutated)),
                "CR 723.5: a decision for a controlled player is addressed to the controller");
        assertTrue(String.valueOf(misaddressed.getMessage()).contains("addressed to the controller"),
                misaddressed.getMessage());
    }

    /**
     * The controlled player's own principal is refused outright and receives no
     * part of the decision, on a live controlled-turn frame.
     */
    @Test
    void theControlledPlayersPrincipalIsRefusedTheControlledTurnDecision() {
        Frame frame = driveToControlledClass(CALLBACK_TARGET, 1);
        assertControlledTurnL1(frame);

        JsonObject asControlled = new JsonObject();
        asControlled.addProperty("actor_id", frame.controlledId.toString());
        XmageFullGameDecisionController.DecisionException refused = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> frame.live.session().legalActionsPayload(asControlled));
        assertTrue(refused.getMessage().startsWith("WRONG_ACTOR"), refused.getMessage());
    }

    /**
     * The oracle transport finding, asserted rather than only narrated:
     * {@code pendingNativeWitness()} resolves through {@code pending.actor_id},
     * so on a controlled turn it returns nothing while the same decision's
     * witness is intact on the controlled player's own player instance. This is
     * what makes the controlled turn witnessable with the matrix oracle at all,
     * and it is a test-only transport limitation, not a bridge defect.
     */
    @Test
    void theOracleWitnessIsOnTheControlledPlayerWhileTheSessionAccessorCannotSeeIt() {
        XmageMultiplayerScenario scenario = controlledGame();
        Game game = scenario.session.restorationGame();
        boolean sawUncontrolledWitness = false;
        boolean controlledWithAccessorWitness = false;
        boolean controlledWithoutAccessorWitness = false;
        boolean sawControlled = false;
        boolean controlledTurnEnded = false;
        boolean mindslaverActivated = false;
        int[] castsDone = {0};
        int[] controlledFramesChecked = {0};
        List<String> trace = new ArrayList<>();
        // Driven past the end of the controlled turn, so the consistency claim
        // below covers every controlled frame of that turn and not just the first.
        for (int guard = 0; guard < 300 && !(sawControlled && controlledTurnEnded
                && sawUncontrolledWitness); guard++) {
            JsonObject payload = scenario.session.legalActionsPayload();
            String cls = payload.get("decision_class").getAsString();
            String active = XmageNativeStateRestorationTest.pidOf(
                    scenario.seats, game.getActivePlayerId().toString());
            boolean controlledNow = CONTROLLED.equals(active)
                    && payload.getAsJsonObject("decision").has("acting_for_seat");
            trace.add(cls + (controlledNow ? "(controlled)" : ""));
            long offset = payload.get("decision_offset").getAsLong();
            if (controlledNow) {
                sawControlled = true;
                controlledFramesChecked[0]++;
                Object[] viaAccessor = scenario.session.pendingNativeWitness();
                Object[] viaControlled = ((XmageFullGamePlayer) scenario.seats.get(CONTROLLED))
                        .nativeWitness(offset);
                if (viaAccessor.length == 0) {
                    controlledWithoutAccessorWitness = true;
                    // The witness is not merely absent: the engine still holds it,
                    // bound to this same decision revision, on the controlled player.
                    assertTrue(viaControlled.length > 0,
                            "the engine must still hold the pending decision's witness "
                                    + "on the controlled player at offset " + offset);
                    assertEquals(nativeCallbackFor(cls), String.valueOf(viaControlled[0]),
                            "the controlled player's witness must be this decision's own callback");
                } else {
                    controlledWithAccessorWitness = true;
                }
            } else if (payload.get("actor_id").getAsString()
                    .equals(scenario.seats.get(CONTROLLED).getId().toString())
                    && scenario.session.pendingNativeWitness().length > 0) {
                sawUncontrolledWitness = true;
            }
            if (sawControlled && !controlledNow && !CONTROLLED.equals(active)) {
                controlledTurnEnded = true;
            }
            if (!mindslaverActivated && "priority".equals(cls) && CONTROLLER.equals(active)
                    && !controlledNow) {
                JsonObject mindslaver = scenario.action("activate_ability", "Mindslaver");
                assertNotNull(mindslaver, "Mindslaver must be offered on P1's own turn");
                scenario.submit(mindslaver);
                mindslaverActivated = true;
                continue;
            }
            answerControlledFrame(scenario, game, cls, active, controlledNow, castsDone);
        }
        assertTrue(sawControlled, "the real controlled turn must be reached; trace " + trace);
        assertTrue(controlledTurnEnded,
                "the drive must run past the end of the controlled turn so the accessor "
                        + "behaviour is checked on the whole turn, not on its first frames; trace "
                        + trace);
        assertTrue(controlledFramesChecked[0] > 1,
                "the accessor behaviour must be checked on more than the first controlled frame; "
                        + "checked " + controlledFramesChecked[0] + ", trace " + trace);
        assertTrue(controlledWithoutAccessorWitness,
                "pendingNativeWitness() resolves through the controller's actor_id and so "
                        + "cannot serve a controlled-turn decision");
        assertFalse(controlledWithAccessorWitness,
                "the accessor behaviour must be consistent across the controlled turn");
        assertTrue(sawUncontrolledWitness,
                "the same accessor does serve a frame of the controlled player's own turn in "
                        + "this same game, so the empty witness is specific to turn control and "
                        + "not a broken accessor");
    }

    // ---- the L1 helper the controls share -----------------------------------

    /**
     * The complete controlled-turn L1 obligation for one live frame. Every check
     * below is reused verbatim by the red controls, so weakening any of them lets
     * a control pass.
     */
    private static void assertControlledTurnL1(Frame frame) {
        assertAddressedToController(frame);
        assertBoundToDecisionIdentityAndRevision(frame);
        assertExactBounds(frame);
        assertHexproofIsActorRelative(frame, assertL1SetEquality(frame));
    }

    /** CR 723.5 addressing: the controller decides, and the controlled seat is named. */
    private static void assertAddressedToController(Frame frame) {
        assertEquals(frame.controllerId.toString(), frame.frame.get("actor_id").getAsString(),
                "CR 723.5: the decision must be addressed to the controller "
                        + CONTROLLER + ", not the controlled " + CONTROLLED);
        JsonObject decision = frame.frame.getAsJsonObject("decision");
        assertTrue(decision.has("acting_for_seat"),
                "a controlled-turn decision must name the controlled seat");
        assertEquals(frame.controlledSeat, decision.get("acting_for_seat").getAsInt(),
                "CR 723.5: acting_for_seat must name the controlled seat " + CONTROLLED);
        assertEquals(frame.controllerSeat, decision.get("seat").getAsInt(),
                "the deciding seat must be the controller's own seat");
        for (JsonObject action : actions(frame.frame)) {
            assertEquals(frame.controllerId.toString(), action.get("actor_id").getAsString(),
                    "every offered action must name the controller as its actor");
        }
    }

    /**
     * Decision identity and revision binding, on both sides: the offered actions
     * belong to this decision id and offset, the engine serves this decision's
     * native witness for this offset only, and a submission bound to a foreign
     * identity, a foreign revision or the controlled principal fails closed with
     * a typed error and mutates nothing.
     */
    private static void assertBoundToDecisionIdentityAndRevision(Frame frame) {
        XmageFullGameSession session = frame.live.session();
        String decisionId = frame.frame.get("decision_id").getAsString();
        long offset = frame.frame.get("decision_offset").getAsLong();
        JsonObject decision = frame.frame.getAsJsonObject("decision");
        assertEquals(decisionId, decision.get("decision_id").getAsString());
        assertEquals(offset, decision.get("decision_offset").getAsLong());

        for (JsonObject action : actions(frame.frame)) {
            JsonObject metadata = action.getAsJsonObject("metadata");
            assertEquals(decisionId, metadata.get("decision_id").getAsString(),
                    "every offered action must be bound to this decision id");
            assertEquals(offset, metadata.get("decision_offset").getAsLong(),
                    "every offered action must be bound to this decision revision");
            assertTrue(action.get("action_id").getAsString().startsWith(decisionId + ":"),
                    "an action id must be namespaced by its decision id: "
                            + action.get("action_id").getAsString());
        }

        XmageFullGamePlayer controlled = (XmageFullGamePlayer) frame.live.seats().get(CONTROLLED);
        assertEquals(0, controlled.nativeWitness(offset - 1).length,
                "the native witness must not be served for another revision");
        assertEquals(0, controlled.nativeWitness(offset + 1).length,
                "the native witness must not be served for another revision");

        String stateBefore = XmageNativeStateRestoration.readback(
                session.restorationGame(), frame.live.seats()).toString();
        String digestBefore = session.privilegedStateDigest();
        int transcriptBefore = session.controllerTranscript().size();
        long countBefore = session.pendingDecisionPayload().get("decision_count").getAsLong();
        JsonObject offered0 = actions(frame.frame).get(0);

        JsonObject foreignId = DecisionClassMatrixHarness.proposal(frame.frame, offered0).deepCopy();
        foreignId.getAsJsonObject("choices").addProperty("decision_id", "0".repeat(64));
        assertRejected(frame, foreignId, "STALE_DECISION", "a foreign decision id");

        JsonObject foreignOffset = DecisionClassMatrixHarness.proposal(frame.frame, offered0).deepCopy();
        foreignOffset.getAsJsonObject("choices").addProperty("decision_offset", offset + 1);
        assertRejected(frame, foreignOffset, "STALE_DECISION", "a foreign decision revision");

        JsonObject asControlled = DecisionClassMatrixHarness.proposal(frame.frame, offered0).deepCopy();
        asControlled.addProperty("actor_id", frame.controlledId.toString());
        assertRejected(frame, asControlled, "PILOT_RESPONSE_INVALID: wrong actor",
                "the controlled player's own principal");

        assertEquals(stateBefore, XmageNativeStateRestoration.readback(
                session.restorationGame(), frame.live.seats()).toString(),
                "a refused submission must not mutate the game");
        assertEquals(digestBefore, session.privilegedStateDigest(),
                "a refused submission must not change the privileged engine state");
        assertEquals(transcriptBefore, session.controllerTranscript().size(),
                "a refused submission must not append a transcript event");
        assertEquals(countBefore,
                session.pendingDecisionPayload().get("decision_count").getAsLong(),
                "a refused submission must not advance the decision count");
    }

    private static void assertRejected(Frame frame, JsonObject proposal, String code, String what) {
        XmageFullGameDecisionController.DecisionException rejected = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> frame.live.session().submitAction(proposal),
                "must reject " + what);
        assertNotNull(rejected.getMessage());
        assertTrue(rejected.getMessage().startsWith(code),
                what + ": expected " + code + ", got " + rejected.getMessage());
    }

    /**
     * Exact min/max. Each class under test is one the engine requires exactly one
     * answer to (one priority action, one target, one choice), so the bound must
     * be exactly 1/1 rather than a range that happens to contain 1.
     */
    private static void assertExactBounds(Frame frame) {
        JsonObject decision = frame.frame.getAsJsonObject("decision");
        assertEquals(1, decision.get("minimum_selections").getAsInt(),
                frame.callback + ": the engine requires exactly one answer (min)");
        assertEquals(1, decision.get("maximum_selections").getAsInt(),
                frame.callback + ": the engine requires exactly one answer (max)");
        assertFalse(actions(frame.frame).isEmpty(),
                frame.callback + ": a 1/1 frame must offer at least one engine option");
    }

    /**
     * L1 set-equality against the matrix oracle. The oracle is handed a frame
     * addressed to the controlled player, because the engine callback that
     * offered these options ran on that player's own object; the option set is a
     * property of that callback, not of the principal the frame is served to.
     *
     * @return the oracle, so a caller can assert against the engine's own option
     *         set without recomputing it from the projection
     */
    private static XmageFullGameDecisionClassMatrixTest.Oracle assertL1SetEquality(Frame frame) {
        XmageFullGameDecisionClassMatrixTest.Oracle oracle = oracleForFrame(frame);
        Set<String> projected = oracle.projected();
        assertFalse(projected.isEmpty(),
                frame.callback + ": get_legal_actions must not be empty during a controlled turn");
        assertEquals(oracle.expected(), projected,
                frame.callback + ": projection must equal the engine option set");
        return oracle;
    }

    /** The matrix oracle for this frame, computed only from the engine API. */
    private static XmageFullGameDecisionClassMatrixTest.Oracle oracleForFrame(Frame frame) {
        JsonObject oracleFrame = frame.frame.deepCopy();
        oracleFrame.addProperty("actor_id", frame.controlledId.toString());
        return XmageFullGameDecisionClassMatrixTest.oracleFor(
                frame.callback, frame.live, oracleFrame, frame.witness);
    }

    /**
     * CR 723.5 actor boundary, engine-witnessed: on the controlled player's own
     * targeted spell the controller's hexproof creature is in neither the
     * projection nor the engine oracle, while the engine's own CR 509.1b
     * predicate says that very creature is targetable by the very same source
     * object when the controller is the deciding actor. So what separates the two
     * option sets is the actor relation and not the card list.
     *
     * <p>The actor-relative instrument is {@link Permanent#canBeTargetedBy}, not
     * {@code Target.possibleTargets} with another actor: for this target type
     * {@code TargetPermanentOrPlayer.canTarget(playerId, id, source, game)}
     * discards {@code playerId} and applies hexproof against
     * {@code source.getControllerId()}, so passing a different actor to
     * {@code possibleTargets} does not widen the set. That is asserted below, so
     * this test cannot be quietly "simplified" into a probe that proves nothing.</p>
     */
    private static void assertHexproofIsActorRelative(
            Frame frame, XmageFullGameDecisionClassMatrixTest.Oracle oracle) {
        if (!CALLBACK_TARGET.equals(frame.callback)) {
            return;
        }
        Game game = frame.live.session().restorationGame();
        Target target = (Target) frame.witness[1];
        Ability source = (Ability) frame.witness[2];
        Card sourceCard = game.getCard(source.getSourceId());
        assertNotNull(sourceCard, "the target frame must be raised by a real card");
        assertEquals(TARGETED_SPELL, sourceCard.getName(),
                "this frame must be the controlled player's own targeted spell");
        Permanent hexproof = hexproofPermanent(game);
        String hexproofId = hexproof.getId().toString();
        assertFalse(oracle.expected().contains(hexproofId),
                "CR 509.1b: the controller's hexproof creature must be absent from the engine oracle");
        assertFalse(oracle.projected().contains(hexproofId),
                "CR 509.1b: the controller's hexproof creature must be absent from the projection");
        MageObject sourceObject = game.getObject(source.getId());
        assertFalse(hexproof.canBeTargetedBy(sourceObject, frame.controlledId, source, game),
                "CR 509.1b: the controlled player's own spell must not be able to target "
                        + "the controller's hexproof creature");
        assertTrue(hexproof.canBeTargetedBy(sourceObject, frame.controllerId, source, game),
                "CR 509.1b with CR 723.5: the same source object may target the same creature "
                        + "when the controller is the deciding actor, so the option sets differ "
                        + "because of the actor relation and not the card list");
        assertFalse(target.possibleTargets(frame.controllerId, source, game).contains(hexproofId),
                "this target type applies hexproof against the source's own controller, so "
                        + "possibleTargets is not the actor-relative instrument here");
    }

    /**
     * The controller's hexproof creature on the battlefield, as the permanent.
     * Its hexproof is asserted on the permanent itself, so this cannot pass by
     * naming a card that has lost the ability at the pin.
     */
    private static Permanent hexproofPermanent(Game game) {
        for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
            if (HEXPROOF_CREATURE.equals(permanent.getName())) {
                assertTrue(permanent.getAbilities().stream()
                                .anyMatch(HexproofBaseAbility.class::isInstance),
                        "CR 509.1b: the set-up creature must really have hexproof at this pin");
                return permanent;
            }
        }
        throw new AssertionError("the controller's " + HEXPROOF_CREATURE
                + " must be on the battlefield for the CR 723.5 actor-boundary witness");
    }

    // ---- the controlled-turn drive -------------------------------------------

    /**
     * One live controlled-turn frame plus everything the oracle and the helper
     * need: the seats, the native witness as the controlled player's own engine
     * callback arguments, and that player's id.
     */
    private static final class Frame {
        private final DecisionClassMatrixHarness.Live live;
        private final JsonObject frame;
        private final String callback;
        private final Object[] witness;
        private final UUID controllerId;
        private final UUID controlledId;
        private final int controllerSeat;
        private final int controlledSeat;

        private Frame(DecisionClassMatrixHarness.Live live, JsonObject frame, String callback,
                      Object[] witness, UUID controllerId, UUID controlledId,
                      int controllerSeat, int controlledSeat) {
            this.live = live;
            this.frame = frame;
            this.callback = callback;
            this.witness = witness;
            this.controllerId = controllerId;
            this.controlledId = controlledId;
            this.controllerSeat = controllerSeat;
            this.controlledSeat = controlledSeat;
        }

        Frame withFrame(JsonObject replacement) {
            return new Frame(live, replacement, callback, witness,
                    controllerId, controlledId, controllerSeat, controlledSeat);
        }
    }

    /**
     * Drive a real 2P game: P1 activates an actual Mindslaver naming P2, pays it,
     * and the engine takes P2's next turn. Every controlled-turn frame is
     * answered by the declared test pilot until the requested native callback
     * appears there after {@code skipControlled} earlier controlled-turn frames;
     * that frame is returned live and unmutated.
     */
    private static Frame driveToControlledClass(String callback, int skipControlled) {
        XmageMultiplayerScenario scenario = controlledGame();
        Game game = scenario.session.restorationGame();
        DecisionClassMatrixHarness.Live live =
                new DecisionClassMatrixHarness.Live(scenario.session, scenario.seats);
        UUID controllerId = scenario.seats.get(CONTROLLER).getId();
        UUID controlledId = scenario.seats.get(CONTROLLED).getId();
        int controllerSeat = XmageFullGameStateRedactor.seat(game, controllerId);
        int controlledSeat = XmageFullGameStateRedactor.seat(game, controlledId);

        boolean mindslaverActivated = false;
        int[] castsDone = {0};
        int seenControlled = 0;
        List<String> trace = new ArrayList<>();
        for (int guard = 0; guard < 200; guard++) {
            JsonObject payload = scenario.session.legalActionsPayload();
            String cls = payload.get("decision_class").getAsString();
            String actor = XmageNativeStateRestorationTest.pidOf(
                    scenario.seats, payload.get("actor_id").getAsString());
            String active = XmageNativeStateRestorationTest.pidOf(
                    scenario.seats, game.getActivePlayerId().toString());
            boolean controlledNow = CONTROLLED.equals(active)
                    && payload.getAsJsonObject("decision").has("acting_for_seat");
            trace.add(cls + "/" + actor + (controlledNow ? "(controlled)" : ""));

            if (controlledNow) {
                seenControlled++;
                if (seenControlled > skipControlled && callback.equals(cls)) {
                    return buildFrame(live, payload, callback,
                            controllerId, controlledId, controllerSeat, controlledSeat);
                }
            }
            if (!mindslaverActivated && "priority".equals(cls) && CONTROLLER.equals(active)
                    && !controlledNow) {
                JsonObject mindslaver = scenario.action("activate_ability", "Mindslaver");
                assertNotNull(mindslaver, "Mindslaver must be offered on P1's own turn");
                scenario.submit(mindslaver);
                mindslaverActivated = true;
                continue;
            }
            answerControlledFrame(scenario, game, cls, active, controlledNow, castsDone);
        }
        fail("no " + callback + " frame during a controlled turn; trace " + trace);
        throw new AssertionError("unreachable");
    }

    /**
     * Declared test pilot for every frame that is not the target: pass priority
     * except at the scripted casts, pay real costs, hold attackers, and take the
     * first engine-offered option on any other controlled-turn frame (the
     * choice, and anything else the engine raises).
     */
    private static void answerControlledFrame(
            XmageMultiplayerScenario scenario, Game game, String cls, String active,
            boolean controlledNow, int[] castsDone) {
        if ("priority".equals(cls)) {
            // Scripted casts run only on an empty stack, so each spell is cast
            // once and its own decisions resolve before the next.
            if (controlledNow && game.getStack().isEmpty() && castsDone[0] < 2) {
                String wanted = castsDone[0] == 0
                        ? "Cast " + TARGETED_SPELL : "Cast Painter's Servant";
                JsonObject cast = scenario.action("activate_ability", wanted);
                if (cast != null) {
                    scenario.submit(cast);
                    castsDone[0]++;
                    return;
                }
            }
            JsonObject pass = scenario.action("pass_priority", "Pass");
            assertNotNull(pass, "every priority frame must offer the engine's pass action");
            scenario.submit(pass);
            return;
        }
        if ("mana_payment".equals(cls)) {
            payDeclaredMana(scenario);
            return;
        }
        if ("target".equals(cls)) {
            JsonObject seatTwo = scenario.action("choose_targets", "Full Game Seat 2");
            JsonObject frame = scenario.session.legalActionsPayload();
            scenario.submit(seatTwo != null ? seatTwo : actions(frame).get(0));
            return;
        }
        if ("declare_attacker".equals(cls)) {
            JsonObject hold = scenario.action("hold_attacker", "Do not attack");
            if (hold != null) {
                scenario.submit(hold);
                return;
            }
        }
        JsonObject frame = scenario.session.legalActionsPayload();
        submitDeclaredAnswer(scenario, frame);
    }

    /**
     * Declared test-pilot answer for a frame this drive did not script: select the
     * exact number of options the frame's own bounds require, taken from the
     * engine-offered option ids, so a frame needing several selections is
     * answered completely rather than partially.
     */
    private static void submitDeclaredAnswer(XmageMultiplayerScenario scenario, JsonObject frame) {
        List<JsonObject> offered = actions(frame);
        assertFalse(offered.isEmpty(), "a declared answer needs at least one engine option");
        JsonObject decision = frame.getAsJsonObject("decision");
        int min = decision.get("minimum_selections").getAsInt();
        int max = decision.get("maximum_selections").getAsInt();
        int count = Math.min(Math.max(min, 1), Math.min(max, offered.size()));
        if (count <= 1) {
            scenario.submit(offered.get(0));
            return;
        }
        JsonObject proposal = DecisionClassMatrixHarness.proposal(frame, offered.get(0));
        JsonArray selected = new JsonArray();
        for (int index = 0; index < count; index++) {
            selected.add(XmageFullGameDecisionClassMatrixTest.optionId(offered.get(index)));
        }
        proposal.getAsJsonObject("choices").add("selected_option_ids", selected);
        XmageFullGameSession session = scenario.session;
        JsonObject executed = session.submitAction(proposal);
        assertEquals(frame.get("decision_id").getAsString(),
                executed.get("executed_decision_id").getAsString(),
                "the declared multi-selection must execute the pending decision");
    }

    /**
     * Declared test-pilot payment, identical in policy to the matrix harness:
     * spend pool mana that actually advances the payment, else the first
     * engine-offered mana ability. It never depends on the controlled player
     * having a particular land, so it also pays a red cost the controlled
     * player's Plains could not pay.
     */
    private static void payDeclaredMana(XmageMultiplayerScenario scenario) {
        for (int round = 0; round < 20
                && "mana_payment".equals(scenario.decisionClass()); round++) {
            JsonObject frame = scenario.session.legalActionsPayload();
            JsonObject chosen = null;
            for (String type : List.of("mana_pool", "mana_ability")) {
                for (JsonObject action : actions(frame)) {
                    boolean advances = !"mana_pool".equals(type)
                            || "true".equals(DecisionClassMatrixHarness.nativeField(
                            action, "advances_payment"));
                    if (chosen == null && advances
                            && type.equals(DecisionClassMatrixHarness.optionType(action))) {
                        chosen = action;
                    }
                }
            }
            if (chosen == null) {
                fail("mana payment without an advancing engine option "
                        + DecisionClassMatrixHarness.labels(frame));
            }
            scenario.submit(chosen);
        }
    }

    private static Frame buildFrame(
            DecisionClassMatrixHarness.Live live, JsonObject payload, String callback,
            UUID controllerId, UUID controlledId, int controllerSeat, int controlledSeat) {
        // CR 723.5 engine-witnessed, not only bridge-witnessed. The bridge's own
        // acting_for_seat proves how the bridge routed the frame; these assertions
        // prove the engine itself holds the control relationship on this frame.
        Game game = live.session().restorationGame();
        Player controlledPlayer = game.getPlayer(controlledId);
        assertNotNull(controlledPlayer, callback + ": the controlled player must still be in play");
        assertEquals(controlledId, game.getActivePlayerId(),
                callback + ": this frame must be pending on the controlled player's own turn");
        assertEquals(controllerId, controlledPlayer.getTurnControlledBy(),
                "CR 723.5: the engine must name the controller as controlling this player's turn");
        assertFalse(controlledPlayer.isGameUnderControl(),
                "this is turn control, not game control: a game-under-control relationship "
                        + "would make the CR 723.5 actor boundary unobservable here");
        long offset = payload.get("decision_offset").getAsLong();
        // Oracle transport: the native callback ran on the controlled player's own
        // XmageFullGamePlayer instance (see the class javadoc).
        Object[] witness = ((XmageFullGamePlayer) live.seats().get(CONTROLLED))
                .nativeWitness(offset);
        assertTrue(witness.length > 0,
                callback + ": the controlled player's native witness must be bound to this decision");
        assertEquals(nativeCallbackFor(callback), String.valueOf(witness[0]),
                callback + ": the controlled-turn decision was raised by another native callback");
        return new Frame(live, payload, callback, witness,
                controllerId, controlledId, controllerSeat, controlledSeat);
    }

    /**
     * The native callback kind a projected decision class is raised by. The
     * bridge's {@code choose_object} frames, for instance, are raised by the
     * native {@code chooseTarget} callback whose witness kind is {@code "target"};
     * comparing the projected class name against the witness directly would be
     * wrong for those. The mapping is the matrix test's own, reused unchanged, and
     * an unmapped class fails closed rather than being compared blindly.
     */
    private static String nativeCallbackFor(String decisionClass) {
        String nativeCallback =
                XmageFullGameDecisionClassMatrixTest.EXPECTED_CALLBACK.get(decisionClass);
        assertNotNull(nativeCallback,
                "every decision class this drive meets must name its native callback kind: "
                        + decisionClass);
        return nativeCallback;
    }

    /**
     * The real controlled-turn set-up: an actual Mindslaver on P1's battlefield
     * with the four Islands its {4} needs, and on P2's side a Lightning Bolt (a
     * targeted spell) and a Painter's Servant (an AsEntersBattlefieldAbility
     * colour choice) to cast during the controlled turn, plus the lands to pay
     * them. P1 also controls a real hexproof creature, which CR 509.1b keeps out
     * of P2's own option set while leaving that same permanent targetable by the
     * same Lightning Bolt once P1 is the deciding actor.
     */
    private static XmageMultiplayerScenario controlledGame() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj(CONTROLLER, "Mindslaver", 0, Zone.BATTLEFIELD));
        for (int index = 1; index <= 4; index++) {
            objects.add(XmageMultiplayerScenario.obj(CONTROLLER, "Island", index, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj(CONTROLLED, TARGETED_SPELL, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(CONTROLLED, "Painter's Servant", 1, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(CONTROLLED, "Mountain", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj(CONTROLLED, "Plains", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj(CONTROLLED, "Plains", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj(CONTROLLER, HEXPROOF_CREATURE, 5, Zone.BATTLEFIELD));
        return XmageMultiplayerScenario.start("controlled-turn-l1-" + SEATS + "p",
                SEATS, CONTROLLER, objects);
    }
}