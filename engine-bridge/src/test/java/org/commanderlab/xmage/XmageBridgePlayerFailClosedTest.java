package org.commanderlab.xmage;

import mage.abilities.Ability;
import mage.cards.Cards;
import mage.choices.Choice;
import mage.constants.MultiAmountType;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.game.Game;
import mage.players.Player;
import mage.target.Target;
import mage.target.TargetAmount;
import mage.target.TargetCard;
import mage.util.MultiAmountMessage;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS80 boundary: the B4 externally controlled compatibility path must fail
 * closed on every discretionary Player callback instead of silently returning
 * a tactical default. The null-controller B3 path preserves validated bounded
 * behavior byte-identically.
 */
class XmageBridgePlayerFailClosedTest {

    private static final Set<String> NON_CHOOSE_DISCRETIONARY_CALLBACKS = Set.of(
            "priority",
            "playMana",
            "announceX",
            "getAmount",
            "getMultiAmount",
            "getMultiAmountWithIndividualConstraints",
            "selectAttackers",
            "selectBlockers"
    );

    private static final Set<String> AUDITED_SAFE_PARENT_DELEGATIONS = Set.of(
            "chooseRingBearer",
            "getMultiAmount"
    );

    @Test
    void everyDiscretionaryPlayerCallbackIsOverriddenOrExplicitlyAuditedAsDelegation()
            throws Exception {
        Set<String> directCallbacks = new LinkedHashSet<>();
        Set<String> delegatedCallbacks = new LinkedHashSet<>();

        for (Method method : Player.class.getMethods()) {
            if (!isDiscretionaryCallback(method)) {
                continue;
            }
            if (AUDITED_SAFE_PARENT_DELEGATIONS.contains(method.getName())) {
                delegatedCallbacks.add(method.getName());
                continue;
            }

            Method implementation = XmageBridgePlayer.class.getMethod(
                    method.getName(),
                    method.getParameterTypes()
            );
            assertEquals(
                    XmageBridgePlayer.class,
                    implementation.getDeclaringClass(),
                    () -> "discretionary Player callback inherited without guard: "
                            + method.toGenericString()
            );
            directCallbacks.add(method.getName());
        }

        assertTrue(directCallbacks.contains("chooseAbilityForCast"));
        assertTrue(directCallbacks.contains("chooseLandOrSpellAbility"));
        assertTrue(directCallbacks.contains("chooseTargetAmount"));
        assertTrue(directCallbacks.contains("priority"));
        assertEquals(AUDITED_SAFE_PARENT_DELEGATIONS, delegatedCallbacks);
    }

    @Test
    void externallyControlledDiscretionaryCallbacksFailClosedInsteadOfDefaulting() {
        XmageBridgePlayer player = new XmageBridgePlayer(
                "ws80-external",
                RangeOfInfluence.ALL,
                new ExternalDecisionController()
        );

        assertUnsupported(() -> player.chooseAbilityForCast(null, null, false));
        assertUnsupported(() -> player.chooseLandOrSpellAbility(null, null, false));
        assertUnsupported(() -> player.choose(
                Outcome.Neutral, (Target) null, (Ability) null, (Game) null));
        assertUnsupported(() -> player.choose(
                Outcome.Neutral,
                (Target) null,
                (Ability) null,
                (Game) null,
                (Map<String, java.io.Serializable>) null));
        assertUnsupported(() -> player.choose(
                Outcome.Neutral,
                (Cards) null,
                (TargetCard) null,
                (Ability) null,
                (Game) null));
        assertUnsupported(() -> player.chooseTarget(
                Outcome.Neutral, (Target) null, (Ability) null, (Game) null));
        assertUnsupported(() -> player.chooseTarget(
                Outcome.Neutral,
                (Cards) null,
                (TargetCard) null,
                (Ability) null,
                (Game) null));
        assertUnsupported(() -> player.chooseTargetAmount(
                Outcome.Neutral, (TargetAmount) null, (Ability) null, (Game) null));
        assertUnsupported(() -> player.chooseUse(
                Outcome.Neutral, "use?", (Ability) null, (Game) null));
        assertUnsupported(() -> player.chooseUse(
                Outcome.Neutral, "use?", "second?", "Yes", "No", (Ability) null, (Game) null));
        assertUnsupported(() -> player.choose(
                Outcome.Neutral, (Choice) null, (Game) null));
        assertUnsupported(() -> player.choosePile(
                Outcome.Neutral, "pile?", null, null, (Game) null));
        assertUnsupported(() -> player.playMana(null, null, "pay?", (Game) null));
        assertUnsupported(() -> player.announceX(2, 5, "x?", (Game) null, null, false));
        assertUnsupported(() -> player.chooseReplacementEffect(null, null, (Game) null));
        assertUnsupported(() -> player.chooseTriggeredAbility(null, (Game) null));
        assertUnsupported(() -> player.chooseMode(null, null, (Game) null));
        assertUnsupported(() -> player.selectAttackers((Game) null, null));
        assertUnsupported(() -> player.selectBlockers(null, (Game) null, null));
        assertUnsupported(() -> player.getAmount(2, 5, "amount?", null, (Game) null));
        assertUnsupported(() -> player.getMultiAmountWithIndividualConstraints(
                Outcome.Neutral,
                (List<MultiAmountMessage>) null,
                0,
                0,
                MultiAmountType.MANA,
                (Game) null));
    }

    @Test
    void observableOldDefaultsAreNowFailClosed() {
        XmageBridgePlayer externallyControlled = new XmageBridgePlayer(
                "ws80-observable",
                RangeOfInfluence.ALL,
                new ExternalDecisionController()
        );

        // Old stubs returned minimum scalars, index zero, null, or no-ops.
        // Each would have been observable tactical behavior on real cards.
        XmageGameManager.GameException announceX = assertThrows(
                XmageGameManager.GameException.class,
                () -> externallyControlled.announceX(2, 5, "Fireball?", null, null, false)
        );
        assertTrue(announceX.getMessage().contains("UNSUPPORTED_COMPATIBILITY_DECISION"));

        XmageGameManager.GameException amount = assertThrows(
                XmageGameManager.GameException.class,
                () -> externallyControlled.getAmount(2, 5, "Divide?", null, null)
        );
        assertTrue(amount.getMessage().contains("UNSUPPORTED_COMPATIBILITY_DECISION"));

        XmageGameManager.GameException replacement = assertThrows(
                XmageGameManager.GameException.class,
                () -> externallyControlled.chooseReplacementEffect(null, null, null)
        );
        assertTrue(replacement.getMessage().contains("UNSUPPORTED_COMPATIBILITY_DECISION"));

        assertThrows(
                XmageGameManager.GameException.class,
                () -> externallyControlled.selectAttackers(null, null)
        );
        assertThrows(
                XmageGameManager.GameException.class,
                () -> externallyControlled.selectBlockers(null, null, null)
        );
    }

    @Test
    void nullControllerPreservesValidatedBoundedCompatibilityBehavior() {
        XmageBridgePlayer bounded = new XmageBridgePlayer(
                "ws80-bounded",
                RangeOfInfluence.ALL,
                null
        );

        // Validated B3 bounded defaults preserved byte-identically.
        assertFalse(bounded.chooseMulligan(null));
        assertEquals(2, bounded.announceX(2, 5, "x?", null, null, false));
        assertEquals(2, bounded.getAmount(2, 5, "amount?", null, null));
        assertEquals(0, bounded.chooseReplacementEffect(null, null, null));
        assertNull(bounded.chooseTriggeredAbility(null, null));
        assertNull(bounded.chooseMode(null, null, null));
        assertFalse(bounded.chooseUse(Outcome.Neutral, "use?", null, null));
        assertFalse(bounded.chooseUse(
                Outcome.Neutral, "use?", "second?", "Yes", "No", null, null));
        assertFalse(bounded.choose(Outcome.Neutral, (Choice) null, null));
        assertFalse(bounded.choosePile(Outcome.Neutral, "pile?", null, null, null));
        assertFalse(bounded.playMana(null, null, "pay?", null));
        assertNull(bounded.getMultiAmountWithIndividualConstraints(
                Outcome.Neutral, null, 0, 0, MultiAmountType.MANA, null));

        // No-op lifecycle methods remain no-ops on the bounded path.
        bounded.selectAttackers(null, null);
        bounded.selectBlockers(null, null, null);
        bounded.shuffleLibrary(null, null);
        bounded.abort();
        bounded.skip();
    }

    @Test
    void auditedSafeDelegationsRemainNarrowAndNamed() {
        assertFalse(AUDITED_SAFE_PARENT_DELEGATIONS.contains("chooseAbilityForCast"));
        assertFalse(AUDITED_SAFE_PARENT_DELEGATIONS.contains("chooseLandOrSpellAbility"));
        assertEquals(Set.of("chooseRingBearer", "getMultiAmount"), AUDITED_SAFE_PARENT_DELEGATIONS);
    }

    private static void assertUnsupported(ThrowingCall call) {
        XmageGameManager.GameException failure = assertThrows(
                XmageGameManager.GameException.class,
                call::invoke,
                "externally controlled compatibility callback must fail closed"
        );
        assertTrue(
                failure.getMessage().contains("UNSUPPORTED_COMPATIBILITY_DECISION"),
                "failure must carry UNSUPPORTED_COMPATIBILITY_DECISION, observed: "
                        + failure.getMessage()
        );
    }

    private interface ThrowingCall {
        void invoke();
    }

    private static boolean isDiscretionaryCallback(Method method) {
        String name = method.getName();
        return name.startsWith("choose") || NON_CHOOSE_DISCRETIONARY_CALLBACKS.contains(name);
    }
}
