package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PB-03 restoration-seam characterization salvaged from the Muse XHIGH donor.
 *
 * <p>This is a test-only discriminator against the current
 * {@code XmageNativeStateRestoration} seam. It does not make the historical
 * Muse Python tier table canonical and grants no FULL107 row credit. Rows that
 * parse here still require obligation execution before PASS; rows that fail
 * closed pin the exact unsupported mechanism so qualification cannot silently
 * treat a blanket capability flag or fixture-name prefix as evidence.</p>
 */
class XmagePb03DimensionAdmissionTest {

    private static final long SEED = 424242L;

    private static final List<String> TIER_1 = List.of(
            "MICRO_COMBAT",
            "MICRO_CONTINUOUS_EFFECTS",
            "MICRO_COSTS",
            "MICRO_MODES",
            "MICRO_PREVENTION",
            "MICRO_REPLACEMENT",
            "MICRO_STATE_BASED_ACTIONS",
            "MICRO_TRIGGERS",
            "WS05-CMD-ELIM-4",
            "WS05-MP-BLOCK-4",
            "WS05-MP-COMBAT-4",
            "WS05-MP-COMBAT-5");

    private static final List<String> TIER_2_STACK = List.of(
            "WS05-CMD-ZONE-GY-YES",
            "WS05-CMD-ZONE-GY-NO",
            "WS05-CMD-ZONE-EXILE-YES",
            "WS05-CMD-ZONE-EXILE-NO",
            "WS05-CMD-ZONE-HAND-YES",
            "WS05-CMD-ZONE-HAND-NO",
            "WS05-CMD-ZONE-LIB-NO",
            "WS05-CMD-ZONE-LIB-YES",
            "MICRO_COPY",
            "MICRO_MANA_PAYMENT",
            "MICRO_PRIORITY",
            "MICRO_STACK",
            "MICRO_ZONE_CHANGES",
            "MICRO_RULES_RANDOMNESS",
            "WS05-MP-PRIO-3",
            "WS05-MP-PRIO-5",
            "WS05-MP-ELIM-STACK-3");

    @Test
    void tier1RowsParseAsIs() {
        for (String fixture : TIER_1) {
            XmageNativeStateRestoration.Plan plan =
                    XmageNativeStateRestoration.planFromFrozenRecord(
                            XmageNativeStateRestorationTest.frozenRecord(fixture),
                            "pb03-admit-" + fixture, SEED);
            assertTrue(plan.playerCount() >= 2, fixture + " must plan 2+ players");
        }
    }

    @Test
    void tier2StackRowsFailClosedWithUnsupportedZone() {
        for (String fixture : TIER_2_STACK) {
            try {
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord(fixture),
                        "pb03-admit-" + fixture, SEED);
                fail(fixture + " carries a stack-zone object and must fail closed");
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                assertTrue(exc.getMessage().startsWith("UNSUPPORTED_ZONE"),
                        fixture + " must name UNSUPPORTED_ZONE, got: " + exc.getMessage());
            }
        }
    }

    @Test
    void controlDivergenceRowsFailClosed() {
        // Both rows also attach Control Magic, a second unsupported dimension
        // that parsing refuses first. Each mechanism is checked on its own: the
        // full record fails closed on the attachment, and without it on the
        // divergence, which validatePlan (constructor phase) rejects after
        // planFromFrozenRecord parses, so it is routed through restorationFor
        // to match the production construction path exactly.
        for (String fixture : List.of("MICRO_CONTROL", "WS05-MP-ELIM-CONTROL-3")) {
            JsonObject record = XmageNativeStateRestorationTest.frozenRecord(fixture).deepCopy();
            try {
                XmageNativeStateRestoration.planFromFrozenRecord(
                        record, "pb03-admit-attached-" + fixture, SEED);
                fail(fixture + " requests an attachment and must fail closed");
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                assertTrue(exc.getMessage().startsWith("UNSUPPORTED_ATTACHMENTS"),
                        fixture + " must name UNSUPPORTED_ATTACHMENTS, got: " + exc.getMessage());
            }
            for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
                element.getAsJsonObject().remove("attached_to");
            }
            XmageNativeStateRestoration.Plan plan =
                    XmageNativeStateRestoration.planFromFrozenRecord(
                            record, "pb03-admit-" + fixture, SEED);
            try {
                XmageNativeStateRestorationTest.restorationFor(plan);
                fail(fixture + " carries owner/controller divergence and must fail closed");
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                assertTrue(exc.getMessage().startsWith("UNSUPPORTED_CONTROL_DIVERGENCE"),
                        fixture + " must name UNSUPPORTED_CONTROL_DIVERGENCE, got: "
                                + exc.getMessage());
            }
        }
    }

    @Test
    void tier3LifeZeroPreconditionsFailClosedAtRuntime() {
        for (String fixture : List.of(
                "WS05-MP-ELIM-5",
                "WS05-MP-ELIM-PRIO-3",
                "WS05-MP-ELIM-TURN-3",
                "WS05-MP-ELIM-OWNED-3",
                "WS05-MP-ELIM-STACK-3",
                "WS05-MP-ELIM-CONTROL-3")) {
            JsonObject record =
                    XmageNativeStateRestorationTest.frozenRecord(fixture);
            boolean lifeZeroFound = false;
            for (JsonElement element : record.getAsJsonArray("players")) {
                JsonObject player = element.getAsJsonObject();
                if (player.get("life").getAsInt() == 0) {
                    lifeZeroFound = true;
                }
            }
            assertTrue(lifeZeroFound,
                    fixture + " must request a 0-life player (LIFE_ZERO_PRESTART)");
        }
        // The four rows without other blocking dimensions are characterized
        // through the real full-game arrival path. The engine re-derives
        // starting life during game start, so the requested zero-life state
        // fails closed instead of manufacturing elimination.
        XmageFullGameElimExecutionTest.characterizeElimBlocker(
                "WS05-MP-ELIM-OWNED-3", "pb03-admit-elim-owned-3", "P2", 3);
        XmageFullGameElimExecutionTest.characterizeElimBlocker(
                "WS05-MP-ELIM-PRIO-3", "pb03-admit-elim-prio-3", "P2", 3);
        XmageFullGameElimExecutionTest.characterizeElimBlocker(
                "WS05-MP-ELIM-TURN-3", "pb03-admit-elim-turn-3", "P2", 3);
        XmageFullGameElimExecutionTest.characterizeElimBlocker(
                "WS05-MP-ELIM-5", "pb03-admit-elim-5", "P3", 5);
    }

    @Test
    void turn5ParsesButDoesNotEarnExtraTurnBehaviorCredit() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("WS05-MP-TURN-5"),
                        "pb03-admit-turn5", SEED);
        assertEquals(5, plan.playerCount());

        // Admission/construction is deliberately not extra-turn behavior proof.
        // In particular, a frozen graveyard placement for Nexus of Fate cannot
        // be treated as a resolved-spell postcondition because the card's own
        // replacement effect prevents that graveyard outcome. TURN-5 therefore
        // requires genuine runtime casts/order observation in the Tier-2 suite;
        // this discriminator grants no row credit.
    }
}
