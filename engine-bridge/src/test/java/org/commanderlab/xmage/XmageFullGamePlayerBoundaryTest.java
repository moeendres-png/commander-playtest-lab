package org.commanderlab.xmage;

import mage.constants.RangeOfInfluence;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageFullGamePlayerBoundaryTest {

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
    void everyDirectDiscretionaryPlayerCallbackIsOverriddenOrExplicitlyAuditedAsDelegation()
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

            Method implementation = XmageFullGamePlayer.class.getMethod(
                    method.getName(),
                    method.getParameterTypes()
            );
            assertEquals(
                    XmageFullGamePlayer.class,
                    implementation.getDeclaringClass(),
                    () -> "discretionary Player callback inherited from parent: " + method.toGenericString()
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
    void targetAmountMissingNumericChoiceFailsClosedInsteadOfDefaultingToOne() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws07",
                RangeOfInfluence.ALL,
                controller
        );
        XmageFullGameDecisionController.DecisionResponse response =
                new XmageFullGameDecisionController.DecisionResponse(
                        "decision",
                        "actor",
                        List.of("target"),
                        List.of(),
                        null
                );

        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> player.requireNumericChoice(response, "target_amount")
        );

        assertTrue(failure.getMessage().contains("PILOT_RESPONSE_INVALID"));
        assertTrue(failure.getMessage().contains("numeric choice required for target_amount"));
        assertNotNull(controller.terminalFailure());
        assertTrue(controller.terminalFailure().getMessage().contains("numeric choice required for target_amount"));
    }

    @Test
    void explicitTargetAmountNumericChoiceIsPreserved() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws07",
                RangeOfInfluence.ALL,
                controller
        );
        XmageFullGameDecisionController.DecisionResponse response =
                new XmageFullGameDecisionController.DecisionResponse(
                        "decision",
                        "actor",
                        List.of("target"),
                        List.of(),
                        3
                );

        assertEquals(3, player.requireNumericChoice(response, "target_amount"));
        assertNull(controller.terminalFailure());
    }

    @Test
    void auditedSafeDelegationsRemainNarrowAndNamed() {
        assertFalse(AUDITED_SAFE_PARENT_DELEGATIONS.contains("chooseAbilityForCast"));
        assertFalse(AUDITED_SAFE_PARENT_DELEGATIONS.contains("chooseLandOrSpellAbility"));
        assertEquals(Set.of("chooseRingBearer", "getMultiAmount"), AUDITED_SAFE_PARENT_DELEGATIONS);
    }

    private static boolean isDiscretionaryCallback(Method method) {
        String name = method.getName();
        return name.startsWith("choose") || NON_CHOOSE_DISCRETIONARY_CALLBACKS.contains(name);
    }
}
