package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.constants.Zone;
import mage.game.Game;
import mage.players.Player;
import mage.target.Target;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import static org.commanderlab.xmage.DecisionClassMatrixHarness.Placed;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.Scenario;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.Step;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.actions;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.labels;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.nativeField;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.optionType;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.pass;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.proposal;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.sorted;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.step;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 per-decision-class matrix on the full-game production lane.
 *
 * <p>For each decision class, a native-restored scenario reaches one real pending
 * decision of that class, and the test checks:</p>
 * <ul>
 *   <li>L1: {@code get_legal_actions} is non-empty and set-equal to the engine's
 *       option set. The test computes that set itself from the native callback
 *       arguments ({@link XmageFullGameSession#pendingNativeWitness()}) and the
 *       live game through the engine's own API, never from the bridge's
 *       {@code legal_options}.</li>
 *   <li>S1: every offered action, submitted in a fresh identical session at the
 *       same frame, is accepted, and the pending decision advances.</li>
 *   <li>S2: a stale offset, a stale decision id, a wrong actor, an option that was
 *       not offered and a malformed proposal each fail with a typed error, and the
 *       privileged engine-state digest, decision identity and decision count are
 *       unchanged afterwards.</li>
 * </ul>
 *
 * <p>Every class the lane can emit appears either here or in
 * {@link XmageFullGameDecisionClassInventoryTest} with a code reason.</p>
 */
class XmageFullGameDecisionClassMatrixTest {

    static final Map<String, Scenario> SCENARIOS = new LinkedHashMap<>();

    /**
     * The native callback each scenario's target decision must come from; the
     * oracle is chosen by it. "ring_bearer" is the delegation case: the ring-bearer
     * prompt raises its decision through the target callback.
     */
    static final Map<String, String> EXPECTED_CALLBACK = Map.ofEntries(
            Map.entry("priority", "priority"),
            Map.entry("target", "target"),
            Map.entry("mana_payment", "mana_payment"),
            Map.entry("target_amount", "target_amount"),
            Map.entry("mode", "mode"),
            Map.entry("announce_x", "announce_x"),
            Map.entry("trigger_order", "trigger_order"),
            Map.entry("choice", "choice"),
            Map.entry("replacement_effect", "replacement_effect"),
            Map.entry("choose_object", "target"),
            Map.entry("pile", "pile"),
            Map.entry("declare_attacker", "declare_attacker"),
            Map.entry("declare_blocker", "declare_blocker"),
            Map.entry("multi_amount_combat", "multi_amount"),
            Map.entry("amount", "amount"),
            Map.entry("choose_use", "choose_use"),
            Map.entry("multi_amount", "multi_amount"),
            Map.entry("ring_bearer", "target"),
            Map.entry("cast_ability", "cast_ability"),
            Map.entry("land_or_spell", "land_or_spell"),
            Map.entry("starting_player", "target"),
            Map.entry("mulligan", "mulligan"),
            Map.entry("london_bottom", "target"),
            Map.entry("london_bottom_two", "target"));

    static {
        SCENARIOS.put("priority", new Scenario("matrix-priority", 66201L,
                List.of(Placed.hand("P1", "Lightning Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Grizzly Bears")),
                List.of(), "priority", "P1"));
        SCENARIOS.put("target", new Scenario("matrix-target", 66202L,
                List.of(Placed.hand("P1", "Lightning Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Lightning Bolt")),
                "target", "P1"));
        SCENARIOS.put("mana_payment", new Scenario("matrix-mana-payment", 66203L,
                List.of(Placed.hand("P1", "Lightning Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Plains")),
                // Float first, then reach the payment frame that offers the
                // pool: the tapped Mountain's mana sits in the pool and XMage
                // offers it as mana_pool options (autoPayment is off, so the
                // engine only spends the pool once a type is unlocked).
                List.of(step("priority", "P1", "Cast Lightning Bolt"),
                        new Step("target", "P1", "target P2",
                                action -> label(action).equals("Full Game Seat 2")),
                        DecisionClassMatrixHarness.tapLand("mana_payment", "P1")),
                "mana_payment", "P1"));
        SCENARIOS.put("target_amount", new Scenario("matrix-target-amount", 66204L,
                List.of(Placed.hand("P1", "Forked Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Forked Bolt")),
                "target_amount", "P1"));
        SCENARIOS.put("mode", new Scenario("matrix-mode", 66205L,
                List.of(Placed.hand("P1", "Boros Charm"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Plains"),
                        Placed.battlefield("P1", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Boros Charm")),
                "mode", "P1"));
        SCENARIOS.put("announce_x", new Scenario("matrix-announce-x", 66206L,
                List.of(Placed.hand("P1", "Blaze"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain")),
                List.of(step("priority", "P1", "Cast Blaze")),
                "announce_x", "P1"));
        SCENARIOS.put("trigger_order", new Scenario("matrix-trigger-order", 66207L,
                List.of(Placed.hand("P1", "Grizzly Bears"),
                        Placed.battlefield("P1", "Forest"),
                        Placed.battlefield("P1", "Forest"),
                        Placed.battlefield("P1", "Soul Warden"),
                        Placed.battlefield("P1", "Soul Warden")),
                List.of(step("priority", "P1", "Cast Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("trigger_order", "P1")),
                "trigger_order", "P1"));
        SCENARIOS.put("choice", new Scenario("matrix-choice", 66208L,
                List.of(Placed.hand("P1", "Painter's Servant"),
                        Placed.battlefield("P1", "Plains"),
                        Placed.battlefield("P1", "Plains")),
                List.of(step("priority", "P1", "Cast Painter's Servant"),
                        DecisionClassMatrixHarness.passUntil("choice", "P1")),
                "choice", "P1"));
        SCENARIOS.put("replacement_effect", new Scenario("matrix-replacement", 66209L,
                List.of(Placed.hand("P1", "Battlegrowth"),
                        Placed.battlefield("P1", "Forest"),
                        Placed.battlefield("P1", "Hardened Scales"),
                        Placed.battlefield("P1", "Corpsejack Menace"),
                        Placed.battlefield("P1", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Battlegrowth"),
                        step("target", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("replacement_effect", "P1")),
                "replacement_effect", "P1"));
        SCENARIOS.put("choose_object", new Scenario("matrix-choose-object", 66210L,
                List.of(Placed.hand("P1", "Fact or Fiction"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Fact or Fiction"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P2")),
                "choose_object", "P2"));
        SCENARIOS.put("pile", new Scenario("matrix-pile", 66210L,
                List.of(Placed.hand("P1", "Fact or Fiction"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Fact or Fiction"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P2"),
                        DecisionClassMatrixHarness.selectNone("choose_object", "P2")),
                "pile", "P1"));
        SCENARIOS.put("declare_attacker", new Scenario("matrix-attack", 66211L,
                List.of(Placed.battlefield("P1", "Grizzly Bears")),
                List.of(DecisionClassMatrixHarness.passUntil("declare_attacker", "P1")),
                "declare_attacker", "P1"));
        SCENARIOS.put("declare_blocker", new Scenario("matrix-block", 66214L,
                List.of(Placed.battlefield("P1", "Colossal Dreadmaw"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(DecisionClassMatrixHarness.passUntil("declare_attacker", "P1"),
                        step("declare_attacker", "P1", "attacks"),
                        DecisionClassMatrixHarness.passUntil("declare_blocker", "P2")),
                "declare_blocker", "P2"));
        SCENARIOS.put("multi_amount_combat", new Scenario("matrix-trample", 66214L,
                List.of(Placed.battlefield("P1", "Colossal Dreadmaw"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(DecisionClassMatrixHarness.passUntil("declare_attacker", "P1"),
                        step("declare_attacker", "P1", "attacks"),
                        DecisionClassMatrixHarness.passUntil("declare_blocker", "P2"),
                        step("declare_blocker", "P2", "blocks"),
                        DecisionClassMatrixHarness.passUntil("multi_amount", "P1")),
                "multi_amount", "P1"));
        SCENARIOS.put("amount", new Scenario("matrix-amount", 66217L,
                List.of(Placed.hand("P1", "Indentured Djinn"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Indentured Djinn"),
                        DecisionClassMatrixHarness.passUntil("amount", "P2")),
                "amount", "P2"));
        SCENARIOS.put("choose_use", new Scenario("matrix-choose-use", 66212L,
                List.of(Placed.hand("P1", "Ponder"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Ponder"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P1"),
                        DecisionClassMatrixHarness.chooseFirst("choose_object", "P1"),
                        DecisionClassMatrixHarness.chooseFirst("choose_object", "P1"),
                        DecisionClassMatrixHarness.passUntil("choose_use", "P1")),
                "choose_use", "P1"));
        SCENARIOS.put("multi_amount", new Scenario("matrix-multi-amount", 66215L,
                List.of(Placed.hand("P1", "Manamorphose"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain")),
                List.of(step("priority", "P1", "Cast Manamorphose"),
                        DecisionClassMatrixHarness.passUntil("multi_amount", "P1")),
                "multi_amount", "P1"));
        SCENARIOS.put("ring_bearer", new Scenario("matrix-ring-bearer", 66213L,
                List.of(Placed.hand("P1", "Claim the Precious"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Llanowar Elves"),
                        Placed.battlefield("P1", "Elvish Mystic"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Claim the Precious"),
                        step("target", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P1")),
                "choose_object", "P1"));
        SCENARIOS.put("cast_ability", new Scenario("matrix-cast-ability", 66216L,
                List.of(Placed.hand("P1", "Kari Zev's Expertise"),
                        Placed.hand("P1", "Fire // Ice"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Kari Zev's Expertise"),
                        step("target", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("choose_use", "P1"),
                        step("choose_use", "P1", "Yes")),
                "choice", "P1"));
        SCENARIOS.put("land_or_spell", new Scenario("matrix-land-or-spell", 66219L,
                List.of(Placed.battlefield("P1", "Gix, Yawgmoth Praetor"),
                        Placed.hand("P1", "Grizzly Bears"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        new Placed("P2", Zone.LIBRARY, "Agadeem's Awakening")),
                List.of(step("priority", "P1", "Exile the top X"),
                        DecisionClassMatrixHarness.numeric("announce_x", "P1", 1),
                        step("target", "P1", "Full Game Seat 2"),
                        DecisionClassMatrixHarness.passUntilAny(),
                        step("choose_object", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntilAny(),
                        step("choose_use", "P1", "Yes")),
                "choice", "P1"));
        // Pregame (no restoration): starting player, mulligan, London bottom.
        SCENARIOS.put("starting_player", new Scenario("matrix-start", 66218L, null,
                List.of(), "choose_object", "P1"));
        SCENARIOS.put("mulligan", new Scenario("matrix-mulligan", 66218L, null,
                List.of(step("choose_object", "P1", "Full Game Seat 1")), "mulligan", "P1"));
        SCENARIOS.put("london_bottom", new Scenario("matrix-london", 66218L, null,
                List.of(step("choose_object", "P1", "Full Game Seat 1"),
                        step("mulligan", "P1", "Take mulligan"),
                        step("mulligan", "P2", "Keep opening hand")),
                "target", "P1"));
        // Two mulligans: the London bottom of two cards (the engine asks one at a time).
        SCENARIOS.put("london_bottom_two", new Scenario("matrix-london-two", 66218L, null,
                List.of(step("choose_object", "P1", "Full Game Seat 1"),
                        step("mulligan", "P1", "Take mulligan"),
                        step("mulligan", "P2", "Keep opening hand"),
                        DecisionClassMatrixHarness.chooseFirst("target", "P1"),
                        step("mulligan", "P1", "Take mulligan")),
                "target", "P1"));
    }

    /** S2 compares the privileged (keyed) state digest; the test launch carries a key. */
    @org.junit.jupiter.api.BeforeEach
    void orchestrationLaunch() {
        XmageRulesRngResultTape.keyForTests(new byte[32]);
    }

    @org.junit.jupiter.api.AfterEach
    void principalLaunch() {
        XmageRulesRngResultTape.keyForTests(null);
    }

    private static String label(JsonObject action) {
        return DecisionClassMatrixHarness.label(action);
    }

    @Test
    void priorityMatrix() {
        runClass("priority");
    }

    @Test
    void targetMatrix() {
        runClass("target");
    }

    @Test
    void manaPaymentMatrix() {
        runClass("mana_payment");
    }

    @Test
    void targetAmountMatrix() {
        runClass("target_amount");
    }

    @Test
    void modeMatrix() {
        runClass("mode");
    }

    @Test
    void announceXMatrix() {
        runClass("announce_x");
    }

    @Test
    void triggerOrderMatrix() {
        runClass("trigger_order");
    }

    @Test
    void choiceMatrix() {
        runClass("choice");
    }

    @Test
    void replacementEffectMatrix() {
        runClass("replacement_effect");
    }

    @Test
    void chooseObjectMatrix() {
        runClass("choose_object");
    }

    @Test
    void pileMatrix() {
        runClass("pile");
    }

    @Test
    void declareAttackerMatrix() {
        runClass("declare_attacker");
    }

    @Test
    void declareBlockerMatrix() {
        runClass("declare_blocker");
    }

    @Test
    void multiAmountCombatMatrix() {
        runClass("multi_amount_combat");
    }

    @Test
    void amountMatrix() {
        runClass("amount");
    }

    @Test
    void chooseUseMatrix() {
        runClass("choose_use");
    }

    @Test
    void multiAmountMatrix() {
        runClass("multi_amount");
    }

    @Test
    void ringBearerMatrix() {
        runClass("ring_bearer");
    }

    @Test
    void castAbilityMatrix() {
        runClass("cast_ability");
    }

    @Test
    void landOrSpellMatrix() {
        runClass("land_or_spell");
    }

    /**
     * Red control for the land-or-spell callback: its land components follow the
     * one engine caller at the pin; reached from anywhere else, it fails closed
     * instead of building a legality of its own.
     */
    @Test
    void landOrSpellFromAnUndeclaredCallerFailsClosed() {
        Scenario scenario = SCENARIOS.get("priority");
        DecisionClassMatrixHarness.Live live = DecisionClassMatrixHarness.open(scenario);
        JsonObject frame = DecisionClassMatrixHarness.driveToTarget(live, scenario);
        Game game = live.session().restorationGame();
        XmageFullGamePlayer actor = (XmageFullGamePlayer) game.getPlayer(
                UUID.fromString(frame.get("actor_id").getAsString()));
        mage.cards.Card bolt = actor.getHand().getCards(game).iterator().next();
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> actor.chooseLandOrSpellAbility(bolt, game, false));
        assertTrue(failure.getMessage().startsWith("UNSUPPORTED_DECISION_CLASS: land-or-spell choice from an undeclared engine caller"),
                failure.getMessage());
    }

    @Test
    void startingPlayerMatrix() {
        runClass("starting_player");
    }

    @Test
    void mulliganMatrix() {
        runClass("mulligan");
    }

    @Test
    void londonBottomMatrix() {
        runClass("london_bottom");
    }

    @Test
    void londonBottomTwoCardsMatrix() {
        Scenario scenario = SCENARIOS.get("london_bottom_two");
        JsonObject frame = DecisionClassMatrixHarness.driveToTarget(DecisionClassMatrixHarness.open(scenario), scenario);
        // XMage asks a two-card bottom as successive single selections.
        JsonObject decision = frame.getAsJsonObject("decision");
        assertTrue(decision.get("prompt").getAsString().contains("(2 more)"), decision.get("prompt").getAsString());
        assertEquals(1, decision.get("minimum_selections").getAsInt());
        assertEquals(1, decision.get("maximum_selections").getAsInt());
        runClass("london_bottom_two");
    }


    /**
     * #689 red control that stays in the suite: the native return of one
     * accepted option must not satisfy the S1 native-return check for another
     * offered option, and an offset no callback answered must read as no
     * return. Without this, an assertion that never fires would pass S1
     * vacuously.
     */
    @Test
    void nativeReturnAssertionRejectsAnOptionThePilotDidNotSelect() {
        Scenario scenario = SCENARIOS.get("choose_use");
        DecisionClassMatrixHarness.Live live = DecisionClassMatrixHarness.open(scenario);
        JsonObject frame = DecisionClassMatrixHarness.driveToTarget(live, scenario);
        List<JsonObject> offered = actions(frame);
        JsonObject selected = offered.get(0);
        JsonObject other = offered.get(1);
        assertNotEquals(selected.get("action_id").getAsString(),
                other.get("action_id").getAsString(), "two distinct choose_use options");
        JsonObject proposal = proposal(frame, selected);
        live.session().submitAction(proposal);
        String where = "native return red control";
        assertThrows(AssertionError.class,
                () -> assertNativeReturn(EXPECTED_CALLBACK.get("choose_use"), live.session(), other,
                        proposal, "", where),
                "the native return of the accepted option must not satisfy the option not chosen");
        // The offset discipline: a decision no callback answered has no return.
        Game game = live.session().restorationGame();
        XmageFullGamePlayer actor = (XmageFullGamePlayer) game.getPlayer(
                UUID.fromString(selected.get("actor_id").getAsString()));
        long offset = proposal.getAsJsonObject("choices").get("decision_offset").getAsLong();
        assertEquals(1, actor.nativeReturn(offset).length,
                "the answered decision must record exactly one native return");
        // Offset discipline: a decision no callback answered has no return, so a
        // mis-addressed read fails closed instead of borrowing another one.
        assertEquals(0, actor.nativeReturn(offset + 1L).length,
                "an unanswered decision must have no native return");
        assertEquals(0, actor.nativeReturn(offset + 1000L).length,
                "a native return must never be served for an unrelated decision");
    }

    /**
     * #689 P1 red control that stays in the suite: the target assertion reads
     * the ids XMage actually applied, so a callback that adds a different
     * offered id — or whose add never landed because
     * {@code replaceEvent(TargetEvent)} vetoed it — must be rejected, exactly
     * as it would be if the mis-route happened in the callback itself.
     *
     * <p>Driving the real engine for each shape would need a replacement
     * effect that vetoes a TARGETED event mid-cast; the comparison is the same
     * one {@link #assertNativeReturn} runs, so the mis-route is applied to the
     * witness rather than to the callback, and the control still fails if the
     * assertion ever stops reading the applied ids.</p>
     */
    @Test
    void targetNativeReturnRejectsIdsTheEngineNeverApplied() {
        String where = "target applied-ids red control";
        String selected = "11111111-1111-4111-8111-111111111111";
        String otherOffered = "22222222-2222-4222-8222-222222222222";

        // The mis-route: the callback added a different offered id than the
        // pilot selected. Recorded, but not the selected one.
        assertThrows(AssertionError.class,
                () -> assertAppliedTargetIds(where, List.of(otherOffered), List.of(selected), Boolean.TRUE),
                "a callback that applied a different offered id must fail S1");

        // The vetoed add: the callback's response named an id, but
        // replaceEvent(TargetEvent) vetoed it, so the engine applied nothing.
        assertThrows(AssertionError.class,
                () -> assertAppliedTargetIds(where, List.of(), List.of(selected), Boolean.TRUE),
                "a vetoed add must fail S1 even though the response named an id");

        // And the honest answer still passes, so the control is not merely
        // asserting that everything throws.
        assertAppliedTargetIds(where, List.of(selected), List.of(selected), Boolean.TRUE);
        assertAppliedTargetIds(where, List.of(), List.of(), Boolean.FALSE);
    }

    /**
     * #689 P2 red control that stays in the suite: the pool-delta check must
     * reject a spend of the wrong amount, of the wrong type, and of nothing.
     * Before the floating-mana scenario the branch was unreachable, so a
     * mis-spent pool could not have been caught.
     */
    @Test
    void manaPoolDeltaRejectsASpendThatDidNotHappen() {
        DecisionClassMatrixHarness.Live live =
                DecisionClassMatrixHarness.open(SCENARIOS.get("mana_payment"));
        JsonObject frame = DecisionClassMatrixHarness.driveToTarget(live, SCENARIOS.get("mana_payment"));
        JsonObject poolOption = null;
        for (JsonObject action : actions(frame)) {
            if ("mana_pool".equals(optionType(action))) {
                poolOption = action;
                break;
            }
        }
        assertNotNull(poolOption, "the payment frame must offer a pool option for this control");
        String poolBefore = manaPoolSignature(live.session(), poolOption);
        final JsonObject offered = poolOption;
        Player payer = live.session().restorationGame()
                .getPlayer(UUID.fromString(offered.get("actor_id").getAsString()));
        String where = "mana pool delta red control";

        // Nothing was spent: the pool is exactly as it was before the answer, so
        // the expected "one less than before" delta does not hold.
        assertThrows(AssertionError.class,
                () -> assertManaPoolSpent(payer, nativeField(offered, "mana_type"), poolBefore, where),
                "an unspent pool must fail the delta check");

        // A spend of a type that was never in the pool: the delta expects -1
        // and the engine still holds 0.
        Map<mage.constants.ManaType, Integer> before = parseManaPool(poolBefore, where);
        for (mage.constants.ManaType type : mage.constants.ManaType.getTrueManaTypes()) {
            if (before.getOrDefault(type, 0) == 0) {
                final mage.constants.ManaType absent = type;
                assertThrows(AssertionError.class,
                        () -> assertManaPoolSpent(payer, absent.name(), poolBefore, where),
                        "a spend of a mana type that was not in the pool must fail the delta check");
                break;
            }
        }

        // The honest case on the live engine: spend the selected pool option
        // for real, then assert the delta holds. Without this the control
        // would only prove the check can throw.
        JsonObject proposal = proposal(frame, offered);
        live.session().submitAction(proposal);
        assertManaPoolSpent(payer, nativeField(offered, "mana_type"), poolBefore, where);
    }

    // ---- matrix core ----------------------------------------------------------

    static void runClass(String key) {
        Scenario scenario = SCENARIOS.get(key);
        String decisionClass = scenario.targetClass();
        DecisionClassMatrixHarness.Live live = DecisionClassMatrixHarness.open(scenario);
        JsonObject frame = DecisionClassMatrixHarness.driveToTarget(live, scenario);

        // L1: non-empty and set-equal to the engine oracle.
        assertFalse(actions(frame).isEmpty(), decisionClass + ": empty projection");
        assertTrue(frame.get("complete").getAsBoolean());
        Object[] witness = live.session().pendingNativeWitness();
        assertTrue(witness.length > 0, key + ": no native witness bound to the pending decision");
        assertEquals(EXPECTED_CALLBACK.get(key), String.valueOf(witness[0]),
                key + ": the pending decision was raised by another native callback");
        XmageFullGamePlayer actorPlayer = (XmageFullGamePlayer) live.session().restorationGame()
                .getPlayer(UUID.fromString(frame.get("actor_id").getAsString()));
        long offset = frame.get("decision_offset").getAsLong();
        assertEquals(0, actorPlayer.nativeWitness(offset - 1).length, key + ": witness served for another decision");
        assertEquals(0, actorPlayer.nativeWitness(offset + 1).length, key + ": witness served for another decision");
        Oracle oracle = oracleFor(String.valueOf(witness[0]), live, frame, witness);
        assertEquals(oracle.expected(), oracle.projected(),
                decisionClass + ": projection must equal the engine option set; frame " + labels(frame));

        // S2 on this live frame: each malformed submission is rejected with no mutation.
        rejectWithoutMutation(live, frame);

        // S1: every offered action is accepted at the same frame in a fresh session.
        // Option ids are fresh per game, so the same option in a fresh identical
        // session is named by its semantic key: type, label and ordinal among equals.
        cardinalityAccepted(scenario, frame, key);
        List<String> keys = semanticKeys(frame);
        for (String optionKey : keys) {
            DecisionClassMatrixHarness.Live fresh = DecisionClassMatrixHarness.open(scenario);
            JsonObject same = DecisionClassMatrixHarness.driveToTarget(fresh, scenario);
            List<String> sameKeys = semanticKeys(same);
            assertEquals(new java.util.TreeSet<>(keys), new java.util.TreeSet<>(sameKeys),
                    decisionClass + " S1: identical option set in a fresh session");
            JsonObject action = actions(same).get(sameKeys.indexOf(optionKey));
            List<JsonObject> proposals = acceptedProposals(same, action);
            for (int variant = 0; variant < proposals.size(); variant++) {
                DecisionClassMatrixHarness.Live run = fresh;
                JsonObject proposal = proposals.get(variant);
                if (variant > 0) {
                    run = DecisionClassMatrixHarness.open(scenario);
                    JsonObject again = DecisionClassMatrixHarness.driveToTarget(run, scenario);
                    proposal = rebind(proposal, again, actions(again).get(semanticKeys(again).indexOf(optionKey)));
                }
                String before = proposal.getAsJsonObject("choices").get("decision_id").getAsString();
                String routedId = proposal.get("legal_action_id").getAsString();
                JsonObject routed = actions(run == fresh ? same : run.session().legalActionsPayload())
                        .stream().filter(candidate -> candidate.get("action_id").getAsString().equals(routedId))
                        .findFirst().orElseThrow();
                String poolBefore = manaPoolSignature(run.session(), routed);
                JsonObject result = run.session().submitAction(proposal);
                assertEquals(before, result.get("executed_decision_id").getAsString());
                assertRouted(run.session(), routed, proposal, decisionClass + " S1 " + optionKey);
                assertNativeReturn(EXPECTED_CALLBACK.get(key), run.session(), routed, proposal,
                        poolBefore, decisionClass + " S1 " + optionKey);
                JsonObject after = run.session().pendingDecisionPayload();
                if (!after.get("decision").isJsonNull()) {
                    assertNotEquals(before, after.getAsJsonObject("decision").get("decision_id").getAsString(),
                            decisionClass + " S1: decision must advance after " + optionKey);
                }
            }
        }
    }

    /**
     * S1 routing: the engine-side record of the accepted decision names the option
     * the pilot chose (by its native label) and the numeric value it sent, so an
     * accepted proposal cannot have been routed to a different native choice.
     */
    static void assertRouted(XmageFullGameSession session, JsonObject action, JsonObject proposal, String where) {
        com.google.gson.JsonArray transcript = session.controllerTranscript();
        JsonObject accepted = null;
        for (int index = transcript.size() - 1; index >= 0; index--) {
            JsonObject event = transcript.get(index).getAsJsonObject();
            if ("decision_accepted".equals(event.has("kind") ? event.get("kind").getAsString() : "")) {
                accepted = event;
                break;
            }
        }
        assertTrue(accepted != null, where + ": no accepted decision recorded");
        JsonObject choices = proposal.getAsJsonObject("choices");
        if (choices.has("numeric_choice")) {
            assertEquals(choices.get("numeric_choice").getAsInt(), accepted.get("numeric_choice").getAsInt(), where);
        }
        if (choices.has("numeric_choices")) {
            assertEquals(choices.get("numeric_choices"), accepted.get("numeric_choices"), where);
        }
        com.google.gson.JsonArray labels = accepted.getAsJsonArray("selected_option_labels");
        if (!labels.isEmpty() && !choices.has("selected_option_ids")) {
            assertEquals(1, labels.size(), where + ": one native option routed");
            assertEquals(DecisionClassMatrixHarness.label(action),
                    labels.get(0).getAsString(), where + ": routed to a different native option");
        }
    }

    /**
     * #689 S1 native return: the value the native callback handed back to (or
     * applied in) XMage for the answered decision must be the value derived from
     * the option the pilot selected.
     *
     * <p>{@link #assertRouted} proves the controller recorded the selected
     * option; a callback that recorded the right option and returned or applied
     * a different value still satisfied it. This closes that hole: the expected
     * native value is derived here from the routed option's own id or metadata
     * (never from the transcript) and compared with
     * {@link XmageFullGamePlayer#nativeReturn(long)} for the exact decision
     * offset the answer closed. A callback that returns void
     * ({@code selectAttackers}/{@code selectBlockers}) is witnessed by the
     * identifiers it applied plus the live applied engine state, named in the
     * branch below; nothing else in the matrix is void.</p>
     *
     * @param poolBefore the answering player's mana pool before the answer, or
     *                   {@code ""} when it was not observed
     */
    @SuppressWarnings("unchecked")
    static void assertNativeReturn(String callback, XmageFullGameSession session,
                                   JsonObject action, JsonObject proposal,
                                   String poolBefore, String where) {
        Game game = session.restorationGame();
        UUID actorId = UUID.fromString(action.get("actor_id").getAsString());
        Player actorPlayer = game.getPlayer(actorId);
        assertTrue(actorPlayer instanceof XmageFullGamePlayer,
                where + ": the answered decision has no external player");
        long offset = proposal.getAsJsonObject("choices").get("decision_offset").getAsLong();
        Object[] returned = ((XmageFullGamePlayer) actorPlayer).nativeReturn(offset);
        assertTrue(returned.length > 0,
                where + ": no native return recorded for the answered decision " + offset);
        switch (callback) {
            case "priority" -> {
                if ("pass_priority".equals(optionType(action))) {
                    assertNull(returned[0], where + ": passing priority must hand XMage no ability");
                } else {
                    assertTrue(returned[0] instanceof ActivatedAbility,
                            where + ": a priority option must hand XMage its own ability");
                    assertEquals(actionAbilityKey(action), abilityKey((Ability) returned[0]), where);
                }
            }
            case "target" -> assertAppliedTargetIds(
                    where, (List<String>) returned[0], selectedOptionIds(proposal), returned[1]);
            case "target_amount" -> {
                assertEquals(optionId(action), String.valueOf(returned[0]), where);
                assertEquals(numericChoice(proposal), returned[1],
                        where + ": the amount handed to the native target must be the selected one");
            }
            case "declare_attacker" -> {
                // Void callback: the witness is the pair handed to the engine
                // plus the combat state that declaration applied (CR 508.1).
                String attackerId = nativeField(action, "object_id");
                assertEquals(attackerId, String.valueOf(returned[0]), where);
                if ("hold_attacker".equals(optionType(action))) {
                    assertNull(returned[1], where + ": holding must declare no defender");
                    assertFalse(game.getCombat().getAttackers().contains(UUID.fromString(attackerId)),
                            where + ": a held attacker must not be attacking in XMage");
                } else {
                    String defenderId = nativeField(action, "defender_id");
                    assertEquals(defenderId, String.valueOf(returned[1]), where);
                    mage.game.combat.CombatGroup group =
                            game.getCombat().findGroup(UUID.fromString(attackerId));
                    assertNotNull(group, where + ": the declared attacker is in no combat group");
                    assertEquals(defenderId, group.getDefenderId().toString(),
                            where + ": the engine must attack the selected defender");
                }
            }
            case "declare_blocker" -> {
                // Void callback: the witness is the blocks handed to the engine
                // plus the combat state that declaration applied (CR 509.1).
                String blockerId = nativeField(action, "blocker_id");
                String attackerId = nativeField(action, "attacker_id");
                @SuppressWarnings("unchecked")
                List<UUID> declared = (List<UUID>) returned[1];
                assertEquals(blockerId, String.valueOf(returned[0]), where);
                assertEquals(List.of(UUID.fromString(attackerId)), declared,
                        where + ": the blocks handed to the engine must be the selected option");
                mage.game.combat.CombatGroup group =
                        game.getCombat().findGroup(UUID.fromString(attackerId));
                assertNotNull(group, where + ": the blocked attacker is in no combat group");
                assertTrue(group.getBlockers().contains(UUID.fromString(blockerId)),
                        where + ": the engine must block with the selected blocker");
            }
            case "mana_payment" -> {
                String type = optionType(action);
                if ("cancel_mana_payment".equals(type)) {
                    assertEquals("cancel", returned[0], where);
                } else if ("mana_pool".equals(type)) {
                    assertEquals("pool", returned[0], where);
                    assertEquals(nativeField(action, "mana_type"), String.valueOf(returned[1]), where);
                    assertManaPoolSpent(actorPlayer, nativeField(action, "mana_type"), poolBefore, where);
                } else {
                    assertEquals("ability", returned[0], where);
                    assertEquals(actionAbilityKey(action), abilityKey((Ability) returned[1]), where);
                    // The applied payment state: a tapping mana ability left its
                    // permanent tapped in the engine (CR 508.1d / 111.3). A
                    // tapping ability whose permanent is gone is a failure, not
                    // a reason to skip: the check must not pass vacuously.
                    if (returned[1] instanceof Ability ability && tapsSource(ability)) {
                        assertNotNull(ability.getSourceId(),
                                where + ": a tapping mana ability must name its source permanent");
                        mage.game.permanent.Permanent source = game.getPermanent(ability.getSourceId());
                        assertNotNull(source,
                                where + ": the tapped permanent of the selected mana ability is not in XMage");
                        assertTrue(source.isTapped(),
                                where + ": the selected mana ability was not applied in XMage");
                    }
                }
            }
            case "announce_x", "amount" ->
                    assertEquals(numericChoice(proposal), returned[0],
                            where + ": the number handed to XMage must be the selected one");
            case "multi_amount" -> {
                @SuppressWarnings("unchecked")
                List<Integer> vector = (List<Integer>) returned[0];
                assertEquals(numericVector(proposal), vector,
                        where + ": the amount vector handed to XMage must be the selected one");
            }
            case "replacement_effect" ->
                    assertEquals(Integer.valueOf(nativeField(action, "index")), returned[0],
                            where + ": the applied replacement must be the selected index");
            case "choose_use" ->
                    assertEquals(Boolean.valueOf(nativeField(action, "value")), returned[0],
                            where + ": the boolean handed to XMage must be the selected option's value");
            case "mulligan" ->
                    assertEquals(Boolean.valueOf("mulligan".equals(optionType(action))), returned[0],
                            where + ": the mulligan boolean must be the selected option");
            case "pile" -> {
                // XMage reads pile 1 as true and pile 2 as false. The branch is
                // keyed on the option id the callback built
                // (stableId("pile", "1"/"2")) and cross-checked against the
                // selected pile's own card ids, never on the display label, so
                // a relabelled projection cannot silently satisfy it.
                String pileOne = XmageFullGameDecisionController.stableId("pile", "1");
                String pileTwo = XmageFullGameDecisionController.stableId("pile", "2");
                boolean first = pileOne.equals(optionId(action));
                assertTrue(first ^ pileTwo.equals(optionId(action)),
                        where + ": a pile option id must be pile 1 or pile 2");
                assertEquals(Boolean.valueOf(first), returned[0],
                        where + ": XMage reads pile 1 as true, pile 2 as false");
                // The chosen pile's engine card ids, recorded beside the boolean.
                // An empty pile is a legal answer and is compared as such, not
                // skipped: the option id selects the pile, never the label.
                @SuppressWarnings("unchecked")
                List<String> chosenPile = (List<String>) returned[1];
                assertEquals(pileCardIds(action), chosenPile,
                        where + ": the ids handed to XMage must be the selected pile's own cards");
            }
            case "choice" -> {
                String choiceKey = nativeField(action, "choice_key");
                if (choiceKey != null) {
                    assertEquals(Boolean.TRUE, returned[0],
                            where + ": a key choice must hand XMage its own key");
                    assertEquals(choiceKey, returned[1], where);
                } else {
                    assertEquals(Boolean.FALSE, returned[0], where);
                    assertEquals(nativeField(action, "choice"), returned[1],
                            where + ": the choice handed to XMage must be the selected value");
                }
            }
            case "mode" -> {
                assertTrue(returned[0] instanceof mage.abilities.Mode,
                        where + ": a mode option must hand XMage its own mode");
                assertEquals(optionId(action), ((mage.abilities.Mode) returned[0]).getId().toString(),
                        where);
            }
            case "trigger_order" -> {
                assertTrue(returned[0] instanceof mage.abilities.TriggeredAbility,
                        where + ": a trigger option must hand XMage its own ability");
                assertEquals(actionAbilityKey(action), abilityKey((Ability) returned[0]), where);
            }
            case "cast_ability", "land_or_spell" -> {
                assertTrue(returned[0] instanceof Ability,
                        where + ": a cast option must hand XMage its own ability");
                assertEquals(actionAbilityKey(action), abilityKey((Ability) returned[0]), where);
            }
            default -> throw new AssertionError(
                    "no native-return expectation for native callback " + callback);
        }
    }

/**
 * The engine's card ids for one offered pile, from its native metadata.
 */
    static List<String> pileCardIds(JsonObject action) {
        List<String> ids = new ArrayList<>();
        com.google.gson.JsonArray cards = DecisionClassMatrixHarness.nativeMetadata(action)
                .getAsJsonArray("cards");
        if (cards != null) {
            cards.forEach(element -> ids.add(element.getAsJsonObject().get("object_id").getAsString()));
        }
        return ids;
    }

    /**
     * The option ids the pilot's proposal actually selects, resolved the way
     * {@link XmageFullGameActionProjection#toDecisionResponse} resolves them:
     * the explicit {@code selected_option_ids} when the proposal carries one,
     * otherwise the single option named by {@code legal_action_id}. An empty
     * array is a real answer (a frame whose minimum is 0), not a missing field.
     */
    static List<String> selectedOptionIds(JsonObject proposal) {
        JsonObject choices = proposal.getAsJsonObject("choices");
        if (choices.has("selected_option_ids") && !choices.get("selected_option_ids").isJsonNull()) {
            List<String> selected = new ArrayList<>();
            choices.getAsJsonArray("selected_option_ids")
                    .forEach(element -> selected.add(element.getAsString()));
            return selected;
        }
        String legalActionId = proposal.has("legal_action_id")
                && !proposal.get("legal_action_id").isJsonNull()
                ? proposal.get("legal_action_id").getAsString().trim() : "";
        if (legalActionId.isEmpty()) {
            return List.of();
        }
        int separator = legalActionId.indexOf(':');
        assertTrue(separator > 0 && separator < legalActionId.length() - 1,
                "malformed legal_action_id in the proposal under test: " + legalActionId);
        return List.of(legalActionId.substring(separator + 1));
    }

    /** Whether activating this ability taps its source permanent (CR 111.3). */
    private static boolean tapsSource(Ability ability) {
        for (mage.abilities.costs.Cost cost : ability.getCosts()) {
            if (cost instanceof mage.abilities.costs.common.TapSourceCost) {
                return true;
            }
        }
        return false;
    }

    /**
     * The applied payment state of a pool spend: exactly one mana of the
     * selected type left the pool and nothing else did.
     *
     * <p>Both sides are keyed on the {@link mage.constants.ManaType} enum, not
     * on a string: the option's {@code mana_type} is {@code ManaType.toString()}
     * (lower case, "red") while the signature is written with
     * {@code ManaType.name()} (upper case, "RED"), so a string-keyed comparison
     * would miss every entry. Resolving the enum keeps the delta exact.</p>
     */
    private static void assertManaPoolSpent(
            Player payer, String manaType, String poolBefore, String where) {
        assertFalse(poolBefore.isEmpty(),
                where + ": the answering player's mana pool was not observed before the spend");
        mage.constants.ManaType selected = manaType(manaType, where);
        Map<mage.constants.ManaType, Integer> before = parseManaPool(poolBefore, where);
        assertEquals(before.getOrDefault(selected, 0) - 1,
                payer.getManaPool().get(selected),
                where + ": the selected pool mana must be the mana XMage spent");
        for (Map.Entry<mage.constants.ManaType, Integer> entry : before.entrySet()) {
            if (entry.getKey() == selected) {
                continue;
            }
            assertEquals(entry.getValue().intValue(),
                    payer.getManaPool().get(entry.getKey()),
                    where + ": payment must spend only the selected pool mana");
        }
    }

    /** The engine {@link mage.constants.ManaType} an option's native name denotes. */
    private static mage.constants.ManaType manaType(String value, String where) {
        for (mage.constants.ManaType type : mage.constants.ManaType.getTrueManaTypes()) {
            if (type.name().equalsIgnoreCase(value) || type.toString().equalsIgnoreCase(value)) {
                return type;
            }
        }
        throw new AssertionError(where + ": unknown native mana type " + value);
    }

    /** The answering player's mana pool, as observed before the answer. */
    static String manaPoolSignature(XmageFullGameSession session, JsonObject action) {
        Player actorPlayer = session.restorationGame()
                .getPlayer(UUID.fromString(action.get("actor_id").getAsString()));
        if (actorPlayer == null) {
            return "";
        }
        StringBuilder signature = new StringBuilder();
        for (mage.constants.ManaType type : mage.constants.ManaType.getTrueManaTypes()) {
            signature.append(type.name()).append('=').append(actorPlayer.getManaPool().get(type))
                    .append(';');
        }
        return signature.toString();
    }

    private static Map<mage.constants.ManaType, Integer> parseManaPool(String signature, String where) {
        Map<mage.constants.ManaType, Integer> pool = new LinkedHashMap<>();
        for (String entry : signature.split(";")) {
            int equals = entry.indexOf('=');
            if (equals > 0) {
                pool.put(manaType(entry.substring(0, equals), where),
                        Integer.parseInt(entry.substring(equals + 1)));
            }
        }
        return pool;
    }

    private static Integer numericChoice(JsonObject proposal) {
        JsonObject choices = proposal.getAsJsonObject("choices");
        return choices.has("numeric_choice") && !choices.get("numeric_choice").isJsonNull()
                ? choices.get("numeric_choice").getAsInt() : null;
    }

    private static List<Integer> numericVector(JsonObject proposal) {
        JsonObject choices = proposal.getAsJsonObject("choices");
        List<Integer> vector = new ArrayList<>();
        if (choices.has("numeric_choices") && !choices.get("numeric_choices").isJsonNull()) {
            choices.getAsJsonArray("numeric_choices").forEach(element -> vector.add(element.getAsInt()));
        }
        return vector;
    }

    /**
     * The proposals S1 submits for one offered action: the action itself, or for a
     * numeric action its lowest and highest legal value, or for a joint vector the
     * lowest and highest legal totals filled leg by leg.
     */
    static List<JsonObject> acceptedProposals(JsonObject frame, JsonObject action) {
        List<JsonObject> proposals = new ArrayList<>();
        JsonObject context = frame.getAsJsonObject("decision").getAsJsonObject("context");
        boolean numeric = context.has("numeric_legs")
                || context.has("numeric_min") && context.has("numeric_max");
        if (!numeric) {
            proposals.add(proposal(frame, action));
        } else if (context.has("numeric_legs")) {
            for (int total : new int[] {context.get("numeric_total_min").getAsInt(),
                    context.get("numeric_total_max").getAsInt()}) {
                com.google.gson.JsonArray vector = new com.google.gson.JsonArray();
                int remaining = total;
                for (com.google.gson.JsonElement leg : context.getAsJsonArray("numeric_legs")) {
                    int min = leg.getAsJsonObject().get("min").getAsInt();
                    int take = Math.max(min, Math.min(leg.getAsJsonObject().get("max").getAsInt(), remaining));
                    vector.add(take);
                    remaining -= take;
                }
                JsonObject proposal = proposal(frame, action);
                proposal.getAsJsonObject("choices").add("numeric_choices", vector);
                proposals.add(proposal);
            }
        } else {
            for (int value : new int[] {context.get("numeric_min").getAsInt(),
                    context.get("numeric_max").getAsInt()}) {
                JsonObject proposal = proposal(frame, action);
                proposal.getAsJsonObject("choices").addProperty("numeric_choice", value);
                proposals.add(proposal);
            }
        }
        return proposals;
    }

    /** Re-bind a proposal built on one session's frame to an identical frame of another. */
    static JsonObject rebind(JsonObject proposal, JsonObject frame, JsonObject action) {
        JsonObject copy = proposal.deepCopy();
        copy.addProperty("actor_id", action.get("actor_id").getAsString());
        copy.addProperty("legal_action_id", action.get("action_id").getAsString());
        copy.getAsJsonObject("choices").addProperty("decision_id", frame.get("decision_id").getAsString());
        copy.getAsJsonObject("choices").addProperty("decision_offset", frame.get("decision_offset").getAsLong());
        return copy;
    }

    /**
     * The ids the engine actually applied to the native target must be exactly
     * the ids the pilot selected, and the boolean XMage read must be their
     * emptiness.
     *
     * <p>This is the P1 comparison, isolated so a permanent red control can
     * drive it with a deliberately mis-routed witness: a callback that added a
     * different offered id, or whose add was vetoed by
     * {@code replaceEvent(TargetEvent)}, must be rejected here rather than
     * passing on the controller's response.</p>
     */
    static void assertAppliedTargetIds(String where, List<String> applied,
                                       List<String> selected, Object returnedFlag) {
        assertEquals(selected, applied,
                where + ": the ids applied to the native target must be the selected options");
        assertEquals(Boolean.valueOf(!selected.isEmpty()), returnedFlag,
                where + ": XMage reads a non-empty selection as true, an empty one as false");
    }

    /**
     * #689 P2: the native-return binding for the cardinality S1 acceptances,
     * where the answer is a set of option ids rather than one option.
     *
     * <p>The empty selection is a real answer the engine applies, not the
     * absence of one: an empty target selection must add nothing and hand
     * XMage {@code false}, and an empty block must declare no block. The
     * maximal selection must apply exactly the ids the pilot named. The
     * expectation is read off the proposal, never off the transcript.</p>
     */
    @SuppressWarnings("unchecked")
    static void assertNativeReturnForSelection(String callback, XmageFullGameSession session,
                                               JsonObject frame, JsonObject proposal, String where) {
        Game game = session.restorationGame();
        UUID actorId = UUID.fromString(frame.get("actor_id").getAsString());
        Player actorPlayer = game.getPlayer(actorId);
        assertTrue(actorPlayer instanceof XmageFullGamePlayer,
                where + ": the answered decision has no external player");
        long offset = proposal.getAsJsonObject("choices").get("decision_offset").getAsLong();
        Object[] returned = ((XmageFullGamePlayer) actorPlayer).nativeReturn(offset);
        assertTrue(returned.length > 0,
                where + ": no native return recorded for the answered decision " + offset);
        List<String> selected = selectedOptionIds(proposal);
        switch (callback) {
            case "target" ->
                    assertAppliedTargetIds(where, (List<String>) returned[0], selected, returned[1]);
            case "declare_blocker" -> {
                String blockerId = nativeField(actions(frame).get(0), "blocker_id");
                assertEquals(blockerId, String.valueOf(returned[0]), where + ": the blocker asked");
                @SuppressWarnings("unchecked")
                List<UUID> declared = (List<UUID>) returned[1];
                assertEquals(selected.stream().map(UUID::fromString).toList(), declared,
                        where + ": the blocks handed to the engine must be the selected options");
                if (selected.isEmpty()) {
                    // CR 509.1a: an empty selection declares no block, so the
                    // blocker must appear in no combat group.
                    for (UUID attackerId : game.getCombat().getAttackers()) {
                        mage.game.combat.CombatGroup group = game.getCombat().findGroup(attackerId);
                        if (group != null) {
                            assertFalse(group.getBlockers().contains(UUID.fromString(blockerId)),
                                    where + ": an empty selection must declare no block in XMage");
                        }
                    }
                }
            }
            default -> throw new AssertionError(
                    "no selection-cardinality native-return expectation for native callback " + callback);
        }
    }

    /** S1 for selection cardinality: the empty selection (min 0) and a maximal one. */
    static void cardinalityAccepted(Scenario scenario, JsonObject frame, String key) {
        JsonObject decision = frame.getAsJsonObject("decision");
        int min = decision.get("minimum_selections").getAsInt();
        int max = decision.get("maximum_selections").getAsInt();
        String callback = EXPECTED_CALLBACK.get(key);
        if (min == 0 && max > 0) {
            DecisionClassMatrixHarness.Live fresh = DecisionClassMatrixHarness.open(scenario);
            JsonObject same = DecisionClassMatrixHarness.driveToTarget(fresh, scenario);
            JsonObject proposal = DecisionClassMatrixHarness.emptySelection(same);
            JsonObject result = fresh.session().submitAction(proposal);
            assertEquals(same.get("decision_id").getAsString(), result.get("executed_decision_id").getAsString());
            assertNativeReturnForSelection(callback, fresh.session(), same, proposal,
                    key + " S1 empty selection");
        }
        if (max > 1 && actions(frame).size() > 1) {
            DecisionClassMatrixHarness.Live fresh = DecisionClassMatrixHarness.open(scenario);
            JsonObject same = DecisionClassMatrixHarness.driveToTarget(fresh, scenario);
            List<JsonObject> offered = actions(same);
            int count = Math.min(max, offered.size());
            JsonObject proposal = proposal(same, offered.get(0));
            com.google.gson.JsonArray selected = new com.google.gson.JsonArray();
            for (int index = 0; index < count; index++) {
                selected.add(DecisionClassMatrixHarness.metadata(offered.get(index)).get("option_id").getAsString());
            }
            proposal.getAsJsonObject("choices").add("selected_option_ids", selected);
            JsonObject result = fresh.session().submitAction(proposal);
            assertEquals(same.get("decision_id").getAsString(), result.get("executed_decision_id").getAsString());
            assertNativeReturnForSelection(callback, fresh.session(), same, proposal,
                    key + " S1 selection of " + count);
        }
    }

    static List<String> semanticKeys(JsonObject frame) {
        List<String> keys = new ArrayList<>();
        Map<String, Integer> seen = new LinkedHashMap<>();
        for (JsonObject action : actions(frame)) {
            // Engine object ids in labels ("[270]") are fresh per game; strip them.
            String base = optionType(action) + "|" + label(action).replaceAll("\\[[0-9a-f]{3}\\]", "[id]");
            int ordinal = seen.merge(base, 1, Integer::sum);
            keys.add(base + "#" + ordinal);
        }
        return keys;
    }

    record Oracle(Set<String> expected, Set<String> projected) {
    }

    static Oracle oracleFor(String kind, DecisionClassMatrixHarness.Live live,
                            JsonObject frame, Object[] witness) {
        Game game = live.session().restorationGame();
        Player actor = game.getPlayer(UUID.fromString(frame.get("actor_id").getAsString()));
        JsonObject decision = frame.getAsJsonObject("decision");
        Set<String> expected = new HashSet<>();
        Set<String> projected = new HashSet<>();
        switch (kind) {
            case "priority" -> {
                // Engine: pass, plus every playable ability (no hash de-duplication). A mana
                // ability with its own mana cost needs the F-35 affordability filter; the
                // scenarios hold none, which the assertion keeps true.
                expected.add("pass_priority");
                for (ActivatedAbility ability
                        : ((mage.players.PlayerImpl) actor).getPlayable(game, false, Zone.ALL, false)) {
                    assertTrue(!ability.isManaAbility() || ability.getManaCostsToPay().isEmpty(),
                            "scenario must not need the F-35 affordability filter: " + ability);
                    expected.add(abilityKey(ability));
                }
                for (JsonObject action : actions(frame)) {
                    projected.add("pass_priority".equals(optionType(action))
                            ? "pass_priority" : actionAbilityKey(action));
                }
            }
            case "target", "target_amount" -> {
                Target target = (Target) witness[1];
                Ability source = (Ability) witness[2];
                mage.cards.Cards cards = witness.length > 3 ? (mage.cards.Cards) witness[3] : null;
                Set<UUID> possible = cards == null
                        ? target.possibleTargets(actor.getId(), source, game)
                        : target.possibleTargets(actor.getId(), source, game,
                        cards.getCards(game).stream().map(mage.MageItem::getId).collect(Collectors.toSet()));
                possible.forEach(id -> expected.add(id.toString()));
                actions(frame).forEach(action -> projected.add(optionId(action)));
                if ("target".equals(kind)) {
                    int min = Math.max(0, target.getMinNumberOfTargets() - target.getSize());
                    int max = Math.min(Math.max(0, target.getMaxNumberOfTargets() - target.getSize()),
                            possible.size());
                    assertEquals(Math.min(min, max), decision.get("minimum_selections").getAsInt(), "min");
                    assertEquals(max, decision.get("maximum_selections").getAsInt(), "max");
                } else {
                    JsonObject context = decision.getAsJsonObject("context");
                    assertEquals(1, context.get("numeric_min").getAsInt());
                    assertEquals(Math.max(1, ((mage.target.TargetAmount) target).getAmountRemaining()),
                            context.get("numeric_max").getAsInt());
                }
            }
            case "mode" -> {
                mage.abilities.Modes modes = (mage.abilities.Modes) witness[1];
                Ability source = (Ability) witness[2];
                List<mage.abilities.Mode> available = new ArrayList<>(modes.getAvailableModes(source, game));
                // CR 700.2a: a mode whose required targets cannot be chosen cannot be chosen,
                // unless no mode can (then the cast rewinds, and all stay listed).
                List<mage.abilities.Mode> choosable = available.stream()
                        .filter(mode -> mode.getTargets().canChoose(actor.getId(), source, game))
                        .toList();
                (choosable.isEmpty() ? available : choosable)
                        .forEach(mode -> expected.add(mode.getId().toString()));
                actions(frame).forEach(action -> projected.add(optionId(action)));
            }
            case "announce_x", "amount" -> {
                JsonObject context = decision.getAsJsonObject("context");
                expected.add(witness[1] + ".." + witness[2]);
                projected.add(context.get("numeric_min").getAsInt() + ".." + context.get("numeric_max").getAsInt());
                assertEquals(1, actions(frame).size(), "one numeric action");
            }
            case "multi_amount" -> {
                @SuppressWarnings("unchecked")
                List<mage.util.MultiAmountMessage> messages = (List<mage.util.MultiAmountMessage>) witness[1];
                JsonObject context = decision.getAsJsonObject("context");
                expected.add("total " + witness[2] + ".." + witness[3]);
                projected.add("total " + context.get("numeric_total_min").getAsInt() + ".."
                        + context.get("numeric_total_max").getAsInt());
                for (int index = 0; index < messages.size(); index++) {
                    expected.add("leg" + index + " " + messages.get(index).min + ".." + messages.get(index).max);
                }
                com.google.gson.JsonArray legs = context.getAsJsonArray("numeric_legs");
                for (int index = 0; index < legs.size(); index++) {
                    JsonObject leg = legs.get(index).getAsJsonObject();
                    projected.add("leg" + index + " " + leg.get("min").getAsInt() + ".." + leg.get("max").getAsInt());
                }
            }
            case "trigger_order" -> {
                @SuppressWarnings("unchecked")
                List<mage.abilities.TriggeredAbility> abilities =
                        (List<mage.abilities.TriggeredAbility>) witness[1];
                abilities.forEach(ability -> expected.add(abilityKey(ability)));
                actions(frame).forEach(action -> projected.add(actionAbilityKey(action)));
            }
            case "choice" -> {
                mage.choices.Choice choice = (mage.choices.Choice) witness[1];
                if (choice.isKeyChoice()) {
                    expected.addAll(choice.getKeyChoices().keySet());
                    actions(frame).forEach(action -> projected.add(nativeField(action, "choice_key")));
                } else {
                    expected.addAll(choice.getChoices());
                    actions(frame).forEach(action -> projected.add(nativeField(action, "choice")));
                }
            }
            case "cast_ability" -> {
                mage.cards.Card card = (mage.cards.Card) witness[1];
                boolean noMana = (Boolean) witness[2];
                Zone zone = game.getState().getZone(card.getMainCard().getId());
                mage.players.PlayerImpl.getCastableSpellAbilities(game, actor.getId(), card, zone, noMana)
                        .values().forEach(ability -> expected.add(abilityKey(ability)));
                actions(frame).forEach(action -> projected.add(actionAbilityKey(action)));
            }
            case "land_or_spell" -> {
                mage.cards.Card card = (mage.cards.Card) witness[1];
                boolean noMana = (Boolean) witness[2];
                Zone zone = game.getState().getZone(card.getMainCard().getId());
                mage.players.PlayerImpl.getCastableSpellAbilities(game, actor.getId(), card, zone, noMana)
                        .values().forEach(ability -> expected.add(abilityKey(ability)));
                for (mage.cards.Card component : mage.util.CardUtil.getCastableComponents(
                        card, null, null, actor, game, null, true)) {
                    if (component.isLand(game)) {
                        component.getAbilities(game).stream()
                                .filter(ability -> ability instanceof mage.abilities.PlayLandAbility)
                                .forEach(ability -> expected.add(abilityKey(ability)));
                    }
                }
                actions(frame).forEach(action -> projected.add(actionAbilityKey(action)));
            }
            case "replacement_effect" -> {
                @SuppressWarnings("unchecked")
                Map<String, String> effects = (Map<String, String>) witness[1];
                expected.addAll(effects.keySet());
                actions(frame).forEach(action -> projected.add(nativeField(action, "xmage_key")));
            }
            case "pile" -> {
                @SuppressWarnings("unchecked")
                List<? extends mage.cards.Card> pile1 = (List<? extends mage.cards.Card>) witness[1];
                @SuppressWarnings("unchecked")
                List<? extends mage.cards.Card> pile2 = (List<? extends mage.cards.Card>) witness[2];
                expected.add("Pile 1:" + pile1.size());
                expected.add("Pile 2:" + pile2.size());
                for (JsonObject action : actions(frame)) {
                    projected.add(DecisionClassMatrixHarness.label(action) + ":"
                            + DecisionClassMatrixHarness.nativeMetadata(action).getAsJsonArray("cards").size());
                }
            }
            case "choose_use" -> {
                expected.add("true");
                expected.add("false");
                actions(frame).forEach(action -> projected.add(nativeField(action, "value")));
            }
            case "mulligan" -> {
                // CR 103.5: keep or take a mulligan.
                expected.add("keep");
                expected.add("mulligan");
                actions(frame).forEach(action -> projected.add(optionType(action)));
            }
            case "declare_attacker" -> {
                // The frame asks about one attacker: hold, or attack each defender it can attack.
                String attackerId = nativeField(actions(frame).get(0), "object_id");
                mage.game.permanent.Permanent attacker = game.getPermanent(UUID.fromString(attackerId));
                assertTrue(actor.getAvailableAttackers(game).contains(attacker), "attacker is available");
                expected.add("hold:" + attackerId);
                for (UUID defender : game.getCombat().getDefenders()) {
                    if (attacker.canAttack(defender, game)) {
                        expected.add("attack:" + defender);
                    }
                }
                for (JsonObject action : actions(frame)) {
                    projected.add("hold_attacker".equals(optionType(action))
                            ? "hold:" + nativeField(action, "object_id")
                            : "attack:" + nativeField(action, "defender_id"));
                }
            }
            case "declare_blocker" -> {
                // The frame asks about one blocker: each attacker it can block (min 0 = no block).
                String blockerId = nativeField(actions(frame).get(0), "blocker_id");
                mage.game.permanent.Permanent blocker = game.getPermanent(UUID.fromString(blockerId));
                for (UUID attackerId : game.getCombat().getAttackers()) {
                    mage.game.permanent.Permanent attacker = game.getPermanent(attackerId);
                    if (attacker != null && blocker.canBlock(attackerId, game)) {
                        expected.add(attackerId.toString());
                    }
                }
                actions(frame).forEach(action -> projected.add(nativeField(action, "attacker_id")));
                assertEquals(0, decision.get("minimum_selections").getAsInt(), "blocking is optional");
            }
            case "mana_payment" -> {
                expected.add("cancel_mana_payment");
                for (mage.constants.ManaType type : mage.constants.ManaType.getTrueManaTypes()) {
                    if (actor.getManaPool().get(type) > 0) {
                        expected.add("pool:" + type);
                    }
                }
                for (mage.game.permanent.Permanent permanent
                        : game.getBattlefield().getAllActivePermanents(actor.getId())) {
                    for (ActivatedAbility ability
                            : permanent.getAbilities().getActivatedManaAbilities(Zone.BATTLEFIELD)) {
                        if (ability.canActivate(actor.getId(), game).canActivate()) {
                            expected.add(abilityKey(ability));
                        }
                    }
                }
                for (mage.abilities.SpecialAction special
                        : game.getState().getSpecialActions().getControlledBy(actor.getId(), true).values()) {
                    expected.add(abilityKey(special));
                }
                for (JsonObject action : actions(frame)) {
                    String type = optionType(action);
                    if ("cancel_mana_payment".equals(type)) {
                        projected.add(type);
                    } else if ("mana_pool".equals(type)) {
                        projected.add("pool:" + nativeField(action, "mana_type"));
                    } else {
                        projected.add(actionAbilityKey(action));
                    }
                }
            }
            default -> throw new AssertionError("no oracle for native callback " + kind);
        }
        return new Oracle(sorted(expected), sorted(projected));
    }

    static String optionId(JsonObject action) {
        return DecisionClassMatrixHarness.metadata(action).get("option_id").getAsString();
    }

    static String abilityKey(Ability ability) {
        return ability.getSourceId() + "/" + ability.getOriginalId();
    }

    static String actionAbilityKey(JsonObject action) {
        return nativeField(action, "source_object_id") + "/" + nativeField(action, "ability_original_id");
    }

    // ---- S2 -------------------------------------------------------------------

    /** A corrupted proposal and the typed error code it must be rejected with. */
    record Bad(String name, JsonObject proposal, String code) {
    }

    /**
     * Every corruption starts from a proposal S1 accepts on this frame (with its
     * numeric field where the frame is numeric), so a rejection is caused by the
     * one corrupted field only.
     */
    static void rejectWithoutMutation(DecisionClassMatrixHarness.Live live, JsonObject frame) {
        XmageFullGameSession session = live.session();
        JsonObject action = actions(frame).get(0);
        JsonObject base = acceptedProposals(frame, action).get(0);
        String readback = XmageNativeStateRestoration.readback(session.restorationGame(), live.seats()).toString();
        String privileged = session.privilegedStateDigest();
        int transcriptSize = session.controllerTranscript().size();
        long count = session.pendingDecisionPayload().get("decision_count").getAsLong();
        String decisionId = frame.get("decision_id").getAsString();
        JsonObject decision = frame.getAsJsonObject("decision");
        JsonObject context = decision.getAsJsonObject("context");

        List<Bad> bad = new ArrayList<>();
        JsonObject staleOffset = base.deepCopy();
        staleOffset.getAsJsonObject("choices").addProperty("decision_offset",
                frame.get("decision_offset").getAsLong() + 1);
        bad.add(new Bad("stale offset", staleOffset, "STALE_DECISION"));
        JsonObject staleId = base.deepCopy();
        staleId.getAsJsonObject("choices").addProperty("decision_id", "0".repeat(64));
        bad.add(new Bad("stale decision id", staleId, "STALE_DECISION"));
        JsonObject wrongActor = base.deepCopy();
        String other = live.seats().values().stream()
                .map(player -> player.getId().toString())
                .filter(id -> !id.equals(frame.get("actor_id").getAsString()))
                .findFirst().orElseThrow();
        wrongActor.addProperty("actor_id", other);
        bad.add(new Bad("wrong actor", wrongActor, "PILOT_RESPONSE_INVALID: wrong actor"));
        JsonObject unoffered = base.deepCopy();
        unoffered.addProperty("legal_action_id", decisionId + ":" + "f".repeat(64));
        bad.add(new Bad("unoffered action", unoffered, "ILLEGAL_ACTION"));
        JsonObject malformed = base.deepCopy();
        malformed.remove("actor_id");
        bad.add(new Bad("missing actor", malformed, "PILOT_RESPONSE_INVALID: missing actor_id"));
        if (context.has("numeric_min") && context.has("numeric_max") && !context.has("numeric_legs")) {
            for (int value : new int[] {context.get("numeric_min").getAsInt() - 1,
                    context.get("numeric_max").getAsInt() + 1}) {
                JsonObject outOfRange = base.deepCopy();
                outOfRange.getAsJsonObject("choices").addProperty("numeric_choice", value);
                bad.add(new Bad("numeric " + value, outOfRange, "PILOT_RESPONSE_INVALID: numeric choice out of range"));
            }
        }
        if (context.has("numeric_legs")) {
            com.google.gson.JsonArray legs = context.getAsJsonArray("numeric_legs");
            com.google.gson.JsonArray over = base.getAsJsonObject("choices")
                    .getAsJsonArray("numeric_choices").deepCopy();
            over.set(0, new com.google.gson.JsonPrimitive(
                    legs.get(0).getAsJsonObject().get("max").getAsInt() + 1));
            JsonObject legOut = base.deepCopy();
            legOut.getAsJsonObject("choices").add("numeric_choices", over);
            bad.add(new Bad("joint leg above max", legOut, "PILOT_RESPONSE_INVALID: joint leg 0"));
            com.google.gson.JsonArray shorter = new com.google.gson.JsonArray();
            for (int index = 0; index < legs.size() - 1; index++) {
                shorter.add(0);
            }
            JsonObject legCount = base.deepCopy();
            legCount.getAsJsonObject("choices").add("numeric_choices", shorter);
            bad.add(new Bad("joint vector short", legCount, "PILOT_RESPONSE_INVALID: joint vector length"));
        }
        int max = decision.get("maximum_selections").getAsInt();
        if (max >= 1 && actions(frame).size() > max) {
            JsonObject tooMany = base.deepCopy();
            com.google.gson.JsonArray selected = new com.google.gson.JsonArray();
            for (int index = 0; index <= max; index++) {
                selected.add(optionId(actions(frame).get(index)));
            }
            tooMany.getAsJsonObject("choices").add("selected_option_ids", selected);
            bad.add(new Bad("selections above max", tooMany, "PILOT_RESPONSE_INVALID: selected " + (max + 1) + " options"));
        }
        if (max > 1) {
            JsonObject duplicate = base.deepCopy();
            com.google.gson.JsonArray selected = new com.google.gson.JsonArray();
            selected.add(optionId(action));
            selected.add(optionId(action));
            duplicate.getAsJsonObject("choices").add("selected_option_ids", selected);
            bad.add(new Bad("duplicate selection", duplicate, "PILOT_RESPONSE_INVALID: duplicate option id"));
        }

        for (Bad entry : bad) {
            XmageFullGameDecisionController.DecisionException rejected = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.submitAction(entry.proposal()), "must reject " + entry.name());
            assertTrue(rejected.getMessage() != null && rejected.getMessage().startsWith(entry.code()),
                    entry.name() + ": expected " + entry.code() + ", got " + rejected.getMessage());
            JsonObject now = session.pendingDecisionPayload();
            assertEquals(readback, XmageNativeStateRestoration.readback(session.restorationGame(), live.seats()).toString(),
                    "a rejected submission must not mutate the game: " + entry.name());
            assertEquals(privileged, session.privilegedStateDigest(),
                    "a rejected submission must not change the privileged state: " + entry.name());
            assertEquals(transcriptSize, session.controllerTranscript().size(),
                    "a rejected submission must not append an event: " + entry.name());
            assertEquals(count, now.get("decision_count").getAsLong());
            assertEquals(decisionId, now.getAsJsonObject("decision").get("decision_id").getAsString());
        }
        // The unmodified base is still accepted here: the rejections left the frame usable.
        JsonObject result = session.submitAction(base);
        assertEquals(decisionId, result.get("executed_decision_id").getAsString());
    }

    static Set<String> keys(Iterable<String> values) {
        return sorted(values);
    }

    static Map<String, Boolean> unused() {
        return Map.of();
    }
}
