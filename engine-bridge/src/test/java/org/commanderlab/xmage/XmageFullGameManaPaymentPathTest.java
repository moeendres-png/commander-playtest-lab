package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.Mana;
import mage.abilities.costs.common.TapSourceCost;
import mage.abilities.keyword.FlyingAbility;
import mage.abilities.mana.SimpleManaAbility;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #961 T-1: a mana payment frame takes the mana abilities of the active permanents and the
 * available mana directly instead of through the whole playable calculation. With
 * {@code commanderlab.verifyManaPaymentPath} on, every payment runs both and they must agree;
 * a mismatch throws, which fails the game. The pilot casts what it can so that payments happen.
 */
class XmageFullGameManaPaymentPathTest {

    private static JsonObject chooseCasting(JsonObject legal) {
        if ("priority".equals(legal.get("decision_class").getAsString())) {
            JsonObject land = null;
            JsonObject cast = null;
            for (var element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                String label = FullGameTestPilot.label(action);
                if (land == null && label.contains("Play ")) {
                    land = action;
                }
                if (cast == null && label.contains("Cast ")) {
                    cast = action;
                }
            }
            if (land != null) {
                return FullGameTestPilot.proposal(legal, land);
            }
            if (cast != null) {
                return FullGameTestPilot.proposal(legal, cast);
            }
        }
        JsonObject decision = legal.getAsJsonObject("decision");
        int min = decision.get("minimum_selections").getAsInt();
        if (min > 1 && min == decision.get("maximum_selections").getAsInt()) {
            // A fixed number of cards (the London mulligan bottom): the first ones by semantic key.
            List<JsonObject> actions = new ArrayList<>();
            legal.getAsJsonArray("actions").forEach(element -> actions.add(element.getAsJsonObject()));
            actions.sort(Comparator.comparing(FullGameTestPilot::key));
            JsonObject proposal = FullGameTestPilot.proposal(legal, actions.get(0));
            JsonArray ids = new JsonArray();
            for (JsonObject action : actions.subList(0, min)) {
                String actionId = action.get("action_id").getAsString();
                ids.add(actionId.substring(actionId.indexOf(':') + 1));
            }
            proposal.getAsJsonObject("choices").add("selected_option_ids", ids);
            return proposal;
        }
        return FullGameTestPilot.choose(legal);
    }

    private static int play(XmageFullGameSession session, int decisions) {
        int answered = 0;
        while (answered < decisions) {
            JsonObject status = session.pendingDecisionPayload();
            if (status.get("decision") == null || status.get("decision").isJsonNull()) {
                return answered;
            }
            session.submitAction(chooseCasting(session.legalActionsPayload()));
            answered++;
        }
        return answered;
    }

    @Test
    void directPathAgreesWithTheFullPlayableCalculationOnEveryPayment() throws Exception {
        String property = XmageFullGamePlayer.VERIFY_MANA_PAYMENT_PATH;
        String before = System.getProperty(property);
        long verified = XmageFullGamePlayer.MANA_PATH_VERIFIED.get();
        System.setProperty(property, "true");
        try {
            for (long seed : new long[] {7101L, 7102L}) {
                XmageFullGameSession session = FullGameTestPilot.realDeckSession("t1-verify-" + seed, 4, seed);
                try {
                    assertTrue(play(session, 1200) > 300, "the game must run for a while");
                } finally {
                    session.shutdownGame();
                }
            }
        } finally {
            if (before == null) {
                System.clearProperty(property);
            } else {
                System.setProperty(property, before);
            }
        }
        assertTrue(XmageFullGamePlayer.MANA_PATH_VERIFIED.get() - verified >= 20,
                "payments must have been compared: " + (XmageFullGamePlayer.MANA_PATH_VERIFIED.get() - verified));
    }

    @Test
    void withoutTheSwitchPaymentsTakeTheDirectPath() throws Exception {
        assertFalse(Boolean.getBoolean(XmageFullGamePlayer.VERIFY_MANA_PAYMENT_PATH));
        long fast = XmageFullGamePlayer.MANA_PATH_FAST.get();
        long full = XmageFullGamePlayer.MANA_PATH_FULL.get();
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("t1-fast", 4, 7103L);
        try {
            assertTrue(play(session, 800) > 200, "the game must run for a while");
        } finally {
            session.shutdownGame();
        }
        assertTrue(XmageFullGamePlayer.MANA_PATH_FAST.get() - fast >= 10,
                "payments must take the direct path: " + (XmageFullGamePlayer.MANA_PATH_FAST.get() - fast));
        assertEquals(0, XmageFullGamePlayer.MANA_PATH_FULL.get() - full,
                "these decks have no mana ability outside the battlefield");
    }

    @Test
    void aManaAbilityOutsideTheBattlefieldKeepsTheFullCalculation() throws Exception {
        long full = XmageFullGamePlayer.MANA_PATH_FULL.get();
        // Simian Spirit Guide has a mana ability that works from the hand.
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("t1-spirit-guide", 4, 7104L,
                "Simian Spirit Guide");
        try {
            assertTrue(play(session, 800) > 200, "the game must run for a while");
        } finally {
            session.shutdownGame();
        }
        assertTrue(XmageFullGamePlayer.MANA_PATH_FULL.get() - full >= 10,
                "payments must take the full calculation: " + (XmageFullGamePlayer.MANA_PATH_FULL.get() - full));
    }

    @Test
    void aManaAbilityGivenToACardOutsideTheBattlefieldIsFound() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("t1-granted", 4, 7105L);
        try {
            assertTrue(play(session, 60) > 20, "the game must run for a while");
            assertFalse(session.pendingDecisionPayload().get("decision").isJsonNull());
            Game game = session.restorationGame();
            // The engine is parked on a decision, so the state can be touched: give the bottom card of
            // a library what an effect applied in the last effects cycle would give it.
            Card target = game.getPlayer(game.getPlayerList().get(0)).getLibrary().getFromBottom(game);
            assertNotNull(target, "the library holds a card");
            assertFalse(XmageFullGamePlayer.grantedManaAbilityOutsideBattlefield(game));

            game.getState().addOtherAbility(target, FlyingAbility.getInstance());
            assertFalse(XmageFullGamePlayer.grantedManaAbilityOutsideBattlefield(game),
                    "an ability that is no mana ability changes nothing");

            game.getState().addOtherAbility(target,
                    new SimpleManaAbility(Zone.LIBRARY, Mana.GreenMana(1), new TapSourceCost()));
            assertTrue(XmageFullGamePlayer.grantedManaAbilityOutsideBattlefield(game));
        } finally {
            session.shutdownGame();
        }
    }
}
