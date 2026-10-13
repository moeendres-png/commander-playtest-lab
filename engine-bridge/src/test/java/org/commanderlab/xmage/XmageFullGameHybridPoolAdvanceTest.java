package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.Mana;
import mage.abilities.costs.mana.ManaCostsImpl;
import mage.constants.ManaType;
import mage.constants.Zone;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #755: a pool option may only be marked {@code advances_payment} when that
 * mana can pay part of the unpaid cost. The pinned engine's
 * {@code HybridManaCost.testPay} falls through its color switch
 * (HybridManaCost.java:62-88) and accepts every colored mana for a two-color
 * hybrid symbol, so green mana was reported as advancing {@code {B/R}} and the
 * payment frame repeated without progress.
 */
class XmageFullGameHybridPoolAdvanceTest {

    private static final String AVATAR = "Avatar of Discord"; // {B/R}{B/R}{B/R}

    /** Red before the fix: green in the pool was marked as advancing {B/R}. */
    @Test
    void offColorPoolManaDoesNotAdvanceAHybridCost() {
        XmageMultiplayerScenario s = scenario("issue755-hybrid-off-color");
        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), AVATAR));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        s.submit(labelled(s, "Forest"));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());

        JsonObject green = labelled(s, "Spend green mana from pool");
        assertFalse(advances(green),
                "REGRESSION GUARD: green mana cannot pay {B/R}, so spending it does not "
                        + "advance the payment: " + green);
    }

    /** Positive control: an on-color land pays the hybrid cost to completion. */
    @Test
    void onColorManaPaysTheHybridCost() {
        XmageMultiplayerScenario s = scenario("issue755-hybrid-on-color");
        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), AVATAR));
        int blackSpends = 0;
        for (int i = 0; i < 3; i++) {
            assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
            s.submit(labelled(s, "Swamp"));
            if ("mana_payment".equals(s.decisionClass())
                    && s.labels().contains("Spend black mana from pool")) {
                JsonObject black = labelled(s, "Spend black mana from pool");
                assertTrue(advances(black), "black mana pays {B/R}: " + black);
                s.submit(black);
                blackSpends++;
            }
        }
        assertTrue(blackSpends > 0, "the on-color pool option was checked at least once");
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull());
        assertFalse(s.session.restorationGame().getStack().isEmpty(),
                "the hybrid cost was paid in full and the spell is on the stack");
    }

    /**
     * Consistency control under Mycosynth Lattice ("spend mana as though it
     * were mana of any color"): the bridge pays from the pool by unlocking one
     * type, and the pinned ManaPool.pay rejects a manual spend whose type was
     * not unlocked before any as-though remap (ManaPool.java:115). The engine
     * therefore does not take green for {B/R} here, and the projection must say so.
     */
    @Test
    void projectionMatchesTheEngineUnderSpendAsAnyColor() {
        XmageMultiplayerScenario s = scenario("issue755-hybrid-lattice", "Mycosynth Lattice");
        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), AVATAR));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        s.submit(labelled(s, "Forest"));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        JsonObject green = labelled(s, "Spend green mana from pool");
        assertFalse(advances(green), "projection: " + green);
        List<String> before = s.labels();
        s.submit(green);
        assertEquals(before, s.labels(), "engine witness: the green spend paid nothing");
    }

    /** The helper on real engine cost objects, one per relevant component kind. */
    @Test
    void advanceIsDecidedPerComponent() {
        ManaCostsImpl<mage.abilities.costs.mana.ManaCost> hybrid = new ManaCostsImpl<>("{B/R}");
        assertTrue(XmageFullGamePlayer.advancesUnpaid(hybrid, Mana.BlackMana(1), ManaType.BLACK));
        assertTrue(XmageFullGamePlayer.advancesUnpaid(hybrid, Mana.RedMana(1), ManaType.RED));
        assertFalse(XmageFullGamePlayer.advancesUnpaid(hybrid, Mana.GreenMana(1), ManaType.GREEN));
        assertFalse(XmageFullGamePlayer.advancesUnpaid(hybrid, Mana.ColorlessMana(1), ManaType.COLORLESS));

        ManaCostsImpl<mage.abilities.costs.mana.ManaCost> colorlessOrWhite = new ManaCostsImpl<>("{C/W}");
        assertTrue(colorlessOrWhite.get(0) instanceof mage.abilities.costs.mana.ColorlessHybridManaCost);
        assertTrue(XmageFullGamePlayer.advancesUnpaid(colorlessOrWhite, Mana.WhiteMana(1), ManaType.WHITE));
        assertTrue(XmageFullGamePlayer.advancesUnpaid(colorlessOrWhite, Mana.ColorlessMana(1), ManaType.COLORLESS));
        assertFalse(XmageFullGamePlayer.advancesUnpaid(colorlessOrWhite, Mana.GreenMana(1), ManaType.GREEN),
                "{C/W} cannot be paid with green (the engine's testPay falls through to G)");

        ManaCostsImpl<mage.abilities.costs.mana.ManaCost> mixed = new ManaCostsImpl<>("{1}{B/R}");
        assertTrue(XmageFullGamePlayer.advancesUnpaid(mixed, Mana.GreenMana(1), ManaType.GREEN),
                "green still pays the generic part");

        ManaCostsImpl<mage.abilities.costs.mana.ManaCost> twoOrWhite = new ManaCostsImpl<>("{2/W}");
        assertTrue(XmageFullGamePlayer.advancesUnpaid(twoOrWhite, Mana.GreenMana(1), ManaType.GREEN),
                "a mono-hybrid {2/W} is still answered by the engine: any mana pays its generic option");
    }

    private static XmageMultiplayerScenario scenario(String tag, String... battlefield) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int i = 0; i < battlefield.length; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", battlefield[i], 10 + i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", AVATAR, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 0, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        assertEquals("P1", s.actor());
        return s;
    }

    private static boolean advances(JsonObject action) {
        return action.getAsJsonObject("metadata").getAsJsonObject("xmage_option_metadata")
                .get("advances_payment").getAsBoolean();
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String prefix) {
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.getAsJsonObject("metadata").get("label").getAsString().startsWith(prefix)) {
                return candidate;
            }
        }
        assertNotNull(null, "no option labelled " + prefix + "*: " + s.labels());
        return null;
    }
}
