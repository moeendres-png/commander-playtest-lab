package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.ManaType;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #752: while a mana ability's own cost is being paid, no payment frame inside
 * that payment may offer that same ability again, whether directly or through
 * another mana ability in between.
 *
 * <p>Three Tree Mascot (Oracle): "{1}: Add one mana of any color. Activate only
 * once each turn." ({@code LimitedTimesPerTurnActivatedManaAbility}). The
 * pinned engine counts an activation only after its costs are paid
 * ({@code ActivatedAbilityImpl.activate}), so while the first {1} is unpaid
 * the ability still reads as activatable. Offering it lets a pilot nest the
 * same payment without bound, and in a real 6P game the engine later refused
 * the stale offer. That aborted the game with XMAGE_ACTION_EXECUTION_FAILED /
 * "mana activation failed".
 */
class XmageFullGameSelfFundingManaAbilityTest {

    private static final String MASCOT = "Three Tree Mascot";
    private static final String FOREST = "Forest";

    /**
     * Red before the fix: the frame paying the Mascot's {1} offered the Mascot
     * itself. Green after: only the Forests fund it, the ability resolves and
     * the player gets the chosen color.
     */
    @Test
    void paymentForAManaAbilityDoesNotOfferThatAbility() {
        XmageMultiplayerScenario s = scenario("issue752-self-funding");
        Game game = s.session.restorationGame();

        s.submit(labelled(s, MASCOT));
        assertEquals("mana_payment", s.decisionClass(),
                "activating the Mascot asks for its {1}: " + s.labels());
        assertTrue(s.labels().stream().noneMatch(label -> label.contains(MASCOT)),
                "REGRESSION GUARD: the Mascot cannot fund its own activation: " + s.labels());
        assertEquals(2, s.labels().stream().filter(label -> label.startsWith(FOREST)).count(),
                "every other source stays offered: " + s.labels());

        s.submit(labelled(s, FOREST));
        if ("mana_payment".equals(s.decisionClass())) {
            // The Forest's {G} lands in the pool; the pilot spends it.
            s.submit(labelled(s, "Spend green"));
        }
        assertEquals("choice", s.decisionClass(), "the ability resolves: " + s.labels());
        s.submit(labelled(s, "Blue"));

        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull());
        assertEquals("priority", s.decisionClass(), "the game continues: " + s.labels());
        assertEquals(1, s.seats.get("P1").getManaPool().get(ManaType.BLUE),
                "the Mascot added the chosen color");
        assertFalse(game.getState().isGameOver());
    }

    /**
     * The indirect cycle: two Mascots. The frame paying the first offers the
     * second, but the frame paying the second, opened from the first's frame,
     * must not offer the first again. RED if only the directly paid ability
     * is excluded.
     */
    @Test
    void nestedPaymentDoesNotOfferAnAbilityStillBeingPaidFurtherUp() {
        XmageMultiplayerScenario s = scenario("issue752-two-mascots", 2);

        s.submit(labelled(s, MASCOT));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        assertEquals(1, s.labels().stream().filter(label -> label.startsWith(MASCOT)).count(),
                "the other Mascot is not mid-activation and stays offered: " + s.labels());

        s.submit(labelled(s, MASCOT));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        assertTrue(s.labels().stream().noneMatch(label -> label.startsWith(MASCOT)),
                "REGRESSION GUARD: both Mascots are mid-activation, neither may fund the "
                        + "other: " + s.labels());
    }

    /** The guard is narrow: only keys recorded as in flight are excluded. */
    @Test
    void onlyAbilitiesBeingPaidAreExcluded() {
        XmageMultiplayerScenario s = scenario("issue752-predicate", 2);
        Game game = s.session.restorationGame();
        XmageFullGamePlayer player = (XmageFullGamePlayer) s.seats.get("P1");
        List<mage.abilities.Ability> mascots = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> MASCOT.equals(p.getName()))
                .map(p -> p.getAbilities().stream().filter(mage.abilities.Ability::isManaAbility)
                        .findFirst().orElseThrow())
                .toList();
        mage.abilities.Ability forest = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> FOREST.equals(p.getName())).findFirst().orElseThrow()
                .getAbilities().stream().filter(mage.abilities.Ability::isManaAbility)
                .findFirst().orElseThrow();
        assertEquals(2, mascots.size());

        player.recordManaPaymentInFlightForBoundaryTest(mascots.get(0));
        assertTrue(player.manaActivationInFlight(mascots.get(0).copy()),
                "the engine's activated copy keeps the original id and source");
        assertFalse(player.manaActivationInFlight(mascots.get(1)),
                "the same card on another permanent is a different source and stays offered");
        assertFalse(player.manaActivationInFlight(forest),
                "another source's ability is never excluded");
    }

    private static XmageMultiplayerScenario scenario(String tag) {
        return scenario(tag, 1);
    }

    private static XmageMultiplayerScenario scenario(String tag, int mascots) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int i = 0; i < mascots; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", MASCOT, i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", FOREST, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", FOREST, 1, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        assertEquals("P1", s.actor(), "control: P1 holds priority");
        return s;
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String fragment) {
        JsonObject match = null;
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.getAsJsonObject("metadata").get("label").getAsString().startsWith(fragment)) {
                if (match == null) {
                    match = candidate;
                }
            }
        }
        assertNotNull(match, "no option labelled " + fragment + "*: " + s.labels());
        return match;
    }
}
